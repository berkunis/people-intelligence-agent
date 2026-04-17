"""Storage adapter protocol. Lets the agent speak one API to DuckDB or BigQuery.

The point of this abstraction:
  - Local demo runs against DuckDB with no cloud setup
  - Production path runs against BigQuery with IAM, bytes-scanned limits, audit
  - The agent's SQL and query plan remain the same
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    data_type: str
    description: str = ""


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: list[ColumnSchema]
    description: str = ""
    row_count: int | None = None
    freshness_ts: datetime | None = None


@dataclass
class QueryPlan:
    """What a dry-run tells us before we pay to execute."""

    estimated_bytes: int | None = None
    estimated_rows: int | None = None
    backend: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    row_count: int
    bytes_processed: int | None
    latency_ms: int
    sql: str
    freshness_ts: datetime | None = None


class StorageBackend(ABC):
    """Abstract storage backend. Implementations: DuckDBBackend, BigQueryBackend."""

    name: str

    @abstractmethod
    def list_tables(self) -> list[TableSchema]:
        """All tables the agent is permitted to see."""

    @abstractmethod
    def get_schema(self, table: str) -> TableSchema:
        """Schema for one table."""

    @abstractmethod
    def explain(self, sql: str) -> QueryPlan:
        """Dry-run: what will this query cost?"""

    @abstractmethod
    def execute(self, sql: str, max_bytes: int | None = None) -> QueryResult:
        """Run the query. max_bytes is the circuit breaker."""

    @abstractmethod
    def close(self) -> None: ...
