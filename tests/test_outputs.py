"""Tests for CLI output: CSV/Parquet parity, manifest validity, determinism."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import polars as pl
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _PROJECT_ROOT / "scripts" / "generate_assessment_data.py"

_CANDIDATE_TABLES = [
    "leads", "spots", "spot_attributes", "inquiries",
    "market_context", "availability_snapshot",
]
_EVALUATION_TABLES = ["outcomes"]


def _run_cli(tmp_path: Path, seed: int = 42) -> Path:
    """Run the CLI and return the output directory."""
    result = subprocess.run(
        [
            "uv", "run", "python", str(_SCRIPT),
            "--seed", str(seed),
            "--config", "config/default.yaml",
            "--output", str(tmp_path / "data"),
        ],
        capture_output=True, text=True, cwd=_PROJECT_ROOT,
    )
    assert result.returncode == 0, f"CLI failed:\n{result.stderr}"
    return tmp_path / "data"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_path = tmp_path_factory.mktemp("cli_output")
    return _run_cli(tmp_path, seed=42)


@pytest.fixture(scope="module")
def output_dir_again(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Second run with same seed for determinism tests."""
    tmp_path = tmp_path_factory.mktemp("cli_output2")
    return _run_cli(tmp_path, seed=42)


# ---------------------------------------------------------------------------
# File presence
# ---------------------------------------------------------------------------


class TestFilePresence:
    def test_all_candidate_csv_exist(self, output_dir: Path) -> None:
        for name in _CANDIDATE_TABLES:
            path = output_dir / "candidate" / "csv" / f"{name}.csv"
            assert path.is_file(), f"Missing {path}"

    def test_all_candidate_parquet_exist(self, output_dir: Path) -> None:
        for name in _CANDIDATE_TABLES:
            path = output_dir / "candidate" / "parquet" / f"{name}.parquet"
            assert path.is_file(), f"Missing {path}"

    def test_outcomes_csv_exists(self, output_dir: Path) -> None:
        path = output_dir / "evaluation" / "csv" / "outcomes.csv"
        assert path.is_file(), f"Missing {path}"

    def test_outcomes_parquet_exists(self, output_dir: Path) -> None:
        path = output_dir / "evaluation" / "parquet" / "outcomes.parquet"
        assert path.is_file(), f"Missing {path}"

    def test_manifest_exists(self, output_dir: Path) -> None:
        path = output_dir / "manifest.json"
        assert path.is_file(), f"Missing manifest at {path}"


# ---------------------------------------------------------------------------
# CSV / Parquet parity
# ---------------------------------------------------------------------------


class TestCsvParquetParity:
    @pytest.mark.parametrize("name", _CANDIDATE_TABLES + _EVALUATION_TABLES)
    def test_same_columns(self, output_dir: Path, name: str) -> None:
        category = "evaluation" if name in _EVALUATION_TABLES else "candidate"
        csv_path = output_dir / category / "csv" / f"{name}.csv"
        parquet_path = output_dir / category / "parquet" / f"{name}.parquet"

        csv_df = pl.read_csv(csv_path)
        pq_df = pl.read_parquet(parquet_path)

        assert csv_df.columns == pq_df.columns, (
            f"Column mismatch for {name}:\nCSV: {csv_df.columns}\n"
            f"Parquet: {pq_df.columns}"
        )

    @pytest.mark.parametrize("name", _CANDIDATE_TABLES + _EVALUATION_TABLES)
    def test_same_row_count(self, output_dir: Path, name: str) -> None:
        category = "evaluation" if name in _EVALUATION_TABLES else "candidate"
        csv_df = pl.read_csv(output_dir / category / "csv" / f"{name}.csv")
        pq_df = pl.read_parquet(output_dir / category / "parquet" / f"{name}.parquet")

        assert len(csv_df) == len(pq_df), (
            f"Row count mismatch for {name}: CSV={len(csv_df)} Parquet={len(pq_df)}"
        )

    @pytest.mark.parametrize("name", _CANDIDATE_TABLES + _EVALUATION_TABLES)
    def test_identical_content(self, output_dir: Path, name: str) -> None:
        category = "evaluation" if name in _EVALUATION_TABLES else "candidate"
        csv_df = pl.read_csv(
            output_dir / category / "csv" / f"{name}.csv",
            infer_schema_length=10000,
        )
        pq_df = pl.read_parquet(output_dir / category / "parquet" / f"{name}.parquet")

        # Align dtypes for comparison: Parquet preserves types, CSV infers them.
        for col in csv_df.columns:
            csv_col = csv_df[col]
            pq_col = pq_df[col]

            if csv_col.dtype == pl.Utf8 and pq_col.dtype != pl.Utf8:
                csv_df = csv_df.with_columns(pq_col.cast(pl.Utf8).alias(f"{col}_aligned"))
                csv_df = csv_df.drop(col).rename({f"{col}_aligned": col})
            elif pq_col.dtype == pl.Utf8 and csv_col.dtype != pl.Utf8:
                pq_df = pq_df.with_columns(csv_col.cast(pl.Utf8).alias(f"{col}_aligned"))
                pq_df = pq_df.drop(col).rename({f"{col}_aligned": col})

        # Sort by first column for stable comparison
        sort_col = csv_df.columns[0]
        csv_sorted = csv_df.sort(sort_col)
        pq_sorted = pq_df.sort(sort_col)

        assert csv_sorted.equals(pq_sorted), (
            f"Content mismatch for {name}"
        )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class TestManifest:
    @pytest.fixture(scope="module")
    def manifest(self, output_dir: Path) -> dict:
        return json.loads((output_dir / "manifest.json").read_text())

    def test_manifest_has_seed(self, manifest: dict) -> None:
        assert manifest["seed"] == 42

    def test_manifest_has_temporal_range(self, manifest: dict) -> None:
        tr = manifest["temporal_range"]
        assert "start" in tr
        assert "end" in tr
        assert tr["start"] == "2025-01-01"
        assert tr["end"] == "2026-06-30"

    def test_manifest_has_generated_at(self, manifest: dict) -> None:
        ga = manifest["generated_at"]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ga), (
            f"Invalid timestamp: {ga}"
        )

    def test_manifest_has_all_tables(self, manifest: dict) -> None:
        tables = set(manifest["tables"].keys())
        expected = set(_CANDIDATE_TABLES + _EVALUATION_TABLES)
        assert tables == expected, f"Tables: {tables} != expected {expected}"

    def test_manifest_row_counts_positive(self, manifest: dict) -> None:
        for name, info in manifest["tables"].items():
            assert info["rows"] > 0, f"{name} has 0 rows"

    @pytest.mark.parametrize("name", _CANDIDATE_TABLES + _EVALUATION_TABLES)
    def test_manifest_row_counts_match_files(
        self, output_dir: Path, manifest: dict, name: str,
    ) -> None:
        category = "evaluation" if name in _EVALUATION_TABLES else "candidate"
        df = pl.read_csv(output_dir / category / "csv" / f"{name}.csv")
        assert len(df) == manifest["tables"][name]["rows"], (
            f"Manifest rows {manifest['tables'][name]['rows']} != "
            f"CSV rows {len(df)} for {name}"
        )

    @pytest.mark.parametrize("name", _CANDIDATE_TABLES + _EVALUATION_TABLES)
    def test_schema_hash_is_valid_sha256(
        self, output_dir: Path, manifest: dict, name: str,
    ) -> None:
        """Verify the manifest schema hash is valid and matches recomputation."""
        sha = manifest["tables"][name]["schema_hash"]
        assert len(sha) == 64, f"Invalid SHA-256 length for {name}: {len(sha)}"
        assert re.match(r"^[0-9a-f]{64}$", sha), f"Not hex: {sha}"

        # Recompute from the CSV
        category = "evaluation" if name in _EVALUATION_TABLES else "candidate"
        df = pl.read_csv(
            output_dir / category / "csv" / f"{name}.csv",
            infer_schema_length=10000,
        )
        schema_tuples = [(col, str(df.schema[col])) for col in sorted(df.columns)]
        recomputed = hashlib.sha256(
            json.dumps(schema_tuples, sort_keys=True).encode()
        ).hexdigest()
        assert sha == recomputed, (
            f"Schema hash mismatch for {name}: manifest={sha} recomputed={recomputed}"
        )

    def test_manifest_has_output_paths(self, manifest: dict) -> None:
        paths = manifest["output_paths"]
        for name in _CANDIDATE_TABLES + _EVALUATION_TABLES:
            assert f"{name}_csv" in paths, f"Missing {name}_csv in output_paths"
            assert f"{name}_parquet" in paths, f"Missing {name}_parquet in output_paths"

    def test_manifest_output_paths_exist(
        self, output_dir: Path, manifest: dict,
    ) -> None:
        for rel in manifest["output_paths"].values():
            full = output_dir / rel
            assert full.is_file(), f"Output path {full} does not exist"


# ---------------------------------------------------------------------------
# Hidden outcomes protection
# ---------------------------------------------------------------------------


class TestHiddenOutcomes:
    def test_outcomes_not_in_candidate_csv(self, output_dir: Path) -> None:
        path = output_dir / "candidate" / "csv" / "outcomes.csv"
        assert not path.exists(), "outcomes.csv must NOT be in candidate/csv/"

    def test_outcomes_not_in_candidate_parquet(self, output_dir: Path) -> None:
        path = output_dir / "candidate" / "parquet" / "outcomes.parquet"
        assert not path.exists(), "outcomes.parquet must NOT be in candidate/parquet/"

    def test_hidden_columns_not_in_candidate_csv(self, output_dir: Path) -> None:
        for name in _CANDIDATE_TABLES:
            df = pl.read_csv(output_dir / "candidate" / "csv" / f"{name}.csv")
            hidden = [c for c in df.columns if c.startswith("_")]
            assert not hidden, (
                f"{name}.csv has hidden columns: {hidden}"
            )

    def test_hidden_columns_not_in_candidate_parquet(self, output_dir: Path) -> None:
        for name in _CANDIDATE_TABLES:
            df = pl.read_parquet(
                output_dir / "candidate" / "parquet" / f"{name}.parquet"
            )
            hidden = [c for c in df.columns if c.startswith("_")]
            assert not hidden, (
                f"{name}.parquet has hidden columns: {hidden}"
            )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_produces_same_manifest(
        self, output_dir: Path, output_dir_again: Path,
    ) -> None:
        m1 = json.loads((output_dir / "manifest.json").read_text())
        m2 = json.loads((output_dir_again / "manifest.json").read_text())

        # Timestamp will differ, so compare only tables and output_paths.
        assert m1["seed"] == m2["seed"]
        assert m1["tables"] == m2["tables"], (
            "Table metadata differs between runs with same seed"
        )
        assert m1["output_paths"] == m2["output_paths"]

    def test_same_seed_produces_same_file_hashes(
        self, output_dir: Path, output_dir_again: Path,
    ) -> None:
        """Verify file content hashes match across runs."""
        files1 = sorted(output_dir.rglob("*"))
        files2 = sorted(output_dir_again.rglob("*"))

        rel1 = {p.relative_to(output_dir): p for p in files1 if p.is_file()}
        rel2 = {p.relative_to(output_dir_again): p for p in files2 if p.is_file()}

        for rel in sorted(set(rel1) & set(rel2)):
            if rel.name == "manifest.json":
                continue  # timestamp differs
            h1 = hashlib.sha256(rel1[rel].read_bytes()).hexdigest()
            h2 = hashlib.sha256(rel2[rel].read_bytes()).hexdigest()
            assert h1 == h2, f"Content hash mismatch for {rel}"
