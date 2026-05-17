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


def _events_by_project(events: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for event in events:
        service = event.get("service") if isinstance(event, dict) else None
        project = (service or {}).get("project_name") or "default"
        grouped.setdefault(project, []).append(event)
    return grouped


def ingest_per_project(client: TestClient, events: list[dict], *, login_first: bool = True) -> dict[str, str]:
    """Ingest events using a per-project API key for each distinct project_name.

    Requires the dashboard admin session so /api/projects/.../api-keys is reachable.
    Returns a mapping of project_name -> api_key for follow-up assertions.
    """
    if login_first:
        login(client)
    keys: dict[str, str] = {}
    for project, project_events in _events_by_project(events).items():
        keys[project] = client.post(f"/api/projects/{project}/api-keys").json()["api_key"]
        response = client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {keys[project]}"},
            json={"events": project_events},
        )
        assert response.status_code == 200, response.text
    return keys


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


def test_project_group_can_be_set_when_creating_key_and_updated(tmp_path):
    client = make_client(tmp_path)
    login(client)

    response = client.post("/api/projects/shop/api-keys", json={"group_name": "production"})
    assert response.status_code == 200
    assert response.json()["group_name"] == "production"
    projects = client.get("/api/projects").json()
    assert projects[0]["project_name"] == "shop"
    assert projects[0]["group_name"] == "production"

    update = client.put("/api/projects/shop/settings", json={"group_name": "work"})
    assert update.status_code == 200
    assert update.json()["group_name"] == "work"
    projects = client.get("/api/projects").json()
    assert projects[0]["group_name"] == "work"


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
    apps = client.get("/api/apps").json()
    assert all(app["project_name"] == "shop" for app in apps)
    assert any(app["service_name"] == wrong_project_event["service"]["name"] for app in apps)
    keys = client.get("/api/projects/shop/api-keys").json()
    assert keys[0]["prefix"] == created["prefix"]
    assert keys[0]["name"] == "shop"
    assert "api_key" not in keys[0]


def test_ingest_rejects_missing_invalid_and_admin_keys(tmp_path):
    """Ingest must require a valid project API key — no header, bad key, and the admin key all 401."""
    client = make_client(tmp_path)
    events = sample_events()

    # No Authorization header
    assert client.post("/v1/ingest", json={"events": events}).status_code == 401
    # Garbage token
    assert client.post(
        "/v1/ingest",
        headers={"Authorization": "Bearer not-a-real-key"},
        json={"events": events},
    ).status_code == 401
    # Legacy collector-wide admin key is rejected for ingest
    assert client.post(
        "/v1/ingest",
        headers={"Authorization": "Bearer test-key"},
        json={"events": events},
    ).status_code == 401

    # And none of those rejected requests created a project entry in the dashboard.
    login(client)
    assert client.get("/api/projects").json() == []
    assert client.get("/api/apps").json() == []


def test_insecure_dev_still_requires_project_key_for_ingest(tmp_path):
    client = make_insecure_client(tmp_path)

    assert client.post("/v1/ingest", json={"events": sample_events()}).status_code == 401
    assert client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"events": sample_events()}).status_code == 401
    assert client.get("/api/projects").json() == []
    assert client.get("/api/apps").json() == []


def test_projects_endpoint_hides_unregistered_projects(tmp_path):
    """A project_name with apps but no registered API key must not appear in the dashboard."""
    client = make_client(tmp_path)
    login(client)
    # Seed `apps` directly to mimic legacy / leaked data that landed before key enforcement.
    settings = Settings(api_key="test-key", dashboard_username="admin", dashboard_password="secret", database_path=tmp_path / "collector.sqlite3")
    db = Database(settings.database_path)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO apps(id, project_name, service_name, first_seen, last_seen, metadata_json) VALUES(?,?,?,?,?,?)",
            ("ghost-app", "ghost-project", "ghost", "now", "now", "{}"),
        )

    assert all(p["project_name"] != "ghost-project" for p in client.get("/api/projects").json())
    assert all(a["project_name"] != "ghost-project" for a in client.get("/api/apps").json())


def test_delete_project_removes_telemetry_and_keys(tmp_path):
    client = make_client(tmp_path)
    ingest_per_project(client, correlated_events())

    response = client.delete("/api/projects/shop")
    assert response.status_code == 200
    assert response.json()["deleted"]["apps"] == 2

    assert all(project["project_name"] != "shop" for project in client.get("/api/projects").json())
    assert all(app["project_name"] != "shop" for app in client.get("/api/apps").json())
    assert client.get("/api/projects/shop/api-keys").json() == []
    assert client.delete("/api/projects/shop").status_code == 404


def test_correlated_logs_level_filtering_and_app_project_scope(tmp_path):
    client = make_client(tmp_path)
    ingest_per_project(client, correlated_events())
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
    ingest_per_project(client, [*sample_events(), *correlated_events()])

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
    # Legacy collector-wide admin key must be rejected for ingest — only project API keys authorize.
    assert client.post("/v1/ingest", headers={"Authorization": "Bearer test-key"}, json={"events": sample_events()}).status_code == 401
    assert client.get("/api/apps").status_code == 401

    login(client)
    project_key = client.post("/api/projects/internal-assistant/api-keys").json()["api_key"]
    response = client.post(
        "/v1/ingest",
        headers={"Authorization": f"Bearer {project_key}"},
        json={"batch_id": "batch-1", "events": sample_events()},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == len(sample_events())

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


def http_dep_events():
    service = {"project_name": "internal-assistant", "name": "client", "display_name": "Client", "language": "python"}
    base = {"schema_version": "1.0", "service": service, "kind": "http_client_call"}
    calls = [
        ("dep-1", "2026-05-09T22:00:00.000Z", "/v1/agents", 200, 80.0),
        ("dep-2", "2026-05-09T22:00:01.000Z", "/v1/agents", 200, 120.0),
        ("dep-3", "2026-05-09T22:00:02.000Z", "/v1/agents/42", 200, 60.0),
        ("dep-4", "2026-05-09T22:00:03.000Z", "/v1/agents/42", 304, 20.0),
        ("dep-5", "2026-05-09T22:00:04.000Z", "/v1/health", 200, 10.0),
        ("dep-6", "2026-05-09T22:00:05.000Z", "/v1/agents/missing", 404, 30.0),
        ("dep-7", "2026-05-09T22:00:06.000Z", "/v1/agents", 500, 200.0),
        ("dep-8", "2026-05-09T22:00:07.000Z", "/v1/agents", 200, 95.0),
    ]
    return [{**base, "event_id": evt_id, "timestamp": ts, "trace_id": f"trace-{evt_id}", "payload": {"method": "GET", "host": "lx-internal-agents.example.com", "target": "lx-internal-agents.example.com", "path": path, "status_code": status, "duration_ms": ms}} for evt_id, ts, path, status, ms in calls]


def test_dependency_context_returns_stats_distribution_paths_and_samples(tmp_path):
    client = make_client(tmp_path)
    ingest_per_project(client, http_dep_events())

    apps = client.get("/api/apps").json()
    app_id = apps[0]["id"]
    deps = client.get(f"/api/apps/{app_id}/dependencies").json()
    http_dep = next(dep for dep in deps if dep["dependency_type"] == "http")

    ctx = client.get(f"/api/dependencies/{http_dep['id']}/context").json()

    assert ctx["dependency"]["target"] == "lx-internal-agents.example.com"
    assert len(ctx["samples"]) == 8

    stats = ctx["stats"]
    assert stats["count"] == 8
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 200.0
    assert stats["avg_ms"] > 0
    assert stats["p50_ms"] > 0
    assert stats["p95_ms"] > 0
    assert stats["calls_per_min"] > 0

    dist = {entry["bucket"]: entry["count"] for entry in ctx["status_distribution"]}
    assert dist == {"2xx": 5, "3xx": 1, "4xx": 1, "5xx": 1}

    paths = {entry["path"]: entry for entry in ctx["top_paths"]}
    assert paths["/v1/agents"]["count"] == 4
    assert paths["/v1/agents/42"]["count"] == 2
    assert paths["/v1/agents"]["error_count"] == 1
    assert paths["/v1/agents"]["avg_ms"] > 0
    assert paths["/v1/agents"]["p95_ms"] > 0
    assert paths["/v1/health"]["error_count"] == 0

    assert isinstance(ctx["time_series"], list)
    assert all({"bucket_start", "call_count", "avg_ms"} <= set(point.keys()) for point in ctx["time_series"])
    assert sum(point["call_count"] for point in ctx["time_series"]) == 8


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
    ingest_per_project(client, semantic_trace_events())

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
    project_key = client.post("/api/projects/internal-assistant/api-keys").json()["api_key"]
    response = client.post("/v1/ingest", headers={"Authorization": f"Bearer {project_key}"}, json={"events": sample_events()})
    assert response.status_code == 200

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


def _provision_agent_project(tmp_path, project: str = "shop") -> tuple[TestClient, str]:
    client = make_client(tmp_path)
    keys = ingest_per_project(client, correlated_events())
    return client, keys[project]


def test_agent_api_rejects_missing_or_invalid_keys(tmp_path):
    client, _ = _provision_agent_project(tmp_path)
    assert client.get("/v1/agent/info").status_code == 401
    assert client.get("/v1/agent/info", headers={"Authorization": "Bearer not-a-key"}).status_code == 401
    # Legacy collector-wide admin key must be rejected for the agent API
    assert client.get("/v1/agent/info", headers={"Authorization": "Bearer test-key"}).status_code == 401


def test_agent_api_info_apps_and_routes_are_project_scoped(tmp_path):
    client, shop_key = _provision_agent_project(tmp_path, "shop")
    info = client.get("/v1/agent/info", headers={"Authorization": f"Bearer {shop_key}"}).json()
    assert info["project_name"] == "shop"
    services = {app["service_name"] for app in info["apps"]}
    assert services == {"backend", "worker"}

    apps = client.get("/v1/agent/apps", headers={"Authorization": f"Bearer {shop_key}"}).json()
    assert {app["service_name"] for app in apps} == {"backend", "worker"}
    assert all(app["project_name"] == "shop" for app in apps)

    routes = client.get("/v1/agent/routes", headers={"Authorization": f"Bearer {shop_key}"}).json()
    assert all(route.get("service_name") in {"backend", "worker"} for route in routes)


def test_agent_api_logs_and_exceptions_are_filterable(tmp_path):
    client, shop_key = _provision_agent_project(tmp_path, "shop")
    auth = {"Authorization": f"Bearer {shop_key}"}

    all_logs = client.get("/v1/agent/logs", headers=auth).json()
    messages = {log["message"] for log in all_logs}
    assert "checkout started" in messages
    assert "payment failed" in messages
    assert "other project noise" not in messages

    error_logs = client.get("/v1/agent/logs", headers=auth, params={"level": "ERROR"}).json()
    assert {log["message"] for log in error_logs} == {"payment failed", "retry queued"}

    search_hits = client.get("/v1/agent/search", headers=auth, params={"q": "payment", "window_minutes": 43200}).json()
    assert any("payment" in log["message"] for log in search_hits["logs"])

    trace = client.get("/v1/agent/traces/trace-corr", headers=auth).json()
    assert trace["trace_id"] == "trace-corr"
    assert any(log.get("message") == "payment failed" for log in trace["logs"])

    context = client.get("/v1/agent/traces/trace-corr/context", headers=auth).json()
    assert "trace-corr" in context["text"]


def test_agent_api_rejects_cross_project_trace_lookup(tmp_path):
    # Provision both projects so other-project data exists
    client = make_client(tmp_path)
    keys = ingest_per_project(client, correlated_events())
    shop_key = keys["shop"]
    other_key = keys["other"]

    # `other` project has no trace-corr — must 404 even though it exists in `shop`
    other_lookup = client.get("/v1/agent/traces/trace-corr", headers={"Authorization": f"Bearer {other_key}"})
    assert other_lookup.status_code == 404

    shop_lookup = client.get("/v1/agent/traces/trace-corr", headers={"Authorization": f"Bearer {shop_key}"})
    assert shop_lookup.status_code == 200
