"""The load-bearing file.

Governance middleware wraps every tool invocation with:
  1. RBAC — can this role call this tool?
  2. Pre-execution — bytes-scanned guard via dry-run
  3. Execution — the tool does its thing
  4. Post-execution — k-anonymity check on result
  5. PII redaction — before the LLM ever sees a row
  6. Audit — one record per call, written to the audit log

The decorator pattern is deliberate: any tool added without @governed is
rejected by the architectural lint in `tests/test_governance_lint.py`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

from governance import audit, k_anon, pii, rbac
from governance.rbac import Role


@dataclass
class ToolContext:
    role: Role
    audit_record: audit.AuditRecord
    max_bytes: int | None = None


@dataclass
class ToolResult:
    """What every @governed tool returns to the agent."""

    data: Any
    row_count: int
    sql: str | None = None
    refused: bool = False
    refusal_reason: str | None = None
    refusal_detail: str | None = None

    def for_llm(self) -> dict[str, Any]:
        """Shape handed to the LLM as a tool_result. No PII, no raw SQL bodies."""
        if self.refused:
            return {
                "refused": True,
                "reason": self.refusal_reason,
                "detail": self.refusal_detail,
            }
        return {
            "row_count": self.row_count,
            "data": self.data,
        }


class GovernanceViolation(Exception):
    """Raised when a tool call is structurally disallowed (RBAC, schema)."""


def governed(tool_name: str) -> Callable:
    """Decorator. Every agent tool must wear this."""

    def decorator(fn: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
        @wraps(fn)
        def wrapper(ctx: ToolContext, *args: Any, **kwargs: Any) -> ToolResult:
            t0 = time.perf_counter()

            # 1. RBAC
            if not rbac.can_invoke(ctx.role, tool_name):
                reason = f"Role {ctx.role.value} cannot invoke tool {tool_name}"
                ctx.audit_record.append_tool_call(
                    audit.ToolCallRecord(
                        name=tool_name,
                        arguments=kwargs,
                        refused=True,
                        refusal_reason="rbac",
                        latency_ms=0,
                    )
                )
                ctx.audit_record.refusals.append({"reason": "rbac", "detail": reason})
                return ToolResult(
                    data=None,
                    row_count=0,
                    refused=True,
                    refusal_reason="rbac",
                    refusal_detail=reason,
                )

            # 2 + 3. Execute
            result = fn(ctx, *args, **kwargs)

            # 4. k-anonymity (only for non-individual-level roles)
            grant = rbac.grant_for(ctx.role)
            decision = k_anon.check(
                result.row_count,
                threshold=grant.k_anon_threshold,
                allow_individual_rows=grant.allow_individual_rows,
            )
            if not decision.allowed:
                ctx.audit_record.refusals.append(
                    {"reason": decision.reason or "k_anon", "detail": decision.detail or ""}
                )
                result = ToolResult(
                    data=None,
                    row_count=result.row_count,
                    sql=result.sql,
                    refused=True,
                    refusal_reason=decision.reason,
                    refusal_detail=decision.detail,
                )

            # 5. PII redaction is applied by each tool against the data it returns,
            #    using pii.redact_rows with grant.allow_salary_amounts. See tools.py.
            #    (We apply it at the tool layer because the tool knows its table.)

            # 6. Audit
            latency_ms = int((time.perf_counter() - t0) * 1000)
            ctx.audit_record.append_tool_call(
                audit.ToolCallRecord(
                    name=tool_name,
                    arguments=kwargs,
                    row_count=result.row_count,
                    refused=result.refused,
                    refusal_reason=result.refusal_reason,
                    latency_ms=latency_ms,
                )
            )
            if result.sql:
                ctx.audit_record.sql_executed.append(result.sql)
            return result

        wrapper.__governed_tool_name__ = tool_name  # type: ignore[attr-defined]
        return wrapper

    return decorator


__all__ = [
    "GovernanceViolation",
    "ToolContext",
    "ToolResult",
    "governed",
    "pii",
    "rbac",
]
