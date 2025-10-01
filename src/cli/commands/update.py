"""CLI command for incremental indexing updates."""
from __future__ import annotations

import logging
from pathlib import Path

import click

from src.cli.context import get_app_config, get_service   # ✅ corregido
from src.cli.utils import ELASTIC_ERRORS
from src.services.file_indexer import collect_documents

logger = logging.getLogger(__name__)


def register(cli: click.Group) -> None:
    """Register the update command."""

    @cli.command(name="update")
    @click.argument(
        "directory", type=click.Path(exists=True, file_okay=False, path_type=Path)
    )
    @click.pass_context
    def update_command(ctx: click.Context, directory: Path) -> None:
        """Synchronise the index with the files under ``DIRECTORY``."""

        config = get_app_config(ctx)
        if not config.elasticsearch.has_credentials():
            raise click.ClickException(
                "Authentication is required to update documents. Configure "
                "ELASTIC_USERNAME/ELASTIC_PASSWORD, ELASTIC_API_KEY, or "
                "ELASTIC_BEARER_TOKEN."
            )

        service = get_service(ctx)

        try:
            documents, skipped = collect_documents(directory)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to scan documents for update")
            raise click.ClickException("Failed to scan documents for update.") from exc

        try:
            existing_docs = service.existing_documents()
        except ELASTIC_ERRORS as exc:
            logger.exception("Failed to fetch existing documents")
            raise click.ClickException(
                "Unable to retrieve existing documents from Elasticsearch."
            ) from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error retrieving existing documents")
            raise click.ClickException(
                "An unexpected error occurred while preparing the update."
            ) from exc

        remaining = dict(existing_docs)
        to_index = []
        added_paths: list[str] = []
        updated_paths: list[str] = []

        for doc in documents:
            existing = remaining.pop(doc.path, None)
            if existing is None:
                to_index.append(doc)
                added_paths.append(doc.path)
                continue

            doc.doc_id = existing.get("id") or doc.doc_id or doc.path
            if (existing.get("lastModified") or "") != doc.last_modified:
                to_index.append(doc)
                updated_paths.append(doc.path)

        delete_ids: list[str] = []
        removed_paths: list[str] = []
        for path_str, metadata in remaining.items():
            doc_id = metadata.get("id")
            if doc_id:
                delete_ids.append(doc_id)
            removed_paths.append(path_str)

        indexed_count = 0
        deleted_count = 0
        try:
            if to_index:
                indexed_count = service.index_documents(to_index)
            if delete_ids:
                deleted_count = service.delete_documents(delete_ids)
        except ELASTIC_ERRORS as exc:
            logger.exception("Incremental update failed")
            raise click.ClickException("Elasticsearch update failed.") from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error during incremental update")
            raise click.ClickException(
                "An unexpected error occurred while updating the index."
            ) from exc

        if not any([added_paths, updated_paths, removed_paths]):
            click.echo("No changes detected. Index is up to date.")
        else:
            click.echo(
                "Update complete. Added: {added}, Updated: {updated}, Deleted: {deleted}, Skipped: {skipped}.".format(
                    added=len(added_paths),
                    updated=len(updated_paths),
                    deleted=deleted_count,
                    skipped=skipped,
                )
            )
