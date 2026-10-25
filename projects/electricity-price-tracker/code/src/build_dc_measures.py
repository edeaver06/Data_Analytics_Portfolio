"""Build state-level data-center *industry* measures (research stage; not modeled yet).
Sources (US gov, public domain; raw in data/raw, see reports/data_center_measures_research.md):
  BLS QCEW annual, NAICS 518210, private ownership, state level (agglvl 58):
    https://data.bls.gov/cew/data/api/{2021,2024}/a/industry/518210.csv
  Census County Business Patterns state files, NAICS 518210, all LFO:
    https://www2.census.gov/programs-surveys/cbp/datasets/{2021,2023}/cbp{yy}st.zip
NAICS 518210 = "Computing infrastructure providers, data processing, web hosting & related"
(it's an industry, not data-center facilities or MW; employment is not electricity load).
Output: data/clean/dc_industry_state.csv
"""
import pandas as pd
FIPS = {"01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE","11":"DC","12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS","21":"KY","22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS","29":"MO","30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY","37":"NC","38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD","47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV","55":"WI","56":"WY"}
def qcew(y):
    d = pd.read_csv(f"data/raw/qcew_518210_{y}_a.csv", dtype=str)
    s = d[(d.agglvl_code == "58") & (d.own_code == "5")].copy()
    s["state"] = s.area_fips.str[:2].map(FIPS); s = s.dropna(subset=["state"]).set_index("state")
    return pd.DataFrame({f"qcew_estabs_{y}": pd.to_numeric(s.annual_avg_estabs),
                         f"qcew_emp_{y}": pd.to_numeric(s.annual_avg_emplvl),
                         f"qcew_disclosure_{y}": s.disclosure_code.fillna("")})
def cbp(y):
    s = pd.read_csv(f"data/raw/cbp_518210_{y}_state.csv", dtype=str)
    s["state"] = s.fipstate.map(FIPS); s = s.set_index("state")
    # emp_nf noise flag: G <2%, H 2-5%, J >=5% (Census disclosure-avoidance noise)
    return pd.DataFrame({f"cbp_estab_{y}": pd.to_numeric(s.est), f"cbp_emp_{y}": pd.to_numeric(s.emp),
                         f"cbp_emp_noise_flag_{y}": s.emp_nf})
t = pd.concat([qcew(2021), qcew(2024), cbp(2021), cbp(2023)], axis=1)
t["qcew_emp_chg_pct_2021_2024"] = 100 * (t.qcew_emp_2024 / t.qcew_emp_2021 - 1)
t["qcew_estabs_chg_pct_2021_2024"] = 100 * (t.qcew_estabs_2024 / t.qcew_estabs_2021 - 1)
t["cbp_emp_chg_pct_2021_2023"] = 100 * (t.cbp_emp_2023 / t.cbp_emp_2021 - 1)
assert len(t) == 51
t.round(2).sort_index().to_csv("data/clean/dc_industry_state.csv", index_label="state")
print(t[["qcew_emp_2021","qcew_emp_2024","qcew_emp_chg_pct_2021_2024","cbp_emp_chg_pct_2021_2023"]].sort_values("qcew_emp_chg_pct_2021_2024").round(1).to_string())
print("spearman qcew vs cbp chg:", t.qcew_emp_chg_pct_2021_2024.corr(t.cbp_emp_chg_pct_2021_2023, method="spearman").round(2))
