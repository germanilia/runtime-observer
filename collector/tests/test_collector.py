from __future__ import annotations

from fastapi.testclient import TestClient

from runtime_observer_server.config import Settings
from runtime_observer_server.main import create_app


def make_client(tmp_path):
    settings = Settings(api_key="test-key", dashboard_username="admin", dashboard_password="secret", database_path=tmp_path / "collector.sqlite3")
    return TestClient(create_app(settings))


def dashboard_auth() -> tuple[str, str]:
    return ("admin", "secret")


def sample_events():
    service = {"project_name": "internal-assistant", "name": "backend", "display_name": "Sample API", "language": "python", "runtime_version": "3.11", "sdk_version": "0.1.0"}
    return [
        {"schema_version": "1.0", "event_id": "evt-app", "timestamp": "2026-05-09T20:00:00.000Z", "service": service, "kind": "app_started", "payload": {"environment": "test"}},
        {"schema_version": "1.0", "event_id": "evt-route", "timestamp": "2026-05-09T20:00:01.000Z", "service": service, "kind": "route_discovered", "payload": {"method": "GET", "route_pattern": "/health"}},
        {"schema_version": "1.0", "event_id": "evt-start", "timestamp": "2026-05-09T20:00:02.000Z", "service": service, "trace_id": "trace-1", "span_id": "span-1", "kind": "request_started", "payload": {"method": "GET", "route_pattern": "/health"}},
        {"schema_version": "1.0", "event_id": "evt-log", "timestamp": "2026-05-09T20:00:02.500Z", "service": service, "trace_id": "trace-1", "span_id": "span-1", "kind": "log_record", "payload": {"level": "INFO", "logger_name": "sample", "message": "ok token=Bearer abc.def.ghi", "method": "GET", "route_pattern": "/health"}},
        {"schema_version": "1.0", "event_id": "evt-finish", "timestamp": "2026-05-09T20:00:03.000Z", "service": service, "trace_id": "trace-1", "span_id": "span-1", "kind": "request_finished", "payload": {"method": "GET", "route_pattern": "/health", "duration_ms": 42, "status_code": 200}},
        {"schema_version": "1.0", "event_id": "evt-exc", "timestamp": "2026-05-09T20:00:04.000Z", "service": service, "trace_id": "trace-2", "kind": "exception_raised", "payload": {"type": "ValueError", "message": "boom"}},
        {"schema_version": "1.0", "event_id": "evt-db", "timestamp": "2026-05-09T20:00:05.000Z", "service": service, "trace_id": "trace-1", "kind": "db_query", "payload": {"operation": "SELECT", "table": "users", "duration_ms": 7}},
        {"schema_version": "1.0", "event_id": "evt-llm", "timestamp": "2026-05-09T20:00:06.000Z", "service": service, "trace_id": "trace-1", "kind": "llm_call", "payload": {"provider": "openai", "model": "gpt-test", "input_tokens": 10, "output_tokens": 5, "duration_ms": 100}},
    ]


def correlated_events():
    backend = {"project_name": "shop", "name": "backend", "display_name": "Backend", "language": "python"}
    worker = {"project_name": "shop", "name": "worker", "display_name": "Worker", "language": "python"}
    other = {"project_name": "other", "name": "other-worker", "display_name": "Other Worker", "language": "python"}
    return [
        {"schema_version": "1.0", "event_id": "corr-start", "timestamp": "2026-05-09T21:00:00.000Z", "service": backend, "trace_id": "trace-corr", "kind": "request_started", "payload": {"method": "POST", "route_pattern": "/checkout"}},
        {"schema_version": "1.0", "event_id": "corr-backend-info", "timestamp": "2026-05-09T21:00:01.000Z", "service": backend, "trace_id": "trace-corr", "kind": "log_record", "payload": {"level": "INFO", "logger_name": "api", "message": "checkout started", "method": "POST", "route_pattern": "/checkout"}},
        {"schema_version": "1.0", "event_id": "corr-worker-error", "timestamp": "2026-05-09T21:00:02.000Z", "service": worker, "trace_id": "trace-corr", "kind": "log_record", "payload": {"level": "ERROR", "logger_name": "worker", "message": "payment failed"}},
        {"schema_version": "1.0", "event_id": "corr-worker-near", "timestamp": "2026-05-09T21:00:03.000Z", "service": worker, "kind": "log_record", "payload": {"level": "ERROR", "logger_name": "worker", "message": "retry queued"}},
        {"schema_version": "1.0", "event_id": "corr-other-near", "timestamp": "2026-05-09T21:00:03.000Z", "service": other, "kind": "log_record", "payload": {"level": "ERROR", "logger_name": "other", "message": "other project noise"}},
        {"schema_version": "1.0", "event_id": "corr-finish", "timestamp": "2026-05-09T21:00:04.000Z", "service": backend, "trace_id": "trace-corr", "kind": "request_finished", "payload": {"method": "POST", "route_pattern": "/checkout", "duration_ms": 40, "status_code": 500}},
    ]


def test_correlated_logs_level_filtering_and_app_project_scope(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"events": correlated_events()})
    assert response.status_code == 200
    apps = client.get("/api/apps", auth=dashboard_auth()).json()
    app_by_name = {app["service_name"]: app for app in apps}

    error_logs = client.get("/api/traces/trace-corr/correlated-logs", params={"level": "ERROR"}, auth=dashboard_auth()).json()
    messages = {log["message"] for log in error_logs["logs"]}
    assert messages == {"payment failed", "retry queued"}
    assert "other project noise" not in messages
    assert {group["service_name"] for group in error_logs["groups"]} == {"worker"}
    assert {log["correlation"]["type"] for log in error_logs["logs"]} == {"exact_trace", "nearby_time"}

    worker_only = client.get(
        "/api/traces/trace-corr/correlated-logs",
        params={"app_ids": app_by_name["worker"]["id"], "level": "ERROR"},
        auth=dashboard_auth(),
    ).json()
    assert {log["app_id"] for log in worker_only["logs"]} == {app_by_name["worker"]["id"]}

    all_projects = client.get("/api/traces/trace-corr/correlated-logs", params={"level": "ERROR", "same_project": "false"}, auth=dashboard_auth()).json()
    assert "other project noise" in {log["message"] for log in all_projects["logs"]}


def test_auth_ingest_dashboard_logs_and_clear(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/v1/ingest", json={"events": []}).status_code == 401

    response = client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"batch_id": "batch-1", "events": sample_events()})
    assert response.status_code == 200
    assert response.json()["accepted"] == len(sample_events())

    assert client.get("/api/apps").status_code == 401
    apps = client.get("/api/apps", auth=dashboard_auth()).json()
    assert len(apps) == 1
    assert apps[0]["project_name"] == "internal-assistant"
    assert apps[0]["service_name"] == "backend"
    assert apps[0]["display_name"] == "Sample API"
    app_id = apps[0]["id"]

    overview = client.get(f"/api/apps/{app_id}/overview", auth=dashboard_auth()).json()
    assert overview["request_count"] == 1
    assert overview["log_count"] == 1

    routes = client.get(f"/api/apps/{app_id}/routes", auth=dashboard_auth()).json()
    assert routes[0]["route_pattern"] == "/health"
    assert routes[0]["p95_ms"] == 42

    logs = client.get(f"/api/apps/{app_id}/logs", params={"text": "ok"}, auth=dashboard_auth()).json()
    assert len(logs) == 1
    assert "Bearer" not in logs[0]["message"]

    trace = client.get(f"/api/apps/{app_id}/traces/trace-1", auth=dashboard_auth()).json()
    assert len(trace["events"]) >= 4
    assert len(trace["logs"]) == 1

    exceptions = client.get(f"/api/apps/{app_id}/exceptions", auth=dashboard_auth()).json()
    assert exceptions[0]["type"] == "ValueError"

    deps = client.get(f"/api/apps/{app_id}/dependencies", auth=dashboard_auth()).json()
    assert deps[0]["dependency_type"] == "db"

    failing = client.post("/api/agent/get_failing_routes", json={"app_id": app_id, "limit": 5}, auth=dashboard_auth()).json()
    assert isinstance(failing, list)

    clear = client.post("/api/admin/clear", headers={"Authorization": "Bearer test-key"})
    assert clear.status_code == 200
    assert client.get("/api/apps", auth=dashboard_auth()).json() == []
