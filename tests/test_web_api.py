"""Tests for the FastAPI web application."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.core.config import AppConfig, ElasticsearchSettings
from src.services.elasticsearch_service import Document
from src.web.app import create_app


class DummyService:
    """Test double implementing the Elasticsearch service interface."""

    def __init__(self) -> None:
        self.indexed_documents: list[Document] = []
        self.ensure_index_calls = 0
        self.search_invocations: list[tuple[str, int]] = []

    def ensure_index(self) -> None:
        self.ensure_index_calls += 1

    def index_documents(self, documents: list[Document]) -> int:
        self.indexed_documents.extend(documents)
        return len(documents)

    def search(self, query: str, top: int):
        self.search_invocations.append((query, top))
        return {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {"_source": {"path": "sample.txt"}, "_score": 1.23},
                ],
            }
        }

    def count_documents(self) -> int:
        return 4

    def stats(self) -> dict[str, int | str]:
        return {
            "documents": 4,
            "status": "green",
            "search_query_total": 10,
            "search_query_time_in_millis": 42,
            "uptime_millis": 1000,
        }

    def close(self) -> None:  # pragma: no cover - no action needed for dummy service
        return None


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    token = base64.b64encode(b"elastic:changeme").decode("ascii")
    return {"Authorization": f"Basic {token}"}


@pytest.fixture()
def api_client() -> tuple[TestClient, DummyService]:
    service = DummyService()
    config = AppConfig(elasticsearch=ElasticsearchSettings(username="elastic", password="changeme"))
    app = create_app(config=config, service=service)
    client = TestClient(app)
    return client, service


def test_requires_authentication(api_client: tuple[TestClient, DummyService]) -> None:
    client, _ = api_client
    response = client.get("/stats")
    assert response.status_code == 401


def test_search_endpoint(api_client: tuple[TestClient, DummyService], auth_headers: dict[str, str]) -> None:
    client, service = api_client
    response = client.get("/search", params={"query": "test", "top": 5}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["path"] == "sample.txt"
    assert service.search_invocations == [("test", 5)]


def test_index_folder(api_client: tuple[TestClient, DummyService], auth_headers: dict[str, str], tmp_path: Path) -> None:
    client, service = api_client
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "example.txt").write_text("hello", encoding="utf-8")

    response = client.post("/index", data={"folder": str(docs_dir)}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["indexed"] == 1
    assert service.ensure_index_calls == 1
    assert service.indexed_documents


def test_index_file_upload(api_client: tuple[TestClient, DummyService], auth_headers: dict[str, str]) -> None:
    client, service = api_client
    response = client.post(
        "/index",
        headers=auth_headers,
        files={"file": ("upload.txt", b"some content", "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["indexed"] == 1
    assert service.indexed_documents[-1].path == "upload.txt"
    assert service.indexed_documents[-1].content.strip() == "some content"


def test_stats_endpoint(api_client: tuple[TestClient, DummyService], auth_headers: dict[str, str]) -> None:
    client, _ = api_client
    response = client.get("/stats", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == 4
    assert body["status"] == "green"
