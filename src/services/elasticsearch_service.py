"""Elasticsearch integration layer."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from elasticsearch import Elasticsearch, exceptions as es_exceptions
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import ElasticsearchSettings

logger = logging.getLogger(__name__)

CONTENT_ANALYZER = "content_analyzer"


@dataclass
class Document:
    """Representation of a document to be indexed."""

    path: str
    content: str
    size: int
    last_modified: str
    doc_id: Optional[str] = None
    name: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    language: Optional[str] = None
    keywords: Optional[List[str]] = None

    def to_source(self) -> Dict[str, Any]:
        """Return the Elasticsearch document body, excluding empty values."""

        source: Dict[str, Any] = {
            "path": self.path,
            "content": self.content,
            "size": self.size,
            "lastModified": self.last_modified,
        }

        optional_fields = {
            "name": self.name,
            "author": self.author,
            "title": self.title,
            "date": self.date,
            "language": self.language,
            "keywords": self.keywords,
        }

        for field, value in optional_fields.items():
            if value is None:
                continue
            source[field] = value

        return source


class ElasticsearchService:
    """Service wrapper for Elasticsearch operations with retries."""

    def __init__(self, settings: ElasticsearchSettings) -> None:
        self._settings = settings
        self._client: Optional[Elasticsearch] = None

    @property
    def client(self) -> Elasticsearch:
        """Lazily construct an Elasticsearch client."""

        if self._client is None:
            auth_kwargs = self._settings.auth_kwargs()
            self._client = Elasticsearch(self._settings.url(), **auth_kwargs)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def ensure_index(self) -> None:
        """Ensure the configured index exists."""

        index = self._settings.index
        if self.client.indices.exists(index=index):
            logger.info("Index '%s' already exists", index)
            return

        logger.info("Creating index '%s'", index)
        self.client.indices.create(
            index=index,
            settings={
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "filter": {
                        "content_stop": {"type": "stop", "stopwords": "_english_"},
                        "content_stemmer": {"type": "snowball", "language": "English"},
                    },
                    "analyzer": {
                        CONTENT_ANALYZER: {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "content_stop",
                                "content_stemmer",
                            ],
                        }
                    },
                },
            },
            mappings={
                "properties": {
                    "path": {"type": "keyword"},
                    "content": {
                        "type": "text",
                        "analyzer": CONTENT_ANALYZER,
                        "search_analyzer": CONTENT_ANALYZER,
                    },
                    "size": {"type": "long"},
                    "lastModified": {"type": "date"},
                    "name": {"type": "keyword"},
                    "author": {"type": "keyword"},
                    "title": {"type": "text"},
                    "date": {"type": "date", "ignore_malformed": True},
                    "language": {"type": "keyword"},
                    "keywords": {"type": "keyword"},
                }
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def index_documents(self, documents: Iterable[Document]) -> int:
        """Bulk index documents into Elasticsearch."""

        from elasticsearch.helpers import bulk  # lazy import

        actions = [
            {
                "_op_type": "index",
                "_index": self._settings.index,
                "_id": doc.doc_id or doc.path,
                "_source": doc.to_source(),
            }
            for doc in documents
        ]

        if not actions:
            logger.info("No documents to index")
            return 0

        logger.info("Indexing %s documents", len(actions))
        success, _ = bulk(self.client, actions, refresh=True)
        logger.info("Indexed %s documents", success)
        return int(success)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def delete_documents(self, document_ids: Iterable[str]) -> int:
        """Delete documents by identifier using the bulk API."""

        ids = list(document_ids)
        if not ids:
            logger.info("No documents to delete")
            return 0

        from elasticsearch.helpers import bulk  # lazy import

        actions = [
            {
                "_op_type": "delete",
                "_index": self._settings.index,
                "_id": doc_id,
            }
            for doc_id in ids
        ]

        logger.info("Deleting %s documents", len(actions))
        success, _ = bulk(self.client, actions, refresh=True)
        logger.info("Deleted %s documents", success)
        return int(success)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def search(self, query: str, top: int) -> Dict[str, Any]:
        """Search for documents using a query string."""

        logger.debug("Executing search for query '%s'", query)
        response = self.client.search(
            index=self._settings.index,
            query={"query_string": {"query": query}},
            size=top,
        )
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def count_documents(self) -> int:
        """Return the number of documents in the index."""

        response = self.client.count(index=self._settings.index)
        return int(response.get("count", 0))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def stats(self) -> Dict[str, Any]:
        """Return aggregated statistics for the index and cluster."""

        index_stats = self.client.indices.stats(index=self._settings.index)
        nodes_stats = self.client.nodes.stats()
        cluster_health = self.client.cluster.health()

        uptime_millis = 0
        for node in nodes_stats.get("nodes", {}).values():
            jvm = node.get("jvm", {})
            uptime_millis = max(uptime_millis, jvm.get("uptime_in_millis", 0))

        primaries = index_stats.get("_all", {}).get("primaries", {})
        search_stats = primaries.get("search", {})
        store_stats = primaries.get("store", {})

        try:
            latest = self.client.search(
                index=self._settings.index,
                query={"match_all": {}},
                sort=[{"lastModified": "desc"}],
                size=1,
                _source=["lastModified"],
            )
            hits = latest.get("hits", {}).get("hits", [])
            last_indexing_date = (
                hits[0].get("_source", {}).get("lastModified") if hits else None
            )
        except es_exceptions.TransportError:
            last_indexing_date = None

        query_total = search_stats.get("query_total", 0) or 0
        query_time = search_stats.get("query_time_in_millis", 0) or 0
        avg_query_time = query_time / query_total if query_total else 0.0

        return {
            "documents": index_stats.get("_all", {})
            .get("total", {})
            .get("docs", {})
            .get("count", 0),
            "index_size_in_bytes": store_stats.get("size_in_bytes", 0),
            "search_query_total": query_total,
            "search_query_time_in_millis": query_time,
            "average_query_time_ms": round(avg_query_time, 2),
            "last_indexing_date": last_indexing_date,
            "uptime_millis": uptime_millis,
            "status": cluster_health.get("status"),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def analyze_text(self, text: str, analyzer: Optional[str] = None) -> Dict[str, Any]:
        """Return token analysis for ``text`` using the configured analyzer."""

        body: Dict[str, Any] = {"text": text}
        body["analyzer"] = analyzer or CONTENT_ANALYZER
        logger.debug("Analyzing text using analyzer '%s'", body["analyzer"])
        return self.client.indices.analyze(index=self._settings.index, body=body)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(es_exceptions.TransportError),
        reraise=True,
    )
    def existing_documents(self) -> Dict[str, Dict[str, Any]]:
        """Return a mapping of document paths to metadata stored in Elasticsearch."""

        from elasticsearch.helpers import scan  # lazy import

        results: Dict[str, Dict[str, Any]] = {}
        for hit in scan(
            self.client,
            index=self._settings.index,
            query={"query": {"match_all": {}}, "_source": ["path", "lastModified"]},
        ):
            source = hit.get("_source", {})
            path = source.get("path")
            if not path:
                continue
            results[path] = {
                "id": hit.get("_id"),
                "lastModified": source.get("lastModified"),
            }

        logger.debug("Fetched metadata for %s documents", len(results))
        return results

    def close(self) -> None:
        """Close the underlying Elasticsearch client."""

        if self._client:
            self._client.close()
            self._client = None
