"""Spot2 assessment data — synthetic data generation primitives.

Barrel module: re-exports only, no logic.
"""

from spot2_assessment_data.config import AssessmentConfig, GeoJitter, OutputRoots, RowCounts, TargetRates, TemporalRange
from spot2_assessment_data.constants import (
    BuildingStatus,
    LeadSource,
    MexicanState,
    Modality,
    PropertyClass,
    Region,
    Sector,
    SpotType,
    UserType,
)
from spot2_assessment_data.distributions import (
    MissingnessSpec,
    absorption_velocity,
    apply_missingness,
    area_sqm,
    days_on_market,
    occupancy_rate,
    price_per_sqm,
)
from spot2_assessment_data.generators import (
    generate_availability_snapshot,
    generate_inquiries,
    generate_leads,
    generate_market_context,
    generate_spot_attributes,
    generate_spots,
)
from spot2_assessment_data.geo_catalog import GeoCatalog, LocationAnchor
from spot2_assessment_data.rng import SeedRng

__all__ = [
    "AssessmentConfig",
    "BuildingStatus",
    "GeoCatalog",
    "GeoJitter",
    "LeadSource",
    "LocationAnchor",
    "MexicanState",
    "MissingnessSpec",
    "Modality",
    "OutputRoots",
    "PropertyClass",
    "Region",
    "RowCounts",
    "Sector",
    "SeedRng",
    "SpotType",
    "TargetRates",
    "TemporalRange",
    "UserType",
    "absorption_velocity",
    "apply_missingness",
    "area_sqm",
    "days_on_market",
    "generate_availability_snapshot",
    "generate_inquiries",
    "generate_leads",
    "generate_market_context",
    "generate_spot_attributes",
    "generate_spots",
    "occupancy_rate",
    "price_per_sqm",
]
