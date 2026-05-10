from __future__ import annotations

import json
from datetime import datetime, timedelta, UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from .config import Settings
from .db import Database
from .store import row_to_dict, rows_to_dicts


def get_db(request: Request) -> Database:
    return request.app.state.database


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_bearer(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if settings.insecure_dev_mode:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {settings.api_key}":
        raise HTTPException(status_code=401, detail="Invalid Runtime Observer API key")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def visible_apps_clause(alias: str = "apps") -> tuple[str, tuple[str, ...]]:
    return "1=1", ()


def log_window_start(log_window_minutes: int | None) -> str | None:
    if not log_window_minutes or log_window_minutes <= 0:
        return None
    return iso(datetime.now(UTC) - timedelta(minutes=log_window_minutes))


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
            SELECT events.*, apps.service_name
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

    @router.post("/v1/ingest", dependencies=[Depends(require_bearer)])
    async def ingest(request: Request) -> dict[str, Any]:
        body = await request.json()
        events = body.get("events")
        if not isinstance(events, list):
            raise HTTPException(status_code=422, detail="events must be a list")
        return request.app.state.store.ingest(events)

    @router.post("/v1/ingest/browser")
    async def ingest_browser(request: Request, api_key: str = "", settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        if not settings.insecure_dev_mode and api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid Runtime Observer API key")
        body = await request.json()
        events = body.get("events")
        if not isinstance(events, list):
            raise HTTPException(status_code=422, detail="events must be a list")
        return request.app.state.store.ingest(events)

    @router.get("/api/apps")
    def apps(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        clause, params = visible_apps_clause("apps")
        with db.connect() as conn:
            rows = conn.execute(f"SELECT * FROM apps WHERE {clause} ORDER BY last_seen DESC", params).fetchall()
            return rows_to_dicts(rows)

    @router.get("/api/overview")
    def global_overview(log_window_minutes: int | None = Query(60), log_limit: int = Query(300, ge=20, le=2000), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        log_start = log_window_start(log_window_minutes)
        log_time_clause = "AND logs.timestamp >= ?" if log_start else ""
        log_params: list[Any] = [log_start] if log_start else []
        with db.connect() as conn:
            visible_clause, visible_params = visible_apps_clause("apps")
            apps = rows_to_dicts(conn.execute(f"SELECT * FROM apps WHERE {visible_clause} ORDER BY last_seen DESC", visible_params).fetchall())
            totals = row_to_dict(
                conn.execute(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM events) event_count,
                      (SELECT COUNT(*) FROM logs) log_count,
                      (SELECT COUNT(*) FROM exceptions) exception_count,
                      (SELECT COALESCE(SUM(call_count),0) FROM routes) request_count,
                      (SELECT COALESCE(SUM(error_count),0) FROM routes) error_count
                    """
                ).fetchone()
            )
            by_kind = rows_to_dicts(conn.execute("SELECT events.app_id, apps.service_name, apps.display_name, events.kind, COUNT(*) count FROM events JOIN apps ON apps.id=events.app_id GROUP BY events.app_id, apps.service_name, apps.display_name, events.kind ORDER BY count DESC").fetchall())
            by_level = rows_to_dicts(conn.execute("SELECT logs.app_id, apps.service_name, apps.display_name, logs.level, COUNT(*) count FROM logs JOIN apps ON apps.id=logs.app_id GROUP BY logs.app_id, apps.service_name, apps.display_name, logs.level ORDER BY count DESC").fetchall())
            recent_errors = rows_to_dicts(
                conn.execute(
                    """
                    SELECT exceptions.*, apps.service_name
                    FROM exceptions JOIN apps ON apps.id = exceptions.app_id
                    ORDER BY last_seen DESC LIMIT 20
                    """
                ).fetchall()
            )
            recent_logs = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT logs.*, apps.service_name
                    FROM logs JOIN apps ON apps.id = logs.app_id
                    WHERE 1=1
                      {log_time_clause}
                    ORDER BY timestamp DESC LIMIT ?
                    """,
                    [*log_params, log_limit],
                ).fetchall()
            )
            routes = rows_to_dicts(
                conn.execute(
                    """
                    SELECT routes.*, apps.service_name
                    FROM routes JOIN apps ON apps.id = routes.app_id
                    ORDER BY routes.last_seen DESC, routes.p95_ms DESC LIMIT 60
                    """
                ).fetchall()
            )
            dependencies = rows_to_dicts(
                conn.execute(
                    """
                    SELECT dependencies.*, apps.service_name
                    FROM dependencies JOIN apps ON apps.id = dependencies.app_id
                    WHERE dependencies.target NOT IN ('unknown', 'unknown-db')
                      AND dependencies.target IS NOT NULL
                      AND dependencies.target != ''
                    ORDER BY dependencies.call_count DESC LIMIT 40
                    """
                ).fetchall()
            )
            dependencies = enrich_dependencies(conn, dependencies)
            storage = db.path.stat().st_size if db.path.exists() else 0
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
                "retention": {"days": settings.retention_days, "database_bytes": storage},
            }

    @router.get("/api/apps/{app_id}/overview")
    def overview(app_id: str, db: Database = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        with db.connect() as conn:
            app = row_to_dict(conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone())
            if not app:
                raise HTTPException(status_code=404, detail="app not found")
            counts = row_to_dict(conn.execute("SELECT COUNT(*) event_count FROM events WHERE app_id=?", (app_id,)).fetchone())
            request_count = conn.execute("SELECT COALESCE(SUM(call_count),0) FROM routes WHERE app_id=?", (app_id,)).fetchone()[0]
            error_count = conn.execute("SELECT COALESCE(SUM(error_count),0) FROM routes WHERE app_id=?", (app_id,)).fetchone()[0]
            log_count = conn.execute("SELECT COUNT(*) FROM logs WHERE app_id=?", (app_id,)).fetchone()[0]
            slow_routes = rows_to_dicts(conn.execute("SELECT * FROM routes WHERE app_id=? ORDER BY p95_ms DESC LIMIT 10", (app_id,)).fetchall())
            failing_routes = rows_to_dicts(conn.execute("SELECT * FROM routes WHERE app_id=? AND error_count > 0 ORDER BY error_count DESC LIMIT 10", (app_id,)).fetchall())
            storage = db.path.stat().st_size if db.path.exists() else 0
            return {"app": app, "event_count": counts["event_count"], "request_count": request_count, "error_count": error_count, "log_count": log_count, "top_slow_routes": slow_routes, "top_failing_routes": failing_routes, "retention": {"days": settings.retention_days, "database_bytes": storage}}

    @router.get("/api/apps/{app_id}/routes")
    def routes(app_id: str, db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        with db.connect() as conn:
            return rows_to_dicts(conn.execute("SELECT * FROM routes WHERE app_id=? ORDER BY last_seen DESC", (app_id,)).fetchall())

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
    def exception_detail(app_id: str, exception_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            exception = row_to_dict(conn.execute("SELECT * FROM exceptions WHERE app_id=? AND id=?", (app_id, exception_id)).fetchone())
            if not exception:
                raise HTTPException(status_code=404, detail="exception not found")
            same_trace_logs = rows_to_dicts(conn.execute("SELECT logs.*, apps.service_name FROM logs JOIN apps ON apps.id=logs.app_id WHERE trace_id=? ORDER BY timestamp", (exception.get("sample_trace_id"),)).fetchall()) if exception.get("sample_trace_id") else []
            nearby = logs_around(conn, exception.get("last_seen"), trace_id=exception.get("sample_trace_id"), window_seconds=180)
            trace = trace_detail(app_id, exception["sample_trace_id"], db) if exception.get("sample_trace_id") else None
            return {"exception": exception, "trace": trace, "correlated_logs": same_trace_logs, "nearby_logs_all_apps": nearby}

    @router.get("/api/apps/{app_id}/logs")
    def logs(app_id: str, trace_id: str | None = None, route_id: str | None = None, level: str | None = None, logger: str | None = None, text: str | None = None, start: str | None = None, end: str | None = None, limit: int = Query(100, le=500), db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        where = ["logs.app_id=?"]
        params: list[Any] = [app_id]
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
    def all_logs(level: str | None = None, text: str | None = None, start: str | None = None, end: str | None = None, limit: int = Query(200, le=1000), db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
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
    def dependencies(app_id: str, db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        with db.connect() as conn:
            return rows_to_dicts(conn.execute("SELECT * FROM dependencies WHERE app_id=? ORDER BY call_count DESC", (app_id,)).fetchall())

    @router.get("/api/apps/{app_id}/call-graph")
    def call_graph(app_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            routes = rows_to_dicts(conn.execute("SELECT id, method, route_pattern, call_count, error_count FROM routes WHERE app_id=?", (app_id,)).fetchall())
            deps = rows_to_dicts(conn.execute("SELECT dependency_type, target, operation, call_count, error_count FROM dependencies WHERE app_id=?", (app_id,)).fetchall())
            llm = rows_to_dicts(conn.execute("SELECT provider, model, route_id, call_count, input_tokens, output_tokens FROM llm_usage WHERE app_id=?", (app_id,)).fetchall())
            return {"routes": routes, "dependencies": deps, "llm_usage": llm}

    @router.get("/api/entrypoints")
    def entrypoints(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    """
                    SELECT routes.*, apps.service_name,
                      (SELECT COUNT(*) FROM traces WHERE traces.route_id=routes.id AND traces.app_id=routes.app_id) trace_count,
                      (SELECT COUNT(*) FROM logs WHERE logs.route_id=routes.id AND logs.app_id=routes.app_id) log_count
                    FROM routes JOIN apps ON apps.id=routes.app_id
                    ORDER BY routes.last_seen DESC, routes.call_count DESC
                    """
                ).fetchall()
            )

    @router.get("/api/routes/{route_id}/requests")
    def route_requests(route_id: str, limit: int = Query(50, le=250), db: Database = Depends(get_db)) -> dict[str, Any]:
        with db.connect() as conn:
            route = row_to_dict(
                conn.execute(
                    """
                    SELECT routes.*, apps.service_name
                    FROM routes JOIN apps ON apps.id=routes.app_id
                    WHERE routes.id=?
                    """,
                    (route_id,),
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
        data = trace_map(trace_id, db)
        lines = [f"# Runtime Observer Trace Context", "", f"Trace ID: `{trace_id}`", ""]
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
                related_logs.extend(logs_around(conn, event.get("timestamp"), trace_id=event.get("trace_id"), window_seconds=30, limit=40))
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

    @router.get("/api/traces/{trace_id}/map")
    def trace_map(trace_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
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
            events = rows_to_dicts(conn.execute("SELECT events.*, apps.service_name FROM events JOIN apps ON apps.id=events.app_id WHERE events.trace_id=? ORDER BY events.timestamp", (trace_id,)).fetchall())
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
            return {"trace_id": trace_id, "traces": traces, "events": events, "spans": spans, "logs": logs, "flow_logs": flow_logs, "nearby_background_logs": nearby_background_logs, "exceptions": exceptions, "dependencies": dependencies, "timeline": timeline, "nearby_logs_all_apps": nearby_logs}

    @router.post("/api/admin/clear", dependencies=[Depends(require_bearer)])
    def clear(db: Database = Depends(get_db)) -> dict[str, str]:
        db.clear()
        return {"status": "cleared"}

    @router.get("/api/agent/tools")
    def agent_tools() -> dict[str, list[str]]:
        return {"tools": ["get_application_map", "get_route_summary", "get_trace", "get_trace_agent_context", "get_log_agent_context", "get_dependency_context", "get_dependency_agent_context", "get_exception_context", "get_slowest_routes", "get_failing_routes", "get_dependency_map", "get_llm_usage", "search_logs", "search_events"]}

    @router.post("/api/agent/{tool_name}")
    async def agent_tool(tool_name: str, request: Request, db: Database = Depends(get_db)) -> Any:
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
                return dependencies(app_id, db)
            if tool_name == "get_llm_usage":
                group_by = args.get("group_by") or "model"
                group_col = "provider" if group_by == "provider" else "model"
                return rows_to_dicts(conn.execute(f"SELECT {group_col}, SUM(call_count) call_count, SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens, SUM(error_count) error_count FROM llm_usage WHERE app_id=? GROUP BY {group_col}", (app_id,)).fetchall())
            if tool_name == "search_logs":
                filters = args.get("filters") or {}
                return all_logs(filters.get("level"), filters.get("text"), filters.get("start"), filters.get("end"), int(filters.get("limit", 100)), db)
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


DASHBOARD_HTML = r'''
<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Runtime Observer</title>
<style>
:root{--bg:#071019;--panel:#0d1724;--panel2:#111f31;--line:#26364a;--text:#edf5ff;--muted:#9fb1c7;--blue:#5bc0ff;--green:#64f4ac;--yellow:#ffd166;--red:#ff647c;--shadow:0 22px 70px rgba(0,0,0,.32)}*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#08111c,#0a1019 45%,#050910);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.top{position:sticky;top:0;z-index:10;background:rgba(7,16,25,.92);backdrop-filter:blur(18px);border-bottom:1px solid var(--line);padding:16px 22px;display:flex;align-items:center;justify-content:space-between;gap:16px}.brand{display:flex;align-items:center;gap:13px}.mark{width:46px;height:46px;border-radius:16px;background:linear-gradient(135deg,#5bc0ff,#7c3aed 55%,#64f4ac);box-shadow:0 0 34px rgba(91,192,255,.35)}h1{font-size:20px;margin:0}.hint,.small{color:var(--muted);font-size:13px}.status{display:flex;align-items:center;gap:10px}.dot{width:10px;height:10px;border-radius:999px;background:var(--green);box-shadow:0 0 16px var(--green)}button,input,select{background:#0a1320;color:var(--text);border:1px solid var(--line);border-radius:12px;padding:10px 12px;font:inherit}button{cursor:pointer}button:hover{border-color:#5480aa}.primary{background:linear-gradient(135deg,#1f7fb0,#5b45d6);border:0}.layout{display:grid;grid-template-columns:330px minmax(0,1fr);gap:18px;padding:18px}.panel{background:linear-gradient(180deg,rgba(17,31,49,.96),rgba(10,19,32,.96));border:1px solid var(--line);border-radius:22px;box-shadow:var(--shadow);overflow:hidden}.panelTitle{padding:15px 17px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:10px}.panelTitle h2{margin:0;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#d6e7fb}.content{padding:15px}.stack{display:grid;gap:12px}.app,.entry,.traceItem,.log,.error{width:100%;text-align:left;background:#0a1320;border:1px solid var(--line);border-radius:16px;padding:13px;color:var(--text)}.app.active,.entry.active,.traceItem.active{border-color:#62b8f2;background:#112b42}.app b,.entry b{display:block;margin-bottom:4px}.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;padding:4px 9px;color:var(--muted);font-size:12px}.main{display:grid;gap:18px}.kpis{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:12px}.kpi{padding:16px}.kpi .num{font-size:30px;font-weight:800;line-height:1}.kpi .label{margin-top:7px;color:var(--muted);font-size:12px;text-transform:uppercase}.grid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);gap:18px}.bar{display:grid;grid-template-columns:minmax(100px,190px) 1fr auto;gap:10px;align-items:center}.track{height:10px;border-radius:999px;background:#07101a;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--green));border-radius:999px}.fill.err{background:linear-gradient(90deg,var(--red),var(--yellow))}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.list{display:grid;gap:10px;max-height:360px;overflow:auto}.log{cursor:pointer}.log:hover,.error:hover,.traceItem:hover,.entry:hover{border-color:#5c86ad}.logHeader,.routeHeader{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:6px}.level-ERROR,.level-CRITICAL{color:var(--red);border-color:rgba(255,100,124,.55)}.level-WARNING{color:var(--yellow);border-color:rgba(255,209,102,.55)}.level-INFO{color:var(--blue)}.level-DEBUG{color:var(--muted)}.split{display:grid;grid-template-columns:minmax(290px,.85fr) minmax(0,1.15fr);gap:14px}.mapCanvas{min-height:360px;background:radial-gradient(circle at 20% 10%,rgba(91,192,255,.1),transparent 28%),#08111c;border:1px solid var(--line);border-radius:18px;padding:18px;overflow:auto}.nodeRow{display:flex;align-items:center;gap:12px;margin:12px 0}.node{min-width:180px;max-width:310px;border:1px solid var(--line);border-radius:16px;background:#0d1724;padding:12px}.node.route{border-color:rgba(91,192,255,.7)}.node.dep{border-color:rgba(100,244,172,.55)}.node.errorNode{border-color:rgba(255,100,124,.7)}.arrow{width:54px;height:2px;background:linear-gradient(90deg,var(--blue),transparent);position:relative}.arrow:after{content:"";position:absolute;right:0;top:-4px;border-left:8px solid var(--blue);border-top:5px solid transparent;border-bottom:5px solid transparent}.drawer{position:fixed;right:0;top:0;bottom:0;width:min(980px,96vw);background:#07101a;border-left:1px solid var(--line);box-shadow:-30px 0 90px rgba(0,0,0,.55);transform:translateX(105%);transition:.22s ease;z-index:30;display:flex;flex-direction:column}.drawer.open{transform:translateX(0)}.drawerTop{padding:16px 18px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}.drawerBody{padding:18px;overflow:auto}.tabs,.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}.tabBtn{border-radius:999px;padding:10px 14px}.tabBtn.active{background:#123454;border-color:#62b8f2}.depCard{background:#0a1320;border:1px solid var(--line);border-radius:16px;padding:13px;cursor:pointer}.depCard:hover{border-color:#64f4ac}.explain{padding:10px 12px;border:1px solid var(--line);border-radius:14px;background:#08111c;color:var(--muted);font-size:13px}.copyOk{color:var(--green)}.empty{border:1px dashed var(--line);border-radius:16px;padding:20px;color:var(--muted);text-align:center}pre{white-space:pre-wrap;word-break:break-word;background:#050a12;border:1px solid var(--line);border-radius:14px;padding:12px;max-height:330px;overflow:auto}.toolbar input{min-width:240px}.livePulse{animation:pulse 1.5s ease-in-out infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}@media(max-width:1120px){.layout{grid-template-columns:1fr}.grid,.split{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}}
</style></head><body>
<div class="top"><div class="brand"><div class="mark"></div><div><h1>Runtime Observer</h1><div class="hint">Live command deck for Internal Assistant backend + frontend</div></div></div><div class="status"><span class="dot livePulse" id="liveDot"></span><span id="liveText" class="hint">live refresh every 10s</span><select id="refreshInterval" title="Refresh interval"><option value="1000">1s</option><option value="10000" selected>10s</option><option value="20000">20s</option><option value="60000">60s</option><option value="0">Manual</option></select><button class="primary" id="refreshBtn">Refresh now</button></div></div>
<div class="layout"><aside class="stack"><section class="panel"><div class="panelTitle"><h2>Entry points</h2><span class="pill">click route</span></div><div id="entrypoints" class="content stack"></div></section></aside><main class="main"><section class="panel"><div class="panelTitle"><h2>Applications</h2><span class="pill" id="appCount">0</span></div><div id="appTabs" class="content tabs"></div></section><section id="kpis" class="kpis"></section><section class="grid"><div class="panel"><div class="panelTitle"><h2>Route performance</h2><span class="pill">p95 latency</span></div><div id="routes" class="content stack"></div></div><div class="panel"><div class="panelTitle"><h2>Activity summary</h2><span class="pill">live</span></div><div id="mix" class="content stack"></div></div></section><section class="panel"><div class="panelTitle"><h2 id="routeTitle">Select an entry point to inspect request traces</h2><span class="pill" id="routeMeta">no route selected</span></div><div class="content split"><div><div class="small" style="margin-bottom:8px">Requests for selected route</div><div id="traceList" class="list"></div></div><div><div class="small" style="margin-bottom:8px">Logs related to selected route/request</div><div id="routeLogs" class="list"></div></div></div></section><section class="grid"><div class="panel"><div class="panelTitle"><h2>Errors</h2><span class="pill">click for context</span></div><div id="errors" class="content list"></div></div><div class="panel"><div class="panelTitle"><h2>Dependencies</h2><span class="pill">click for context</span></div><div class="content"><div class="explain">Dependencies are external work observed for the selected app: DB queries, HTTP calls, and LLM calls. Each card shows aggregate count + a recent sample payload so you can see who/what triggered it.</div></div><div id="deps" class="content stack"></div></div></section><section class="panel"><div class="panelTitle"><h2>Logs</h2><div class="toolbar"><button class="tabBtn active" data-logtab="all">All</button><button class="tabBtn" data-logtab="client">Client console</button><button class="tabBtn" data-logtab="backend">Backend</button><input id="logSearch" placeholder="Search log message"><select id="logWindow" title="How far back to show logs"><option value="5">last 5m</option><option value="15">last 15m</option><option value="60" selected>last 1h</option><option value="360">last 6h</option><option value="1440">last 24h</option><option value="0">all retained</option></select><select id="level"><option value="">all levels</option><option>ERROR</option><option>WARNING</option><option>INFO</option><option>DEBUG</option></select><button id="searchBtn">Search</button></div></div><div id="logs" class="content list"></div></section></main></div>
<div id="drawer" class="drawer"><div class="drawerTop"><div><h1 id="drawerTitle">Trace map</h1><div id="drawerSub" class="hint"></div></div><button id="closeBtn">Close</button></div><div id="drawerBody" class="drawerBody"></div></div>
<script>
let overview={apps:[],totals:{},routes:[],dependencies:[],recent_logs:[],recent_errors:[],event_kinds:[],log_levels:[]};let entries=[];let selectedApp='all';let selectedRouteId=null;let selectedTraceId=null;let routeState=null;let isRefreshing=false;let logTab='all';let refreshTimer=null;let refreshMs=10000;let logWindowMinutes=Number(localStorage.getItem('runtimeObserverLogWindowMinutes')||60);const copyCache=new Map();
const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const num=n=>Number(n||0).toLocaleString();async function api(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(await r.text());return r.json();}function visible(rows){return selectedApp==='all'?rows:rows.filter(r=>r.app_id===selectedApp||r.id===selectedApp)}function appName(a){return a?.display_name||a?.service_name||'unknown app'}function kpi(label,value){return `<div class="panel kpi"><div class="num">${num(value)}</div><div class="label">${label}</div></div>`}
function renderApps(){$('appCount').textContent=overview.apps.length;$('appTabs').innerHTML=`<button class="tabBtn ${selectedApp==='all'?'active':''}" data-app="all">Overview: all apps</button>`+overview.apps.map(a=>`<button class="tabBtn ${selectedApp===a.id?'active':''}" data-app="${esc(a.id)}">${esc(appName(a))}</button>`).join('');document.querySelectorAll('[data-app]').forEach(b=>b.onclick=()=>{selectedApp=b.dataset.app;selectedRouteId=null;selectedTraceId=null;routeState=null;render();});}
function renderEntries(){const rows=visible(entries);$('entrypoints').innerHTML=rows.length?rows.map(r=>`<button class="entry ${selectedRouteId===r.id?'active':''}" data-route="${esc(r.id)}"><div class="routeHeader"><b>${esc(r.method)} ${esc(r.route_pattern)}</b><span class="pill">${num(r.call_count)} calls</span></div><span class="small">${esc(r.service_name)} • ${num(r.log_count)} logs • ${num(r.trace_count)} traces</span></button>`).join(''):'<div class="empty">No routes yet. Exercise the app and telemetry will appear here.</div>';document.querySelectorAll('[data-route]').forEach(b=>b.onclick=()=>selectRoute(b.dataset.route));}
function renderBars(id,rows,label,value,danger=false){const max=Math.max(1,...rows.map(r=>Number(r[value]||0)));$(id).innerHTML=rows.length?rows.slice(0,12).map(r=>`<div class="bar"><span class="mono" title="${esc(r[label])}">${esc(r[label]).slice(0,30)}</span><div class="track"><div class="fill ${danger?'err':''}" style="width:${Math.max(4,Number(r[value]||0)/max*100)}%"></div></div><b>${num(r[value])}</b></div>`).join(''):'<div class="empty">No data yet</div>';}
function renderDependencies(rows){const max=Math.max(1,...rows.map(r=>Number(r.call_count||0)));$('deps').innerHTML=rows.length?rows.slice(0,12).map(r=>{const sample=r.last_sample||{};const p=sample.payload||{};const who=p.source_function||p.route_pattern||p.source_file||r.service_name||'unknown caller';const sql=p.rendered_statement||p.statement_template||p.statement_fingerprint||'';const payload=JSON.stringify(r);return `<div class="depCard" data-dep="${esc(payload)}"><div class="routeHeader"><b>${esc(r.display)}</b><span class="pill">${num(r.call_count)} calls</span></div><div class="bar"><span class="small">last seen by ${esc(who)}</span><div class="track"><div class="fill" style="width:${Math.max(4,Number(r.call_count||0)/max*100)}%"></div></div><b>${r.p95_duration_ms?Math.round(Number(r.p95_duration_ms))+'ms p95':''}</b></div><div class="small mono">${esc(sql || `${r.service_name||''} ${r.operation||''}`).slice(0,180)}</div>${sample.trace_id?`<div class="small">sample trace ${esc(sample.trace_id)}</div>`:''}${r.error_count?`<div class="small level-ERROR">${num(r.error_count)} errors</div>`:''}</div>`}).join(''):'<div class="empty">No dependency calls yet</div>';document.querySelectorAll('.depCard').forEach(el=>el.onclick=()=>openDependency(JSON.parse(el.dataset.dep)));}
function logCopyState(logId){return copyCache.get(`log:${logId}`)?.status||'missing';}function logCopyLabel(logId){const s=logCopyState(logId);if(s==='ready')return 'Copy for AI';if(s==='error')return 'Retry prepare';return 'Preparing...';}function renderLogs(target,rows){$(target).innerHTML=rows.length?rows.map(l=>{const state=logCopyState(l.id);return `<div class="log" data-log='${esc(JSON.stringify(l))}'><div class="logHeader"><span class="pill level-${esc(l.level)}">${esc(l.level||'LOG')}</span><span class="small">${esc(l.service_name)} • ${esc(l.timestamp)}</span></div><div>${esc(l.message)}</div><div class="routeHeader"><div class="small mono">${esc(l.logger_name||'')} ${l.trace_id?'• trace '+esc(l.trace_id):''}</div><button data-copy-log="${esc(l.id)}" ${state==='ready'||state==='error'?'':'disabled'}>${logCopyLabel(l.id)}</button></div></div>`}).join(''):'<div class="empty">No logs found</div>';document.querySelectorAll(`#${target} .log`).forEach(el=>el.onclick=()=>openLog(JSON.parse(el.dataset.log)));document.querySelectorAll(`#${target} [data-copy-log]`).forEach(btn=>{prepareLogCopyBackground(btn.dataset.copyLog);btn.onclick=async ev=>{ev.preventDefault();ev.stopPropagation();await copyLog(btn.dataset.copyLog,btn);};});}
const eventLabels={log_record:'Logs',db_query:'Database queries',http_client_call:'HTTP/API calls',route_discovered:'Entry points discovered',request_finished:'Requests completed',request_started:'Requests started',sdk_diagnostic:'SDK diagnostics',app_started:'App starts',span_started:'Spans/functions',span_finished:'Spans/functions',dependency_inventory:'Dependency inventory',exception_raised:'Exceptions'};function sumMix(rows,key){const scoped=visible(rows||[]);const grouped=new Map();scoped.forEach(r=>{const raw=r[key]||'unknown';const label=eventLabels[raw]||String(raw).replaceAll('_',' ');grouped.set(label,(grouped.get(label)||0)+Number(r.count||0));});return Array.from(grouped.entries()).map(([label,value])=>({label,value})).sort((a,b)=>b.value-a.value);}function renderMix(){const kinds=sumMix(overview.event_kinds,'kind').filter(r=>r.label!=='SDK diagnostics'||r.value>0);const levels=sumMix(overview.log_levels,'level');$('mix').innerHTML='<div class="small">Readable activity for selected app</div><div id="kindBars" class="stack"></div><div class="small" style="margin-top:8px">Logs by level</div><div id="levelBars" class="stack"></div>';renderBars('kindBars',kinds,'label','value');renderBars('levelBars',levels,'label','value',true);}
function renderErrors(){const rows=visible(overview.recent_errors||[]);$('errors').innerHTML=rows.length?rows.map(e=>`<button class="error" data-error="${esc(e.app_id)}|${esc(e.id)}"><div class="routeHeader"><b>${esc(e.type)}</b><span class="pill level-ERROR">${num(e.count)}x</span></div><div>${esc(e.normalized_message)}</div><span class="small">${esc(e.service_name)} • ${esc(e.last_seen)} • trace ${esc(e.sample_trace_id||'none')}</span></button>`).join(''):'<div class="empty">No captured errors.</div>';document.querySelectorAll('[data-error]').forEach(b=>b.onclick=()=>{const [app,id]=b.dataset.error.split('|');openError(app,id);});}
function selectedTraceLogs(){if(!selectedTraceId)return routeState.logs||[];const logs=routeState.logs||[];const exact=logs.filter(l=>l.trace_id===selectedTraceId);if(exact.length)return exact;const trace=(routeState.traces||[]).find(t=>t.id===selectedTraceId);if(!trace||!trace.finished_at)return [];const base=new Date(trace.finished_at).getTime();return logs.filter(l=>{const ts=new Date(l.timestamp||0).getTime();return l.route_id===trace.route_id&&Number.isFinite(ts)&&Math.abs(ts-base)<=15000;});}function renderTraceList(){if(!routeState){$('traceList').innerHTML='<div class="empty">Pick an entry point from the left.</div>';$('routeLogs').innerHTML='<div class="empty">Route/request logs appear here.</div>';return;}const traces=routeState.traces||[];$('traceList').innerHTML=traces.length?traces.map(t=>`<button class="traceItem ${selectedTraceId===t.id?'active':''}" data-trace="${esc(t.id)}"><div class="routeHeader"><b>${esc(t.status_code||'')} ${esc(t.method)} ${esc(t.route_pattern)}</b><span class="pill">${Math.round(Number(t.duration_ms||0))}ms</span></div><span class="small">${esc(t.service_name)} • ${esc(t.finished_at||t.started_at)} • ${num(t.log_count)} exact logs</span></button>`).join(''):'<div class="empty">No request traces for this route yet.</div>';document.querySelectorAll('[data-trace]').forEach(b=>b.onclick=()=>openTraceMap(b.dataset.trace));renderLogs('routeLogs',selectedTraceLogs());}
function logWindowQuery(){return `log_window_minutes=${encodeURIComponent(logWindowMinutes)}&log_limit=1000`;}function logWindowStartParam(){if(!logWindowMinutes)return '';return new Date(Date.now()-logWindowMinutes*60*1000).toISOString();}function syncLogWindowSelect(){const select=$('logWindow');if(select)select.value=String(logWindowMinutes);}function filterLogTab(rows){if(logTab==='client')return rows.filter(l=>(l.service_name||'').includes('frontend')||String(l.logger_name||'').startsWith('browser.'));if(logTab==='backend')return rows.filter(l=>(l.service_name||'').includes('backend'));return rows;}function dependencyLabel(dep){if(dep.dependency_type==='db')return `DB ${dep.target||'unknown'} ${dep.operation||''}`.trim().slice(0,120);if(dep.dependency_type==='http')return `HTTP ${dep.operation||''} ${dep.target||''}`.trim();if(dep.dependency_type==='package')return `pkg ${dep.target}`;return `${dep.dependency_type||'dep'} ${dep.target||''} ${dep.operation||''}`;}function render(){renderApps();renderEntries();const routes=visible(overview.routes||[]);const logs=filterLogTab(visible(overview.recent_logs||[]));const errors=visible(overview.recent_errors||[]);const deps=visible(overview.dependencies||[]).map(d=>({...d,display:dependencyLabel(d)}));const totalReq=selectedApp==='all'?overview.totals.request_count:routes.reduce((a,r)=>a+Number(r.call_count||0),0);$('kpis').innerHTML=kpi('Applications',selectedApp==='all'?overview.apps.length:1)+kpi('Requests',totalReq)+kpi('Errors',selectedApp==='all'?overview.totals.exception_count:errors.length)+kpi('Logs',selectedApp==='all'?overview.totals.log_count:logs.length)+kpi('Events',overview.totals.event_count);renderBars('routes',routes,'route_pattern','p95_ms');renderDependencies(deps);renderMix();renderErrors();renderLogs('logs',logs);document.querySelectorAll('[data-logtab]').forEach(b=>b.classList.toggle('active',b.dataset.logtab===logTab));renderTraceList();}
function refreshLabel(){return refreshMs===0?'manual refresh':`live refresh every ${refreshMs/1000}s`;}function setRefreshIntervalMs(ms){refreshMs=Number(ms);if(refreshTimer)clearInterval(refreshTimer);refreshTimer=null;$('liveDot').classList.toggle('livePulse',refreshMs!==0);$('liveText').textContent=refreshLabel();if(refreshMs>0)refreshTimer=setInterval(refresh,refreshMs);}async function refresh(){if(isRefreshing)return;isRefreshing=true;try{const [o,e]=await Promise.all([api(`/api/overview?${logWindowQuery()}`),api('/api/entrypoints')]);overview=o;entries=e;$('liveText').textContent=`${refreshLabel()} • logs ${logWindowMinutes?`last ${logWindowMinutes}m`:'all retained'} • updated ${new Date().toLocaleTimeString()}`;if(selectedRouteId)await loadRoute(selectedRouteId,false);render();syncLogWindowSelect();}catch(err){$('liveText').textContent='telemetry refresh failed';console.error(err);}finally{isRefreshing=false;}}
async function selectRoute(routeId){selectedRouteId=routeId;selectedTraceId=null;await loadRoute(routeId,true);render();}async function loadRoute(routeId,openFirst){routeState=await api(`/api/routes/${encodeURIComponent(routeId)}/requests`);const r=routeState.route;$('routeTitle').textContent=`${r.method} ${r.route_pattern}`;$('routeMeta').textContent=`${r.service_name} • ${num(r.call_count)} calls • p95 ${Math.round(Number(r.p95_ms||0))}ms`;if(openFirst&&routeState.traces?.length)selectedTraceId=routeState.traces[0].id;}
function closeDrawer(){$('drawer').classList.remove('open')}function copyTrace(traceId,btn=null){copyPrepared(`trace:${traceId}`,'✓ Copied full trace context for AI agent',btn,'Copy full trace for AI');}function showCopyStatus(message,isError=false){let el=$('copyStatus');if(!el){el=document.createElement('span');el.id='copyStatus';el.className='copyOk small';$('drawerBody')?.prepend(el);}el.textContent=message;el.style.display='inline-flex';el.style.marginLeft='8px';el.classList.toggle('level-ERROR',isError);el.classList.toggle('copyOk',!isError);if(!isError&&message.startsWith('✓'))setTimeout(()=>{el.textContent='';},3500);}function setCopyButton(btn,text,disabled=false){if(!btn)return;btn.textContent=text;btn.disabled=disabled;btn.style.opacity=disabled?'.7':'1';}function preparedTextarea(){let area=$('preparedCopyText');if(!area){area=document.createElement('textarea');area.id='preparedCopyText';area.setAttribute('aria-hidden','true');area.style.position='fixed';area.style.left='0';area.style.top='0';area.style.width='1px';area.style.height='1px';area.style.opacity='0.01';area.style.zIndex='-1';document.body.appendChild(area);}return area;}function writeClipboardTextNow(text){const area=preparedTextarea();area.value=text;area.focus();area.select();area.setSelectionRange(0,area.value.length);const ok=document.execCommand('copy');if(!ok)throw new Error('copy command failed');}function showManualCopy(text){$('drawerTitle').textContent='Manual copy';$('drawerSub').textContent='Automatic clipboard copy was blocked by the browser';let body=$('drawerBody');body.innerHTML='<div class="tabs"><span id="copyStatus" class="level-ERROR small">Browser blocked automatic copy. The full AI context is selected below. Press Cmd/Ctrl+C.</span></div><div class="explain">This is the same content the copy button tried to put on your clipboard.</div><textarea id="manualCopyText" style="width:100%;min-height:70vh;background:#050a12;color:var(--text);border:1px solid var(--line);border-radius:14px;padding:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace"></textarea>';$('drawer').classList.add('open');const area=$('manualCopyText');area.value=text;area.focus();area.select();area.setSelectionRange(0,area.value.length);}function updateLogCopyButtons(logId){document.querySelectorAll(`[data-copy-log="${CSS.escape(logId)}"]`).forEach(btn=>{const state=logCopyState(logId);btn.disabled=state!=='ready'&&state!=='error';btn.textContent=logCopyLabel(logId);});}function prepareLogCopyBackground(logId){const key=`log:${logId}`;if(copyCache.has(key))return;copyCache.set(key,{status:'loading',text:''});api(`/api/logs/${encodeURIComponent(logId)}/agent-context`).then(data=>{copyCache.set(key,{status:'ready',text:data.text});updateLogCopyButtons(logId);}).catch(err=>{console.error(err);copyCache.set(key,{status:'error',text:''});updateLogCopyButtons(logId);});}function prepareCopy(key,path,readyText='Ready to copy'){copyCache.set(key,{status:'loading',text:''});api(path).then(data=>{copyCache.set(key,{status:'ready',text:data.text});preparedTextarea().value=data.text;showCopyStatus(readyText);}).catch(err=>{console.error(err);copyCache.set(key,{status:'error',text:''});showCopyStatus('Failed to prepare copy context',true);});}function copyPrepared(key,successMessage,btn,resetText){const item=copyCache.get(key);if(!item){showCopyStatus('Preparing copy context. Click again when ready.',true);setCopyButton(btn,'Preparing...',true);setTimeout(()=>setCopyButton(btn,resetText,false),900);return;}if(item.status==='loading'){showCopyStatus('Still preparing copy context — try again in a second',true);setCopyButton(btn,'Preparing...',true);setTimeout(()=>setCopyButton(btn,resetText,false),900);return;}if(item.status==='error'){showCopyStatus('Copy context failed to prepare',true);setCopyButton(btn,'Copy failed',false);return;}try{writeClipboardTextNow(item.text);showCopyStatus(successMessage);setCopyButton(btn,'✓ Copied',false);setTimeout(()=>setCopyButton(btn,resetText,false),2500);}catch(err){showManualCopy(item.text);setCopyButton(btn,'Manual copy opened',false);}}async function copyLog(logId,btn=null){const key=`log:${logId}`;const existing=copyCache.get(key);if(!existing||existing.status==='loading'){prepareLogCopyBackground(logId);setCopyButton(btn,'Preparing...',true);showCopyStatus('Still preparing log context. The button will enable automatically.',true);return;}if(existing.status==='error'){copyCache.delete(key);prepareLogCopyBackground(logId);setCopyButton(btn,'Preparing...',true);showCopyStatus('Retrying log context preparation...',true);return;}copyPrepared(key,'✓ Copied log context for AI agent',btn,'Copy for AI');}function copyDependency(depId,btn=null){copyPrepared(`dep:${depId}`,'✓ Copied dependency errors/context for AI agent',btn,'Copy dependency errors for AI');}async function openDependency(dep){const data=await api(`/api/dependencies/${encodeURIComponent(dep.id)}/context`);const sample=dep.last_sample||{};const errorRows=(data.error_samples||[]).map(e=>`<div class="log"><div class="logHeader"><span class="pill level-ERROR">ERROR</span><span class="small">${esc(e.timestamp)} ${e.trace_id?'• trace '+esc(e.trace_id):'• no trace'}</span></div><div class="mono">${esc(e.payload?.error_type||e.payload?.error||'dependency error')}</div><div>${esc(e.payload?.error_message||'')}</div><pre>${esc(JSON.stringify(e.payload,null,2))}</pre>${e.trace_id?`<button onclick="openTraceMap('${esc(e.trace_id)}')">Open trace</button>`:''}</div>`).join('');const related=(data.related_logs||[]).map(l=>`<div class="log"><div class="logHeader"><span class="pill level-${esc(l.level)}">${esc(l.level||'LOG')}</span><span class="small">${esc(l.service_name)} • ${esc(l.timestamp)}</span></div><div>${esc(l.message)}</div><div class="small mono">${esc(l.logger_name||'')}</div></div>`).join('');$('drawerTitle').textContent='Dependency context';$('drawerSub').textContent=`${dep.service_name} • ${dep.call_count} calls • ${dep.error_count||0} errors`;$('drawerBody').innerHTML=`<div class="explain">This is an aggregate dependency. The error samples below are the actual failed events that produced the error count. If a background task has no trace, use the related logs around the failure timestamp.</div><div class="tabs"><button class="primary" data-copy-dep="${esc(dep.id)}" style="pointer-events:auto;cursor:pointer">Copy dependency errors for AI</button><span id="copyStatus" class="copyOk small" style="min-width:220px">Preparing copy context...</span>${sample.trace_id?`<button data-open-trace="${esc(sample.trace_id)}">Open latest sample trace</button>`:''}</div><h2>Error samples</h2><div class="list">${errorRows||'<div class="empty">No individual error payloads retained for this dependency yet.</div>'}</div><h2>Related logs around error samples</h2><div class="list">${related||'<div class="empty">No nearby logs found.</div>'}</div><h2>Aggregate + latest sample</h2><pre>${esc(JSON.stringify(data,null,2))}</pre>`;$('drawer').classList.add('open');prepareCopy(`dep:${dep.id}`,`/api/dependencies/${encodeURIComponent(dep.id)}/agent-context`,'Ready to copy dependency context');}async function openLog(log){if(log.trace_id){await openTraceMap(log.trace_id);return;}$('drawerTitle').textContent='Log record';$('drawerSub').textContent=`${log.service_name} • ${log.timestamp}`;$('drawerBody').innerHTML=`<div class="tabs"><button class="primary" data-copy-log="${esc(log.id)}">Copy log context for AI</button><span id="copyStatus" class="copyOk small">Preparing copy context...</span></div><div class="empty">This log has no trace id, so only the record and nearby logs are available.</div><pre>${esc(JSON.stringify(log,null,2))}</pre>`;$('drawer').classList.add('open');prepareCopy(`log:${log.id}`,`/api/logs/${encodeURIComponent(log.id)}/agent-context`,'Ready to copy log context');}
function eventPayload(item){try{return JSON.parse(item.payload_json||'{}')}catch{return {}}}function renderMap(data){const traces=data.traces||[],deps=data.dependencies||[],exceptions=data.exceptions||[],logs=data.logs||[],spans=data.spans||[];const nodes=[];traces.forEach(t=>nodes.push(`<div class="nodeRow"><div class="node route"><b>HTTP route</b><div>${esc(t.service_name)}</div><div class="mono">${esc(t.method)} ${esc(t.route_pattern)}</div><div class="small">${Math.round(Number(t.duration_ms||0))}ms • status ${esc(t.status_code||'')}</div></div></div>`));spans.filter(s=>s.kind==='function').slice(0,12).forEach(s=>nodes.push(`<div class="nodeRow"><div class="arrow"></div><div class="node"><b>Function</b><div class="mono">${esc(s.name||'handler')}</div><div class="small">${Math.round(Number(s.duration_ms||0))}ms • ${esc(s.status||'')}</div></div></div>`));logs.slice(0,12).forEach(l=>nodes.push(`<div class="nodeRow"><div class="arrow"></div><div class="node"><b>${esc(l.source_function||l.logger_name||'log')}</b><div>${esc(l.message).slice(0,140)}</div><div class="small">${esc(l.service_name)} • ${esc(l.level||'LOG')}</div></div></div>`));deps.slice(0,20).forEach(d=>{const p=eventPayload(d);const tables=Array.isArray(p.tables)?p.tables.join(', '):'';const target=p.target||p.host||p.database||p.model||tables||'dependency';const operation=p.rendered_statement||p.statement_template||p.statement_fingerprint||p.operation||p.method||p.provider||'';const title=d.kind==='db_query'?'Database query':d.kind==='http_client_call'?'HTTP client call':'Dependency call';nodes.push(`<div class="nodeRow"><div class="arrow"></div><div class="node dep"><b>${title}</b><div>${esc(target)}</div><div class="small mono">${esc(operation).slice(0,360)}</div><div class="small">${p.duration_ms?Math.round(Number(p.duration_ms))+'ms':''}${p.row_count!=null?' • rows '+esc(p.row_count):''}${p.status_code?' • status '+esc(p.status_code):''}</div></div></div>`)});exceptions.forEach(e=>nodes.push(`<div class="nodeRow"><div class="arrow"></div><div class="node errorNode"><b>${esc(e.type)}</b><div>${esc(e.normalized_message)}</div></div></div>`));return `<div class="mapCanvas">${nodes.length?nodes.join(''):'<div class="empty">No map nodes for this trace yet.</div>'}</div>`;}
async function openTraceMap(traceId){selectedTraceId=traceId;renderTraceList();copyCache.delete(`trace:${traceId}`);const data=await api(`/api/traces/${encodeURIComponent(traceId)}/map`);const flowLogs=data.flow_logs||data.logs||[];const backgroundLogs=data.nearby_background_logs||[];$('drawerTitle').textContent='Triggered map';$('drawerSub').textContent=`trace ${traceId} • ${flowLogs.length} exact logs • ${data.events.length} events • ${data.dependencies.length} dependency calls • ${backgroundLogs.length} nearby background logs hidden`;const logsHtml=flowLogs.map(l=>`<div class="log"><div class="logHeader"><span class="pill level-${esc(l.level)}">${esc(l.level||'LOG')}</span><span class="small">${esc(l.service_name)} • ${esc(l.timestamp)} • exact trace</span></div><div>${esc(l.message)}</div><div class="small mono">${esc(l.logger_name||'')} ${l.source_function?'• '+esc(l.source_function):''}</div></div>`).join('')||'<div class="empty">No logs directly correlated to this trace. Nearby background logs are intentionally separated below.</div>';const backgroundHtml=backgroundLogs.slice(0,80).map(l=>`<div class="log"><div class="logHeader"><span class="pill level-${esc(l.level)}">${esc(l.level||'LOG')}</span><span class="small">${esc(l.service_name)} • ${esc(l.timestamp)} • ${l.trace_id?'other trace':'background/no trace'}</span></div><div>${esc(l.message)}</div><div class="small mono">${esc(l.logger_name||'')} ${l.source_function?'• '+esc(l.source_function):''}</div></div>`).join('');const depRows=(data.dependencies||[]).map(d=>{const p=eventPayload(d);return `<tr><td>${esc(d.kind)}</td><td>${esc(p.target||p.host||(Array.isArray(p.tables)?p.tables.join(', '):''))}</td><td class="mono">${esc(p.rendered_statement||p.statement_template||p.statement_fingerprint||p.operation||p.method||p.request_body_preview||'').slice(0,420)}${p.parameters?`<div class="small mono">params: ${esc(String(p.parameters)).slice(0,240)}</div>`:''}</td><td>${p.duration_ms?Math.round(Number(p.duration_ms)):''}</td></tr>`}).join('');$('drawerBody').innerHTML=`<div class="tabs"><button class="primary" data-copy-trace="${esc(traceId)}">Copy full trace for AI</button><span id="copyStatus" class="copyOk small">Preparing copy context...</span><span class="pill">${data.traces.length} route</span><span class="pill">${data.spans.length} spans/functions</span><span class="pill">${data.dependencies.length} dependency calls</span><span class="pill">${flowLogs.length} exact logs</span><span class="pill">${backgroundLogs.length} nearby background hidden</span><span class="pill">${data.exceptions.length} errors</span></div><div class="explain">Only exact trace-id events are shown in the causal flow. Cron jobs, SQS pollers, Telegram polling, and lock heartbeats run independently with no trace id, so they are separated as nearby background activity instead of being mixed into this request.</div>${renderMap({...data,logs:flowLogs})}<h2>Dependency details + inputs</h2><pre>${depRows?'<table><thead><tr><th>kind</th><th>target</th><th>operation/input</th><th>ms</th></tr></thead><tbody>'+depRows+'</tbody></table>':'No dependency calls captured for this request.'}</pre><h2>Exact flow logs</h2><div class="list">${logsHtml}</div><h2>Raw causal timeline</h2><pre>${esc(JSON.stringify((data.timeline||data.events).slice(0,160),null,2))}</pre><details><summary>Nearby background activity, not part of this trace (${backgroundLogs.length})</summary><div class="explain">These logs happened around the same time but have no matching trace_id. Use this only for environmental noise or scheduler investigations.</div><div class="list">${backgroundHtml||'<div class="empty">No nearby background logs.</div>'}</div></details>`;$('drawer').classList.add('open');prepareCopy(`trace:${traceId}`,`/api/traces/${encodeURIComponent(traceId)}/agent-context`,'Ready to copy trace context');}
async function openError(appId,id){const data=await api(`/api/apps/${encodeURIComponent(appId)}/exceptions/${encodeURIComponent(id)}`);if(data.exception?.sample_trace_id){await openTraceMap(data.exception.sample_trace_id);return;}$('drawerTitle').textContent='Error';$('drawerSub').textContent=data.exception?.last_seen||'';$('drawerBody').innerHTML=`<pre>${esc(JSON.stringify(data,null,2))}</pre>`;$('drawer').classList.add('open');}
async function searchLogs(){const q=encodeURIComponent($('logSearch').value);const level=encodeURIComponent($('level').value);const start=encodeURIComponent(logWindowStartParam());const rows=await api(`/api/logs?text=${q}&level=${level}&start=${start}&limit=1000`);renderLogs('logs',selectedApp==='all'?rows:rows.filter(r=>r.app_id===selectedApp));}
$('refreshBtn').onclick=refresh;$('refreshInterval').onchange=e=>setRefreshIntervalMs(e.target.value);$('logWindow').onchange=e=>{logWindowMinutes=Number(e.target.value);localStorage.setItem('runtimeObserverLogWindowMinutes',String(logWindowMinutes));refresh();};syncLogWindowSelect();$('searchBtn').onclick=searchLogs;$('closeBtn').onclick=closeDrawer;document.querySelectorAll('[data-logtab]').forEach(b=>b.onclick=()=>{logTab=b.dataset.logtab;render();});document.addEventListener('click',ev=>{const depBtn=ev.target.closest('[data-copy-dep]');if(depBtn){ev.preventDefault();ev.stopPropagation();copyDependency(depBtn.dataset.copyDep,depBtn);return;}const traceBtn=ev.target.closest('[data-copy-trace]');if(traceBtn){ev.preventDefault();ev.stopPropagation();copyTrace(traceBtn.dataset.copyTrace,traceBtn);return;}const logBtn=ev.target.closest('[data-copy-log]');if(logBtn){ev.preventDefault();ev.stopPropagation();copyLog(logBtn.dataset.copyLog,logBtn);return;}const openTraceBtn=ev.target.closest('[data-open-trace]');if(openTraceBtn){ev.preventDefault();ev.stopPropagation();openTraceMap(openTraceBtn.dataset.openTrace);}});setRefreshIntervalMs($('refreshInterval').value);refresh();
</script></body></html>
'''
