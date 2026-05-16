# Runtime Observer monorepo commands

# Default: list available commands
default:
    @just --list

# Find an available port starting from a preferred port.
[private]
_find-port PREFERRED:
    #!/usr/bin/env bash
    port={{ PREFERRED }}
    while lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; do
        echo "Port $port is busy, trying next..." >&2
        port=$((port + 1))
    done
    echo "$port"

# Kill processes listening on a port. Used by `just run` for a predictable dev port.
[private]
_kill-port PORT:
    #!/usr/bin/env bash
    pids=$(lsof -tiTCP:{{ PORT }} -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Killing process(es) on port {{ PORT }}: $pids"
        kill $pids 2>/dev/null || true
        sleep 1
        remaining=$(lsof -tiTCP:{{ PORT }} -sTCP:LISTEN 2>/dev/null || true)
        if [ -n "$remaining" ]; then
            echo "Force killing process(es) on port {{ PORT }}: $remaining"
            kill -9 $remaining 2>/dev/null || true
        fi
    fi

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

# Run the application locally with live reload (collector dashboard).
# This intentionally frees the requested port first for a predictable dev URL.
run PORT="4319":
    just _kill-port {{ PORT }}
    @echo "Runtime Observer UI:      http://127.0.0.1:{{ PORT }}/"
    @echo "Runtime Observer backend: http://127.0.0.1:{{ PORT }}/v1/ingest"
    @echo "Runtime Observer API docs: http://127.0.0.1:{{ PORT }}/docs"
    cd collector && RUNTIME_OBSERVER_INSECURE_DEV=true uv run uvicorn runtime_observer_server.main:app --reload --host 127.0.0.1 --port {{ PORT }} --no-access-log

# Run the collector locally with live reload
run-collector PORT="4319":
    just run {{ PORT }}

# Start LocalStack SQS for local buffered-ingest development.
localstack-sqs:
    docker compose up localstack

# Run collector through the LocalStack-backed SQS ingest buffer.
run-buffered PORT="4319":
    docker compose up localstack -d
    just _kill-port {{ PORT }}
    cd collector && RUNTIME_OBSERVER_INSECURE_DEV=true RUNTIME_OBSERVER_INGEST_QUEUE_BACKEND=sqs RUNTIME_OBSERVER_SQS_ENDPOINT_URL=http://localhost:4566 RUNTIME_OBSERVER_SQS_QUEUE_URL=http://localhost:4566/000000000000/runtime-observer-ingest AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 uv run uvicorn runtime_observer_server.main:app --reload --host 127.0.0.1 --port {{ PORT }} --no-access-log

# Run all tests. Each test recipe uses dynamically allocated ports so multiple
# test runs can execute side by side without fighting over the dev port.
test:
    just test-python-sdk
    just test-collector
    just test-schemas

# Smoke test target used by the pre-push hook
test-smoke:
    just test

# Python SDK tests
test-python-sdk PREFERRED_PORT="4319":
    #!/usr/bin/env bash
    set -euo pipefail
    TEST_PORT=$(just _find-port {{ PREFERRED_PORT }})
    echo "Using Runtime Observer test port $TEST_PORT for SDK tests"
    cd python-sdk && RUNTIME_OBSERVER_PORT="$TEST_PORT" uv run --with pytest --with fastapi --with httpx python -m pytest tests -q

# Collector API tests
test-collector PREFERRED_PORT="4319":
    #!/usr/bin/env bash
    set -euo pipefail
    TEST_PORT=$(just _find-port {{ PREFERRED_PORT }})
    echo "Using Runtime Observer test port $TEST_PORT for collector tests"
    cd collector && RUNTIME_OBSERVER_PORT="$TEST_PORT" uv run --with pytest --with httpx python -m pytest tests -q

# Schema/example validation tests
test-schemas:
    cd schemas && python3 -m unittest discover -s tests -q

# JavaScript SDK tests
test-js-sdk:
    npm test

# Build a local JavaScript SDK tarball for installing into another project.
# Example in the target app: npm install /path/to/runtime-observer/runtime-observer-0.2.0.tgz
pack-js-sdk:
    npm pack

# Compile importable Python packages
compile:
    cd python-sdk && uv run python -m compileall runtime_observer
    cd collector && uv run python -m compileall runtime_observer_server

# Lint placeholder: compile and tests are the current validation gates
lint:
    just compile

# Deploy Runtime Observer to EC2 behind an ALB. Example: just deploy-ec2 sela
deploy-ec2 ENVIRONMENT="sela":
    ./scripts/deploy_ec2.sh {{ ENVIRONMENT }}

# Deploy Runtime Observer to the homeserver via the `homeserver` SSH alias.
# NPM forwards https://metrics.homeserver to ro-collector:4319.
# Example:
#   just deploy-homeserver
#   just deploy-homeserver --clean-volume   # wipe the SQLite volume first
deploy-homeserver *args:
    @bash scripts/deploy-homeserver.sh {{ args }}

# Run the minimal FastAPI example after starting the collector.
# Uses the requested port if available, otherwise the next free port.
run-example PREFERRED_PORT="8000":
    #!/usr/bin/env bash
    set -euo pipefail
    PORT=$(just _find-port {{ PREFERRED_PORT }})
    echo "Starting example on http://127.0.0.1:$PORT"
    cd examples/python-fastapi-minimal && uv run uvicorn app.main:app --reload --port "$PORT"
