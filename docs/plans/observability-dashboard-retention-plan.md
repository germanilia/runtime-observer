# Runtime Observer Observability, Retention, and Dashboard Upgrade Plan

Generated: 2026-05-11

## Executive summary

This plan addresses the reported trace/debugging usability issues and adds stronger telemetry retention controls, clearer trace causality, a more visual errors dashboard, and sortable/actionable overview tables.

The work should be implemented in small phases because it touches storage schema, ingest semantics, API aggregation, and the embedded dashboard UI.

## Immediate answer: repeated DB queries in the trace

The repeated-looking `SELECT custom_agents_1... WHERE custom_agents_1.id IN (9)` queries are **not a UI rendering bug**. They are separate backend DB calls captured by the SDK in one request trace.

They are different relationship-loading queries for the same agent id:

- `custom_agent_tools -> custom_tools`
- `custom_agent_mcp_servers -> mcp_servers`
- `custom_agent_knowledge_bases -> knowledge_bases`
- `custom_agent_aws_connectors -> connectors`
- `custom_agent_skills -> skills`
- `custom_agent_vault_secrets -> vault_secrets`
- `custom_agent_sub_agents -> custom_agents`
- `custom_agent_teams -> agent_teams`
- `custom_agent_workflows -> workflows`
- `custom_tool_vault_secrets -> vault_secrets`

They happen in a tight sequence during `publish_article` / `newspaper_ingestion_service.ingest`. The trace should present them as **relationship loader fan-out** instead of implying they are identical duplicates.

The actual 500 cause is the final insert:

```text
UniqueViolationError: duplicate key value violates unique constraint "newspaper_articles_slug_key"
Key (slug)=(claude-api-agpl-license-blocking-anthropic-2026-05-10) already exists.
```

Likely app fix: make `upsert_by_slug` atomic with PostgreSQL `INSERT ... ON CONFLICT (slug) DO UPDATE`, or catch the race after `SELECT slug` and update/refetch instead of returning 500.

## Goals

1. Make trace maps easier to read and distinguish repeated calls from different calls.
2. Preserve the last hour of logs regardless of global retention cleanup.
3. Keep logs relevant to errors and interesting traces longer than ordinary logs.
4. Add settings for retention policy: requests, logs, errors, and pinned trace context.
5. Fix dashboard card/dialog layout problems so content has room to breathe.
6. Add a visual error analytics dashboard with clustering by type, route, service, fingerprint, and time.
7. Make overview tables sortable and add operational insight widgets.

## Non-goals for this phase

- Replacing the embedded dashboard with a separate frontend app.
- Full distributed tracing protocol support such as OTLP export/import.
- Rewriting the SDK instrumentation.
- Fixing the source application's `newspaper_articles_slug_key` bug inside this repository.

## Multi-agent work plan

| Agent | Track | Ownership | Deliverables |
|---|---|---|---|
| Agent A | Storage + Retention | Database schema, cleanup policy, retained contexts | New retention schema/settings, safe cleanup, relevant-log pinning |
| Agent B | Trace Semantics + APIs | Trace map APIs, dependency grouping, error analytics | Grouped dependencies, repeated-call explanations, error clusters endpoints |
| Agent C | Dashboard UX | Drawer/cards/tables/widgets | Wider trace drawer, readable tables, sortable tables, expanded cards, visual error page |
| Agent D | QA + Migration | Tests, backwards compatibility, deployment verification | Unit tests, migration tests, seeded examples, deploy checklist |

## Phase 0 — Safety and diagnostics

### Tasks

- Add tests covering current behavior before schema changes.
- Verify SQLite and Postgres compatibility for new tables/indexes.
- Create seed fixtures with:
  - A trace containing many relationship-loader DB calls.
  - A duplicate-slug IntegrityError trace.
  - Logs older than one hour and logs linked to errors.

### Files likely touched

- `collector/tests/`
- `collector/runtime_observer_server/db.py`
- `collector/runtime_observer_server/store.py`
- `collector/runtime_observer_server/api.py`

### Acceptance criteria

- `just test-collector` passes before feature work begins.
- Tests assert that repeated DB calls are stored as separate events.

## Phase 1 — Retention model and settings

### Current state

`CollectorStore.cleanup(retention_days)` deletes old rows from:

- `events`
- `logs`
- `route_durations`
- `dependency_durations`

This is too coarse. It can delete logs that are still useful for investigating retained errors/traces.

### Proposed retention policy

Add project/global settings with safe defaults:

| Setting | Default | Meaning |
|---|---:|---|
| `log_retention_minutes_minimum` | 60 | Always retain at least last hour of logs |
| `request_retention_days` | 7 | Normal request/trace/event retention |
| `error_retention_days` | 30 | Error fingerprint and sample retention |
| `error_context_log_window_minutes` | 10 | Logs around errors to keep/pin |
| `interesting_trace_retention_days` | 14 | Traces manually pinned or marked interesting |
| `max_error_fingerprints` | 1000 | Cap retained error clusters per project |
| `max_requests_per_route` | 5000 | Optional rolling cap to protect storage |

### Schema additions

Add `collector_settings`:

```sql
CREATE TABLE IF NOT EXISTS collector_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT
);
```

Add `retention_pins`:

```sql
CREATE TABLE IF NOT EXISTS retention_pins (
  id TEXT PRIMARY KEY,
  app_id TEXT,
  trace_id TEXT,
  route_id TEXT,
  log_id TEXT,
  exception_id TEXT,
  reason TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

Recommended indexes:

- `idx_logs_trace_time ON logs(trace_id, timestamp)`
- `idx_logs_route_time ON logs(route_id, timestamp)`
- `idx_exceptions_last_seen ON exceptions(app_id, last_seen)`
- `idx_traces_error_time ON traces(app_id, has_error, finished_at)`
- `idx_retention_pins_expiry ON retention_pins(expires_at)`

### Cleanup algorithm

1. Compute `minimum_log_cutoff = now - log_retention_minutes_minimum`.
2. Compute `request_cutoff = now - request_retention_days`.
3. Compute `error_cutoff = now - error_retention_days`.
4. Build protected sets:
   - logs with `timestamp >= minimum_log_cutoff`
   - logs whose `trace_id` belongs to retained error samples
   - logs within `error_context_log_window_minutes` around retained exceptions
   - traces/logs explicitly in `retention_pins` and not expired
5. Delete unprotected normal telemetry past request cutoff.
6. Delete old error fingerprints only after error cutoff and caps are applied.

### Acceptance criteria

- Logs from the last 60 minutes are never deleted by cleanup.
- Error sample traces keep exact and nearby logs according to policy.
- Existing SQLite installations migrate without data loss.
- Postgres startup remains fast and does not run migrations on every request.

## Phase 2 — Trace semantics and dependency grouping

### Current issue

The trace dependency table shows every DB query as a flat row. This makes relationship-loader fan-out look like accidental duplicate UI rows.

### Proposed changes

Add server-side trace summarization in `/api/traces/{trace_id}/map`:

- `dependency_groups`: grouped by `(kind, target, operation family, source function, time bucket)`.
- `relationship_loaders`: detect SQLAlchemy relationship load patterns:
  - `custom_agents_1.id ... WHERE ... IN (...)`
  - many queries within 100 ms with same parent id
  - joins through association tables
- `duplicate_candidates`: exact same fingerprint + parameters repeated N times.
- `slow_gap_markers`: time gaps between dependency calls, e.g. the ~16 s gap before the failing insert in this trace.

### UI explanation labels

For this trace, the map should display:

- “Agent relationship loading fan-out: 9 related-resource queries, total ~104 ms”
- “Article existence check: slug not found at 22:12:01.296”
- “Delayed insert failed 16.0 s later: slug already existed — likely race/concurrent insert or stale pre-check”

### Acceptance criteria

- Users can toggle between `Grouped` and `Raw events`.
- Grouped view shows count, distinct tables, total duration, max duration, and first/last timestamp.
- Raw view remains available for exact debugging.

## Phase 3 — Error analytics dashboard

### New dashboard areas

Add an **Errors** page/tab with:

1. Error cluster list
   - grouped by fingerprint
   - type, route, service, last seen, first seen, count, affected traces
2. Visual clustering widgets
   - errors by type
   - errors by route
   - errors by service/app
   - errors over time heatmap/timeline
3. Error detail panel
   - latest sample trace map
   - exact logs
   - nearby logs
   - top related dependencies
   - copy context for AI
4. Triage controls
   - hide/restore fingerprint
   - mark resolved
   - pin context
   - retention override

### New API endpoints

- `GET /api/errors/summary?window=...`
- `GET /api/errors/clusters?group_by=fingerprint|route|type|service`
- `GET /api/errors/timeline?bucket=minute|hour|day`
- `POST /api/errors/{exception_id}/pin`
- `POST /api/errors/{exception_id}/resolve`

### Acceptance criteria

- Duplicate slug errors cluster together by fingerprint.
- Route-level grouping shows `POST /api/v1/agent/newspaper/articles` as a failing route.
- Error details preserve and surface relevant logs/context.

## Phase 4 — Dashboard layout and readability

### Trace drawer/table improvements

Current issue: the triggered map drawer and dependency table are too narrow. `kind` and `target` columns truncate useful information.

Changes:

- Add drawer modes: normal / wide / full-screen.
- Default trace map drawer to wide or full-screen on desktop.
- Replace dependency details `<pre><table>...</table></pre>` with a styled responsive table wrapper.
- Column sizing:
  - `kind`: 120px
  - `target`: minmax(220px, 25%)
  - `operation/input`: minmax(520px, 1fr)
  - `ms`: 80px
- Add horizontal scroll for long SQL, but allow wrapping for target and route.
- Add copy buttons per dependency row.

### Card fixes

Current issue: cards do not expand enough for text.

Changes:

- Remove fixed/min constraining heights where present.
- Allow `.project-card`, `.error-item`, `.dep-card`, `.trace-item`, `.node`, `.log-item` to expand vertically.
- Use `overflow-wrap:anywhere` for long slugs, route names, and SQL snippets.
- Add `line-clamp` only where there is an explicit expand/collapse affordance.

### Acceptance criteria

- The attached card screenshot no longer truncates key content without an expand path.
- Long error messages and routes wrap cleanly.
- Trace dependency table is readable at 1440px desktop width.

## Phase 5 — Sortable overview tables and insight widgets

### Sortable tables

Add a small table renderer helper in `dashboard.py`:

- sortable columns
- active sort indicator
- stable sort state per table in `localStorage`
- numeric/date/string sort handling
- optional client-side filtering

Tables to convert first:

- Routes / entrypoints
- Recent errors
- Dependencies
- Logs
- Trace dependency details

### New insight widgets

Overview should include:

- Request volume over time
- Error rate over time
- Slowest routes by p95
- Top failing routes
- Log level trend
- Dependency failure/latency chart
- Active time heatmap: requests by hour/day
- “New errors in selected window”
- “No logs for error traces” warning widget

### New API aggregation endpoints

- `GET /api/metrics/timeseries?metric=requests|errors|logs&bucket=minute|hour&window=...`
- `GET /api/routes/summary?sort=p95|errors|requests`
- `GET /api/dependencies/summary?sort=p95|errors|calls`
- `GET /api/activity/heatmap?bucket=hour_of_day`

### Acceptance criteria

- Tables sort without full page reload.
- Widgets respect selected project/app and log window.
- Dashboard still renders with no data.

## Phase 6 — Settings UI

### Settings sections

Add a settings page/drawer:

1. Retention
   - minimum log window
   - request retention days
   - error retention days
   - interesting trace retention days
   - max rows/caps
2. Error triage
   - resolved error visibility
   - default error grouping
3. Dashboard
   - default refresh interval
   - default log window
   - default drawer size

### API endpoints

- `GET /api/settings`
- `PUT /api/settings`

### Validation

- Minimum log retention cannot be below 60 minutes unless explicitly allowed by env/config.
- Max caps must be bounded to avoid accidental unbounded storage.
- Settings changes should record `updated_by` and `updated_at`.

### Acceptance criteria

- Admin can change retention values in UI.
- Settings persist across restarts.
- Invalid values return clear 400 responses.

## Implementation order

1. Backend schema/settings foundation.
2. Safe cleanup logic and tests.
3. Trace map grouped dependency API.
4. Drawer/table/card layout improvements.
5. Error analytics APIs.
6. Errors dashboard UI.
7. Sortable tables and overview widgets.
8. Settings UI.
9. Documentation and deployment smoke test.

## File manifest

| File | Action | Notes |
|---|---|---|
| `collector/runtime_observer_server/db.py` | modify | Add settings/pins schema and indexes, SQLite/Postgres compatible migrations |
| `collector/runtime_observer_server/config.py` | modify | Add retention defaults from env |
| `collector/runtime_observer_server/store.py` | modify | Implement policy-driven cleanup, pin relevant logs around errors |
| `collector/runtime_observer_server/api.py` | modify | Add settings, error analytics, time series, grouped trace map endpoints |
| `collector/runtime_observer_server/dashboard.py` | modify | Add settings UI, visual errors dashboard, sortable tables, wider trace drawer, card fixes |
| `collector/tests/` | modify/add | Retention, grouped traces, settings validation, error analytics tests |
| `docs/deployment.md` | modify | Document retention settings and operational behavior |
| `docs/plans/observability-dashboard-retention-plan.md` | add | This plan |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Retention cleanup accidentally deletes needed investigation data | Implement protected sets and tests with error sample traces/logs |
| SQLite/Postgres behavior diverges | Add tests against SQLite and a lightweight Postgres smoke path where practical |
| Dashboard JS grows harder to maintain | Introduce small helpers for sortable tables and drawer sizing rather than large rewrites |
| More aggregation queries slow the dashboard | Add indexes, bounded limits, and API-side windows |
| Storage grows too much due to pinned logs/errors | Add configurable caps and visible storage indicators |

## Acceptance checklist

- [ ] Last-hour logs are retained after cleanup.
- [ ] Error sample traces keep exact logs and nearby logs.
- [ ] Admin can configure request/error/log retention.
- [ ] Trace map shows grouped dependency calls and raw event toggle.
- [ ] Triggered map drawer can expand wide/fullscreen.
- [ ] Dependency details table has readable `kind`, `target`, and `operation/input` columns.
- [ ] Cards wrap/expand text cleanly.
- [ ] Errors dashboard clusters by fingerprint, type, route, and service.
- [ ] Overview tables are sortable.
- [ ] New widgets show request/error/log/dependency trends.
- [ ] `just test` passes.
