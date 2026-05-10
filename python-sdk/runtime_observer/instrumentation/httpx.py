from __future__ import annotations

import functools
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _safe_url(url: Any) -> dict[str, str | None]:
    parsed = urlsplit(str(url))
    query = "<redacted>" if parsed.query else ""
    return {"scheme": parsed.scheme, "host": parsed.netloc, "path": parsed.path or "/", "url": urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", query, ""))}


def _emit(observer: Any, kind: str, payload: dict[str, Any]) -> None:
    emit = getattr(observer, "emit_event", None) or getattr(observer, "emit")
    emit(kind, payload)


def instrument_httpx(observer: Any) -> bool:
    try:
        import httpx
    except Exception:
        _emit(observer, "sdk_diagnostic", {"instrumentation": "httpx", "status": "unavailable"})
        return False

    changed = False
    if not getattr(httpx.Client.request, "_runtime_observer_wrapped", False):
        original_sync = httpx.Client.request

        @functools.wraps(original_sync)
        def sync_wrapped(self: Any, method: str, url: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            error: BaseException | None = None
            response = None
            try:
                response = original_sync(self, method, url, **kwargs)
                return response
            except BaseException as exc:
                error = exc
                raise
            finally:
                _emit_call(observer, method, url, started, response, error)

        sync_wrapped._runtime_observer_wrapped = True  # type: ignore[attr-defined]
        httpx.Client.request = sync_wrapped
        changed = True

    if not getattr(httpx.AsyncClient.request, "_runtime_observer_wrapped", False):
        original_async = httpx.AsyncClient.request

        @functools.wraps(original_async)
        async def async_wrapped(self: Any, method: str, url: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            error: BaseException | None = None
            response = None
            try:
                response = await original_async(self, method, url, **kwargs)
                return response
            except BaseException as exc:
                error = exc
                raise
            finally:
                _emit_call(observer, method, url, started, response, error)

        async_wrapped._runtime_observer_wrapped = True  # type: ignore[attr-defined]
        httpx.AsyncClient.request = async_wrapped
        changed = True

    if changed:
        _emit(observer, "sdk_diagnostic", {"instrumentation": "httpx", "status": "instrumented"})
    return True


def _emit_call(observer: Any, method: str, url: Any, started: float, response: Any, error: BaseException | None) -> None:
    details = _safe_url(url)
    _emit(observer, "http_client_call", {"library": "httpx", "dependency_type": "http", "method": method.upper(), **details, "target": details["host"], "status_code": getattr(response, "status_code", None), "duration_ms": (time.perf_counter() - started) * 1000, "error_type": type(error).__name__ if error else None})


def instrument(observer: Any) -> bool:
    return instrument_httpx(observer)
