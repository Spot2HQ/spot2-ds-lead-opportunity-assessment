"""Validation checks for generated synthetic dataset (12 checks)."""
import re
from pathlib import Path
import numpy as np
import polars as pl
import yaml

ALL_TABLES = ["leads","spots","spot_attributes","inquiries","market_context","availability_snapshot","outcomes"]
CANDIDATE = [t for t in ALL_TABLES if t != "outcomes"]

EXPECTED_COLS = {
    "leads":["lead_id","user_type","company_size","industry","search_sector","search_modality",
              "target_area_sqm","min_budget_mxn_rent_monthly","max_budget_mxn_rent_monthly",
              "min_budget_mxn_sale_total","max_budget_mxn_sale_total","preferred_state","preferred_municipality",
             "preferred_corridor","source","prior_searches","prior_inquiries","has_converted_before",
             "lead_score_internal","created_at"],
    "spots":["spot_id","broker_id","sector_name","type_name","state","municipality","settlement",
             "corridor","region","lat","lon","title","description","area_sqm","price_sqm_mxn_rent",
             "price_sqm_mxn_sale","price_total_mxn_rent","price_total_mxn_sale","maintenance_cost_mxn",
             "modality","days_on_market","total_inquiries","total_views","is_active","created_at"],
    "spot_attributes":["spot_id","natural_light","luminaires","charging_ports","security_type",
                       "floor_level","elevators","vertical_height_m","parking_spaces","building_status",
                       "floor_material","amenities"],
    "inquiries":["inquiry_id","lead_id","spot_id","inquiry_at","channel","message_length",
                  "requested_area_sqm","requested_budget_mxn_rent_monthly","requested_budget_mxn_sale_total","urgency_days","asked_visit",
                 "broker_response","broker_response_hours"],
    "market_context":["state","municipality","corridor","sector","month","similar_available_spots",
                      "avg_price_sqm_mxn","recent_occupancy_rate","absorption_velocity_days",
                      "recent_inquiry_volume"],
    "availability_snapshot":["snapshot_id","spot_id","snapshot_date","is_available",
                             "days_until_available","competing_inquiries_30d"],
    "outcomes":["lead_id","converted_to_visit","converted_to_closure","conversion_date","final_spot_id",
                "spot_available_for_lead","opportunity_label","lead_quality_true"],
}

MISS_SPEC = {"leads":{"company_size":0.05,"industry":0.03,"preferred_corridor":0.08,
                       "min_budget_mxn_rent_monthly":0.33,"min_budget_mxn_sale_total":0.52},
             "spot_attributes":{"vertical_height_m":0.15,"floor_material":0.08,"charging_ports":0.20},
             "inquiries":{"urgency_days":0.30,"broker_response_hours":0.15}}
MISS_TOL = 0.05

PII_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|"
    r"\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|"
    r"\b\d{1,5}\s+[\w\s]+(street|st|ave|avenue|blvd|road|rd|calle|av\.|avenida|col\.|colonia)\b", re.I)

MX_B = {"lat_min":14.0,"lat_max":33.0,"lon_min":-118.0,"lon_max":-86.0}
T_START, T_END = "2025-01-01", "2026-06-30"
# Per-table date ranges from synthetic-data-guide
DT_RANGES = {"leads":(T_START,T_END), "spots":("2024-01-01","2026-12-31"),
    "inquiries":(T_START,"2026-07-31"), "market_context":("2024-01-01","2026-06-01"),
    "availability_snapshot":("2024-01-01","2026-07-31"), "outcomes":(T_START,"2026-08-31")}
DT_COLS = {"leads":"created_at","spots":"created_at","inquiries":"inquiry_at",
    "market_context":"month","availability_snapshot":"snapshot_date","outcomes":"conversion_date"}


# --- Helpers ---

def _load(dd: Path, t: str) -> pl.DataFrame:
    s = "evaluation" if t == "outcomes" else "candidate"
    return pl.read_parquet(dd / s / "parquet" / f"{t}.parquet")

def _cfg(dd: Path) -> dict:
    with open(dd.parent / "config" / "default.yaml") as f:
        return yaml.safe_load(f)

# --- Checks ---

def check_tables_exist(dd: Path) -> dict:
    missing = []
    for t in ALL_TABLES:
        s = "evaluation" if t == "outcomes" else "candidate"
        if not (dd / s / "csv" / f"{t}.csv").exists(): missing.append(f"{s}/csv/{t}.csv")
        if not (dd / s / "parquet" / f"{t}.parquet").exists(): missing.append(f"{s}/parquet/{t}.parquet")
    ok = len(missing) == 0
    return {"passed":ok, "details":f"{14-len(missing)}/14 found" if ok else f"Missing:{missing}"}

def check_row_counts(dd: Path, cfg: dict) -> dict:
    tgts = cfg["row_counts"]
    fp = cfg["row_count_tolerances"]["fixed"]["pct"] / 100
    ft = set(cfg["row_count_tolerances"]["fixed"]["tables"])
    gp = cfg["row_count_tolerances"]["generated"]["pct"] / 100
    acts, bad = {}, []
    for t in ALL_TABLES:
        n = _load(dd, t).shape[0]; acts[t] = n
        tol = fp if t in ft else gp
        if not (tgts[t]*(1-tol) <= n <= tgts[t]*(1+tol)):
            bad.append(f"{t}:{n} vs {tgts[t]}±{tol*100:.0f}%")
    return {"passed":len(bad)==0, "details":acts if not bad else f"Failures:{bad}"}

def check_required_columns(dd: Path) -> dict:
    bad = []
    for t, exp in EXPECTED_COLS.items():
        df = _load(dd, t); a = set(df.columns); e = set(exp)
        m, x = e-a, a-e
        if m or x: bad.append(f"{t}: miss={m} extra={x}" if m and x else f"{t}: miss={m}" if m else f"{t}: extra={x}")
    return {"passed":len(bad)==0, "details":"OK" if not bad else "; ".join(bad)}

def check_fk_integrity(dd: Path) -> dict:
    lids = set(_load(dd,"leads")["lead_id"].to_list())
    sids = set(_load(dd,"spots")["spot_id"].to_list())
    issues = []
    for t, fk, ref in [("inquiries","lead_id","leads"), ("inquiries","spot_id","spots"),
                        ("availability_snapshot","spot_id","spots"), ("outcomes","lead_id","leads")]:
        rs = lids if ref == "leads" else sids
        o = _load(dd,t).filter(~pl.col(fk).is_in(rs)).shape[0]
        if o: issues.append(f"{t}.{fk}: {o} orphans")
    return {"passed":len(issues)==0, "details":"OK" if not issues else "; ".join(issues)}

def check_geo_consistency(dd: Path) -> dict:
    s = _load(dd,"spots"); n=s.shape[0]
    in_b = s.filter((pl.col("lat")>=MX_B["lat_min"])&(pl.col("lat")<=MX_B["lat_max"])
                    &(pl.col("lon")>=MX_B["lon_min"])&(pl.col("lon")<=MX_B["lon_max"])).shape[0]
    fin = s.filter(pl.col("lat").is_finite()&pl.col("lon").is_finite()).shape[0]
    span = s.group_by("state").agg(min_lat=pl.col("lat").min(),max_lat=pl.col("lat").max())
    wide = span.filter((pl.col("max_lat")-pl.col("min_lat"))>15.0)
    issues = []
    if in_b<n: issues.append(f"{n-in_b}/{n} out of bounds")
    if fin<n: issues.append(f"{n-fin} non-finite")
    if wide.shape[0]: issues.append(f"Big span:{wide['state'].to_list()}")
    return {"passed":len(issues)==0, "details":f"All {n} OK" if not issues else "; ".join(issues)}

def check_no_pii(dd: Path) -> dict:
    hits = []
    for t in CANDIDATE:
        df = _load(dd, t)
        for c in [c for c in df.columns if df[c].dtype==pl.Utf8]:
            for v in df[c].drop_nulls().head(2000).to_list():
                if PII_RE.search(str(v)):
                    hits.append(f"{t}.{c}:{v[:80]}")
                    if len(hits)>=5: break
            if len(hits)>=5: break
    return {"passed":len(hits)==0, "details":"No PII" if not hits else f"Suspect:{hits}"}

def check_missingness(dd: Path) -> dict:
    bad = []
    for t, cols in MISS_SPEC.items():
        df = _load(dd, t)
        for c, ex in cols.items():
            ac = df[c].null_count()/df.shape[0]
            if not (ex-MISS_TOL <= ac <= ex+MISS_TOL):
                bad.append(f"{t}.{c}: {ex:.0%}±{MISS_TOL:.0%}, got {ac:.1%}")
    return {"passed":len(bad)==0, "details":"OK" if not bad else "; ".join(bad)}

def check_temporal_range(dd: Path) -> dict:
    issues = []
    for t, dc in DT_COLS.items():
        df = _load(dd, t)
        ds = df.select(pl.col(dc).cast(pl.Utf8).str.strip_chars().str.slice(0,10))
        lo, hi = DT_RANGES[t]
        bf = ds.filter(pl.col(dc)<lo).shape[0]
        af = ds.filter(pl.col(dc)>hi).shape[0]
        if bf: issues.append(f"{t}.{dc}: {bf} before {lo}")
        if af: issues.append(f"{t}.{dc}: {af} after {hi}")
    return {"passed":len(issues)==0, "details":"OK" if not issues else "; ".join(issues)}

def check_base_rates(dd: Path) -> dict:
    o = _load(dd,"outcomes")
    vr, cr, ar = o["converted_to_visit"].mean(), o["converted_to_closure"].mean(), o["spot_available_for_lead"].mean()
    ok = 0.18<=vr<=0.26 and 0.07<=cr<=0.13 and 0.55<=ar<=0.75
    return {"passed":ok, "details":{"converted_to_visit":round(vr,4),
            "converted_to_closure":round(cr,4),"spot_available_for_lead":round(ar,4)}}

def check_candidate_eval_separation(dd: Path) -> dict:
    csvs = {p.name for p in (dd/"candidate"/"csv").glob("*.csv")}
    pqs  = {p.name for p in (dd/"candidate"/"parquet").glob("*.parquet")}
    bad = []
    if "outcomes.csv" in csvs: bad.append("outcomes.csv in candidate/csv")
    if "outcomes.parquet" in pqs: bad.append("outcomes.parquet in candidate/parquet")
    return {"passed":len(bad)==0, "details":"Separated" if not bad else "; ".join(bad)}

def check_leakage_traps(dd: Path) -> dict:
    l = _load(dd,"leads")
    p, m = [], []
    for c in ["lead_score_internal","has_converted_before"]:
        (p if c in l.columns else m).append(c)
    return {"passed":len(m)==0, "details":f"Present:{p}" if not m else f"Missing:{m}"}


def compute_signal_score(dd: Path) -> dict:
    leads = _load(dd,"leads")
    inq = _load(dd,"inquiries")
    mkt = _load(dd,"market_context")
    out = _load(dd,"outcomes")
    iagg = inq.group_by("lead_id").agg(ask_rate=pl.col("asked_visit").mean(),
        acc_rate=pl.col("broker_response").eq("accepted").mean(),
        noresp_rate=pl.col("broker_response").eq("no_response").mean(),
        sch_rate=pl.col("broker_response").eq("scheduled_visit").mean(), inq_cnt=pl.count(),
        resp_median=pl.col("broker_response_hours").median())
    # Match leads to their preferred state/sector from market_context latest month
    latest_mkt = mkt.sort("month").group_by(["state","sector"]).tail(1).select(
        ["state","sector","recent_occupancy_rate","absorption_velocity_days"])
    lead_ctx = leads.join(latest_mkt, left_on=["preferred_state","search_sector"],
        right_on=["state","sector"], how="left")
    df = lead_ctx.join(iagg, on="lead_id", how="left").join(
        out.select(["lead_id","converted_to_visit"]), on="lead_id")
    df = df.with_columns(ask_rate=pl.col("ask_rate").fill_null(0),
        acc_rate=pl.col("acc_rate").fill_null(0), noresp_rate=pl.col("noresp_rate").fill_null(0),
        sch_rate=pl.col("sch_rate").fill_null(0), inq_cnt=pl.col("inq_cnt").fill_null(0),
        resp_median=pl.col("resp_median").fill_null(168.0),
        recent_occupancy_rate=pl.col("recent_occupancy_rate").fill_null(0.8),
        absorption_velocity_days=pl.col("absorption_velocity_days").fill_null(120.0))
    def _n(c): cmin,cmax=df[c].min(),df[c].max(); return pl.lit(0.5) if cmax==cmin else (pl.col(c)-cmin)/(cmax-cmin)
    ps = df.select(pl.when(pl.col("prior_inquiries").is_between(1,5)).then(1.0)
        .when(pl.col("prior_inquiries")>5).then(0.5).otherwise(0.0))[:,0].to_numpy()
    df = df.with_columns(sv=_n("ask_rate"),sa=_n("acc_rate"),sn=_n("noresp_rate"),
        ss=_n("sch_rate"),si=_n("inq_cnt"),srp=_n("resp_median"),
        sro=_n("recent_occupancy_rate"),sav=_n("absorption_velocity_days"),
        sp=pl.lit(ps), sr=pl.when(pl.col("source")=="referral").then(1.0).otherwise(0.0),
        st=pl.when(pl.col("user_type")=="tenant_direct").then(1.0).otherwise(0.0),
        ss2=pl.when(pl.col("search_sector")=="Office").then(1.0).otherwise(0.0),
        sh=pl.when(pl.col("has_converted_before")).then(1.0).otherwise(0.0))
    df = df.with_columns(score=0.12*pl.col("sv")+0.10*pl.col("sa")-0.08*pl.col("sn")
        +0.06*pl.col("ss")+0.03*pl.col("si")-0.05*pl.col("srp")
        +0.03*pl.col("sro")-0.05*pl.col("sav")+0.12*pl.col("sp")
        +0.10*pl.col("sr")+0.08*pl.col("st")+0.08*pl.col("ss2")+0.10*pl.col("sh"))
    y,s = df["converted_to_visit"].cast(pl.Int8).to_numpy(), df["score"].to_numpy()
    n,br = len(y), float(y.mean())
    pos,neg = s[y==1], s[y==0]
    # Rank AUC
    all_s = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))])
    labels = all_s[np.argsort(np.concatenate([pos,neg]))] if len(pos) and len(neg) else all_s
    seen,acc = 0,0.0
    for i in range(len(labels)-1,-1,-1):
        if labels[i]==0: acc+=seen
        else: seen+=1
    auc = acc/(len(pos)*len(neg)) if len(pos) and len(neg) else 0.5
    # Precision@top10%
    k = max(1,int(n*0.10))
    prec = float(y[np.argpartition(-s,k)[:k]].mean())
    ok = auc>=0.60 and prec>=br*1.5
    return {"passed":ok, "details":{"auc":round(auc,4),"precision_at_top10":round(prec,4),
            "base_rate":round(br,4),"threshold":round(br*1.5,4)}}


def run_all_checks(dd: Path) -> dict:
    c = _cfg(dd)
    return {"tables_exist":check_tables_exist(dd), "row_counts":check_row_counts(dd,c),
        "required_columns":check_required_columns(dd), "fk_integrity":check_fk_integrity(dd),
        "geo_consistency":check_geo_consistency(dd), "no_pii":check_no_pii(dd),
        "missingness":check_missingness(dd), "temporal_range":check_temporal_range(dd),
        "base_rates":check_base_rates(dd), "candidate_eval_separation":check_candidate_eval_separation(dd),
        "leakage_traps":check_leakage_traps(dd), "signal_utility":compute_signal_score(dd)}
