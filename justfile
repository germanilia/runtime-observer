# Runtime Observer monorepo commands

# Default: list available commands
default:
    @just --list

# Configure project-local git hooks
setup-hooks:
    git config core.hooksPath .githooks
    chmod +x .githooks/pre-push
    @echo "Git hooks configured."
    @echo "Pre-push will run smoke tests, write .git/git-reports/pre-push-latest.html, and stop if Claude finds blockers or documentation changes to review."

# Install editable local packages and test dependencies
init:
    @echo "Installing Python SDK..."
    cd python-sdk && uv pip install --system -e . pytest fastapi httpx
    @echo "Installing collector..."
    cd collector && uv pip install --system -e . pytest
    @echo "Configuring git hooks..."
    just setup-hooks
    @echo "Runtime Observer initialized."

# Run the collector locally
run-collector PORT="4319":
    cd collector && uv run runtime-observer-server --port {{ PORT }} --insecure-dev

# Run all tests

test:
    just test-python-sdk
    just test-collector
    just test-schemas

# Smoke test target used by the pre-push hook
test-smoke:
    just test

# Python SDK tests
test-python-sdk:
    cd python-sdk && uv run --with pytest --with fastapi --with httpx python -m pytest tests -q

# Collector API tests
test-collector:
    cd collector && uv run --with pytest --with httpx python -m pytest tests -q

# Schema/example validation tests
test-schemas:
    cd schemas && python3 -m unittest discover -s tests -q

# Compile importable Python packages
compile:
    cd python-sdk && uv run python -m compileall runtime_observer
    cd collector && uv run python -m compileall runtime_observer_server

# Lint placeholder: compile and tests are the current validation gates
lint:
    just compile

# Run the minimal FastAPI example after starting the collector
run-example PORT="8000":
    cd examples/python-fastapi-minimal && uv run uvicorn app.main:app --reload --port {{ PORT }}
