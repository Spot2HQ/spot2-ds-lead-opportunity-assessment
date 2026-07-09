"""CLI to generate the Spot2 DS Lead Opportunity Assessment dataset.

Generates all 7 synthetic tables (6 candidate + 1 hidden outcomes) and
writes each to both CSV and Parquet under the specified output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is importable regardless of CWD (project root or scripts/).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC = str(_PROJECT_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.generators import (
    generate_availability_snapshot,
    generate_inquiries,
    generate_leads,
    generate_market_context,
    generate_spot_attributes,
    generate_spots,
)
from spot2_assessment_data.generators._outcomes import generate_outcomes
from spot2_assessment_data.geo_catalog import GeoCatalog
from spot2_assessment_data.rng import SeedRng

# Columns prefixed with '_' are internal/hidden and must be stripped
# before writing candidate-facing outputs.
_HIDDEN_COL_PREFIX = "_"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_schema_hash(df: pl.DataFrame) -> str:
    """SHA-256 over ordered (col_name, logical_type) tuples."""
    schema_tuples = [(col, str(df.schema[col])) for col in sorted(df.columns)]
    schema_str = json.dumps(schema_tuples, sort_keys=True)
    return hashlib.sha256(schema_str.encode()).hexdigest()


def _strip_hidden(df: pl.DataFrame) -> pl.DataFrame:
    """Drop columns whose name starts with '_'."""
    hidden = [c for c in df.columns if c.startswith(_HIDDEN_COL_PREFIX)]
    return df.drop(hidden) if hidden else df


def _write_table(
    df: pl.DataFrame,
    name: str,
    output_root: Path,
    manifest_tables: dict,
    manifest_paths: dict,
    *,
    candidate: bool = True,
) -> None:
    """Write a table to both CSV and Parquet, updating manifest entries."""
    if candidate:
        csv_dir = output_root / "candidate" / "csv"
        parquet_dir = output_root / "candidate" / "parquet"
        df_write = _strip_hidden(df)
    else:
        csv_dir = output_root / "evaluation" / "csv"
        parquet_dir = output_root / "evaluation" / "parquet"
        df_write = df

    csv_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)

    csv_path = csv_dir / f"{name}.csv"
    parquet_path = parquet_dir / f"{name}.parquet"

    df_write.write_csv(csv_path)

    # Keep Parquet and manifest schemas aligned with the CSV artifact that
    # candidates receive and tests independently read back.
    persisted_df = pl.read_csv(csv_path, infer_schema_length=10000)
    persisted_df.write_parquet(parquet_path)

    manifest_tables[name] = {
        "rows": len(persisted_df),
        "columns": len(persisted_df.columns),
        "schema_hash": _compute_schema_hash(persisted_df),
    }
    manifest_paths[f"{name}_csv"] = str(csv_path.relative_to(output_root))
    manifest_paths[f"{name}_parquet"] = str(parquet_path.relative_to(output_root))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Spot2 DS Lead Opportunity Assessment synthetic data."
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed (overrides config value). Default: 42."
    )
    parser.add_argument(
        "--config", default="config/default.yaml",
        help="Path to config YAML. Default: config/default.yaml."
    )
    parser.add_argument(
        "--output", default="data",
        help="Output root directory. Default: data."
    )
    args = parser.parse_args()

    # 1. Load config
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = _PROJECT_ROOT / config_path
    config = AssessmentConfig.from_yaml(config_path)

    seed = args.seed
    output_root = _PROJECT_ROOT / args.output

    # 2. Init RNG and GeoCatalog with the same seed for determinism
    rng = SeedRng(rng=np.random.default_rng(seed))
    geo_rng = np.random.default_rng(seed)
    geo_catalog = GeoCatalog(rng=geo_rng)

    # 3. Generate all 7 tables in dependency order
    leads_df = generate_leads(rng, config, geo_catalog)
    spots_df = generate_spots(rng, config, geo_catalog)
    attrs_df = generate_spot_attributes(spots_df, rng)
    inquiries_df = generate_inquiries(leads_df, spots_df, rng, config)
    market_df = generate_market_context(spots_df, rng, config)
    avail_df = generate_availability_snapshot(spots_df, inquiries_df, rng, config)

    # Outcomes uses the same RNG — must be last since it depends on all others.
    outcomes_df = generate_outcomes(
        leads_df, inquiries_df, avail_df, market_df, spots_df, rng, config,
    )

    # 4 & 5. Write candidate tables and hidden outcomes
    manifest_tables: dict = {}
    manifest_paths: dict = {}

    candidate_tables = [
        ("leads", leads_df),
        ("spots", spots_df),
        ("spot_attributes", attrs_df),
        ("inquiries", inquiries_df),
        ("market_context", market_df),
        ("availability_snapshot", avail_df),
    ]
    for name, df in candidate_tables:
        _write_table(df, name, output_root, manifest_tables, manifest_paths)

    _write_table(
        outcomes_df, "outcomes", output_root,
        manifest_tables, manifest_paths, candidate=False,
    )

    # 6. Write manifest
    manifest = {
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temporal_range": {
            "start": str(config.temporal_range.start),
            "end": str(config.temporal_range.end),
        },
        "tables": manifest_tables,
        "output_paths": manifest_paths,
    }

    manifest_path = output_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    total_rows = sum(t["rows"] for t in manifest_tables.values())
    print(f"✅ Generated {total_rows:,} rows across {len(manifest_tables)} tables")
    print(f"   Manifest: {manifest_path}")
    print(f"   Candidate CSV:      {output_root / 'candidate' / 'csv'}")
    print(f"   Candidate Parquet:   {output_root / 'candidate' / 'parquet'}")
    print(f"   Evaluation CSV:      {output_root / 'evaluation' / 'csv'}")
    print(f"   Evaluation Parquet:  {output_root / 'evaluation' / 'parquet'}")


if __name__ == "__main__":
    main()
