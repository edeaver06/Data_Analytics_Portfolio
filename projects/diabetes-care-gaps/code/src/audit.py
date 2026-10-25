"""Independent audit: recompute every KPI with plain SQL (sql/01_views.sql) and compare to the R marts.
Also scans project text for phone numbers, street addresses, a banned descriptor word and secrets."""
import re, sqlite3, sys, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
c = sqlite3.connect(root / "data/clean/care_gaps.sqlite")
results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail)); print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""))

measures = ["a1c_tested", "a1c_lt8", "a1c_gt9", "bp_lt140_90", "eye_exam", "kidney_eval", "statin_40_75"]
sql_members = f"""
WITH m AS (
  SELECT s.*, p.sex,
    CASE WHEN s.age <= 44 THEN '18-44' WHEN s.age <= 64 THEN '45-64' ELSE '65-75' END AS age_band,
    COALESCE((SELECT CASE WHEN pn.payer_name IN ('Medicare','Medicaid','Dual Eligible') THEN pn.payer_name
                          WHEN pn.payer_name = 'NO_INSURANCE' OR pn.payer_name IS NULL THEN 'Uninsured' ELSE 'Commercial' END
              FROM stg_cover pn WHERE pn.patient = s.patient AND pn.start <= y.p_end AND (pn."end" IS NULL OR pn."end" >= y.p_end)
              ORDER BY pn.start DESC LIMIT 1), 'Uninsured') AS payer_group
  FROM v_sql_member s JOIN stg_patients p USING (patient) JOIN v_years y USING (my))
SELECT * FROM m"""
c.execute("DROP TABLE IF EXISTS audit_sql_member"); c.execute("CREATE TEMP TABLE audit_sql_member AS " + sql_members)

# 1. every KPI row, every breakdown
mism = 0; n = 0
for bd, col in [("overall", "'All'"), ("age_band", "age_band"), ("sex", "sex"), ("payer_group", "payer_group")]:
    for ms in measures:
        q = f"""SELECT my, {col} AS grp, COUNT({ms}) AS d, SUM({ms}) AS nu FROM audit_sql_member
                WHERE {ms} IS NOT NULL GROUP BY 1, 2"""
        sql = {(int(r[0]), r[1]): (r[2], r[3]) for r in c.execute(q)}
        rk = {(int(r[0]), r[1]): (r[2], r[3]) for r in c.execute(
            "SELECT my, \"group\", denominator, numerator FROM kpi WHERE breakdown=? AND measure=?", (bd, ms))}
        n += len(rk)
        for k in set(sql) | set(rk):
            if sql.get(k) != rk.get(k): mism += 1; print("  mismatch", bd, ms, k, sql.get(k), rk.get(k))
check("All KPI rows recomputed in SQL match R (denominator and numerator)", mism == 0, f"{n} KPI rows, {mism} mismatches")

# 2. patient-level
diff = c.execute(f"""SELECT COUNT(*) FROM member_measures r JOIN audit_sql_member s USING (my, patient)
   WHERE {' OR '.join(f'COALESCE(r.{m},-1) != COALESCE(s.{m},-1)' for m in measures)}""").fetchone()[0]
only = c.execute("""SELECT (SELECT COUNT(*) FROM member_measures r WHERE NOT EXISTS (SELECT 1 FROM audit_sql_member s WHERE s.my=r.my AND s.patient=r.patient))
                         + (SELECT COUNT(*) FROM audit_sql_member s WHERE NOT EXISTS (SELECT 1 FROM member_measures r WHERE s.my=r.my AND s.patient=r.patient))""").fetchone()[0]
check("Patient-level flags identical in R and SQL", diff == 0 and only == 0, f"{diff} flag diffs, {only} membership diffs")

# 3. worklist size
wl_sql = c.execute(f"""SELECT COUNT(*) FROM audit_sql_member WHERE my = 2026 AND (a1c_tested = 0 OR a1c_lt8 = 0 OR bp_lt140_90 = 0
   OR eye_exam = 0 OR kidney_eval = 0 OR statin_40_75 = 0)""").fetchone()[0]
wl_r = c.execute("SELECT COUNT(*) FROM worklist_2026").fetchone()[0]
check("Worklist size (patients with >=1 open gap, MY2026 YTD) matches SQL", wl_sql == wl_r, f"SQL {wl_sql} vs R {wl_r}")

# 4. every percentage quoted in public text exists in the computed outputs
rates = {round(100 * r[0], 1) for r in c.execute("SELECT rate FROM kpi")}
extra = set()
for line in (root / "reports/figure_numbers.txt").read_text().splitlines():
    extra.add(round(100 * float(line.split("=")[1]), 1))
targets = {round(100 * r[0], 1) for r in c.execute("SELECT target FROM targets")}
bad = []
for f in ["README.md", "STORY.md"]:
    p = root / f
    if not p.exists(): continue
    for m in re.finditer(r"(\d+(?:\.\d+)?)%", p.read_text()):
        v = float(m.group(1))
        if v not in rates | extra | targets | {4.0, 8.0, 9.0, 20.0}: bad.append(f"{f}:{m.group(0)}")
check("Every % in README/STORY traces to a computed rate or stated threshold", not bad, ", ".join(bad))

# 5. privacy / wording / secrets scan over text files that would be published
txt = [p for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".R", ".Rmd", ".sql", ".py", ".sh", ".csv", ".txt", ".html"}
       and "data/raw" not in str(p)]
phone = re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b")
addr = re.compile(r"\b\d{2,5} [A-Z][a-z]+ (Street|St|Avenue|Ave|Road|Rd|Center|Suite|Lane|Ln|Drive|Dr)\b")
# case-sensitive token prefixes (avoids false hits inside base64 font blobs in the self-contained HTML)
secret = re.compile(r"(\bghp_[A-Za-z0-9]{20}|github_pat_|\bsk-[A-Za-z0-9]{20}|\bAKIA[0-9A-Z]{16}\b|(?i:api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9]{16,}|EIA_API_KEY|GITHUB_TOKEN)")
hits = {"phone": [], "address": [], "banned-descriptor word": [], "secret": [], "SSN": []}
for p in txt:
    s = p.read_text(errors="ignore")
    if phone.search(s): hits["phone"].append(p.name)
    if addr.search(s): hits["address"].append(p.name)
    if ("foren" + "sic") in s.lower(): hits["banned-descriptor word"].append(p.name)
    if secret.search(s) and p.name != "audit.py": hits["secret"].append(p.name)
    if re.search(r"\b999-\d{2}-\d{4}\b", s): hits["SSN"].append(p.name)
for k, v in hits.items(): check(f"No {k} in project text files", not v, ", ".join(sorted(set(v))))

ok = all(r[1] for r in results)
(root / "reports/audit.md").write_text("# Audit results\n\nRun: `python3 src/audit.py`\n\n" +
    "\n".join(f"- {'PASS' if r[1] else 'FAIL'}: {r[0]}{' - ' + r[2] if r[2] else ''}" for r in results) + "\n")
sys.exit(0 if ok else 1)
