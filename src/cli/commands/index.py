"""CLI command for indexing documents from the filesystem."""
from __future__ import annotations

import logging
from pathlib import Path

import click
from src.cli.context import get_app_config, get_service
from src.cli.utils import ELASTIC_ERRORS
from src.services.file_indexer import collect_documents

logger = logging.getLogger(__name__)


def register(cli: click.Group) -> None:
    """Register the command with the main CLI group."""

    @cli.command(name="index")
    @click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
    @click.pass_context
    def index_command(ctx: click.Context, directory: Path) -> None:
        """Index supported documents under ``DIRECTORY``."""

        config = get_app_config(ctx)
        if not config.elasticsearch.has_credentials():
            raise click.ClickException(
                "Authentication is required to index documents. Configure "
                "ELASTIC_USERNAME/ELASTIC_PASSWORD, ELASTIC_API_KEY, or "
                "ELASTIC_BEARER_TOKEN."
            )

        service = get_service(ctx)
        try:
            documents, skipped = collect_documents(directory)
            indexed = service.index_documents(documents)
        except ELASTIC_ERRORS as exc:
            logger.exception("Failed to index documents")
            raise click.ClickException("Elasticsearch indexing failed.") from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error during indexing")
            raise click.ClickException("An unexpected error occurred during indexing.") from exc

        click.echo(f"Indexing complete. Indexed: {indexed}, Skipped: {skipped}.")
