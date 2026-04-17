"""Load synthetic parquet files into the DuckDB warehouse."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv()

PARQUET_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"
DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "warehouse" / "pia.duckdb"

TABLES = [
    "workday_employees",
    "workday_comp",
    "workday_org",
    "greenhouse_requisitions",
    "greenhouse_candidates",
    "greenhouse_applications",
    "docebo_courses",
    "docebo_completions",
]


def main() -> None:
    db_path = Path(os.getenv("PIA_DUCKDB_PATH", str(DEFAULT_DB)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    for table in TABLES:
        parquet_path = PARQUET_DIR / f"{table}.parquet"
        if not parquet_path.exists():
            raise FileNotFoundError(
                f"{parquet_path} missing — run `uv run python -m data.synthetic.generate` first"
            )
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{parquet_path}')")
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        row_count = int(count[0]) if count else 0
        print(f"  loaded {table:<35} {row_count:>8,} rows")
    conn.close()
    print(f"\nWarehouse ready at: {db_path}")


if __name__ == "__main__":
    main()
