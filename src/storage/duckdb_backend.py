"""DuckDB storage backend. Local, zero-setup — used by `make demo`."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import duckdb

from storage.adapter import (
    ColumnSchema,
    QueryPlan,
    QueryResult,
    StorageBackend,
    TableSchema,
)

TABLE_DESCRIPTIONS = {
    "workday_employees": "One row per employee (active + former). Source of truth for headcount, attrition, org/region membership.",
    "workday_comp": "Compensation record per employee. Salary in USD after regional multiplier. Bands available for k-anon-safe access.",
    "workday_org": "Org hierarchy dimension. Join employees.org → org_name.",
    "greenhouse_requisitions": "Open and closed hiring reqs. Status, org, region, hiring manager.",
    "greenhouse_candidates": "Candidate identities. External emails are synthetic.",
    "greenhouse_applications": "Candidate × req applications. Stage progression and outcome.",
    "docebo_courses": "Course catalog. `required=true` for compliance training.",
    "docebo_completions": "Per-employee × course completion records. Status: completed | in_progress.",
}


class DuckDBBackend(StorageBackend):
    name = "duckdb"

    def __init__(self, path: str | Path, read_only: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Default read-only: agent never writes, and it allows concurrent readers
        # (e.g., a duckdb REPL open for debugging).
        self.conn = duckdb.connect(str(self.path), read_only=read_only)

    def list_tables(self) -> list[TableSchema]:
        rows = self.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1"
        ).fetchall()
        return [self.get_schema(r[0]) for r in rows]

    def get_schema(self, table: str) -> TableSchema:
        cols = self.conn.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='main' AND table_name=?
            ORDER BY ordinal_position
            """,
            [table],
        ).fetchall()
        row_count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        count = int(row_count[0]) if row_count else 0
        return TableSchema(
            name=table,
            description=TABLE_DESCRIPTIONS.get(table, ""),
            columns=[ColumnSchema(name=c[0], data_type=c[1]) for c in cols],
            row_count=count,
            freshness_ts=datetime.fromtimestamp(self.path.stat().st_mtime)
            if self.path.exists()
            else None,
        )

    def explain(self, sql: str) -> QueryPlan:
        try:
            self.conn.execute(f"EXPLAIN {sql}")
            return QueryPlan(backend=self.name)
        except duckdb.Error as e:
            return QueryPlan(backend=self.name, warnings=[f"explain failed: {e}"])

    def execute(self, sql: str, max_bytes: int | None = None) -> QueryResult:
        t0 = time.perf_counter()
        result = self.conn.execute(sql)
        columns = [d[0] for d in result.description] if result.description else []
        rows = [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
        latency_ms = int((time.perf_counter() - t0) * 1000)
        freshness = datetime.fromtimestamp(self.path.stat().st_mtime) if self.path.exists() else None
        return QueryResult(
            rows=rows,
            row_count=len(rows),
            bytes_processed=None,
            latency_ms=latency_ms,
            sql=sql,
            freshness_ts=freshness,
        )

    def close(self) -> None:
        self.conn.close()
