from __future__ import annotations

import asyncio
import logging
import pytest

from runtime_observer import init_runtime_observer
from runtime_observer.config import resolve_config
from runtime_observer.logs import RuntimeObserverLoggingHandler
from runtime_observer.context import ObserverContext, get_current_context, use_context
from runtime_observer.redaction import redact_string, summarize_value


def test_config_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("RUNTIME_OBSERVER_API_KEY", "env-key")
    config = resolve_config(api_key="explicit", service_name="svc", enabled=False)
    assert config.api_key == "explicit"
    assert config.service_name == "svc"
    assert config.enabled is False


def test_project_name_is_deprecated_and_not_required_for_export(monkeypatch):
    monkeypatch.delenv("RUNTIME_OBSERVER_PROJECT_NAME", raising=False)
    config = resolve_config(api_key="project-key", service_name="svc", enabled=True)
    assert config.project_name is None
    assert config.exporting_enabled is True

    with pytest.warns(DeprecationWarning, match="project_name"):
        legacy = resolve_config(api_key="project-key", project_name="legacy", service_name="svc", enabled=True)
    assert legacy.project_name == "legacy"
    assert legacy.exporting_enabled is True


def test_config_log_level_filters_debug(monkeypatch):
    monkeypatch.setenv("RUNTIME_OBSERVER_LOG_LEVEL", "info")
    config = resolve_config(enabled=False)
    assert "DEBUG" not in config.log_levels
    assert {"INFO", "WARNING", "ERROR", "CRITICAL"}.issubset(config.log_levels)


def test_config_log_levels_allow_explicit_set(monkeypatch):
    monkeypatch.setenv("RUNTIME_OBSERVER_LOG_LEVELS", "warning,error")
    config = resolve_config(enabled=False)
    assert config.log_levels == {"WARNING", "ERROR"}


def test_redaction_secret_patterns():
    assert "<redacted:jwt>" in redact_string("token eyJabcDEF12345.eyJabcDEF12345.signature12345")
    assert "<redacted:aws_access_key>" in redact_string("AKIAABCDEFGHIJKLMNOP")
    summary = summarize_value({"password": "super-secret", "email": "user@example.com"})
    assert summary["items"]["password"]["value"] == "<redacted:secret>"
    assert summary["items"]["email"]["value"] == "<redacted:email>"


def test_context_propagates_across_asyncio():
    async def read_context():
        await asyncio.sleep(0)
        return get_current_context().trace_id

    async def run():
        with use_context(ObserverContext(trace_id="trace-1")):
            return await read_context()

    assert asyncio.run(run()) == "trace-1"


def test_python_sdk_supports_all_schema_event_kinds():
    observer = init_runtime_observer(service_name="test", enabled=True, insecure_local_dev=True, capture_logs=False)
    observer.exporter.shutdown(timeout=0.1)
    event = observer.emit("function_called", {"name": "calculate_quote", "attributes": {"source": "manual_instrumentation"}})
    assert event["kind"] == "function_called"
    assert event["payload"]["name"] == "calculate_quote"


def test_exporter_drops_when_queue_full():
    observer = init_runtime_observer(service_name="test", enabled=True, insecure_local_dev=True, max_queue_size=1, capture_logs=False)
    observer.exporter.shutdown(timeout=0.1)
    observer.exporter.enqueue(observer.builder.event("sdk_diagnostic", {"n": 1}))
    observer.exporter.enqueue(observer.builder.event("sdk_diagnostic", {"n": 2}))
    assert observer.exporter.dropped_events >= 1


def test_stdlib_log_capture_is_redacted():
    observer = init_runtime_observer(service_name="test", enabled=True, insecure_local_dev=True, capture_logs=True)
    observer.exporter.shutdown(timeout=0.1)
    logger = logging.getLogger("runtime_observer_test")
    logger.warning("Authorization Bearer abcdefghijklmnopqrstuvwxyz0123456789")
    events = []
    while not observer.exporter._queue.empty():
        events.append(observer.exporter._queue.get_nowait())
    log_events = [event for event in events if event["kind"] == "log_record"]
    assert log_events
    assert "<redacted:token>" in log_events[-1]["payload"]["message"]


def test_existing_stdlib_handler_uses_new_log_level_config():
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    root.handlers = [handler for handler in root.handlers if not isinstance(handler, RuntimeObserverLoggingHandler)]
    try:
        first = init_runtime_observer(service_name="test", enabled=True, insecure_local_dev=True, capture_logs=True)
        first.exporter.shutdown(timeout=0.1)
        second = init_runtime_observer(service_name="test", enabled=True, insecure_local_dev=True, capture_logs=True, log_level="INFO")
        second.exporter.shutdown(timeout=0.1)
        logger = logging.getLogger("runtime_observer_reconfigured")
        logger.setLevel(logging.DEBUG)
        logger.debug("debug should not be captured")
        logger.info("info should be captured")
        events = []
        while not second.exporter._queue.empty():
            events.append(second.exporter._queue.get_nowait())
        messages = [event["payload"].get("message") for event in events if event["kind"] == "log_record"]
        assert "debug should not be captured" not in messages
        assert "info should be captured" in messages
    finally:
        root.handlers = previous_handlers
