"""generate_outcomes — HIDDEN outcomes table for evaluation only.

NOT exported from the public generators package. Must NOT be visible
in any candidate-facing output.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.rng import SeedRng

_SECTOR_REF: Final[dict[str, float]] = {
    "Industrial": 150,
    "Office": 350,
    "Retail": 300,
    "Land": 50,
}

def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    x = np.clip(x, -50, 50)
    return 1 / (1 + np.exp(-x))


def generate_outcomes(
    leads_df: pl.DataFrame,
    inquiries_df: pl.DataFrame,
    availability_df: pl.DataFrame,
    market_df: pl.DataFrame,
    spots_df: pl.DataFrame,
    rng: SeedRng,
    config: AssessmentConfig,
) -> pl.DataFrame:
    """Generate the HIDDEN outcomes table (~5000 rows).

    One row per lead. P(conversion) computed using the guide's logistic
    function with lead-level features and aggregated inquiry-level features.
    """
    n_leads = len(leads_df)

    # --- Lead-level features ---
    leads_source = np.array(leads_df["source"].to_list())
    leads_sector = np.array(leads_df["search_sector"].to_list())
    leads_user_type = np.array(leads_df["user_type"].to_list())
    leads_max_rent = leads_df["max_budget_mxn_rent_monthly"].to_numpy()
    leads_max_sale = leads_df["max_budget_mxn_sale_total"].to_numpy()
    leads_area = leads_df["target_area_sqm"].to_numpy()
    leads_prior_inq = leads_df["prior_inquiries"].to_numpy()
    leads_created = leads_df["created_at"].to_list()

    rent_refs = np.array([_SECTOR_REF.get(sector, 200) for sector in leads_sector])
    sale_refs = rent_refs * 180
    rent_affordability = np.divide(
        leads_max_rent,
        leads_area * rent_refs,
        out=np.zeros_like(leads_max_rent),
        where=leads_max_rent > 0,
    )
    sale_affordability = np.divide(
        leads_max_sale,
        leads_area * sale_refs,
        out=np.zeros_like(leads_max_sale),
        where=leads_max_sale > 0,
    )
    affordability = np.maximum(rent_affordability, sale_affordability)
    median_affordability = (
        float(np.median(affordability[affordability > 0]))
        if (affordability > 0).any()
        else 1.0
    )

    # --- Build inquiry index per lead ---
    inq_by_lead: dict[int, list[int]] = {}
    inq_data: dict[int, dict] = {}
    for row in inquiries_df.iter_rows(named=True):
        lid = row["lead_id"]
        iid = row["inquiry_id"]
        inq_by_lead.setdefault(lid, []).append(iid)
        inq_data[iid] = {
            "spot_id": row["spot_id"],
            "broker_response": row["broker_response"],
            "asked_visit": row["asked_visit"],
        }

    # --- Build availability index per spot ---
    avail_by_spot: dict[int, list[bool]] = {}
    for row in availability_df.iter_rows(named=True):
        sid = row["spot_id"]
        avail_by_spot.setdefault(sid, []).append(row["is_available"])

    # --- Market context: median absorption_velocity per (corridor, sector) ---
    abs_velocity: dict[tuple[str, str], float] = {}
    for row in market_df.iter_rows(named=True):
        key = (row["corridor"], row["sector"])
        if key not in abs_velocity:
            abs_velocity[key] = float(row["absorption_velocity_days"])

    # --- Spot sector and corridor ---
    spot_sectors: dict[int, str] = {}
    spot_corridors: dict[int, str] = {}
    for row in spots_df.iter_rows(named=True):
        spot_sectors[row["spot_id"]] = row["sector_name"]
        spot_corridors[row["spot_id"]] = row["corridor"]

    # --- Compute per-lead probabilities ---
    p_visit = np.zeros(n_leads, dtype=np.float64)
    best_spot_ids: list[int | None] = [None] * n_leads
    best_available: list[bool] = [True] * n_leads

    # Lead-level components (same for all inquiries of a lead)
    lead_logit = np.zeros(n_leads, dtype=np.float64)
    lead_logit += 0.7 * (leads_source == "referral").astype(np.float64)
    lead_logit += 0.5 * (leads_sector == "Office").astype(np.float64)
    lead_logit += 0.4 * (leads_user_type == "tenant_direct").astype(np.float64)
    lead_logit += 0.3 * (affordability > median_affordability).astype(np.float64)
    pi_arr = leads_prior_inq.astype(np.float64)
    lead_logit += 0.4 * ((pi_arr > 1) & (pi_arr <= 5)).astype(np.float64)

    for idx in range(n_leads):
        lid = int(leads_df["lead_id"][idx])
        inqs = inq_by_lead.get(lid, [])
        if not inqs:
            p_visit[idx] = 0.05  # minimal chance for leads with no inquiries
            continue

        # Aggregated inquiry features: use best broker response and OR for asked_visit
        best_br_score = -1.0  # higher = more favorable
        any_asked = False
        best_sid = None
        for iid in inqs:
            idata = inq_data[iid]
            br = idata["broker_response"]
            av = idata["asked_visit"]
            sid = idata["spot_id"]

            if av:
                any_asked = True

            br_score = {"accepted": 0.2, "scheduled_visit": 0.1, "rejected": -0.1, "no_response": -0.5}.get(br, 0)
            if br_score > best_br_score:
                best_br_score = br_score
                best_sid = sid if best_sid is None else sid

        # Compute inquiry-level components using best inquiry
        if best_br_score > -0.5:  # at least one inquiry with response
            inq_logit = best_br_score + 0.5 * (1 if any_asked else 0)
            # Penalty for no_response if the best is no_response
            if best_br_score == -0.5:
                inq_logit += -0.5
        else:
            inq_logit = -0.5  # all no_response

        # Market and availability from best spot
        if best_sid is not None:
            sc = spot_sectors.get(best_sid, "Office")
            co = spot_corridors.get(best_sid, "unknown")
            abs_v = abs_velocity.get((co, sc), 150.0)
            inq_logit += -0.3 * (1 if abs_v > 180 else 0)

            avail_list = avail_by_spot.get(best_sid, [True])
            spot_avail = avail_list[-1] if avail_list else True
            inq_logit += -0.4 * (0 if spot_avail else 1)
        else:
            spot_avail = True

        # Total logit = lead components + inquiry components + noise + bias
        # Bias calibrated to produce ~22% conversion rate
        total_logit = float(lead_logit[idx]) + inq_logit + float(rng.rng.normal(0, 0.3)) - 2.3
        p_visit[idx] = float(_sigmoid(np.array([total_logit]))[0])
        best_spot_ids[idx] = best_sid
        best_available[idx] = spot_avail

    # --- Bernoulli for converted_to_visit ---
    converted_to_visit = (rng.rng.random(n_leads) < p_visit).tolist()

    # --- converted_to_closure: subset of visit, ~45% ---
    # P(closure) = P(visit) * P(closure | visit) ≈ 0.22 * 0.45 ≈ 0.10
    converted_to_closure = [
        v and rng.rng.random() < 0.45 for v in converted_to_visit
    ]

    # --- conversion_date: 7-60 days post creation ---
    conversion_dates: list[str | None] = []
    for idx in range(n_leads):
        if converted_to_visit[idx]:
            created = leads_created[idx]
            if isinstance(created, datetime):
                created_dt = created
            else:
                created_dt = datetime.strptime(str(created)[:19], "%Y-%m-%d %H:%M:%S")
            offset_days = int(rng.rng.integers(7, 61))
            conv_date = created_dt + timedelta(days=offset_days)
            conversion_dates.append(conv_date.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            conversion_dates.append(None)

    # --- opportunity_label ---
    labels: list[str] = []
    for idx in range(n_leads):
        if converted_to_visit[idx]:
            labels.append("Converted")
        elif p_visit[idx] >= 0.15 and best_available[idx]:
            labels.append("HighQualityAvailable")
        elif p_visit[idx] >= 0.15:
            labels.append("HighQualityUnavailable")
        else:
            labels.append("LowQuality")

    df = pl.DataFrame({
        "lead_id": leads_df["lead_id"].to_list(),
        "converted_to_visit": converted_to_visit,
        "converted_to_closure": converted_to_closure,
        "conversion_date": conversion_dates,
        "final_spot_id": [
            sid if closure else None
            for sid, closure in zip(best_spot_ids, converted_to_closure)
        ],
        "spot_available_for_lead": best_available,
        "opportunity_label": labels,
        "lead_quality_true": [round(float(p), 4) for p in p_visit],
    })

    # Convert datetime
    df = df.with_columns([
        pl.when(pl.col("conversion_date").is_not_null())
        .then(pl.col("conversion_date").str.strptime(pl.Datetime("us"), "%Y-%m-%d %H:%M:%S"))
        .otherwise(None)
        .alias("conversion_date"),
    ])

    return df
