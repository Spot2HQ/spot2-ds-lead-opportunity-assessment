"""Distribution helpers for synthetic data generation.

Provides realistic parameterized distributions for price/sqm, area,
days-on-market, occupancy, absorption velocity, and missingness patterns
by sector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.constants import Sector
from spot2_assessment_data.rng import SeedRng

# Monthly rent price per square meter in MXN (2025-2026 market ranges).
_PRICE_PER_SQM: Final[dict[Sector, tuple[float, float, float, float]]] = {
    Sector.INDUSTRIAL: (150, 66, 94, 563),
    Sector.OFFICE: (350, 112, 112, 980),
    Sector.RETAIL: (300, 117, 100, 833),
    Sector.LAND: (50, 30, 15, 200),
}

# Area in square meters.
_AREA_SQM: Final[dict[Sector, tuple[float, float, float, float]]] = {
    Sector.INDUSTRIAL: (5_000, 8_000, 200, 80_000),
    Sector.OFFICE: (500, 1_200, 30, 20_000),
    Sector.RETAIL: (250, 600, 20, 15_000),
    Sector.LAND: (10_000, 20_000, 100, 200_000),
}

# Days on market — exponential mean by sector.
_DOM_MEAN: Final[dict[Sector, float]] = {
    Sector.INDUSTRIAL: 120.0,
    Sector.OFFICE: 90.0,
    Sector.RETAIL: 75.0,
    Sector.LAND: 180.0,
}

# Occupancy rate — beta distribution parameters (alpha, beta).
_OCCUPANCY_PARAMS: Final[dict[Sector, tuple[float, float]]] = {
    Sector.INDUSTRIAL: (6.0, 2.0),
    Sector.OFFICE: (4.0, 3.0),
    Sector.RETAIL: (5.0, 3.0),
    Sector.LAND: (2.0, 8.0),
}

# Absorption velocity — log-normal params (mean_days, std_days, floor, ceiling).
_ABSORPTION_PARAMS: Final[dict[Sector, tuple[float, float, float, float]]] = {
    Sector.INDUSTRIAL: (90.0, 60.0, 7.0, 365.0),
    Sector.OFFICE: (60.0, 40.0, 3.0, 270.0),
    Sector.RETAIL: (45.0, 30.0, 3.0, 210.0),
    Sector.LAND: (150.0, 120.0, 14.0, 730.0),
}

# Missingness specification typed contract.
@dataclass(frozen=True, slots=True)
class MissingnessSpec:
    """Specification for column-level missingness in a table."""

    table: str
    column: str
    mechanism: str  # "MCAR", "MAR", "MNAR"
    rate: float
    depends_on: str | None = None  # MAR conditioning column


def price_per_sqm(sector: Sector, rng: SeedRng) -> float:
    """Return a realistic price per square meter for the given sector."""
    mean, std, floor, ceiling = _PRICE_PER_SQM[sector]
    return rng.log_normal(mean, std, floor, ceiling)


def area_sqm(sector: Sector, rng: SeedRng) -> float:
    """Return a realistic area in sqm for the given sector."""
    mean, std, floor, ceiling = _AREA_SQM[sector]
    return rng.log_normal(mean, std, floor, ceiling)


def days_on_market(rng: SeedRng, sector: Sector | None = None) -> int:
    """Return days-on-market drawn from an exponential distribution.

    If sector is provided, uses sector-specific mean; otherwise defaults to 90.
    """
    mean = _DOM_MEAN.get(sector, 90.0) if sector else 90.0
    return max(1, int(rng.rng.exponential(mean)))


def occupancy_rate(sector: Sector, rng: SeedRng) -> float:
    """Return a sector-appropriate occupancy rate in [0, 1]."""
    alpha, beta = _OCCUPANCY_PARAMS[sector]
    return float(rng.rng.beta(alpha, beta))


def absorption_velocity(sector: Sector, rng: SeedRng) -> int:
    """Return days-to-absorb for the given sector."""
    mean, std, floor, ceiling = _ABSORPTION_PARAMS[sector]
    return max(1, int(rng.log_normal(mean, std, floor, ceiling)))


def apply_missingness(
    df: pl.DataFrame, specs: list[MissingnessSpec], rng: SeedRng
) -> pl.DataFrame:
    """Apply MCAR / MAR / MNAR missingness to a DataFrame in-place.

    Args:
        df: Input DataFrame.
        specs: List of missingness specifications.
        rng: Seeded RNG for reproducibility.

    Returns:
        DataFrame with nulls applied (mutates input df for efficiency).
    """
    for spec in specs:
        col = spec.column
        if col not in df.columns:
            continue
        n = len(df)
        mask: np.ndarray
        match spec.mechanism:
            case "MCAR":
                mask = rng.rng.random(n) < spec.rate
            case "MAR" if spec.depends_on and spec.depends_on in df.columns:
                dep_col = df[spec.depends_on].to_numpy().flatten()
                dep_max = dep_col.max() or 1.0
                prob = (dep_col / dep_max) * spec.rate * 2
                mask = rng.rng.random(n) < np.clip(prob, 0, 0.95)
            case "MNAR":
                vals = df[col].to_numpy().flatten()
                with np.errstate(invalid="ignore"):
                    extremeness = np.abs(vals - np.nanmean(vals)) / (np.nanstd(vals) or 1.0)
                prob = np.nan_to_num(extremeness / extremeness.max() * spec.rate * 2, nan=0)
                mask = rng.rng.random(n) < np.clip(prob, 0, 0.95)
            case _:
                continue
        df = df.with_columns(
            pl.when(pl.Series(mask)).then(None).otherwise(pl.col(col)).alias(col)
        )
    return df
