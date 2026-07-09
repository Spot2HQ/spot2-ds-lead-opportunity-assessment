"""Configuration loading and validation for assessment data generation.

Parses config/default.yaml and validates all required keys using Pydantic v2.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field

_CONFIG_DIR: Final[Path] = Path("config")
_DEFAULT_CONFIG_PATH: Final[Path] = _CONFIG_DIR / "default.yaml"


class TemporalRange(BaseModel):
    """Date range for synthetic data coverage."""

    model_config = ConfigDict(frozen=True)

    start: date
    end: date


class RowCounts(BaseModel):
    """Target row counts for each synthetic table."""

    model_config = ConfigDict(frozen=True)

    leads: int
    spots: int
    spot_attributes: int
    inquiries: int
    market_context: int
    availability_snapshot: int
    outcomes: int


class TargetRate(BaseModel):
    """A target rate with required fields."""

    model_config = ConfigDict(frozen=True)

    mean: float
    tolerance: float


class TargetRateMinMax(BaseModel):
    """A target rate with min/max bounds instead of mean/tolerance."""

    model_config = ConfigDict(frozen=True)

    min: float
    max: float


class TargetRates(BaseModel):
    """Outcome target rates for synthetic data validation."""

    model_config = ConfigDict(frozen=True)

    converted_to_visit: TargetRate
    converted_to_closure: TargetRate
    spot_available_for_lead: TargetRateMinMax


class GeoJitter(BaseModel):
    """Geometry jitter configuration."""

    model_config = ConfigDict(frozen=True)

    max_km: float
    rule: str


class OutputRoots(BaseModel):
    """Output directory configuration."""

    model_config = ConfigDict(frozen=True)

    candidate_csv: str
    candidate_parquet: str
    evaluation_csv: str
    evaluation_parquet: str
    internal: str


class AssessmentConfig(BaseModel):
    """Full assessment data generation configuration.

    All fields are frozen after construction — the config is immutable
    once loaded.
    """

    model_config = ConfigDict(frozen=True)

    seed: int
    temporal_range: TemporalRange
    row_counts: RowCounts
    target_rates: TargetRates
    geo_jitter: GeoJitter
    output_roots: OutputRoots

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> AssessmentConfig:
        """Load and validate config from a YAML file.

        Args:
            path: Path to the YAML config file. Defaults to config/default.yaml.

        Returns:
            A validated, frozen AssessmentConfig instance.

        Raises:
            FileNotFoundError: If the config file does not exist.
            pydantic.ValidationError: If any required key is missing or has wrong type.
        """
        resolved = Path(path) if path else _DEFAULT_CONFIG_PATH
        if not resolved.is_file():
            raise FileNotFoundError(f"Config file not found: {resolved.resolve()}")
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        return cls(**raw)

    @property
    def start_datetime(self) -> datetime:
        """temporal_range.start as a timezone-naive midnight datetime."""
        return datetime(self.temporal_range.start.year, self.temporal_range.start.month, self.temporal_range.start.day)

    @property
    def end_datetime(self) -> datetime:
        """temporal_range.end as a timezone-naive midnight datetime."""
        return datetime(self.temporal_range.end.year, self.temporal_range.end.month, self.temporal_range.end.day)
