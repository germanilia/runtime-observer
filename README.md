# Runtime Observer

Runtime Observer is a lightweight telemetry contract, Python SDK, and local collector dashboard for understanding application runtime behavior: routes, traces, logs, exceptions, dependency calls, and LLM usage.

## Repository layout

- `python-sdk/` — importable `runtime_observer` SDK and instrumentation helpers.
- `collector/` — FastAPI collector and local HTML dashboard backed by SQLite.
- `schemas/` — shared JSON Schema contract plus validated event examples.
- `examples/python-fastapi-minimal/` — minimal FastAPI app instrumented with the SDK.
- `docs/` — architecture, API, deployment, and development notes.

## Quick start

```bash
just init
just test
just run-collector
```

Open the collector dashboard at `http://127.0.0.1:4319/`.

## Configuration

Copy `.env.example` to `.env` and replace placeholder secrets for non-local use.

Important settings:

- `RUNTIME_OBSERVER_API_KEY` — bearer token expected by `/v1/ingest`.
- `RUNTIME_OBSERVER_DASHBOARD_USERNAME` / `RUNTIME_OBSERVER_DASHBOARD_PASSWORD` — basic auth for the dashboard.
- `RUNTIME_OBSERVER_DB` — SQLite path used by the collector.
- `RUNTIME_OBSERVER_INSECURE_DEV` — disables auth only for local development.

## Commands

- `just init` — install editable packages and configure hooks.
- `just test` — run SDK, collector, and schema tests.
- `just test-smoke` — validation run used by the pre-push hook.
- `just run-collector` — run the local collector on port 4319.
- `just run-example` — run the minimal FastAPI example.
- `just setup-hooks` — configure `.githooks/pre-push`.

## Git hooks

After cloning, run:

```bash
just setup-hooks
```

The pre-push hook runs smoke tests, generates `.git/git-reports/pre-push-latest.html`, and asks Claude to review blockers and update docs when needed. If docs are changed by the hook, review and commit them before pushing again.
