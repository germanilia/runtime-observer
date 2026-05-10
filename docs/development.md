# Development

## Setup

```bash
just init
just setup-hooks
```

## Validation

```bash
just test
just compile
```

Test recipes dynamically choose an available Runtime Observer port, so multiple test runs can execute side by side without colliding with a local `just run` process.

The root `justfile` delegates to each project area:

- `python-sdk/` tests validate SDK config, redaction, context propagation, and instrumentation.
- `collector/` tests validate ingestion, auth, dashboard APIs, redaction, and clearing data.
- `schemas/` tests validate every checked-in example against the schema and secret rules.

## Running locally

```bash
just run
```

`just run` starts the collector dashboard with uvicorn live reload at `http://127.0.0.1:4319/`. It kills any existing process listening on port 4319 before starting. Use `just run <port>` to request a different fixed development port.

## Runtime artifacts

Generated caches, SQLite databases, logs, virtual environments, and local `.env` files are ignored by `.gitignore` and must not be committed.

## Hooks

The repository uses `.githooks/pre-push`. Run `just setup-hooks` after cloning. The hook runs `just test-smoke`, writes a visual git report to `.git/git-reports/pre-push-latest.html`, and asks Claude to review blockers and update docs when necessary.
