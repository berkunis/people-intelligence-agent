"""Quick interactive query tool — `uv run python -m storage.query "SELECT ..."`.

Exists so you can sanity-check the warehouse without writing inline Python.
The agent uses the same StorageBackend under the hood.
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table

from storage.factory import get_backend

DEFAULT_SQL = """
SELECT org, region, COUNT(*) AS headcount
FROM workday_employees
WHERE is_active
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 15
"""


def main() -> None:
    sql = " ".join(sys.argv[1:]).strip() or DEFAULT_SQL
    console = Console()
    backend = get_backend()
    try:
        result = backend.execute(sql)
        if not result.rows:
            console.print("[yellow]no rows[/yellow]")
            return
        table = Table(show_lines=False, header_style="bold cyan")
        for col in result.rows[0]:
            table.add_column(str(col))
        for row in result.rows:
            table.add_row(*[str(v) if v is not None else "—" for v in row.values()])
        console.print(table)
        console.print(
            f"\n[dim]{result.row_count} rows · {result.latency_ms}ms · "
            f"freshness={result.freshness_ts:%Y-%m-%d %H:%M}[/dim]"
        )
    finally:
        backend.close()


if __name__ == "__main__":
    main()
