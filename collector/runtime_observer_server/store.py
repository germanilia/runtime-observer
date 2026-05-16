from __future__ import annotations

import contextvars
import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from .db import Database

SECRET_KEYS = re.compile(r"password|passwd|secret|token|api_?key|authorization|cookie|credential|private_key|access_key|refresh_token|id_token", re.I)
_BATCH_ROUTES: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar("runtime_observer_batch_routes", default=None)
_BATCH_DEPS: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar("runtime_observer_batch_deps", default=None)

SECRET_VALUES = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\b(password|passwd|secret|token|api[_-]?key|apikey|authorization|cookie|credential|private[_-]?key|access[_-]?key|refresh[_-]?token|id[_-]?token)\s*[:=]\s*([^\s,;]+)", re.I),
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def stable_id(*parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def dumps(value: Any) -> str:
    return json.dumps(redact(value), separators=(",", ":"), ensure_ascii=False)


def hour_bucket(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed.astimezone(UTC).replace(minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def redact(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "<truncated>"
    if isinstance(value, dict):
        output = {}
        for key, item in list(value.items())[:100]:
            key_text = str(key)
            output[key_text] = "<redacted>" if SECRET_KEYS.search(key_text) else redact(item, depth + 1)
        return output
    if isinstance(value, list):
        return [redact(item, depth + 1) for item in value[:100]]
    if isinstance(value, str):
        text = value[:4096]
        for pattern in SECRET_VALUES:
            if pattern.groups >= 2:
                text = pattern.sub(lambda match: f"{match.group(1)}=<redacted>", text)
            else:
                text = pattern.sub("<redacted>", text)
        return text
    return value


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


class CollectorStore:
    def __init__(self, database: Database):
        self.database = database

    def ingest(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        accepted = 0
        rejected = 0
        with self.database.connect() as conn:
            touched_routes: set[str] = set()
            touched_deps: set[str] = set()
            route_token = _BATCH_ROUTES.set(touched_routes)
            dep_token = _BATCH_DEPS.set(touched_deps)
            try:
                for event in events:
                    try:
                        self._ingest_one(conn, event)
                        accepted += 1
                    except (KeyError, TypeError, ValueError, sqlite3.Error):
                        rejected += 1
                for route_id in touched_routes:
                    self._refresh_route(conn, route_id)
                for dep_id in touched_deps:
                    self._refresh_dependency(conn, dep_id)
            finally:
                _BATCH_ROUTES.reset(route_token)
                _BATCH_DEPS.reset(dep_token)
        return {"accepted": accepted, "rejected": rejected, "server_time": now_iso()}

    def cleanup(
        self,
        retention_days: int,
        *,
        min_log_minutes: int = 60,
        exception_window_minutes: int = 180,
        raw_event_retention_hours: int | None = None,
        regular_log_retention_hours: int | None = None,
        trace_retention_days: int | None = None,
        duration_retention_days: int | None = None,
        exception_retention_days: int | None = None,
        aggregate_retention_days: int | None = None,
    ) -> None:
        with self.database.connect() as conn:
            stored = self._stored_retention_settings(conn)
            retention_days = int(stored.get("retention_days", retention_days))
            min_log_minutes = int(stored.get("min_log_minutes", min_log_minutes))
            exception_window_minutes = int(stored.get("exception_window_minutes", exception_window_minutes))
            now = datetime.now(UTC)
            cutoff = (now - timedelta(days=retention_days)).isoformat().replace("+00:00", "Z")
            raw_event_cutoff = (now - timedelta(hours=raw_event_retention_hours or retention_days * 24)).isoformat().replace("+00:00", "Z")
            regular_log_cutoff = (now - timedelta(hours=regular_log_retention_hours or max(min_log_minutes, 60) / 60)).isoformat().replace("+00:00", "Z")
            trace_cutoff = (now - timedelta(days=trace_retention_days or retention_days)).isoformat().replace("+00:00", "Z")
            duration_cutoff = (now - timedelta(days=duration_retention_days or retention_days)).isoformat().replace("+00:00", "Z")
            exception_cutoff = (now - timedelta(days=exception_retention_days or max(retention_days, 30))).isoformat().replace("+00:00", "Z")
            aggregate_cutoff = (now - timedelta(days=aggregate_retention_days or 365)).isoformat().replace("+00:00", "Z")
            self._prepare_retention_protection(conn, now, exception_window_minutes)
            # Commit so concurrent ingest writers can take the writer lock between deletes.
            # Temp tables created above live for the connection's lifetime, not the transaction.
            conn.commit()
            deletions: list[tuple[str, tuple[Any, ...]]] = [
                (
                    """
                    DELETE FROM logs
                    WHERE timestamp < ?
                      AND UPPER(COALESCE(level,'')) NOT IN ('ERROR','CRITICAL')
                      AND id NOT IN (SELECT id FROM protected_logs)
                      AND COALESCE(trace_id, '') NOT IN (SELECT trace_id FROM protected_traces)
                    """,
                    (regular_log_cutoff,),
                ),
                (
                    """
                    DELETE FROM logs
                    WHERE timestamp < ? AND timestamp < ?
                      AND id NOT IN (SELECT id FROM protected_logs)
                      AND COALESCE(trace_id, '') NOT IN (SELECT trace_id FROM protected_traces)
                    """,
                    (cutoff, regular_log_cutoff),
                ),
                (
                    """
                    DELETE FROM events
                    WHERE timestamp < ?
                      AND COALESCE(trace_id, '') NOT IN (SELECT trace_id FROM protected_traces)
                    """,
                    (raw_event_cutoff,),
                ),
                ("DELETE FROM route_durations WHERE timestamp < ?", (duration_cutoff,)),
                ("DELETE FROM dependency_durations WHERE timestamp < ?", (duration_cutoff,)),
                (
                    """
                    DELETE FROM spans
                    WHERE COALESCE(finished_at, started_at) < ?
                      AND COALESCE(trace_id, '') NOT IN (SELECT trace_id FROM protected_traces)
                    """,
                    (trace_cutoff,),
                ),
                (
                    """
                    DELETE FROM traces
                    WHERE COALESCE(finished_at, started_at) < ?
                      AND COALESCE(id, '') NOT IN (SELECT trace_id FROM protected_traces)
                    """,
                    (trace_cutoff,),
                ),
                ("DELETE FROM exceptions WHERE last_seen < ?", (exception_cutoff,)),
                ("DELETE FROM route_metrics_hourly WHERE bucket_start < ?", (aggregate_cutoff,)),
                ("DELETE FROM dependency_metrics_hourly WHERE bucket_start < ?", (aggregate_cutoff,)),
                ("DELETE FROM log_metrics_hourly WHERE bucket_start < ?", (aggregate_cutoff,)),
            ]
            for sql, params in deletions:
                conn.execute(sql, params)
                conn.commit()

    def _stored_retention_settings(self, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute("SELECT value_json FROM collector_settings WHERE key='retention'").fetchone()
        if not row:
            return {}
        try:
            data = json.loads(row["value_json"] or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _prepare_retention_protection(self, conn: sqlite3.Connection, now: datetime, exception_window_minutes: int) -> None:
        conn.execute("DROP TABLE IF EXISTS protected_traces")
        conn.execute("DROP TABLE IF EXISTS protected_logs")
        conn.execute("CREATE TEMP TABLE protected_traces(trace_id TEXT PRIMARY KEY)")
        conn.execute("CREATE TEMP TABLE protected_logs(id TEXT PRIMARY KEY)")
        for row in conn.execute("SELECT sample_trace_id, last_seen FROM exceptions").fetchall():
            trace_id = row["sample_trace_id"]
            if trace_id:
                conn.execute("INSERT OR IGNORE INTO protected_traces(trace_id) VALUES(?)", (trace_id,))
            seen = self._parse_iso(row["last_seen"])
            if seen:
                start = (seen - timedelta(minutes=exception_window_minutes)).isoformat().replace("+00:00", "Z")
                end = (seen + timedelta(minutes=exception_window_minutes)).isoformat().replace("+00:00", "Z")
                for log in conn.execute("SELECT id FROM logs WHERE timestamp BETWEEN ? AND ?", (start, end)).fetchall():
                    conn.execute("INSERT OR IGNORE INTO protected_logs(id) VALUES(?)", (log["id"],))
        now_iso_value = now.isoformat().replace("+00:00", "Z")
        for pin in conn.execute("SELECT trace_id, start_time, end_time FROM retention_pins WHERE expires_at IS NULL OR expires_at > ?", (now_iso_value,)).fetchall():
            if pin["trace_id"]:
                conn.execute("INSERT OR IGNORE INTO protected_traces(trace_id) VALUES(?)", (pin["trace_id"],))
            if pin["start_time"] and pin["end_time"]:
                for log in conn.execute("SELECT id FROM logs WHERE timestamp BETWEEN ? AND ?", (pin["start_time"], pin["end_time"])).fetchall():
                    conn.execute("INSERT OR IGNORE INTO protected_logs(id) VALUES(?)", (log["id"],))

    def _parse_iso(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _ingest_one(self, conn: sqlite3.Connection, event: dict[str, Any]) -> None:
        if not isinstance(event, dict) or "kind" not in event:
            raise ValueError("event.kind is required")
        service = event.get("service") or {}
        project_name = str(service.get("project_name") or "default")
        service_name = str(service.get("name") or "unknown-service")
        app_id = stable_id(project_name, service_name)
        timestamp = str(event.get("timestamp") or now_iso())
        kind = str(event["kind"])
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError("event.payload must be an object")
        self._upsert_app(conn, app_id, service_name, service, timestamp, payload if kind == "app_started" else {})
        event_id = str(event.get("event_id") or uuid4())
        cursor = conn.execute(
            "INSERT OR IGNORE INTO events(id, app_id, trace_id, span_id, parent_span_id, kind, timestamp, payload_json, raw_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (event_id, app_id, event.get("trace_id"), event.get("span_id"), event.get("parent_span_id"), kind, timestamp, dumps(payload), dumps(event)),
        )
        if cursor.rowcount == 0:
            return
        handler = getattr(self, f"_handle_{kind}", None)
        if handler:
            handler(conn, app_id, event, payload, timestamp)

    def _upsert_app(self, conn: sqlite3.Connection, app_id: str, service_name: str, service: dict[str, Any], timestamp: str, metadata: dict[str, Any]) -> None:
        display_name = service.get("display_name") or metadata.get("display_name") or metadata.get("app_name")
        conn.execute(
            """
            INSERT INTO apps(id, project_name, service_name, display_name, language, runtime_version, sdk_version, first_seen, last_seen, metadata_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen, project_name=COALESCE(excluded.project_name, apps.project_name), display_name=COALESCE(excluded.display_name, apps.display_name), language=COALESCE(excluded.language, apps.language),
              runtime_version=COALESCE(excluded.runtime_version, apps.runtime_version), sdk_version=COALESCE(excluded.sdk_version, apps.sdk_version)
            """,
            (app_id, service.get("project_name") or "default", service_name, display_name, service.get("language"), service.get("runtime_version"), service.get("sdk_version"), timestamp, timestamp, dumps(metadata)),
        )

    def _route_values(self, payload: dict[str, Any]) -> tuple[str, str]:
        method = payload.get("method") or payload.get("http_method")
        route_pattern = payload.get("route_pattern") or payload.get("route") or payload.get("path") or "unknown"
        if not method and isinstance(payload.get("structured"), dict):
            structured = payload["structured"]
            method = structured.get("method") or structured.get("http_method")
            route_pattern = route_pattern if route_pattern != "unknown" else structured.get("path") or structured.get("route_pattern") or structured.get("route") or "unknown"
        return str(method or "UNKNOWN"), str(route_pattern)

    def _upsert_route(self, conn: sqlite3.Connection, app_id: str, method: str, route_pattern: str, timestamp: str) -> str:
        route_id = stable_id(app_id, method, route_pattern)
        conn.execute(
            "INSERT INTO routes(id, app_id, method, route_pattern, last_seen) VALUES(?,?,?,?,?) ON CONFLICT(app_id, method, route_pattern) DO UPDATE SET last_seen=excluded.last_seen",
            (route_id, app_id, method, route_pattern, timestamp),
        )
        return route_id

    def _handle_route_discovered(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        method, route_pattern = self._route_values(payload)
        self._upsert_route(conn, app_id, method, route_pattern, timestamp)

    def _handle_request_started(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        method, route_pattern = self._route_values(payload)
        route_id = self._upsert_route(conn, app_id, method, route_pattern, timestamp)
        conn.execute("INSERT OR IGNORE INTO traces(id, app_id, route_id, started_at) VALUES(?,?,?,?)", (event.get("trace_id"), app_id, route_id, timestamp))

    def _handle_request_finished(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        method, route_pattern = self._route_values(payload)
        route_id = self._upsert_route(conn, app_id, method, route_pattern, timestamp)
        duration = float(payload.get("duration_ms") or payload.get("duration") or 0)
        status_code = int(payload.get("status_code") or 0)
        has_error = int(status_code >= 500 or bool(payload.get("error")))
        trace_id = event.get("trace_id")
        conn.execute("INSERT INTO route_durations(route_id, trace_id, duration_ms, status_code, timestamp) VALUES(?,?,?,?,?)", (route_id, trace_id, duration, status_code, timestamp))
        conn.execute(
            """
            INSERT INTO traces(id, app_id, route_id, finished_at, duration_ms, status_code, has_error) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(id, app_id) DO UPDATE SET route_id=excluded.route_id, finished_at=excluded.finished_at,
              duration_ms=excluded.duration_ms, status_code=excluded.status_code, has_error=excluded.has_error
            """,
            (trace_id, app_id, route_id, timestamp, duration, status_code, has_error),
        )
        self._upsert_route_metric(conn, app_id, route_id, timestamp, duration, has_error)
        touched_routes = _BATCH_ROUTES.get()
        if touched_routes is None:
            self._refresh_route(conn, route_id)
        else:
            touched_routes.add(route_id)

    def _handle_span_started(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        self._insert_span(conn, app_id, event, payload, timestamp, None)

    def _handle_span_finished(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        self._insert_span(conn, app_id, event, payload, timestamp, float(payload.get("duration_ms") or 0))

    def _insert_span(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str, duration: float | None) -> None:
        conn.execute(
            "INSERT INTO spans(trace_id, app_id, span_id, parent_span_id, name, kind, started_at, finished_at, duration_ms, status, payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (event.get("trace_id"), app_id, event.get("span_id"), event.get("parent_span_id"), payload.get("name"), payload.get("kind"), payload.get("started_at") or timestamp, timestamp, duration, payload.get("status"), dumps(payload)),
        )

    def _handle_exception_raised(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        exc_type = str(payload.get("type") or payload.get("exception_type") or "Exception")
        message = str(payload.get("message") or "")[:512]
        fingerprint = str(payload.get("fingerprint") or stable_id(exc_type, message))
        exception_id = stable_id(app_id, fingerprint)
        conn.execute(
            """
            INSERT INTO exceptions(id, app_id, fingerprint, type, normalized_message, first_seen, last_seen, count, sample_trace_id, sample_payload_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(app_id, fingerprint) DO UPDATE SET last_seen=excluded.last_seen, count=exceptions.count + 1, sample_trace_id=excluded.sample_trace_id
            """,
            (exception_id, app_id, fingerprint, exc_type, message, timestamp, timestamp, 1, event.get("trace_id"), dumps(payload)),
        )
        conn.execute("UPDATE traces SET has_error=1 WHERE app_id=? AND id=?", (app_id, event.get("trace_id")))

    def _handle_log_record(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        method, route_pattern = self._route_values(payload)
        route_id = None if route_pattern == "unknown" else self._upsert_route(conn, app_id, method, route_pattern, timestamp)
        level = str(payload.get("level") or "INFO").upper()
        conn.execute(
            "INSERT OR IGNORE INTO logs(id, app_id, trace_id, span_id, route_id, timestamp, level, logger_name, message, source_file, source_function, source_line, structured_json, exception_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(event.get("event_id") or uuid4()), app_id, event.get("trace_id"), event.get("span_id"), route_id, timestamp, level, payload.get("logger_name") or payload.get("logger"), redact(payload.get("message") or ""), payload.get("source_file"), payload.get("source_function"), payload.get("source_line"), dumps(payload.get("structured") or {}), dumps(payload.get("exception") or {})),
        )
        self._upsert_log_metric(conn, app_id, route_id, level, timestamp)

    def _handle_dependency_inventory(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        for dep in payload.get("dependencies") or []:
            name = dep.get("name") if isinstance(dep, dict) else str(dep)
            self._upsert_dependency(conn, app_id, "package", str(name), dep.get("version") if isinstance(dep, dict) else None, 0, False, timestamp)

    def _handle_db_query(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        tables = payload.get("tables") if isinstance(payload.get("tables"), list) else []
        target = payload.get("target") or payload.get("database") or payload.get("table") or (tables[0] if tables else None) or "unknown-db"
        operation = payload.get("operation") or payload.get("statement_fingerprint") or "query"
        self._upsert_dependency(conn, app_id, "db", str(target), str(operation), float(payload.get("duration_ms") or 0), bool(payload.get("error") or payload.get("error_type")), timestamp)

    def _handle_http_client_call(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        self._upsert_dependency(conn, app_id, "http", str(payload.get("host") or payload.get("url") or "unknown"), str(payload.get("method") or "GET"), float(payload.get("duration_ms") or 0), bool(payload.get("error")), timestamp)

    def _handle_llm_call(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        provider = str(payload.get("provider") or "unknown")
        model = str(payload.get("model") or "unknown")
        route_id = payload.get("route_id")
        usage_id = stable_id(app_id, provider, model, route_id)
        conn.execute(
            """
            INSERT INTO llm_usage(id, app_id, provider, model, route_id, call_count, input_tokens, output_tokens, error_count, total_duration_ms)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(app_id, provider, model, route_id) DO UPDATE SET call_count=llm_usage.call_count+1,
              input_tokens=llm_usage.input_tokens+excluded.input_tokens, output_tokens=llm_usage.output_tokens+excluded.output_tokens,
              error_count=llm_usage.error_count+excluded.error_count, total_duration_ms=llm_usage.total_duration_ms+excluded.total_duration_ms
            """,
            (usage_id, app_id, provider, model, route_id, 1, int(payload.get("input_tokens") or 0), int(payload.get("output_tokens") or 0), int(bool(payload.get("error"))), float(payload.get("duration_ms") or 0)),
        )

    def _upsert_dependency(self, conn: sqlite3.Connection, app_id: str, dep_type: str, target: str, operation: str | None, duration: float, error: bool, timestamp: str) -> str:
        dep_id = stable_id(app_id, dep_type, target, operation)
        current = conn.execute("SELECT call_count, avg_duration_ms FROM dependencies WHERE id=?", (dep_id,)).fetchone()
        count = int(current["call_count"]) if current else 0
        avg = float(current["avg_duration_ms"]) if current else 0
        new_avg = ((avg * count) + duration) / (count + 1) if duration else avg
        conn.execute(
            "INSERT INTO dependencies(id, app_id, dependency_type, target, operation, call_count, error_count, avg_duration_ms) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(app_id, dependency_type, target, operation) DO UPDATE SET call_count=dependencies.call_count+1, error_count=dependencies.error_count+excluded.error_count, avg_duration_ms=excluded.avg_duration_ms",
            (dep_id, app_id, dep_type, target, operation, 1, int(error), new_avg),
        )
        if duration:
            conn.execute("INSERT INTO dependency_durations(dependency_id, duration_ms, timestamp) VALUES(?,?,?)", (dep_id, duration, timestamp))
            self._upsert_dependency_metric(conn, app_id, dep_id, timestamp, duration, error)
            touched_deps = _BATCH_DEPS.get()
            if touched_deps is None:
                self._refresh_dependency(conn, dep_id)
            else:
                touched_deps.add(dep_id)
        return dep_id

    def _refresh_route(self, conn: sqlite3.Connection, route_id: str) -> None:
        totals = conn.execute("SELECT COALESCE(SUM(request_count),0) call_count, COALESCE(SUM(error_count),0) error_count FROM route_metrics_hourly WHERE route_id=?", (route_id,)).fetchone()
        rows = conn.execute("SELECT duration_ms FROM (SELECT duration_ms FROM route_durations WHERE route_id=? ORDER BY timestamp DESC LIMIT 10000) ORDER BY duration_ms", (route_id,)).fetchall()
        if not rows:
            return
        durations = [float(row["duration_ms"]) for row in rows]
        p50 = durations[int((len(durations) - 1) * 0.50)]
        p95 = durations[int((len(durations) - 1) * 0.95)]
        conn.execute("UPDATE routes SET call_count=?, error_count=?, p50_ms=?, p95_ms=? WHERE id=?", (int(totals["call_count"] or 0), int(totals["error_count"] or 0), p50, p95, route_id))

    def _refresh_dependency(self, conn: sqlite3.Connection, dep_id: str) -> None:
        rows = conn.execute("SELECT duration_ms FROM dependency_durations WHERE dependency_id=? ORDER BY duration_ms LIMIT 10000", (dep_id,)).fetchall()
        if rows:
            p95 = float(rows[int((len(rows) - 1) * 0.95)]["duration_ms"])
            conn.execute("UPDATE dependencies SET p95_duration_ms=? WHERE id=?", (p95, dep_id))

    def _upsert_route_metric(self, conn: sqlite3.Connection, app_id: str, route_id: str, timestamp: str, duration: float, has_error: int) -> None:
        bucket = hour_bucket(timestamp)
        conn.execute(
            """
            INSERT INTO route_metrics_hourly(route_id, app_id, bucket_start, request_count, error_count, total_duration_ms, min_duration_ms, max_duration_ms)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(route_id, bucket_start) DO UPDATE SET
              request_count=route_metrics_hourly.request_count+1,
              error_count=route_metrics_hourly.error_count+excluded.error_count,
              total_duration_ms=route_metrics_hourly.total_duration_ms+excluded.total_duration_ms,
              min_duration_ms=CASE WHEN route_metrics_hourly.min_duration_ms IS NULL OR excluded.min_duration_ms < route_metrics_hourly.min_duration_ms THEN excluded.min_duration_ms ELSE route_metrics_hourly.min_duration_ms END,
              max_duration_ms=CASE WHEN route_metrics_hourly.max_duration_ms IS NULL OR excluded.max_duration_ms > route_metrics_hourly.max_duration_ms THEN excluded.max_duration_ms ELSE route_metrics_hourly.max_duration_ms END
            """,
            (route_id, app_id, bucket, 1, has_error, duration, duration, duration),
        )

    def _upsert_dependency_metric(self, conn: sqlite3.Connection, app_id: str, dep_id: str, timestamp: str, duration: float, error: bool) -> None:
        bucket = hour_bucket(timestamp)
        conn.execute(
            """
            INSERT INTO dependency_metrics_hourly(dependency_id, app_id, bucket_start, call_count, error_count, total_duration_ms, min_duration_ms, max_duration_ms)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(dependency_id, bucket_start) DO UPDATE SET
              call_count=dependency_metrics_hourly.call_count+1,
              error_count=dependency_metrics_hourly.error_count+excluded.error_count,
              total_duration_ms=dependency_metrics_hourly.total_duration_ms+excluded.total_duration_ms,
              min_duration_ms=CASE WHEN dependency_metrics_hourly.min_duration_ms IS NULL OR excluded.min_duration_ms < dependency_metrics_hourly.min_duration_ms THEN excluded.min_duration_ms ELSE dependency_metrics_hourly.min_duration_ms END,
              max_duration_ms=CASE WHEN dependency_metrics_hourly.max_duration_ms IS NULL OR excluded.max_duration_ms > dependency_metrics_hourly.max_duration_ms THEN excluded.max_duration_ms ELSE dependency_metrics_hourly.max_duration_ms END
            """,
            (dep_id, app_id, bucket, 1, int(error), duration, duration, duration),
        )

    def _upsert_log_metric(self, conn: sqlite3.Connection, app_id: str, route_id: str | None, level: str, timestamp: str) -> None:
        bucket = hour_bucket(timestamp)
        conn.execute(
            """
            INSERT INTO log_metrics_hourly(app_id, route_id, level, bucket_start, log_count) VALUES(?,?,?,?,?)
            ON CONFLICT(app_id, route_id, level, bucket_start) DO UPDATE SET log_count=log_metrics_hourly.log_count+1
            """,
            (app_id, route_id or "", level, bucket, 1),
        )
