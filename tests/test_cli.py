"""CLI behaviour tests."""
from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from src.cli.main import cli
from src.core.config import AppConfig, ElasticsearchSettings
from src.services.elasticsearch_service import Document


def _auth_config() -> AppConfig:
    return AppConfig(elasticsearch=ElasticsearchSettings(api_key="test"))


def _runner() -> CliRunner:
    return CliRunner()


def test_init_command_success() -> None:
    runner = _runner()
    service = MagicMock()

    with patch("src.cli.main.load_config", return_value=_auth_config()), patch(
        "src.cli.main.ElasticsearchService", return_value=service
    ):
        result = runner.invoke(cli, ["init"])

    assert result.exit_code == 0
    service.ensure_index.assert_called_once()


def test_index_command_outputs_summary(tmp_path) -> None:
    runner = _runner()
    service = MagicMock()
    service.index_documents.return_value = 2

    with patch("src.cli.main.load_config", return_value=_auth_config()), patch(
        "src.cli.main.ElasticsearchService", return_value=service
    ), patch(
        "src.services.file_indexer.collect_documents",
        return_value=([MagicMock()], 1),
    ):
        result = runner.invoke(cli, ["index", str(tmp_path)])

    assert result.exit_code == 0
    assert "Indexed" in result.output
    service.index_documents.assert_called_once()


def test_search_command_displays_results() -> None:
    runner = _runner()
    service = MagicMock()
    service.search.return_value = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {"_score": 1.23, "_source": {"path": "/tmp/file.txt"}},
            ],
        }
    }

    with patch("src.cli.main.load_config", return_value=_auth_config()), patch(
        "src.cli.main.ElasticsearchService", return_value=service
    ):
        result = runner.invoke(cli, ["search", "test"])

    assert result.exit_code == 0
    assert "Total hits: 1" in result.output
    assert "/tmp/file.txt" in result.output


def test_search_command_json_output() -> None:
    runner = _runner()
    service = MagicMock()
    response = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                {"_score": 1.0, "_source": {"path": "/tmp/one.txt"}},
                {"_score": 0.5, "_source": {"path": "/tmp/two.txt"}},
            ],
        }
    }
    service.search.return_value = response

    with patch("src.cli.main.load_config", return_value=_auth_config()), patch(
        "src.cli.main.ElasticsearchService", return_value=service
    ):
        result = runner.invoke(cli, ["search", "test", "--output", "json"])

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["hits"]["total"]["value"] == 2


def test_stats_command_handles_error() -> None:
    runner = _runner()
    service = MagicMock()
    service.stats.side_effect = Exception("boom")

    with patch("src.cli.main.load_config", return_value=_auth_config()), patch(
        "src.cli.main.ElasticsearchService", return_value=service
    ):
        result = runner.invoke(cli, ["stats"])

    assert result.exit_code != 0
    assert "error occurred" in result.output


def test_stats_command_exports_json(tmp_path) -> None:
    runner = _runner()
    service = MagicMock()
    service.stats.return_value = {
        "documents": 5,
        "index_size_in_bytes": 1024,
        "average_query_time_ms": 2.5,
    }
    export_path = tmp_path / "stats.json"

    with patch("src.cli.main.load_config", return_value=_auth_config()), patch(
        "src.cli.main.ElasticsearchService", return_value=service
    ):
        result = runner.invoke(
            cli,
            ["stats", "--output", "json", "--export", str(export_path)],
        )

    assert result.exit_code == 0
    exported = json.loads(export_path.read_text())
    assert exported["documents"] == 5


def test_update_command_applies_changes(tmp_path) -> None:
    runner = _runner()
    service = MagicMock()
    document_path = str((tmp_path / "file.txt").resolve())
    document = Document(
        path=document_path,
        content="Hello",
        size=5,
        last_modified="2024-01-01T00:00:00",
        doc_id=document_path,
    )
    service.existing_documents.return_value = {
        document_path: {"id": "existing-id", "lastModified": "2023-01-01T00:00:00"},
        str((tmp_path / "old.txt").resolve()): {
            "id": "old-id",
            "lastModified": "2023-01-01T00:00:00",
        },
    }
    service.index_documents.return_value = 1
    service.delete_documents.return_value = 1

    with ExitStack() as stack:
        stack.enter_context(
            patch("src.cli.main.load_config", return_value=_auth_config())
        )
        stack.enter_context(
            patch("src.cli.main.ElasticsearchService", return_value=service)
        )
        stack.enter_context(
            patch(
                "src.cli.commands.update.collect_documents",
                return_value=([document], 0),
            )
        )
        result = runner.invoke(cli, ["update", str(tmp_path)])

    assert result.exit_code == 0
    indexed_docs = service.index_documents.call_args[0][0]
    assert indexed_docs[0].doc_id == "existing-id"
    service.delete_documents.assert_called_once_with(["old-id"])
    assert "Update complete" in result.output


def test_index_requires_authentication(tmp_path) -> None:
    runner = _runner()

    config = AppConfig()
    with patch("src.cli.main.load_config", return_value=config), patch(
        "src.cli.main.ElasticsearchService"
    ):
        result = runner.invoke(cli, ["index", str(tmp_path)])

    assert result.exit_code != 0
    assert "Authentication is required" in result.output


def test_analyze_command_outputs_tokens() -> None:
    runner = _runner()
    service = MagicMock()
    service.analyze_text.return_value = {
        "tokens": [
            {"token": "example", "position": 0, "start_offset": 0, "end_offset": 7}
        ]
    }

    with ExitStack() as stack:
        stack.enter_context(
            patch("src.cli.main.load_config", return_value=_auth_config())
        )
        stack.enter_context(
            patch("src.cli.main.ElasticsearchService", return_value=service)
        )
        result = runner.invoke(cli, ["analyze", "Example text"])

    assert result.exit_code == 0
    assert "example" in result.output
    service.analyze_text.assert_called_once()
