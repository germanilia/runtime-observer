from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import time
import uuid
from typing import Any, Iterator

from .config import RuntimeObserverConfig, resolve_config
from .context import child_span_context
from .exporter import BatchExporter
from .logs import attach_loguru, attach_stdlib_logging
from .metadata import collect_app_metadata, collect_dependency_inventory
from .schema import EventBuilder


@dataclass
class RuntimeObserver:
    config: RuntimeObserverConfig
    exporter: BatchExporter = field(init=False)
    builder: EventBuilder = field(init=False)
    _started: bool = field(default=False, init=False)
    _loguru_sink_id: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.exporter = BatchExporter(self.config)
        self.builder = EventBuilder(self.config)
        self.start()

    def start(self) -> None:
        if self._started or not self.config.enabled:
            return
        self.exporter.start()
        self._started = True
        if self.config.capture_logs:
            attach_stdlib_logging(lambda payload: self.emit_event("log_record", payload), self.config)
            self._loguru_sink_id = attach_loguru(lambda payload: self.emit_event("log_record", payload), self.config)
        self.emit_event("app_started", collect_app_metadata())
        self.emit_event("dependency_inventory", collect_dependency_inventory())
        self.instrument_common_dependencies()

    def emit_event(self, kind: str, payload: dict[str, Any] | None = None, **ids: str | None) -> dict[str, Any]:
        event = self.builder.event(kind, payload or {}, **ids)
        self.exporter.enqueue(event)
        return event

    emit = emit_event

    @contextmanager
    def start_span(self, name: str, *, kind: str = "custom", attributes: dict[str, Any] | None = None) -> Iterator[str]:
        span_id = str(uuid.uuid4())
        start = time.perf_counter()
        with child_span_context(span_id) as context:
            self.emit_event("span_started", {"name": name, "kind": kind, "attributes": attributes or {}}, span_id=span_id, parent_span_id=context.parent_span_id)
            try:
                yield span_id
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                self.emit_event("span_finished", {"name": name, "kind": kind, "duration_ms": duration_ms, "status": "error", "error_type": type(exc).__name__}, span_id=span_id, parent_span_id=context.parent_span_id)
                raise
            else:
                duration_ms = (time.perf_counter() - start) * 1000
                self.emit_event("span_finished", {"name": name, "kind": kind, "duration_ms": duration_ms, "status": "ok"}, span_id=span_id, parent_span_id=context.parent_span_id)

    def capture_exception(self, exc: BaseException, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        from .schema import exception_payload

        return self.emit_event("exception_raised", exception_payload(exc, config=self.config, extra=extra))

    def instrument_fastapi(self, app: Any, **options: Any) -> None:
        from .instrumentation.fastapi import instrument_fastapi
        instrument_fastapi(app, self, **options)

    def instrument_logging(self) -> None:
        attach_stdlib_logging(lambda payload: self.emit_event("log_record", payload), self.config)

    def instrument_sqlalchemy(self, engine_or_cls: Any | None = None) -> bool:
        from .instrumentation.sqlalchemy import instrument_sqlalchemy
        return instrument_sqlalchemy(self, engine_or_cls)

    def instrument_requests(self) -> bool:
        from .instrumentation.requests import instrument_requests
        return instrument_requests(self)

    def instrument_httpx(self) -> bool:
        from .instrumentation.httpx import instrument_httpx
        return instrument_httpx(self)

    def instrument_litellm(self) -> bool:
        from .instrumentation.litellm import instrument_litellm
        return instrument_litellm(self)

    def instrument_common_dependencies(self) -> None:
        for module_name, function_name in (("sqlalchemy", "instrument_sqlalchemy"), ("requests", "instrument_requests"), ("httpx", "instrument_httpx"), ("litellm", "instrument_litellm")):
            try:
                module = __import__(f"runtime_observer.instrumentation.{module_name}", fromlist=[function_name])
                getattr(module, function_name)(self)
            except Exception as exc:
                self.emit_event("sdk_diagnostic", {"instrumentation": module_name, "status": "failed", "error_type": type(exc).__name__})

    def flush(self, timeout: float | None = None) -> None:
        self.exporter.flush(timeout=timeout)

    def shutdown(self, timeout: float = 5.0) -> None:
        self.exporter.shutdown(timeout=timeout)


def _init_runtime_observer(**kwargs: Any) -> RuntimeObserver:
    return RuntimeObserver(resolve_config(**kwargs))


def _from_env(**kwargs: Any) -> RuntimeObserver:
    return RuntimeObserver(resolve_config(**kwargs))


init_runtime_observer = _init_runtime_observer
init_runtime_observer.from_env = _from_env  # type: ignore[attr-defined]

__all__ = ["RuntimeObserver", "RuntimeObserverConfig", "init_runtime_observer"]
