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

The root `justfile` delegates to each project area:

- `python-sdk/` tests validate SDK config, redaction, context propagation, and instrumentation.
- `collector/` tests validate ingestion, auth, dashboard APIs, redaction, and clearing data.
- `schemas/` tests validate every checked-in example against the schema and secret rules.

## Runtime artifacts

Generated caches, SQLite databases, logs, virtual environments, and local `.env` files are ignored by `.gitignore` and must not be committed.

## Hooks

The repository uses `.githooks/pre-push`. Run `just setup-hooks` after cloning. The hook runs `just test-smoke`, writes a visual git report to `.git/git-reports/pre-push-latest.html`, and asks Claude to review blockers and update docs when necessary.
