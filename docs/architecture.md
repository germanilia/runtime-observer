# Architecture

Runtime Observer has three main layers:

1. **SDK** — application-side instrumentation builds redacted telemetry events and exports them to a collector.
2. **Collector** — FastAPI service validates, stores, aggregates, and exposes runtime data.
3. **Schema contract** — JSON Schema and examples keep SDKs and collectors aligned.

## Data flow

```text
Instrumented app → runtime_observer SDK → /v1/ingest → ingest buffer (direct, memory, or SQS) → worker batch processor → collector store → SQLite/Postgres → dashboard/API/agent context endpoints
```

## SDK responsibilities

- Resolve runtime configuration from explicit overrides and environment variables.
- Propagate trace/span context across async and framework boundaries.
- Capture route, span, log, exception, dependency, and LLM events.
- Redact secrets and summarize high-risk payloads before export.
- Queue and export events without blocking the application hot path.

## Collector responsibilities

- Enforce project-scoped API-key authentication for ingestion and session-cookie auth for dashboard/API routes unless insecure dev mode is enabled. The first dashboard login bootstraps the admin user; SDK ingest keys are generated per project in the dashboard and stored hashed in the database.
- Store raw redacted events plus query-optimized aggregates in the database.
- Provide dashboard APIs for apps, routes, traces, logs, exceptions, dependencies, errors, metrics, and agent context.
- Buffer ingest traffic before database writes. Local/test deployments can use direct or in-memory mode; Docker/local development can use LocalStack SQS; AWS deployments should use SQS with a DLQ.
- Batch-process telemetry into raw tables plus hourly aggregate tables for route, dependency, and log metrics.
- Apply retention cleanup periodically on a background thread, respecting `collector_settings`-stored retention overrides and `retention_pins`.

## Persistence

The collector supports SQLite (default for local development and lightweight deployments) and PostgreSQL (set `RUNTIME_OBSERVER_DATABASE_URL` to a `postgres://` URL). The schema is applied automatically on startup via `db.py`. Runtime SQLite database files are intentionally ignored by git.

Raw telemetry has short retention: regular non-error logs default to 4 hours, raw events to 24 hours, and durations/traces to a few days. Error logs, exception-linked traces, and nearby exception context are protected longer. Hourly aggregate tables keep long-term route/dependency/log counts without retaining the entire raw history.
