# Runtime Observer

Runtime Observer is a lightweight telemetry contract, Python SDK, and local collector dashboard for understanding application runtime behavior: routes, traces, logs, exceptions, dependency calls, and LLM usage.

## Repository layout

- `python-sdk/` — importable `runtime_observer` SDK and instrumentation helpers.
- `collector/` — FastAPI collector and local HTML dashboard backed by SQLite.
- `schemas/` — shared JSON Schema contract plus validated event examples.
- `examples/python-fastapi-minimal/` — minimal FastAPI app instrumented with the SDK.
- `docs/` — integration, architecture, API, deployment, and development notes.

## Quick start

```bash
just init
just test
just run
```

Open the collector dashboard at `http://127.0.0.1:4319/`. `just run` uses live reload and frees port 4319 before starting so repeated local runs are predictable. The first dashboard login creates the admin user; later logins require that username/password. After login, the dashboard opens on project selection; choose a project to inspect its apps, routes, traces, logs, dependencies, and generated SDK API keys.

To install directly from GitHub without cloning:

```bash
python -m pip install \
  'runtime-observer @ git+https://github.com/germanilia/runtime-observer.git#subdirectory=python-sdk'
python -m pip install \
  'runtime-observer-server @ git+https://github.com/germanilia/runtime-observer.git#subdirectory=collector'
```

The same URLs work with `uv pip install`. For browser apps, install the lightweight helper directly from GitHub:

```bash
npm install github:germanilia/runtime-observer
```

See [`docs/integration.md`](docs/integration.md) for full setup and examples.

## Configuration

Copy `.env.example` to `.env` and replace placeholder secrets for non-local use.

Important settings:

- `RUNTIME_OBSERVER_SECRETS` — path to `secrets.yml`; the SQLite connection string lives there.
- `RUNTIME_OBSERVER_ENDPOINT` — SDK collector base URL, for example `http://127.0.0.1:4319`.
- `RUNTIME_OBSERVER_PROJECT_NAME` — project shown on the post-login project selection screen.
- `RUNTIME_OBSERVER_SERVICE_NAME` — app/service name inside the project.
- `RUNTIME_OBSERVER_API_KEY` — project SDK key generated in the dashboard and stored hashed in the DB.
- `RUNTIME_OBSERVER_INSECURE_DEV` — disables auth only for local development.

## Documentation

- [`docs/integration.md`](docs/integration.md) — GitHub installation, collector setup, FastAPI/logging/dependency/browser ingestion, dashboard usage, preferences, and troubleshooting.
- [`docs/api.md`](docs/api.md) — ingestion, dashboard, query, and agent tool APIs.
- [`docs/deployment.md`](docs/deployment.md) — local process, Docker Compose, and security checklist.

## Commands

- `just init` — install editable packages and configure hooks.
- `just test` — run SDK, collector, and schema tests.
- `just test-smoke` — validation run used by the pre-push hook.
- `just run` — run the local collector with live reload on port 4319, killing any existing listener on that port first.
- `just run-collector` — alias for `just run`.
- `just run-example` — run the minimal FastAPI example.
- `just setup-hooks` — configure `.githooks/pre-push`.

## Git hooks

After cloning, run:

```bash
just setup-hooks
```

The pre-push hook runs smoke tests, generates `.git/git-reports/pre-push-latest.html`, and asks Claude to review blockers and update docs when needed. If docs are changed by the hook, review and commit them before pushing again.
