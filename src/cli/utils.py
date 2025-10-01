"""Utility helpers for CLI commands."""
from __future__ import annotations

from elasticsearch import exceptions as es_exceptions

ELASTIC_ERRORS = (
    es_exceptions.TransportError,
    es_exceptions.ApiError,
    es_exceptions.SerializationError,
    es_exceptions.ConnectionError,
    es_exceptions.RequestError,
    es_exceptions.NotFoundError,
    es_exceptions.ConflictError,
)
