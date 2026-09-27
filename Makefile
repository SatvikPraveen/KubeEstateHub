# KubeEstateHub developer entry point. `make help` lists targets.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

PYTHON   ?= python3
VENV     ?= .venv
BIN      := $(CURDIR)/bin
PY       := $(VENV)/bin/python
K8S_VERSION ?= 1.31.0
OVERLAYS := development staging production
SERVICES := listings-api analytics-worker metrics-service frontend-dashboard realestate-sync-operator
REGISTRY ?= ghcr.io/satvikpraveen/kubeestatehub
TAG      ?= $(shell git rev-parse --short HEAD)

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- Python
$(PY):
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt

.PHONY: install
install: $(PY) ## Create .venv with runtime + dev dependencies

.PHONY: lint
lint: $(PY) ## Ruff lint + format check, yamllint
	$(VENV)/bin/ruff check src tests scripts
	$(VENV)/bin/ruff format --check src tests scripts
	$(VENV)/bin/yamllint -s .

.PHONY: fmt
fmt: $(PY) ## Auto-format Python
	$(VENV)/bin/ruff check --fix src tests scripts
	$(VENV)/bin/ruff format src tests scripts

.PHONY: test
test: $(PY) ## Unit tests with coverage
	$(PY) -m pytest --cov --cov-report=term-missing:skip-covered --cov-report=xml

.PHONY: test-integration
test-integration: $(PY) ## Integration tests (needs DATABASE_URL; the schema is recreated)
	$(PY) -m pytest -m integration tests/integration

.PHONY: benchmark
benchmark: $(PY) ## Monte Carlo validation study (writes docs/research/results-table.md)
	PYTHONPATH=src/analytics-worker $(PY) -m analytics_worker benchmark --replications 50 --format markdown \
	  | tee docs/research/results-table.md

# ---------------------------------------------------------------- Kubernetes
$(BIN)/kubeconform:
	hack/install-tools.sh $(BIN)

.PHONY: tools
tools: $(BIN)/kubeconform ## Install pinned helm, kubeconform, conftest, kube-linter, kind into ./bin

.PHONY: generate
generate: ## Regenerate derived manifests (DB migrations ConfigMap, Grafana dashboards)
	$(PYTHON) hack/generate.py

.PHONY: verify-generated
verify-generated: generate ## Fail if generated files are out of date
	git diff --exit-code -- manifests helm-charts

.PHONY: validate
validate: tools ## Render every overlay and the chart; kubeconform, kube-linter, conftest, promtool
	hack/validate.sh

.PHONY: kind-up
kind-up: tools ## Create a local kind cluster and deploy the development overlay
	hack/kind-e2e.sh up

.PHONY: kind-e2e
kind-e2e: tools ## Full cluster e2e: kind, build/load images, deploy, smoke test, teardown
	hack/kind-e2e.sh all

# ---------------------------------------------------------------- Containers
.PHONY: images
images: ## Build all service images tagged $(REGISTRY)/<service>:$(TAG)
	@for s in $(SERVICES); do \
	  docker build --build-arg CODE_VERSION=$(TAG) -t $(REGISTRY)/$$s:$(TAG) src/$$s || exit 1; \
	done

.PHONY: up
up: ## Run the full stack locally with docker compose (dashboard on :3000)
	docker compose up -d --build --wait postgres redis listings-api metrics-service frontend
	docker compose up seed pipeline

.PHONY: down
down: ## Stop the local stack and delete its volume
	docker compose down -v --remove-orphans

.PHONY: e2e
e2e: ## End-to-end smoke test against a fresh compose stack
	scripts/e2e-compose.sh

.PHONY: load-test
load-test: ## k6 load test against BASE_URL (default: local compose stack)
	docker run --rm -i --network host -e BASE_URL=$${BASE_URL:-http://127.0.0.1:3000} \
	  -v $(CURDIR)/tests/load:/scripts grafana/k6:0.54.0 run /scripts/listings-api.js

.PHONY: clean
clean: ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .hypothesis coverage.xml reports
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
