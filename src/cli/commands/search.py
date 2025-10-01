"""CLI command for executing search queries."""
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
    """Register the command with the main CLI group."""

    @cli.command(name="search")
    @click.argument("query", type=str)
    @click.option(
        "--top",
        type=int,
        default=None,
        help="Number of top results to return.",
    )
    @click.pass_context
    def search_command(ctx: click.Context, query: str, top: int | None) -> None:
        """Execute ``QUERY`` against the configured index."""

        config = get_app_config(ctx)
        if not config.elasticsearch.has_credentials():
            raise click.ClickException(
                "Authentication is required to search. Configure "
                "ELASTIC_USERNAME/ELASTIC_PASSWORD, ELASTIC_API_KEY, or "
                "ELASTIC_BEARER_TOKEN."
            )

        service = get_service(ctx)
        top = top or config.cli.default_top

        if not query.strip():
            raise click.BadParameter("Query string cannot be empty.")

        try:
            response = service.search(query, top)
        except ELASTIC_ERRORS as exc:
            logger.exception("Search execution failed")
            raise click.ClickException("Failed to execute the search query.") from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error during search")
            raise click.ClickException("An unexpected error occurred during search.") from exc

        hits = response.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        click.echo(f"Total hits: {total}")

        table = Table(title="Top Results")
        table.add_column("Path", style="cyan")
        table.add_column("Score", style="magenta")

        for hit in hits.get("hits", []):
            source = hit.get("_source", {})
            table.add_row(source.get("path", "N/A"), f"{hit.get('_score', 0):.2f}")

        console.print(table)
