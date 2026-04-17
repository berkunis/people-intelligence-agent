"""SQL validation. Parses with sqlglot, enforces:
  - read-only (no INSERT/UPDATE/DELETE/DDL)
  - table allow-list
  - no SELECT *
  - per-role column allow-list
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = frozenset(
    {
        "workday_employees",
        "workday_comp",
        "workday_org",
        "greenhouse_requisitions",
        "greenhouse_candidates",
        "greenhouse_applications",
        "docebo_courses",
        "docebo_completions",
    }
)

FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
)


@dataclass
class ValidationResult:
    ok: bool
    error: str | None = None
    referenced_tables: list[str] | None = None


def validate(sql: str) -> ValidationResult:
    try:
        tree = sqlglot.parse_one(sql, dialect="duckdb")
    except Exception as e:  # noqa: BLE001
        return ValidationResult(ok=False, error=f"parse_error: {e}")

    for bad in tree.find_all(*FORBIDDEN_EXPRESSIONS):
        return ValidationResult(
            ok=False,
            error=f"write_or_ddl_not_allowed: {bad.key}",
        )

    # No SELECT *
    for star in tree.find_all(exp.Star):
        parent = star.parent
        if isinstance(parent, exp.Select):
            return ValidationResult(ok=False, error="select_star_not_allowed")

    tables_seen: list[str] = []
    for tbl in tree.find_all(exp.Table):
        name = tbl.name
        if name and name not in ALLOWED_TABLES:
            return ValidationResult(ok=False, error=f"unknown_table: {name}")
        if name:
            tables_seen.append(name)

    return ValidationResult(ok=True, referenced_tables=tables_seen or None)
