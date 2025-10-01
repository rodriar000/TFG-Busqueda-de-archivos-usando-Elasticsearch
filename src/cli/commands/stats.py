"""CLI command to display index and cluster statistics."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import click
from src.cli.context import get_service
from src.cli.utils import ELASTIC_ERRORS
from src.cli.rendering import render_stats   # ✅ ahora desde rendering.py

logger = logging.getLogger(__name__)


def register(cli: click.Group) -> None:
    """Register the command with the main CLI group."""

    @cli.command(name="stats")
    @click.option(
        "--output",
        "output_format",
        type=click.Choice(["table", "json", "csv"], case_sensitive=False),
        default="table",
        show_default=True,
        help="Output format for statistics.",
    )
    @click.option(   # ✅ corregido
        "--export",
        "export_path",
        type=click.Path(path_type=Path, dir_okay=False),
        help="Optional path to export the statistics for evaluation.",
    )
    @click.pass_context
    def stats_command(ctx: click.Context, output_format: str, export_path: Path | None) -> None:
        """Display statistics for the configured Elasticsearch index."""

        service = get_service(ctx)
        try:
            stats = service.stats()
        except ELASTIC_ERRORS as exc:
            logger.exception("Failed to retrieve statistics")
            raise click.ClickException("Unable to retrieve Elasticsearch statistics.") from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error retrieving statistics")
            raise click.ClickException("An unexpected error occurred while fetching statistics.") from exc

        _render_output(stats, output_format)

        if export_path:
            _export_stats(stats, export_path, output_format)


def _render_output(stats: dict[str, object], output_format: str) -> None:
    normalized = output_format.lower()
    if normalized == "json":
        click.echo(json.dumps(stats, indent=2, default=str))
    elif normalized == "csv":
        click.echo(_to_csv(stats))
    else:
        render_stats(stats)


def _export_stats(stats: dict[str, object], path: Path, output_format: str) -> None:
    normalized = output_format.lower()
    if normalized == "json":
        path.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
        return
    csv_content = _to_csv(stats)
    path.write_text(csv_content, encoding="utf-8")


def _to_csv(stats: dict[str, object]) -> str:
    lines = ["metric,value"]
    for key, value in stats.items():
        lines.append(f"{key},{_escape_csv_value(value)}")
    return "\n".join(lines)


def _escape_csv_value(value: object) -> str:
    text = str(value)
    if any(c in text for c in [",", "\n", '"']):
        return f'"{text.replace('"', '""')}"'
    return text
