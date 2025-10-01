"""Tests for file indexing metadata extraction."""
from __future__ import annotations

from src.services.file_indexer import collect_documents


def test_collect_documents_includes_metadata(tmp_path) -> None:
    sample = tmp_path / "example.txt"
    sample.write_text("Sample content", encoding="utf-8")

    documents, skipped = collect_documents(tmp_path)

    assert skipped == 0
    assert len(documents) == 1

    document = documents[0]
    assert document.name == "example.txt"
    assert document.doc_id == str(sample.resolve())
    assert document.date is not None
    assert document.language is None
    assert document.keywords is None
