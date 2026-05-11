from __future__ import annotations

import pytest

from runtime_observer import init_runtime_observer

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _drain(observer):
    observer.exporter._stop.set()
    events = []
    while not observer.exporter._queue.empty():
        events.append(observer.exporter._queue.get_nowait())
    return events


def test_fastapi_requests_routes_and_logs():
    app = FastAPI()
    observer = init_runtime_observer(project_name="test", service_name="fastapi-test", enabled=True, insecure_local_dev=True, capture_logs=False)
    observer.exporter.shutdown(timeout=0.1)

    @app.get("/items/{item_id}")
    def get_item(item_id: str):
        return {"item_id": item_id}

    observer.instrument_fastapi(app)
    response = TestClient(app).get("/items/abc", headers={"X-Correlation-ID": "corr-1"})
    assert response.status_code == 200
    events = _drain(observer)
    kinds = [event["kind"] for event in events]
    assert "route_discovered" in kinds
    assert "request_started" in kinds
    finished = [event for event in events if event["kind"] == "request_finished"][-1]
    assert finished["payload"]["route_pattern"] == "/items/{item_id}"
    assert finished["payload"]["path"] == "/items/<redacted:path_param>"
    assert finished["payload"]["correlation_id"] == "corr-1"


def test_fastapi_exception_event_contains_stack():
    app = FastAPI()
    observer = init_runtime_observer(project_name="test", service_name="fastapi-test", enabled=True, insecure_local_dev=True, capture_logs=False)
    observer.exporter.shutdown(timeout=0.1)

    @app.get("/boom")
    def boom():
        raise RuntimeError("bad token Bearer abcdefghijklmnopqrstuvwxyz0123456789")

    observer.instrument_fastapi(app)
    with pytest.raises(RuntimeError):
        TestClient(app, raise_server_exceptions=True).get("/boom")
    events = _drain(observer)
    exception = [event for event in events if event["kind"] == "exception_raised"][-1]
    assert exception["payload"]["type"] == "RuntimeError"
    assert "<redacted:token>" in exception["payload"]["message"]
    assert exception["payload"]["route_pattern"] == "/boom"
    assert exception["payload"]["stack"]
