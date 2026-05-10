from __future__ import annotations

from collections import defaultdict, deque
import logging
import threading
import time
import traceback
from typing import Any

from .config import RuntimeObserverConfig
from .context import get_current_context
from .redaction import redact_mapping, redact_string

_internal = threading.local()


def is_internal_logging() -> bool:
    return bool(getattr(_internal, "active", False))


class _InternalGuard:
    def __enter__(self):
        _internal.active = True

    def __exit__(self, exc_type, exc, tb):
        _internal.active = False


class LogRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, logger_name: str, level: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.time()
        key = (logger_name, level)
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


class RuntimeObserverLoggingHandler(logging.Handler):
    def __init__(self, observer_or_emit, config: RuntimeObserverConfig | None = None, level: int = logging.DEBUG) -> None:
        super().__init__(level=level)
        self.observer = observer_or_emit if hasattr(observer_or_emit, "emit_event") else None
        self.emit_log = observer_or_emit if self.observer is None else None
        self.config = config or getattr(observer_or_emit, "config", RuntimeObserverConfig())
        self.rate_limiter = LogRateLimiter(self.config.log_rate_limit_per_minute)

    def emit(self, record: logging.LogRecord) -> None:
        if is_internal_logging() or (record.name == "runtime_observer" or record.name.startswith("runtime_observer.")):
            return
        level = record.levelname.upper()
        if level not in self.config.log_levels:
            return
        if not self.rate_limiter.allow(record.name, level):
            return
        try:
            with _InternalGuard():
                payload = build_log_payload(record, self.config)
                if self.observer is not None:
                    self.observer.emit_event("log_record", payload)
                else:
                    self.emit_log(payload)
        except Exception:
            return


def build_log_payload(record: logging.LogRecord, config: RuntimeObserverConfig) -> dict[str, Any]:
    context = get_current_context()
    payload: dict[str, Any] = {
        "level": record.levelname,
        "logger_name": record.name,
        "message": redact_string(record.getMessage(), max_length=config.log_message_max_length),
        "source_file": record.pathname,
        "source_function": record.funcName,
        "source_line": record.lineno,
        "thread": record.threadName,
        "process": record.process,
        "trace_id": context.trace_id,
        "span_id": context.span_id,
        "route_id": context.route_id,
        "route_pattern": context.route_pattern,
        "route": context.route_pattern,
        "correlation_id": context.correlation_id,
    }
    standard = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())
    extras = {key: value for key, value in record.__dict__.items() if key not in standard and not key.startswith("_")}
    if extras:
        payload["structured"] = redact_mapping(extras)
    if record.exc_info:
        payload["exception"] = {"type": record.exc_info[0].__name__ if record.exc_info[0] else None, "message": redact_string(str(record.exc_info[1]), max_length=config.max_string_length), "stack": traceback.format_exception(*record.exc_info)[-20:]}
    return payload


def attach_stdlib_logging(emit_log, config: RuntimeObserverConfig) -> RuntimeObserverLoggingHandler:
    handler = RuntimeObserverLoggingHandler(emit_log, config)
    root = logging.getLogger()
    if not any(isinstance(existing, RuntimeObserverLoggingHandler) for existing in root.handlers):
        root.addHandler(handler)
    return handler


class LoguruSink:
    def __init__(self, emit_log, config: RuntimeObserverConfig) -> None:
        self.emit_log = emit_log
        self.config = config
        self.rate_limiter = LogRateLimiter(config.log_rate_limit_per_minute)

    def __call__(self, message: Any) -> None:
        if is_internal_logging():
            return
        record = message.record
        level = record["level"].name.upper()
        logger_name = record.get("name") or "loguru"
        if level not in self.config.log_levels or not self.rate_limiter.allow(logger_name, level):
            return
        context = get_current_context()
        with _InternalGuard():
            payload = {"level": level, "logger_name": logger_name, "message": redact_string(record.get("message", ""), max_length=self.config.log_message_max_length), "source_file": str(record["file"].path), "source_function": record["function"], "source_line": record["line"], "thread": str(record["thread"].name), "process": record["process"].id, "trace_id": context.trace_id, "span_id": context.span_id, "route_id": context.route_id, "route_pattern": context.route_pattern, "correlation_id": context.correlation_id, "structured": redact_mapping(record.get("extra") or {})}
            if record.get("exception"):
                payload["exception"] = {"type": record["exception"].type.__name__, "message": redact_string(str(record["exception"].value), max_length=self.config.max_string_length)}
            self.emit_log(payload)


def attach_loguru(emit_log, config: RuntimeObserverConfig) -> int | None:
    try:
        from loguru import logger
    except Exception:
        return None
    return logger.add(LoguruSink(emit_log, config), level="DEBUG", enqueue=False, catch=True)
