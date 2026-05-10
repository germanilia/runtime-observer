# API

## Ingestion

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/v1/ingest` | Bearer API key | Accepts `{ "events": [...] }` telemetry batches. |
| `POST` | `/v1/ingest/browser` | Query API key unless insecure dev mode | Browser-friendly ingestion endpoint. |

## Dashboard and query APIs

Dashboard routes require basic auth unless insecure dev mode is enabled.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Embedded Runtime Observer dashboard. |
| `GET` | `/api/apps` | List observed applications. |
| `GET` | `/api/overview` | Global counts, recent logs, routes, errors, and dependencies. |
| `GET` | `/api/apps/{app_id}/overview` | Per-application overview. |
| `GET` | `/api/apps/{app_id}/routes` | Routes seen for an application. |
| `GET` | `/api/apps/{app_id}/routes/{route_id}/traces` | Recent traces for a route. |
| `GET` | `/api/apps/{app_id}/traces/{trace_id}` | Trace detail with events, spans, logs, and exceptions. |
| `GET` | `/api/apps/{app_id}/exceptions` | Exception aggregates for an application. |
| `GET` | `/api/apps/{app_id}/exceptions/{exception_id}` | Exception detail with correlated trace and logs. |
| `GET` | `/api/apps/{app_id}/logs` | Filtered logs for an application. |
| `GET` | `/api/apps/{app_id}/logs/{log_id}` | Single log record. |
| `GET` | `/api/apps/{app_id}/dependencies` | Dependency aggregates. |
| `GET` | `/api/apps/{app_id}/call-graph` | Routes, dependencies, and LLM usage for call-graph rendering. |
| `GET` | `/api/logs` | Global log search across all applications. |
| `GET` | `/api/entrypoints` | All routes across all applications with trace and log counts. |
| `GET` | `/api/routes/{route_id}/requests` | Recent traces and related logs for a route. |
| `GET` | `/api/traces/{trace_id}/map` | Full causal map: spans, events, exact logs, dependencies, nearby background logs. |
| `GET` | `/api/traces/{trace_id}/correlated-logs` | Cross-app trace logs grouped by app/service with `level`, comma-separated `app_ids`, `same_project`, `window_seconds`, and `limit` filters plus exact-vs-nearby correlation metadata. |
| `GET` | `/api/traces/{trace_id}/agent-context` | Markdown context for agent-assisted debugging of a trace. |
| `GET` | `/api/dependencies/{dependency_id}/context` | Dependency samples, error samples, and nearby logs. |
| `GET` | `/api/dependencies/{dependency_id}/agent-context` | Markdown context for agent-assisted debugging of a dependency. |
| `GET` | `/api/logs/{log_id}/agent-context` | Markdown context for agent-assisted debugging of a log entry. |
| `POST` | `/api/admin/clear` | Clear collector data; bearer API key required. |

## Agent tool APIs

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/agent/tools` | Lists available agent tool names. |
| `POST` | `/api/agent/{tool_name}` | Dispatches an agent tool call with JSON body `{ "app_id": "...", ... }`. |

Available tool names: `get_application_map`, `get_route_summary`, `get_trace`, `get_trace_agent_context`, `get_log_agent_context`, `get_dependency_context`, `get_dependency_agent_context`, `get_exception_context`, `get_slowest_routes`, `get_failing_routes`, `get_dependency_map`, `get_llm_usage`, `search_logs`, `search_events`.
