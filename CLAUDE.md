# Runtime Observer

Lightweight telemetry contract, Python SDK, and local collector dashboard for application runtime observation.

## Mandatory workflow

- Keep changes small and focused.
- Run `just test` before committing changes that affect code or schemas.
- Run `just setup-hooks` after cloning so pre-push smoke tests and review hooks are active.
- Do not commit runtime databases, caches, logs, virtual environments, or local secrets.

## Stack

- **SDK**: Python package in `python-sdk/`; browser/Node.js SDK in `js-sdk/` (exported via the repo-root `package.json`, not yet published to npm).
- **Collector**: FastAPI app in `collector/`, SQLite persistence, embedded dashboard HTML.
- **Schemas**: JSON Schema plus example events in `schemas/`.
- **Examples**: minimal FastAPI integration in `examples/python-fastapi-minimal/`.
- **Deployments**: AWS via `scripts/deploy_ec2.sh`; single-container homeserver via `scripts/deploy-homeserver.sh` + `docker-compose.homeserver.yml` (see `deployments/homeserver/`).
- **Task runner**: `just`.

## Architecture

### SDK (`python-sdk/runtime_observer/`)
- `config.py` — environment and override resolution.
- `context.py` — trace/span context propagation.
- `exporter.py` — async event queue and HTTP export.
- `instrumentation/` — FastAPI, requests, httpx, SQLAlchemy, and LiteLLM hooks.
- `redaction.py` — shared redaction and value summarization.
- `schema.py` — event envelope construction.

### Collector (`collector/runtime_observer_server/`)
- `main.py` — FastAPI app factory, auth middleware, CLI entrypoint.
- `api.py` — ingest, dashboard, context, and agent tool endpoints.
- `db.py` — SQLite schema and connection management.
- `store.py` — ingest processing, aggregation, and redaction.
- `config.py` — collector settings from environment.

### Schemas (`schemas/`)
- `runtime_observer_schema.json` is the telemetry contract.
- `examples/*.json` provide one valid example per MVP event kind.
- `tests/` validates examples and rejects obvious secrets.

## Commands

- `just init` — install local editable packages and configure hooks.
- `just run` — start the collector dashboard with live reload, killing any existing listener on the requested port first.
- `just run-collector` — alias for `just run`.
- `just test` — run all validation tests.
- `just test-python-sdk` — run SDK tests.
- `just test-collector` — run collector tests.
- `just test-schemas` — run schema example validation.
- `just test-js-sdk` — run the browser/Node.js SDK tests (`npm test`).
- `just pack-js-sdk` — produce a local JS SDK tarball for installing into another project.
- `just deploy-homeserver` — build the collector image and ship it to the `homeserver` SSH alias (see `docs/deployment.md`).
- `just compile` — compile Python packages.
- `just lint` — current lint gate, delegates to compile.

## Git hooks

At the start of a session, verify hooks with:

```bash
git config core.hooksPath
```

If the output is not `.githooks`, run `just setup-hooks` before pushing. The hook runs smoke tests, creates `.git/git-reports/pre-push-latest.html`, and asks Claude to review blockers and update affected documentation.
