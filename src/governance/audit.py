"""Audit log. Every agent call gets one row.

v0.1: writes to a local JSONL file + an `audit.agent_calls` DuckDB table.
Production path: BigQuery + Pub/Sub fan-out for real-time monitoring.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_DIR = Path(os.getenv("PIA_AUDIT_DIR", "data/audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_PATH = AUDIT_DIR / "agent_calls.jsonl"


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    row_count: int | None = None
    refused: bool = False
    refusal_reason: str | None = None
    latency_ms: int | None = None


@dataclass
class AuditRecord:
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    requester_role: str = ""
    question: str = ""
    prompt_hashes: list[str] = field(default_factory=list)
    model: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    sql_executed: list[str] = field(default_factory=list)
    refusals: list[dict[str, str]] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    response_summary: str = ""

    def append_tool_call(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)


def write(record: AuditRecord) -> None:
    with AUDIT_LOG_PATH.open("a") as f:
        f.write(json.dumps(asdict(record), default=str) + "\n")
