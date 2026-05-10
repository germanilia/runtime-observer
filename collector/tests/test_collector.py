from __future__ import annotations

import os

from fastapi.testclient import TestClient

from runtime_observer_server.config import Settings
from runtime_observer_server.main import create_app


def test_settings_load_database_url_from_secrets_file(tmp_path):
    secrets_file = tmp_path / "secrets.yml"
    db_path = tmp_path / "runtime.sqlite3"
    secrets_file.write_text(f"database:\n  url: sqlite:///{db_path}\n")

    old_value = os.environ.get("RUNTIME_OBSERVER_SECRETS")
    os.environ["RUNTIME_OBSERVER_SECRETS"] = str(secrets_file)
    try:
        settings = Settings.from_env()
    finally:
        if old_value is None:
            os.environ.pop("RUNTIME_OBSERVER_SECRETS", None)
        else:
            os.environ["RUNTIME_OBSERVER_SECRETS"] = old_value

    assert settings.database_path == db_path


def make_client(tmp_path):
    settings = Settings(api_key="test-key", dashboard_username="admin", dashboard_password="secret", database_path=tmp_path / "collector.sqlite3")
    return TestClient(create_app(settings))


def make_insecure_client(tmp_path):
    settings = Settings(api_key="test-key", database_path=tmp_path / "collector.sqlite3", insecure_dev_mode=True)
    return TestClient(create_app(settings))


def login(client: TestClient, username: str = "admin", password: str = "secret") -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def sample_events():
    service = {"project_name": "internal-assistant", "name": "backend", "display_name": "Sample API", "language": "python", "runtime_version": "3.11", "sdk_version": "0.1.0"}
    return [
        {"schema_version": "1.0", "event_id": "evt-app", "timestamp": "2026-05-09T20:00:00.000Z", "service": service, "kind": "app_started", "payload": {"environment": "test"}},
        {"schema_version": "1.0", "event_id": "evt-route", "timestamp": "2026-05-09T20:00:01.000Z", "service": service, "kind": "route_discovered", "payload": {"method": "GET", "route_pattern": "/health"}},
        {"schema_version": "1.0", "event_id": "evt-start", "timestamp": "2026-05-09T20:00:02.000Z", "service": service, "trace_id": "trace-1", "span_id": "span-1", "kind": "request_started", "payload": {"method": "GET", "route_pattern": "/health"}},
        {"schema_version": "1.0", "event_id": "evt-log", "timestamp": "2026-05-09T20:00:02.500Z", "service": service, "trace_id": "trace-1", "span_id": "span-1", "kind": "log_record", "payload": {"level": "INFO", "logger_name": "sample", "message": "ok token=Bearer abc.def.ghi", "method": "GET", "route_pattern": "/health"}},
        {"schema_version": "1.0", "event_id": "evt-span-start", "timestamp": "2026-05-09T20:00:02.600Z", "service": service, "trace_id": "trace-1", "span_id": "span-worker", "kind": "span_started", "payload": {"name": "load_user", "kind": "function"}},
        {"schema_version": "1.0", "event_id": "evt-span-finish", "timestamp": "2026-05-09T20:00:02.900Z", "service": service, "trace_id": "trace-1", "span_id": "span-worker", "kind": "span_finished", "payload": {"name": "load_user", "kind": "function", "duration_ms": 30, "status": "ok"}},
        {"schema_version": "1.0", "event_id": "evt-finish", "timestamp": "2026-05-09T20:00:03.000Z", "service": service, "trace_id": "trace-1", "span_id": "span-1", "kind": "request_finished", "payload": {"method": "GET", "route_pattern": "/health", "duration_ms": 42, "status_code": 200}},
        {"schema_version": "1.0", "event_id": "evt-exc", "timestamp": "2026-05-09T20:00:04.000Z", "service": service, "trace_id": "trace-2", "kind": "exception_raised", "payload": {"type": "ValueError", "message": "boom"}},
        {"schema_version": "1.0", "event_id": "evt-db", "timestamp": "2026-05-09T20:00:05.000Z", "service": service, "trace_id": "trace-1", "span_id": "span-worker", "kind": "db_query", "payload": {"operation": "SELECT", "table": "users", "duration_ms": 7}},
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


def test_project_api_keys_scope_ingest_by_project(tmp_path):
    client = make_client(tmp_path)
    login(client)
    created = client.post("/api/projects/shop/api-keys").json()
    project_key = created["api_key"]

    response = client.post("/v1/ingest", headers={"Authorization": f"Bearer {project_key}"}, json={"events": correlated_events()[:1]})
    assert response.status_code == 200
    assert response.json()["accepted"] == 1

    wrong_project_event = dict(correlated_events()[-2])
    response = client.post("/v1/ingest", headers={"Authorization": f"Bearer {project_key}"}, json={"events": [wrong_project_event]})
    assert response.status_code == 403

    projects = client.get("/api/projects").json()
    assert any(project["project_name"] == "shop" for project in projects)
    keys = client.get("/api/projects/shop/api-keys").json()
    assert keys[0]["prefix"] == created["prefix"]
    assert keys[0]["name"] == "shop"
    assert "api_key" not in keys[0]


def test_correlated_logs_level_filtering_and_app_project_scope(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"events": correlated_events()})
    assert response.status_code == 200
    login(client)
    apps = client.get("/api/apps").json()
    app_by_name = {app["service_name"]: app for app in apps}

    error_logs = client.get("/api/traces/trace-corr/correlated-logs", params={"level": "ERROR"}).json()
    messages = {log["message"] for log in error_logs["logs"]}
    assert messages == {"payment failed", "retry queued"}
    assert "other project noise" not in messages
    assert {group["service_name"] for group in error_logs["groups"]} == {"worker"}
    assert {log["correlation"]["type"] for log in error_logs["logs"]} == {"exact_trace", "nearby_time"}

    worker_only = client.get(
        "/api/traces/trace-corr/correlated-logs",
        params={"app_ids": app_by_name["worker"]["id"], "level": "ERROR"},
    ).json()
    assert {log["app_id"] for log in worker_only["logs"]} == {app_by_name["worker"]["id"]}

    all_projects = client.get("/api/traces/trace-corr/correlated-logs", params={"level": "ERROR", "same_project": "false"}).json()
    assert "other project noise" in {log["message"] for log in all_projects["logs"]}


def test_auth_ingest_dashboard_logs_and_clear(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/v1/ingest", json={"events": []}).status_code == 401

    response = client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"batch_id": "batch-1", "events": sample_events()})
    assert response.status_code == 200
    assert response.json()["accepted"] == len(sample_events())

    assert client.get("/api/apps").status_code == 401
    login(client)
    apps = client.get("/api/apps").json()
    assert len(apps) == 1
    assert apps[0]["project_name"] == "internal-assistant"
    assert apps[0]["service_name"] == "backend"
    assert apps[0]["display_name"] == "Sample API"
    app_id = apps[0]["id"]

    overview = client.get(f"/api/apps/{app_id}/overview").json()
    assert overview["request_count"] == 1
    assert overview["log_count"] == 1

    routes = client.get(f"/api/apps/{app_id}/routes").json()
    assert routes[0]["route_pattern"] == "/health"
    assert routes[0]["p95_ms"] == 42

    logs = client.get(f"/api/apps/{app_id}/logs", params={"text": "ok"}).json()
    assert len(logs) == 1
    assert "Bearer" not in logs[0]["message"]

    trace = client.get(f"/api/apps/{app_id}/traces/trace-1").json()
    assert len(trace["events"]) >= 4
    assert len(trace["logs"]) == 1

    trace_map = client.get("/api/traces/trace-1/map").json()
    flow = trace_map["flow"]
    assert {node["type"] for node in flow["nodes"]} >= {"route", "span", "dependency", "log"}
    span_node = next(node for node in flow["nodes"] if node["type"] == "span")
    db_node = next(node for node in flow["nodes"] if node.get("kind") == "db_query")
    assert any(edge["from"] == span_node["id"] and edge["to"] == db_node["id"] for edge in flow["edges"])
    assert any(edge["to"] == span_node["id"] for edge in flow["edges"])

    exceptions = client.get(f"/api/apps/{app_id}/exceptions").json()
    assert exceptions[0]["type"] == "ValueError"

    deps = client.get(f"/api/apps/{app_id}/dependencies").json()
    assert deps[0]["dependency_type"] == "db"

    failing = client.post("/api/agent/get_failing_routes", json={"app_id": app_id, "limit": 5}).json()
    assert isinstance(failing, list)

    clear = client.post("/api/admin/clear")
    assert clear.status_code == 200
    assert client.get("/api/apps").json() == []


def test_session_login_logout_and_first_admin_bootstrap(tmp_path):
    client = make_client(tmp_path)

    assert client.get("/api/auth/me").status_code == 401
    login(client, "owner", "secret")
    assert client.get("/api/auth/me").json()["user"] == {"username": "owner", "role": "admin"}

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/apps").status_code == 401

    assert client.post("/api/auth/login", json={"username": "owner", "password": "wrong"}).status_code == 401
    login(client, "owner", "secret")
    assert client.get("/api/apps").status_code == 200


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
