"""generate_market_context — synthetic market context aggregations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.rng import SeedRng

_SECTORS: Final[list[str]] = ["Industrial", "Office", "Retail", "Land"]

# Sector base ranges for occupancy
_OCC_BASE: Final[dict[str, tuple[float, float]]] = {
    "Industrial": (0.80, 0.95),
    "Office": (0.75, 0.90),
    "Retail": (0.70, 0.85),
    "Land": (0.50, 0.70),
}

# Sector base ranges for absorption velocity (days)
_ABS_BASE: Final[dict[str, tuple[float, float]]] = {
    "Industrial": (90, 240),
    "Office": (60, 180),
    "Retail": (45, 150),
    "Land": (120, 365),
}


def generate_market_context(
    spots_df: pl.DataFrame,
    rng: SeedRng,
    config: AssessmentConfig,
) -> pl.DataFrame:
    """Generate market_context table (~500 rows).

    Aggregated per valid (state/municipality/corridor/sector/month) that
    exists in the spots data, for Jan 2024 - Jun 2026.
    """
    n_target = config.row_counts.market_context

    # Generate months: Jan 2024 - Jun 2026
    months: list[date] = []
    y, m = 2024, 1
    while (y < 2026) or (y == 2026 and m <= 6):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    month_strs = [d.strftime("%Y-%m-%d") for d in months]

    # --- Count total spots per (state, municipality, corridor) triple ---
    spot_counts = spots_df.group_by(["state", "municipality", "corridor"]).len()
    total_by_triple: dict[tuple[str, str, str], int] = {
        (r["state"], r["municipality"], r["corridor"]): r["len"]
        for r in spot_counts.iter_rows(named=True)
    }

    # --- Build all valid (state, muni, corridor, sector, month) candidates ---
    valid_combos = sorted(
        spots_df.select(["state", "municipality", "corridor", "sector_name"])
        .unique()
        .rows()
    )

    all_candidates: list[tuple[str, str, str, str, str]] = []
    for st, mun, corr, sec in valid_combos:
        for ms in month_strs:
            all_candidates.append((st, mun, corr, sec, ms))

    # Shuffle so selected rows span diverse combos
    rng.rng.shuffle(all_candidates)
    selected = all_candidates[:n_target]

    # --- Build price baseline from spots by corridor and sector ---
    spot_prices: dict[tuple[str, str], list[float]] = {}
    for row in spots_df.iter_rows(named=True):
        key = (row["corridor"], row["sector_name"])
        spot_prices.setdefault(key, []).append(float(row["price_sqm_mxn_rent"]))

    price_median: dict[tuple[str, str], float] = {
        k: float(np.median(v)) for k, v in spot_prices.items() if v
    }
    _fallback_price: dict[str, float] = {
        "Industrial": 150, "Office": 350, "Retail": 300, "Land": 50,
    }

    # --- Generate rows ---
    rows: list[dict] = []
    for st, mun, corr, sec, month_str in selected:
        pc = price_median.get((corr, sec), _fallback_price.get(sec, 200))

        m_date = datetime.strptime(month_str, "%Y-%m-%d")
        years_from_2024 = (m_date.year - 2024) + (m_date.month - 1) / 12
        trend = 1 + 0.03 * years_from_2024
        season = 1 + 0.03 * np.sin(2 * np.pi * (m_date.month - 1) / 12)
        avg_price = round(pc * trend * season * rng.rng.uniform(0.9, 1.1), 2)

        occ_lo, occ_hi = _OCC_BASE[sec]
        occupancy = round(rng.rng.uniform(occ_lo, occ_hi), 3)

        abs_lo, abs_hi = _ABS_BASE[sec]
        absorption = round(rng.rng.uniform(abs_lo, abs_hi), 1)

        # similar_available_spots: 5-15% of total spots in that triple
        total_triple = total_by_triple.get((st, mun, corr), 100)
        lo_sim = max(1, int(total_triple * 0.05))
        hi_sim = max(lo_sim + 1, int(total_triple * 0.15))
        similar_spots = int(rng.rng.integers(lo_sim, hi_sim + 1))

        inquiry_vol = int(rng.rng.integers(50, 501))

        rows.append({
            "state": st,
            "municipality": mun,
            "corridor": corr,
            "sector": sec,
            "month": month_str,
            "similar_available_spots": similar_spots,
            "avg_price_sqm_mxn": avg_price,
            "recent_occupancy_rate": occupancy,
            "absorption_velocity_days": absorption,
            "recent_inquiry_volume": inquiry_vol,
        })

    df = pl.DataFrame(rows)
    if len(df) > 0:
        df = df.with_columns([
            pl.col("month").str.strptime(pl.Date, "%Y-%m-%d"),
        ])

    return df
