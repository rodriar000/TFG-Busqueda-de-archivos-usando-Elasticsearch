"""Tests for configuration loading."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import AppConfig, load_config


def test_load_config_from_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        """
        elasticsearch:
          host: example.com
          port: 1234
        logging:
          level: DEBUG
        cli:
          default_top: 5
        """,
        encoding="utf-8",
    )

    config = load_config(config_path=yaml_path)
    assert isinstance(config, AppConfig)
    assert config.elasticsearch.host == "example.com"
    assert config.elasticsearch.port == 1234
    assert config.cli.default_top == 5
    assert config.logging.level == "DEBUG"


def test_env_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("elasticsearch:\n  host: example.com\n", encoding="utf-8")

    monkeypatch.setenv("ELASTIC_HOST", "env-host")
    monkeypatch.setenv("ELASTIC_PORT", "9300")
    monkeypatch.setenv("DEFAULT_TOP", "20")

    config = load_config(config_path=yaml_path)
    assert config.elasticsearch.host == "env-host"
    assert config.elasticsearch.port == 9300
    assert config.cli.default_top == 20


def test_api_key_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("ELASTIC_API_KEY", "abc123")

    config = load_config(config_path=yaml_path)
    assert config.elasticsearch.api_key == "abc123"
    assert config.elasticsearch.has_credentials()
