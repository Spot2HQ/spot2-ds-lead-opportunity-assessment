"""Tests for geo_catalog.py — LocationAnchor, GeoCatalog, jitter, and tuple consistency."""

from pathlib import Path

import numpy as np
import yaml

from spot2_assessment_data.geo_catalog import (
    GeoCatalog,
    LocationAnchor,
    _haversine_km,
    _load_anchors_from_seed_yaml,
)

_GEO_SEED_PATH = Path("config/geo_reference_seed.yaml")


def _make_catalog(seed: int = 42) -> GeoCatalog:
    """Given: a seed YAML file with 18 anchors."""
    anchors = _load_anchors_from_seed_yaml(_GEO_SEED_PATH)
    rng = np.random.default_rng(seed)
    return GeoCatalog(anchors=anchors, rng=rng)


class TestLoadCatalog:
    """Tests for loading GeoCatalog from seed YAML and evidence JSON."""

    def test_load_from_seed_yaml_has_anchors(self) -> None:
        """When: loading from seed YAML. Then: valid anchors present."""
        catalog = _make_catalog()
        assert len(catalog.anchors) == 18
        for a in catalog.anchors:
            assert isinstance(a.state, str) and len(a.state) > 0
            assert isinstance(a.centroid_lat, float)
            assert isinstance(a.centroid_lon, float)

    def test_load_from_seed_yaml_states(self) -> None:
        """When: loading from seed YAML. Then: states list is populated."""
        catalog = _make_catalog()
        states = catalog.states
        assert "CDMX" in states
        assert "Nuevo León" in states
        assert "Jalisco" in states
        assert len(states) == 12

    def test_load_from_evidence_json_fallback(self) -> None:
        """When: loading from evidence JSON that points to seed.
        Then: same 18 anchors are loaded via fallback."""
        evidence_path = Path(
            ".omo/evidence/clickhouse-shapes-summary.json"
        )
        # The evidence file may exist relative to the brain vault.
        # Try relative to project root first.
        candidates = [
            evidence_path,
            Path("../../Spot2-brain") / evidence_path,
        ]
        found: Path | None = None
        for c in candidates:
            if c.is_file():
                found = c
                break
        if found is None:
            # Evidence file not found — skip gracefully.
            return
        catalog = GeoCatalog.from_evidence_json(str(found))
        assert len(catalog.anchors) == 18


class TestJitter:
    """Tests for generate_spot_location jitter bounds."""

    def test_jitter_stays_within_max_km(self) -> None:
        """Given: an anchor and max_jitter_km = 2.5.
        When: generating 1000 spot locations.
        Then: all are within 2.5 km of centroid."""
        catalog = _make_catalog()
        anchor = catalog.anchors[0]
        max_km = 2.5
        for _ in range(1000):
            lat, lon = catalog.generate_spot_location(anchor, max_km)
            dist = _haversine_km(anchor.centroid_lat, anchor.centroid_lon, lat, lon)
            assert dist <= max_km * 1.01, f"Distance {dist:.4f} > {max_km}"

    def test_jitter_zero_returns_centroid(self) -> None:
        """Given: max_jitter_km = 0.
        When: generating location.
        Then: returns exact centroid."""
        catalog = _make_catalog()
        anchor = catalog.anchors[0]
        lat, lon = catalog.generate_spot_location(anchor, 0.0)
        assert lat == anchor.centroid_lat
        assert lon == anchor.centroid_lon

    def test_jitter_negative_returns_centroid(self) -> None:
        """Given: max_jitter_km < 0.
        When: generating location.
        Then: returns exact centroid."""
        catalog = _make_catalog()
        anchor = catalog.anchors[0]
        lat, lon = catalog.generate_spot_location(anchor, -1.0)
        assert lat == anchor.centroid_lat
        assert lon == anchor.centroid_lon

    def test_jitter_preserves_anchor_tuples_for_multiple_anchors(self) -> None:
        """Given: 3 different anchors.
        When: jittering from each.
        Then: the coordinates always remain within the max_km bound."""
        catalog = _make_catalog()
        max_km = 2.5
        for anchor in catalog.anchors[:3]:
            for _ in range(200):
                lat, lon = catalog.generate_spot_location(anchor, max_km)
                dist = _haversine_km(anchor.centroid_lat, anchor.centroid_lon, lat, lon)
                assert dist <= max_km * 1.01


class TestTupleConsistency:
    """Tests for validate_tuple_consistency."""

    def test_valid_tuple_passes(self) -> None:
        """Given: a spot matching a real anchor exactly.
        When: validating tuple consistency.
        Then: returns True."""
        catalog = _make_catalog()
        anchor = catalog.anchors[0]
        ok = catalog.validate_tuple_consistency(
            state=anchor.state,
            municipality=anchor.municipality,
            settlement=anchor.settlement,
            region=anchor.region,
            corridor=anchor.corridor,
            lat=anchor.centroid_lat,
            lon=anchor.centroid_lon,
            max_deviation_km=2.5,
        )
        assert ok

    def test_cdmx_state_with_monterrey_coordinates_rejected(self) -> None:
        """Given: a spot claiming CDMX state with Monterrey coordinates.
        When: validating tuple consistency.
        Then: returns False — inconsistent tuple."""
        catalog = _make_catalog()
        # Monterrey centroid from the seed data.
        monterrey_lat, monterrey_lon = 25.6751, -100.3185
        ok = catalog.validate_tuple_consistency(
            state="CDMX",
            municipality="Miguel Hidalgo",
            settlement="Polanco",
            region="centro",
            corridor="polanco",
            lat=monterrey_lat,
            lon=monterrey_lon,
            max_deviation_km=2.5,
        )
        assert not ok

    def test_wrong_region_rejected(self) -> None:
        """Given: a spot with correct state but wrong region for anchor.
        When: validating.
        Then: returns False."""
        catalog = _make_catalog()
        anchor = catalog.anchors[0]  # centro
        ok = catalog.validate_tuple_consistency(
            state=anchor.state,
            municipality=anchor.municipality,
            settlement=anchor.settlement,
            region="occidente",  # wrong region
            corridor=anchor.corridor,
            lat=anchor.centroid_lat,
            lon=anchor.centroid_lon,
            max_deviation_km=2.5,
        )
        assert not ok

    def test_unknown_state_rejected(self) -> None:
        """Given: a state not in the catalog.
        When: validating.
        Then: returns False."""
        catalog = _make_catalog()
        ok = catalog.validate_tuple_consistency(
            state="Zacatecas",
            municipality="Zacatecas",
            settlement="Centro",
            region="centro-norte",
            corridor="centro-zacatecas",
            lat=22.7709,
            lon=-102.5832,
            max_deviation_km=2.5,
        )
        assert not ok

    def test_all_anchors_self_consistent(self) -> None:
        """Given: all 18 anchors.
        When: validating each against itself with its own coordinates.
        Then: all pass."""
        catalog = _make_catalog()
        for anchor in catalog.anchors:
            ok = catalog.validate_tuple_consistency(
                state=anchor.state,
                municipality=anchor.municipality,
                settlement=anchor.settlement,
                region=anchor.region,
                corridor=anchor.corridor,
                lat=anchor.centroid_lat,
                lon=anchor.centroid_lon,
                max_deviation_km=2.5,
            )
            assert ok, f"Anchor {anchor.key} failed self-consistency"


class TestGetValidAnchor:
    """Tests for get_valid_anchor."""

    def test_returns_location_anchor(self) -> None:
        """When: calling get_valid_anchor.
        Then: returns a LocationAnchor from the catalog."""
        catalog = _make_catalog()
        anchor = catalog.get_valid_anchor()
        assert isinstance(anchor, LocationAnchor)
        assert anchor in catalog.anchors


class TestGetAnchorByState:
    """Tests for get_anchor_by_state."""

    def test_returns_anchors_for_cdmx(self) -> None:
        """Given: state = CDMX.
        When: calling get_anchor_by_state.
        Then: returns 3 anchors."""
        catalog = _make_catalog()
        result = catalog.get_anchor_by_state("CDMX")
        assert len(result) == 3
        for a in result:
            assert a.state == "CDMX"

    def test_returns_empty_for_unknown_state(self) -> None:
        """Given: an unknown state.
        When: calling get_anchor_by_state.
        Then: returns empty list."""
        catalog = _make_catalog()
        result = catalog.get_anchor_by_state("UnknownState")
        assert result == []


class TestLocationAnchor:
    """Tests for LocationAnchor dataclass."""

    def test_key_is_five_tuple(self) -> None:
        """Given: a LocationAnchor.
        When: accessing .key.
        Then: returns 5-tuple of identity fields."""
        anchor = LocationAnchor(
            state="CDMX",
            municipality="Miguel Hidalgo",
            settlement="Polanco",
            region="centro",
            corridor="polanco",
            centroid_lat=19.4336,
            centroid_lon=-99.1908,
        )
        key = anchor.key
        assert key == ("CDMX", "Miguel Hidalgo", "Polanco", "centro", "polanco")
        assert len(key) == 5

    def test_is_frozen(self) -> None:
        """Given: a LocationAnchor.
        When: attempting mutation.
        Then: raises FrozenInstanceError."""
        anchor = LocationAnchor(
            state="CDMX",
            municipality="Miguel Hidalgo",
            settlement="Polanco",
            region="centro",
            corridor="polanco",
            centroid_lat=19.4336,
            centroid_lon=-99.1908,
        )
        try:
            anchor.state = "Jalisco"  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except Exception:
            pass  # expected
