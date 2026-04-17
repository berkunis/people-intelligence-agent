"""BigQuery storage backend. The cloud path.

Key differences from DuckDB:
  - Dry-run (`QueryJobConfig(dry_run=True)`) gives real `total_bytes_processed` before execution
  - `max_bytes` is enforced via `maximum_bytes_billed` — hard stop, no surprise bills
  - Freshness comes from table metadata, not file mtime
"""

from __future__ import annotations

import os
import time
from datetime import datetime

from google.cloud import bigquery

from storage.adapter import (
    ColumnSchema,
    QueryPlan,
    QueryResult,
    StorageBackend,
    TableSchema,
)
from storage.duckdb_backend import TABLE_DESCRIPTIONS


class BigQueryBackend(StorageBackend):
    name = "bigquery"

    def __init__(self, project: str | None = None, dataset: str | None = None):
        self.project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.dataset = dataset or os.getenv("PIA_BQ_DATASET", "pia")
        self.client = bigquery.Client(project=self.project)

    def _dataset_ref(self) -> str:
        return f"{self.project}.{self.dataset}"

    def list_tables(self) -> list[TableSchema]:
        tables = self.client.list_tables(self._dataset_ref())
        return [self.get_schema(t.table_id) for t in tables]

    def get_schema(self, table: str) -> TableSchema:
        tbl = self.client.get_table(f"{self._dataset_ref()}.{table}")
        cols = [
            ColumnSchema(name=f.name, data_type=f.field_type, description=f.description or "")
            for f in tbl.schema
        ]
        return TableSchema(
            name=table,
            description=TABLE_DESCRIPTIONS.get(table, tbl.description or ""),
            columns=cols,
            row_count=tbl.num_rows,
            freshness_ts=tbl.modified,
        )

    def explain(self, sql: str) -> QueryPlan:
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        try:
            job = self.client.query(sql, job_config=cfg)
            return QueryPlan(
                estimated_bytes=job.total_bytes_processed,
                backend=self.name,
            )
        except Exception as e:  # noqa: BLE001
            return QueryPlan(backend=self.name, warnings=[f"dry-run failed: {e}"])

    def execute(self, sql: str, max_bytes: int | None = None) -> QueryResult:
        cfg = bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes) if max_bytes else None
        t0 = time.perf_counter()
        job = self.client.query(sql, job_config=cfg)
        result = job.result()
        rows = [dict(r.items()) for r in result]
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return QueryResult(
            rows=rows,
            row_count=len(rows),
            bytes_processed=job.total_bytes_processed,
            latency_ms=latency_ms,
            sql=sql,
            freshness_ts=datetime.now(),
        )

    def close(self) -> None:
        self.client.close()
