.PHONY: build run test lint index-sample search-sample web

PYTHON ?= python3
IMAGE ?= file-search-cli:latest
MODULE ?= src.cli.main

build: ## Build the CLI Docker image
	docker build -t $(IMAGE) .

run: ## Display CLI help locally
        $(PYTHON) -m $(MODULE) --help

web: ## Launch the FastAPI web server locally
	uvicorn src.web.app:app --reload --host 0.0.0.0 --port 8000

test: ## Run the pytest suite
	pytest

lint: ## Run static analysis with Ruff
	ruff check src tests

index-sample: ## Index the bundled sample documents
	$(PYTHON) -m $(MODULE) index samples/documents

search-sample: ## Execute a sample search query
	$(PYTHON) -m $(MODULE) search "analyzers"
