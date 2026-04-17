"""The five tools the agent can call. Every one is wrapped in @governed.

Each tool returns a ToolResult. The middleware handles RBAC, k-anonymity,
audit logging. Tools are responsible for:
  - running the right query
  - applying PII redaction to their rows via pii.redact_rows
  - reporting a truthful row_count
"""

from __future__ import annotations

from typing import Any

from agent.sql_validator import validate
from governance import pii
from governance.middleware import ToolContext, ToolResult, governed
from governance.rbac import grant_for
from llm.client import ToolSpec
from storage.adapter import StorageBackend


def _summarize_rows(rows: list[dict[str, Any]], max_rows: int = 50) -> list[dict[str, Any]]:
    """Cap how many rows reach the LLM. Aggregates are small; raw lists get truncated."""
    return rows[:max_rows]


@governed("query_warehouse")
def query_warehouse(
    ctx: ToolContext,
    *,
    backend: StorageBackend,
    sql: str,
    table_hint: str | None = None,
) -> ToolResult:
    """Execute a validated read-only SQL query. Applies PII redaction per role."""
    v = validate(sql)
    if not v.ok:
        return ToolResult(
            data=None,
            row_count=0,
            sql=sql,
            refused=True,
            refusal_reason="invalid_sql",
            refusal_detail=v.error,
        )

    plan = backend.explain(sql)
    if ctx.max_bytes and plan.estimated_bytes and plan.estimated_bytes > ctx.max_bytes:
        return ToolResult(
            data=None,
            row_count=0,
            sql=sql,
            refused=True,
            refusal_reason="bytes_budget",
            refusal_detail=(
                f"dry-run {plan.estimated_bytes:,} bytes exceeds budget {ctx.max_bytes:,}"
            ),
        )

    result = backend.execute(sql, max_bytes=ctx.max_bytes)
    grant = grant_for(ctx.role)

    redacted = result.rows
    if table_hint:
        redacted = pii.redact_rows(
            table_hint, result.rows, allow_salary_amounts=grant.allow_salary_amounts
        )

    return ToolResult(
        data={
            "rows": _summarize_rows(redacted),
            "truncated": len(redacted) > 50,
            "latency_ms": result.latency_ms,
            "freshness_ts": str(result.freshness_ts) if result.freshness_ts else None,
            "bytes_processed": result.bytes_processed,
        },
        row_count=result.row_count,
        sql=sql,
    )


@governed("get_headcount_report")
def get_headcount_report(
    ctx: ToolContext,
    *,
    backend: StorageBackend,
    dimension: str = "org",
    region: str | None = None,
) -> ToolResult:
    """Headcount aggregation along one dimension, optionally filtered by region."""
    allowed_dims = {"org", "region", "level", "job_family"}
    if dimension not in allowed_dims:
        return ToolResult(
            data=None,
            row_count=0,
            refused=True,
            refusal_reason="invalid_argument",
            refusal_detail=f"dimension must be one of {sorted(allowed_dims)}",
        )
    where = "WHERE is_active"
    if region:
        where += f" AND region = '{region.replace(chr(39), '')}'"
    sql = f"""
        SELECT {dimension}, COUNT(*) AS headcount
        FROM workday_employees
        {where}
        GROUP BY 1
        ORDER BY 2 DESC
    """.strip()
    result = backend.execute(sql)
    return ToolResult(
        data={"rows": result.rows, "freshness_ts": str(result.freshness_ts)},
        row_count=result.row_count,
        sql=sql,
    )


@governed("analyze_attrition")
def analyze_attrition(
    ctx: ToolContext,
    *,
    backend: StorageBackend,
    org: str | None = None,
    region: str | None = None,
    months: int = 12,
) -> ToolResult:
    """Attrition rate over the last N months, optionally scoped to org/region."""
    filters = [f"termination_date >= CURRENT_DATE - INTERVAL {months} MONTH"]
    if org:
        filters.append(f"org = '{org.replace(chr(39), '')}'")
    if region:
        filters.append(f"region = '{region.replace(chr(39), '')}'")
    where = " AND ".join(filters)
    sql = f"""
        SELECT
            termination_reason,
            COUNT(*) AS terminations,
            ROUND(100.0 * COUNT(*) /
                NULLIF((SELECT COUNT(*) FROM workday_employees WHERE is_active), 0), 2) AS pct_of_active
        FROM workday_employees
        WHERE {where}
        GROUP BY 1
        ORDER BY 2 DESC
    """.strip()
    result = backend.execute(sql)
    return ToolResult(
        data={"rows": result.rows, "freshness_ts": str(result.freshness_ts)},
        row_count=result.row_count,
        sql=sql,
    )


@governed("summarize_pipeline")
def summarize_pipeline(
    ctx: ToolContext,
    *,
    backend: StorageBackend,
    org: str | None = None,
) -> ToolResult:
    """Hiring pipeline summary: applications by stage, optionally scoped to org."""
    where = "WHERE r.status = 'open'"
    if org:
        where += f" AND r.org = '{org.replace(chr(39), '')}'"
    sql = f"""
        SELECT
            a.current_stage,
            COUNT(*) AS applications,
            COUNT(DISTINCT a.req_id) AS reqs_touched
        FROM greenhouse_applications a
        JOIN greenhouse_requisitions r ON r.req_id = a.req_id
        {where}
        GROUP BY 1
        ORDER BY 2 DESC
    """.strip()
    result = backend.execute(sql)
    return ToolResult(
        data={"rows": result.rows, "freshness_ts": str(result.freshness_ts)},
        row_count=result.row_count,
        sql=sql,
    )


@governed("get_learning_completion")
def get_learning_completion(
    ctx: ToolContext,
    *,
    backend: StorageBackend,
    category: str | None = None,
) -> ToolResult:
    """Completion rate for courses, optionally filtered by category."""
    filters = []
    if category:
        filters.append(f"c.category = '{category.replace(chr(39), '')}'")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT
            c.category,
            COUNT(*) FILTER (WHERE cp.status = 'completed') AS completed,
            COUNT(*) AS assigned,
            ROUND(100.0 * COUNT(*) FILTER (WHERE cp.status = 'completed') / NULLIF(COUNT(*), 0), 2) AS completion_pct
        FROM docebo_completions cp
        JOIN docebo_courses c ON c.course_id = cp.course_id
        {where}
        GROUP BY 1
        ORDER BY 4 DESC
    """.strip()
    result = backend.execute(sql)
    return ToolResult(
        data={"rows": result.rows, "freshness_ts": str(result.freshness_ts)},
        row_count=result.row_count,
        sql=sql,
    )


# ---------- Tool specs exposed to the LLM ----------

TOOL_REGISTRY = {
    "query_warehouse": query_warehouse,
    "get_headcount_report": get_headcount_report,
    "analyze_attrition": analyze_attrition,
    "summarize_pipeline": summarize_pipeline,
    "get_learning_completion": get_learning_completion,
}


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="query_warehouse",
            description=(
                "Execute a validated read-only SQL query on the People warehouse. "
                "Prefer specialized tools over this one for common reports."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Read-only SELECT statement. Must reference only allowed tables.",
                    },
                    "table_hint": {
                        "type": "string",
                        "description": "Primary table the query targets, for PII redaction.",
                    },
                },
                "required": ["sql"],
            },
        ),
        ToolSpec(
            name="get_headcount_report",
            description="Active headcount aggregated by dimension (org|region|level|job_family).",
            input_schema={
                "type": "object",
                "properties": {
                    "dimension": {"type": "string", "enum": ["org", "region", "level", "job_family"]},
                    "region": {"type": "string", "description": "Optional filter: AMER|EMEA|APAC"},
                },
                "required": ["dimension"],
            },
        ),
        ToolSpec(
            name="analyze_attrition",
            description="Terminations by reason in the last N months, optionally scoped.",
            input_schema={
                "type": "object",
                "properties": {
                    "org": {"type": "string"},
                    "region": {"type": "string", "enum": ["AMER", "EMEA", "APAC"]},
                    "months": {"type": "integer", "default": 12},
                },
            },
        ),
        ToolSpec(
            name="summarize_pipeline",
            description="Open-req applications grouped by stage.",
            input_schema={
                "type": "object",
                "properties": {"org": {"type": "string"}},
            },
        ),
        ToolSpec(
            name="get_learning_completion",
            description="Course completion rate by category.",
            input_schema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["compliance", "leadership", "technical", "soft_skills"],
                    }
                },
            },
        ),
    ]
