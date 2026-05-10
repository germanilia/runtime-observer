# Python FastAPI minimal Runtime Observer example

This app is intentionally separate from Internal Assistant. It can run with or without the future `runtime_observer` SDK installed.

## Install

```bash
cd runtime-observer-product/implementation/examples/python-fastapi-minimal
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

If testing a local SDK package later, also install it into this venv, for example:

```bash
python -m pip install -e ../../python-sdk
```

## Run with collector

Start the collector in another terminal when it exists:

```bash
runtime-observer-server --port 4319 --api-key local-dev-key
```

Run the sample app:

```bash
cd runtime-observer-product/implementation/examples/python-fastapi-minimal
. .venv/bin/activate
RUNTIME_OBSERVER_ENABLED=true \
RUNTIME_OBSERVER_API_KEY=local-dev-key \
RUNTIME_OBSERVER_ENDPOINT=http://127.0.0.1:4319 \
RUNTIME_OBSERVER_CAPTURE_MODE=dev \
uvicorn app.main:app --host 127.0.0.1 --port 8020
```

## Exercise telemetry

```bash
curl -s http://127.0.0.1:8020/health
curl -s http://127.0.0.1:8020/items/1
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8020/items/404
curl -s http://127.0.0.1:8020/outbound
curl -s -X POST 'http://127.0.0.1:8020/llm-simulated?prompt_size=42'
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8020/boom
```

Expected telemetry when SDK + collector are available: `app_started`, `route_discovered`, `request_started`, `request_finished`, `db_query`, `http_client_call`, `log_record`, and `exception_raised` events. The `/llm-simulated` route produces application logs and response metadata for exercising LLM-related dashboards before real LiteLLM instrumentation exists.
