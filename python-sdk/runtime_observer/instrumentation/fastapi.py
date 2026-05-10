from __future__ import annotations

import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from runtime_observer.context import ObserverContext, new_id, reset_context, set_current_context
from runtime_observer.schema import exception_payload, route_id


def _route_pattern(scope: Scope) -> str:
    route = scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    path_params = scope.get("path_params") or {}
    path = str(scope.get("path") or "/")
    for key, value in path_params.items():
        path = path.replace(str(value), "{" + str(key) + "}")
    return path


def _safe_path(scope: Scope) -> str:
    path = str(scope.get("path") or "/")
    path_params = scope.get("path_params") or {}
    for value in path_params.values():
        path = path.replace(str(value), "<redacted:path_param>")
    return path


class RuntimeObserverASGIMiddleware:
    def __init__(self, app: ASGIApp, observer: Any) -> None:
        self.app = app
        self.observer = observer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method") or "GET")
        incoming_trace_id = _header(scope, b"x-runtime-observer-trace-id")
        trace_id = incoming_trace_id or new_id()
        span_id = new_id()
        correlation_id = _header(scope, b"x-correlation-id") or trace_id
        pattern = str(scope.get("path") or "/")
        rid = route_id(self.observer.config.service_name or "python-service", method, pattern)
        token = set_current_context(ObserverContext(trace_id=trace_id, span_id=span_id, correlation_id=correlation_id, route_id=rid, route_pattern=pattern, method=method, path=str(scope.get("path") or "/")))
        start = time.perf_counter()
        status_code = 500
        request_bytes = 0
        response_bytes = 0

        async def wrapped_receive() -> Message:
            nonlocal request_bytes
            message = await receive()
            if message["type"] == "http.request":
                request_bytes += len(message.get("body") or b"")
            return message

        async def wrapped_send(message: Message) -> None:
            nonlocal status_code, response_bytes
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
            elif message["type"] == "http.response.body":
                response_bytes += len(message.get("body") or b"")
            await send(message)

        self.observer.emit_event("request_started", {"method": method, "path": _safe_path(scope), "route_pattern": pattern, "correlation_id": correlation_id}, trace_id=trace_id, span_id=span_id)
        self.observer.emit_event("span_started", {"name": f"HTTP {method} {pattern}", "kind": "route", "method": method, "route_pattern": pattern}, trace_id=trace_id, span_id=span_id)
        try:
            await self.app(scope, wrapped_receive, wrapped_send)
            pattern = _route_pattern(scope)
            rid = route_id(self.observer.config.service_name or "python-service", method, pattern)
        except Exception as exc:
            pattern = _route_pattern(scope)
            rid = route_id(self.observer.config.service_name or "python-service", method, pattern)
            reset_context(token)
            token = set_current_context(ObserverContext(trace_id=trace_id, span_id=span_id, correlation_id=correlation_id, route_id=rid, route_pattern=pattern, method=method, path=str(scope.get("path") or "/")))
            self.observer.emit_event("exception_raised", exception_payload(exc, config=self.observer.config, extra={"method": method, "route_pattern": pattern, "route_id": rid, "status_code": status_code}), trace_id=trace_id, span_id=span_id)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            try:
                reset_context(token)
            except Exception:
                pass
            token = set_current_context(ObserverContext(trace_id=trace_id, span_id=span_id, correlation_id=correlation_id, route_id=rid, route_pattern=pattern, method=method, path=str(scope.get("path") or "/")))
            status = "error" if status_code >= 500 else "ok"
            discovered = getattr(scope.get("app"), "state", None)
            discovered_key = f"{method} {pattern}"
            if discovered is not None:
                seen = getattr(discovered, "runtime_observer_seen_routes", set())
                if discovered_key not in seen:
                    seen.add(discovered_key)
                    discovered.runtime_observer_seen_routes = seen
                    self.observer.emit_event("route_discovered", {"method": method, "route_pattern": pattern, "route_id": rid})
            endpoint = scope.get("endpoint")
            if endpoint is not None:
                function_span_id = new_id()
                function_name = f"{getattr(endpoint, '__module__', '')}.{getattr(endpoint, '__name__', repr(endpoint))}"
                self.observer.emit_event(
                    "span_finished",
                    {
                        "name": function_name,
                        "kind": "function",
                        "duration_ms": duration_ms,
                        "status": status,
                        "route_pattern": pattern,
                        "route_id": rid,
                        "source_module": getattr(endpoint, "__module__", None),
                        "source_function": getattr(endpoint, "__name__", None),
                    },
                    trace_id=trace_id,
                    span_id=function_span_id,
                    parent_span_id=span_id,
                )
            payload = {"method": method, "path": _safe_path(scope), "route_pattern": pattern, "route_id": rid, "status_code": status_code, "duration_ms": duration_ms, "request_bytes": request_bytes, "response_bytes": response_bytes, "correlation_id": correlation_id}
            self.observer.emit_event("request_finished", payload, trace_id=trace_id, span_id=span_id)
            self.observer.emit_event("span_finished", {"name": f"HTTP {method} {pattern}", "kind": "route", "duration_ms": duration_ms, "status": status, "route_id": rid}, trace_id=trace_id, span_id=span_id)
            reset_context(token)


def _header(scope: Scope, key: bytes) -> str | None:
    for name, value in scope.get("headers") or []:
        if name.lower() == key:
            return value.decode("latin1")
    return None


def discover_routes(app: Any, observer: Any) -> None:
    for route in getattr(getattr(app, "router", None), "routes", []):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or []
        endpoint = getattr(route, "endpoint", None)
        for method in sorted(methods):
            if method in {"HEAD", "OPTIONS"}:
                continue
            pattern = str(path)
            observer.emit_event("route_discovered", {"method": method, "route_pattern": pattern, "route_id": route_id(observer.config.service_name or "python-service", method, pattern), "handler": f"{getattr(endpoint, '__module__', '')}.{getattr(endpoint, '__name__', '')}" if endpoint else None})


def instrument_fastapi(app: Any, observer: Any, *, discover: bool = True) -> None:
    if getattr(app.state, "runtime_observer_instrumented", False):
        return
    app.state.runtime_observer_instrumented = True
    if discover:
        discover_routes(app, observer)
    app.add_middleware(RuntimeObserverASGIMiddleware, observer=observer)
