from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import time
import uuid
from typing import Iterator


@dataclass(frozen=True, slots=True)
class ObserverContext:
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    correlation_id: str | None = None
    route_id: str | None = None
    route_pattern: str | None = None
    method: str | None = None
    path: str | None = None

    def __init__(self, trace_id: str | None = None, span_id: str | None = None, parent_span_id: str | None = None, correlation_id: str | None = None, route_id: str | None = None, route_pattern: str | None = None, method: str | None = None, path: str | None = None, route: str | None = None) -> None:
        object.__setattr__(self, "trace_id", trace_id)
        object.__setattr__(self, "span_id", span_id)
        object.__setattr__(self, "parent_span_id", parent_span_id)
        object.__setattr__(self, "correlation_id", correlation_id)
        object.__setattr__(self, "route_id", route_id)
        object.__setattr__(self, "route_pattern", route_pattern or route)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "path", path)


TraceContext = ObserverContext
_current_context: ContextVar[ObserverContext] = ContextVar("runtime_observer_context", default=ObserverContext())
_span_stack: ContextVar[tuple[str, ...]] = ContextVar("runtime_observer_span_stack", default=())


def get_current_context() -> ObserverContext:
    return _current_context.get()


def current_context() -> ObserverContext | None:
    context = get_current_context()
    return context if context.trace_id else None


def set_current_context(context: ObserverContext):
    return _current_context.set(context)


def set_context(context: ObserverContext | None):
    return _current_context.set(context or ObserverContext())


def reset_context(token) -> None:
    _current_context.reset(token)


def current_span_id() -> str | None:
    stack = _span_stack.get()
    if stack:
        return stack[-1]
    return get_current_context().span_id


@contextmanager
def use_context(context: ObserverContext) -> Iterator[ObserverContext]:
    token = set_current_context(context)
    try:
        yield context
    finally:
        reset_context(token)


@contextmanager
def child_span_context(span_id: str, *, parent_span_id: str | None = None) -> Iterator[ObserverContext]:
    current = get_current_context()
    context = ObserverContext(trace_id=current.trace_id, span_id=span_id, parent_span_id=parent_span_id or current.span_id, correlation_id=current.correlation_id, route_id=current.route_id, route_pattern=current.route_pattern, method=current.method, path=current.path)
    with use_context(context):
        yield context


@contextmanager
def push_span(span_id: str) -> Iterator[None]:
    stack = _span_stack.get()
    token = _span_stack.set((*stack, span_id))
    try:
        yield
    finally:
        _span_stack.reset(token)


@contextmanager
def span_context(span_id: str, parent_span_id: str | None = None) -> Iterator[ObserverContext | None]:
    with push_span(span_id):
        yield current_context()


def new_id() -> str:
    return str(uuid.uuid4())


def monotonic_ms() -> float:
    return time.perf_counter() * 1000
