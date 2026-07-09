"""Package the candidate-facing data bundle as a zip archive.

Rules (fail-closed):
- INCLUDE: README-candidate.md, assessment.md, all candidate CSV/Parquet tables,
  optional feature_dictionary.csv/.md, optional sample_submission.csv
- EXCLUDE: outcome*, *outcome*, evaluation, internal, synthetic-data-guide,
  reviewer-rubric, scripts, src, tests, config, .omo, .git, CLICKHOUSE,
  secret, password, any credential-like path component
- Fail if a required candidate file (from manifest output_paths) is missing
- Fail if any denied name pattern appears in the archive member list
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


# ── Denial patterns ──────────────────────────────────────────────────────────
# Each entry is a (pattern, description) tuple.
# - If pattern has no path separator, it matches any path *component* (basename or dirname).
# - If pattern contains a path separator, it matches the full relative path.
# Entries that are plain directory names get an implicit "dir as component" match.
_DENIED_PREFIXES: tuple[str, ...] = (
    "outcome",
    "evaluation",
    "internal",
    "synthetic-data-guide",
    "reviewer-rubric",
    "scripts",
    "src",
    "tests",
    "config",
    ".omo",
    ".git",
    "CLICKHOUSE",
    "secret",
    "password",
)

# Additional whole-word credential-like names
_CREDENTIAL_WORDS: tuple[str, ...] = (
    "secret",
    "password",
    "credential",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
)


def _is_path_component_denied(component: str) -> bool:
    """Check if a single path component matches any denied prefix."""
    lower = component.lower()
    for prefix in _DENIED_PREFIXES:
        if lower.startswith(prefix) or lower.endswith(prefix):
            return True
    return False


def _is_credential_name(name: str) -> bool:
    """Check if a name contains a credential-like word."""
    lower = name.lower()
    for word in _CREDENTIAL_WORDS:
        if word in lower:
            return True
    return False


def _is_path_denied(rel_path: str) -> str | None:
    """Return a reason string if *rel_path* is denied, else None."""
    parts = Path(rel_path).parts

    for part in parts:
        if _is_path_component_denied(part):
            return f"path component '{part}' matches a denied prefix/pattern"

    name = Path(rel_path).name
    if name.startswith("outcome") or "outcome" in name.lower():
        return f"filename '{name}' matches outcome exclusion"

    if _is_credential_name(rel_path):
        return f"path '{rel_path}' matches credential-like name exclusion"

    return None


# ── Candidate table discovery ────────────────────────────────────────────────


def _candidate_tables_from_manifest(manifest_path: Path) -> list[str]:
    """Extract the base table names that belong to the candidate bundle.

    Tables whose output paths start with ``candidate/`` qualify.
    """
    manifest = json.loads(manifest_path.read_text())
    paths: dict[str, str] = manifest.get("output_paths", {})
    tables: list[str] = []
    for key, rel in paths.items():
        if rel.startswith("candidate/"):
            # key formats:  "leads_csv", "spots_parquet", etc.
            table = key.rsplit("_", 1)[0]
            if table not in tables:
                tables.append(table)
    return tables


# ── Bundle collection ────────────────────────────────────────────────────────


def collect_bundle_files(
    project_root: Path,
    data_dir: Path,
) -> list[tuple[Path, str]]:
    """Gather every file that belongs in the candidate bundle.

    Returns a list of ``(absolute_source_path, archive_relative_path)`` tuples.
    """
    files: list[tuple[Path, str]] = []
    errors: list[str] = []

    # 1. Required doc files (at project root)
    for doc in ("README-candidate.md", "assessment.md"):
        doc_path = project_root / doc
        if not doc_path.is_file():
            errors.append(f"required doc file missing: {doc}")
        else:
            files.append((doc_path, doc))

    # 2. Optional doc/data files (at project root)
    for optional in ("feature_dictionary.csv", "feature_dictionary.md", "sample_submission.csv"):
        opt_path = project_root / optional
        if opt_path.is_file():
            files.append((opt_path, optional))

    # 3. Candidate CSV tables
    csv_dir = data_dir / "candidate" / "csv"
    if csv_dir.is_dir():
        for f in sorted(csv_dir.iterdir()):
            if f.is_file() and f.suffix == ".csv":
                files.append((f, f"data/candidate/csv/{f.name}"))

    # 4. Candidate Parquet tables
    parquet_dir = data_dir / "candidate" / "parquet"
    if parquet_dir.is_dir():
        for f in sorted(parquet_dir.iterdir()):
            if f.is_file() and f.suffix == ".parquet":
                files.append((f, f"data/candidate/parquet/{f.name}"))

    # 5. Fail if any required candidate table is missing
    manifest_path = data_dir / "manifest.json"
    if manifest_path.is_file():
        expected_tables = _candidate_tables_from_manifest(manifest_path)
        for table in expected_tables:
            csv_path = csv_dir / f"{table}.csv"
            pq_path = parquet_dir / f"{table}.parquet"
            if not csv_path.is_file():
                errors.append(f"required candidate CSV missing: {csv_path.relative_to(project_root)}")
            if not pq_path.is_file():
                errors.append(f"required candidate Parquet missing: {pq_path.relative_to(project_root)}")
    else:
        # Without manifest, the tables directory serves as ground truth — just
        # note it so callers know we couldn't cross-check.
        pass

    if errors:
        sys.stderr.write("FAIL-CLOSED: required files missing:\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        sys.exit(1)

    return files


# ── Safety scan ──────────────────────────────────────────────────────────────


def scan_for_denied(files: list[tuple[Path, str]]) -> None:
    """Fail-closed if any archive member path is denied."""
    denied: list[str] = []
    for _, arcname in files:
        reason = _is_path_denied(arcname)
        if reason:
            denied.append(f"  {arcname}: {reason}")

    if denied:
        sys.stderr.write("FAIL-CLOSED: denied paths would be included in archive:\n")
        sys.stderr.write("\n".join(denied))
        sys.stderr.write("\n")
        sys.exit(1)


# ── Zip creation ─────────────────────────────────────────────────────────────


def create_bundle(files: list[tuple[Path, str]], output_path: Path) -> None:
    """Write the zip archive."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in files:
            zf.write(src, arcname)


# ── Verification ─────────────────────────────────────────────────────────────


def verify_bundle(output_path: Path, expected_count: int) -> None:
    """Post-creation sanity check: re-read the archive and verify member count
    and that no denied names snuck through."""
    with zipfile.ZipFile(output_path, "r") as zf:
        names = zf.namelist()

    if len(names) != expected_count:
        sys.stderr.write(
            f"FAIL-CLOSED: archive member count mismatch: "
            f"expected {expected_count}, got {len(names)}\n"
        )
        sys.stderr.write("Archive contents:\n")
        for n in names:
            sys.stderr.write(f"  {n}\n")
        sys.exit(1)

    for name in names:
        reason = _is_path_denied(name)
        if reason:
            sys.stderr.write(
                f"FAIL-CLOSED: denied path in final archive: {name}: {reason}\n"
            )
            sys.exit(1)

    print(f"✓ Bundle verified: {len(names)} files, no denied paths")
    for n in names:
        print(f"  {n}")


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package candidate-facing data bundle as a zip archive."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="Path to the data/ directory (e.g. data)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output zip path (e.g. dist/bundle.zip)",
    )
    args = parser.parse_args()

    project_root = args.data_dir.resolve().parent
    data_dir = args.data_dir.resolve()

    if not data_dir.is_dir():
        sys.stderr.write(f"FAIL-CLOSED: data directory not found: {data_dir}\n")
        sys.exit(1)

    # --- Collect ---
    files = collect_bundle_files(project_root, data_dir)

    # --- Safety scan ---
    scan_for_denied(files)

    # --- Create ---
    create_bundle(files, args.output.resolve())

    # --- Verify ---
    verify_bundle(args.output.resolve(), len(files))


if __name__ == "__main__":
    main()
