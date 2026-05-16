from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import platform
import traceback
import uuid
from typing import Any

from .config import RuntimeObserverConfig
from .context import get_current_context
from .redaction import redact_mapping, redact_string

SCHEMA_VERSION = "1.0"
SDK_VERSION = "0.1.0"
VALID_EVENT_KINDS = {
    "app_started",
    "dependency_inventory",
    "route_discovered",
    "request_started",
    "request_finished",
    "span_started",
    "span_finished",
    "exception_raised",
    "db_query",
    "http_client_call",
    "llm_call",
    "log_record",
    "metric_counter",
    "sdk_diagnostic",
    "function_called",
    "function_returned",
    "background_job_started",
    "background_job_finished",
    "tool_call",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def stable_id(*parts: str | None) -> str:
    raw = "|".join(part or "" for part in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def route_id(service_name: str, method: str, route_pattern: str) -> str:
    return stable_id(service_name, method.upper(), route_pattern)


def exception_fingerprint(exc: BaseException) -> str:
    tb = traceback.extract_tb(exc.__traceback__)
    frame = tb[-1] if tb else None
    top = f"{frame.filename}:{frame.name}:{frame.lineno}" if frame else "unknown"
    normalized = redact_string(str(exc), max_length=256)
    return stable_id(type(exc).__name__, top, normalized)


def exception_payload(exc: BaseException, *, config: RuntimeObserverConfig, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    frames = [
        {"file": frame.filename, "function": frame.name, "line": frame.lineno, "module": frame.filename.rsplit("/", 1)[-1]}
        for frame in traceback.extract_tb(exc.__traceback__)
    ]
    payload = {
        "type": type(exc).__name__,
        "message": redact_string(str(exc), max_length=config.max_string_length),
        "fingerprint": exception_fingerprint(exc),
        "stack": frames,
    }
    if exc.__cause__:
        payload["cause"] = {"type": type(exc.__cause__).__name__, "message": redact_string(str(exc.__cause__), max_length=config.max_string_length)}
    if extra:
        payload.update(redact_mapping(extra))
    return payload


@dataclass(slots=True)
class EventBuilder:
    config: RuntimeObserverConfig

    def service(self) -> dict[str, str]:
        service = {
            "project_name": self.config.project_name or "",
            "name": self.config.service_name or "python-service",
            "language": "python",
            "runtime_version": platform.python_version(),
            "sdk_version": SDK_VERSION,
        }
        if self.config.display_name:
            service["display_name"] = self.config.display_name
        return service

    def event(self, kind: str, payload: dict[str, Any] | None = None, *, trace_id: str | None = None, span_id: str | None = None, parent_span_id: str | None = None) -> dict[str, Any]:
        if kind not in VALID_EVENT_KINDS:
            raise ValueError(f"unsupported event kind: {kind}")
        context = get_current_context()
        event = {
            "schema_version": SCHEMA_VERSION,
            "event_id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "service": self.service(),
            "trace_id": trace_id if trace_id is not None else context.trace_id,
            "span_id": span_id if span_id is not None else context.span_id,
            "parent_span_id": parent_span_id if parent_span_id is not None else context.parent_span_id,
            "kind": kind,
            "payload": payload or {},
        }
        if self.config.debug_schema_validation:
            self.validate_event(event)
        return event

    def validate_event(self, event: dict[str, Any]) -> None:
        for field in ("schema_version", "event_id", "timestamp", "service", "kind", "payload"):
            if field not in event:
                raise ValueError(f"missing event field: {field}")
        if event["kind"] not in VALID_EVENT_KINDS:
            raise ValueError(f"invalid event kind: {event['kind']}")
        if not isinstance(event["payload"], dict):
            raise ValueError("event payload must be an object")
