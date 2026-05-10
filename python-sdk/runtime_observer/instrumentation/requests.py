from __future__ import annotations

import functools
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def safe_url(url: str) -> dict[str, str | None]:
    parsed = urlsplit(url)
    query = "<redacted>" if parsed.query else ""
    return {"scheme": parsed.scheme, "host": parsed.netloc, "path": parsed.path or "/", "url": urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", query, ""))}


def _emit(observer: Any, kind: str, payload: dict[str, Any]) -> None:
    emit = getattr(observer, "emit_event", None) or getattr(observer, "emit")
    emit(kind, payload)


def instrument_requests(observer: Any) -> bool:
    try:
        import requests.sessions
    except Exception:
        _emit(observer, "sdk_diagnostic", {"instrumentation": "requests", "status": "unavailable"})
        return False

    original = requests.sessions.Session.request
    if getattr(original, "_runtime_observer_wrapped", False) or getattr(original, "_runtime_observer", False):
        return True

    @functools.wraps(original)
    def wrapped(self: Any, method: str, url: str, **kwargs: Any) -> Any:
        started = time.perf_counter()
        error: BaseException | None = None
        response = None
        try:
            response = original(self, method, url, **kwargs)
            return response
        except BaseException as exc:
            error = exc
            raise
        finally:
            _emit(observer, "http_client_call", {"library": "requests", "dependency_type": "http", "method": method.upper(), **safe_url(str(url)), "target": safe_url(str(url))["host"], "status_code": getattr(response, "status_code", None), "duration_ms": (time.perf_counter() - started) * 1000, "error_type": type(error).__name__ if error else None})

    wrapped._runtime_observer_wrapped = True  # type: ignore[attr-defined]
    wrapped._runtime_observer_original = original  # type: ignore[attr-defined]
    requests.sessions.Session.request = wrapped
    _emit(observer, "sdk_diagnostic", {"instrumentation": "requests", "status": "instrumented"})
    return True


def instrument(observer: Any) -> bool:
    return instrument_requests(observer)
