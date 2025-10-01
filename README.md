# File Search CLI

A production-ready, plugin-driven command line interface and web API for indexing and searching local documents with Elasticsearch.

## Features

- Modular architecture with clearly separated core, CLI, and service layers.
- Configuration via YAML, `.env`, or environment variables with support for API key, bearer token, or basic authentication.
- Robust logging with rotating file handlers and retry-aware Elasticsearch interactions.
- Enhanced indexing pipeline with custom analyzers for stop words, lowercasing, stemming, and rich metadata capture using
  pdfminer/Apache Tika compatible extraction.
- Extensible command registration through a plugin mechanism including an analyzer inspection command.
- Incremental update workflow that synchronises filesystem changes (additions, updates, removals) with the Elasticsearch index.
- FastAPI-powered web API with Swagger UI for indexing, searching, and monitoring statistics.
- Dockerfile and Docker Compose definitions for running Elasticsearch together with the CLI and web API containers.
- Automation through a developer-friendly `Makefile`, pytest suites, Ruff linting, and GitHub Actions CI/CD that builds and ships Docker images.

## Quick Start (Docker Compose)

1. Ensure Docker and Docker Compose are installed.
2. Create a `.env` file or export the credentials you plan to use. The provided Compose stack boots Elasticsearch with the default `elastic/changeme` credentials.
3. Launch the stack (CLI, Elasticsearch, and FastAPI web API):

   ```bash
   docker compose up -d
   ```

4. Explore the FastAPI docs at <http://localhost:8000/docs>. Authenticate using the same credentials configured for Elasticsearch (e.g. the default `elastic/changeme` Basic auth).

5. Run CLI commands inside the container (the CLI service sleeps by default so it is ready for exec commands):

   ```bash
   docker compose exec cli python -m src.cli.main --help
   docker compose exec cli python -m src.cli.main init
   docker compose exec cli python -m src.cli.main index samples/documents
   docker compose exec cli python -m src.cli.main search "powerful analyzers"
   docker compose exec cli python -m src.cli.main analyze "Powerful analyzers at work"
   docker compose exec cli python -m src.cli.main update samples/documents
   ```

6. Tear everything down when finished:

   ```bash
   docker compose down -v
   ```

The CLI container mounts the local `config/` directory and sample documents so configuration changes or new content are immediately visible.

## Authentication

Indexing, searching, and analyzer inspection require authentication. Provide credentials via one of the following mechanisms:

- Username and password (`ELASTIC_USERNAME` and `ELASTIC_PASSWORD`).
- API key (`ELASTIC_API_KEY`).
- Bearer token (`ELASTIC_BEARER_TOKEN`).

Values can be defined in `config/config.yaml`, in a `.env` file, or exported directly into the environment. Environment variables take precedence over YAML configuration.

## Web API

### Local development

Run the API locally with auto-reload:

```bash
make web
```

By default the server listens on <http://127.0.0.1:8000>. The OpenAPI/Swagger UI is available at `/docs` and ReDoc at `/redoc`.

### Authentication

All endpoints enforce authentication using the same credentials as the CLI and Elasticsearch integration:

- **Basic auth** — `Authorization: Basic ...` (set `ELASTIC_USERNAME`/`ELASTIC_PASSWORD`).
- **API key** — `X-API-Key: <value>` (`ELASTIC_API_KEY`).
- **Bearer token** — `Authorization: Bearer <token>` (`ELASTIC_BEARER_TOKEN`).

If multiple credential types are configured, any valid option is accepted. Missing credentials will cause requests to be rejected.

### REST endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/index` | `POST` | Index an uploaded `.txt`/`.pdf` file (`multipart/form-data`) or all supported documents in a folder path (`folder` form field). |
| `/search` | `GET` | Query documents via the Elasticsearch query-string syntax (`query` parameter) and control result size with `top`. |
| `/stats` | `GET` | Return aggregated statistics including document count, uptime, and cluster health. |

Example requests (Basic auth):

```bash
curl -u elastic:changeme -X POST "http://localhost:8000/index" \
  -F folder=/app/samples/documents

curl -u elastic:changeme "http://localhost:8000/search?query=analytics&top=5"

curl -u elastic:changeme "http://localhost:8000/stats"
```

## CLI Usage

Invoke the CLI using the module path:

```bash
python -m src.cli.main --help
```

Available commands include:

- `init` – Ensure the Elasticsearch index exists with the desired settings and analyzers.
- `index DIRECTORY` – Recursively index `.txt` and `.pdf` files under `DIRECTORY`.
- `update DIRECTORY` – Perform incremental sync by indexing new/changed files and deleting removed ones.
- `search QUERY [--output text|json]` – Execute query-string searches and display ranked results or raw JSON.
- `stats [--output table|json|csv] [--export PATH]` – Show document counts, index size, performance metrics, and optionally
  export them for evaluation.
- `analyze TEXT` – Display analyzer tokenization details for the provided text.

Example:

```bash
python -m src.cli.main search "machine learning" --top 5 --output json
python -m src.cli.main update samples/documents
python -m src.cli.main stats --output csv --export stats.csv
```

### Document metadata

Each indexed document stores the following fields (when available) to support academic evaluation:

| Field | Description |
| --- | --- |
| `path` | Absolute file path used as a stable identifier. |
| `name` | File name extracted from the filesystem. |
| `author` | Author metadata extracted from PDF headers. |
| `title` | Title metadata extracted from PDF headers. |
| `date` | Creation/modified date from metadata (falls back to filesystem timestamp for text files). |
| `language` | Language metadata reported by the document, when available. |
| `keywords` | Comma or semicolon separated keywords parsed into a list. |
| `content` | Full text content used for search. |
| `size` | File size in bytes. |
| `lastModified` | Filesystem last-modified timestamp used for incremental updates. |

## Developer Guide

### Prerequisites

- Python 3.10+
- Docker (optional but recommended for Elasticsearch)

### Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The `Makefile` streamlines common tasks:

```bash
make run            # Show CLI help
make web            # Run the FastAPI server locally
make index-sample   # Index the bundled sample documents
make search-sample  # Run a sample search
make lint           # Ruff static analysis
make test           # Run pytest
make build          # Build the Docker image locally
```

### Testing & Quality

```bash
make test
make lint
```

### Logging

Logs are written to the file specified in configuration (default `logs/file-search-cli.log`) with rotation to prevent unbounded growth. Adjust log level and rotation policy through configuration.

### Extending the CLI

New commands can be added by creating a module under `src/cli/commands/` that exposes a `register(cli)` function. The CLI automatically discovers and registers these plugins on startup.

## Evaluation

The project aligns with the academic TFG requirements by exposing measurable metrics and exportable reports:

- Run `python -m src.cli.main stats --output json --export stats.json` to capture document counts, index size, average query time,
  and last indexing date as structured JSON.
- Use `--output csv --export metrics.csv` to generate a CSV file suitable for spreadsheet analysis.
- Combine CLI statistics with system-level measurements (e.g. `docker stats` for memory, `du -sh` for disk usage of the volume)
  during experiments to document resource consumption.
- Leverage the incremental `update` command to log added/updated/removed documents while timing executions for performance
  evaluations.

## Continuous Integration & Delivery

GitHub Actions (`.github/workflows/ci.yml`) runs pytest on every push or pull request, then builds and (on non-PR events) publishes a Docker image to the GitHub Container Registry. Tagged releases (`v*`) automatically create GitHub Releases with the same pipeline output.
