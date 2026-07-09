"""Typed domain constants for Spot2 synthetic data generation.

All domain concepts are represented as StrEnum so the type checker
enforces correct values and catches typos at compile time.
"""

from enum import StrEnum


class Sector(StrEnum):
    """Real estate sector classification."""

    INDUSTRIAL = "industrial"
    OFFICE = "office"
    RETAIL = "retail"
    LAND = "land"


class UserType(StrEnum):
    """Spot2 platform user types."""

    BROKER = "broker"
    TENANT_DIRECT = "tenant_direct"
    INVESTOR = "investor"
    DEVELOPER = "developer"


class Modality(StrEnum):
    """Transaction modality for spots/spaces."""

    RENT = "rent"
    SALE = "sale"
    BOTH = "both"


class LeadSource(StrEnum):
    """Lead acquisition channels."""

    ORGANIC = "organic"
    REFERRAL = "referral"
    PAID = "paid"
    SOCIAL = "social"
    EMAIL = "email"
    EVENT = "event"


class SpotType(StrEnum):
    """Spot listing type."""

    SINGLE = "single"
    SUBSPACE = "subspace"


class PropertyClass(StrEnum):
    """Property quality classification."""

    A = "A"
    B = "B"
    C = "C"


class BuildingStatus(StrEnum):
    """Physical condition of a building."""

    NEW = "new"
    GOOD = "good"
    FAIR = "fair"
    NEEDS_RENOVATION = "needs_renovation"


class MexicanState(StrEnum):
    """Minimum set of Mexican states for geo catalog."""

    CDMX = "CDMX"
    MEXICO = "Estado de México"
    NUEVO_LEON = "Nuevo León"
    JALISCO = "Jalisco"
    QUERETARO = "Querétaro"


class Region(StrEnum):
    """Macro regions of Mexico used in geo catalog."""

    NORTE = "norte"
    CENTRO = "centro"
    OCCIDENTE = "occidente"
    SUR = "sur"
