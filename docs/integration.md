# Integration guide

This guide covers installing Runtime Observer from GitHub, running the collector, and instrumenting Python/FastAPI, logging, dependencies, and browser clients.

## Package availability

Runtime Observer is not published to PyPI or npm yet. Install the Python SDK and collector directly from this repository using GitHub `subdirectory` URLs. Browser and Node.js projects install the JavaScript SDK from the repository root. The npm package name is `runtime-observer`, with separate `runtime-observer/browser` and `runtime-observer/node` entrypoints.

## Install from GitHub

Use the repository URL with the package subdirectory.

### pip

```bash
python -m pip install \
  'runtime-observer @ git+https://github.com/germanilia/runtime-observer.git#subdirectory=python-sdk'

python -m pip install \
  'runtime-observer-server @ git+https://github.com/germanilia/runtime-observer.git#subdirectory=collector'
```

For SSH access:

```bash
python -m pip install \
  'runtime-observer @ git+ssh://git@github.com/germanilia/runtime-observer.git#subdirectory=python-sdk'
```

### uv

```bash
uv pip install \
  'runtime-observer @ git+https://github.com/germanilia/runtime-observer.git#subdirectory=python-sdk'

uv pip install \
  'runtime-observer-server @ git+https://github.com/germanilia/runtime-observer.git#subdirectory=collector'
```

Pin a branch, tag, or commit for reproducible installs:

```bash
uv pip install \
  'runtime-observer @ git+https://github.com/germanilia/runtime-observer.git@main#subdirectory=python-sdk'
```

## Collector setup

The collector is a FastAPI service backed by SQLite.

```bash
cp secrets.example.yml secrets.yml
# Edit secrets.yml and set database.url to your SQLite path.
export RUNTIME_OBSERVER_SECRETS='./secrets.yml'

runtime-observer-server --host 127.0.0.1 --port 4319
```

Open `http://127.0.0.1:4319/`. The first successful dashboard login creates the first user and assigns the `admin` role. After that, the same username/password must be used to sign in.

### Auth and first admin

Dashboard users and sessions are stored in the collector SQLite database. Bootstrap behavior:

1. If no user exists, `POST /api/auth/login` creates the submitted username/password as the admin user.
2. If a user already exists, login validates credentials and creates a session cookie.
3. `POST /api/auth/logout` clears the session.

Ingestion is separate from dashboard login. SDKs authenticate with project-scoped API keys generated in the dashboard and saved hashed in the SQLite database.

Project keys are scoped to one `project_name`; if an SDK sends events with a different project name the collector overrides `service.project_name` in every event to match the key's project, so events are always stored under the correct project regardless of what the SDK sent. Browser ingestion sends the same key as `?api_key=...` to `/v1/ingest/browser` because browsers cannot safely set long-lived bearer headers for beacon-style calls.

For local-only experiments you can run with `RUNTIME_OBSERVER_INSECURE_DEV=true` or `--insecure-dev`, but do not expose that mode outside localhost.

## Project bootstrap flow

1. Start the collector and open `http://127.0.0.1:4319/`.
2. Sign in. The first login creates the admin user; future logins require those credentials.
3. If this is a brand-new collector with no projects yet, click **Create first project SDK key** and enter the exact project name your app will send.
4. After data exists, login opens the **project selection** screen. Choose a project to inspect only that project's apps, routes, traces, logs, dependencies, and errors.
5. Use **Generate SDK API key** on the project card or inside the selected project. Copy it immediately; only the prefix is shown later.
6. Give the agent these four values: collector base URL, project name, service/app name, and project API key.

## Python/FastAPI integration

Use the same `project_name` for all services that should appear under one dashboard project, and use different `service_name` values for each app (`backend`, `worker`, `frontend`, and so on). The project name must exactly match the project SDK key scope in the collector.

Install the SDK into your application environment, then configure it with the collector base URL. Do not include `/v1/ingest` in `RUNTIME_OBSERVER_ENDPOINT`; the SDK appends that path.

```bash
export RUNTIME_OBSERVER_ENDPOINT='http://127.0.0.1:4319'
export RUNTIME_OBSERVER_API_KEY='ro_xxxxxxxx_project_key_from_dashboard'
export RUNTIME_OBSERVER_PROJECT_NAME='checkout'
export RUNTIME_OBSERVER_SERVICE_NAME='orders-api'
export RUNTIME_OBSERVER_CAPTURE_MODE='dev'
```

Instrument a FastAPI app:

```python
from fastapi import FastAPI
from runtime_observer import init_runtime_observer

app = FastAPI()
observer = init_runtime_observer.from_env(
    project_name="checkout",      # optional if env var is set
    service_name="orders-api",    # app/service name shown in the UI
    api_key="ro_xxxxxxxx_project_key_from_dashboard",  # optional if env var is set
    endpoint="http://127.0.0.1:4319",                  # optional if env var is set
)
observer.instrument_fastapi(app)

@app.get("/health")
def health():
    return {"ok": True}
```

Or use the helper:

```python
from fastapi import FastAPI
from runtime_observer.auto import init_from_env

app = FastAPI()
observer = init_from_env(app)
```

The FastAPI middleware emits route discovery, request start/finish, trace/span IDs, exceptions, and route-correlated logs.

### Python services without FastAPI

For workers, CLIs, background jobs, or scripts, initialize the observer and emit events manually:

```python
from runtime_observer import init_runtime_observer

observer = init_runtime_observer.from_env(
    project_name="checkout",
    service_name="billing-worker",
)

observer.emit("log_record", {
    "level": "INFO",
    "logger_name": "worker.startup",
    "message": "billing worker started",
})

observer.flush(timeout=2)
```

Call `observer.shutdown()` before process exit for short-lived jobs so queued events are exported.

## Logging and instrumentation

When `RUNTIME_OBSERVER_CAPTURE_LOGS=true` (default), the SDK attaches stdlib logging and loguru sinks. Logs inside an observed request inherit trace, span, route, and correlation IDs.

```python
import logging

log = logging.getLogger(__name__)
log.info("created order", extra={"order_id": "ord_123"})
```

The SDK also tries to auto-instrument installed common dependencies:

- `requests`
- `httpx`
- `SQLAlchemy`
- `LiteLLM`

You can call instrumentation explicitly if needed:

```python
observer.instrument_requests()
observer.instrument_httpx()
observer.instrument_sqlalchemy(engine)
observer.instrument_litellm()
```

Use custom spans for important internal operations. Spans make functions visible in the trace map and are the best way to show business-level steps that are not HTTP/database/LLM calls:

```python
with observer.start_span(
    "price quote",
    kind="function",
    attributes={"source": "cache", "cart_size": len(cart.items)},
):
    quote = calculate_quote(cart)
```

Capture handled exceptions when you catch and recover from them; otherwise the FastAPI middleware only sees unhandled exceptions:

```python
try:
    charge_customer(order)
except PaymentDeclined as exc:
    observer.capture_exception(exc, extra={"order_id": order.id, "payment_provider": "stripe"})
    return {"status": "declined"}
```

Emit counters for product/business metrics that are not naturally represented as logs or dependency calls:

```python
observer.emit("metric_counter", {
    "name": "orders.created",
    "value": 1,
    "attributes": {"region": "us-east-1", "channel": "web"},
})
```

### Manual code injection for richer metrics

Automatic instrumentation captures framework and dependency behavior, but the best business metrics often require a small SDK call inside the base application code where the domain context exists. This is supported and expected: inject `start_span()`, `capture_exception()`, `logging` calls, or schema-compatible `observer.emit()` calls at important boundaries.

Good injection points include order creation, checkout transitions, cache decisions, queue/job starts and finishes, tool invocations, feature-flag branches, and expensive internal functions:

```python
def create_order(cart, user):
    with observer.start_span("price quote", kind="function", attributes={"cart_size": len(cart.items)}):
        quote = calculate_quote(cart)

    observer.emit("function_called", {
        "name": "reserve_inventory",
        "attributes": {"item_count": len(cart.items)},
    })
    reservation = reserve_inventory(cart)
    observer.emit("function_returned", {
        "name": "reserve_inventory",
        "status": "ok",
        "attributes": {"reserved": len(reservation.items)},
    })

    observer.emit("metric_counter", {
        "name": "orders.created",
        "value": 1,
        "attributes": {"channel": "web", "currency": quote.currency},
    })
    return persist_order(user, quote, reservation)
```

For workers and agents, use the lifecycle event kinds directly:

```python
observer.emit("background_job_started", {"name": "nightly_rollup", "attributes": {"queue": "billing"}})
try:
    run_rollup()
    observer.emit("background_job_finished", {"name": "nightly_rollup", "status": "ok"})
except Exception as exc:
    observer.capture_exception(exc, extra={"job": "nightly_rollup"})
    observer.emit("background_job_finished", {"name": "nightly_rollup", "status": "error", "error_type": type(exc).__name__})
    raise
```

Add useful, non-secret values as span attributes, log `extra`, or event payload fields. Good enrichment fields include operation names, route-independent business identifiers, queue names, cache hit/miss, model/provider names, row counts, item counts, and feature flags. Avoid raw prompts, passwords, tokens, full request bodies, or customer PII unless you have explicitly configured redaction and production capture mode.

### Python enrichment options

| What to add | SDK API | Dashboard effect |
| --- | --- | --- |
| Request routes and trace IDs | `observer.instrument_fastapi(app)` | Route list, request traces, p50/p95 latency, exceptions |
| Function/business steps | `with observer.start_span(...)` | Function nodes inside the trace map |
| Logs with context | stdlib `logging` / loguru after observer start | Correlated logs on route, trace, and log screens |
| Handled exceptions | `observer.capture_exception(exc, extra={...})` | Error cards and trace/error context even when the app recovers |
| Outbound HTTP | `observer.instrument_requests()` / `observer.instrument_httpx()` | Dependency cards and dependency details |
| Database calls | `observer.instrument_sqlalchemy(engine)` | DB dependency cards, query timing, related traces |
| LLM calls | `observer.instrument_litellm()` | LLM dependency cards, model/provider metadata, durations |
| Business counters | `observer.emit("metric_counter", {...})` | Raw event stream and metric-oriented context |
| Injected function events | `observer.emit("function_called", {...})` / `observer.emit("function_returned", {...})` | Explicit business operation breadcrumbs |
| Worker lifecycle | `observer.emit("background_job_started", {...})` / `observer.emit("background_job_finished", {...})` | Job/queue visibility without FastAPI |
| Agent/tool calls | `observer.emit("tool_call", {...})` | Tool execution context for agent-style apps |
| Custom events | `observer.emit("log_record", {...})` or another supported event kind | Extra searchable context in logs/events |

Supported event kinds are `app_started`, `dependency_inventory`, `route_discovered`, `request_started`, `request_finished`, `span_started`, `span_finished`, `exception_raised`, `db_query`, `http_client_call`, `llm_call`, `log_record`, `metric_counter`, `sdk_diagnostic`, `function_called`, `function_returned`, `background_job_started`, `background_job_finished`, and `tool_call`.

## Browser and Node.js SDK

The JavaScript SDK lives in this repository under `js-sdk/` and is exported by the repository-root `package.json`. It is not currently published to npm. Prefer the host project's normal frontend setup command and add Runtime Observer in the form that matches how that project consumes unpublished packages.

For local development against a checked-out Runtime Observer repository, install from the repository root. npm will read the root `package.json` and expose the `js-sdk/` entrypoints:

```bash
npm install /absolute/path/to/runtime-observer
npm install runtime-observer@file:/absolute/path/to/runtime-observer
```

You can also build a tarball from the Runtime Observer repository root and install that file in the target app:

```bash
just pack-js-sdk
npm install /absolute/path/to/runtime-observer/runtime-observer-0.2.0.tgz
```

Or add it explicitly to `package.json`:

```json
{
  "dependencies": {
    "runtime-observer": "file:/absolute/path/to/runtime-observer"
  }
}
```

For GitHub installs, use:

```bash
npm install runtime-observer@github:germanilia/runtime-observer
```

If npm reports `Could not read package.json ... git-clone.../package.json`, verify that GitHub still reports `main` as the repository default branch. npm Git dependencies do not support pip-style `#subdirectory=...` fragments, so use a local file dependency or a published JS package instead of trying a subdirectory install.

### Browser setup

Configure it once during application startup:

```js
import { initBrowserObserver } from 'runtime-observer/browser';

const observer = initBrowserObserver({
  endpoint: 'http://127.0.0.1:4319',
  apiKey: 'ro_xxxxxxxx_project_key_from_dashboard',
  projectName: 'checkout',
  serviceName: 'frontend',
});

observer.installBrowserHooks();
observer.instrumentFetch();
observer.captureNavigation();

observer.emit('app_started', {
  environment: import.meta.env.MODE,
  location: window.location.origin,
});

observer.emit('log_record', {
  level: 'INFO',
  logger_name: 'browser.app',
  message: 'frontend started',
});
```

`observer.installBrowserHooks()` captures browser `error`, `unhandledrejection`, and page-hide flushes. `observer.instrumentFetch()` records browser `fetch` calls. Use `observer.emit()` for page-load, user action, feature, and performance milestones you want to see even when no error occurs. These calls are the browser equivalent of code-level enrichment: place them where the UI has useful product context.

Useful browser enrichment examples:

```js
observer.emit('log_record', {
  level: 'INFO',
  logger_name: 'browser.navigation',
  message: 'route changed',
  route: window.location.pathname,
});

observer.emit('metric_counter', {
  name: 'ui.button.clicked',
  value: 1,
  attributes: { button: 'checkout-submit', route: window.location.pathname },
});

observer.emit('log_record', {
  level: 'WARNING',
  logger_name: 'browser.validation',
  message: 'checkout form validation failed',
  field_count: invalidFields.length,
});
```

A browser can also post schema-compatible events directly to the browser endpoint. Browser events must follow the shared schema and include the same envelope fields as SDK events (`schema_version`, `event_id`, `timestamp`, `service`, `trace_id`, `span_id`, `parent_span_id`, `kind`, and `payload`). See [`../schemas/README.md`](../schemas/README.md) and [`api.md`](api.md).

### Node.js services

For Node.js services on Node 18+, use the Node entrypoint. It resolves `RUNTIME_OBSERVER_*` environment variables, batches events, preserves async trace context with `AsyncLocalStorage`, emits startup/dependency events, and can instrument global `fetch` and Express middleware:

```js
import express from 'express';
import { initRuntimeObserver } from 'runtime-observer/node';

const observer = initRuntimeObserver.fromEnv({ serviceName: 'node-service' });
observer.instrumentFetch();

const app = express();
observer.instrumentExpress(app);

observer.emit('log_record', {
  level: 'INFO',
  logger_name: 'node.bootstrap',
  message: 'node service started',
});

app.get('/sync', async (_req, res) => {
  await observer.startSpan('syncCatalog', async () => {
    await syncCatalog();
  }, { kind: 'function', attributes: { source: 'shopify' } });
  res.json({ ok: true });
});

process.on('beforeExit', () => observer.shutdown());
```

For non-Express workers, use the same observer manually:

```js
const observer = initRuntimeObserver.fromEnv({ serviceName: 'worker' });

try {
  await observer.startSpan('nightly_rollup', () => doWork(), { kind: 'job' });
} catch (error) {
  observer.captureException(error, { job: 'nightly_rollup' });
  throw error;
} finally {
  await observer.shutdown();
}
```

Because the browser endpoint accepts the API key in the URL, only use browser ingestion from trusted/internal environments or put the collector behind a trusted proxy. Node.js ingestion sends the key in the `Authorization` header. CORS is open by default to support local dashboards and internal tools.

### JavaScript enrichment options

| What to add | SDK API | Dashboard effect |
| --- | --- | --- |
| Frontend/server startup | `observer.emit('app_started', {...})` | Creates the app/service and shows recent activity |
| Browser runtime errors | `observer.installBrowserHooks()` | Error logs for `window.error` and unhandled promises |
| User actions | `observer.emit('log_record', {...})` | Searchable frontend activity and context |
| Business counters | `observer.emit('metric_counter', {...})` | Raw metric events and metric-oriented context |
| Timed function work | `observer.startSpan(name, fn, options)` | Function timing in event/trace context |
| Handled errors | `observer.captureException(error, extra)` | Error records even if the UI/server recovers |
| Cross-service correlation | pass `{ traceId, spanId, parentSpanId }` as the third argument or use Node async context | Groups related browser, Node, and backend events by trace |

## Dashboard behavior

### Hiding and preferences

The dashboard persists server-side hiding rules per dashboard user through `/api/preferences/hidden`. Entry points/routes can be hidden and restored; the same preference model is used for route/dependency visibility. It also provides filters/tabs for app scope, log source, selected route, and log time window. The log time window is stored in browser `localStorage` as `runtimeObserverLogWindowMinutes`.

Trace details intentionally hide unrelated nearby background logs from the main causal flow. They remain available in the trace drawer under the collapsed “Nearby background activity” section.

### Trace map

Open a route, select a trace, and the “Triggered map” drawer shows:

- route/request node
- function spans
- exact trace logs
- dependency calls and inputs
- exceptions
- raw causal timeline
- separated nearby background logs

Use “Copy full trace for AI” to copy the trace agent context from `/api/traces/{trace_id}/agent-context`.

## Dependency inventory and maps

On startup, the SDK emits application metadata and dependency inventory. Runtime dependency calls are aggregated from events such as `db_query`, `http_client_call`, and `llm_call`. The dashboard and APIs use this data for dependency cards, dependency context, and call graph views.

Useful endpoints:

- `/api/apps/{app_id}/dependencies`
- `/api/apps/{app_id}/call-graph`
- `/api/dependencies/{dependency_id}/context`
- `/api/dependencies/{dependency_id}/agent-context`

## Troubleshooting

- **No events appear:** confirm the collector is running, `RUNTIME_OBSERVER_ENDPOINT` is the collector base URL, `RUNTIME_OBSERVER_PROJECT_NAME` exactly matches the project key scope, and the API key was copied from the project screen.
- **401 on ingest:** set `Authorization: Bearer <RUNTIME_OBSERVER_API_KEY>` for `/v1/ingest`, or pass `?api_key=...` to `/v1/ingest/browser`.
- **Events land in wrong project:** if `RUNTIME_OBSERVER_PROJECT_NAME` doesn't match the key's project the collector silently overrides it — check the project name shown in the dashboard and ensure you're using the key for the intended project.
- **Dashboard asks for auth:** sign in with the first admin credentials you created on initial login. The ingest bearer key is separate from dashboard login.
- **Double `/v1/ingest/v1/ingest` URL:** remove `/v1/ingest` from `RUNTIME_OBSERVER_ENDPOINT`.
- **No exports in local dev:** provide an API key or set `RUNTIME_OBSERVER_INSECURE_DEV=true` for SDK experiments.
- **Missing dependency calls:** make sure the dependency package is installed before the observer starts, or call the relevant `observer.instrument_*()` method explicitly.
- **Missing business metrics:** automatic instrumentation cannot infer product semantics; inject `observer.emit("metric_counter", ...)`, function events, job lifecycle events, or spans at the point in code where the business action happens.
- **Logs missing trace IDs:** ensure logging happens inside the FastAPI request context or inside a span created by the observer.
- **Sensitive data concerns:** use `RUNTIME_OBSERVER_CAPTURE_MODE=prod` and keep `RUNTIME_OBSERVER_CAPTURE_DB_QUERY_VALUES=false` in production-like environments.
