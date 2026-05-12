from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from runtime_observer_server.config import Settings
from runtime_observer_server.db import Database
from runtime_observer_server.main import create_app
from runtime_observer_server.store import CollectorStore


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


def test_database_self_heals_after_file_removal(tmp_path):
    db_path = tmp_path / "collector.sqlite3"
    db = Database(db_path)
    db_path.unlink()

    with db.connect() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    assert "routes" in tables
    assert "user_preferences" in tables


def test_database_migrates_old_app_service_name_unique_constraint(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE apps (
              id TEXT PRIMARY KEY, service_name TEXT NOT NULL UNIQUE, language TEXT,
              runtime_version TEXT, sdk_version TEXT, first_seen TEXT NOT NULL,
              last_seen TEXT NOT NULL, metadata_json TEXT NOT NULL
            );
            INSERT INTO apps(id, service_name, language, runtime_version, sdk_version, first_seen, last_seen, metadata_json)
            VALUES('app-1', 'api', 'python', '3.13', '0.1.0', 'now', 'now', '{}');
            """
        )

    db = Database(db_path)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO apps(id, project_name, service_name, first_seen, last_seen, metadata_json) VALUES(?,?,?,?,?,?)",
            ("app-2", "other", "api", "now", "now", "{}"),
        )
        rows = conn.execute("SELECT id, service_name FROM apps ORDER BY id").fetchall()

    assert [row[0] for row in rows] == ["app-1", "app-2"]


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


def iso_at(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def test_settings_api_validates_and_persists_retention(tmp_path):
    client = make_client(tmp_path)
    login(client)

    assert client.get("/api/settings").json()["retention"]["min_log_minutes"] == 60
    response = client.put("/api/settings", json={"retention": {"retention_days": 14, "min_log_minutes": 120, "exception_window_minutes": 30}})
    assert response.status_code == 200
    assert response.json()["retention"] == {"retention_days": 14, "min_log_minutes": 120, "exception_window_minutes": 30}
    assert client.get("/api/settings").json()["retention"]["retention_days"] == 14
    assert client.put("/api/settings", json={"retention": {"min_log_minutes": 10}}).status_code == 422


def test_cleanup_keeps_last_hour_of_logs_even_with_zero_day_retention(tmp_path):
    db = Database(tmp_path / "collector.sqlite3")
    app_id = "app"
    with db.connect() as conn:
        conn.execute("INSERT INTO apps(id, service_name, first_seen, last_seen, metadata_json) VALUES(?,?,?,?,?)", (app_id, "api", iso_at(timedelta(hours=-2)), iso_at(timedelta()), "{}"))
        conn.execute("INSERT INTO logs(id, app_id, timestamp, structured_json, exception_json, message) VALUES(?,?,?,?,?,?)", ("recent", app_id, iso_at(timedelta(minutes=-30)), "{}", "{}", "recent"))
        conn.execute("INSERT INTO logs(id, app_id, timestamp, structured_json, exception_json, message) VALUES(?,?,?,?,?,?)", ("old", app_id, iso_at(timedelta(minutes=-90)), "{}", "{}", "old"))

    CollectorStore(db).cleanup(0)

    with db.connect() as conn:
        ids = {row["id"] for row in conn.execute("SELECT id FROM logs").fetchall()}
    assert ids == {"recent"}


def test_cleanup_preserves_exception_trace_and_nearby_logs(tmp_path):
    db = Database(tmp_path / "collector.sqlite3")
    app_id = "app"
    old = iso_at(timedelta(days=-2))
    nearby = iso_at(timedelta(days=-2, minutes=5))
    unrelated = iso_at(timedelta(days=-2, hours=2))
    with db.connect() as conn:
        conn.execute("INSERT INTO apps(id, service_name, first_seen, last_seen, metadata_json) VALUES(?,?,?,?,?)", (app_id, "api", old, old, "{}"))
        conn.execute("INSERT INTO exceptions(id, app_id, fingerprint, type, normalized_message, first_seen, last_seen, count, sample_trace_id, sample_payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)", ("exc", app_id, "fp", "ValueError", "boom", old, old, 1, "trace-error", "{}"))
        conn.execute("INSERT INTO traces(id, app_id, started_at, finished_at) VALUES(?,?,?,?)", ("trace-error", app_id, old, old))
        conn.execute("INSERT INTO traces(id, app_id, started_at, finished_at) VALUES(?,?,?,?)", ("trace-old", app_id, old, old))
        conn.execute("INSERT INTO spans(trace_id, app_id, started_at, finished_at, payload_json) VALUES(?,?,?,?,?)", ("trace-error", app_id, old, old, "{}"))
        conn.execute("INSERT INTO events(id, app_id, trace_id, kind, timestamp, payload_json, raw_json) VALUES(?,?,?,?,?,?,?)", ("evt-error", app_id, "trace-error", "log_record", old, "{}", "{}"))
        conn.execute("INSERT INTO events(id, app_id, trace_id, kind, timestamp, payload_json, raw_json) VALUES(?,?,?,?,?,?,?)", ("evt-old", app_id, "trace-old", "log_record", old, "{}", "{}"))
        conn.execute("INSERT INTO logs(id, app_id, trace_id, timestamp, structured_json, exception_json, message) VALUES(?,?,?,?,?,?,?)", ("exact", app_id, "trace-error", old, "{}", "{}", "exact"))
        conn.execute("INSERT INTO logs(id, app_id, timestamp, structured_json, exception_json, message) VALUES(?,?,?,?,?,?)", ("nearby", app_id, nearby, "{}", "{}", "nearby"))
        conn.execute("INSERT INTO logs(id, app_id, timestamp, structured_json, exception_json, message) VALUES(?,?,?,?,?,?)", ("unrelated", app_id, unrelated, "{}", "{}", "unrelated"))

    CollectorStore(db).cleanup(1, exception_window_minutes=10)

    with db.connect() as conn:
        log_ids = {row["id"] for row in conn.execute("SELECT id FROM logs").fetchall()}
        trace_ids = {row["id"] for row in conn.execute("SELECT id FROM traces").fetchall()}
        event_ids = {row["id"] for row in conn.execute("SELECT id FROM events").fetchall()}
    assert log_ids == {"exact", "nearby"}
    assert trace_ids == {"trace-error"}
    assert event_ids == {"evt-error"}


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
    assert response.status_code == 200

    projects = client.get("/api/projects").json()
    assert any(project["project_name"] == "shop" for project in projects)
    assert not any(project["project_name"] == "other" for project in projects)
    keys = client.get("/api/projects/shop/api-keys").json()
    assert keys[0]["prefix"] == created["prefix"]
    assert keys[0]["name"] == "shop"
    assert "api_key" not in keys[0]


def test_delete_project_removes_telemetry_and_keys(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"events": correlated_events()})
    assert response.status_code == 200
    login(client)
    client.post("/api/projects/shop/api-keys")

    response = client.delete("/api/projects/shop")
    assert response.status_code == 200
    assert response.json()["deleted"]["apps"] == 2

    assert all(project["project_name"] != "shop" for project in client.get("/api/projects").json())
    assert all(app["project_name"] != "shop" for app in client.get("/api/apps").json())
    assert client.get("/api/projects/shop/api-keys").json() == []
    assert client.delete("/api/projects/shop").status_code == 404


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


def test_error_dashboard_aggregation_endpoints_respect_scope(tmp_path):
    client = make_client(tmp_path)
    events = [*sample_events(), *correlated_events()]
    response = client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"events": events})
    assert response.status_code == 200
    login(client)

    summary = client.get("/api/errors/summary", params={"log_window_minutes": 0, "project_name": "internal-assistant"}).json()
    assert summary["totals"]["exception_count"] == 1
    assert summary["totals"]["cluster_count"] == 1
    assert summary["by_type"][0]["type"] == "ValueError"
    assert summary["by_service"][0]["service_name"] == "backend"

    clusters = client.get("/api/errors/clusters", params={"project_name": "internal-assistant"}).json()
    assert len(clusters) == 1
    assert clusters[0]["type"] == "ValueError"
    assert clusters[0]["project_name"] == "internal-assistant"

    timeline = client.get("/api/errors/timeline", params={"project_name": "internal-assistant", "window_minutes": 43200, "bucket_minutes": 60}).json()
    assert sum(row["count"] for row in timeline) == 1
    assert timeline[0]["type"] == "ValueError"

    series = client.get("/api/metrics/timeseries", params={"project_name": "shop", "window_minutes": 43200, "bucket_minutes": 60}).json()
    assert sum(row["requests"] for row in series) == 1
    assert sum(row["request_errors"] for row in series) == 1
    assert sum(row["error_logs"] for row in series) == 2

    scoped = client.get("/api/errors/clusters", params={"project_name": "shop"}).json()
    assert scoped == []


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


def semantic_trace_events():
    service = {"project_name": "shop", "name": "api", "display_name": "Shop API", "language": "python"}
    return [
        {"schema_version": "1.0", "event_id": "sem-start", "timestamp": "2026-05-09T22:00:00.000Z", "service": service, "trace_id": "trace-sem", "span_id": "root", "kind": "request_started", "payload": {"method": "GET", "route_pattern": "/orders"}},
        {"schema_version": "1.0", "event_id": "sem-span-start", "timestamp": "2026-05-09T22:00:00.010Z", "service": service, "trace_id": "trace-sem", "span_id": "load-orders", "parent_span_id": "root", "kind": "span_started", "payload": {"name": "load_orders", "kind": "function"}},
        {"schema_version": "1.0", "event_id": "sem-db-1", "timestamp": "2026-05-09T22:00:00.100Z", "service": service, "trace_id": "trace-sem", "span_id": "load-orders", "kind": "db_query", "payload": {"operation": "SELECT orders.items", "table": "order_items", "statement_fingerprint": "SELECT * FROM order_items WHERE order_id=?", "model": "Order", "relationship": "items", "loader_strategy": "lazy", "duration_ms": 30}},
        {"schema_version": "1.0", "event_id": "sem-db-2", "timestamp": "2026-05-09T22:00:00.180Z", "service": service, "trace_id": "trace-sem", "span_id": "load-orders", "kind": "db_query", "payload": {"operation": "SELECT orders.items", "table": "order_items", "statement_fingerprint": "SELECT * FROM order_items WHERE order_id=?", "model": "Order", "relationship": "items", "loader_strategy": "lazy", "duration_ms": 25}},
        {"schema_version": "1.0", "event_id": "sem-db-3", "timestamp": "2026-05-09T22:00:00.260Z", "service": service, "trace_id": "trace-sem", "span_id": "load-orders", "kind": "db_query", "payload": {"operation": "SELECT orders.items", "table": "order_items", "statement_fingerprint": "SELECT * FROM order_items WHERE order_id=?", "model": "Order", "relationship": "items", "loader_strategy": "lazy", "duration_ms": 35}},
        {"schema_version": "1.0", "event_id": "sem-http", "timestamp": "2026-05-09T22:00:01.500Z", "service": service, "trace_id": "trace-sem", "span_id": "load-orders", "kind": "http_client_call", "payload": {"host": "payments.internal", "method": "GET", "duration_ms": 80}},
        {"schema_version": "1.0", "event_id": "sem-span-finish", "timestamp": "2026-05-09T22:00:02.800Z", "service": service, "trace_id": "trace-sem", "span_id": "load-orders", "parent_span_id": "root", "kind": "span_finished", "payload": {"name": "load_orders", "kind": "function", "duration_ms": 2790, "status": "ok"}},
        {"schema_version": "1.0", "event_id": "sem-finish", "timestamp": "2026-05-09T22:00:03.000Z", "service": service, "trace_id": "trace-sem", "span_id": "root", "kind": "request_finished", "payload": {"method": "GET", "route_pattern": "/orders", "duration_ms": 3000, "status_code": 200}},
    ]


def test_trace_map_includes_semantic_groups_gaps_and_duplicates(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"events": semantic_trace_events()})
    assert response.status_code == 200
    login(client)

    trace_map = client.get("/api/traces/trace-sem/map").json()

    assert {"dependency_groups", "relationship_loader_groups", "slow_gap_markers", "duplicate_candidates"} <= set(trace_map)
    assert "flow" in trace_map and "timeline" in trace_map  # existing fields are preserved

    db_group = next(group for group in trace_map["dependency_groups"] if group["dependency_type"] == "db")
    assert db_group["target"] == "order_items"
    assert db_group["operation"] == "SELECT orders.items"
    assert db_group["count"] == 3
    assert db_group["total_duration_ms"] == 90
    assert db_group["span_ids"] == ["load-orders"]

    loader_group = trace_map["relationship_loader_groups"][0]
    assert loader_group["model"] == "Order"
    assert loader_group["relationship"] == "items"
    assert loader_group["loader_strategy"] == "lazy"
    assert loader_group["count"] == 3
    assert loader_group["suspected_n_plus_one"] is True

    duplicate = trace_map["duplicate_candidates"][0]
    assert duplicate["dependency_type"] == "db"
    assert duplicate["count"] == 3
    assert duplicate["event_ids"] == ["sem-db-1", "sem-db-2", "sem-db-3"]

    assert any(marker["from_event_id"] == "sem-db-3" and marker["to_event_id"] == "sem-http" for marker in trace_map["slow_gap_markers"])


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
