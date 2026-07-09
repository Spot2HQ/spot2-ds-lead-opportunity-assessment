"""Geography catalog for synthetic data location generation.

Provides LocationAnchor typed dataclass, GeoCatalog for loading anchors
from ClickHouse evidence JSON or fallback seed YAML, and helpers for
bounded jitter and tuple consistency validation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NewType

import numpy as np
import yaml

from spot2_assessment_data.config import AssessmentConfig

_KM_PER_DEG_LAT: Final[float] = 111.32
_EVIDENCE_PATH: Final[Path] = Path(
    ".omo/evidence/clickhouse-shapes-summary.json"
)
_GEO_SEED_PATH: Final[Path] = Path("config/geo_reference_seed.yaml")

# NewType for branded coordinate components.
Latitude = NewType("Latitude", float)
Longitude = NewType("Longitude", float)


@dataclass(frozen=True, slots=True)
class LocationAnchor:
    """A validated geographic anchor — a real place in Mexico with a centroid.

    All fields are frozen. An anchor identifies a unique geographic identity
    tuple used for consistent location generation.
    """

    state: str
    municipality: str
    settlement: str
    region: str
    corridor: str
    centroid_lat: float
    centroid_lon: float

    @property
    def latent(self) -> Latitude:
        """Branded latitude for the anchor centroid."""
        return Latitude(self.centroid_lat)

    @property
    def lonent(self) -> Longitude:
        """Branded longitude for the anchor centroid."""
        return Longitude(self.centroid_lon)

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        """Immutable identity tuple: (state, municipality, settlement, region, corridor)."""
        return (self.state, self.municipality, self.settlement, self.region, self.corridor)


def _load_anchors_from_seed_yaml(path: Path) -> list[LocationAnchor]:
    """Load location anchors from the seed YAML config."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        LocationAnchor(
            state=loc["state"],
            municipality=loc["municipality"],
            settlement=loc["settlement"],
            region=loc["region"],
            corridor=loc["corridor"],
            centroid_lat=loc["centroid_lat"],
            centroid_lon=loc["centroid_lon"],
        )
        for loc in raw["locations"]
    ]


def _load_anchors_from_evidence(path: Path) -> list[LocationAnchor]:
    """Load location anchors from ClickHouse evidence JSON.

    If the evidence JSON points to a seed fallback, follows that path.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    summary = raw["geo_reference_summary"]
    if summary["source"] == "seed_config":
        fallback_path = Path(raw.get("fallback_source", ""))
        if fallback_path.is_file():
            return _load_anchors_from_seed_yaml(fallback_path)
    return [
        LocationAnchor(
            state=t["state"],
            municipality=t["municipality"],
            settlement=t["settlement"],
            region=t["region"],
            corridor=t["corridor"],
            centroid_lat=t["centroid_lat"],
            centroid_lon=t["centroid_lon"],
        )
        for t in summary.get("sample_tuples", [])
    ]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points in km."""
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


class GeoCatalog:
    """Catalog of geographic reference anchors for synthetic data generation.

    Loads anchors from ClickHouse evidence JSON or fallback seed YAML.
    Exposes only valid (state, municipality, settlement, region, corridor)
    tuples that correspond to real Mexican locations.
    """

    def __init__(
        self,
        anchors: list[LocationAnchor] | None = None,
        rng: np.random.Generator | None = None,
    ) -> None:
        """Create a GeoCatalog.

        Args:
            anchors: Pre-built list of anchors. If None, loads from evidence or seed.
            rng: numpy Generator for random anchor selection. Defaults to seeded RNG.
        """
        self._anchors = anchors if anchors is not None else self._load_default_anchors()
        self._rng = rng if rng is not None else np.random.default_rng(42)
        self._by_state: dict[str, list[LocationAnchor]] = {}
        for a in self._anchors:
            self._by_state.setdefault(a.state, []).append(a)

    @staticmethod
    def _load_default_anchors() -> list[LocationAnchor]:
        """Try evidence JSON first, then fall back to seed YAML."""
        evidence_path = _EVIDENCE_PATH
        if evidence_path.is_file():
            return _load_anchors_from_evidence(evidence_path)
        return _load_anchors_from_seed_yaml(_GEO_SEED_PATH)

    @staticmethod
    def from_seed_yaml(path: Path | str) -> GeoCatalog:
        """Create a GeoCatalog from a specific seed YAML file."""
        return GeoCatalog(anchors=_load_anchors_from_seed_yaml(Path(path)))

    @staticmethod
    def from_evidence_json(path: Path | str) -> GeoCatalog:
        """Create a GeoCatalog from a specific evidence JSON file."""
        return GeoCatalog(anchors=_load_anchors_from_evidence(Path(path)))

    @property
    def anchors(self) -> list[LocationAnchor]:
        """All loaded anchors (read-only)."""
        return self._anchors

    @property
    def states(self) -> list[str]:
        """Sorted list of unique states in the catalog."""
        return sorted({a.state for a in self._anchors})

    def get_valid_anchor(self) -> LocationAnchor:
        """Return a random valid anchor from the catalog."""
        idx = self._rng.integers(0, len(self._anchors))
        return self._anchors[idx]

    def get_anchor_by_state(self, state: str) -> list[LocationAnchor]:
        """Return all anchors for a given state (empty list if none)."""
        return self._by_state.get(state, [])

    def generate_spot_location(
        self, anchor: LocationAnchor, max_jitter_km: float
    ) -> tuple[float, float]:
        """Generate a (lat, lon) with bounded jitter from an anchor centroid.

        The jittered coordinate is guaranteed to stay within `max_jitter_km`
        of the centroid.

        Args:
            anchor: The anchor to jitter from.
            max_jitter_km: Maximum displacement in km.

        Returns:
            (latitude, longitude) tuple.
        """
        if max_jitter_km <= 0:
            return anchor.centroid_lat, anchor.centroid_lon
        r = self._rng.uniform(0, max_jitter_km)
        theta = self._rng.uniform(0, 2 * np.pi)

        d_lat = r * np.cos(theta) / _KM_PER_DEG_LAT
        d_lon = r * np.sin(theta) / (_KM_PER_DEG_LAT * np.cos(np.radians(anchor.centroid_lat)))

        lat = anchor.centroid_lat + d_lat
        lon = anchor.centroid_lon + d_lon
        return lat, lon

    def validate_tuple_consistency(
        self, state: str, municipality: str, settlement: str,
        region: str, corridor: str, lat: float, lon: float,
        max_deviation_km: float,
    ) -> bool:
        """Check if a spot row is consistent with a valid anchor.

        Args:
            state, municipality, settlement, region, corridor: Tuple fields.
            lat, lon: Spot coordinates.
            max_deviation_km: Maximum allowed distance from anchor centroid.

        Returns:
            True if the tuple matches a valid anchor and coordinates are within bounds.
        """
        for anchor in self._by_state.get(state, []):
            if (
                anchor.municipality == municipality
                and anchor.settlement == settlement
                and anchor.region == region
                and anchor.corridor == corridor
            ):
                dist = _haversine_km(anchor.centroid_lat, anchor.centroid_lon, lat, lon)
                return dist <= max_deviation_km
        return False
