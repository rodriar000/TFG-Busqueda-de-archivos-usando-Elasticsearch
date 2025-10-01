"""Helpers for rendering CLI outputs (tables, stats, etc.)."""
from __future__ import annotations
from rich.console import Console
from rich.table import Table

console = Console()

def render_stats(stats: dict[str, int | str]) -> None:
    """Render statistics in a nice table using Rich."""
    table = Table(title="Elasticsearch Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)
