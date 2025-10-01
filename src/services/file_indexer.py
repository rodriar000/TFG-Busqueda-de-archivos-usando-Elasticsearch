"""File indexing utilities."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser

from .elasticsearch_service import Document, ElasticsearchService

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {".txt", ".pdf"}


@dataclass
class IndexingResult:
    """Summary of an indexing operation."""

    indexed: int
    skipped: int


def collect_documents(root: Path) -> Tuple[List[Document], int]:
    """Collect documents from ``root`` and count skipped files."""

    documents: List[Document] = []
    skipped = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.debug("Skipping unsupported file %s", path)
            continue
        try:
            content, metadata = extract_document(path)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to parse %s: %s", path, exc)
            skipped += 1
            continue

        stat = path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
        documents.append(
            Document(
                path=str(path.resolve()),
                content=content,
                size=stat.st_size,
                last_modified=last_modified,
                doc_id=str(path.resolve()),
                name=metadata.get("name"),
                author=metadata.get("author"),
                title=metadata.get("title"),
                date=metadata.get("date"),
                language=metadata.get("language"),
                keywords=metadata.get("keywords"),
            )
        )

    return documents, skipped


def index_path(service: ElasticsearchService, root: Path) -> IndexingResult:
    """Index the supported files under ``root`` using ``service``."""

    documents, skipped = collect_documents(root)
    indexed = service.index_documents(documents)
    return IndexingResult(indexed=indexed, skipped=skipped)


def extract_document(path: Path) -> Tuple[str, Dict[str, object]]:
    """Extract text content and metadata from a supported file."""

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    metadata = {
        "name": path.name,
        "author": None,
        "title": None,
        "date": None,
        "language": None,
        "keywords": None,
    }

    if suffix == ".txt":
        content = path.read_text(encoding="utf-8", errors="ignore")
        metadata["date"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        return content, metadata

    if suffix == ".pdf":
        content = extract_text(str(path))
        metadata.update(extract_pdf_metadata(path))
        return content, metadata

    raise ValueError(f"Unsupported file type: {suffix}")


def extract_pdf_metadata(path: Path) -> Dict[str, object]:
    """Extract metadata from a PDF document using pdfminer."""

    extracted: Dict[str, object] = {
        "author": None,
        "title": None,
        "date": None,
        "language": None,
        "keywords": None,
    }

    try:
        with path.open("rb") as handle:
            parser = PDFParser(handle)
            document = PDFDocument(parser)
            if not document.info:
                return extracted

            for raw_info in document.info:
                for key, value in raw_info.items():
                    name = _decode_pdf_value(key)
                    if not name:
                        continue
                    normalized = name.lower()
                    decoded_value = _decode_pdf_value(value)
                    if normalized == "author" and decoded_value:
                        extracted["author"] = decoded_value
                    elif normalized == "title" and decoded_value:
                        extracted["title"] = decoded_value
                    elif normalized in {"creationdate", "moddate", "date"}:
                        parsed_date = _parse_pdf_date(decoded_value)
                        if parsed_date:
                            extracted["date"] = parsed_date
                    elif normalized in {"lang", "language"} and decoded_value:
                        extracted["language"] = decoded_value
                    elif normalized == "keywords":
                        extracted["keywords"] = _split_keywords(decoded_value)
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("Unable to read PDF metadata from %s: %s", path, exc)

    return extracted


def _decode_pdf_value(value: object) -> str | None:
    """Decode PDF metadata values to strings."""

    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore").strip().strip("/") or None
        except Exception:  # pylint: disable=broad-except
            return None
    if isinstance(value, str):
        return value.strip().strip("/") or None
    return str(value)


def _parse_pdf_date(value: str | None) -> str | None:
    """Parse PDF date strings to ISO format."""

    if not value:
        return None

    cleaned = value.strip()
    if cleaned.startswith("D:"):
        cleaned = cleaned[2:]

    date_formats = [
        "%Y%m%d%H%M%S%z",
        "%Y%m%d%H%M%S",
        "%Y%m%d",
    ]

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(cleaned[: len(fmt)], fmt)
            return parsed.isoformat()
        except ValueError:
            continue

    return None


def _split_keywords(value: str | None) -> List[str] | None:
    """Split keyword metadata values into a list."""

    if not value:
        return None

    parts = [
        item.strip()
        for item in re.split(r"[,;]", value)
        if item.strip()
    ]

    return parts or None
