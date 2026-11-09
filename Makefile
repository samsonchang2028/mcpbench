.DEFAULT_GOAL := help
.NOTPARALLEL:

PYTHON ?= python3.14
export GOMAXPROCS := 2
export GOTOOLCHAIN := local
export UV_PYTHON_DOWNLOADS := never
export PYTHONDONTWRITEBYTECODE := 1
export MCPBENCH_TEST_PYTHON ?= $(abspath $(if $(UV_PROJECT_ENVIRONMENT),$(UV_PROJECT_ENVIRONMENT),.venv))/bin/python

.PHONY: help tools setup check check-go check-python lock-check
help:
	@echo "After fresh admission: make setup; make check"
	@echo "Runtime/containers/inference remain gated by docs/TASK_GRAPH.md."

tools:
	@test "$$(go env GOVERSION)" = go1.26.8 || { echo 'Go 1.26.8 required'; exit 1; }
	@test "$$($(PYTHON) -c 'import platform; print(platform.python_version())')" = 3.14.4 || { echo 'Python 3.14.4 required'; exit 1; }
	@test "$$(uv --version | cut -d ' ' -f 2)" = 0.13.4 || { echo 'uv 0.13.4 required'; exit 1; }

# Downloads and compilation require refreshed resource/connectivity admission.
setup: tools
	go mod download
	uv sync --locked --python $(PYTHON) --no-python-downloads --no-build

check: tools lock-check check-go check-python

lock-check:
	uv lock --check --offline --python $(PYTHON)
	go mod verify

# Compile the pinned libraries while runtime packages are still empty boundaries.
check-go:
	go test -mod=readonly -p 1 -tags=dependencies ./...
	go vet -mod=readonly -p 1 -tags=dependencies ./...
	go build -mod=readonly -p 1 -o bin/agent ./cmd/agent
	go build -mod=readonly -p 1 -o bin/billing-mcp ./cmd/billing-mcp

check-python:
	uv run --locked --offline --no-sync python -m unittest contracts.tests.test_contracts eval.fixtures.test_fixtures db.tests.test_offline eval.grading.test_oracle eval.reset.test_contract observability.test_jsonl eval.runner.test_artifacts eval.runner.test_lifecycle
	uv run --locked --offline --no-sync python -m eval.fixtures.validate
