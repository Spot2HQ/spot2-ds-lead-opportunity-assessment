"""generate_leads — synthetic leads table generator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.geo_catalog import GeoCatalog
from spot2_assessment_data.rng import SeedRng

# --- Sector display names matching guide spec ---
SECTOR_NAMES: Final[list[str]] = ["Industrial", "Office", "Retail", "Land"]
# Price-per-sqm reference (MXN rent) for budget computation per sector.
_SECTOR_PRICE_MEAN: Final[dict[str, float]] = {
    "Industrial": 150,
    "Office": 350,
    "Retail": 300,
    "Land": 50,
}

_USER_TYPES: Final[list[str]] = ["broker", "tenant_direct", "investor", "developer"]
_USER_TYPE_WEIGHTS: Final[list[float]] = [0.35, 0.40, 0.20, 0.05]

_COMPANY_SIZES: Final[list[str]] = ["small", "medium", "large", "enterprise"]
_COMPANY_WEIGHTS: Final[list[float]] = [0.25, 0.35, 0.25, 0.15]

_INDUSTRIES: Final[list[str]] = [
    "technology", "retail", "manufacturing", "logistics",
    "financial", "healthcare", "other",
]
_INDUSTRY_WEIGHTS: Final[list[float]] = [0.20, 0.25, 0.15, 0.10, 0.10, 0.10, 0.10]

_SECTOR_WEIGHTS: Final[list[float]] = [0.25, 0.30, 0.30, 0.15]

_MODALITIES: Final[list[str]] = ["rent", "sale", "both"]
_MODALITY_WEIGHTS: Final[list[float]] = [0.50, 0.30, 0.20]

_SOURCES: Final[list[str]] = ["organic", "referral", "paid", "social", "email", "event"]
_SOURCE_WEIGHTS: Final[list[float]] = [0.30, 0.20, 0.25, 0.10, 0.10, 0.05]

# --- Prior bins ---
_PRIOR_SEARCH_BINS: Final[list[float]] = [0.35, 0.30, 0.20, 0.15]
_PRIOR_INQUIRY_BINS: Final[list[float]] = [0.45, 0.30, 0.15, 0.10]


def _pick_weighted(rng: SeedRng, items: list[str], weights: list[float], n: int) -> list[str]:
    """Return `n` weighted choices."""
    probs = np.asarray(weights, dtype=np.float64) / sum(weights)
    indices = rng.rng.choice(len(items), size=n, p=probs)
    return [items[i] for i in indices]


def _categorical_series(values: list[str], n: int, rng: SeedRng) -> pl.Series:
    """Build a polars Enum series from a list of values."""
    idx = rng.rng.integers(0, len(values), size=n)
    return pl.Series([values[i] for i in idx], dtype=pl.String)


def generate_leads(
    rng: SeedRng,
    config: AssessmentConfig,
    geo_catalog: GeoCatalog,
) -> pl.DataFrame:
    """Generate the synthetic leads table (~5000 rows).

    Returns a DataFrame with all candidate-facing columns plus a hidden
    ``_conversion_signal`` column used by ``generate_outcomes`` for
    lead_score_internal correlation.
    """
    n = config.row_counts.leads
    t_start = config.start_datetime
    t_end = config.end_datetime

    # --- Identity ---
    lead_ids = list(range(1, n + 1))

    # --- Categorical columns ---
    user_type = _pick_weighted(rng, _USER_TYPES, _USER_TYPE_WEIGHTS, n)
    company_size = _pick_weighted(rng, _COMPANY_SIZES, _COMPANY_WEIGHTS, n)
    industry = _pick_weighted(rng, _INDUSTRIES, _INDUSTRY_WEIGHTS, n)
    search_sector = _pick_weighted(rng, SECTOR_NAMES, _SECTOR_WEIGHTS, n)
    search_modality = _pick_weighted(rng, _MODALITIES, _MODALITY_WEIGHTS, n)
    source = _pick_weighted(rng, _SOURCES, _SOURCE_WEIGHTS, n)

    # --- Geo preferences ---
    # 12 states from geo_catalog with tiered distribution:
    # Tier 1 (top 3 — 40%): CDMX, Estado de México, Jalisco
    # Tier 2 (next 5 — 40%): Nuevo León, Querétaro, Guanajuato, Puebla, Yucatán
    # Tier 3 (remaining 4 — 20%): Baja California, Sonora, San Luis Potosí, Chihuahua
    top3 = 0.40 / 3
    next5 = 0.40 / 5
    rest = 0.20 / 4
    state_names = [
        "CDMX", "Estado de México", "Jalisco",
        "Nuevo León", "Querétaro", "Guanajuato", "Puebla", "Yucatán",
        "Baja California", "Sonora", "San Luis Potosí", "Chihuahua",
    ]
    state_weights = [top3, top3, top3, next5, next5, next5, next5, next5, rest, rest, rest, rest]
    preferred_state = _pick_weighted(rng, state_names, state_weights, n)

    # Build geo index: state -> [municipalities], (state, municipality) -> [corridors]
    _sm_to_c: dict[tuple[str, str], list[str]] = {}
    _state_munis: dict[str, set[str]] = {}
    for a in geo_catalog.anchors:
        _state_munis.setdefault(a.state, set()).add(a.municipality)
        _sm_to_c.setdefault((a.state, a.municipality), []).append(a.corridor)

    def _match_geo(state: str) -> tuple[str, str]:
        """Pick municipality and corridor matching the given state."""
        munis = sorted(_state_munis.get(state, {"Unknown"}))
        muni = munis[rng.rng.integers(0, len(munis))]
        corridors = _sm_to_c.get((state, muni), ["unknown"])
        corr = corridors[rng.rng.integers(0, len(corridors))]
        return muni, corr

    preferred_municipality = []
    preferred_corridor = []
    for st in preferred_state:
        m, c = _match_geo(st)
        preferred_municipality.append(m)
        preferred_corridor.append(c)

    # --- Area and budget ---
    area_arr = np.array([rng.log_normal(500, 400, 30, 10000) for _ in range(n)])
    rent_price_means = np.array([_SECTOR_PRICE_MEAN[s] for s in search_sector])
    rent_reference = area_arr * rent_price_means
    sale_reference = rent_reference * 180
    modalities = np.array(search_modality)
    rent_applicable = np.isin(modalities, ["rent", "both"])
    sale_applicable = np.isin(modalities, ["sale", "both"])
    affordability_factor = rng.rng.uniform(0.7, 0.9, size=n)
    min_budget_rent = (rent_reference * affordability_factor).round(2)
    min_budget_sale = (sale_reference * affordability_factor).round(2)
    max_budget_rent = (min_budget_rent * rng.rng.uniform(1.1, 1.5, size=n)).round(2)
    max_budget_sale = (min_budget_sale * rng.rng.uniform(1.1, 1.5, size=n)).round(2)
    max_budget_rent = np.maximum(max_budget_rent, min_budget_rent)
    max_budget_sale = np.maximum(max_budget_sale, min_budget_sale)

    # --- Prior activity ---
    prior_searches = _assign_binned(rng, n, _PRIOR_SEARCH_BINS, [0, (1, 3), (4, 10), (11, 60)])
    prior_inquiries = _assign_binned(rng, n, _PRIOR_INQUIRY_BINS, [0, (1, 5), (6, 15), (16, 100)])

    # --- has_converted_before: 10% true, correlated with prior_inquiries ---
    hcb_prob = np.clip(0.05 + 0.01 * np.array(prior_inquiries), 0, 0.95)
    has_converted_before = (rng.rng.random(n) < hcb_prob).tolist()

    # --- _conversion_signal (hidden, used for lead_score_internal correlation) ---
    rent_affordability = np.divide(
        max_budget_rent, rent_reference, out=np.zeros(n), where=rent_applicable,
    )
    sale_affordability = np.divide(
        max_budget_sale, sale_reference, out=np.zeros(n), where=sale_applicable,
    )
    normalized_budget = np.maximum(rent_affordability, sale_affordability)
    median_affordability = float(np.median(normalized_budget[normalized_budget > 0]))
    signal = np.zeros(n, dtype=np.float64)
    signal += 0.7 * (np.array(source) == "referral").astype(np.float64)
    signal += 0.5 * (np.array(search_sector) == "Office").astype(np.float64)
    signal += 0.4 * (np.array(user_type) == "tenant_direct").astype(np.float64)
    signal += 0.3 * (normalized_budget > median_affordability).astype(np.float64)
    pi_arr = np.array(prior_inquiries, dtype=np.float64)
    signal += 0.4 * ((pi_arr > 1) & (pi_arr <= 5)).astype(np.float64)
    signal /= 2.3  # normalize to ~[0, 1]

    # lead_score_internal: random(0,1) + 0.15*signal + noise
    lead_score_internal = np.clip(
        rng.rng.random(n) + 0.15 * signal + rng.rng.normal(0, 0.05, size=n), 0, 1
    )

    # --- created_at: uniform over temporal range, weekday bias ---
    total_days = (t_end - t_start).days
    day_offsets = rng.rng.integers(0, total_days + 1, size=n)
    created_at_dt = [t_start + timedelta(days=int(d)) for d in day_offsets]
    # Boost weekday probability by sometimes shifting weekend to nearest weekday
    for i, dt in enumerate(created_at_dt):
        if dt.weekday() >= 5 and rng.rng.random() < 0.4:
            shift = -1 if dt.weekday() == 5 else 1
            created_at_dt[i] = dt + timedelta(days=shift)
    created_at = [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in created_at_dt]

    # --- Build DataFrame ---
    def _nullable(values: np.ndarray, mask: np.ndarray) -> list[float | None]:
        return [float(value) if applicable else None for value, applicable in zip(values, mask)]

    df = pl.DataFrame({
        "lead_id": lead_ids,
        "user_type": user_type,
        "company_size": company_size,
        "industry": industry,
        "search_sector": search_sector,
        "search_modality": search_modality,
        "target_area_sqm": area_arr.round(1),
        "min_budget_mxn_rent_monthly": _nullable(min_budget_rent, rent_applicable),
        "max_budget_mxn_rent_monthly": _nullable(max_budget_rent, rent_applicable),
        "min_budget_mxn_sale_total": _nullable(min_budget_sale, sale_applicable),
        "max_budget_mxn_sale_total": _nullable(max_budget_sale, sale_applicable),
        "preferred_state": preferred_state,
        "preferred_municipality": preferred_municipality,
        "preferred_corridor": preferred_corridor,
        "source": source,
        "prior_searches": prior_searches,
        "prior_inquiries": prior_inquiries,
        "has_converted_before": has_converted_before,
        "lead_score_internal": lead_score_internal.round(4),
        "created_at": created_at,
        # Hidden columns (stripped before candidate output):
        "_conversion_signal": signal.round(4),
        "_median_affordability": round(median_affordability, 4),
    })

    # --- Outliers ---
    # target_area_sqm > 5000: 2%
    outlier_mask = rng.rng.random(n) < 0.02
    df = df.with_columns(
        pl.when(pl.Series(outlier_mask))
        .then(pl.Series(rng.rng.uniform(5000, 10000, size=n)).round(1))
        .otherwise(pl.col("target_area_sqm"))
        .alias("target_area_sqm"),
    )

    rent_extreme = (rng.rng.random(n) < 0.03) & rent_applicable
    sale_extreme = (rng.rng.random(n) < 0.03) & sale_applicable
    max_budget_rent_final = np.where(
        rent_extreme,
        max_budget_rent * rng.rng.uniform(3.0, 5.0, size=n),
        max_budget_rent,
    )
    max_budget_sale_final = np.where(
        sale_extreme,
        max_budget_sale * rng.rng.uniform(3.0, 5.0, size=n),
        max_budget_sale,
    )
    df = df.with_columns(
        pl.Series(
            "max_budget_mxn_rent_monthly",
            _nullable(max_budget_rent_final.round(2), rent_applicable),
        ),
        pl.Series(
            "max_budget_mxn_sale_total",
            _nullable(max_budget_sale_final.round(2), sale_applicable),
        ),
    )

    # prior_inquiries > 50: 3%
    pi_mask = rng.rng.random(n) < 0.03
    df = df.with_columns(
        pl.when(pl.Series(pi_mask))
        .then(pl.Series(rng.rng.integers(51, 200, size=n), dtype=pl.Int64))
        .otherwise(pl.col("prior_inquiries"))
        .alias("prior_inquiries"),
    )

    # --- Missingness ---
    df = _apply_mcar(df, "company_size", 0.05, rng)
    df = _apply_mcar(df, "industry", 0.03, rng)
    df = _apply_mcar(df, "preferred_corridor", 0.08, rng)
    df = _apply_mcar(df, "min_budget_mxn_rent_monthly", 0.04, rng, modalities == "rent")
    df = _apply_mcar(df, "min_budget_mxn_sale_total", 0.04, rng, modalities == "sale")

    # --- Correct dtypes ---
    df = df.with_columns([
        pl.col("created_at").str.strptime(pl.Datetime("us"), "%Y-%m-%d %H:%M:%S"),
    ])

    return df


def _assign_binned(
    rng: SeedRng, n: int, probs: list[float],
    ranges: list[int | tuple[int, int]],
) -> list[int]:
    """Assign each of n items a value from the given bin ranges."""
    cum = np.cumsum(probs)
    result: list[int] = []
    for _ in range(n):
        p = rng.rng.random()
        for j, c in enumerate(cum):
            if p < c:
                r = ranges[j]
                if isinstance(r, tuple):
                    result.append(int(rng.rng.integers(r[0], r[1] + 1)))
                else:
                    result.append(int(r))
                break
        else:
            result.append(0)
    return result


def _apply_mcar(
    df: pl.DataFrame,
    col: str,
    rate: float,
    rng: SeedRng,
    applicable_mask: np.ndarray | None = None,
) -> pl.DataFrame:
    """Apply MCAR missingness to a column."""
    n = len(df)
    mask = rng.rng.random(n) < rate
    if applicable_mask is not None:
        mask &= applicable_mask
    return df.with_columns(
        pl.when(pl.Series(mask)).then(None).otherwise(pl.col(col)).alias(col)
    )
