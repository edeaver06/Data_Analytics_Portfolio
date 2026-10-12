"""Build the aircraft-readiness DuckDB warehouse, run data-quality checks and export model-ready tables.

Usage: python src/build.py [--months YYYY-MM ...]
Inputs (see README "Run it"): data/raw/sdrs/*.parquet, data/raw/registry/{MASTER,ACFTREF}.txt,
data/raw/cmapss/train_FD00*.txt, data/ref/*.csv
"""
import glob, os, sys
from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/aircraft_readiness.duckdb"
EXPORT = ROOT / "data/export"
sys.path.insert(0, str(ROOT / "src"))
import synthetic  # noqa: E402

EXPORT_TABLES = ["dim_date", "dim_aircraft", "dim_ata", "dim_operator", "dim_part", "dim_sdr_code", "dim_stage", "dim_precaution",
                 "fct_discrepancy", "fct_tail_interval", "fct_engine_run", "fct_mc_rate_benchmark",
                 "kpi_mtbr_by_model", "kpi_repeat_by_ata", "kpi_monthly", "kpi_report_lag", "kpi_top_parts", "kpi_engine_mtbf",
                 "syn_dim_tail", "syn_fct_status_daily", "syn_fct_work_order", "syn_fct_requisition", "syn_fct_backlog_daily", "syn_assumptions", "syn_kpi_fleet"]


def complete_window(files):
    """Use the longest run of consecutive downloaded windows starting at the earliest one."""
    import datetime as dt
    wins = sorted((dt.date.fromisoformat(Path(f).stem.split("_")[1]), dt.date.fromisoformat(Path(f).stem.split("_")[2]), f) for f in files)
    keep, end = [], None
    for a, b, f in wins:
        if end is None or a == end + dt.timedelta(days=1):
            keep.append(f); end = b
        else:
            break
    return keep, wins[0][0], end


def load_raw(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    cutoff = os.environ.get("SDR_END", "2025-06-29")  # analysis window ends on a whole month
    files = [f for f in glob.glob(str(ROOT / "data/raw/sdrs/*.parquet")) if Path(f).stem.split("_")[2] <= cutoff]
    files, start, end = complete_window(files)
    con.execute(f"CREATE OR REPLACE TABLE raw.sdrs AS SELECT * FROM read_parquet({[str(f) for f in files]}, union_by_name=true)")
    reg = ROOT / "data/raw/registry"
    con.execute(f"CREATE OR REPLACE TABLE raw.registry_master AS SELECT * FROM read_csv('{reg}/MASTER.txt', all_varchar=true, header=true, quote='')")
    con.execute(f"CREATE OR REPLACE TABLE raw.registry_acftref AS SELECT * FROM read_csv('{reg}/ACFTREF.txt', all_varchar=true, header=true, quote='')")
    cols = ["unit", "cycle"] + [f"op{i}" for i in range(1, 4)] + [f"s{i}" for i in range(1, 22)]
    frames = []
    for f in sorted(glob.glob(str(ROOT / "data/raw/cmapss/train_FD00*.txt"))):
        d = pd.read_csv(f, sep=r"\s+", header=None).iloc[:, :26]; d.columns = cols
        d.insert(0, "dataset", Path(f).stem.replace("train_", "")); frames.append(d)
    con.register("cm", pd.concat(frames)); con.execute("CREATE OR REPLACE TABLE raw.cmapss AS SELECT * FROM cm")
    for t, f in [("ref_jasc", "jasc_codes.csv"), ("ref_codes", "sdr_code_labels.csv"), ("ref_gao", "gao_mission_capable_rates.csv")]:
        con.execute(f"CREATE OR REPLACE TABLE raw.{t} AS SELECT * FROM read_csv('{ROOT}/data/ref/{f}', header=true, all_varchar={'true' if t=='ref_jasc' else 'false'})")
    return start, end


def run_sql(con):
    for f in sorted((ROOT / "sql").glob("0*.sql")):
        con.execute(f.read_text())


def run_checks(con):
    fails = []
    for f in sorted((ROOT / "sql/tests").glob("*.sql")):
        n = con.execute(f"SELECT count(*) FROM ({f.read_text().rstrip().rstrip(';')})").fetchone()[0]
        print(f"  [{'PASS' if n == 0 else 'FAIL'}] {f.stem} ({n} bad rows)")
        if n: fails.append(f.stem)
    return fails


def export(con):
    EXPORT.mkdir(parents=True, exist_ok=True)
    for t in EXPORT_TABLES:
        con.execute(f"COPY mart.{t} TO '{EXPORT}/{t}.csv' (HEADER)")
        con.execute(f"COPY mart.{t} TO '{EXPORT}/{t}.parquet' (FORMAT parquet)")


APP_QUERIES = {
    "discrepancy": """SELECT f.difficulty_date, dd.year_month, a.ata_chapter, a.ata_chapter_name, ac.make, ac.model,
        o.operator_code, p.part_name, f.part_condition, pr.precaution_label, f.is_in_operation, f.is_operational_interruption,
        f.is_repeat_30d, f.report_lag_days
        FROM mart.fct_discrepancy f JOIN mart.dim_date dd ON dd.date_key = f.difficulty_date_key
        JOIN mart.dim_ata a USING (ata_key) JOIN mart.dim_aircraft ac USING (aircraft_key)
        JOIN mart.dim_operator o USING (operator_key) JOIN mart.dim_part p USING (part_key)
        JOIN mart.dim_precaution pr USING (precaution_code)""",
    "tail_interval": """SELECT a.make, a.model, i.hours_between, i.cycles_between, i.days_between, i.ends_in_interruption
        FROM mart.fct_tail_interval i JOIN mart.dim_aircraft a USING (aircraft_key) WHERE i.is_valid""",
    "engine_run": "SELECT * FROM mart.fct_engine_run",
    **{t: f"SELECT * FROM mart.{t}" for t in ["syn_fct_status_daily", "syn_fct_work_order", "syn_fct_requisition",
                                               "syn_fct_backlog_daily", "syn_assumptions", "syn_kpi_fleet"]},
}


def export_app(con):
    """Small parquet extract so the Streamlit app runs with no build step (GAO data deliberately excluded)."""
    d = ROOT / "app/data"; d.mkdir(parents=True, exist_ok=True)
    for name, q in APP_QUERIES.items():
        con.execute(f"COPY ({q}) TO '{d}/{name}.parquet' (FORMAT parquet, COMPRESSION zstd)")


def main():
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    start, end = load_raw(con)
    print(f"SDR window: {start} to {end}")
    run_sql(con)
    synthetic.build(con)
    fails = run_checks(con)
    export(con)
    export_app(con)
    con.close()
    if fails:
        sys.exit(f"Data-quality checks failed: {fails}")


if __name__ == "__main__":
    main()
