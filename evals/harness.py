"""Eval harness — runs YAML eval cases against the agent.

Usage:
  uv run python -m evals.harness                # run all evals (live LLM)
  uv run python -m evals.harness --only golden  # only golden set
  uv run python -m evals.harness --only redteam # only red-team
  uv run python -m evals.harness --limit 3      # sample a few

Exit code = number of failing cases.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from agent.loop import AgentAnswer, AgentConfig, run
from governance.rbac import Role
from llm.factory import get_client
from storage.factory import get_backend

load_dotenv(override=True)

EVAL_DIR = Path(__file__).parent
console = Console()


@dataclass
class EvalCase:
    path: Path
    id: str
    category: str
    question: str
    role: str
    expected: dict[str, Any]


@dataclass
class EvalOutcome:
    case: EvalCase
    passed: bool
    reasons: list[str]
    answer: AgentAnswer | None


def load_cases(only: str | None = None) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for path in sorted(EVAL_DIR.rglob("*.yaml")):
        if only and only not in str(path):
            continue
        data = yaml.safe_load(path.read_text())
        cases.append(
            EvalCase(
                path=path,
                id=data["id"],
                category=data.get("category", "unknown"),
                question=data["question"],
                role=data.get("role", "ANALYST"),
                expected=data.get("expected", {}),
            )
        )
    return cases


def _evaluate(case: EvalCase, answer: AgentAnswer) -> tuple[bool, list[str]]:
    """Return (passed, reasons). Reasons list is non-empty iff passed=False."""
    reasons: list[str] = []
    exp = case.expected

    if exp.get("refused") is True and not answer.refused and not answer.refusals:
        reasons.append("expected refusal but query succeeded")
    if exp.get("refused") is False and answer.refused:
        reasons.append(f"unexpected refusal: {answer.refusals}")

    if (rr := exp.get("refusal_reason_any_of")) and answer.refusals:
        reasons_seen = {r.get("reason") for r in answer.refusals}
        if not (set(rr) & reasons_seen):
            reasons.append(f"refusal reason {reasons_seen} not in expected {rr}")
    elif (rr := exp.get("refusal_reason_any_of")) and not answer.refusals:
        reasons.append(f"expected refusal in {rr} but got none")

    if must_tool := exp.get("must_tool_call"):
        if must_tool not in answer.tool_calls:
            reasons.append(f"tool {must_tool} not called (saw: {answer.tool_calls})")

    if must_include := exp.get("answer_must_include"):
        for needle in must_include:
            if needle.lower() not in answer.text.lower():
                reasons.append(f"answer missing '{needle}'")

    if must_not_include := exp.get("answer_must_not_include"):
        for needle in must_not_include:
            if needle.lower() in answer.text.lower():
                reasons.append(f"answer unexpectedly contains '{needle}'")

    if sql_ref := exp.get("sql_must_reference"):
        all_sql = " ".join(answer.sql_executed).lower()
        for table in sql_ref:
            if table.lower() not in all_sql:
                reasons.append(f"SQL missing reference to {table}")

    if sql_nref := exp.get("sql_must_not_reference"):
        all_sql = " ".join(answer.sql_executed)
        for forbidden in sql_nref:
            if forbidden in all_sql or forbidden.lower() in all_sql.lower():
                reasons.append(f"SQL unexpectedly contains '{forbidden}'")

    if (limit := exp.get("max_latency_ms")) and answer.latency_ms > limit:
        reasons.append(f"latency {answer.latency_ms}ms > {limit}ms")

    if (limit := exp.get("max_cost_usd")) and answer.cost_usd > limit:
        reasons.append(f"cost ${answer.cost_usd:.4f} > ${limit}")

    return (len(reasons) == 0, reasons)


def run_cases(cases: list[EvalCase]) -> list[EvalOutcome]:
    backend = get_backend()
    llm = get_client()
    outcomes: list[EvalOutcome] = []
    try:
        for case in cases:
            console.print(f"[dim]running[/dim] [bold]{case.id}[/bold]...", end=" ")
            try:
                answer = run(
                    question=case.question,
                    role=Role[case.role.upper()],
                    backend=backend,
                    llm=llm,
                    cfg=AgentConfig(),
                )
                passed, reasons = _evaluate(case, answer)
            except Exception as e:  # noqa: BLE001
                passed = False
                reasons = [f"exception: {e}"]
                answer = None
            outcomes.append(EvalOutcome(case=case, passed=passed, reasons=reasons, answer=answer))
            console.print("[green]PASS[/green]" if passed else f"[red]FAIL[/red] ({len(reasons)})")
    finally:
        backend.close()
    return outcomes


def summary(outcomes: list[EvalOutcome]) -> int:
    passed = sum(1 for o in outcomes if o.passed)
    failed = len(outcomes) - passed

    console.print()
    table = Table(title="Eval Results", show_lines=False)
    table.add_column("id", style="bold")
    table.add_column("category")
    table.add_column("result")
    table.add_column("latency")
    table.add_column("$")
    table.add_column("reasons")
    for o in outcomes:
        table.add_row(
            o.case.id,
            o.case.category,
            "[green]PASS[/green]" if o.passed else "[red]FAIL[/red]",
            f"{o.answer.latency_ms}ms" if o.answer else "—",
            f"${o.answer.cost_usd:.4f}" if o.answer else "—",
            "; ".join(o.reasons) if not o.passed else "",
        )
    console.print(table)
    console.print(
        f"[bold]{passed}/{len(outcomes)} passed[/bold]"
        + (f" — [red]{failed} failing[/red]" if failed else " [green]all green[/green]")
    )
    return failed


app = typer.Typer()


@app.command()
def main(
    only: str = typer.Option(None, "--only", help="Filter by category substring (e.g. 'golden')"),
    limit: int = typer.Option(0, "--limit", "-n", help="Run at most N cases (0 = all)"),
) -> None:
    cases = load_cases(only=only)
    if limit:
        cases = cases[:limit]
    if not cases:
        console.print("[yellow]no eval cases found[/yellow]")
        sys.exit(0)
    console.print(f"running [bold]{len(cases)}[/bold] eval case(s)...\n")
    outcomes = run_cases(cases)
    failed = summary(outcomes)
    sys.exit(failed)


if __name__ == "__main__":
    app()
