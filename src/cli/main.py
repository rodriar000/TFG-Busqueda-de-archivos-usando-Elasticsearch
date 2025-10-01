"""Entry point for the file search CLI with plugin support."""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Callable

import click
from rich.console import Console
from rich.table import Table

from src.core.config import load_config
from src.core.logging_config import configure_logging
from src.services.elasticsearch_service import ElasticsearchService

console = Console()
logger = logging.getLogger(__name__)


def _load_plugins(cli_group: click.Group) -> None:
    """Dynamically load CLI command plugins."""
    commands_pkg = importlib.import_module("src.cli.commands")
    for module_info in pkgutil.iter_modules(commands_pkg.__path__):
        module = importlib.import_module(f"{commands_pkg.__name__}.{module_info.name}")
        register: Callable[[click.Group], None] = getattr(module, "register")
        register(cli_group)


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration YAML file.",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None) -> None:
    """File search command line interface."""
    app_config = load_config(config_path=config_path)
    configure_logging(app_config.logging)
    ctx.obj = {
        "config": app_config,
        "service": ElasticsearchService(app_config.elasticsearch),
    }
    logger.debug("CLI initialised with config: %s", app_config)


def render_stats(stats: dict[str, int | str]) -> None:
    """Render statistics in a table."""
    table = Table(title="Elasticsearch Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


def main() -> None:
    """CLI entry point for setuptools scripts."""
    cli()


# Register commands when module is imported
_load_plugins(cli)
