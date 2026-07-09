"""Shared fixtures for generator tests."""
from __future__ import annotations

import pytest
import polars as pl

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
