# Integration guide

This guide covers installing Runtime Observer from GitHub, running the collector, and instrumenting Python/FastAPI, logging, dependencies, and browser clients.

## Package availability

Runtime Observer is not published to PyPI or npm yet. Install the Python SDK and collector directly from this repository using GitHub `subdirectory` URLs. Browser and Node.js projects install the lightweight npm helper from the repository root. The npm package name is `runtime-observer-browser`, but the GitHub install target is the repository root.

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

Project keys are scoped to one `project_name`; if an SDK sends events for a different project, the collector rejects the batch with `403`. Browser ingestion sends the same key as `?api_key=...` to `/v1/ingest/browser` because browsers cannot safely set long-lived bearer headers for beacon-style calls.

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
| Business counters | `observer.emit("metric_counter", {...})` | Raw event stream and future metric aggregation |
| Custom events | `observer.emit("log_record", {...})` or another supported event kind | Extra searchable context in logs/events |

Supported event kinds are `app_started`, `dependency_inventory`, `route_discovered`, `request_started`, `request_finished`, `span_started`, `span_finished`, `exception_raised`, `db_query`, `http_client_call`, `llm_call`, `log_record`, `metric_counter`, and `sdk_diagnostic`.

## Browser and Node.js SDK

Install the JavaScript helper directly from GitHub:

```bash
npm install runtime-observer-browser@github:germanilia/runtime-observer
```

Or add it explicitly to `package.json`:

```json
{
  "dependencies": {
    "runtime-observer-browser": "github:germanilia/runtime-observer"
  }
}
```

Then run `npm install`.

### Browser setup

Configure it once during application startup:

```js
import {
  configureRuntimeObserver,
  emitRuntimeObserverEvent,
  installRuntimeObserverBrowserHooks,
} from 'runtime-observer-browser';

configureRuntimeObserver({
  endpoint: 'http://127.0.0.1:4319',
  apiKey: 'ro_xxxxxxxx_project_key_from_dashboard',
  projectName: 'checkout',
  serviceName: 'frontend',
});
installRuntimeObserverBrowserHooks();

await emitRuntimeObserverEvent('app_started', {
  environment: import.meta.env.MODE,
  location: window.location.origin,
});

await emitRuntimeObserverEvent('log_record', {
  level: 'INFO',
  logger_name: 'browser.app',
  message: 'frontend started',
});
```

`installRuntimeObserverBrowserHooks()` currently captures browser `error` and `unhandledrejection` events. Use `emitRuntimeObserverEvent()` for page-load, user action, feature, and performance milestones you want to see even when no error occurs.

Useful browser enrichment examples:

```js
await emitRuntimeObserverEvent('log_record', {
  level: 'INFO',
  logger_name: 'browser.navigation',
  message: 'route changed',
  route: window.location.pathname,
});

await emitRuntimeObserverEvent('metric_counter', {
  name: 'ui.button.clicked',
  value: 1,
  attributes: { button: 'checkout-submit', route: window.location.pathname },
});

await emitRuntimeObserverEvent('log_record', {
  level: 'WARNING',
  logger_name: 'browser.validation',
  message: 'checkout form validation failed',
  field_count: invalidFields.length,
});
```

A browser can also post schema-compatible events directly to the browser endpoint. Browser events must follow the shared schema and include the same envelope fields as SDK events (`schema_version`, `event_id`, `timestamp`, `service`, `trace_id`, `span_id`, `parent_span_id`, `kind`, and `payload`). See [`../schemas/README.md`](../schemas/README.md) and [`api.md`](api.md).

### Node.js services

For Node.js services on Node 18+, the same package can emit manual events because it uses the built-in `fetch` API:

```js
import { configureRuntimeObserver, emitRuntimeObserverEvent } from 'runtime-observer-browser';

configureRuntimeObserver({
  endpoint: process.env.RUNTIME_OBSERVER_ENDPOINT,
  apiKey: process.env.RUNTIME_OBSERVER_API_KEY,
  projectName: process.env.RUNTIME_OBSERVER_PROJECT_NAME,
  serviceName: process.env.RUNTIME_OBSERVER_SERVICE_NAME || 'node-service',
});

await emitRuntimeObserverEvent('app_started', {
  environment: process.env.NODE_ENV || 'development',
  pid: process.pid,
});

await emitRuntimeObserverEvent('log_record', {
  level: 'INFO',
  logger_name: 'node.bootstrap',
  message: 'node service started',
});
```

Wrap important Node functions with paired span events if you want them to appear as timed work in the trace/event stream:

```js
const spanId = crypto.randomUUID();
const started = performance.now();
await emitRuntimeObserverEvent('span_started', {
  name: 'syncCatalog',
  kind: 'function',
  attributes: { source: 'shopify' },
}, { spanId });

try {
  await syncCatalog();
  await emitRuntimeObserverEvent('span_finished', {
    name: 'syncCatalog',
    kind: 'function',
    status: 'ok',
    duration_ms: performance.now() - started,
  }, { spanId });
} catch (error) {
  await emitRuntimeObserverEvent('exception_raised', {
    type: error.name || 'Error',
    message: error.message,
    stack: String(error.stack || ''),
  }, { spanId });
  await emitRuntimeObserverEvent('span_finished', {
    name: 'syncCatalog',
    kind: 'function',
    status: 'error',
    duration_ms: performance.now() - started,
  }, { spanId });
  throw error;
}
```

Because the browser endpoint accepts the API key in the URL, only use browser ingestion from trusted/internal environments or put the collector behind a trusted proxy. Node.js ingestion sends the key in the `Authorization` header. CORS is open by default to support local dashboards and internal tools.

### JavaScript enrichment options

| What to add | SDK API | Dashboard effect |
| --- | --- | --- |
| Frontend/server startup | `emitRuntimeObserverEvent('app_started', {...})` | Creates the app/service and shows recent activity |
| Browser runtime errors | `installRuntimeObserverBrowserHooks()` | Error logs for `window.error` and unhandled promises |
| User actions | `emitRuntimeObserverEvent('log_record', {...})` | Searchable frontend activity and context |
| Business counters | `emitRuntimeObserverEvent('metric_counter', {...})` | Raw metric events and future metric aggregation |
| Timed function work | `span_started` + `span_finished` events | Function timing in event/trace context |
| Handled errors | `exception_raised` event | Error records even if the UI/server recovers |
| Cross-service correlation | pass `{ traceId, spanId, parentSpanId }` as the third argument | Groups related browser, Node, and backend events by trace |

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
- **403 on ingest:** the project-scoped API key does not match the event `service.project_name`; fix `RUNTIME_OBSERVER_PROJECT_NAME` or generate a key for the intended project.
- **Dashboard asks for auth:** sign in with the first admin credentials you created on initial login. The ingest bearer key is separate from dashboard login.
- **Double `/v1/ingest/v1/ingest` URL:** remove `/v1/ingest` from `RUNTIME_OBSERVER_ENDPOINT`.
- **No exports in local dev:** provide an API key or set `RUNTIME_OBSERVER_INSECURE_DEV=true` for SDK experiments.
- **Missing dependency calls:** make sure the dependency package is installed before the observer starts, or call the relevant `observer.instrument_*()` method explicitly.
- **Logs missing trace IDs:** ensure logging happens inside the FastAPI request context or inside a span created by the observer.
- **Sensitive data concerns:** use `RUNTIME_OBSERVER_CAPTURE_MODE=prod` and keep `RUNTIME_OBSERVER_CAPTURE_DB_QUERY_VALUES=false` in production-like environments.
