"""CLI command for initialising an Elasticsearch index."""
from __future__ import annotations

import logging

import click
from src.cli.context import get_service
from src.cli.utils import ELASTIC_ERRORS

logger = logging.getLogger(__name__)


def register(cli: click.Group) -> None:
    """Register the command with the main CLI group."""

    @cli.command(name="init")
    @click.pass_context
    def init_command(ctx: click.Context) -> None:
        """Create the configured Elasticsearch index if it does not exist."""

        service = get_service(ctx)
        try:
            service.ensure_index()
            click.echo("Index initialised successfully.")
        except ELASTIC_ERRORS as exc:
            logger.exception("Failed to initialise index")
            raise click.ClickException("Failed to initialise the index.") from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error during index initialisation")
            raise click.ClickException("An unexpected error occurred.") from exc
