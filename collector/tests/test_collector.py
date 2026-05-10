from __future__ import annotations

from fastapi.testclient import TestClient

from runtime_observer_server.config import Settings
from runtime_observer_server.main import create_app


def make_client(tmp_path):
    settings = Settings(api_key="test-key", dashboard_username="admin", dashboard_password="secret", database_path=tmp_path / "collector.sqlite3")
    return TestClient(create_app(settings))


def make_insecure_client(tmp_path):
    settings = Settings(api_key="test-key", database_path=tmp_path / "collector.sqlite3", insecure_dev_mode=True)
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


def test_hidden_route_preferences_are_per_user(tmp_path):
    client = make_insecure_client(tmp_path)
    client.post("/v1/ingest", json={"events": sample_events()})

    alice = {"X-Runtime-Observer-User": "alice"}
    bob = {"X-Runtime-Observer-User": "bob"}
    route = client.get("/api/entrypoints", headers=alice).json()[0]

    response = client.post(
        "/api/preferences/hidden",
        json={"target_kind": "route", "target_id": route["id"], "app_id": route["app_id"]},
        headers=alice,
    )
    assert response.status_code == 200

    assert client.get("/api/entrypoints", headers=alice).json() == []
    assert client.get(f"/api/apps/{route['app_id']}/routes", headers=alice).json() == []
    assert client.get("/api/entrypoints", headers=bob).json()[0]["id"] == route["id"]
    assert client.get(f"/api/apps/{route['app_id']}/routes", headers=bob).json()[0]["id"] == route["id"]

    overview = client.get("/api/overview", headers=alice).json()
    assert overview["routes"] == []
    assert overview["totals"]["request_count"] == 0

    hidden = client.get("/api/entrypoints", params={"include_hidden": True}, headers=alice).json()
    assert hidden[0]["id"] == route["id"]
    assert hidden[0]["hidden"] == 1

    restore = client.delete(f"/api/preferences/hidden/route/{route['id']}", params={"app_id": route["app_id"]}, headers=alice)
    assert restore.status_code == 200
    assert client.get("/api/entrypoints", headers=alice).json()[0]["id"] == route["id"]
