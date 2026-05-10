# Architecture

Runtime Observer has three main layers:

1. **SDK** — application-side instrumentation builds redacted telemetry events and exports them to a collector.
2. **Collector** — FastAPI service validates, stores, aggregates, and exposes runtime data.
3. **Schema contract** — JSON Schema and examples keep SDKs and collectors aligned.

## Data flow

```text
Instrumented app → runtime_observer SDK → /v1/ingest → collector store → SQLite → dashboard/API/agent context endpoints
```

## SDK responsibilities

- Resolve runtime configuration from explicit overrides and environment variables.
- Propagate trace/span context across async and framework boundaries.
- Capture route, span, log, exception, dependency, and LLM events.
- Redact secrets and summarize high-risk payloads before export.
- Queue and export events without blocking the application hot path.

## Collector responsibilities

- Enforce API-key authentication for ingestion and basic auth for dashboard/API routes unless insecure dev mode is enabled.
- Store raw redacted events plus query-optimized aggregates in SQLite.
- Provide dashboard APIs for apps, routes, traces, logs, exceptions, dependencies, and agent context.
- Apply retention cleanup during startup.

## Persistence

The collector uses SQLite for local development and lightweight deployments. Runtime database files are intentionally ignored by git.
