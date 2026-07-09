"""Validate generated synthetic dataset acceptance criteria — main runner.

Usage:
    uv run python scripts/validate_generated_data.py --data-dir data --evidence evidence.json
"""

import argparse, json, sys
from pathlib import Path

from validators import run_all_checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated synthetic dataset")
    parser.add_argument("--data-dir", default="data", help="Path to data directory")
    parser.add_argument("--evidence", required=True, help="Path for JSON evidence output")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        print(f"Error: data directory '{data_dir}' not found", file=sys.stderr)
        return 1

    results = run_all_checks(data_dir)

    all_passed = all(v["passed"] for v in results.values())
    output = {"passed": all_passed, "checks": results}

    evidence_path = Path(args.evidence).resolve()
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print("=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    for name, result in results.items():
        status = "\u2713" if result["passed"] else "\u2717"
        print(f"  {status} {name}: {_fmt_detail(result['details'])}")
    print("=" * 60)
    print(f"OVERALL: {'PASSED' if all_passed else 'FAILED'}")

    return 0 if all_passed else 1


def _fmt_detail(detail) -> str:
    if isinstance(detail, dict):
        return ", ".join(f"{k}={v}" for k, v in detail.items())
    return str(detail)


if __name__ == "__main__":
    raise SystemExit(main())
