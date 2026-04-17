"""k-anonymity threshold enforcement.

If a query returns fewer than k rows, the middleware refuses with a structured
refusal. The agent never rephrases a refused query in an attempt to circumvent
(enforced by a check in the agent loop).

Special case: individual-level tools (with `allow_individual_rows=True` role)
bypass k-anon — the role carries the authorization.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KAnonDecision:
    allowed: bool
    reason: str | None = None
    detail: str | None = None


def check(
    row_count: int,
    *,
    threshold: int,
    allow_individual_rows: bool,
) -> KAnonDecision:
    if allow_individual_rows:
        return KAnonDecision(allowed=True)
    if row_count < threshold:
        return KAnonDecision(
            allowed=False,
            reason="k_anonymity",
            detail=f"Query returned {row_count} rows; k={threshold} threshold enforced.",
        )
    return KAnonDecision(allowed=True)
