"""Tests for config.py — config loading and validation."""

from datetime import date

import pytest
from pydantic import ValidationError

from spot2_assessment_data.config import AssessmentConfig

# Path relative to project root (tests run from project root via pyproject.toml pythonpath).
_CONFIG_PATH = "config/default.yaml"


class TestValidConfig:
    """Tests for valid config loading."""

    def test_loads_all_required_keys(self) -> None:
        """Given: a valid config/default.yaml.
        When: loading via from_yaml().
        Then: all required fields are populated correctly."""
        cfg = AssessmentConfig.from_yaml(_CONFIG_PATH)

        assert cfg.seed == 42
        assert isinstance(cfg.temporal_range.start, date)
        assert isinstance(cfg.temporal_range.end, date)
        assert cfg.temporal_range.start == date(2025, 1, 1)
        assert cfg.temporal_range.end == date(2026, 6, 30)

        assert cfg.row_counts.leads == 5000
        assert cfg.row_counts.spots == 3000
        assert cfg.row_counts.outcomes == 5000

        assert cfg.target_rates.converted_to_visit.mean == 0.22
        assert cfg.target_rates.converted_to_visit.tolerance == 0.04
        assert cfg.target_rates.converted_to_closure.mean == 0.10
        assert cfg.target_rates.converted_to_closure.tolerance == 0.03
        assert cfg.target_rates.spot_available_for_lead.min == 0.55
        assert cfg.target_rates.spot_available_for_lead.max == 0.75

        assert cfg.geo_jitter.max_km == 2.5
        assert "same" in cfg.geo_jitter.rule.lower()

        assert cfg.output_roots.candidate_csv == "data/candidate/csv"
        assert cfg.output_roots.evaluation_parquet == "data/evaluation/parquet"
        assert cfg.output_roots.internal == "data/internal"

    def test_config_is_frozen(self) -> None:
        """Given: a loaded config.
        When: attempting to mutate.
        Then: raises ValidationError or TypeError."""
        cfg = AssessmentConfig.from_yaml(_CONFIG_PATH)
        with pytest.raises(ValidationError):
            cfg.seed = 99  # type: ignore[misc]

    def test_start_datetime_property(self) -> None:
        """Given: a loaded config.
        When: accessing start_datetime.
        Then: returns midnight datetime."""
        cfg = AssessmentConfig.from_yaml(_CONFIG_PATH)
        dt = cfg.start_datetime
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.minute == 0

    def test_end_datetime_property(self) -> None:
        """Given: a loaded config.
        When: accessing end_datetime.
        Then: returns midnight datetime."""
        cfg = AssessmentConfig.from_yaml(_CONFIG_PATH)
        dt = cfg.end_datetime
        assert dt.year == 2026
        assert dt.month == 6
        assert dt.day == 30


class TestMissingKeyError:
    """Tests for missing required keys."""

    def test_missing_seed_raises(self) -> None:
        """When: seed key is missing. Then: ValidationError."""
        with pytest.raises(ValidationError, match="seed"):
            AssessmentConfig(
                temporal_range={"start": "2025-01-01", "end": "2025-12-31"},
                row_counts={
                    "leads": 100, "spots": 100, "spot_attributes": 100,
                    "inquiries": 100, "market_context": 100,
                    "availability_snapshot": 100, "outcomes": 100,
                },
                target_rates={
                    "converted_to_visit": {"mean": 0.2, "tolerance": 0.05},
                    "converted_to_closure": {"mean": 0.1, "tolerance": 0.03},
                    "spot_available_for_lead": {"min": 0.5, "max": 0.8},
                },
                geo_jitter={"max_km": 2.5, "rule": "must remain"},
                output_roots={
                    "candidate_csv": "a", "candidate_parquet": "b",
                    "evaluation_csv": "c", "evaluation_parquet": "d",
                    "internal": "e",
                },
            )

    def test_missing_temporal_range_raises(self) -> None:
        """When: temporal_range key is missing. Then: ValidationError."""
        with pytest.raises(ValidationError, match="temporal_range"):
            AssessmentConfig(
                seed=42,
                row_counts={
                    "leads": 100, "spots": 100, "spot_attributes": 100,
                    "inquiries": 100, "market_context": 100,
                    "availability_snapshot": 100, "outcomes": 100,
                },
                target_rates={
                    "converted_to_visit": {"mean": 0.2, "tolerance": 0.05},
                    "converted_to_closure": {"mean": 0.1, "tolerance": 0.03},
                    "spot_available_for_lead": {"min": 0.5, "max": 0.8},
                },
                geo_jitter={"max_km": 2.5, "rule": "must remain"},
                output_roots={
                    "candidate_csv": "a", "candidate_parquet": "b",
                    "evaluation_csv": "c", "evaluation_parquet": "d",
                    "internal": "e",
                },
            )

    def test_missing_row_counts_raises(self) -> None:
        """When: row_counts key is missing. Then: ValidationError."""
        with pytest.raises(ValidationError, match="row_counts"):
            AssessmentConfig(
                seed=42,
                temporal_range={"start": "2025-01-01", "end": "2025-12-31"},
                target_rates={
                    "converted_to_visit": {"mean": 0.2, "tolerance": 0.05},
                    "converted_to_closure": {"mean": 0.1, "tolerance": 0.03},
                    "spot_available_for_lead": {"min": 0.5, "max": 0.8},
                },
                geo_jitter={"max_km": 2.5, "rule": "must remain"},
                output_roots={
                    "candidate_csv": "a", "candidate_parquet": "b",
                    "evaluation_csv": "c", "evaluation_parquet": "d",
                    "internal": "e",
                },
            )

    def test_missing_output_roots_raises(self) -> None:
        """When: output_roots key is missing. Then: ValidationError."""
        with pytest.raises(ValidationError, match="output_roots"):
            AssessmentConfig(
                seed=42,
                temporal_range={"start": "2025-01-01", "end": "2025-12-31"},
                row_counts={
                    "leads": 100, "spots": 100, "spot_attributes": 100,
                    "inquiries": 100, "market_context": 100,
                    "availability_snapshot": 100, "outcomes": 100,
                },
                target_rates={
                    "converted_to_visit": {"mean": 0.2, "tolerance": 0.05},
                    "converted_to_closure": {"mean": 0.1, "tolerance": 0.03},
                    "spot_available_for_lead": {"min": 0.5, "max": 0.8},
                },
                geo_jitter={"max_km": 2.5, "rule": "must remain"},
            )


class TestBadTypes:
    """Tests for wrong type validation."""

    def test_seed_must_be_int(self) -> None:
        """When: seed is a string. Then: ValidationError."""
        with pytest.raises(ValidationError):
            AssessmentConfig(
                seed="forty-two",  # type: ignore[arg-type]
                temporal_range={"start": "2025-01-01", "end": "2025-12-31"},
                row_counts={
                    "leads": 100, "spots": 100, "spot_attributes": 100,
                    "inquiries": 100, "market_context": 100,
                    "availability_snapshot": 100, "outcomes": 100,
                },
                target_rates={
                    "converted_to_visit": {"mean": 0.2, "tolerance": 0.05},
                    "converted_to_closure": {"mean": 0.1, "tolerance": 0.03},
                    "spot_available_for_lead": {"min": 0.5, "max": 0.8},
                },
                geo_jitter={"max_km": 2.5, "rule": "must remain"},
                output_roots={
                    "candidate_csv": "a", "candidate_parquet": "b",
                    "evaluation_csv": "c", "evaluation_parquet": "d",
                    "internal": "e",
                },
            )

    def test_geo_jitter_max_km_must_be_float(self) -> None:
        """When: geo_jitter.max_km is a string. Then: ValidationError."""
        with pytest.raises(ValidationError):
            AssessmentConfig(
                seed=42,
                temporal_range={"start": "2025-01-01", "end": "2025-12-31"},
                row_counts={
                    "leads": 100, "spots": 100, "spot_attributes": 100,
                    "inquiries": 100, "market_context": 100,
                    "availability_snapshot": 100, "outcomes": 100,
                },
                target_rates={
                    "converted_to_visit": {"mean": 0.2, "tolerance": 0.05},
                    "converted_to_closure": {"mean": 0.1, "tolerance": 0.03},
                    "spot_available_for_lead": {"min": 0.5, "max": 0.8},
                },
                geo_jitter={"max_km": "two-point-five", "rule": "must remain"},  # type: ignore[dict-item]
                output_roots={
                    "candidate_csv": "a", "candidate_parquet": "b",
                    "evaluation_csv": "c", "evaluation_parquet": "d",
                    "internal": "e",
                },
            )
