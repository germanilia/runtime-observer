from __future__ import annotations

import functools
import inspect
import time
from typing import Any

from runtime_observer.redaction import stable_hash


def _emit(observer: Any, kind: str, payload: dict[str, Any]) -> None:
    emit = getattr(observer, "emit_event", None) or getattr(observer, "emit")
    emit(kind, payload)


def instrument_litellm(observer: Any) -> bool:
    try:
        import litellm
    except Exception:
        _emit(observer, "sdk_diagnostic", {"instrumentation": "litellm", "status": "unavailable"})
        return False
    changed = False
    if hasattr(litellm, "completion") and not getattr(litellm.completion, "_runtime_observer_wrapped", False):
        litellm.completion = _wrap_sync(observer, litellm.completion)
        changed = True
    if hasattr(litellm, "acompletion") and not getattr(litellm.acompletion, "_runtime_observer_wrapped", False):
        litellm.acompletion = _wrap_async(observer, litellm.acompletion)
        changed = True
    if changed:
        _emit(observer, "sdk_diagnostic", {"instrumentation": "litellm", "status": "instrumented"})
    return True


def _wrap_sync(observer: Any, original: Any) -> Any:
    @functools.wraps(original)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        error: BaseException | None = None
        response = None
        try:
            response = original(*args, **kwargs)
            return response
        except BaseException as exc:
            error = exc
            raise
        finally:
            _emit(observer, "llm_call", _payload(kwargs, response, started, error, inspect.isgenerator(response)))
    wrapped._runtime_observer_wrapped = True  # type: ignore[attr-defined]
    wrapped._runtime_observer_original = original  # type: ignore[attr-defined]
    return wrapped


def _wrap_async(observer: Any, original: Any) -> Any:
    @functools.wraps(original)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        error: BaseException | None = None
        response = None
        try:
            response = await original(*args, **kwargs)
            return response
        except BaseException as exc:
            error = exc
            raise
        finally:
            _emit(observer, "llm_call", _payload(kwargs, response, started, error, inspect.isasyncgen(response)))
    wrapped._runtime_observer_wrapped = True  # type: ignore[attr-defined]
    wrapped._runtime_observer_original = original  # type: ignore[attr-defined]
    return wrapped


def _payload(kwargs: dict[str, Any], response: Any, started: float, error: BaseException | None, streaming: bool) -> dict[str, Any]:
    messages = kwargs.get("messages") or []
    prompt = kwargs.get("prompt")
    text_for_hash = repr(messages) if messages else repr(prompt)
    usage = _usage(response)
    return {"provider": _provider_from_model(str(kwargs.get("model", "unknown"))), "model": kwargs.get("model"), "streaming": bool(kwargs.get("stream") or streaming), "duration_ms": (time.perf_counter() - started) * 1000, "input_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"), "output_tokens": usage.get("completion_tokens") or usage.get("output_tokens"), "total_tokens": usage.get("total_tokens"), "prompt": {"length": len(text_for_hash), "hash": stable_hash(text_for_hash), "redacted": True}, "response": _response_summary(response), "tool_call_names": _tool_call_names(response), "error_type": type(error).__name__ if error else None, "error_message": str(error) if error else None}


def _usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    return {key: getattr(usage, key) for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens") if hasattr(usage, key)}


def _response_summary(response: Any) -> dict[str, Any]:
    if response is None:
        return {"present": False}
    text = repr(response)
    return {"present": True, "length": len(text), "hash": stable_hash(text), "redacted": True}


def _tool_call_names(response: Any) -> list[str]:
    return [] if "tool_calls" not in repr(response) else ["<redacted_tool_call_name>"]


def _provider_from_model(model: str) -> str:
    return model.split("/", 1)[0] if "/" in model else "unknown"


def instrument(observer: Any) -> bool:
    return instrument_litellm(observer)
