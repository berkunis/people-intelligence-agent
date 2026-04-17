"""k-anonymity threshold enforcement.

Two distinct checks:
  1. Individual-row refusal: if a role cannot see individual rows, a tool that
     returns individual-level data is refused outright.
  2. Small-cell suppression: on aggregated results, any group (row) whose
     count-like value is below `threshold` triggers refusal. Large aggregate
     categories are fine — "AMER=574, EMEA=310, APAC=155" passes k=5 because
     every group has >= 5 members.

The agent never rephrases a refused query in an attempt to circumvent
(enforced by a check in the agent loop).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COUNT_LIKE_COLUMNS = {
    "count",
    "headcount",
    "terminations",
    "completed",
    "assigned",
    "applications",
    "reqs_touched",
    "count_star()",
    "n",
}


@dataclass(frozen=True)
class KAnonDecision:
    allowed: bool
    reason: str | None = None
    detail: str | None = None


def _min_count_across_groups(rows: list[dict[str, Any]]) -> int | None:
    """Lowest integer value across rows in any column named like a count."""
    if not rows:
        return None
    mins: list[int] = []
    for row in rows:
        for col, val in row.items():
            if col.lower() in COUNT_LIKE_COLUMNS and isinstance(val, (int, float)) and val > 0:
                mins.append(int(val))
    return min(mins) if mins else None


def check(
    row_count: int,
    *,
    threshold: int,
    allow_individual_rows: bool,
    rows: list[dict[str, Any]] | None = None,
) -> KAnonDecision:
    if allow_individual_rows:
        return KAnonDecision(allowed=True)

    # 1. No rows at all → pass (empty result isn't a privacy concern).
    if row_count == 0:
        return KAnonDecision(allowed=True)

    # 2. If we can see count-like columns, check minimum group size.
    if rows is not None:
        min_group = _min_count_across_groups(rows)
        if min_group is not None:
            if min_group < threshold:
                return KAnonDecision(
                    allowed=False,
                    reason="k_anonymity",
                    detail=f"Smallest group has {min_group} members; k={threshold} threshold enforced.",
                )
            return KAnonDecision(allowed=True)

    # 3. No count column seen → conservative fallback: refuse if fewer than k rows.
    if row_count < threshold:
        return KAnonDecision(
            allowed=False,
            reason="k_anonymity",
            detail=f"Query returned {row_count} rows and no count column; k={threshold} threshold enforced.",
        )
    return KAnonDecision(allowed=True)
