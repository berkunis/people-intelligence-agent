"""Pick the backend from env. Callers don't care which one they got."""

from __future__ import annotations

import os

from storage.adapter import StorageBackend


def get_backend() -> StorageBackend:
    backend = os.getenv("PIA_STORAGE_BACKEND", "duckdb").lower()
    if backend == "duckdb":
        from storage.duckdb_backend import DuckDBBackend

        path = os.getenv("PIA_DUCKDB_PATH", "data/warehouse/pia.duckdb")
        return DuckDBBackend(path)
    if backend == "bigquery":
        from storage.bigquery_backend import BigQueryBackend

        return BigQueryBackend()
    raise ValueError(f"Unknown PIA_STORAGE_BACKEND={backend}; expected 'duckdb' or 'bigquery'")
