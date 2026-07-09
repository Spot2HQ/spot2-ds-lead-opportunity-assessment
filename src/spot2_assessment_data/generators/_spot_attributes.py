"""generate_spot_attributes — 1:1 attributes for each spot."""

from __future__ import annotations

import json
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.rng import SeedRng

_SECURITY_TYPES: Final[list[str]] = ["none", "basic", "cctv", "full"]
_SECURITY_WEIGHTS: Final[list[float]] = [0.15, 0.40, 0.30, 0.15]

_BUILDING_STATUSES: Final[list[str]] = ["new", "good", "fair", "needs_renovation"]
_BUILDING_WEIGHTS: Final[list[float]] = [0.20, 0.45, 0.25, 0.10]

_FLOOR_MATERIALS: Final[list[str]] = [
    "concrete", "ceramic", "polished_concrete", "wood", "carpet",
]
_FLOOR_WEIGHTS: Final[list[float]] = [0.35, 0.25, 0.20, 0.10, 0.10]

# Amenity pools
_AMENITY_POOL: Final[list[str]] = [
    "reception", "cafeteria", "meeting_rooms", "gym", "rooftop",
    "parking", "storage", "kitchen", "lounge", "conference_room",
    "loading_dock", "security_booth",
]


def _pick_weighted(values: list[str], weights: list[float], n: int, rng: SeedRng) -> list[str]:
    probs = np.asarray(weights, dtype=np.float64) / sum(weights)
    idx = rng.rng.choice(len(values), size=n, p=probs)
    return [values[i] for i in idx]


def generate_spot_attributes(
    spots_df: pl.DataFrame,
    rng: SeedRng,
) -> pl.DataFrame:
    """Generate spot_attributes table (1:1 with spots)."""
    n = len(spots_df)
    spot_ids = spots_df["spot_id"].to_list()
    sector_names = spots_df["sector_name"].to_list()
    area_sqm = spots_df["area_sqm"].to_numpy()

    # natural_light: 70% true (less for industrial)
    light_prob = np.where(
        np.array(sector_names) == "Industrial", 0.55, 0.75
    )
    natural_light = (rng.rng.random(n) < light_prob).tolist()

    # luminaires: 40% 0, 30% 1-5, 20% 6-15, 10% >15
    luminaires = _binned_int(rng, n, [0.40, 0.30, 0.20, 0.10], [0, (1, 5), (6, 15), (16, 40)])

    # charging_ports: 80% 0, 15% 1-5, 5% >5
    charging_ports = _binned_int(rng, n, [0.80, 0.15, 0.05], [0, (1, 5), (6, 20)])

    # security_type
    security = _pick_weighted(_SECURITY_TYPES, _SECURITY_WEIGHTS, n, rng)

    # floor_level: 50% 0, 25% 1-3, 15% 4-10, 10% >10
    floor_level = _binned_int(rng, n, [0.50, 0.25, 0.15, 0.10], [0, (1, 3), (4, 10), (11, 30)])

    # elevators: correlated with floor_level and area
    elevators = np.maximum(
        0,
        (np.array(floor_level, dtype=np.float64) / 3 + area_sqm / 500).astype(int)
        + rng.rng.poisson(1, size=n),
    ).tolist()

    # vertical_height_m: Industrial ~8, Office ~3, Retail ~4, Land ~0
    vh = np.zeros(n, dtype=np.float64)
    for i, sn in enumerate(sector_names):
        if sn == "Industrial":
            vh[i] = rng.rng.normal(8, 1.5)
        elif sn == "Office":
            vh[i] = rng.rng.normal(3, 0.5)
        elif sn == "Retail":
            vh[i] = rng.rng.normal(4, 0.8)
        else:
            vh[i] = 0.0
    vertical_height = np.maximum(0, vh).round(1)

    # parking_spaces: correlated with area
    ratio = {"Industrial": 1 / 50, "Office": 1 / 20, "Retail": 1 / 30, "Land": 0.0}
    parking = np.maximum(
        0,
        (np.array([ratio.get(s, 0) for s in sector_names]) * area_sqm + rng.rng.poisson(2, size=n)).astype(int),
    ).tolist()

    # building_status
    building_status = _pick_weighted(_BUILDING_STATUSES, _BUILDING_WEIGHTS, n, rng)

    # floor_material
    floor_material = _pick_weighted(_FLOOR_MATERIALS, _FLOOR_WEIGHTS, n, rng)

    # amenities: 60% have at least 1
    amenities: list[str] = []
    for _ in range(n):
        if rng.rng.random() < 0.6:
            count = rng.rng.integers(1, 5)
            items = rng.rng.choice(_AMENITY_POOL, size=count, replace=False).tolist()
            amenities.append(json.dumps(items, ensure_ascii=False))
        else:
            amenities.append(json.dumps([]))

    df = pl.DataFrame({
        "spot_id": spot_ids,
        "natural_light": natural_light,
        "luminaires": luminaires,
        "charging_ports": charging_ports,
        "security_type": security,
        "floor_level": floor_level,
        "elevators": elevators,
        "vertical_height_m": vertical_height.tolist(),
        "parking_spaces": parking,
        "building_status": building_status,
        "floor_material": floor_material,
        "amenities": amenities,
    })

    # --- Missingness ---
    df = _apply_mcar(df, "vertical_height_m", 0.15, rng)
    df = _apply_mcar(df, "floor_material", 0.08, rng)
    df = _apply_mcar(df, "charging_ports", 0.20, rng)

    return df


def _binned_int(
    rng: SeedRng, n: int, probs: list[float],
    ranges: list[int | tuple[int, int]],
) -> list[int]:
    """Generate binned integer values."""
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


def _apply_mcar(df: pl.DataFrame, col: str, rate: float, rng: SeedRng) -> pl.DataFrame:
    n = len(df)
    mask = rng.rng.random(n) < rate
    return df.with_columns(
        pl.when(pl.Series(mask)).then(None).otherwise(pl.col(col)).alias(col)
    )
