"""The agent loop. Typed state machine — no framework.

States:
  THINKING   → call LLM
  TOOL_USE   → LLM requested a tool; invoke it, append tool_result, go back to THINKING
  ANSWER     → LLM returned final text; emit AgentAnswer and stop
  REFUSED    → governance layer refused (RBAC / k-anon / budget); stop
  ERROR      → unrecoverable error; stop

Budgets:
  MAX_TOOL_CALLS (default 8) — protects against infinite tool loops
  TOKEN_BUDGET   (default 50k) — cost governance
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from agent.tools import TOOL_REGISTRY, tool_specs
from governance import audit
from governance.middleware import ToolContext, ToolResult
from governance.rbac import Role, grant_for
from llm.client import LLMClient, Message, StopReason
from observability import metrics
from storage.adapter import StorageBackend

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class State(str, Enum):
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    ANSWER = "answer"
    REFUSED = "refused"
    ERROR = "error"


@dataclass
class AgentAnswer:
    text: str
    sql_executed: list[str]
    tool_calls: list[str]
    refusals: list[dict[str, str]]
    citations: dict[str, Any]
    audit_id: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    refused: bool = False


@dataclass
class AgentConfig:
    max_tool_calls: int = int(os.getenv("PIA_MAX_TOOL_CALLS", "8"))
    token_budget: int = int(os.getenv("PIA_TOKEN_BUDGET_PER_QUERY", "50000"))
    bytes_budget: int = int(os.getenv("PIA_BQ_BYTES_SCANNED_LIMIT", "1073741824"))
    max_output_tokens: int = 2048
    system_prompt_version: str = "text_to_sql/v1.0.0"


def _load_prompt(version: str) -> tuple[str, str]:
    """Return (body, sha256). Today's date is substituted."""
    path = PROMPTS_DIR / f"{version}.md"
    body = path.read_text()
    body = body.replace("{today}", date.today().isoformat())
    digest = hashlib.sha256(body.encode()).hexdigest()[:16]
    return body, digest


def _schema_block(backend: StorageBackend) -> str:
    """Inject the schema the LLM is allowed to see."""
    parts = ["<schema>"]
    for table in backend.list_tables():
        cols = ", ".join(f"{c.name}:{c.data_type}" for c in table.columns)
        desc = f" — {table.description}" if table.description else ""
        parts.append(f"- {table.name} ({table.row_count or '?'} rows){desc}")
        parts.append(f"    {cols}")
    parts.append("</schema>")
    return "\n".join(parts)


@dataclass
class _RunState:
    messages: list[Message] = field(default_factory=list)
    tool_calls_made: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


def run(
    *,
    question: str,
    role: Role,
    backend: StorageBackend,
    llm: LLMClient,
    cfg: AgentConfig | None = None,
) -> AgentAnswer:
    cfg = cfg or AgentConfig()
    grant = grant_for(role)
    system_body, prompt_hash = _load_prompt(cfg.system_prompt_version)
    system = f"{system_body}\n\n{_schema_block(backend)}"

    audit_rec = audit.AuditRecord(
        requester_role=role.value,
        question=question,
        prompt_hashes=[f"{cfg.system_prompt_version}#{prompt_hash}"],
        model=llm.model,
    )
    ctx = ToolContext(role=role, audit_record=audit_rec, max_bytes=cfg.bytes_budget)

    state = State.THINKING
    rs = _RunState(messages=[Message(role="user", content=question)])
    t0 = time.perf_counter()
    final_text = ""

    while state not in (State.ANSWER, State.REFUSED, State.ERROR):
        # Budget checks
        if rs.tool_calls_made >= cfg.max_tool_calls:
            state = State.REFUSED
            audit_rec.refusals.append(
                {"reason": "tool_call_budget", "detail": f"exceeded {cfg.max_tool_calls}"}
            )
            final_text = "I exceeded my tool-call budget before reaching an answer. Please rephrase."
            break
        if rs.tokens_in + rs.tokens_out >= cfg.token_budget:
            state = State.REFUSED
            audit_rec.refusals.append(
                {"reason": "token_budget", "detail": f"exceeded {cfg.token_budget}"}
            )
            final_text = "Token budget exhausted. Please rephrase more narrowly."
            break

        # 1. Call LLM
        response = llm.complete(
            system=system,
            messages=rs.messages,
            tools=tool_specs(),
            max_tokens=cfg.max_output_tokens,
        )
        rs.tokens_in += response.input_tokens
        rs.tokens_out += response.output_tokens
        rs.cost_usd += response.cost_usd

        if response.stop_reason == StopReason.TOOL_USE and response.tool_calls:
            # Append assistant turn (Claude shape: need to include tool_use blocks)
            assistant_content: list[dict[str, Any]] = []
            if response.text:
                assistant_content.append({"type": "text", "text": response.text})
            for tc in response.tool_calls:
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            rs.messages.append(Message(role="assistant", content=assistant_content))

            state = State.TOOL_USE

            # 2. Execute each tool call
            for tc in response.tool_calls:
                rs.tool_calls_made += 1
                fn = TOOL_REGISTRY.get(tc.name)
                if fn is None:
                    result = ToolResult(
                        data=None,
                        row_count=0,
                        refused=True,
                        refusal_reason="unknown_tool",
                        refusal_detail=f"{tc.name} not registered",
                    )
                else:
                    try:
                        result = fn(ctx, backend=backend, **tc.arguments)
                    except Exception as e:  # noqa: BLE001
                        result = ToolResult(
                            data=None,
                            row_count=0,
                            refused=True,
                            refusal_reason="tool_error",
                            refusal_detail=str(e),
                        )
                rs.messages.append(
                    llm.format_tool_result(tc.id, json.dumps(result.for_llm(), default=str))
                )
            state = State.THINKING
            continue

        # End turn: final answer
        final_text = response.text
        state = State.ANSWER

    latency_ms = int((time.perf_counter() - t0) * 1000)
    audit_rec.tokens_in = rs.tokens_in
    audit_rec.tokens_out = rs.tokens_out
    audit_rec.cost_usd = round(rs.cost_usd, 6)
    audit_rec.latency_ms = latency_ms
    audit_rec.response_summary = (final_text[:280] + "…") if len(final_text) > 280 else final_text
    audit.write(audit_rec)

    # Observability — emit Prometheus metrics for this run.
    outcome = "refused" if state == State.REFUSED else "answered"
    metrics.agent_queries_total.labels(role=role.value, model=llm.model, outcome=outcome).inc()
    metrics.agent_latency_seconds.labels(role=role.value).observe(latency_ms / 1000.0)
    metrics.agent_tool_calls_per_query.labels(role=role.value).observe(rs.tool_calls_made)
    metrics.agent_tokens_total.labels(direction="in").inc(rs.tokens_in)
    metrics.agent_tokens_total.labels(direction="out").inc(rs.tokens_out)
    metrics.agent_cost_usd_total.labels(model=llm.model).inc(rs.cost_usd)
    for tc in audit_rec.tool_calls:
        tool_outcome = "refused" if tc.refused else "ok"
        metrics.agent_tool_calls_total.labels(tool=tc.name, outcome=tool_outcome).inc()
    for ref in audit_rec.refusals:
        metrics.agent_refusals_total.labels(reason=ref.get("reason", "unknown")).inc()
    metrics.push_to_gateway()

    citations: dict[str, Any] = {
        "sql_executed": audit_rec.sql_executed,
        "tool_calls": [tc.name for tc in audit_rec.tool_calls],
        "prompt_hashes": audit_rec.prompt_hashes,
        "model": llm.model,
    }

    return AgentAnswer(
        text=final_text,
        sql_executed=audit_rec.sql_executed,
        tool_calls=[tc.name for tc in audit_rec.tool_calls],
        refusals=audit_rec.refusals,
        citations=citations,
        audit_id=audit_rec.audit_id,
        tokens_in=rs.tokens_in,
        tokens_out=rs.tokens_out,
        cost_usd=round(rs.cost_usd, 6),
        latency_ms=latency_ms,
        refused=state == State.REFUSED,
    )
