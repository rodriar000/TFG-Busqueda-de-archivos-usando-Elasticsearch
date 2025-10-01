"""CLI command for testing Elasticsearch analyzers."""
from __future__ import annotations

import logging

import click
from rich.console import Console
from rich.table import Table

from src.cli.context import get_app_config, get_service
from src.cli.utils import ELASTIC_ERRORS

logger = logging.getLogger(__name__)
console = Console()


def register(cli: click.Group) -> None:
    """Register the analyze command with the main CLI group."""

    @cli.command(name="analyze")
    @click.argument("text", type=str)
    @click.option(
        "--analyzer",
        type=str,
        default=None,
        help="Optional analyzer name to test (defaults to configured analyzer).",
    )
    @click.pass_context
    def analyze_command(ctx: click.Context, text: str, analyzer: str | None) -> None:
        """Display token analysis for ``TEXT`` using the configured index analyzer."""

        config = get_app_config(ctx)
        if not config.elasticsearch.has_credentials():
            raise click.ClickException(
                "Authentication is required to analyze text. Configure "
                "ELASTIC_USERNAME/ELASTIC_PASSWORD, ELASTIC_API_KEY, or "
                "ELASTIC_BEARER_TOKEN."
            )

        service = get_service(ctx)
        try:
            response = service.analyze_text(text, analyzer=analyzer)
        except ELASTIC_ERRORS as exc:
            logger.exception("Failed to analyze text")
            raise click.ClickException("Elasticsearch analysis failed.") from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected analysis error")
            raise click.ClickException(
                "An unexpected error occurred while analyzing text."
            ) from exc

        tokens = response.get("tokens", [])
        if not tokens:
            click.echo("No tokens returned for the supplied text.")
            return

        table = Table(title="Analyzed Tokens")
        table.add_column("Token", style="cyan")
        table.add_column("Position", justify="right")
        table.add_column("Start", justify="right")
        table.add_column("End", justify="right")

        for token in tokens:
            table.add_row(
                token.get("token", ""),
                str(token.get("position", "")),
                str(token.get("start_offset", "")),
                str(token.get("end_offset", "")),
            )

        console.print(table)
