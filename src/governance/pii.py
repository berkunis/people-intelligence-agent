"""PII anonymization. Applied before any row reaches the LLM.

Design: the *storage adapter* returns raw rows; the governance middleware
applies redaction per data-class config before the rows enter the agent's
message history. A bug in agent code cannot leak data because the agent
never sees it.
"""

from __future__ import annotations

from typing import Any

# Per-column governance class. Extend per source system.
COLUMN_CLASSES: dict[str, dict[str, str]] = {
    "workday_employees": {
        "full_name": "pii_strip",
        "work_email": "pii_domain_only",
        "country": "public",
        "hire_date": "public",
        "termination_date": "public",
        "termination_reason": "public",
        "is_active": "public",
        "org": "public",
        "region": "public",
        "level": "public",
        "is_manager": "public",
        "job_family": "public",
        "job_title": "public",
        "employee_id": "stable_id",
        "manager_id": "stable_id",
    },
    "workday_comp": {
        "employee_id": "stable_id",
        "effective_date": "public",
        "base_salary_usd": "comp_restricted",
        "salary_band": "public",
        "currency": "public",
        "region": "public",
    },
    "greenhouse_candidates": {
        "candidate_id": "stable_id",
        "first_seen_at": "public",
        "source": "public",
        "external_email": "pii_domain_only",
    },
}


def _domain_only(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return "@" + email.split("@", 1)[1]


def redact_row(
    table: str,
    row: dict[str, Any],
    *,
    allow_salary_amounts: bool = False,
) -> dict[str, Any]:
    """Apply column-class redactions for one row."""
    classes = COLUMN_CLASSES.get(table, {})
    out: dict[str, Any] = {}
    for col, val in row.items():
        cls = classes.get(col, "unknown")
        if cls == "pii_strip":
            continue
        if cls == "pii_domain_only":
            out[col] = _domain_only(val)
        elif cls == "comp_restricted" and not allow_salary_amounts:
            continue  # keep salary_band only
        else:
            out[col] = val
    return out


def redact_rows(
    table: str,
    rows: list[dict[str, Any]],
    *,
    allow_salary_amounts: bool = False,
) -> list[dict[str, Any]]:
    return [redact_row(table, r, allow_salary_amounts=allow_salary_amounts) for r in rows]
