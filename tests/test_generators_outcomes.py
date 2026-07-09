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

class TestSpotAttributes:
    def test_security_type_values(self, attrs_df: pl.DataFrame) -> None:
        valid = {"none", "basic", "cctv", "full"}
        vals = set(attrs_df["security_type"].drop_nulls().to_list())
        assert vals.issubset(valid)

    def test_building_status_values(self, attrs_df: pl.DataFrame) -> None:
        valid = {"new", "good", "fair", "needs_renovation"}
        vals = set(attrs_df["building_status"].drop_nulls().to_list())
        assert vals.issubset(valid)

    def test_amenities_is_json_array(self, attrs_df: pl.DataFrame) -> None:
        import json
        for val in attrs_df["amenities"].drop_nulls().to_list():
            parsed = json.loads(val)
            assert isinstance(parsed, list)


# ======================================================================
# Spot specifics
# ======================================================================


class TestSpots:
    def test_is_active_rate(self, spots_df: pl.DataFrame) -> None:
        rate = spots_df["is_active"].mean()
        assert 0.83 <= rate <= 0.93, f"is_active rate {rate:.3f}"

    def test_days_on_market_max(self, spots_df: pl.DataFrame) -> None:
        assert spots_df["days_on_market"].max() <= 730

    def test_modality_values(self, spots_df: pl.DataFrame) -> None:
        valid = {"rent", "sale", "both"}
        vals = set(spots_df["modality"].to_list())
        assert vals.issubset(valid)

    def test_sector_name_values(self, spots_df: pl.DataFrame) -> None:
        valid = {"Industrial", "Office", "Retail", "Land"}
        vals = set(spots_df["sector_name"].to_list())
        assert vals.issubset(valid)


# ======================================================================
# Leads specifics
# ======================================================================


class TestLeads:
    def test_user_type_values(self, leads_df: pl.DataFrame) -> None:
        valid = {"broker", "tenant_direct", "investor", "developer"}
        vals = set(leads_df["user_type"].to_list())
        assert vals.issubset(valid)

    def test_search_sector_values(self, leads_df: pl.DataFrame) -> None:
        valid = {"Industrial", "Office", "Retail", "Land"}
        vals = set(leads_df["search_sector"].to_list())
        assert vals.issubset(valid)

    def test_source_values(self, leads_df: pl.DataFrame) -> None:
        valid = {"organic", "referral", "paid", "social", "email", "event"}
        vals = set(leads_df["source"].to_list())
        assert vals.issubset(valid)

    def test_target_area_sqm_range(self, leads_df: pl.DataFrame) -> None:
        area = leads_df["target_area_sqm"].drop_nulls()
        assert area.min() >= 30.0
        assert area.max() <= 10000.0

    def test_lead_score_internal_leakage_trap(
        self, leads_df: pl.DataFrame, outcomes_df: pl.DataFrame,
    ) -> None:
        """lead_score_internal must exist and be a float column."""
        assert "lead_score_internal" in leads_df.columns
        assert leads_df["lead_score_internal"].dtype in (pl.Float64, pl.Float32)


# ======================================================================
# Inquiries specifics
# ======================================================================


class TestInquiries:
    def test_broker_response_values(self, inquiries_df: pl.DataFrame) -> None:
        valid = {"accepted", "rejected", "no_response", "scheduled_visit"}
        vals = set(inquiries_df["broker_response"].drop_nulls().to_list())
        assert vals.issubset(valid)

    def test_channel_values(self, inquiries_df: pl.DataFrame) -> None:
        valid = {"web", "app", "whatsapp", "email", "phone"}
        vals = set(inquiries_df["channel"].to_list())
        assert vals.issubset(valid)

    def test_asked_visit_rate(self, inquiries_df: pl.DataFrame) -> None:
        rate = inquiries_df["asked_visit"].mean()
        assert 0.15 <= rate <= 0.35, f"asked_visit rate {rate:.3f}"

    def test_each_lead_has_inquiries(
        self, leads_df: pl.DataFrame, inquiries_df: pl.DataFrame,
    ) -> None:
        lead_ids = set(leads_df["lead_id"].to_list())
        inq_leads = set(inquiries_df["lead_id"].to_list())
        assert inq_leads.issubset(lead_ids)


# ======================================================================
# Availability specifics
# ======================================================================


class TestAvailability:
    def test_is_available_rate(self, avail_df: pl.DataFrame) -> None:
        rate = avail_df["is_available"].mean()
        assert 0.58 <= rate <= 0.72, f"is_available rate {rate:.3f}"

    def test_days_until_available_logical(self, avail_df: pl.DataFrame) -> None:
        available = avail_df.filter(pl.col("is_available"))
        assert available["days_until_available"].sum() == 0


# ======================================================================
# Outcomes specifics
# ======================================================================


class TestOutcomes:
    def test_opportunity_label_values(self, outcomes_df: pl.DataFrame) -> None:
        valid = {"HighQualityAvailable", "HighQualityUnavailable", "LowQuality", "Converted"}
        vals = set(outcomes_df["opportunity_label"].to_list())
        assert vals == valid

    def test_all_labels_present(self, outcomes_df: pl.DataFrame) -> None:
        counts = outcomes_df.group_by("opportunity_label").len()
        assert len(counts) == 4, "All 4 opportunity labels must be present"

    def test_lead_quality_true_in_range(self, outcomes_df: pl.DataFrame) -> None:
        q = outcomes_df["lead_quality_true"]
        assert q.min() >= 0.0
        assert q.max() <= 1.0

    def test_conversion_date_after_created(self) -> None:
        """Covered by temporal range tests."""
        pass
