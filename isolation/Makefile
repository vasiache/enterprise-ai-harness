.PHONY: help up down clean test lint fmt deploy-tenant destroy-tenant

TENANT ?= alpha
CLUSTER ?= multitenant-agent-k8s

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'


up: ## Spin up Kind cluster + platform stack (kagent + Supabase + Vault + Argo)
	scripts/setup-kind.sh

down: ## Tear down Kind cluster (registry сохраняется - образы не пересобираются при up)
	kind delete cluster --name $(CLUSTER) || true

clean: ## Full teardown: Kind cluster + registry (следующий up пересоберёт все образы)
	kind delete cluster --name $(CLUSTER) || true
	docker rm -f kind-registry 2>/dev/null || true


lint: ## Run ruff linter
	uv run ruff check .

fmt: ## Auto-format with ruff
	uv run ruff format .

test: ## Run all tests
	uv run pytest

test-one: ## Run a single test: make test-one T=tests/path/test_file.py::test_name
	uv run pytest $(T) -v


deploy-tenant: ## Deploy a tenant: make deploy-tenant TENANT=alpha
	uv run python scripts/admin/tenant.py deploy --tenant $(TENANT)

destroy-tenant: ## Remove a tenant: make destroy-tenant TENANT=alpha
	uv run python scripts/admin/tenant.py undeploy --tenant $(TENANT)
