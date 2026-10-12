"""pytest checks. Unit tests run anywhere; warehouse tests skip when data/aircraft_readiness.duckdb is missing."""
import sys
from pathlib import Path
import duckdb, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DB = ROOT / "data/aircraft_readiness.duckdb"
needs_db = pytest.mark.skipif(not DB.exists(), reason="run scripts/run.sh first to build the warehouse")


def test_complete_window_stops_at_gap(tmp_path):
    from build import complete_window
    names = ["sdr_2025-01-01_2025-01-05", "sdr_2025-01-06_2025-01-10", "sdr_2025-01-16_2025-01-20"]
    files = [str(tmp_path / f"{n}.parquet") for n in names]
    keep, start, end = complete_window(files)
    assert len(keep) == 2 and str(start) == "2025-01-01" and str(end) == "2025-01-10"


def test_repeat_and_interval_logic_on_toy_data():
    """Runs the real SQL on a tiny hand-made SDR set."""
    con = duckdb.connect()
    con.execute("CREATE SCHEMA raw")
    rows = [  # id, date, sub, op, jasc, stage, precaution, tail, hours, cycles
        ("A1", "1/1/2025 0:00:00", "1/2/2025 0:00:00", "OPX", "3230", "TO", "C", "N1", "1000.0", "500.0"),
        ("A2", "1/10/2025 0:00:00", "1/12/2025 0:00:00", "OPX", "3210", "LD", "A", "N1", "1050.0", "520.0"),
        ("A3", "3/30/2025 0:00:00", "3/31/2025 0:00:00", "OPX", "3210", "CR", "K", "N1", "1500.0", "700.0"),
        ("B1", "1/5/2025 0:00:00", "1/5/2025 0:00:00", "OPX", "5310", "IN", "K", "N2", "nan", "nan"),
    ]
    cols = ["OperatorControlNumber", "DifficultyDate", "SubmissionDate", "OperatorDesignator", "JASCCode",
            "StageOfOperationCode", "PrecautionaryProcedureA", "RegistryNNumber", "AircraftTotalTime", "AircraftTotalCycles"]
    df = pd.DataFrame(rows, columns=cols)
    for c in ["SubmitterTypeCode", "SDRType", "NatureOfConditionA", "HowDiscoveredCode", "AircraftMake", "AircraftModel",
              "AircraftSerialNumber", "PartName", "PartNumber", "PartCondition", "Discrepancy"]:
        df[c] = "nan"
    con.register("d", df); con.execute("CREATE TABLE raw.sdrs AS SELECT * FROM d")
    con.execute("CREATE TABLE raw.registry_master AS SELECT 'N1' \"N-NUMBER\", '1' \"MFR MDL CODE\", '2010' \"YEAR MFR\", '3' \"TYPE REGISTRANT\", 'X' \"NAME\", 'SD' \"STATE\", '20100101' \"AIR WORTH DATE\"")
    con.execute("CREATE TABLE raw.registry_acftref AS SELECT '1' CODE, 'M' MFR, 'T' MODEL, '2' \"NO-ENG\", '9' \"NO-SEATS\", 'CLASS 3' \"AC-WEIGHT\"")
    con.execute(f"CREATE TABLE raw.ref_jasc AS SELECT * FROM read_csv('{ROOT}/data/ref/jasc_codes.csv', all_varchar=true)")
    con.execute(f"CREATE TABLE raw.ref_codes AS SELECT * FROM read_csv('{ROOT}/data/ref/sdr_code_labels.csv')")
    con.execute(f"CREATE TABLE raw.ref_gao AS SELECT * FROM read_csv('{ROOT}/data/ref/gao_mission_capable_rates.csv')")
    con.execute("CREATE TABLE raw.cmapss AS SELECT 'FD001' dataset, 1 unit, range AS cycle FROM range(1, 201)")
    for f in sorted((ROOT / "sql").glob("0*.sql")):
        con.execute(f.read_text())
    f = con.sql("SELECT sdr_id, is_repeat_30d, is_operational_interruption, report_lag_days FROM mart.fct_discrepancy ORDER BY 1").df().set_index("sdr_id")
    assert bool(f.loc["A2", "is_repeat_30d"])          # same tail, ATA 32, 9 days later, both in flight
    assert not bool(f.loc["A3", "is_repeat_30d"])      # 79 days later: outside window
    assert bool(f.loc["A1", "is_operational_interruption"]) and not bool(f.loc["A3", "is_operational_interruption"])
    assert f.loc["A2", "report_lag_days"] == 2
    iv = con.sql("SELECT hours_between, is_valid FROM mart.fct_tail_interval ORDER BY to_date").fetchall()
    assert iv[0] == (50.0, True) and iv[1] == (450.0, True)
    assert con.sql("SELECT cycles_to_failure FROM mart.fct_engine_run").fetchone()[0] == 200
    assert con.sql("SELECT count(*) FROM mart.fct_mc_rate_benchmark").fetchone()[0] == 56


def test_synthetic_layer_is_flagged_and_reproducible():
    import synthetic
    out = []
    for _ in range(2):
        con = duckdb.connect(); con.execute("CREATE SCHEMA mart")
        con.execute("CREATE TABLE mart.fct_tail_interval AS SELECT 3000.0 hours_between, TRUE ends_in_interruption, TRUE is_valid")
        con.execute("CREATE TABLE mart.dim_ata AS SELECT '3210' ata_key, '32' ata_chapter")
        con.execute("CREATE TABLE mart.fct_discrepancy AS SELECT '3210' ata_key, TRUE is_operational_interruption")
        synthetic.build(con)
        for t in ["syn_fct_status_daily", "syn_fct_work_order", "syn_fct_requisition"]:
            assert con.sql(f"SELECT bool_and(is_synthetic) FROM mart.{t}").fetchone()[0] in (True, None)
        out.append(con.sql("SELECT * FROM mart.syn_kpi_fleet").fetchall())
    assert out[0] == out[1]


@needs_db
def test_warehouse_quality_checks_pass():
    from build import run_checks
    con = duckdb.connect(str(DB), read_only=True)
    assert run_checks(con) == []


@needs_db
def test_exports_exist_and_match_warehouse():
    con = duckdb.connect(str(DB), read_only=True)
    n = con.sql("SELECT count(*) FROM mart.fct_discrepancy").fetchone()[0]
    p = ROOT / "data/export/fct_discrepancy.parquet"
    assert p.exists() and len(pd.read_parquet(p)) == n
