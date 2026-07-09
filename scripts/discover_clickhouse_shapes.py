#!/usr/bin/env python3
"""Discover ClickHouse table/column shapes in datalake and platform databases."""
from __future__ import annotations

import argparse, json, os, re, subprocess, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

SSM_PARAM = "/jean/CLICKHOUSE_URL"
AWS_PROFILE = "DataScientist-114302912952"
PII_PATTERNS = [
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    r"\+?[\d]{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,5}",
    r"(?:Calle|Avenida|Av\.|Blvd|Callejón|Pasaje|Privada|Circuito|Cerrada)\s[\w\d\s,.#\-]+",
    r"\b\d{5}\b",
]
_PII_CHECK_COMPILED = [re.compile(p, re.IGNORECASE) for p in PII_PATTERNS]


@dataclass
class ClickHouseConnection:
    host: str
    port: int
    username: str
    password: str
    database: str
    secure: bool


@dataclass
class TableInfo:
    name: str
    engine: str
    row_count: int | None


@dataclass
class ColumnInfo:
    database: str
    table: str
    name: str
    type_: str


def fetch_clickhouse_url() -> str:
    result = subprocess.run(
        ["aws", "ssm", "get-parameter", "--name", SSM_PARAM, "--with-decryption",
         "--profile", AWS_PROFILE, "--query", "Parameter.Value", "--output", "text"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AWS SSM call failed (exit {result.returncode}): {result.stderr.strip()}")
    url = result.stdout.strip()
    if not url:
        raise RuntimeError("AWS SSM returned empty URL")
    return url


def parse_clickhouse_url(url: str) -> ClickHouseConnection:
    parsed = urlparse(url)
    secure = parsed.scheme in {"clickhouses", "clickhouse+https"}
    return ClickHouseConnection(
        host=parsed.hostname or "localhost",
        port=parsed.port or (8443 if secure else 8123),
        username=parsed.username or "default",
        password=parsed.password or "",
        database=parsed.path.lstrip("/") or "default",
        secure=secure,
    )


def validate_no_pii(data: Any) -> list[str]:
    serialized = json.dumps(data, default=str)
    return [f"Pattern '{p.pattern}' matched {len(m)} times"
            for p, m in ((p, p.findall(serialized)) for p in _PII_CHECK_COMPILED) if m]


def connect_clickhouse(kwargs: ClickHouseConnection):
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=kwargs.host, port=kwargs.port,
        username=kwargs.username, password=kwargs.password,
        database=kwargs.database, secure=kwargs.secure,
        autogenerate_session_id=False,
    )


def discover_tables(client, database: str) -> list[TableInfo]:
    rows = client.query(
        "SELECT name, engine, total_rows FROM system.tables "
        "WHERE database = {db:String} ORDER BY name",
        parameters={"db": database},
    )
    return [TableInfo(name=r[0], engine=r[1], row_count=r[2]) for r in rows.result_rows]


def discover_relevant_columns(client) -> list[ColumnInfo]:
    result = client.query(
        "SELECT database, table, name, type FROM system.columns "
        "WHERE database IN ('datalake', 'platform') "
        "AND (table LIKE '%spot%' OR table LIKE '%lead%' OR table LIKE '%inquiry%' "
        "OR table LIKE '%visit%' OR table LIKE '%convers%') "
        "ORDER BY database, table, name"
    )
    return [ColumnInfo(database=r[0], table=r[1], name=r[2], type_=r[3]) for r in result.result_rows]


def discover_geo_reference(client, table_name: str, database: str = "datalake") -> dict[str, Any]:
    cols_needed = ["state", "municipality", "settlement", "region", "corridor"]
    cols_result = client.query(
        "SELECT name FROM system.columns WHERE database = {db:String} AND table = {tbl:String} "
        "AND name IN (SELECT arrayJoin({cols:Array(String)}) as name)",
        parameters={"db": database, "tbl": table_name, "cols": cols_needed},
    )
    available = [r[0] for r in cols_result.result_rows]
    if not available:
        return {"source": "clickhouse", "error": "no_geo_columns_found", "total_tuples": 0}
    centroid = client.query(
        "SELECT name FROM system.columns WHERE database = {db:String} AND table = {tbl:String} "
        "AND (name LIKE '%lat%' OR name LIKE '%lon%' OR name LIKE '%long%')",
        parameters={"db": database, "tbl": table_name},
    )
    all_cols = available + [r[0] for r in centroid.result_rows]
    sample = client.query(f"SELECT DISTINCT {', '.join(all_cols)} FROM {database}.{table_name} LIMIT 500")
    return {
        "source": "clickhouse", "total_tuples": len(sample.result_rows),
        "columns_found": all_cols,
        "sample_tuples": [dict(zip(all_cols, r)) for r in sample.result_rows],
    }


def load_seed_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    locations = data.get("locations", [])
    return {
        "databases_inspected": ["datalake", "platform"],
        "fallback_used": True,
        "fallback_source": str(path),
        "discovered_tables": {"datalake": [], "platform": []},
        "relevant_columns": [],
        "geo_reference_summary": {
            "source": "seed_config",
            "total_tuples": len(locations),
            "states": sorted({loc["state"] for loc in locations}),
            "sample_tuples": locations,
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Discover ClickHouse shapes")
    p.add_argument("--output", required=True, type=Path, help="Output JSON path")
    p.add_argument("--schema-only", action="store_true", help="Allow aggregate DISTINCT queries")
    p.add_argument("--dry-run", action="store_true", help="Validate config only")
    args = p.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        try:
            kwargs = parse_clickhouse_url(fetch_clickhouse_url())
            if not kwargs.host:
                raise RuntimeError("Parsed ClickHouse URL has no host")
            args.output.write_text(json.dumps({"dry_run": True, "url_valid": True}, indent=2))
            print(f"[dry-run] ClickHouse URL valid: host={kwargs.host}, port={kwargs.port}")
        except Exception as exc:
            args.output.write_text(json.dumps({"dry_run": True, "url_valid": False, "error": str(exc)}, indent=2))
            print(f"[dry-run] FAILED: {exc}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    evidence: dict[str, Any] = {}

    try:
        print("[*] Fetching ClickHouse URL from SSM...")
        kwargs = parse_clickhouse_url(fetch_clickhouse_url())
        print(f"[*] Connecting to ClickHouse at {kwargs.host}:{kwargs.port}...")
        client = connect_clickhouse(kwargs)
        print("[*] Connected. Discovering tables...")

        datalake_tables = discover_tables(client, "datalake")
        platform_tables = discover_tables(client, "platform")
        relevant_columns = discover_relevant_columns(client)

        geo_ref: dict[str, Any] = {"source": "clickhouse", "total_tuples": 0, "note": "schema_only_flag_not_set"}
        if args.schema_only:
            geo_table = next(
                (t.name for t in datalake_tables
                 if any(kw in t.name.lower() for kw in ["location", "geo", "region", "colonia", "settlement", "state"])),
                None,
            )
            if geo_table:
                print(f"[*] Discovering geo reference from datalake.{geo_table}...")
                geo_ref = discover_geo_reference(client, geo_table)
            else:
                geo_ref = {"source": "clickhouse", "total_tuples": 0, "error": "no_geo_table_found"}

        evidence = {
            "databases_inspected": ["datalake", "platform"],
            "fallback_used": False,
            "discovered_tables": {
                "datalake": [{"name": t.name, "engine": t.engine, "row_count": t.row_count} for t in datalake_tables],
                "platform": [{"name": t.name, "engine": t.engine, "row_count": t.row_count} for t in platform_tables],
            },
            "relevant_columns": [
                {"database": c.database, "table": c.table, "name": c.name, "type": c.type_}
                for c in relevant_columns
            ],
            "geo_reference_summary": geo_ref,
        }
        client.close()
        print(f"[*] Discovery complete: {len(datalake_tables)} datalake tables, "
              f"{len(platform_tables)} platform tables, {len(relevant_columns)} relevant columns")

    except Exception as exc:
        print(f"[!] ClickHouse connection failed: {exc}", file=sys.stderr)
        print("[*] Falling back to config/geo_reference_seed.yaml...")
        seed_path = Path(__file__).parent.parent / "config" / "geo_reference_seed.yaml"
        if not seed_path.exists():
            print(f"[!] Seed file not found at {seed_path}", file=sys.stderr)
            sys.exit(1)
        try:
            evidence = load_seed_yaml(seed_path)
            print(f"[*] Fallback evidence loaded: {evidence['geo_reference_summary']['total_tuples']} geo tuples")
        except Exception as fallback_exc:
            print(f"[!] Fallback also failed: {fallback_exc}", file=sys.stderr)
            sys.exit(1)

    violations = validate_no_pii(evidence)
    if violations:
        print("[!] PII DETECTED in output:", file=sys.stderr)
        for v in violations:
            print(f"    - {v}", file=sys.stderr)
        sys.exit(1)

    args.output.write_text(json.dumps(evidence, indent=2, default=str))
    print(f"[✓] Evidence written to {args.output}")


if __name__ == "__main__":
    main()
