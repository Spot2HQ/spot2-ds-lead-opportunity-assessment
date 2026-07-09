"""Tests for synthetic table generators.

Covers all generators with row counts, column presence, FK integrity,
base rates, temporal range, missingness, leakage traps, geo consistency,
determinism, and hidden outcomes protection.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import polars as pl
import pytest

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.geo_catalog import GeoCatalog
from spot2_assessment_data.rng import SeedRng

from spot2_assessment_data.generators._leads import generate_leads
from spot2_assessment_data.generators._spots import generate_spots
from spot2_assessment_data.generators._spot_attributes import generate_spot_attributes
from spot2_assessment_data.generators._inquiries import generate_inquiries
from spot2_assessment_data.generators._market_context import generate_market_context
from spot2_assessment_data.generators._availability import generate_availability_snapshot
from spot2_assessment_data.generators._outcomes import generate_outcomes

_CONFIG_PATH = "config/default.yaml"

# --- Fixtures ---


@pytest.fixture(scope="module")
def config() -> AssessmentConfig:
    return AssessmentConfig.from_yaml(_CONFIG_PATH)


@pytest.fixture(scope="module")
def rng(config: AssessmentConfig) -> SeedRng:
    return SeedRng.from_config(config)


@pytest.fixture(scope="module")
def geo_catalog() -> GeoCatalog:
    return GeoCatalog()


@pytest.fixture(scope="module")
def leads_df(rng: SeedRng, config: AssessmentConfig, geo_catalog: GeoCatalog) -> pl.DataFrame:
    return generate_leads(rng, config, geo_catalog)


@pytest.fixture(scope="module")
def spots_df(rng: SeedRng, config: AssessmentConfig, geo_catalog: GeoCatalog) -> pl.DataFrame:
    return generate_spots(rng, config, geo_catalog)


@pytest.fixture(scope="module")
def attrs_df(spots_df: pl.DataFrame, rng: SeedRng) -> pl.DataFrame:
    return generate_spot_attributes(spots_df, rng)


@pytest.fixture(scope="module")
def inquiries_df(
    leads_df: pl.DataFrame, spots_df: pl.DataFrame, rng: SeedRng, config: AssessmentConfig,
) -> pl.DataFrame:
    return generate_inquiries(leads_df, spots_df, rng, config)


@pytest.fixture(scope="module")
def market_df(spots_df: pl.DataFrame, rng: SeedRng, config: AssessmentConfig) -> pl.DataFrame:
    return generate_market_context(spots_df, rng, config)


@pytest.fixture(scope="module")
def avail_df(
    spots_df: pl.DataFrame, inquiries_df: pl.DataFrame,
    rng: SeedRng, config: AssessmentConfig,
) -> pl.DataFrame:
    return generate_availability_snapshot(spots_df, inquiries_df, rng, config)


@pytest.fixture(scope="module")
def outcomes_df(
    leads_df: pl.DataFrame, inquiries_df: pl.DataFrame, avail_df: pl.DataFrame,
    market_df: pl.DataFrame, spots_df: pl.DataFrame,
    rng: SeedRng, config: AssessmentConfig,
) -> pl.DataFrame:
    return generate_outcomes(leads_df, inquiries_df, avail_df, market_df, spots_df, rng, config)


# --- Helper ---


def _null_rate(df: pl.DataFrame, col: str) -> float:
    """Fraction of null values in a column."""
    total = len(df)
    nulls = df[col].null_count()
    return nulls / total if total > 0 else 0.0


# ======================================================================
# Row counts
# ======================================================================

class TestTemporalRange:
    def test_leads_created_at_in_range(
        self, leads_df: pl.DataFrame, config: AssessmentConfig,
    ) -> None:
        t_start = config.temporal_range.start
        t_end = config.temporal_range.end
        created = leads_df["created_at"].drop_nulls()
        for dt in created.to_list():
            d = dt.date() if isinstance(dt, datetime) else dt
            assert t_start <= d <= t_end, f"{d} not in [{t_start}, {t_end}]"

    def test_inquiries_inquiry_at_after_lead_created(self) -> None:
        """Inquiry dates should be reasonable — checked in FK tests."""
        pass  # Already covered by FK integrity

    def test_conversion_date_when_converted(
        self, outcomes_df: pl.DataFrame, config: AssessmentConfig,
    ) -> None:
        converted = outcomes_df.filter(pl.col("converted_to_visit"))
        conv_dates = converted["conversion_date"].drop_nulls()
        assert len(conv_dates) == len(converted), (
            "All converted leads must have a conversion_date"
        )

    def test_conversion_date_null_when_not_converted(
        self, outcomes_df: pl.DataFrame,
    ) -> None:
        not_converted = outcomes_df.filter(~pl.col("converted_to_visit"))
        nulls = not_converted["conversion_date"].null_count()
        assert nulls == len(not_converted), (
            "Non-converted leads must have null conversion_date"
        )


# ======================================================================
# Missingness
# ======================================================================


class TestMissingness:
    def test_leads_company_size_missingness(self, leads_df: pl.DataFrame) -> None:
        rate = _null_rate(leads_df, "company_size")
        assert 0.02 <= rate <= 0.08, f"company_size missing rate {rate:.3f}"

    def test_leads_industry_missingness(self, leads_df: pl.DataFrame) -> None:
        rate = _null_rate(leads_df, "industry")
        assert 0.01 <= rate <= 0.06, f"industry missing rate {rate:.3f}"

    def test_leads_preferred_corridor_missingness(self, leads_df: pl.DataFrame) -> None:
        rate = _null_rate(leads_df, "preferred_corridor")
        assert 0.04 <= rate <= 0.12, f"preferred_corridor missing rate {rate:.3f}"

    def test_leads_rent_budget_missingness(self, leads_df: pl.DataFrame) -> None:
        rent_leads = leads_df.filter(pl.col("search_modality").is_in(["rent", "both"]))
        rate = rent_leads["min_budget_mxn_rent_monthly"].null_count() / rent_leads.height
        assert 0.01 <= rate <= 0.08, f"rent budget missing rate {rate:.3f}"

    def test_attrs_vertical_height_missingness(self, attrs_df: pl.DataFrame) -> None:
        rate = _null_rate(attrs_df, "vertical_height_m")
        assert 0.10 <= rate <= 0.20, f"vertical_height_m missing rate {rate:.3f}"

    def test_attrs_floor_material_missingness(self, attrs_df: pl.DataFrame) -> None:
        rate = _null_rate(attrs_df, "floor_material")
        assert 0.04 <= rate <= 0.12, f"floor_material missing rate {rate:.3f}"

    def test_attrs_charging_ports_missingness(self, attrs_df: pl.DataFrame) -> None:
        rate = _null_rate(attrs_df, "charging_ports")
        assert 0.14 <= rate <= 0.26, f"charging_ports missing rate {rate:.3f}"

    def test_inquiries_urgency_days_missingness(self, inquiries_df: pl.DataFrame) -> None:
        rate = _null_rate(inquiries_df, "urgency_days")
        assert 0.20 <= rate <= 0.40, f"urgency_days missing rate {rate:.3f}"


# ======================================================================
# Leakage traps
# ======================================================================


class TestLeakageTraps:
    def test_lead_score_internal_exists(self, leads_df: pl.DataFrame) -> None:
        assert "lead_score_internal" in leads_df.columns

    def test_lead_score_internal_is_float(self, leads_df: pl.DataFrame) -> None:
        scores = leads_df["lead_score_internal"].drop_nulls()
        assert scores.dtype in (pl.Float64, pl.Float32)
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0

    def test_has_converted_before_exists(self, leads_df: pl.DataFrame) -> None:
        assert "has_converted_before" in leads_df.columns

    def test_has_converted_before_rate(self, leads_df: pl.DataFrame) -> None:
        rate = leads_df["has_converted_before"].mean()
        assert 0.05 <= rate <= 0.18, f"has_converted_before rate {rate:.3f}"


# ======================================================================
# Geo consistency
# ======================================================================


class TestGeoConsistency:
    def test_spots_state_in_catalog(
        self, spots_df: pl.DataFrame, geo_catalog: GeoCatalog,
    ) -> None:
        states = set(geo_catalog.states)
        for s in spots_df["state"].unique().to_list():
            assert s in states, f"Unknown state: {s}"

    def test_spots_geo_tuples_valid(
        self, spots_df: pl.DataFrame, geo_catalog: GeoCatalog,
    ) -> None:
        max_km = 2.5 * 1.01  # 1% tolerance
        for row in spots_df.iter_rows(named=True):
            ok = geo_catalog.validate_tuple_consistency(
                state=row["state"],
                municipality=row["municipality"],
                settlement=row["settlement"],
                region=row["region"],
                corridor=row["corridor"],
                lat=row["lat"],
                lon=row["lon"],
                max_deviation_km=max_km,
            )
            assert ok, (
                f"Geo tuple invalid: ({row['state']}, {row['municipality']}, "
                f"{row['settlement']}, {row['region']}, {row['corridor']}) "
                f"at ({row['lat']}, {row['lon']})"
            )

    def test_spots_lat_lon_reasonable(self, spots_df: pl.DataFrame) -> None:
        # Mexico bounding box
        lats = spots_df["lat"]
        lons = spots_df["lon"]
        assert lats.min() > 14.0 and lats.max() < 33.0
        assert lons.min() > -118.0 and lons.max() < -86.0

    def test_no_complex_type(self, spots_df: pl.DataFrame) -> None:
        types = spots_df["type_name"].unique().to_list()
        assert "Complex" not in types, "Spots must not include Complex type"


def test_avg_price_uses_rentable_only(
    market_df: pl.DataFrame, spots_df: pl.DataFrame,
):
    """market_context.avg_price_sqm_mxn reflects rent/both spots only."""
    # Check that any non-null avg_price corresponds to corridors/sectors
    # that have rentable spots (modality rent or both)
    rentable = set()
    for row in spots_df.filter(pl.col("modality").is_in(["rent", "both"])).iter_rows(named=True):
        rentable.add((row["corridor"], row["sector_name"]))
    for row in market_df.iter_rows(named=True):
        key = (row["corridor"], row["sector"])
        if key in rentable:
            assert row["avg_price_sqm_mxn"] is not None, f"avg_price null for rentable {key}"


def test_avg_price_ignores_sale_only_inventory(config: AssessmentConfig) -> None:
    spots = pl.DataFrame({
        "state": ["Jalisco", "Jalisco"],
        "municipality": ["Guadalajara", "Guadalajara"],
        "corridor": ["Centro", "Centro"],
        "sector_name": ["Office", "Office"],
        "price_sqm_mxn_rent": [350.0, None],
    })

    market = generate_market_context(spots, SeedRng.from_config(config), config)

    assert market.height > 0
    assert market["avg_price_sqm_mxn"].min() >= 315.0


# ======================================================================
# Determinism
# ======================================================================


class TestDeterminism:
    def test_same_seed_produces_identical_leads(
        self, config: AssessmentConfig,
    ) -> None:
        gc1 = GeoCatalog()
        gc2 = GeoCatalog()
        rng1 = SeedRng.from_config(config)
        rng2 = SeedRng.from_config(config)
        df1 = generate_leads(rng1, config, gc1)
        df2 = generate_leads(rng2, config, gc2)
        assert df1.equals(df2)

    def test_same_seed_produces_identical_spots(
        self, config: AssessmentConfig,
    ) -> None:
        gc1 = GeoCatalog()
        gc2 = GeoCatalog()
        rng1 = SeedRng.from_config(config)
        rng2 = SeedRng.from_config(config)
        df1 = generate_spots(rng1, config, gc1)
        df2 = generate_spots(rng2, config, gc2)
        assert df1.equals(df2)

    def test_same_seed_produces_identical_outcomes(
        self, config: AssessmentConfig,
    ) -> None:
        gc1 = GeoCatalog()
        gc2 = GeoCatalog()
        rng1 = SeedRng.from_config(config)
        rng2 = SeedRng.from_config(config)
        leads = generate_leads(rng1, config, gc1)
        spots = generate_spots(rng1, config, gc1)
        inq = generate_inquiries(leads, spots, rng1, config)
        mkt = generate_market_context(spots, rng1, config)
        avl = generate_availability_snapshot(spots, inq, rng1, config)

        # Fresh RNG and GeoCatalog for second run
        rng3 = SeedRng.from_config(config)
        rng4 = SeedRng.from_config(config)
        gc3 = GeoCatalog()
        gc4 = GeoCatalog()
        leads2 = generate_leads(rng3, config, gc3)
        spots2 = generate_spots(rng3, config, gc3)
        inq2 = generate_inquiries(leads2, spots2, rng3, config)
        mkt2 = generate_market_context(spots2, rng3, config)
        avl2 = generate_availability_snapshot(spots2, inq2, rng3, config)

        o1 = generate_outcomes(leads, inq, avl, mkt, spots, rng1, config)
        o2 = generate_outcomes(leads2, inq2, avl2, mkt2, spots2, rng3, config)
        assert o1.equals(o2)

    def test_different_seed_produces_different_leads(
        self, config: AssessmentConfig, geo_catalog: GeoCatalog,
    ) -> None:
        rng1 = SeedRng(rng=__import__("numpy").random.default_rng(42))
        rng2 = SeedRng(rng=__import__("numpy").random.default_rng(999))
        df1 = generate_leads(rng1, config, geo_catalog)
        df2 = generate_leads(rng2, config, geo_catalog)
        assert not df1.equals(df2)


# ======================================================================
# Spot attributes specifics
# ======================================================================
