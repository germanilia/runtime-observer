from __future__ import annotations

import asyncio
import logging

from runtime_observer import init_runtime_observer
from runtime_observer.config import resolve_config
from runtime_observer.context import ObserverContext, get_current_context, use_context
from runtime_observer.redaction import redact_string, summarize_value


def test_config_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("RUNTIME_OBSERVER_API_KEY", "env-key")
    config = resolve_config(api_key="explicit", service_name="svc", enabled=False)
    assert config.api_key == "explicit"
    assert config.service_name == "svc"
    assert config.enabled is False


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
