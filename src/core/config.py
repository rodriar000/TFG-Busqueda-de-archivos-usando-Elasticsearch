"""Application configuration loading utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import os

import yaml
from dotenv import load_dotenv


@dataclass
class LoggingSettings:
    """Configuration for application logging."""

    level: str = "INFO"
    file: str = "logs/file-search-cli.log"
    max_bytes: int = 1_048_576
    backup_count: int = 5


@dataclass
class CLISettings:
    """Configuration for CLI defaults."""

    default_top: int = 10


@dataclass
class ElasticsearchSettings:
    """Settings for the Elasticsearch connection."""

    host: str = "localhost"
    port: int = 9200
    scheme: str = "http"
    index: str = "docs"
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    bearer_token: Optional[str] = None

    def url(self) -> str:
        """Return the base URL for the Elasticsearch instance."""

        return f"{self.scheme}://{self.host}:{self.port}"

    def has_credentials(self) -> bool:
        """Return ``True`` when any authentication credentials are configured."""

        return bool(
            (self.username and self.password)
            or self.api_key
            or self.bearer_token
        )

    def auth_kwargs(self) -> Dict[str, Any]:
        """Return keyword arguments for Elasticsearch client authentication."""

        if self.api_key:
            return {"api_key": self.api_key}
        if self.bearer_token:
            return {"bearer_auth": self.bearer_token}
        if self.username and self.password:
            return {"basic_auth": (self.username, self.password)}
        return {}


@dataclass
class AppConfig:
    """Top-level application configuration."""

    elasticsearch: ElasticsearchSettings = field(default_factory=ElasticsearchSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    cli: CLISettings = field(default_factory=CLISettings)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, giving priority to the override."""

    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path | None = None, env_path: Path | None = None) -> AppConfig:
    """Load application configuration from YAML and environment variables."""

    load_dotenv(dotenv_path=env_path, override=False)

    if config_path is None:
        default_config = Path("config/config.yaml")
        config_path = default_config if default_config.exists() else None

    data: Dict[str, Any] = {}
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

    env_override: Dict[str, Any] = {
        "elasticsearch": {
            "host": os.getenv("ELASTIC_HOST"),
            "port": _try_int(os.getenv("ELASTIC_PORT")),
            "scheme": os.getenv("ELASTIC_SCHEME"),
            "index": os.getenv("ELASTIC_INDEX"),
            "username": os.getenv("ELASTIC_USERNAME"),
            "password": os.getenv("ELASTIC_PASSWORD"),
            "api_key": os.getenv("ELASTIC_API_KEY"),
            "bearer_token": os.getenv("ELASTIC_BEARER_TOKEN"),
        },
        "logging": {
            "level": os.getenv("LOG_LEVEL"),
            "file": os.getenv("LOG_FILE"),
            "max_bytes": _try_int(os.getenv("LOG_MAX_BYTES")),
            "backup_count": _try_int(os.getenv("LOG_BACKUP_COUNT")),
        },
        "cli": {
            "default_top": _try_int(os.getenv("DEFAULT_TOP")),
        },
    }

    merged = _deep_merge(data, _clean_dict(env_override))

    return AppConfig(
        elasticsearch=ElasticsearchSettings(**merged.get("elasticsearch", {})),
        logging=LoggingSettings(**merged.get("logging", {})),
        cli=CLISettings(**merged.get("cli", {})),
    )


def _try_int(value: Optional[str]) -> Optional[int]:
    """Attempt to convert a string value to an integer."""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys with ``None`` values recursively."""

    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            nested = _clean_dict(value)
            if nested:
                cleaned[key] = nested
        elif value is not None:
            cleaned[key] = value
    return cleaned
