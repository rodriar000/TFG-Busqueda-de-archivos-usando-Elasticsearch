"""FastAPI application exposing the file search capabilities."""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)

from src.core.config import AppConfig, load_config
from src.core.logging_config import configure_logging
from src.services.elasticsearch_service import Document, ElasticsearchService
from src.services.file_indexer import IndexingResult, extract_document, index_path

logger = logging.getLogger(__name__)


def create_app(
    config: AppConfig | None = None,
    service: ElasticsearchService | None = None,
) -> FastAPI:
    """Create and configure a FastAPI application instance."""

    app_config = config or load_config()
    if not app_config.elasticsearch.has_credentials():
        logger.warning(
            "Authentication credentials are not configured; API requests will be rejected until "
            "credentials are provided."
        )

    configure_logging(app_config.logging)

    es_service = service or ElasticsearchService(app_config.elasticsearch)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            es_service.close()

    application = FastAPI(
        title="File Search API",
        version="1.0.0",
        description="REST API for indexing and searching documents with Elasticsearch.",
        lifespan=lifespan,
    )

    application.state.config = app_config
    application.state.service = es_service

    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
    bearer_scheme = HTTPBearer(auto_error=False)
    basic_scheme = HTTPBasic(auto_error=False)

    def require_auth(
        api_key: str | None = Depends(api_key_header),
        bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        basic: HTTPBasicCredentials | None = Depends(basic_scheme),
    ) -> None:
        """Validate the request using the configured authentication method."""

        settings = app_config.elasticsearch
        if not (
            settings.api_key
            or settings.bearer_token
            or (settings.username and settings.password)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials are not configured",
            )
        if settings.api_key and api_key:
            if secrets.compare_digest(api_key, settings.api_key):
                return
        if settings.bearer_token and bearer:
            if secrets.compare_digest(bearer.credentials, settings.bearer_token):
                return
        if settings.username and settings.password and basic:
            if secrets.compare_digest(basic.username, settings.username) and secrets.compare_digest(
                basic.password, settings.password
            ):
                return

        headers: dict[str, str] = {}
        if settings.username and settings.password:
            headers["WWW-Authenticate"] = "Basic"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized", headers=headers)

    def get_service(request: Request) -> ElasticsearchService:
        return request.app.state.service

    @application.post("/index", status_code=status.HTTP_201_CREATED)
    async def index_endpoint(
        _: None = Depends(require_auth),
        service: ElasticsearchService = Depends(get_service),
        folder: str | None = Form(None),
        file: UploadFile | None = File(None),
    ) -> dict[str, int]:
        """Index documents from an uploaded file or an existing folder."""

        service.ensure_index()

        if folder:
            folder_path = Path(folder).expanduser()
            if not folder_path.exists():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder does not exist")
            if not folder_path.is_dir():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path is not a directory")

            result: IndexingResult = index_path(service, folder_path)
            return {"indexed": result.indexed, "skipped": result.skipped}

        if file is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either a folder path or a file upload",
            )

        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must have a name")

        content_bytes = await file.read()
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {".txt", ".pdf"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

        with NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(content_bytes)
            temp_file.flush()
            content, metadata = extract_document(Path(temp_file.name))

        metadata["name"] = Path(file.filename).name

        document = Document(
            path=file.filename,
            content=content,
            size=len(content_bytes),
            last_modified=datetime.now(UTC).isoformat(),
            doc_id=file.filename,
            name=metadata.get("name"),
            author=metadata.get("author"),
            title=metadata.get("title"),
            date=metadata.get("date"),
            language=metadata.get("language"),
            keywords=metadata.get("keywords"),
        )
        indexed = service.index_documents([document])
        return {"indexed": indexed, "skipped": 0}

    @application.get("/search")
    def search_endpoint(
        _: None = Depends(require_auth),
        service: ElasticsearchService = Depends(get_service),
        query: str = Query(..., min_length=1),
        top: int = Query(10, ge=1, le=100),
    ) -> dict[str, Any]:
        """Search indexed documents using a query string."""

        response = service.search(query, top)
        hits = response.get("hits", {})
        total = _extract_total_hits(hits.get("total"))
        results = [
            {
                "path": hit.get("_source", {}).get("path"),
                "score": hit.get("_score"),
            }
            for hit in hits.get("hits", [])
        ]
        return {"total": total, "results": results}

    @application.get("/stats")
    def stats_endpoint(
        _: None = Depends(require_auth),
        service: ElasticsearchService = Depends(get_service),
    ) -> dict[str, Any]:
        """Return index statistics and cluster health."""

        document_count = service.count_documents()
        stats = dict(service.stats())
        stats["documents"] = document_count
        return stats

    return application


def _extract_total_hits(total: Any) -> int:
    """Normalise the search total hits to an integer."""

    if isinstance(total, dict) and "value" in total:
        return int(total["value"])
    if isinstance(total, (int, float)):
        return int(total)
    return 0


app = create_app()
