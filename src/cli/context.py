"""Shared CLI context helpers to avoid circular imports."""
from __future__ import annotations

import click
from src.core.config import AppConfig
from src.services.elasticsearch_service import ElasticsearchService


def get_app_config(ctx: click.Context) -> AppConfig:
    """Retrieve AppConfig from the Click context."""
    return ctx.ensure_object(dict)["config"]


def get_service(ctx: click.Context) -> ElasticsearchService:
    """Retrieve ElasticsearchService from the Click context."""
    return ctx.ensure_object(dict)["service"]
