"""generate_inquiries — synthetic inquiries table generator."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.rng import SeedRng

_CHANNELS: Final[list[str]] = ["web", "app", "whatsapp", "email", "phone"]
_CHANNEL_WEIGHTS: Final[list[float]] = [0.30, 0.25, 0.25, 0.15, 0.05]

_BROKER_RESPONSES: Final[list[str]] = ["accepted", "rejected", "no_response", "scheduled_visit"]
_BROKER_WEIGHTS: Final[list[float]] = [0.45, 0.15, 0.20, 0.20]


def generate_inquiries(
    leads_df: pl.DataFrame,
    spots_df: pl.DataFrame,
    rng: SeedRng,
    config: AssessmentConfig,
) -> pl.DataFrame:
    """Generate the synthetic inquiries table (~20000 rows).

    Each lead gets 1-8 inquiries. Spot selection is biased:
    60% same sector, 20% same state (if lead has preferred_state),
    20% fully random.
    """
    n_leads = len(leads_df)
    spot_ids_all = spots_df["spot_id"].to_list()
    spot_sectors = spots_df["sector_name"].to_list()

    lead_ids_list = leads_df["lead_id"].to_list()
    lead_sectors = leads_df["search_sector"].to_list()
    lead_target_area = leads_df["target_area_sqm"].to_numpy()
    lead_max_budget = leads_df["max_budget_mxn"].to_numpy()
    lead_created = leads_df["created_at"].to_list()
    lead_state_list = leads_df["preferred_state"].to_list()

    # Build lookup: spot_id -> row data
    spot_lookup: dict[int, dict] = {}
    for row in spots_df.iter_rows(named=True):
        spot_lookup[row["spot_id"]] = row

    # Build sector -> spots index
    sector_to_spots: dict[str, list[int]] = {}
    for sid, sec in zip(spot_ids_all, spot_sectors):
        sector_to_spots.setdefault(sec, []).append(sid)

    # Build state -> spots index
    state_to_spots: dict[str, list[int]] = {}
    for row in spots_df.iter_rows(named=True):
        state_to_spots.setdefault(row["state"], []).append(row["spot_id"])

    # Generate inquiries per lead
    inquiry_rows: list[dict] = []
    inquiry_id_counter = 1

    for lead_idx in range(n_leads):
        n_inquiries = int(rng.rng.integers(1, 9))
        lid = lead_ids_list[lead_idx]
        lsec = lead_sectors[lead_idx]
        lstate = lead_state_list[lead_idx] if isinstance(lead_state_list[lead_idx], str) else None

        # Parse lead created_at
        lcreated_str = lead_created[lead_idx]
        if isinstance(lcreated_str, datetime):
            lcreated = lcreated_str
        else:
            try:
                lcreated = datetime.strptime(str(lcreated_str)[:19], "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                lcreated = datetime(2025, 1, 1)

        # Pre-filter pools
        sector_pool = sector_to_spots.get(lsec, []) if lsec else []
        state_pool = state_to_spots.get(lstate, []) if lstate else []

        for _ in range(n_inquiries):
            # Weighted spot selection: 60% same sector, 20% same state, 20% random
            rand = rng.rng.random()
            if rand < 0.60 and sector_pool:
                sid = sector_pool[rng.rng.integers(0, len(sector_pool))]
            elif rand < 0.80 and state_pool:
                sid = state_pool[rng.rng.integers(0, len(state_pool))]
            else:
                sid = spot_ids_all[rng.rng.integers(0, len(spot_ids_all))]

            spot_row = spot_lookup[sid]
            spot_created = spot_row["created_at"]
            if isinstance(spot_created, str):
                spot_created = datetime.strptime(str(spot_created)[:19], "%Y-%m-%d %H:%M:%S")
            spot_area = float(spot_row["area_sqm"])

            # inquiry_at: uniform(0, 14) days after lead.created_at,
            #             then clamp to >= spot.created_at
            offset_days = rng.rng.uniform(0, 14)
            inq_at = lcreated + timedelta(days=offset_days)
            if inq_at < spot_created:
                inq_at = spot_created
            # Random hour
            inq_at = inq_at.replace(
                hour=int(rng.rng.integers(7, 21)),
                minute=int(rng.rng.integers(0, 60)),
            )

            # channel
            chan = _pick_one(rng, _CHANNELS, _CHANNEL_WEIGHTS)

            # message_length: log-normal ~200
            msg_len = max(10, int(rng.rng.lognormal(np.log(200), 0.5)))

            # requested_area_sqm: clamp to [0.3x, 5x] of spot.area_sqm
            lead_area = float(lead_target_area[lead_idx])
            req_area = round(max(10, lead_area + rng.rng.normal(0, lead_area * 0.15)), 1)
            req_area = round(max(0.3 * spot_area, min(req_area, 5.0 * spot_area)), 1)

            # requested_budget: cap at lead.max_budget_mxn
            lead_budget = float(lead_max_budget[lead_idx])
            req_budget = round(
                max(0, lead_budget * rng.rng.uniform(0.7, 1.1)), 2
            )
            req_budget = min(req_budget, lead_budget)

            # urgency_days: 30% not specified
            if rng.rng.random() < 0.30:
                urg = None
            else:
                urg_choice = rng.rng.random()
                if urg_choice < 0.20:
                    urg = int(rng.rng.integers(1, 29))
                elif urg_choice < 0.60:
                    urg = int(rng.rng.integers(30, 91))
                else:
                    urg = int(rng.rng.integers(91, 365))

            # asked_visit: 25%
            asked_visit = rng.rng.random() < 0.25

            # broker_response
            br = _pick_one(rng, _BROKER_RESPONSES, _BROKER_WEIGHTS)

            # broker_response_hours: exponential(mean=12h), ~15% null
            br_hours = round(max(0.5, float(rng.rng.exponential(12))), 1)
            if rng.rng.random() < 0.15:
                br_hours = None

            inquiry_rows.append({
                "inquiry_id": inquiry_id_counter,
                "lead_id": lid,
                "spot_id": sid,
                "inquiry_at": inq_at.strftime("%Y-%m-%d %H:%M:%S"),
                "channel": chan,
                "message_length": msg_len,
                "requested_area_sqm": req_area,
                "requested_budget_mxn": req_budget,
                "urgency_days": urg,
                "asked_visit": asked_visit,
                "broker_response": br,
                "broker_response_hours": br_hours,
            })
            inquiry_id_counter += 1

    df = pl.DataFrame(inquiry_rows)

    # Convert datetime
    df = df.with_columns([
        pl.col("inquiry_at").str.strptime(pl.Datetime("us"), "%Y-%m-%d %H:%M:%S"),
    ])

    return df


def _pick_one(rng: SeedRng, items: list[str], weights: list[float]) -> str:
    probs = np.asarray(weights, dtype=np.float64) / sum(weights)
    idx = rng.rng.choice(len(items), p=probs)
    return items[idx]
