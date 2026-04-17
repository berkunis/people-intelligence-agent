"""Role-based access control for tools.

Four roles. Each role is granted a set of tool names and a flag for whether
it can see individual-level (un-aggregated) rows and absolute compensation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    HRBP = "HRBP"
    RECRUITER = "RECRUITER"
    LEADER = "LEADER"
    ANALYST = "ANALYST"


@dataclass(frozen=True)
class RoleGrant:
    tools: frozenset[str]
    allow_individual_rows: bool
    allow_salary_amounts: bool
    k_anon_threshold: int


GRANTS: dict[Role, RoleGrant] = {
    Role.HRBP: RoleGrant(
        tools=frozenset({
            "query_warehouse",
            "get_headcount_report",
            "analyze_attrition",
            "summarize_pipeline",
            "get_learning_completion",
        }),
        allow_individual_rows=True,
        allow_salary_amounts=True,
        k_anon_threshold=1,
    ),
    Role.RECRUITER: RoleGrant(
        tools=frozenset({
            "query_warehouse",
            "summarize_pipeline",
        }),
        allow_individual_rows=True,
        allow_salary_amounts=False,
        k_anon_threshold=1,
    ),
    Role.LEADER: RoleGrant(
        tools=frozenset({
            "query_warehouse",
            "get_headcount_report",
            "analyze_attrition",
            "get_learning_completion",
        }),
        allow_individual_rows=False,
        allow_salary_amounts=False,
        k_anon_threshold=5,
    ),
    Role.ANALYST: RoleGrant(
        tools=frozenset({
            "query_warehouse",
            "get_headcount_report",
            "analyze_attrition",
            "summarize_pipeline",
            "get_learning_completion",
        }),
        allow_individual_rows=False,
        allow_salary_amounts=False,
        k_anon_threshold=5,
    ),
}


def grant_for(role: Role) -> RoleGrant:
    return GRANTS[role]


def can_invoke(role: Role, tool_name: str) -> bool:
    return tool_name in GRANTS[role].tools
