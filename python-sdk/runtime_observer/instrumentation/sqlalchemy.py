from __future__ import annotations

import inspect
import re
import time
from pathlib import Path
from typing import Any

from runtime_observer.context import get_current_context

_LITERAL_RE = re.compile(r"'(?:''|[^'])*'|\b\d+(?:\.\d+)?\b")
_WS_RE = re.compile(r"\s+")
_TABLE_RE = re.compile(r"\b(?:from|join|into|update|table)\s+([\w.\"`]+)", re.IGNORECASE)


def sql_fingerprint(statement: str) -> str:
    return _WS_RE.sub(" ", _LITERAL_RE.sub("?", statement)).strip()[:4000]


def sql_operation(statement: str) -> str:
    first = statement.strip().split(maxsplit=1)[0].upper() if statement.strip() else "OTHER"
    return first if first in {"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"} else "OTHER"


def sql_tables(statement: str) -> list[str]:
    return [match.group(1).strip('\"`') for match in _TABLE_RE.finditer(statement)][:10]


def _emit(observer: Any, kind: str, payload: dict[str, Any]) -> None:
    emit = getattr(observer, "emit_event", None) or getattr(observer, "emit")
    emit(kind, payload)


def instrument_sqlalchemy(observer: Any, engine_or_cls: Any | None = None) -> bool:
    try:
        from sqlalchemy import Engine, event
    except Exception:
        _emit(observer, "sdk_diagnostic", {"instrumentation": "sqlalchemy", "status": "unavailable"})
        return False
    target = engine_or_cls or Engine
    if getattr(target, "_runtime_observer_instrumented", False):
        return True

    def before_cursor_execute(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool) -> None:
        context._runtime_observer_started = time.perf_counter()
        context._runtime_observer_caller = _caller()

    def after_cursor_execute(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool) -> None:
        _emit(observer, "db_query", _payload(statement, parameters, cursor, getattr(context, "_runtime_observer_started", time.perf_counter()), None, executemany, getattr(context, "_runtime_observer_caller", None), getattr(observer, "config", None)))

    def handle_error(exception_context: Any) -> None:
        _emit(observer, "db_query", _payload(exception_context.statement or "", getattr(exception_context, "parameters", None), None, time.perf_counter(), exception_context.original_exception, False, _caller(), getattr(observer, "config", None)))

    event.listen(target, "before_cursor_execute", before_cursor_execute)
    event.listen(target, "after_cursor_execute", after_cursor_execute)
    event.listen(target, "handle_error", handle_error)
    setattr(target, "_runtime_observer_instrumented", True)
    _emit(observer, "sdk_diagnostic", {"instrumentation": "sqlalchemy", "status": "instrumented"})
    return True


def _caller() -> dict[str, Any]:
    stack = _application_stack()
    if not stack:
        return {}
    caller = stack[0]
    return {
        "source_file": caller["source_file"],
        "source_function": caller["source_function"],
        "source_line": caller["source_line"],
        "source_stack": stack[:8],
    }


def _application_stack() -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for frame in inspect.stack()[2:100]:
        filename = frame.filename
        normalized = filename.replace("\\", "/")
        if any(part in normalized for part in ("runtime_observer", "site-packages/sqlalchemy", "site-packages/sqlmodel", "site-packages/aiosqlite", "site-packages/asyncpg")):
            continue
        frames.append({"source_file": str(Path(filename)), "source_function": frame.function, "source_line": frame.lineno})
    return frames


def _payload(statement: str, parameters: Any, cursor: Any, started: float, error: BaseException | None, executemany: bool, caller_override: dict[str, Any] | None = None, config: Any | None = None) -> dict[str, Any]:
    rowcount = getattr(cursor, "rowcount", None) if cursor is not None else None
    tables = sql_tables(statement)
    context = get_current_context()
    caller = caller_override or _caller()
    payload = {
        "operation": sql_operation(statement),
        "statement_fingerprint": sql_fingerprint(statement),
        "statement_template": _truncate(statement, config),
        "tables": tables,
        "target": tables[0] if tables else "unknown-db",
        "duration_ms": (time.perf_counter() - started) * 1000,
        "row_count": rowcount if isinstance(rowcount, int) and rowcount >= 0 else None,
        "executemany": executemany,
        "route_id": context.route_id,
        "route_pattern": context.route_pattern,
        "source": "sqlalchemy",
        **caller,
        "error_type": type(error).__name__ if error else None,
        "error_message": str(error) if error else None,
    }
    if _capture_values(config):
        payload["parameters"] = _serialize_parameters(parameters, config)
        payload["rendered_statement"] = _render_statement(statement, parameters, config)
    return payload


def _capture_values(config: Any | None) -> bool:
    return bool(getattr(config, "capture_db_query_values", True))


def _max_query_length(config: Any | None) -> int:
    return int(getattr(config, "db_query_max_length", 8192) or 8192)


def _truncate(value: str, config: Any | None) -> str:
    max_length = _max_query_length(config)
    return value if len(value) <= max_length else value[:max_length] + "…<truncated>"


def _serialize_parameters(parameters: Any, config: Any | None) -> Any:
    if parameters is None:
        return None
    return _truncate_repr(parameters, config)


def _truncate_repr(value: Any, config: Any | None) -> str:
    rendered = repr(value)
    return _truncate(rendered, config)


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, bytes | bytearray):
        return "'" + bytes(value).hex() + "'"
    return "'" + str(value).replace("'", "''") + "'"


def _render_statement(statement: str, parameters: Any, config: Any | None) -> str:
    rendered = statement
    try:
        if isinstance(parameters, dict):
            for key, value in sorted(parameters.items(), key=lambda item: len(str(item[0])), reverse=True):
                rendered = re.sub(rf":{re.escape(str(key))}\b", _sql_literal(value), rendered)
                rendered = re.sub(rf"%\({re.escape(str(key))}\)s", _sql_literal(value), rendered)
        elif isinstance(parameters, list | tuple):
            values = list(parameters)
            if values and isinstance(values[0], dict):
                return _truncate(f"{statement}\n-- executemany parameters: {_truncate_repr(values, config)}", config)
            rendered = _render_positional_statement(rendered, values)
    except Exception:
        return _truncate(f"{statement}\n-- parameters: {_truncate_repr(parameters, config)}", config)
    return _truncate(rendered, config)


def _render_positional_statement(statement: str, values: list[Any]) -> str:
    rendered = statement
    for index, value in enumerate(values, start=1):
        rendered = re.sub(rf"\${index}(?!\d)", _sql_literal(value), rendered)
    if "$1" not in statement:
        for value in values:
            literal = _sql_literal(value)
            rendered = rendered.replace("?", literal, 1)
            rendered = rendered.replace("%s", literal, 1)
    return rendered


def instrument(observer: Any) -> bool:
    return instrument_sqlalchemy(observer)
