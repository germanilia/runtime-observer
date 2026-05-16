from __future__ import annotations
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from starlette.requests import ClientDisconnect
from .config import Settings
from .dashboard import DASHBOARD_HTML
from .db import Database
from .ingest_queue import IngestQueueError
from .store import now_iso, row_to_dict, rows_to_dicts, stable_id
def get_db(request: Request) -> Database:
    return request.app.state.database
def get_settings(request: Request) -> Settings:
    return request.app.state.settings
SESSION_COOKIE = "runtime_observer_session"
SESSION_DAYS = 7
def _api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
def _project_from_api_key(api_key: str, db: Database, settings: Settings) -> str | None:
    if settings.api_key and hmac.compare_digest(api_key, settings.api_key):
        return None
    key_hash = _api_key_hash(api_key)
    now = iso(datetime.now(UTC))
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, project_name FROM project_api_keys WHERE key_hash=? AND revoked_at IS NULL",
            (key_hash,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid Runtime Observer API key")
        conn.execute("UPDATE project_api_keys SET last_used_at=? WHERE id=?", (now, row["id"]))
        return str(row["project_name"])
def _event_projects(events: list[dict[str, Any]]) -> set[str]:
    projects: set[str] = set()
    for event in events:
        service = event.get("service") if isinstance(event, dict) else None
        if isinstance(service, dict):
            projects.add(str(service.get("project_name") or "default"))
    return projects
def require_ingest_auth(events: list[dict[str, Any]], request: Request, api_key: str | None = None, db: Database | None = None, settings: Settings | None = None) -> str | None:
    resolved_settings = settings or request.app.state.settings
    if resolved_settings.insecure_dev_mode:
        return None
    token = api_key or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Runtime Observer API key is required")
    return _project_from_api_key(token, db or request.app.state.database, resolved_settings)


def apply_project_scope(events: list[dict[str, Any]], project_name: str | None) -> list[dict[str, Any]]:
    if project_name is None:
        return events
    scoped_events: list[dict[str, Any]] = []
    for event in events:
        service = event.get("service") if isinstance(event, dict) else None
        service_data = dict(service) if isinstance(service, dict) else {}
        service_data["project_name"] = project_name
        scoped_events.append({**event, "service": service_data})
    return scoped_events
def require_bearer(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if settings.insecure_dev_mode:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {settings.api_key}":
        raise HTTPException(status_code=401, detail="Invalid Runtime Observer API key")

def _password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 210_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"

def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    return hmac.compare_digest(_password_hash(password, salt), stored_hash)

def session_user(request: Request, db: Database) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    now = iso(datetime.now(UTC))
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT users.id, users.username, users.role, sessions.expires_at
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.id=? AND sessions.expires_at > ?
            """,
            (token, now),
        ).fetchone()
        return row_to_dict(row)

def require_session(request: Request, db: Database = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    if settings.insecure_dev_mode:
        username = request.headers.get("X-Runtime-Observer-User") or "dev"
        return {"id": username, "username": username, "role": "admin"}
    user = session_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def scalar(row: object, key: str | None = None) -> object:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key or next(iter(row)))
    return row[0]  # type: ignore[index]

def current_user(user: dict[str, Any] = Depends(require_session)) -> str:
    return str(user["id"])

def hidden_preference_clause(alias: str, target_kind: str, user_id: str, app_column: str | None = None) -> tuple[str, list[Any]]:
    app_match = f" AND (user_preferences.app_id IS NULL OR user_preferences.app_id='' OR user_preferences.app_id={app_column})" if app_column else ""
    return (
        f"NOT EXISTS (SELECT 1 FROM user_preferences WHERE user_preferences.user_id=? "
        f"AND user_preferences.preference_type='hidden' AND user_preferences.target_kind=? "
        f"AND user_preferences.target_id={alias}.id{app_match})",
        [user_id, target_kind],
    )

def hidden_route_clause(user_id: str, route_column: str = "routes.id", app_column: str = "routes.app_id") -> tuple[str, list[Any]]:
    return (
        "NOT EXISTS (SELECT 1 FROM user_preferences WHERE user_preferences.user_id=? "
        "AND user_preferences.preference_type='hidden' AND user_preferences.target_kind='route' "
        f"AND user_preferences.target_id={route_column} "
        f"AND (user_preferences.app_id IS NULL OR user_preferences.app_id='' OR user_preferences.app_id={app_column}))",
        [user_id],
    )

def visible_apps_clause(user_id: str, alias: str = "apps") -> tuple[str, list[Any]]:
    return hidden_preference_clause(alias, "app", user_id)

def log_window_start(log_window_minutes: int | None) -> str | None:
    if not log_window_minutes or log_window_minutes <= 0:
        return None
    return iso(datetime.now(UTC) - timedelta(minutes=log_window_minutes))


def scoped_apps_filter(user_id: str, *, project_name: str | None = None, app_id: str | None = None, alias: str = "apps") -> tuple[str, list[Any]]:
    clause, params = visible_apps_clause(user_id, alias)
    parts = [clause]
    if project_name:
        parts.append(f"{alias}.project_name=?")
        params.append(project_name)
    if app_id:
        parts.append(f"{alias}.id=?")
        params.append(app_id)
    return " AND ".join(parts), params

def time_bucket(column: str, bucket_minutes: int, *, is_postgres: bool = False) -> str:
    bucket_seconds = max(60, min(bucket_minutes, 1440) * 60)
    if is_postgres:
        return (
            "to_char(to_timestamp((floor(extract(epoch from "
            f"{column}::timestamptz) / {bucket_seconds}) * {bucket_seconds})) "
            "AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')"
        )
    return f"strftime('%Y-%m-%dT%H:%M:%SZ', (CAST(strftime('%s', {column}) AS INTEGER) / {bucket_seconds}) * {bucket_seconds}, 'unixepoch')"


def json_text(column: str, key: str, *, is_postgres: bool = False) -> str:
    if is_postgres:
        return f"({column}::jsonb ->> '{key}')"
    return f"json_extract({column}, '$.{key}')"

def generate_project_api_key() -> tuple[str, str]:
    key_id = secrets.token_hex(4)
    secret = secrets.token_urlsafe(24)
    return f"ro_{key_id}_{secret}", f"ro_{key_id}"

RETENTION_SETTING_KEY = "retention"


def default_retention_settings(settings: Settings) -> dict[str, int]:
    return {
        "retention_days": settings.retention_days,
        "min_log_minutes": settings.retention_min_log_minutes,
        "exception_window_minutes": settings.retention_exception_window_minutes,
    }


def read_retention_settings(conn, settings: Settings) -> dict[str, int]:
    values = default_retention_settings(settings)
    row = conn.execute("SELECT value_json FROM collector_settings WHERE key=?", (RETENTION_SETTING_KEY,)).fetchone()
    if row:
        try:
            stored = json.loads(row["value_json"] or "{}")
        except json.JSONDecodeError:
            stored = {}
        for key in values:
            if key in stored:
                try:
                    values[key] = int(stored[key])
                except (TypeError, ValueError):
                    continue
    return values


def validate_retention_settings(body: dict[str, Any], settings: Settings) -> dict[str, int]:
    values = default_retention_settings(settings)
    aliases = {"retention_days": "retention_days", "days": "retention_days", "min_log_minutes": "min_log_minutes", "exception_window_minutes": "exception_window_minutes"}
    for source, target in aliases.items():
        if source in body:
            try:
                values[target] = int(body[source])
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{target} must be an integer") from None
    limits = {"retention_days": (1, 3650), "min_log_minutes": (60, 10080), "exception_window_minutes": (0, 10080)}
    for key, (minimum, maximum) in limits.items():
        if values[key] < minimum or values[key] > maximum:
            raise HTTPException(status_code=422, detail=f"{key} must be between {minimum} and {maximum}")
    return values

def _delete_project(conn, project_name: str) -> dict[str, int]:
    app_ids = [str(row["id"]) for row in conn.execute("SELECT id FROM apps WHERE project_name=?", (project_name,)).fetchall()]
    deleted = {"apps": 0, "events": 0, "routes": 0, "logs": 0, "api_keys": 0}
    if app_ids:
        placeholders = ",".join("?" for _ in app_ids)
        route_ids = [str(row["id"]) for row in conn.execute(f"SELECT id FROM routes WHERE app_id IN ({placeholders})", app_ids).fetchall()]
        dependency_ids = [str(row["id"]) for row in conn.execute(f"SELECT id FROM dependencies WHERE app_id IN ({placeholders})", app_ids).fetchall()]
        if route_ids:
            route_placeholders = ",".join("?" for _ in route_ids)
            conn.execute(f"DELETE FROM route_durations WHERE route_id IN ({route_placeholders})", route_ids)
        if dependency_ids:
            dep_placeholders = ",".join("?" for _ in dependency_ids)
            conn.execute(f"DELETE FROM dependency_durations WHERE dependency_id IN ({dep_placeholders})", dependency_ids)
        for table in ("events", "traces", "spans", "exceptions", "logs", "routes", "dependencies", "llm_usage"):
            cursor = conn.execute(f"DELETE FROM {table} WHERE app_id IN ({placeholders})", app_ids)
            if table in deleted:
                deleted[table] = cursor.rowcount
        cursor = conn.execute(f"DELETE FROM user_preferences WHERE project_name=? OR app_id IN ({placeholders})", [project_name, *app_ids])
        deleted["preferences"] = cursor.rowcount
        deleted["apps"] = conn.execute(f"DELETE FROM apps WHERE id IN ({placeholders})", app_ids).rowcount
    else:
        deleted["preferences"] = conn.execute("DELETE FROM user_preferences WHERE project_name=?", (project_name,)).rowcount
    deleted["settings"] = conn.execute("DELETE FROM project_settings WHERE project_name=?", (project_name,)).rowcount
    deleted["api_keys"] = conn.execute("DELETE FROM project_api_keys WHERE project_name=?", (project_name,)).rowcount
    return deleted

def _dependency_key_from_event(event: dict[str, Any]) -> tuple[str, str, str, str] | None:
    try:
        payload = json.loads(event.get("payload_json") or "{}")
    except json.JSONDecodeError:
        payload = {}
    kind = event.get("kind")
    if kind == "db_query":
        tables = payload.get("tables") if isinstance(payload.get("tables"), list) else []
        target = payload.get("target") or payload.get("database") or payload.get("table") or (tables[0] if tables else None) or "unknown-db"
        operation = payload.get("operation") or payload.get("statement_fingerprint") or "query"
        return (str(event.get("app_id")), "db", str(target), str(operation))
    if kind == "http_client_call":
        return (str(event.get("app_id")), "http", str(payload.get("host") or payload.get("url") or "unknown"), str(payload.get("method") or "GET"))
    if kind == "llm_call":
        return (str(event.get("app_id")), "llm", str(payload.get("provider") or "unknown"), str(payload.get("model") or "unknown"))
    return None

def enrich_dependencies(conn, dependencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not dependencies:
        return dependencies
    samples = rows_to_dicts(
        conn.execute(
            """
            SELECT events.id, events.app_id, events.trace_id, events.span_id,
              events.parent_span_id, events.kind, events.timestamp,
              events.payload_json, apps.service_name
            FROM events JOIN apps ON apps.id = events.app_id
            WHERE events.kind IN ('db_query','http_client_call','llm_call')
            ORDER BY events.timestamp DESC LIMIT 1000
            """
        ).fetchall()
    )
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for sample in samples:
        key = _dependency_key_from_event(sample)
        if key and key not in by_key:
            try:
                payload = json.loads(sample.get("payload_json") or "{}")
            except json.JSONDecodeError:
                payload = {}
            by_key[key] = {"timestamp": sample.get("timestamp"), "trace_id": sample.get("trace_id"), "payload": payload}
    for dep in dependencies:
        key = (str(dep.get("app_id")), str(dep.get("dependency_type")), str(dep.get("target")), str(dep.get("operation")))
        sample = by_key.get(key)
        if sample:
            dep["last_sample"] = sample
    return dependencies

def _payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(row.get("payload_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _duration_from_payload(payload: dict[str, Any]) -> float | None:
    for key in ("duration_ms", "duration"):
        value = payload.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _short(value: Any, limit: int = 500) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    if isinstance(value, list):
        return [_short(item, limit) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key): _short(item, limit) for key, item in list(value.items())[:40]}
    return value


def _compact_payload(kind: str, payload_json: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(payload_json or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        return {}
    keep_by_kind = {
        "db_query": {"operation", "statement_fingerprint", "statement_template", "tables", "target", "database", "table", "duration_ms", "row_count", "parameters", "route_id", "route_pattern", "error_type", "error_message", "source_file", "source_function", "source_line", "model", "relationship", "loader_strategy"},
        "http_client_call": {"method", "host", "url", "target", "status_code", "duration_ms", "error_type", "error_message"},
        "llm_call": {"provider", "model", "streaming", "duration_ms", "input_tokens", "output_tokens", "total_tokens", "tool_call_names", "error_type", "error_message"},
        "log_record": {"level", "logger_name", "message", "source_file", "source_function", "source_line"},
        "exception_raised": {"type", "message", "fingerprint", "method", "route_pattern", "route_id", "status_code"},
        "request_started": {"method", "path", "route_pattern", "route_id", "correlation_id"},
        "request_finished": {"method", "path", "route_pattern", "route_id", "status_code", "duration_ms", "request_bytes", "response_bytes", "correlation_id"},
        "span_started": {"name", "kind", "attributes"},
        "span_finished": {"name", "kind", "duration_ms", "status", "route_id", "error_type"},
        "route_discovered": {"method", "route_pattern", "route_id"},
    }
    keep = keep_by_kind.get(kind, set(payload.keys()))
    return {key: _short(payload[key]) for key in keep if key in payload and payload[key] is not None}


def _compact_trace_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted = []
    for row in rows:
        item = {key: value for key, value in row.items() if key != "raw_json"}
        payload = _compact_payload(str(item.get("kind") or ""), item.get("payload_json"))
        item["payload_json"] = json.dumps(payload, separators=(",", ":"))
        for key in ("message", "name", "target", "operation"):
            if key in payload and key not in item:
                item[key] = payload[key]
        compacted.append(item)
    return compacted


def _dependency_signature(event: dict[str, Any]) -> dict[str, Any]:
    payload = _payload_from_row(event)
    kind = str(event.get("kind") or "unknown")
    if kind == "db_query":
        tables = payload.get("tables") if isinstance(payload.get("tables"), list) else []
        return {
            "type": "db",
            "target": str(payload.get("target") or payload.get("database") or payload.get("table") or (tables[0] if tables else None) or "unknown-db"),
            "operation": str(payload.get("operation") or payload.get("statement_fingerprint") or payload.get("query_fingerprint") or "query"),
        }
    if kind == "http_client_call":
        return {"type": "http", "target": str(payload.get("host") or payload.get("url") or "unknown"), "operation": str(payload.get("method") or "GET")}
    if kind == "llm_call":
        return {"type": "llm", "target": str(payload.get("provider") or "unknown"), "operation": str(payload.get("model") or "unknown")}
    return {"type": kind, "target": "unknown", "operation": kind}


def build_dependency_groups(dependencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in dependencies:
        signature = _dependency_signature(event)
        key = (signature["type"], signature["target"], signature["operation"])
        payload = _payload_from_row(event)
        duration_ms = _duration_from_payload(payload)
        group = grouped.setdefault(
            key,
            {
                "id": stable_id("dependency_group", *key),
                "dependency_type": signature["type"],
                "target": signature["target"],
                "operation": signature["operation"],
                "count": 0,
                "event_ids": [],
                "span_ids": [],
                "first_timestamp": event.get("timestamp"),
                "last_timestamp": event.get("timestamp"),
                "total_duration_ms": 0.0,
                "max_duration_ms": None,
            },
        )
        group["count"] += 1
        group["event_ids"].append(event.get("id"))
        if event.get("span_id") and event.get("span_id") not in group["span_ids"]:
            group["span_ids"].append(event.get("span_id"))
        if event.get("timestamp"):
            group["first_timestamp"] = min(str(group["first_timestamp"] or event["timestamp"]), str(event["timestamp"]))
            group["last_timestamp"] = max(str(group["last_timestamp"] or event["timestamp"]), str(event["timestamp"]))
        if duration_ms is not None:
            group["total_duration_ms"] += duration_ms
            group["max_duration_ms"] = duration_ms if group["max_duration_ms"] is None else max(float(group["max_duration_ms"]), duration_ms)
    return sorted(grouped.values(), key=lambda item: (-int(item["count"]), str(item["dependency_type"]), str(item["target"]), str(item["operation"])))


def build_relationship_loader_groups(dependencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for event in dependencies:
        if event.get("kind") != "db_query":
            continue
        payload = _payload_from_row(event)
        signature = _dependency_signature(event)
        relationship = payload.get("relationship") or payload.get("relationship_name") or payload.get("orm_relationship")
        model = payload.get("model") or payload.get("entity") or payload.get("orm_model") or payload.get("source_model")
        loader_strategy = payload.get("loader_strategy") or payload.get("load_strategy") or ("lazy" if payload.get("lazy_load") else None)
        if not any([relationship, model, loader_strategy]) and not payload.get("statement_fingerprint") and not payload.get("query_fingerprint"):
            continue
        key = (str(model or "unknown-model"), str(relationship or signature["target"]), str(loader_strategy or "unknown-loader"), str(signature["operation"]))
        duration_ms = _duration_from_payload(payload)
        group = grouped.setdefault(
            key,
            {
                "id": stable_id("relationship_loader_group", *key),
                "model": key[0],
                "relationship": key[1],
                "loader_strategy": key[2],
                "operation": key[3],
                "count": 0,
                "event_ids": [],
                "span_ids": [],
                "total_duration_ms": 0.0,
                "suspected_n_plus_one": False,
            },
        )
        group["count"] += 1
        group["event_ids"].append(event.get("id"))
        if event.get("span_id") and event.get("span_id") not in group["span_ids"]:
            group["span_ids"].append(event.get("span_id"))
        if duration_ms is not None:
            group["total_duration_ms"] += duration_ms
    for group in grouped.values():
        group["suspected_n_plus_one"] = int(group["count"]) >= 3 and str(group["loader_strategy"]).lower() in {"lazy", "select", "unknown-loader"}
    return sorted(grouped.values(), key=lambda item: (-int(item["count"]), str(item["model"]), str(item["relationship"])))


def build_duplicate_candidates(dependencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for group in build_dependency_groups(dependencies):
        if int(group["count"]) < 2:
            continue
        candidates.append(
            {
                "id": stable_id("duplicate_candidate", group["dependency_type"], group["target"], group["operation"]),
                "dependency_type": group["dependency_type"],
                "target": group["target"],
                "operation": group["operation"],
                "count": group["count"],
                "event_ids": group["event_ids"],
                "span_ids": group["span_ids"],
                "total_duration_ms": group["total_duration_ms"],
                "reason": "same dependency signature repeated within trace",
            }
        )
    return candidates


def build_slow_gap_markers(timeline: list[dict[str, Any]], traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points = [(parse_ts(str(item.get("timestamp"))), item) for item in timeline if item.get("timestamp")]
    points = [(ts, item) for ts, item in points if ts is not None]
    if len(points) < 2:
        return []
    trace_duration = max((float(trace.get("duration_ms") or 0) for trace in traces), default=0.0)
    threshold_ms = max(100.0, min(500.0, trace_duration * 0.2 if trace_duration else 500.0))
    markers: list[dict[str, Any]] = []
    for (prev_ts, prev_item), (next_ts, next_item) in zip(points, points[1:]):
        gap_ms = (next_ts - prev_ts).total_seconds() * 1000
        if gap_ms >= threshold_ms:
            markers.append(
                {
                    "id": stable_id("slow_gap", prev_item.get("id"), next_item.get("id"), gap_ms),
                    "gap_ms": gap_ms,
                    "threshold_ms": threshold_ms,
                    "from_timestamp": iso(prev_ts),
                    "to_timestamp": iso(next_ts),
                    "from_event_id": prev_item.get("id"),
                    "to_event_id": next_item.get("id"),
                    "from_kind": prev_item.get("kind"),
                    "to_kind": next_item.get("kind"),
                }
            )
    return markers


def logs_around(conn, timestamp: str | None, *, trace_id: str | None = None, window_seconds: int = 120, limit: int = 250) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    parsed = parse_ts(timestamp)
    if parsed:
        where.append("timestamp BETWEEN ? AND ?")
        params.extend([iso(parsed - timedelta(seconds=window_seconds)), iso(parsed + timedelta(seconds=window_seconds))])
    if trace_id:
        where.append("(trace_id=? OR trace_id IS NULL)")
        params.append(trace_id)
    params.append(limit)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    return rows_to_dicts(
        conn.execute(
            f"""
            SELECT logs.*, apps.service_name
            FROM logs JOIN apps ON apps.id = logs.app_id
            {clause}
            ORDER BY timestamp DESC LIMIT ?
            """,
            params,
        ).fetchall()
    )

def create_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/auth/login")
    async def login(request: Request, response: Response, db: Database = Depends(get_db)) -> dict[str, Any]:
        body = await request.json()
        username = str(body.get("username") or "").strip()
        password = str(body.get("password") or "")
        if not username or not password:
            raise HTTPException(status_code=422, detail="username and password are required")
        now = iso(datetime.now(UTC))
        expires_at = iso(datetime.now(UTC) + timedelta(days=SESSION_DAYS))
        with db.connect() as conn:
            user_count = scalar(conn.execute("SELECT COUNT(*) AS count FROM users").fetchone(), "count")
            if user_count == 0:
                user_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO users (id, username, password_hash, role, created_at, last_login_at) VALUES (?, ?, ?, 'admin', ?, ?)",
                    (user_id, username, _password_hash(password), now, now),
                )
                user = {"id": user_id, "username": username, "role": "admin"}
            else:
                row = conn.execute("SELECT id, username, password_hash, role FROM users WHERE username=?", (username,)).fetchone()
                if not row or not _verify_password(password, row["password_hash"]):
                    raise HTTPException(status_code=401, detail="Invalid username or password")
                user = {"id": row["id"], "username": row["username"], "role": row["role"]}
                conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now, user["id"]))
            token = secrets.token_urlsafe(32)
            conn.execute("INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)", (token, user["id"], now, expires_at))
        response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_DAYS * 24 * 60 * 60)
        return {"user": {"username": user["username"], "role": user["role"]}}

    @router.post("/api/auth/logout")
    def logout(request: Request, response: Response, db: Database = Depends(get_db)) -> dict[str, str]:
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            with db.connect() as conn:
                conn.execute("DELETE FROM sessions WHERE id=?", (token,))
        response.delete_cookie(SESSION_COOKIE)
        return {"status": "logged_out"}

    @router.get("/api/auth/me")
    def me(request: Request, db: Database = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        if settings.insecure_dev_mode:
            return {"user": {"username": "dev", "role": "admin"}}
        user = session_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"user": {"username": user["username"], "role": user["role"]}}

    @router.post("/v1/ingest")
    async def ingest(request: Request, db: Database = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        try:
            body = await request.json()
        except ClientDisconnect as exc:
            raise HTTPException(status_code=400, detail="client disconnected before request body was read") from exc
        events = body.get("events")
        if not isinstance(events, list):
            raise HTTPException(status_code=422, detail="events must be a list")
        project_name = require_ingest_auth(events, request, db=db, settings=settings)
        scoped_events = apply_project_scope(events, project_name)
        try:
            return request.app.state.ingest_backend.enqueue(scoped_events).to_response()
        except IngestQueueError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @router.post("/v1/ingest/browser")
    async def ingest_browser(request: Request, api_key: str = "", db: Database = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        try:
            body = await request.json()
        except ClientDisconnect as exc:
            raise HTTPException(status_code=400, detail="client disconnected before request body was read") from exc
        events = body.get("events")
        if not isinstance(events, list):
            raise HTTPException(status_code=422, detail="events must be a list")
        project_name = require_ingest_auth(events, request, api_key=api_key, db=db, settings=settings)
        scoped_events = apply_project_scope(events, project_name)
        try:
            return request.app.state.ingest_backend.enqueue(scoped_events).to_response()
        except IngestQueueError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @router.get("/api/settings")
    def get_collector_settings(db: Database = Depends(get_db), settings: Settings = Depends(get_settings), user_id: str = Depends(current_user)) -> dict[str, Any]:
        with db.connect() as conn:
            retention = read_retention_settings(conn, settings)
        return {"retention": retention}

    @router.put("/api/settings")
    async def put_collector_settings(request: Request, db: Database = Depends(get_db), settings: Settings = Depends(get_settings), user_id: str = Depends(current_user)) -> dict[str, Any]:
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="settings body must be an object")
        retention_body = body.get("retention") if isinstance(body.get("retention"), dict) else body
        retention = validate_retention_settings(retention_body, settings)
        timestamp = now_iso()
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO collector_settings(key, value_json, updated_at, updated_by) VALUES(?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at, updated_by=excluded.updated_by
                """,
                (RETENTION_SETTING_KEY, json.dumps(retention, separators=(",", ":")), timestamp, user_id),
            )
        return {"retention": retention}

    @router.get("/api/preferences/hidden")
    def get_hidden_preferences(app_id: str | None = None, target_kind: str | None = None, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        where = ["user_id=?", "preference_type='hidden'"]
        params: list[Any] = [user_id]
        if app_id:
            where.append("(app_id=? OR app_id IS NULL OR app_id='')")
            params.append(app_id)
        if target_kind:
            where.append("target_kind=?")
            params.append(target_kind)
        with db.connect() as conn:
            return rows_to_dicts(conn.execute(f"SELECT * FROM user_preferences WHERE {' AND '.join(where)} ORDER BY updated_at DESC", params).fetchall())

    @router.post("/api/preferences/hidden")
    async def hide_preference(request: Request, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, Any]:
        body = await request.json()
        target_kind = str(body.get("target_kind") or "").strip()
        target_id = str(body.get("target_id") or "").strip()
        app_id = body.get("app_id") or ""
        project_name = body.get("project_name") or ""
        if not target_kind or not target_id:
            raise HTTPException(status_code=422, detail="target_kind and target_id are required")
        timestamp = now_iso()
        pref_id = stable_id(user_id, project_name, app_id, "hidden", target_kind, target_id)
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences(id, user_id, project_name, app_id, preference_type, target_kind, target_id, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id, project_name, app_id, preference_type, target_kind, target_id) DO UPDATE SET updated_at=excluded.updated_at
                """,
                (pref_id, user_id, project_name, app_id, "hidden", target_kind, target_id, timestamp, timestamp),
            )
        return {"status": "hidden", "target_kind": target_kind, "target_id": target_id}

    @router.delete("/api/preferences/hidden/{target_kind}/{target_id}")
    def unhide_preference(target_kind: str, target_id: str, app_id: str | None = None, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, str]:
        with db.connect() as conn:
            if app_id:
                conn.execute("DELETE FROM user_preferences WHERE user_id=? AND preference_type='hidden' AND target_kind=? AND target_id=? AND (app_id=? OR app_id IS NULL OR app_id='')", (user_id, target_kind, target_id, app_id))
            else:
                conn.execute("DELETE FROM user_preferences WHERE user_id=? AND preference_type='hidden' AND target_kind=? AND target_id=?", (user_id, target_kind, target_id))
        return {"status": "visible"}

    @router.get("/api/apps")
    def apps(db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        clause, params = visible_apps_clause(user_id, "apps")
        with db.connect() as conn:
            rows = conn.execute(f"SELECT * FROM apps WHERE {clause} ORDER BY last_seen DESC", params).fetchall()
            return rows_to_dicts(rows)

    @router.get("/api/projects")
    def projects(db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        clause, params = visible_apps_clause(user_id, "apps")
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    WITH project_sources AS (
                      SELECT project_name, MIN(first_seen) created_at FROM apps WHERE {clause} GROUP BY project_name
                      UNION ALL
                      SELECT project_name, created_at FROM project_settings
                      UNION ALL
                      SELECT project_name, MIN(created_at) created_at FROM project_api_keys WHERE revoked_at IS NULL GROUP BY project_name
                    ),
                    project_names AS (
                      SELECT project_name, MIN(created_at) created_at FROM project_sources GROUP BY project_name
                    )
                    SELECT project_names.project_name,
                      project_names.created_at,
                      COUNT(DISTINCT apps.id) app_count,
                      MAX(apps.last_seen) last_seen,
                      COALESCE(SUM(routes.call_count), 0) request_count,
                      COALESCE(SUM(routes.error_count), 0) error_count,
                      (SELECT COUNT(*) FROM project_api_keys WHERE project_api_keys.project_name=project_names.project_name AND revoked_at IS NULL) api_key_count
                    FROM project_names
                    LEFT JOIN apps ON apps.project_name=project_names.project_name
                    LEFT JOIN routes ON routes.app_id=apps.id
                    GROUP BY project_names.project_name, project_names.created_at
                    ORDER BY COALESCE(MAX(apps.last_seen), project_names.project_name) DESC
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/api/projects/{project_name}/api-keys")
    def project_api_keys(project_name: str, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    "SELECT id, project_name, name, prefix, created_at, last_used_at, revoked_at FROM project_api_keys WHERE project_name=? ORDER BY created_at DESC",
                    (project_name,),
                ).fetchall()
            )

    @router.delete("/api/projects/{project_name}")
    def delete_project(project_name: str, db: Database = Depends(get_db), user: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
        if user.get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
        with db.connect() as conn:
            exists = conn.execute(
                """
                SELECT 1 FROM apps WHERE project_name=?
                UNION SELECT 1 FROM project_settings WHERE project_name=?
                UNION SELECT 1 FROM project_api_keys WHERE project_name=?
                LIMIT 1
                """,
                (project_name, project_name, project_name),
            ).fetchone()
            if not exists:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
            deleted = _delete_project(conn, project_name)
        return {"status": "deleted", "project_name": project_name, "deleted": deleted}

    @router.post("/api/projects/{project_name}/api-keys")
    def create_project_api_key(project_name: str, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, Any]:
        name = project_name[:80] or "default"
        token, prefix = generate_project_api_key()
        key_id = uuid.uuid4().hex
        timestamp = now_iso()
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO project_settings(project_name, display_name, created_by, created_at, updated_at) VALUES(?,?,?,?,?) ON CONFLICT(project_name) DO UPDATE SET updated_at=excluded.updated_at",
                (project_name, project_name, user_id, timestamp, timestamp),
            )
            conn.execute(
                "INSERT INTO project_api_keys(id, project_name, name, key_hash, prefix, created_by, created_at) VALUES(?,?,?,?,?,?,?)",
                (key_id, project_name, name, _api_key_hash(token), prefix, user_id, timestamp),
            )
        return {"id": key_id, "project_name": project_name, "name": name, "api_key": token, "prefix": prefix, "created_at": timestamp}

    @router.delete("/api/projects/{project_name}/api-keys/{key_id}")
    def revoke_project_api_key(project_name: str, key_id: str, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, str]:
        with db.connect() as conn:
            conn.execute("UPDATE project_api_keys SET revoked_at=? WHERE id=? AND project_name=?", (now_iso(), key_id, project_name))
        return {"status": "revoked"}

    @router.get("/api/overview")
    def global_overview(log_window_minutes: int | None = Query(60), log_limit: int = Query(300, ge=20, le=2000), db: Database = Depends(get_db), settings: Settings = Depends(get_settings), user_id: str = Depends(current_user)) -> dict[str, Any]:
        log_start = log_window_start(log_window_minutes)
        log_time_clause = "AND logs.timestamp >= ?" if log_start else ""
        log_params: list[Any] = [log_start] if log_start else []
        with db.connect() as conn:
            visible_clause, visible_params = visible_apps_clause(user_id, "apps")
            route_clause, route_params = hidden_route_clause(user_id)
            log_route_clause, log_route_params = hidden_route_clause(user_id, "logs.route_id", "logs.app_id")
            dep_clause, dep_params = hidden_preference_clause("dependencies", "dependency", user_id, "dependencies.app_id")
            exc_clause, exc_params = hidden_preference_clause("exceptions", "exception", user_id, "exceptions.app_id")
            apps = rows_to_dicts(conn.execute(f"SELECT * FROM apps WHERE {visible_clause} ORDER BY last_seen DESC", visible_params).fetchall())
            totals = row_to_dict(
                conn.execute(
                    f"""
                    SELECT
                      (SELECT COUNT(*) FROM events JOIN apps ON apps.id=events.app_id WHERE {visible_clause}) event_count,
                      (SELECT COUNT(*) FROM logs JOIN apps ON apps.id=logs.app_id WHERE {visible_clause} AND (logs.route_id IS NULL OR {log_route_clause})) log_count,
                      (SELECT COUNT(*) FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE {visible_clause} AND {exc_clause}) exception_count,
                      (SELECT COALESCE(SUM(call_count),0) FROM routes JOIN apps ON apps.id=routes.app_id WHERE {visible_clause} AND {route_clause}) request_count,
                      (SELECT COALESCE(SUM(error_count),0) FROM routes JOIN apps ON apps.id=routes.app_id WHERE {visible_clause} AND {route_clause}) error_count
                    """,
                    [*visible_params, *visible_params, *log_route_params, *visible_params, *exc_params, *visible_params, *route_params, *visible_params, *route_params],
                ).fetchone()
            )
            by_kind = rows_to_dicts(conn.execute(f"SELECT events.app_id, apps.project_name, apps.service_name, apps.display_name, events.kind, COUNT(*) count FROM events JOIN apps ON apps.id=events.app_id WHERE {visible_clause} GROUP BY events.app_id, apps.project_name, apps.service_name, apps.display_name, events.kind ORDER BY count DESC", visible_params).fetchall())
            by_level = rows_to_dicts(conn.execute(f"SELECT logs.app_id, apps.project_name, apps.service_name, apps.display_name, logs.level, COUNT(*) count FROM logs JOIN apps ON apps.id=logs.app_id WHERE {visible_clause} AND (logs.route_id IS NULL OR {log_route_clause}) GROUP BY logs.app_id, apps.project_name, apps.service_name, apps.display_name, logs.level ORDER BY count DESC", [*visible_params, *log_route_params]).fetchall())
            recent_errors = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT exceptions.*, apps.project_name, apps.service_name
                    FROM exceptions JOIN apps ON apps.id = exceptions.app_id
                    WHERE {visible_clause} AND {exc_clause}
                    ORDER BY last_seen DESC LIMIT 20
                    """,
                    [*visible_params, *exc_params],
                ).fetchall()
            )
            recent_logs = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT logs.*, apps.project_name, apps.service_name
                    FROM logs JOIN apps ON apps.id = logs.app_id
                    WHERE {visible_clause}
                      AND (logs.route_id IS NULL OR {log_route_clause})
                      {log_time_clause}
                    ORDER BY timestamp DESC LIMIT ?
                    """,
                    [*visible_params, *log_route_params, *log_params, log_limit],
                ).fetchall()
            )
            routes = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT routes.*, apps.project_name, apps.service_name
                    FROM routes JOIN apps ON apps.id = routes.app_id
                    WHERE {visible_clause} AND {route_clause}
                    ORDER BY routes.last_seen DESC, routes.p95_ms DESC LIMIT 60
                    """,
                    [*visible_params, *route_params],
                ).fetchall()
            )
            dependencies = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT dependencies.*, apps.project_name, apps.service_name
                    FROM dependencies JOIN apps ON apps.id = dependencies.app_id
                    WHERE {visible_clause} AND {dep_clause}
                      AND dependencies.target NOT IN ('unknown', 'unknown-db')
                      AND dependencies.target IS NOT NULL
                      AND dependencies.target != ''
                    ORDER BY dependencies.call_count DESC LIMIT 40
                    """,
                    [*visible_params, *dep_params],
                ).fetchall()
            )
            db_path = getattr(db, "path", None)
            storage = db_path.stat().st_size if db_path and db_path.exists() else 0
            retention_values = read_retention_settings(conn, settings)
            return {
                "apps": apps,
                "totals": totals,
                "event_kinds": by_kind,
                "log_levels": by_level,
                "recent_errors": recent_errors,
                "recent_logs": recent_logs,
                "routes": routes,
                "dependencies": dependencies,
                "log_window": {"minutes": log_window_minutes, "start": log_start, "limit": log_limit, "returned": len(recent_logs)},
                "retention": {"days": retention_values["retention_days"], "database_bytes": storage},
            }

    @router.get("/api/apps/{app_id}/overview")
    def overview(app_id: str, db: Database = Depends(get_db), settings: Settings = Depends(get_settings), user_id: str = Depends(current_user)) -> dict[str, Any]:
        route_clause, route_params = hidden_route_clause(user_id)
        log_route_clause, log_route_params = hidden_route_clause(user_id, "logs.route_id", "logs.app_id")
        with db.connect() as conn:
            app = row_to_dict(conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone())
            if not app:
                raise HTTPException(status_code=404, detail="app not found")
            counts = row_to_dict(conn.execute("SELECT COUNT(*) event_count FROM events WHERE app_id=?", (app_id,)).fetchone())
            request_count = scalar(conn.execute(f"SELECT COALESCE(SUM(call_count),0) AS count FROM routes WHERE app_id=? AND {route_clause}", [app_id, *route_params]).fetchone(), "count")
            error_count = scalar(conn.execute(f"SELECT COALESCE(SUM(error_count),0) AS count FROM routes WHERE app_id=? AND {route_clause}", [app_id, *route_params]).fetchone(), "count")
            log_count = scalar(conn.execute(f"SELECT COUNT(*) AS count FROM logs WHERE app_id=? AND (logs.route_id IS NULL OR {log_route_clause})", [app_id, *log_route_params]).fetchone(), "count")
            slow_routes = rows_to_dicts(conn.execute(f"SELECT * FROM routes WHERE app_id=? AND {route_clause} ORDER BY p95_ms DESC LIMIT 10", [app_id, *route_params]).fetchall())
            failing_routes = rows_to_dicts(conn.execute(f"SELECT * FROM routes WHERE app_id=? AND {route_clause} AND error_count > 0 ORDER BY error_count DESC LIMIT 10", [app_id, *route_params]).fetchall())
            db_path = getattr(db, "path", None)
            storage = db_path.stat().st_size if db_path and db_path.exists() else 0
            retention_values = read_retention_settings(conn, settings)
            return {"app": app, "event_count": counts["event_count"], "request_count": request_count, "error_count": error_count, "log_count": log_count, "top_slow_routes": slow_routes, "top_failing_routes": failing_routes, "retention": {"days": retention_values["retention_days"], "database_bytes": storage}}

    @router.get("/api/apps/{app_id}/routes")
    def routes(app_id: str, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        route_clause, route_params = hidden_route_clause(user_id)
        with db.connect() as conn:
            return rows_to_dicts(conn.execute(f"SELECT * FROM routes WHERE app_id=? AND {route_clause} ORDER BY last_seen DESC", [app_id, *route_params]).fetchall())

    @router.get("/api/apps/{app_id}/routes/{route_id}/traces")
    def route_traces(app_id: str, route_id: str, limit: int = 50, db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        with db.connect() as conn:
            return rows_to_dicts(conn.execute("SELECT * FROM traces WHERE app_id=? AND route_id=? ORDER BY COALESCE(finished_at, started_at) DESC LIMIT ?", (app_id, route_id, limit)).fetchall())

    @router.get("/api/apps/{app_id}/traces/{trace_id}")
    def trace_detail(app_id: str, trace_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            trace = row_to_dict(conn.execute("SELECT * FROM traces WHERE app_id=? AND id=?", (app_id, trace_id)).fetchone())
            events = rows_to_dicts(conn.execute("SELECT * FROM events WHERE app_id=? AND trace_id=? ORDER BY timestamp", (app_id, trace_id)).fetchall())
            spans = rows_to_dicts(conn.execute("SELECT * FROM spans WHERE app_id=? AND trace_id=? ORDER BY started_at", (app_id, trace_id)).fetchall())
            logs = rows_to_dicts(conn.execute("SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id WHERE logs.trace_id=? ORDER BY logs.timestamp", (trace_id,)).fetchall())
            exceptions = rows_to_dicts(conn.execute("SELECT * FROM exceptions WHERE app_id=? AND sample_trace_id=? ORDER BY last_seen DESC", (app_id, trace_id)).fetchall())
            nearby_logs = logs_around(conn, trace.get("finished_at") if trace else None, trace_id=trace_id)
            return {"trace": trace, "events": events, "spans": spans, "logs": logs, "nearby_logs_all_apps": nearby_logs, "exceptions": exceptions}

    @router.get("/api/apps/{app_id}/exceptions")
    def exceptions(app_id: str, db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        with db.connect() as conn:
            return rows_to_dicts(conn.execute("SELECT * FROM exceptions WHERE app_id=? ORDER BY last_seen DESC", (app_id,)).fetchall())

    @router.get("/api/apps/{app_id}/exceptions/{exception_id}")
    def exception_detail(app_id: str, exception_id: str, include_context: bool = True, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            exception = row_to_dict(conn.execute("SELECT * FROM exceptions WHERE app_id=? AND id=?", (app_id, exception_id)).fetchone())
            if not exception:
                raise HTTPException(status_code=404, detail="exception not found")
            if not include_context:
                return {"exception": exception}
            same_trace_logs = rows_to_dicts(conn.execute("SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id WHERE trace_id=? ORDER BY timestamp", (exception.get("sample_trace_id"),)).fetchall()) if exception.get("sample_trace_id") else []
            nearby = logs_around(conn, exception.get("last_seen"), trace_id=exception.get("sample_trace_id"), window_seconds=180)
            trace = trace_detail(app_id, exception["sample_trace_id"], db) if exception.get("sample_trace_id") else None
            return {"exception": exception, "trace": trace, "correlated_logs": same_trace_logs, "nearby_logs_all_apps": nearby}

    @router.get("/api/apps/{app_id}/logs")
    def logs(app_id: str, trace_id: str | None = None, route_id: str | None = None, level: str | None = None, logger: str | None = None, text: str | None = None, start: str | None = None, end: str | None = None, limit: int = Query(100, le=500), db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        log_route_clause, log_route_params = hidden_route_clause(user_id, "logs.route_id", "logs.app_id")
        where = ["logs.app_id=?", f"(logs.route_id IS NULL OR {log_route_clause})"]
        params: list[Any] = [app_id, *log_route_params]
        for column, value in [("trace_id", trace_id), ("route_id", route_id), ("level", level), ("logger_name", logger)]:
            if value:
                where.append(f"logs.{column}=?")
                params.append(value)
        if text:
            where.append("logs.message LIKE ?")
            params.append(f"%{text}%")
        if start:
            where.append("logs.timestamp >= ?")
            params.append(start)
        if end:
            where.append("logs.timestamp <= ?")
            params.append(end)
        params.append(limit)
        with db.connect() as conn:
            return rows_to_dicts(conn.execute(f"SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id WHERE {' AND '.join(where)} ORDER BY logs.timestamp DESC LIMIT ?", params).fetchall())

    @router.get("/api/logs")
    def all_logs(level: str | None = None, text: str | None = None, start: str | None = None, end: str | None = None, limit: int = Query(200, le=1000), db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        log_route_clause, log_route_params = hidden_route_clause(user_id, "logs.route_id", "logs.app_id")
        where: list[str] = [f"(logs.route_id IS NULL OR {log_route_clause})"]
        params: list[Any] = [*log_route_params]
        if level:
            where.append("logs.level=?")
            params.append(level)
        if text:
            where.append("logs.message LIKE ?")
            params.append(f"%{text}%")
        if start:
            where.append("logs.timestamp >= ?")
            params.append(start)
        if end:
            where.append("logs.timestamp <= ?")
            params.append(end)
        params.append(limit)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with db.connect() as conn:
            return rows_to_dicts(conn.execute(f"SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id {clause} ORDER BY logs.timestamp DESC LIMIT ?", params).fetchall())

    @router.get("/api/apps/{app_id}/logs/{log_id}")
    def log_detail(app_id: str, log_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            log = row_to_dict(conn.execute("SELECT * FROM logs WHERE app_id=? AND id=?", (app_id, log_id)).fetchone())
            if not log:
                raise HTTPException(status_code=404, detail="log not found")
            return log

    @router.get("/api/apps/{app_id}/dependencies")
    def dependencies(app_id: str, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        dep_clause, dep_params = hidden_preference_clause("dependencies", "dependency", user_id, "dependencies.app_id")
        with db.connect() as conn:
            return rows_to_dicts(conn.execute(f"SELECT * FROM dependencies WHERE app_id=? AND {dep_clause} ORDER BY call_count DESC", [app_id, *dep_params]).fetchall())

    @router.get("/api/apps/{app_id}/call-graph")
    def call_graph(app_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            routes = rows_to_dicts(conn.execute("SELECT id, method, route_pattern, call_count, error_count FROM routes WHERE app_id=?", (app_id,)).fetchall())
            deps = rows_to_dicts(conn.execute("SELECT dependency_type, target, operation, call_count, error_count FROM dependencies WHERE app_id=?", (app_id,)).fetchall())
            llm = rows_to_dicts(conn.execute("SELECT provider, model, route_id, call_count, input_tokens, output_tokens FROM llm_usage WHERE app_id=?", (app_id,)).fetchall())
            return {"routes": routes, "dependencies": deps, "llm_usage": llm}

    @router.get("/api/entrypoints")
    def entrypoints(include_hidden: bool = False, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        route_clause, route_params = hidden_route_clause(user_id)
        hidden_select = "EXISTS (SELECT 1 FROM user_preferences WHERE user_preferences.user_id=? AND user_preferences.preference_type='hidden' AND user_preferences.target_kind='route' AND user_preferences.target_id=routes.id AND (user_preferences.app_id IS NULL OR user_preferences.app_id='' OR user_preferences.app_id=routes.app_id)) hidden"
        where = "1=1" if include_hidden else route_clause
        params = [user_id] if include_hidden else [user_id, *route_params]
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT routes.*, apps.project_name, apps.service_name,
                      (SELECT COUNT(*) FROM traces WHERE traces.route_id=routes.id AND traces.app_id=routes.app_id) trace_count,
                      (SELECT COUNT(*) FROM logs WHERE logs.route_id=routes.id AND logs.app_id=routes.app_id) log_count,
                      {hidden_select}
                    FROM routes JOIN apps ON apps.id=routes.app_id
                    WHERE {where}
                    ORDER BY routes.last_seen DESC, routes.call_count DESC
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/api/routes/{route_id}/requests")
    def route_requests(route_id: str, limit: int = Query(50, le=250), include_hidden: bool = False, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, Any]:
        route_clause, route_params = hidden_route_clause(user_id)
        hidden_filter = "" if include_hidden else f"AND {route_clause}"
        with db.connect() as conn:
            route = row_to_dict(
                conn.execute(
                    f"""
                    SELECT routes.*, apps.service_name
                    FROM routes JOIN apps ON apps.id=routes.app_id
                    WHERE routes.id=? {hidden_filter}
                    """,
                    [route_id, *([] if include_hidden else route_params)],
                ).fetchone()
            )
            if not route:
                raise HTTPException(status_code=404, detail="route not found")
            traces = rows_to_dicts(
                conn.execute(
                    """
                    SELECT traces.*, routes.method, routes.route_pattern, apps.service_name,
                      (SELECT COUNT(*) FROM logs WHERE logs.trace_id=traces.id) log_count,
                      (SELECT COUNT(*) FROM exceptions WHERE exceptions.sample_trace_id=traces.id) exception_count
                    FROM traces
                    JOIN routes ON routes.id=traces.route_id AND routes.app_id=traces.app_id
                    JOIN apps ON apps.id=traces.app_id
                    WHERE traces.route_id=?
                    ORDER BY COALESCE(traces.finished_at, traces.started_at) DESC LIMIT ?
                    """,
                    (route_id, limit),
                ).fetchall()
            )
            trace_ids = [row["id"] for row in traces if row.get("id")]
            logs: list[dict[str, Any]] = []
            if trace_ids:
                placeholders = ",".join("?" for _ in trace_ids)
                timestamps = [value for row in traces for value in (row.get("started_at"), row.get("finished_at")) if value]
                time_clause = ""
                params: list[Any] = [*trace_ids, route_id]
                if timestamps:
                    parsed_times = [parse_ts(value) for value in timestamps]
                    clean_times = [value for value in parsed_times if value is not None]
                    if clean_times:
                        time_clause = " OR logs.timestamp BETWEEN ? AND ?"
                        params.extend([iso(min(clean_times) - timedelta(seconds=180)), iso(max(clean_times) + timedelta(seconds=180))])
                logs = rows_to_dicts(
                    conn.execute(
                        f"""
                        SELECT logs.*, apps.service_name,
                          CASE WHEN logs.trace_id IN ({placeholders}) THEN 1 ELSE 0 END exact_trace_match
                        FROM logs JOIN apps ON apps.id=logs.app_id
                        WHERE logs.trace_id IN ({placeholders}) OR logs.route_id=? {time_clause}
                        ORDER BY exact_trace_match DESC, logs.timestamp DESC LIMIT 500
                        """,
                        [*trace_ids, *params],
                    ).fetchall()
                )
            return {"route": route, "traces": traces, "logs": logs}

    def build_trace_agent_context(trace_id: str, db: Database) -> str:
        data = trace_map(trace_id, db=db)
        lines = ["# Runtime Observer Trace Context", "", f"Trace ID: `{trace_id}`", ""]
        for trace in data.get("traces", []):
            lines.extend(["## Request", f"- App: {trace.get('service_name')}", f"- Route: {trace.get('method')} {trace.get('route_pattern')}", f"- Status: {trace.get('status_code')}", f"- Duration ms: {trace.get('duration_ms')}", ""])
        lines.append("## Spans / Functions")
        for span in data.get("spans", []):
            lines.append(f"- {span.get('kind')}: {span.get('name')} ({span.get('duration_ms')}ms, status={span.get('status')})")
        lines.extend(["", "## Dependencies / Inputs"])
        for event in data.get("dependencies", []):
            lines.append(f"### {event.get('kind')} at {event.get('timestamp')}")
            lines.append("```json")
            lines.append(event.get("payload_json") or "{}")
            lines.append("```")
        lines.extend(["", "## Logs"])
        for log in data.get("flow_logs", data.get("logs", [])):
            lines.append(f"[{log.get('timestamp')}] {log.get('service_name')} {log.get('level')} {log.get('logger_name')}: {log.get('message')}")
            if log.get("exception_json") and log.get("exception_json") != "{}":
                lines.append("```json")
                lines.append(log.get("exception_json"))
                lines.append("```")
        lines.extend(["", "## Exceptions"])
        for exc in data.get("exceptions", []):
            lines.append("```json")
            lines.append(json.dumps(exc, indent=2))
            lines.append("```")
        lines.extend(["", "## Raw Timeline"])
        lines.append("```json")
        lines.append(json.dumps(data.get("timeline", [])[:200], indent=2))
        lines.append("```")
        return "\n".join(lines)

    @router.get("/api/traces/{trace_id}/agent-context")
    def trace_agent_context(trace_id: str, db: Database = Depends(get_db)) -> dict[str, str]:
        return {"text": build_trace_agent_context(trace_id, db)}

    @router.get("/api/dependencies/{dependency_id}/context")
    def dependency_context(dependency_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            dependency = row_to_dict(
                conn.execute(
                    """
                    SELECT dependencies.*, apps.service_name
                    FROM dependencies JOIN apps ON apps.id=dependencies.app_id
                    WHERE dependencies.id=?
                    """,
                    (dependency_id,),
                ).fetchone()
            )
            if not dependency:
                raise HTTPException(status_code=404, detail="dependency not found")
            wanted_key = (str(dependency.get("app_id")), str(dependency.get("dependency_type")), str(dependency.get("target")), str(dependency.get("operation")))
            rows = rows_to_dicts(
                conn.execute(
                    """
                    SELECT events.*, apps.service_name
                    FROM events JOIN apps ON apps.id=events.app_id
                    WHERE events.app_id=? AND events.kind IN ('db_query','http_client_call','llm_call')
                    ORDER BY events.timestamp DESC LIMIT 5000
                    """,
                    (dependency.get("app_id"),),
                ).fetchall()
            )
            samples: list[dict[str, Any]] = []
            error_samples: list[dict[str, Any]] = []
            for event in rows:
                if _dependency_key_from_event(event) != wanted_key:
                    continue
                try:
                    payload = json.loads(event.get("payload_json") or "{}")
                except json.JSONDecodeError:
                    payload = {}
                item = {**event, "payload": payload}
                samples.append(item)
                if payload.get("error") or payload.get("error_type") or payload.get("error_message") or int(payload.get("status_code") or 0) >= 400:
                    error_samples.append(item)
                if len(samples) >= 50 and len(error_samples) >= 25:
                    break
            related_logs: list[dict[str, Any]] = []
            for event in (error_samples or samples)[:5]:
                tid = event.get("trace_id")
                if tid:
                    # exact trace match only — time-window proximity includes background jobs
                    # (SQS pollers, image rebuilds, lock heartbeats) that are unrelated
                    related_logs.extend(
                        rows_to_dicts(
                            conn.execute(
                                "SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id"
                                " WHERE logs.trace_id=? ORDER BY logs.timestamp LIMIT 40",
                                (tid,),
                            ).fetchall()
                        )
                    )
                else:
                    related_logs.extend(logs_around(conn, event.get("timestamp"), window_seconds=30, limit=40))
            by_id = {log.get("id"): log for log in related_logs if log.get("id")}
            return {"dependency": dependency, "samples": samples[:50], "error_samples": error_samples[:25], "related_logs": list(by_id.values())[:120]}

    @router.get("/api/dependencies/{dependency_id}/agent-context")
    def dependency_agent_context(dependency_id: str, db: Database = Depends(get_db)) -> dict[str, str]:
        data = dependency_context(dependency_id, db)
        dep = data["dependency"]
        lines = ["# Runtime Observer Dependency Context", "", f"Dependency: `{dep.get('dependency_type')} {dep.get('target')} {dep.get('operation')}`", f"App: {dep.get('service_name')}", f"Calls: {dep.get('call_count')}", f"Errors: {dep.get('error_count')}", f"p95 ms: {dep.get('p95_duration_ms')}", "", "## Error Samples"]
        for event in data.get("error_samples", []):
            lines.append(f"### {event.get('timestamp')} trace={event.get('trace_id')}")
            lines.append("```json")
            lines.append(json.dumps(event.get("payload", {}), indent=2))
            lines.append("```")
        lines.append("\n## Recent Samples")
        for event in data.get("samples", [])[:10]:
            lines.append(f"- {event.get('timestamp')} trace={event.get('trace_id')} payload={json.dumps(event.get('payload', {}))[:1000]}")
        lines.append("\n## Related Logs Around Samples")
        for log in data.get("related_logs", []):
            lines.append(f"[{log.get('timestamp')}] {log.get('service_name')} {log.get('level')} {log.get('logger_name')}: {log.get('message')}")
        return {"text": "\n".join(lines)}

    @router.get("/api/logs/{log_id}/agent-context")
    def log_agent_context(log_id: str, db: Database = Depends(get_db)) -> dict[str, str]:
        with db.connect() as conn:
            log = row_to_dict(conn.execute("SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id WHERE logs.id=?", (log_id,)).fetchone())
            if not log:
                raise HTTPException(status_code=404, detail="log not found")
            if log.get("trace_id"):
                focused = ["# Focused Error / Log", "", "```json", json.dumps(log, indent=2), "```", ""]
                return {"text": "\n".join(focused) + build_trace_agent_context(str(log["trace_id"]), db)}
            nearby = logs_around(conn, log.get("timestamp"), window_seconds=60, limit=100)
            lines = ["# Runtime Observer Log Context", "", "## Focused Log", "```json", json.dumps(log, indent=2), "```", "", "## Nearby Logs ±60s"]
            for item in nearby:
                lines.append(f"[{item.get('timestamp')}] {item.get('service_name')} {item.get('level')} {item.get('logger_name')}: {item.get('message')}")
            return {"text": "\n".join(lines)}

    def build_trace_flow(trace_id: str, traces: list[dict[str, Any]], spans: list[dict[str, Any]], dependencies: list[dict[str, Any]], logs: list[dict[str, Any]], exceptions: list[dict[str, Any]]) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        root_id = f"route:{trace_id}"
        root = traces[0] if traces else {}
        nodes.append({"id": root_id, "type": "route", "label": f"{root.get('method') or 'REQUEST'} {root.get('route_pattern') or trace_id}", "service_name": root.get("service_name"), "timestamp": root.get("started_at"), "duration_ms": root.get("duration_ms")})
        span_ids: set[str] = set()
        ordered_span_ids: list[str] = []
        for item in [*spans, *dependencies, *logs]:
            if item.get("span_id"):
                span_id = str(item["span_id"])
                if span_id not in span_ids:
                    span_ids.add(span_id)
                    ordered_span_ids.append(span_id)
        for span_id in ordered_span_ids:
            span = next((item for item in spans if item.get("span_id") == span_id), {})
            node_id = f"span:{span_id}"
            nodes.append({"id": node_id, "type": "span", "label": span.get("name") or span_id, "service_name": span.get("service_name") or root.get("service_name"), "timestamp": span.get("started_at"), "duration_ms": span.get("duration_ms"), "kind": span.get("kind")})
            parent = span.get("parent_span_id")
            edges.append({"from": f"span:{parent}" if parent and str(parent) in span_ids else root_id, "to": node_id, "label": "calls"})
        for event in dependencies:
            payload = json.loads(event.get("payload_json") or "{}")
            node_id = f"event:{event.get('id')}"
            label = payload.get("operation") or payload.get("method") or payload.get("provider") or event.get("kind")
            nodes.append({"id": node_id, "type": "dependency", "kind": event.get("kind"), "label": str(label), "service_name": event.get("service_name"), "timestamp": event.get("timestamp"), "payload": payload})
            parent = f"span:{event.get('span_id')}" if event.get("span_id") and str(event.get("span_id")) in span_ids else root_id
            edges.append({"from": parent, "to": node_id, "label": "calls"})
        for log in logs:
            node_id = f"log:{log.get('id')}"
            nodes.append({"id": node_id, "type": "log", "label": log.get("message") or log.get("logger_name") or "log", "service_name": log.get("service_name"), "timestamp": log.get("timestamp"), "level": log.get("level")})
            parent = f"span:{log.get('span_id')}" if log.get("span_id") and str(log.get("span_id")) in span_ids else root_id
            edges.append({"from": parent, "to": node_id, "label": "logs"})
        for exc in exceptions:
            node_id = f"exception:{exc.get('id')}"
            nodes.append({"id": node_id, "type": "exception", "label": f"{exc.get('type')}: {exc.get('normalized_message')}", "service_name": exc.get("service_name"), "timestamp": exc.get("last_seen")})
            edges.append({"from": root_id, "to": node_id, "label": "throws"})
        return {"nodes": nodes, "edges": edges}

    @router.get("/api/traces/{trace_id}/map")
    def trace_map(trace_id: str, slim: bool = False, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            traces = rows_to_dicts(
                conn.execute(
                    """
                    SELECT traces.*, routes.method, routes.route_pattern, apps.service_name
                    FROM traces
                    LEFT JOIN routes ON routes.id=traces.route_id AND routes.app_id=traces.app_id
                    JOIN apps ON apps.id=traces.app_id
                    WHERE traces.id=?
                    ORDER BY traces.started_at
                    """,
                    (trace_id,),
                ).fetchall()
            )
            events = rows_to_dicts(
                conn.execute(
                    """
                    SELECT events.id, events.app_id, events.trace_id, events.span_id,
                      events.parent_span_id, events.kind, events.timestamp,
                      events.payload_json, apps.service_name
                    FROM events JOIN apps ON apps.id=events.app_id
                    WHERE events.trace_id=? ORDER BY events.timestamp
                    """,
                    (trace_id,),
                ).fetchall()
            )
            spans = rows_to_dicts(conn.execute("SELECT spans.*, apps.service_name FROM spans JOIN apps ON apps.id=spans.app_id WHERE spans.trace_id=? ORDER BY spans.started_at", (trace_id,)).fetchall())
            logs = rows_to_dicts(conn.execute("SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id WHERE logs.trace_id=? ORDER BY logs.timestamp", (trace_id,)).fetchall())
            exceptions = rows_to_dicts(conn.execute("SELECT exceptions.*, apps.service_name FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE exceptions.sample_trace_id=? ORDER BY exceptions.last_seen DESC", (trace_id,)).fetchall())
            dependencies = [event for event in events if event.get("kind") in {"http_client_call", "db_query", "llm_call"}]
            timestamp = traces[-1].get("finished_at") if traces else (events[-1].get("timestamp") if events else None)
            nearby_logs = logs_around(conn, timestamp, trace_id=trace_id, window_seconds=180, limit=400)
            exact_logs_by_id = {log["id"]: log for log in logs if log.get("id")}
            nearby_background_logs = [log for log in nearby_logs if log.get("trace_id") != trace_id and log.get("id") not in exact_logs_by_id]
            flow_logs = sorted(exact_logs_by_id.values(), key=lambda item: item.get("timestamp") or "")
            timeline = sorted([*events, *[{**span, "kind": "span", "timestamp": span.get("started_at") or span.get("finished_at")} for span in spans], *[{**log, "kind": "log_record", "timestamp": log.get("timestamp"), "correlation": "exact_trace"} for log in flow_logs]], key=lambda item: item.get("timestamp") or "")
            flow = build_trace_flow(trace_id, traces, spans, dependencies, flow_logs, exceptions)
            dependency_groups = build_dependency_groups(dependencies)
            relationship_loader_groups = build_relationship_loader_groups(dependencies)
            slow_gap_markers = build_slow_gap_markers(timeline, traces)
            duplicate_candidates = build_duplicate_candidates(dependencies)
            compact_events = _compact_trace_rows(events)
            compact_dependencies = [event for event in compact_events if event.get("kind") in {"http_client_call", "db_query", "llm_call"}]
            compact_timeline = _compact_trace_rows(timeline)
            event_count = len(compact_events)
            if slim:
                compact_events = []
                compact_timeline = []
                nearby_background_logs = nearby_background_logs[:50]
                logs = []
                nearby_logs = []
                flow = {"nodes": [{"id": trace_id}], "edges": []}
            return {"trace_id": trace_id, "traces": traces, "event_count": event_count, "events": compact_events, "spans": spans, "logs": logs, "flow_logs": flow_logs, "nearby_background_logs": nearby_background_logs, "exceptions": exceptions, "dependencies": compact_dependencies, "timeline": compact_timeline, "nearby_logs_all_apps": nearby_logs, "flow": flow, "dependency_groups": dependency_groups, "relationship_loader_groups": relationship_loader_groups, "slow_gap_markers": slow_gap_markers, "duplicate_candidates": duplicate_candidates}

    @router.get("/api/traces/{trace_id}/correlated-logs")
    def correlated_trace_logs(trace_id: str, level: str | None = None, app_ids: str | None = None, same_project: bool = True, window_seconds: int = Query(180, ge=1, le=3600), limit: int = Query(500, ge=1, le=2000), db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, Any]:
        wanted_apps = {value for value in (app_ids or "").split(",") if value}
        with db.connect() as conn:
            trace_rows = rows_to_dicts(
                conn.execute(
                    """
                    SELECT traces.*, apps.project_name, apps.service_name
                    FROM traces JOIN apps ON apps.id=traces.app_id
                    WHERE traces.id=?
                    """,
                    (trace_id,),
                ).fetchall()
            )
            project_names = {row.get("project_name") for row in trace_rows if row.get("project_name")}
            timestamps = [parse_ts(value) for row in trace_rows for value in (row.get("started_at"), row.get("finished_at")) if value]
            clean_times = [value for value in timestamps if value is not None]
            start = iso(min(clean_times) - timedelta(seconds=window_seconds)) if clean_times else None
            end = iso(max(clean_times) + timedelta(seconds=window_seconds)) if clean_times else None
            where = ["(logs.trace_id=?"]
            params: list[Any] = [trace_id]
            if start and end:
                where[0] += " OR logs.timestamp BETWEEN ? AND ?"
                params.extend([start, end])
            where[0] += ")"
            if level:
                where.append("logs.level=?")
                params.append(level)
            if wanted_apps:
                where.append(f"logs.app_id IN ({','.join('?' for _ in wanted_apps)})")
                params.extend(sorted(wanted_apps))
            if same_project and project_names:
                where.append(f"apps.project_name IN ({','.join('?' for _ in project_names)})")
                params.extend(sorted(project_names))
            params.append(limit)
            logs = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT logs.*, apps.service_name, apps.project_name,
                      CASE WHEN logs.trace_id=? THEN 'exact_trace' ELSE 'nearby_time' END correlation_type
                    FROM logs JOIN apps ON apps.id=logs.app_id
                    WHERE {' AND '.join(where)}
                    ORDER BY logs.timestamp LIMIT ?
                    """,
                    [trace_id, *params],
                ).fetchall()
            )
        for log in logs:
            log["correlation"] = {"type": log.pop("correlation_type")}
        grouped: dict[str, dict[str, Any]] = {}
        for log in logs:
            app_id = str(log.get("app_id"))
            grouped.setdefault(app_id, {"app_id": app_id, "service_name": log.get("service_name"), "logs": []})["logs"].append(log)
        return {"trace_id": trace_id, "logs": logs, "groups": list(grouped.values())}


    @router.get("/api/errors/summary")
    def errors_summary(project_name: str | None = None, app_id: str | None = None, log_window_minutes: int = Query(60, ge=0, le=43200), db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, Any]:
        start = log_window_start(log_window_minutes)
        app_clause, app_params = scoped_apps_filter(user_id, project_name=project_name, app_id=app_id)
        exc_clause, exc_params = hidden_preference_clause("exceptions", "exception", user_id, "exceptions.app_id")
        log_route_clause, log_route_params = hidden_route_clause(user_id, "logs.route_id", "logs.app_id")
        log_time_clause = "AND logs.timestamp >= ?" if start else ""
        with db.connect() as conn:
            totals = row_to_dict(
                conn.execute(
                    f"""
                    SELECT
                      (SELECT COALESCE(SUM(exceptions.count),0) FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE {app_clause} AND {exc_clause}) exception_count,
                      (SELECT COUNT(*) FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE {app_clause} AND {exc_clause}) cluster_count,
                      (SELECT COUNT(*) FROM logs JOIN apps ON apps.id=logs.app_id WHERE {app_clause} AND (logs.route_id IS NULL OR {log_route_clause}) AND UPPER(COALESCE(logs.level,'')) IN ('ERROR','CRITICAL') {log_time_clause}) error_log_count
                    """,
                    [*app_params, *exc_params, *app_params, *exc_params, *app_params, *log_route_params, *([start] if start else [])],
                ).fetchone()
            )
            by_type = rows_to_dicts(conn.execute(f"SELECT exceptions.type, COALESCE(SUM(exceptions.count),0) count, COUNT(*) clusters FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE {app_clause} AND {exc_clause} GROUP BY exceptions.type ORDER BY count DESC LIMIT 20", [*app_params, *exc_params]).fetchall())
            by_service = rows_to_dicts(conn.execute(f"SELECT apps.project_name, apps.service_name, COUNT(*) clusters, COALESCE(SUM(exceptions.count),0) count FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE {app_clause} AND {exc_clause} GROUP BY apps.project_name, apps.service_name ORDER BY count DESC LIMIT 20", [*app_params, *exc_params]).fetchall())
        return {"totals": totals, "by_type": by_type, "by_service": by_service, "window": {"minutes": log_window_minutes, "start": start}}

    @router.get("/api/errors/clusters")
    def error_clusters(project_name: str | None = None, app_id: str | None = None, limit: int = Query(50, ge=1, le=200), db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        app_clause, app_params = scoped_apps_filter(user_id, project_name=project_name, app_id=app_id)
        exc_clause, exc_params = hidden_preference_clause("exceptions", "exception", user_id, "exceptions.app_id")
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT exceptions.*, apps.project_name, apps.service_name, routes.method, routes.route_pattern
                    FROM exceptions
                    JOIN apps ON apps.id=exceptions.app_id
                    LEFT JOIN traces ON traces.id=exceptions.sample_trace_id AND traces.app_id=exceptions.app_id
                    LEFT JOIN routes ON routes.id=traces.route_id AND routes.app_id=traces.app_id
                    WHERE {app_clause} AND {exc_clause}
                    ORDER BY exceptions.count DESC, exceptions.last_seen DESC LIMIT ?
                    """,
                    [*app_params, *exc_params, limit],
                ).fetchall()
            )

    @router.get("/api/errors/timeline")
    def errors_timeline(project_name: str | None = None, app_id: str | None = None, window_minutes: int = Query(1440, ge=1, le=43200), bucket_minutes: int = Query(15, ge=1, le=1440), db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        start = iso(datetime.now(UTC) - timedelta(minutes=window_minutes))
        bucket = time_bucket("events.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        exception_type = json_text("events.payload_json", "type", is_postgres=db.is_postgres)
        app_clause, app_params = scoped_apps_filter(user_id, project_name=project_name, app_id=app_id)
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT {bucket} bucket, apps.project_name, apps.service_name,
                      COALESCE({exception_type}, 'Exception') type,
                      COUNT(*) count
                    FROM events JOIN apps ON apps.id=events.app_id
                    WHERE {app_clause} AND events.kind='exception_raised' AND events.timestamp >= ?
                    GROUP BY bucket, apps.project_name, apps.service_name, type
                    ORDER BY bucket ASC LIMIT 1000
                    """,
                    [*app_params, start],
                ).fetchall()
            )

    @router.get("/api/metrics/timeseries")
    def metrics_timeseries(project_name: str | None = None, app_id: str | None = None, window_minutes: int = Query(1440, ge=1, le=43200), bucket_minutes: int = Query(15, ge=1, le=1440), db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> list[dict[str, Any]]:
        start = iso(datetime.now(UTC) - timedelta(minutes=window_minutes))
        app_clause, app_params = scoped_apps_filter(user_id, project_name=project_name, app_id=app_id)
        route_bucket = time_bucket("route_durations.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        log_bucket = time_bucket("logs.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        event_bucket = time_bucket("events.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        with db.connect() as conn:
            requests = rows_to_dicts(conn.execute(f"""SELECT {route_bucket} bucket, COUNT(*) requests, COALESCE(SUM(CASE WHEN COALESCE(route_durations.status_code,0) >= 500 THEN 1 ELSE 0 END),0) request_errors, AVG(route_durations.duration_ms) avg_ms FROM route_durations JOIN routes ON routes.id=route_durations.route_id JOIN apps ON apps.id=routes.app_id WHERE {app_clause} AND route_durations.timestamp >= ? GROUP BY bucket ORDER BY bucket ASC LIMIT 1000""", [*app_params, start]).fetchall())
            logs = rows_to_dicts(conn.execute(f"""SELECT {log_bucket} bucket, COUNT(*) logs, COALESCE(SUM(CASE WHEN UPPER(COALESCE(logs.level,'')) IN ('ERROR','CRITICAL') THEN 1 ELSE 0 END),0) error_logs FROM logs JOIN apps ON apps.id=logs.app_id WHERE {app_clause} AND logs.timestamp >= ? GROUP BY bucket ORDER BY bucket ASC LIMIT 1000""", [*app_params, start]).fetchall())
            exceptions = rows_to_dicts(conn.execute(f"""SELECT {event_bucket} bucket, COUNT(*) exceptions FROM events JOIN apps ON apps.id=events.app_id WHERE {app_clause} AND events.kind='exception_raised' AND events.timestamp >= ? GROUP BY bucket ORDER BY bucket ASC LIMIT 1000""", [*app_params, start]).fetchall())
        merged: dict[str, dict[str, Any]] = {}
        for rows in (requests, logs, exceptions):
            for row in rows:
                bucket_value = str(row.get("bucket"))
                item = merged.setdefault(bucket_value, {"bucket": bucket_value, "requests": 0, "request_errors": 0, "avg_ms": 0, "logs": 0, "error_logs": 0, "exceptions": 0})
                item.update({key: value for key, value in row.items() if key != "bucket"})
        return [merged[key] for key in sorted(merged)]

    @router.post("/api/admin/clear")
    def clear(db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> dict[str, str]:
        db.clear()
        return {"status": "cleared"}

    @router.get("/api/agent/tools")
    def agent_tools() -> dict[str, list[str]]:
        return {"tools": ["get_application_map", "get_route_summary", "get_trace", "get_trace_agent_context", "get_log_agent_context", "get_dependency_context", "get_dependency_agent_context", "get_exception_context", "get_slowest_routes", "get_failing_routes", "get_dependency_map", "get_llm_usage", "search_logs", "search_events"]}

    @router.post("/api/agent/{tool_name}")
    async def agent_tool(tool_name: str, request: Request, db: Database = Depends(get_db), user_id: str = Depends(current_user)) -> Any:
        args = await request.json()
        app_id = args.get("app_id")
        with db.connect() as conn:
            if tool_name == "get_application_map":
                return call_graph(app_id, db)
            if tool_name == "get_route_summary":
                route = args.get("route")
                return rows_to_dicts(conn.execute("SELECT * FROM routes WHERE app_id=? AND route_pattern LIKE ?", (app_id, f"%{route}%")).fetchall())
            if tool_name == "get_trace":
                return trace_detail(app_id, args.get("trace_id"), db)
            if tool_name == "get_trace_agent_context":
                return trace_agent_context(args.get("trace_id"), db)
            if tool_name == "get_log_agent_context":
                return log_agent_context(args.get("log_id"), db)
            if tool_name == "get_dependency_context":
                return dependency_context(args.get("dependency_id"), db)
            if tool_name == "get_dependency_agent_context":
                return dependency_agent_context(args.get("dependency_id"), db)
            if tool_name == "get_exception_context":
                return exception_detail(app_id, args.get("exception_id"), db)
            if tool_name == "get_slowest_routes":
                return rows_to_dicts(conn.execute("SELECT * FROM routes WHERE app_id=? ORDER BY p95_ms DESC LIMIT ?", (app_id, int(args.get("limit", 5)))).fetchall())
            if tool_name == "get_failing_routes":
                return rows_to_dicts(conn.execute("SELECT * FROM routes WHERE app_id=? ORDER BY error_count DESC LIMIT ?", (app_id, int(args.get("limit", 5)))).fetchall())
            if tool_name == "get_dependency_map":
                return dependencies(app_id, db, user_id)
            if tool_name == "get_llm_usage":
                group_by = args.get("group_by") or "model"
                group_col = "provider" if group_by == "provider" else "model"
                return rows_to_dicts(conn.execute(f"SELECT {group_col}, SUM(call_count) call_count, SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens, SUM(error_count) error_count FROM llm_usage WHERE app_id=? GROUP BY {group_col}", (app_id,)).fetchall())
            if tool_name == "search_logs":
                filters = args.get("filters") or {}
                return all_logs(filters.get("level"), filters.get("text"), filters.get("start"), filters.get("end"), int(filters.get("limit", 100)), db, user_id)
            if tool_name == "search_events":
                query = args.get("query") or {}
                where = ["app_id=?"]
                params: list[Any] = [app_id]
                if query.get("kind"):
                    where.append("kind=?")
                    params.append(query["kind"])
                if query.get("text"):
                    where.append("raw_json LIKE ?")
                    params.append(f"%{query['text']}%")
                params.append(int(query.get("limit", 100)))
                return rows_to_dicts(conn.execute(f"SELECT * FROM events WHERE {' AND '.join(where)} ORDER BY timestamp DESC LIMIT ?", params).fetchall())
        raise HTTPException(status_code=404, detail="unknown agent tool")

    @router.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD_HTML

    return router
