"""Project-scoped read API for autonomous agents.

The endpoints under `/v1/agent/*` are designed for programmatic consumption
by agents that hold a Runtime Observer project API key. Every endpoint is
scoped to the project the key belongs to. The legacy collector-wide admin
key is rejected here on purpose — agents should always be project-scoped.
"""
from __future__ import annotations

import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .api import (
    _api_key_hash,
    _compact_trace_rows,
    _dependency_key_from_event,
    build_dependency_groups,
    build_duplicate_candidates,
    build_relationship_loader_groups,
    build_slow_gap_markers,
    get_db,
    get_settings,
    iso,
    json_text,
    log_window_start,
    logs_around,
    time_bucket,
)
from .config import Settings
from .db import Database
from .store import row_to_dict, rows_to_dicts


def _resolve_project(request: Request, db: Database, settings: Settings) -> str:
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing 'Authorization: Bearer <project-api-key>' header",
        )
    if settings.api_key and hmac.compare_digest(token, settings.api_key):
        raise HTTPException(
            status_code=401,
            detail=(
                "The collector-wide admin key cannot be used with the agent API. "
                "Generate a project API key in the dashboard and use that token instead."
            ),
        )
    key_hash = _api_key_hash(token)
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


def require_project(
    request: Request,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> str:
    return _resolve_project(request, db, settings)


def _app_ids_for_project(conn, project_name: str, app_id: str | None = None) -> list[str]:
    where = "project_name=?"
    params: list[Any] = [project_name]
    if app_id:
        where += " AND id=?"
        params.append(app_id)
    rows = conn.execute(f"SELECT id FROM apps WHERE {where}", params).fetchall()
    return [str(row["id"]) for row in rows]


def _placeholders(values: list[Any]) -> str:
    return ",".join("?" for _ in values)


def _assemble_trace(conn, project_name: str, trace_id: str, *, slim: bool = False) -> dict[str, Any]:
    app_ids = _app_ids_for_project(conn, project_name)
    if not app_ids:
        raise HTTPException(status_code=404, detail="trace not found")
    ph = _placeholders(app_ids)
    traces = rows_to_dicts(
        conn.execute(
            f"""
            SELECT traces.*, routes.method, routes.route_pattern, apps.service_name
            FROM traces
            LEFT JOIN routes ON routes.id=traces.route_id AND routes.app_id=traces.app_id
            JOIN apps ON apps.id=traces.app_id
            WHERE traces.id=? AND traces.app_id IN ({ph})
            ORDER BY traces.started_at
            """,
            [trace_id, *app_ids],
        ).fetchall()
    )
    if not traces:
        raise HTTPException(status_code=404, detail="trace not found")
    events = rows_to_dicts(
        conn.execute(
            f"""
            SELECT events.id, events.app_id, events.trace_id, events.span_id,
              events.parent_span_id, events.kind, events.timestamp,
              events.payload_json, apps.service_name
            FROM events JOIN apps ON apps.id=events.app_id
            WHERE events.trace_id=? AND events.app_id IN ({ph})
            ORDER BY events.timestamp
            """,
            [trace_id, *app_ids],
        ).fetchall()
    )
    spans = rows_to_dicts(
        conn.execute(
            f"""
            SELECT spans.*, apps.service_name FROM spans
            JOIN apps ON apps.id=spans.app_id
            WHERE spans.trace_id=? AND spans.app_id IN ({ph})
            ORDER BY spans.started_at
            """,
            [trace_id, *app_ids],
        ).fetchall()
    )
    logs = rows_to_dicts(
        conn.execute(
            f"""
            SELECT logs.*, apps.service_name FROM logs
            JOIN apps ON apps.id=logs.app_id
            WHERE logs.trace_id=? AND logs.app_id IN ({ph})
            ORDER BY logs.timestamp
            """,
            [trace_id, *app_ids],
        ).fetchall()
    )
    exceptions = rows_to_dicts(
        conn.execute(
            f"""
            SELECT exceptions.*, apps.service_name FROM exceptions
            JOIN apps ON apps.id=exceptions.app_id
            WHERE exceptions.sample_trace_id=? AND exceptions.app_id IN ({ph})
            ORDER BY exceptions.last_seen DESC
            """,
            [trace_id, *app_ids],
        ).fetchall()
    )
    dependencies = [event for event in events if event.get("kind") in {"http_client_call", "db_query", "llm_call"}]
    last_ts = traces[-1].get("finished_at") if traces else (events[-1].get("timestamp") if events else None)
    timeline = sorted(
        [
            *events,
            *[
                {**span, "kind": "span", "timestamp": span.get("started_at") or span.get("finished_at")}
                for span in spans
            ],
            *[{**log, "kind": "log_record", "timestamp": log.get("timestamp")} for log in logs],
        ],
        key=lambda item: item.get("timestamp") or "",
    )
    compact_events = _compact_trace_rows(events)
    compact_deps = [event for event in compact_events if event.get("kind") in {"http_client_call", "db_query", "llm_call"}]
    compact_timeline = _compact_trace_rows(timeline)
    payload = {
        "trace_id": trace_id,
        "trace": traces[0] if traces else None,
        "traces": traces,
        "event_count": len(events),
        "spans": spans,
        "logs": logs,
        "exceptions": exceptions,
    }
    if slim:
        payload.update({"events": [], "dependencies": [], "timeline": []})
        return payload
    payload.update(
        {
            "events": compact_events,
            "dependencies": compact_deps,
            "timeline": compact_timeline,
            "dependency_groups": build_dependency_groups(dependencies),
            "relationship_loader_groups": build_relationship_loader_groups(dependencies),
            "duplicate_candidates": build_duplicate_candidates(dependencies),
            "slow_gap_markers": build_slow_gap_markers(timeline, traces),
            "nearby_logs": logs_around(conn, last_ts, trace_id=trace_id, window_seconds=180, limit=200),
        }
    )
    return payload


def _trace_to_markdown(trace_id: str, data: dict[str, Any]) -> str:
    lines = ["# Runtime Observer Trace Context", "", f"Trace ID: `{trace_id}`", ""]
    for trace in data.get("traces", []):
        lines.extend(
            [
                "## Request",
                f"- App: {trace.get('service_name')}",
                f"- Route: {trace.get('method') or 'n/a'} {trace.get('route_pattern') or 'n/a'}",
                f"- Status: {trace.get('status_code')}",
                f"- Duration ms: {trace.get('duration_ms')}",
                f"- Started at: {trace.get('started_at')}",
                f"- Finished at: {trace.get('finished_at')}",
                "",
            ]
        )
    if data.get("spans"):
        lines.append("## Spans / Functions")
        for span in data["spans"]:
            lines.append(
                f"- {span.get('kind')}: {span.get('name')} "
                f"({span.get('duration_ms')}ms, status={span.get('status')})"
            )
        lines.append("")
    if data.get("dependencies"):
        lines.append("## Dependencies (DB / HTTP / LLM)")
        for event in data["dependencies"]:
            lines.append(f"### {event.get('kind')} at {event.get('timestamp')}")
            lines.append("```json")
            lines.append(event.get("payload_json") or "{}")
            lines.append("```")
    if data.get("logs"):
        lines.extend(["", "## Logs (same trace)"])
        for log in data["logs"]:
            lines.append(
                f"[{log.get('timestamp')}] {log.get('service_name')} "
                f"{log.get('level')} {log.get('logger_name')}: {log.get('message')}"
            )
            exc_json = log.get("exception_json")
            if exc_json and exc_json != "{}":
                lines.extend(["```json", exc_json, "```"])
    if data.get("exceptions"):
        lines.extend(["", "## Exceptions"])
        for exc in data["exceptions"]:
            lines.extend(["```json", json.dumps(exc, indent=2), "```"])
    return "\n".join(lines)


def create_agent_router() -> APIRouter:
    router = APIRouter(prefix="/v1/agent", tags=["agent"])

    @router.get("/info")
    def info(
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        with db.connect() as conn:
            apps = rows_to_dicts(
                conn.execute(
                    "SELECT id, service_name, display_name, language, sdk_version, first_seen, last_seen "
                    "FROM apps WHERE project_name=? ORDER BY last_seen DESC",
                    (project_name,),
                ).fetchall()
            )
        return {
            "project_name": project_name,
            "apps": apps,
            "server_time": iso(datetime.now(UTC)),
        }

    @router.get("/apps")
    def apps(
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    "SELECT * FROM apps WHERE project_name=? ORDER BY last_seen DESC",
                    (project_name,),
                ).fetchall()
            )

    @router.get("/overview")
    def overview(
        log_window_minutes: int = Query(60, ge=1, le=43200),
        log_limit: int = Query(100, ge=1, le=1000),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        log_start = log_window_start(log_window_minutes)
        log_time_clause = "AND logs.timestamp >= ?" if log_start else ""
        log_time_params: list[Any] = [log_start] if log_start else []
        with db.connect() as conn:
            apps_rows = rows_to_dicts(
                conn.execute(
                    "SELECT * FROM apps WHERE project_name=? ORDER BY last_seen DESC",
                    (project_name,),
                ).fetchall()
            )
            totals = row_to_dict(
                conn.execute(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM events JOIN apps ON apps.id=events.app_id WHERE apps.project_name=?) event_count,
                      (SELECT COUNT(*) FROM logs JOIN apps ON apps.id=logs.app_id WHERE apps.project_name=?) log_count,
                      (SELECT COUNT(*) FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE apps.project_name=?) exception_cluster_count,
                      (SELECT COALESCE(SUM(call_count),0) FROM routes JOIN apps ON apps.id=routes.app_id WHERE apps.project_name=?) request_count,
                      (SELECT COALESCE(SUM(error_count),0) FROM routes JOIN apps ON apps.id=routes.app_id WHERE apps.project_name=?) request_error_count
                    """,
                    (project_name, project_name, project_name, project_name, project_name),
                ).fetchone()
            )
            recent_errors = rows_to_dicts(
                conn.execute(
                    """
                    SELECT exceptions.*, apps.service_name
                    FROM exceptions JOIN apps ON apps.id=exceptions.app_id
                    WHERE apps.project_name=?
                    ORDER BY exceptions.last_seen DESC LIMIT 20
                    """,
                    (project_name,),
                ).fetchall()
            )
            recent_logs = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT logs.*, apps.service_name
                    FROM logs JOIN apps ON apps.id=logs.app_id
                    WHERE apps.project_name=? {log_time_clause}
                    ORDER BY logs.timestamp DESC LIMIT ?
                    """,
                    (project_name, *log_time_params, log_limit),
                ).fetchall()
            )
            slow_routes = rows_to_dicts(
                conn.execute(
                    """
                    SELECT routes.*, apps.service_name
                    FROM routes JOIN apps ON apps.id=routes.app_id
                    WHERE apps.project_name=?
                    ORDER BY routes.p95_ms DESC LIMIT 10
                    """,
                    (project_name,),
                ).fetchall()
            )
            failing_routes = rows_to_dicts(
                conn.execute(
                    """
                    SELECT routes.*, apps.service_name
                    FROM routes JOIN apps ON apps.id=routes.app_id
                    WHERE apps.project_name=? AND routes.error_count > 0
                    ORDER BY routes.error_count DESC LIMIT 10
                    """,
                    (project_name,),
                ).fetchall()
            )
        return {
            "project_name": project_name,
            "apps": apps_rows,
            "totals": totals,
            "recent_errors": recent_errors,
            "recent_logs": recent_logs,
            "top_slow_routes": slow_routes,
            "top_failing_routes": failing_routes,
            "log_window": {"minutes": log_window_minutes, "start": log_start, "limit": log_limit},
        }

    @router.get("/routes")
    def routes(
        app_id: str | None = None,
        with_errors_only: bool = False,
        limit: int = Query(100, ge=1, le=500),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        where = ["apps.project_name=?"]
        params: list[Any] = [project_name]
        if app_id:
            where.append("routes.app_id=?")
            params.append(app_id)
        if with_errors_only:
            where.append("routes.error_count > 0")
        params.append(limit)
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT routes.*, apps.service_name
                    FROM routes JOIN apps ON apps.id=routes.app_id
                    WHERE {' AND '.join(where)}
                    ORDER BY routes.last_seen DESC, routes.p95_ms DESC LIMIT ?
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/traces")
    def traces(
        app_id: str | None = None,
        route_id: str | None = None,
        has_error: bool | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = Query(50, ge=1, le=500),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        where = ["apps.project_name=?"]
        params: list[Any] = [project_name]
        if app_id:
            where.append("traces.app_id=?")
            params.append(app_id)
        if route_id:
            where.append("traces.route_id=?")
            params.append(route_id)
        if has_error is not None:
            where.append("traces.has_error=?")
            params.append(1 if has_error else 0)
        if start:
            where.append("COALESCE(traces.finished_at, traces.started_at) >= ?")
            params.append(start)
        if end:
            where.append("COALESCE(traces.finished_at, traces.started_at) <= ?")
            params.append(end)
        params.append(limit)
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT traces.*, routes.method, routes.route_pattern, apps.service_name
                    FROM traces
                    LEFT JOIN routes ON routes.id=traces.route_id AND routes.app_id=traces.app_id
                    JOIN apps ON apps.id=traces.app_id
                    WHERE {' AND '.join(where)}
                    ORDER BY COALESCE(traces.finished_at, traces.started_at) DESC LIMIT ?
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/traces/{trace_id}")
    def trace(
        trace_id: str,
        slim: bool = False,
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        with db.connect() as conn:
            return _assemble_trace(conn, project_name, trace_id, slim=slim)

    @router.get("/traces/{trace_id}/context")
    def trace_context(
        trace_id: str,
        format: str = Query("markdown", pattern="^(markdown|json)$"),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        with db.connect() as conn:
            data = _assemble_trace(conn, project_name, trace_id)
        if format == "json":
            return data
        return {"trace_id": trace_id, "text": _trace_to_markdown(trace_id, data)}

    @router.get("/logs")
    def logs(
        app_id: str | None = None,
        trace_id: str | None = None,
        route_id: str | None = None,
        level: str | None = None,
        logger: str | None = None,
        text: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        where = ["apps.project_name=?"]
        params: list[Any] = [project_name]
        for column, value in [
            ("app_id", app_id),
            ("trace_id", trace_id),
            ("route_id", route_id),
            ("level", level.upper() if level else None),
            ("logger_name", logger),
        ]:
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
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT logs.*, apps.service_name
                    FROM logs JOIN apps ON apps.id=logs.app_id
                    WHERE {' AND '.join(where)}
                    ORDER BY logs.timestamp DESC LIMIT ?
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/logs/{log_id}")
    def log_detail(
        log_id: str,
        window_seconds: int = Query(60, ge=1, le=3600),
        nearby_limit: int = Query(50, ge=0, le=500),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        with db.connect() as conn:
            log = row_to_dict(
                conn.execute(
                    """
                    SELECT logs.*, apps.service_name
                    FROM logs JOIN apps ON apps.id=logs.app_id
                    WHERE logs.id=? AND apps.project_name=?
                    """,
                    (log_id, project_name),
                ).fetchone()
            )
            if not log:
                raise HTTPException(status_code=404, detail="log not found")
            nearby: list[dict[str, Any]] = []
            if nearby_limit > 0:
                nearby_all = logs_around(
                    conn,
                    log.get("timestamp"),
                    trace_id=log.get("trace_id"),
                    window_seconds=window_seconds,
                    limit=nearby_limit * 4,
                )
                project_apps = {row["id"] for row in conn.execute("SELECT id FROM apps WHERE project_name=?", (project_name,)).fetchall()}
                nearby = [item for item in nearby_all if item.get("app_id") in project_apps][:nearby_limit]
            trace_payload: dict[str, Any] | None = None
            if log.get("trace_id"):
                try:
                    trace_payload = _assemble_trace(conn, project_name, str(log["trace_id"]), slim=True)
                except HTTPException:
                    trace_payload = None
            return {"log": log, "nearby_logs": nearby, "trace": trace_payload}

    @router.get("/exceptions")
    def exceptions(
        app_id: str | None = None,
        type: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        where = ["apps.project_name=?"]
        params: list[Any] = [project_name]
        if app_id:
            where.append("exceptions.app_id=?")
            params.append(app_id)
        if type:
            where.append("exceptions.type=?")
            params.append(type)
        params.append(limit)
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT exceptions.*, apps.service_name, routes.method, routes.route_pattern
                    FROM exceptions
                    JOIN apps ON apps.id=exceptions.app_id
                    LEFT JOIN traces ON traces.id=exceptions.sample_trace_id AND traces.app_id=exceptions.app_id
                    LEFT JOIN routes ON routes.id=traces.route_id AND routes.app_id=traces.app_id
                    WHERE {' AND '.join(where)}
                    ORDER BY exceptions.count DESC, exceptions.last_seen DESC LIMIT ?
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/exceptions/{exception_id}")
    def exception_detail(
        exception_id: str,
        include_trace: bool = True,
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        with db.connect() as conn:
            exc = row_to_dict(
                conn.execute(
                    """
                    SELECT exceptions.*, apps.service_name
                    FROM exceptions JOIN apps ON apps.id=exceptions.app_id
                    WHERE exceptions.id=? AND apps.project_name=?
                    """,
                    (exception_id, project_name),
                ).fetchone()
            )
            if not exc:
                raise HTTPException(status_code=404, detail="exception not found")
            trace_payload: dict[str, Any] | None = None
            same_trace_logs: list[dict[str, Any]] = []
            sample_trace_id = exc.get("sample_trace_id")
            if sample_trace_id and include_trace:
                try:
                    trace_payload = _assemble_trace(conn, project_name, str(sample_trace_id))
                except HTTPException:
                    trace_payload = None
                same_trace_logs = rows_to_dicts(
                    conn.execute(
                        """
                        SELECT logs.*, apps.service_name FROM logs
                        JOIN apps ON apps.id=logs.app_id
                        WHERE logs.trace_id=? AND apps.project_name=?
                        ORDER BY logs.timestamp
                        """,
                        (sample_trace_id, project_name),
                    ).fetchall()
                )
            return {"exception": exc, "trace": trace_payload, "correlated_logs": same_trace_logs}

    @router.get("/errors/summary")
    def errors_summary(
        app_id: str | None = None,
        window_minutes: int = Query(60, ge=1, le=43200),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        start = log_window_start(window_minutes)
        where_app = ["apps.project_name=?"]
        params_app: list[Any] = [project_name]
        if app_id:
            where_app.append("apps.id=?")
            params_app.append(app_id)
        app_clause = " AND ".join(where_app)
        time_clause = "AND logs.timestamp >= ?" if start else ""
        with db.connect() as conn:
            totals = row_to_dict(
                conn.execute(
                    f"""
                    SELECT
                      (SELECT COALESCE(SUM(exceptions.count),0) FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE {app_clause}) exception_count,
                      (SELECT COUNT(*) FROM exceptions JOIN apps ON apps.id=exceptions.app_id WHERE {app_clause}) cluster_count,
                      (SELECT COUNT(*) FROM logs JOIN apps ON apps.id=logs.app_id WHERE {app_clause} AND UPPER(COALESCE(logs.level,'')) IN ('ERROR','CRITICAL') {time_clause}) error_log_count
                    """,
                    [*params_app, *params_app, *params_app, *([start] if start else [])],
                ).fetchone()
            )
            by_type = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT exceptions.type,
                      COALESCE(SUM(exceptions.count),0) count,
                      COUNT(*) clusters
                    FROM exceptions JOIN apps ON apps.id=exceptions.app_id
                    WHERE {app_clause}
                    GROUP BY exceptions.type
                    ORDER BY count DESC LIMIT 20
                    """,
                    params_app,
                ).fetchall()
            )
            by_service = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT apps.service_name,
                      COUNT(*) clusters,
                      COALESCE(SUM(exceptions.count),0) count
                    FROM exceptions JOIN apps ON apps.id=exceptions.app_id
                    WHERE {app_clause}
                    GROUP BY apps.service_name
                    ORDER BY count DESC LIMIT 20
                    """,
                    params_app,
                ).fetchall()
            )
        return {
            "totals": totals,
            "by_type": by_type,
            "by_service": by_service,
            "window": {"minutes": window_minutes, "start": start},
        }

    @router.get("/errors/timeline")
    def errors_timeline(
        app_id: str | None = None,
        window_minutes: int = Query(1440, ge=1, le=43200),
        bucket_minutes: int = Query(15, ge=1, le=1440),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        start = iso(datetime.now(UTC) - timedelta(minutes=window_minutes))
        bucket = time_bucket("events.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        type_expr = json_text("events.payload_json", "type", is_postgres=db.is_postgres)
        where = ["apps.project_name=?", "events.kind='exception_raised'", "events.timestamp >= ?"]
        params: list[Any] = [project_name, start]
        if app_id:
            where.append("events.app_id=?")
            params.append(app_id)
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT {bucket} bucket, apps.service_name,
                      COALESCE({type_expr}, 'Exception') type,
                      COUNT(*) count
                    FROM events JOIN apps ON apps.id=events.app_id
                    WHERE {' AND '.join(where)}
                    GROUP BY bucket, apps.service_name, type
                    ORDER BY bucket ASC LIMIT 1000
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/dependencies")
    def dependencies(
        app_id: str | None = None,
        dependency_type: str | None = None,
        target: str | None = None,
        with_errors_only: bool = False,
        limit: int = Query(100, ge=1, le=500),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        where = ["apps.project_name=?"]
        params: list[Any] = [project_name]
        if app_id:
            where.append("dependencies.app_id=?")
            params.append(app_id)
        if dependency_type:
            where.append("dependencies.dependency_type=?")
            params.append(dependency_type)
        if target:
            where.append("dependencies.target LIKE ?")
            params.append(f"%{target}%")
        if with_errors_only:
            where.append("dependencies.error_count > 0")
        params.append(limit)
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT dependencies.*, apps.service_name
                    FROM dependencies JOIN apps ON apps.id=dependencies.app_id
                    WHERE {' AND '.join(where)}
                    ORDER BY dependencies.call_count DESC LIMIT ?
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/dependencies/{dependency_id}")
    def dependency_detail(
        dependency_id: str,
        sample_limit: int = Query(20, ge=1, le=100),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        with db.connect() as conn:
            dep = row_to_dict(
                conn.execute(
                    """
                    SELECT dependencies.*, apps.service_name
                    FROM dependencies JOIN apps ON apps.id=dependencies.app_id
                    WHERE dependencies.id=? AND apps.project_name=?
                    """,
                    (dependency_id, project_name),
                ).fetchone()
            )
            if not dep:
                raise HTTPException(status_code=404, detail="dependency not found")
            wanted_key = (
                str(dep.get("app_id")),
                str(dep.get("dependency_type")),
                str(dep.get("target")),
                str(dep.get("operation")),
            )
            rows = rows_to_dicts(
                conn.execute(
                    """
                    SELECT events.*, apps.service_name
                    FROM events JOIN apps ON apps.id=events.app_id
                    WHERE events.app_id=? AND events.kind IN ('db_query','http_client_call','llm_call')
                    ORDER BY events.timestamp DESC LIMIT 5000
                    """,
                    (dep.get("app_id"),),
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
                if (
                    payload.get("error")
                    or payload.get("error_type")
                    or payload.get("error_message")
                    or int(payload.get("status_code") or 0) >= 400
                ):
                    error_samples.append(item)
                if len(samples) >= sample_limit and len(error_samples) >= sample_limit // 2:
                    break
            return {
                "dependency": dep,
                "samples": samples[:sample_limit],
                "error_samples": error_samples[: max(1, sample_limit // 2)],
            }

    @router.get("/llm-usage")
    def llm_usage(
        app_id: str | None = None,
        group_by: str = Query("model", pattern="^(model|provider)$"),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        column = "provider" if group_by == "provider" else "model"
        where = ["apps.project_name=?"]
        params: list[Any] = [project_name]
        if app_id:
            where.append("llm_usage.app_id=?")
            params.append(app_id)
        with db.connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT llm_usage.{column} as group_key,
                      SUM(llm_usage.call_count) call_count,
                      SUM(llm_usage.input_tokens) input_tokens,
                      SUM(llm_usage.output_tokens) output_tokens,
                      SUM(llm_usage.error_count) error_count
                    FROM llm_usage JOIN apps ON apps.id=llm_usage.app_id
                    WHERE {' AND '.join(where)}
                    GROUP BY llm_usage.{column}
                    ORDER BY call_count DESC
                    """,
                    params,
                ).fetchall()
            )

    @router.get("/metrics/timeseries")
    def metrics(
        app_id: str | None = None,
        window_minutes: int = Query(1440, ge=1, le=43200),
        bucket_minutes: int = Query(15, ge=1, le=1440),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> list[dict[str, Any]]:
        start = iso(datetime.now(UTC) - timedelta(minutes=window_minutes))
        where_app = ["apps.project_name=?"]
        params_app: list[Any] = [project_name]
        if app_id:
            where_app.append("apps.id=?")
            params_app.append(app_id)
        clause = " AND ".join(where_app)
        route_bucket = time_bucket("route_durations.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        log_bucket = time_bucket("logs.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        event_bucket = time_bucket("events.timestamp", bucket_minutes, is_postgres=db.is_postgres)
        with db.connect() as conn:
            requests = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT {route_bucket} bucket,
                      COUNT(*) requests,
                      COALESCE(SUM(CASE WHEN COALESCE(route_durations.status_code,0) >= 500 THEN 1 ELSE 0 END),0) request_errors,
                      AVG(route_durations.duration_ms) avg_ms
                    FROM route_durations
                    JOIN routes ON routes.id=route_durations.route_id
                    JOIN apps ON apps.id=routes.app_id
                    WHERE {clause} AND route_durations.timestamp >= ?
                    GROUP BY bucket ORDER BY bucket ASC LIMIT 1000
                    """,
                    [*params_app, start],
                ).fetchall()
            )
            log_rows = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT {log_bucket} bucket,
                      COUNT(*) logs,
                      COALESCE(SUM(CASE WHEN UPPER(COALESCE(logs.level,'')) IN ('ERROR','CRITICAL') THEN 1 ELSE 0 END),0) error_logs
                    FROM logs JOIN apps ON apps.id=logs.app_id
                    WHERE {clause} AND logs.timestamp >= ?
                    GROUP BY bucket ORDER BY bucket ASC LIMIT 1000
                    """,
                    [*params_app, start],
                ).fetchall()
            )
            exc_rows = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT {event_bucket} bucket,
                      COUNT(*) exceptions
                    FROM events JOIN apps ON apps.id=events.app_id
                    WHERE {clause} AND events.kind='exception_raised' AND events.timestamp >= ?
                    GROUP BY bucket ORDER BY bucket ASC LIMIT 1000
                    """,
                    [*params_app, start],
                ).fetchall()
            )
        merged: dict[str, dict[str, Any]] = {}
        for rows in (requests, log_rows, exc_rows):
            for row in rows:
                bucket_value = str(row.get("bucket"))
                item = merged.setdefault(
                    bucket_value,
                    {"bucket": bucket_value, "requests": 0, "request_errors": 0, "avg_ms": 0, "logs": 0, "error_logs": 0, "exceptions": 0},
                )
                item.update({key: value for key, value in row.items() if key != "bucket"})
        return [merged[key] for key in sorted(merged)]

    @router.get("/search")
    def search(
        q: str = Query(..., min_length=1, description="Free text fragment to search in log messages"),
        level: str | None = None,
        app_id: str | None = None,
        window_minutes: int = Query(1440, ge=1, le=43200),
        limit: int = Query(200, ge=1, le=1000),
        project_name: str = Depends(require_project),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        start = iso(datetime.now(UTC) - timedelta(minutes=window_minutes))
        where = ["apps.project_name=?", "logs.timestamp >= ?", "logs.message LIKE ?"]
        params: list[Any] = [project_name, start, f"%{q}%"]
        if level:
            where.append("logs.level=?")
            params.append(level.upper())
        if app_id:
            where.append("logs.app_id=?")
            params.append(app_id)
        params.append(limit)
        with db.connect() as conn:
            log_hits = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT logs.*, apps.service_name
                    FROM logs JOIN apps ON apps.id=logs.app_id
                    WHERE {' AND '.join(where)}
                    ORDER BY logs.timestamp DESC LIMIT ?
                    """,
                    params,
                ).fetchall()
            )
            exc_hits = rows_to_dicts(
                conn.execute(
                    """
                    SELECT exceptions.*, apps.service_name
                    FROM exceptions JOIN apps ON apps.id=exceptions.app_id
                    WHERE apps.project_name=? AND exceptions.normalized_message LIKE ?
                    ORDER BY exceptions.last_seen DESC LIMIT 50
                    """,
                    (project_name, f"%{q}%"),
                ).fetchall()
            )
        return {"query": q, "logs": log_hits, "exceptions": exc_hits, "window_minutes": window_minutes}

    return router
