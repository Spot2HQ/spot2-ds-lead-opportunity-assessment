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

class TestRowCounts:
    def test_leads_count(self, leads_df: pl.DataFrame, config: AssessmentConfig) -> None:
        target = config.row_counts.leads
        assert abs(len(leads_df) - target) <= target * 0.05

    def test_spots_count(self, spots_df: pl.DataFrame, config: AssessmentConfig) -> None:
        target = config.row_counts.spots
        assert abs(len(spots_df) - target) <= target * 0.05

    def test_attrs_count_1to1_spots(self, attrs_df: pl.DataFrame, spots_df: pl.DataFrame) -> None:
        assert len(attrs_df) == len(spots_df)

    def test_inquiries_count(self, inquiries_df: pl.DataFrame, config: AssessmentConfig) -> None:
        target = config.row_counts.inquiries
        assert abs(len(inquiries_df) - target) <= target * 0.20

    def test_market_context_count(self, market_df: pl.DataFrame, config: AssessmentConfig) -> None:
        target = config.row_counts.market_context
        assert len(market_df) <= target * 1.20

    def test_availability_count(self, avail_df: pl.DataFrame, config: AssessmentConfig) -> None:
        target = config.row_counts.availability_snapshot
        assert abs(len(avail_df) - target) <= target * 0.05

    def test_outcomes_count(self, outcomes_df: pl.DataFrame, config: AssessmentConfig) -> None:
        target = config.row_counts.outcomes
        assert abs(len(outcomes_df) - target) <= target * 0.05


# ======================================================================
# Column presence
# ======================================================================


class TestColumnPresence:
    def test_leads_columns(self, leads_df: pl.DataFrame) -> None:
        expected = {
            "lead_id", "user_type", "company_size", "industry",
            "search_sector", "search_modality", "target_area_sqm",
            "min_budget_mxn", "max_budget_mxn", "preferred_state",
            "preferred_municipality", "preferred_corridor", "source",
            "prior_searches", "prior_inquiries", "has_converted_before",
            "lead_score_internal", "created_at",
        }
        assert expected.issubset(set(leads_df.columns))

    def test_spots_columns(self, spots_df: pl.DataFrame) -> None:
        expected = {
            "spot_id", "broker_id", "sector_name", "type_name",
            "state", "municipality", "settlement", "corridor", "region",
            "lat", "lon", "title", "description", "area_sqm",
            "price_sqm_mxn_rent", "price_sqm_mxn_sale",
            "price_total_mxn_rent", "price_total_mxn_sale",
            "maintenance_cost_mxn", "modality", "days_on_market",
            "total_inquiries", "total_views", "is_active", "created_at",
        }
        assert expected.issubset(set(spots_df.columns))

    def test_attrs_columns(self, attrs_df: pl.DataFrame) -> None:
        expected = {
            "spot_id", "natural_light", "luminaires", "charging_ports",
            "security_type", "floor_level", "elevators",
            "vertical_height_m", "parking_spaces", "building_status",
            "floor_material", "amenities",
        }
        assert expected.issubset(set(attrs_df.columns))

    def test_inquiries_columns(self, inquiries_df: pl.DataFrame) -> None:
        expected = {
            "inquiry_id", "lead_id", "spot_id", "inquiry_at", "channel",
            "message_length", "requested_area_sqm", "requested_budget_mxn",
            "urgency_days", "asked_visit", "broker_response",
            "broker_response_hours",
        }
        assert expected.issubset(set(inquiries_df.columns))

    def test_market_columns(self, market_df: pl.DataFrame) -> None:
        expected = {
            "state", "municipality", "corridor", "sector", "month",
            "similar_available_spots", "avg_price_sqm_mxn",
            "recent_occupancy_rate", "absorption_velocity_days",
            "recent_inquiry_volume",
        }
        assert expected.issubset(set(market_df.columns))

    def test_availability_columns(self, avail_df: pl.DataFrame) -> None:
        expected = {
            "snapshot_id", "spot_id", "snapshot_date", "is_available",
            "days_until_available", "competing_inquiries_30d",
        }
        assert expected.issubset(set(avail_df.columns))

    def test_outcomes_columns(self, outcomes_df: pl.DataFrame) -> None:
        expected = {
            "lead_id", "converted_to_visit", "converted_to_closure",
            "conversion_date", "final_spot_id", "spot_available_for_lead",
            "opportunity_label", "lead_quality_true",
        }
        assert expected.issubset(set(outcomes_df.columns))


# ======================================================================
# FK integrity
# ======================================================================


class TestFKIntegrity:
    def test_attrs_spot_ids_in_spots(
        self, attrs_df: pl.DataFrame, spots_df: pl.DataFrame,
    ) -> None:
        spot_ids = set(spots_df["spot_id"].to_list())
        attr_ids = set(attrs_df["spot_id"].to_list())
        assert attr_ids.issubset(spot_ids)

    def test_inquiry_lead_ids_in_leads(
        self, inquiries_df: pl.DataFrame, leads_df: pl.DataFrame,
    ) -> None:
        lead_ids = set(leads_df["lead_id"].to_list())
        inq_leads = set(inquiries_df["lead_id"].to_list())
        assert inq_leads.issubset(lead_ids)

    def test_inquiry_spot_ids_in_spots(
        self, inquiries_df: pl.DataFrame, spots_df: pl.DataFrame,
    ) -> None:
        spot_ids = set(spots_df["spot_id"].to_list())
        inq_spots = set(inquiries_df["spot_id"].to_list())
        assert inq_spots.issubset(spot_ids)

    def test_avail_spot_ids_in_spots(
        self, avail_df: pl.DataFrame, spots_df: pl.DataFrame,
    ) -> None:
        spot_ids = set(spots_df["spot_id"].to_list())
        avail_spots = set(avail_df["spot_id"].to_list())
        assert avail_spots.issubset(spot_ids)

    def test_outcomes_lead_ids_in_leads(
        self, outcomes_df: pl.DataFrame, leads_df: pl.DataFrame,
    ) -> None:
        lead_ids = set(leads_df["lead_id"].to_list())
        outcome_ids = set(outcomes_df["lead_id"].to_list())
        assert outcome_ids.issubset(lead_ids)


# ======================================================================
# Hidden outcomes
# ======================================================================


class TestHiddenOutcomes:
    def test_outcomes_not_in_public_generators(self) -> None:
        """generate_outcomes must NOT be exported from the public generators package."""
        import spot2_assessment_data.generators as gen
        with pytest.raises(AttributeError):
            _ = gen.generate_outcomes

    def test_outcomes_not_in_public_init(self) -> None:
        """generate_outcomes must NOT be in spot2_assessment_data.__init__."""
        import spot2_assessment_data as sad
        with pytest.raises(AttributeError):
            _ = sad.generate_outcomes

    def test_outcomes_can_be_imported_directly(self) -> None:
        """Internal module import works for testing."""
        from spot2_assessment_data.generators._outcomes import generate_outcomes
        assert callable(generate_outcomes)


# ======================================================================
# Base rates
# ======================================================================


class TestBaseRates:
    def test_converted_to_visit_rate(
        self, outcomes_df: pl.DataFrame, config: AssessmentConfig,
    ) -> None:
        rate = outcomes_df["converted_to_visit"].mean()
        target = config.target_rates.converted_to_visit
        assert abs(rate - target.mean) <= target.tolerance, (
            f"Rate {rate:.4f} outside {target.mean}±{target.tolerance}"
        )

    def test_converted_to_closure_rate(
        self, outcomes_df: pl.DataFrame, config: AssessmentConfig,
    ) -> None:
        rate = outcomes_df["converted_to_closure"].mean()
        target = config.target_rates.converted_to_closure
        assert abs(rate - target.mean) <= target.tolerance, (
            f"Rate {rate:.4f} outside {target.mean}±{target.tolerance}"
        )

    def test_spot_available_for_lead_range(
        self, outcomes_df: pl.DataFrame, config: AssessmentConfig,
    ) -> None:
        rate = outcomes_df["spot_available_for_lead"].mean()
        target = config.target_rates.spot_available_for_lead
        assert target.min <= rate <= target.max, (
            f"Rate {rate:.4f} outside [{target.min}, {target.max}]"
        )

    def test_converted_to_closure_is_subset_of_visit(
        self, outcomes_df: pl.DataFrame,
    ) -> None:
        closure = outcomes_df.filter(pl.col("converted_to_closure"))
        visit_count = closure["converted_to_visit"].sum()
        assert visit_count == len(closure), (
            "All converted_to_closure must also have converted_to_visit"
        )


# ======================================================================
# Temporal range
# ======================================================================
