# API

## Ingestion

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/v1/ingest` | Bearer API key | Accepts `{ "events": [...] }` telemetry batches from SDKs. Use a project-scoped key generated in the UI and stored hashed in the DB. When a project-scoped key is used, `service.project_name` in every event is overridden to match the key's project regardless of what the SDK sent. |
| `POST` | `/v1/ingest/browser` | `?api_key=...` query key unless insecure dev mode | Browser SDK ingestion endpoint. Node.js SDKs should prefer `/v1/ingest` with `Authorization: Bearer ...`. When a project-scoped key is used, `service.project_name` is overridden to match the key's project. |

The Python SDK and Node.js SDK `RUNTIME_OBSERVER_ENDPOINT` should be the collector base URL, for example `http://127.0.0.1:4319`; SDKs append the appropriate ingest path. Set `RUNTIME_OBSERVER_PROJECT_NAME`, `RUNTIME_OBSERVER_SERVICE_NAME`, and `RUNTIME_OBSERVER_API_KEY` in each application.

Both ingest endpoints respond with `{ "accepted": N, "rejected": N, "queued": bool, "server_time": "..." }`. When `queued` is `true` the events have been placed on the ingest buffer (SQS or memory) and will be written to the database by a background worker; `false` means they were written synchronously. Error responses: `429` queue full, `413` single event exceeds SQS message size limit, `503` ingest backend unavailable.

## Dashboard and query APIs

Dashboard routes require a session cookie unless insecure dev mode is enabled. The first `POST /api/auth/login` creates the admin user when the users table is empty.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/auth/login` | Create first admin or sign in and set a session cookie. |
| `POST` | `/api/auth/logout` | Delete current session cookie. |
| `GET` | `/api/auth/me` | Return current dashboard user. |
| `GET` | `/` | Embedded Runtime Observer dashboard. |
| `GET` | `/api/apps` | List observed applications. |
| `GET` | `/api/projects` | List projects for the post-login project selection screen with app/request/error/key counts and project `created_at` timestamp. |
| `GET` | `/api/projects/{project_name}/api-keys` | List project API key metadata. Full key values are never returned. |
| `POST` | `/api/projects/{project_name}/api-keys` | Generate a new project-scoped SDK API key. The full key is returned once. |
| `DELETE` | `/api/projects/{project_name}/api-keys/{key_id}` | Revoke a project-scoped SDK API key. |
| `DELETE` | `/api/projects/{project_name}` | Delete a project and all its telemetry (apps, events, routes, logs, traces, dependencies, and SDK keys). Requires admin role. |
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
| `GET` | `/api/preferences/hidden` | List hidden preferences for the current user, optionally filtered by `app_id` or `target_kind`. |
| `POST` | `/api/preferences/hidden` | Hide an app, route, dependency, or exception from the current user's views. Body: `{ "target_kind", "target_id", "app_id", "project_name" }`. |
| `DELETE` | `/api/preferences/hidden/{target_kind}/{target_id}` | Restore a hidden item for the current user; optionally scope by `?app_id=`. |
| `GET` | `/api/entrypoints` | All routes across all applications with trace and log counts. Append `?include_hidden=true` to include hidden routes with a `hidden` flag. |
| `GET` | `/api/routes/{route_id}/requests` | Recent traces and related logs for a route. Append `?include_hidden=true` to bypass hidden filter. |
| `GET` | `/api/settings` | Get collector settings (currently: `retention` object with `retention_days`, `min_log_minutes`, `exception_window_minutes`). |
| `PUT` | `/api/settings` | Update collector settings. Body: `{ "retention": { "retention_days": N, "min_log_minutes": N, "exception_window_minutes": N } }`. Persisted in `collector_settings`. |
| `GET` | `/api/errors/summary` | Aggregated error summary: total exception count, cluster count, error log count, broken down by exception type and service. Accepts `project_name`, `app_id`, and `log_window_minutes` query params. |
| `GET` | `/api/errors/clusters` | List exception clusters ordered by occurrence count. Accepts `project_name`, `app_id`, `limit`. |
| `GET` | `/api/errors/timeline` | Time-bucketed exception event counts for charts. Accepts `project_name`, `app_id`, `window_minutes`, `bucket_minutes`. |
| `GET` | `/api/metrics/timeseries` | Time-bucketed request, error, log, and exception counts merged into a single series. Accepts `project_name`, `app_id`, `window_minutes`, `bucket_minutes`. |
| `GET` | `/api/traces/{trace_id}/map` | Full causal map: spans, events, exact logs, dependencies, nearby background logs, a `flow` graph, plus insight fields `dependency_groups`, `relationship_loader_groups`, `slow_gap_markers`, and `duplicate_candidates`. |
| `GET` | `/api/traces/{trace_id}/correlated-logs` | Cross-app trace logs grouped by app/service with `level`, comma-separated `app_ids`, `same_project`, `window_seconds`, and `limit` filters plus exact-vs-nearby correlation metadata. |
| `GET` | `/api/traces/{trace_id}/agent-context` | Markdown context for agent-assisted debugging of a trace. |
| `GET` | `/api/dependencies/{dependency_id}/context` | Dependency samples, error samples, and nearby logs. |
| `GET` | `/api/dependencies/{dependency_id}/agent-context` | Markdown context for agent-assisted debugging of a dependency. |
| `GET` | `/api/logs/{log_id}/agent-context` | Markdown context for agent-assisted debugging of a log entry. |
| `POST` | `/api/admin/clear` | Clear collector telemetry data; session cookie required. |

## Agent tool APIs

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/agent/tools` | Lists available agent tool names. |
| `POST` | `/api/agent/{tool_name}` | Dispatches an agent tool call with JSON body `{ "app_id": "...", ... }`. |

Available tool names: `get_application_map`, `get_route_summary`, `get_trace`, `get_trace_agent_context`, `get_log_agent_context`, `get_dependency_context`, `get_dependency_agent_context`, `get_exception_context`, `get_slowest_routes`, `get_failing_routes`, `get_dependency_map`, `get_llm_usage`, `search_logs`, `search_events`.
