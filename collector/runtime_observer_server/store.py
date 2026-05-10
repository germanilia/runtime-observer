from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from .db import Database

SECRET_KEYS = re.compile(r"password|passwd|secret|token|api_?key|authorization|cookie|credential|private_key|access_key|refresh_token|id_token", re.I)
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
            for event in events:
                try:
                    self._ingest_one(conn, event)
                    accepted += 1
                except (KeyError, TypeError, ValueError, sqlite3.Error):
                    rejected += 1
        return {"accepted": accepted, "rejected": rejected, "server_time": now_iso()}

    def cleanup(self, retention_days: int) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat().replace("+00:00", "Z")
        with self.database.connect() as conn:
            for table in ["events", "logs", "route_durations", "dependency_durations"]:
                conn.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))

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
        conn.execute(
            "INSERT OR IGNORE INTO events(id, app_id, trace_id, span_id, parent_span_id, kind, timestamp, payload_json, raw_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (event_id, app_id, event.get("trace_id"), event.get("span_id"), event.get("parent_span_id"), kind, timestamp, dumps(payload), dumps(event)),
        )
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
        return str(payload.get("method") or payload.get("http_method") or "UNKNOWN"), str(payload.get("route_pattern") or payload.get("route") or payload.get("path") or "unknown")

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
        self._refresh_route(conn, route_id)

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
            ON CONFLICT(app_id, fingerprint) DO UPDATE SET last_seen=excluded.last_seen, count=count + 1, sample_trace_id=excluded.sample_trace_id
            """,
            (exception_id, app_id, fingerprint, exc_type, message, timestamp, timestamp, 1, event.get("trace_id"), dumps(payload)),
        )
        conn.execute("UPDATE traces SET has_error=1 WHERE app_id=? AND id=?", (app_id, event.get("trace_id")))

    def _handle_log_record(self, conn: sqlite3.Connection, app_id: str, event: dict[str, Any], payload: dict[str, Any], timestamp: str) -> None:
        method, route_pattern = self._route_values(payload)
        route_id = None if route_pattern == "unknown" else self._upsert_route(conn, app_id, method, route_pattern, timestamp)
        conn.execute(
            "INSERT OR IGNORE INTO logs(id, app_id, trace_id, span_id, route_id, timestamp, level, logger_name, message, source_file, source_function, source_line, structured_json, exception_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(event.get("event_id") or uuid4()), app_id, event.get("trace_id"), event.get("span_id"), route_id, timestamp, payload.get("level"), payload.get("logger_name") or payload.get("logger"), redact(payload.get("message") or ""), payload.get("source_file"), payload.get("source_function"), payload.get("source_line"), dumps(payload.get("structured") or {}), dumps(payload.get("exception") or {})),
        )

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
            ON CONFLICT(app_id, provider, model, route_id) DO UPDATE SET call_count=call_count+1,
              input_tokens=input_tokens+excluded.input_tokens, output_tokens=output_tokens+excluded.output_tokens,
              error_count=error_count+excluded.error_count, total_duration_ms=total_duration_ms+excluded.total_duration_ms
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
            "INSERT INTO dependencies(id, app_id, dependency_type, target, operation, call_count, error_count, avg_duration_ms) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(app_id, dependency_type, target, operation) DO UPDATE SET call_count=call_count+1, error_count=error_count+excluded.error_count, avg_duration_ms=excluded.avg_duration_ms",
            (dep_id, app_id, dep_type, target, operation, 1, int(error), new_avg),
        )
        if duration:
            conn.execute("INSERT INTO dependency_durations(dependency_id, duration_ms, timestamp) VALUES(?,?,?)", (dep_id, duration, timestamp))
            self._refresh_dependency(conn, dep_id)
        return dep_id

    def _refresh_route(self, conn: sqlite3.Connection, route_id: str) -> None:
        rows = conn.execute("SELECT duration_ms, status_code FROM route_durations WHERE route_id=? ORDER BY duration_ms", (route_id,)).fetchall()
        if not rows:
            return
        durations = [float(row["duration_ms"]) for row in rows]
        p50 = durations[int((len(durations) - 1) * 0.50)]
        p95 = durations[int((len(durations) - 1) * 0.95)]
        errors = sum(1 for row in rows if int(row["status_code"] or 0) >= 500)
        conn.execute("UPDATE routes SET call_count=?, error_count=?, p50_ms=?, p95_ms=? WHERE id=?", (len(rows), errors, p50, p95, route_id))

    def _refresh_dependency(self, conn: sqlite3.Connection, dep_id: str) -> None:
        rows = conn.execute("SELECT duration_ms FROM dependency_durations WHERE dependency_id=? ORDER BY duration_ms", (dep_id,)).fetchall()
        if rows:
            p95 = float(rows[int((len(rows) - 1) * 0.95)]["duration_ms"])
            conn.execute("UPDATE dependencies SET p95_duration_ms=? WHERE id=?", (p95, dep_id))
