"""Deterministic RNG helpers for synthetic data generation.

Wraps numpy.random.Generator with a seed from config and provides
helpers for jitter, log-normal, categorical, and temporal split.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig

# Approximate degrees per km at the equator — fine for Mexico's latitudes.
_DEG_PER_KM: Final[float] = 1.0 / 111.32


@dataclass(frozen=True, slots=True)
class SeedRng:
    """Deterministic RNG wrapper seeded from config."""

    rng: np.random.Generator  # noqa: MUTABLE_OK — numpy Generator is thread-safe but has internal state

    @classmethod
    def from_config(cls, config: AssessmentConfig) -> SeedRng:
        """Create a SeedRng from config's seed value."""
        return cls(rng=np.random.default_rng(config.seed))

    def jitter(self, lat: float, lon: float, max_km: float) -> tuple[float, float]:
        """Add bounded uniform noise in km to (lat, lon).

        The jitter is bounded such that the resulting coordinate stays within
        `max_km` of the original point. Applies independent uniform noise to
        lat and lon components, then normalizes displacement.
        """
        if max_km <= 0:
            return lat, lon
        r = self.rng.uniform(0, max_km)
        theta = self.rng.uniform(0, 2 * np.pi)
        d_lat = r * np.cos(theta) * _DEG_PER_KM
        d_lon = r * np.sin(theta) * _DEG_PER_KM
        # Adjust lon delta for latitude (meridians converge toward poles).
        d_lon /= np.cos(np.radians(lat))
        return lat + d_lat, lon + d_lon

    def log_normal(
        self, mean: float, std: float, floor: float, ceiling: float
    ) -> float:
        """Draw from log-normal distribution clamped to [floor, ceiling]."""
        sigma = np.sqrt(np.log1p((std / mean) ** 2))
        mu = np.log(mean) - 0.5 * sigma**2
        value = float(self.rng.lognormal(mu, sigma))
        return max(floor, min(ceiling, value))

    def categorical_weighted(
        self, categories: list[str], weights: list[float]
    ) -> str:
        """Pick a category by weighted random choice."""
        probs = np.asarray(weights, dtype=np.float64)
        probs /= probs.sum()
        idx = self.rng.choice(len(categories), p=probs)
        return categories[idx]

    def temporal_split(
        self, df: pl.DataFrame, ratios: list[float]
    ) -> tuple[pl.DataFrame, ...]:
        """Split a DataFrame into train/val/test by date-based shuffle.

        Applies ratios sequentially: the remaining portion after each split
        is used for subsequent splits. A final residual partition is always
        included even if ratios are an exact partition of 1.0.
        """
        if not ratios:
            return (df,)
        n = len(df)
        indices = self.rng.permutation(n)
        splits: list[pl.DataFrame] = []
        start = 0
        remaining_ratio = 1.0
        for ratio in ratios:
            size = int(n * ratio)
            splits.append(df[indices[start : start + size]])
            start += size
            remaining_ratio -= ratio
        if remaining_ratio > 0 or len(splits) < len(ratios) + 1:
            splits.append(df[indices[start:]])
        return tuple(splits)
