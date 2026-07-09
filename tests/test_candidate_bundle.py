"""Tests for candidate bundle packaging."""
import subprocess
import zipfile
from pathlib import Path
import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
PROJECT_DIR = Path(__file__).resolve().parent.parent


def _run_package(data_dir: str, output: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(SCRIPTS_DIR / "package_candidate_bundle.py"),
         "--data-dir", data_dir, "--output", output],
        cwd=str(PROJECT_DIR), capture_output=True, text=True, timeout=60,
    )


class TestCandidateBundle:
    """Verify the candidate bundle contains only approved files."""

    def test_bundle_contains_all_candidate_tables(self, tmp_path):
        output = str(tmp_path / "test.zip")
        result = _run_package("data", output)
        assert result.returncode == 0, f"Package failed: {result.stderr}"
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
        # Must have docs
        assert any("README-candidate.md" in n for n in names), "Missing README-candidate.md"
        assert any("assessment.md" in n for n in names), "Missing assessment.md"
        # Must have 6 CSV and 6 Parquet candidate tables
        csvs = [n for n in names if n.endswith(".csv")]
        pqs = [n for n in names if n.endswith(".parquet")]
        assert len(csvs) >= 6, f"Expected >=6 CSVs, got {len(csvs)}: {csvs}"
        assert len(pqs) >= 6, f"Expected >=6 Parquets, got {len(pqs)}: {pqs}"

    def test_bundle_excludes_evaluation_files(self, tmp_path):
        output = str(tmp_path / "test.zip")
        result = _run_package("data", output)
        assert result.returncode == 0, f"Package failed: {result.stderr}"
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
        bad = [n for n in names if "evaluation" in n.lower() or "outcome" in n.lower()]
        assert not bad, f"Denied files in bundle: {bad}"

    def test_bundle_excludes_internal_files(self, tmp_path):
        output = str(tmp_path / "test.zip")
        result = _run_package("data", output)
        assert result.returncode == 0
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
        bad = [n for n in names if "internal" in n]
        assert not bad, f"Internal files leaked: {bad}"

    def test_bundle_excludes_config_scripts(self, tmp_path):
        output = str(tmp_path / "test.zip")
        result = _run_package("data", output)
        assert result.returncode == 0
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
        bad = [n for n in names if any(p in n for p in [
            "synthetic-data-guide", "reviewer-rubric", "config/",
            "scripts/", "src/", "tests/", ".omo", ".git",
        ])]
        assert not bad, f"Evaluator files leaked: {bad}"

    def test_fails_when_missing_candidate_data(self, tmp_path):
        """Package should fail if required data is missing."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "candidate").mkdir()
        (empty_dir / "candidate" / "csv").mkdir()
        (empty_dir / "candidate" / "parquet").mkdir()
        output = str(tmp_path / "should_not_exist.zip")
        result = _run_package(str(empty_dir), output)
        assert result.returncode != 0, "Should fail with missing data"
