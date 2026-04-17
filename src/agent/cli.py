"""`pia` command-line entry point.

Usage:
  pia ask "What is engineering headcount in EMEA?"
  pia ask "..." --role HRBP
  pia schema
  pia audit-tail
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from agent.loop import AgentConfig, run
from governance.rbac import Role
from llm.factory import get_client
from storage.factory import get_backend

load_dotenv()

app = typer.Typer(help="people-intelligence-agent CLI")
console = Console()


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural-language question"),
    role: str = typer.Option("ANALYST", "--role", "-r", help="HRBP|RECRUITER|LEADER|ANALYST"),
) -> None:
    """Ask the agent a question."""
    backend = get_backend()
    llm = get_client()
    try:
        answer = run(
            question=question,
            role=Role[role.upper()],
            backend=backend,
            llm=llm,
            cfg=AgentConfig(),
        )
    finally:
        backend.close()

    if answer.refused:
        console.print(Panel(answer.text or "refused", style="red", title="Refused"))
    else:
        console.print(Panel(answer.text, style="green", title="Answer"))

    meta = Table(show_header=False, box=None, pad_edge=False)
    meta.add_row("[dim]model[/dim]", answer.citations.get("model", ""))
    meta.add_row("[dim]tool calls[/dim]", ", ".join(answer.tool_calls) or "—")
    meta.add_row("[dim]latency[/dim]", f"{answer.latency_ms} ms")
    meta.add_row(
        "[dim]tokens[/dim]",
        f"{answer.tokens_in} in / {answer.tokens_out} out  (${answer.cost_usd:.4f})",
    )
    meta.add_row("[dim]audit_id[/dim]", answer.audit_id)
    console.print(meta)

    for sql in answer.sql_executed:
        console.print(Syntax(sql, "sql", theme="ansi_dark", line_numbers=False))

    if answer.refusals:
        console.print(Panel(json.dumps(answer.refusals, indent=2), title="Refusals", style="yellow"))


@app.command()
def schema() -> None:
    """Print the warehouse schema the agent sees."""
    backend = get_backend()
    try:
        for t in backend.list_tables():
            console.print(f"[bold cyan]{t.name}[/bold cyan]  ({t.row_count} rows)")
            if t.description:
                console.print(f"  [dim]{t.description}[/dim]")
            for c in t.columns:
                console.print(f"  {c.name}: {c.data_type}")
            console.print()
    finally:
        backend.close()


@app.command("audit-tail")
def audit_tail(n: int = typer.Option(5, "-n", help="How many recent records to show")) -> None:
    """Tail the audit log."""
    path = Path("data/audit/agent_calls.jsonl")
    if not path.exists():
        console.print("[yellow]No audit log yet — ask a question first.[/yellow]")
        return
    lines = path.read_text().splitlines()[-n:]
    for line in lines:
        record = json.loads(line)
        console.print(Panel(json.dumps(record, indent=2, default=str), title=record["audit_id"][:8]))


if __name__ == "__main__":
    app()
