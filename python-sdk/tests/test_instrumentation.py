from __future__ import annotations

import asyncio
import logging
import sys
import types
import unittest
from unittest.mock import patch

from runtime_observer.config import RuntimeObserverConfig
from runtime_observer.context import ObserverContext, use_context
from runtime_observer.instrumentation.httpx import instrument_httpx
from runtime_observer.instrumentation.litellm import instrument_litellm
from runtime_observer.instrumentation.requests import instrument_requests
from runtime_observer.instrumentation.sqlalchemy import _payload
from runtime_observer.schema import EventBuilder
from runtime_observer.logs import RuntimeObserverLoggingHandler
from runtime_observer.redaction import redact_string, redact_value


class DummyObserver:
    def __init__(self) -> None:
        self.config = RuntimeObserverConfig(enabled=False)
        self.events = []

    def emit_event(self, kind, payload, **ids):
        self.events.append({"kind": kind, "payload": payload, **ids})
        return self.events[-1]

    def emit(self, kind, payload, **ids):
        return self.emit_event(kind, payload, **ids)

    def capture_log(self, **kwargs):
        return self.emit_event("log_record", kwargs)


class InstrumentationTests(unittest.TestCase):
    def test_redacts_secret_keys_and_token_like_strings(self):
        redacted = redact_value({"api_key": "abc", "safe": "Bearer abcdefghijklmnop"})
        self.assertEqual(redacted["api_key"], "<redacted>")
        self.assertIn("Bearer <redacted", str(redacted["safe"]))
        self.assertIn("<redacted:jwt>", redact_string("x eyJabc.def.ghi y"))

    def test_event_builder_includes_display_name(self):
        config = RuntimeObserverConfig(enabled=False, project_name="internal-assistant", service_name="backend", display_name="Sample API")
        service = EventBuilder(config).service()
        self.assertEqual(service["project_name"], "internal-assistant")
        self.assertEqual(service["name"], "backend")
        self.assertEqual(service["display_name"], "Sample API")

    def test_stdlib_handler_captures_context_and_redacts(self):
        observer = DummyObserver()
        logger = logging.getLogger("runtime_observer_test_app")
        logger.handlers = []
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.addHandler(RuntimeObserverLoggingHandler(observer, level=logging.INFO))
        with use_context(ObserverContext(trace_id="trace-1", span_id="span-1", route_pattern="/items/{id}", method="GET")):
            logger.info("hello Bearer abcdefghijklmnop")
        event = observer.events[-1]
        self.assertEqual(event["kind"], "log_record")
        self.assertEqual(event["payload"]["trace_id"], "trace-1")
        self.assertIn("<redacted", event["payload"]["message"])

    def test_requests_wrapper_is_idempotent(self):
        requests = types.ModuleType("requests")
        sessions = types.ModuleType("requests.sessions")

        class Session:
            def request(self, method, url, **kwargs):
                return types.SimpleNamespace(status_code=204)

        sessions.Session = Session
        requests.sessions = sessions
        with patch.dict(sys.modules, {"requests": requests, "requests.sessions": sessions}):
            observer = DummyObserver()
            self.assertTrue(instrument_requests(observer))
            first = Session.request
            self.assertTrue(instrument_requests(observer))
            self.assertIs(Session.request, first)
            Session().request("GET", "https://example.test/path?secret=1")
            self.assertEqual(observer.events[-1]["payload"]["url"], "https://example.test/path?<redacted>")

    def test_httpx_wrapper_sync_and_async_are_idempotent(self):
        httpx = types.ModuleType("httpx")

        class Client:
            def request(self, method, url, **kwargs):
                return types.SimpleNamespace(status_code=200)

        class AsyncClient:
            async def request(self, method, url, **kwargs):
                return types.SimpleNamespace(status_code=201)

        httpx.Client = Client
        httpx.AsyncClient = AsyncClient
        with patch.dict(sys.modules, {"httpx": httpx}):
            observer = DummyObserver()
            self.assertTrue(instrument_httpx(observer))
            sync_first = Client.request
            async_first = AsyncClient.request
            self.assertTrue(instrument_httpx(observer))
            self.assertIs(Client.request, sync_first)
            self.assertIs(AsyncClient.request, async_first)
            Client().request("post", "https://api.test/v1?q=secret")
            asyncio.run(AsyncClient().request("get", "https://api.test/v2"))
            statuses = [event["payload"]["status_code"] for event in observer.events if event["kind"] == "http_client_call"]
            self.assertEqual(statuses, [200, 201])

    def test_sqlalchemy_payload_includes_rendered_statement_and_parameters_in_dev(self):
        config = RuntimeObserverConfig(enabled=False, capture_db_query_values=True)
        payload = _payload(
            "SELECT * FROM users WHERE id = $1::INTEGER AND email = $2::VARCHAR",
            (42, "person@example.test"),
            None,
            0,
            None,
            False,
            {"source_file": "dao/user.py", "source_function": "get", "source_line": 10},
            config,
        )
        self.assertEqual(payload["statement_fingerprint"], "SELECT * FROM users WHERE id = $?::INTEGER AND email = $?::VARCHAR")
        self.assertEqual(payload["parameters"], "(42, 'person@example.test')")
        self.assertIn("id = 42::INTEGER", payload["rendered_statement"])
        self.assertIn("email = 'person@example.test'::VARCHAR", payload["rendered_statement"])

    def test_sqlalchemy_payload_can_omit_query_values(self):
        config = RuntimeObserverConfig(enabled=False, capture_db_query_values=False)
        payload = _payload("SELECT * FROM users WHERE id = ?", (42,), None, 0, None, False, {}, config)
        self.assertIn("statement_template", payload)
        self.assertNotIn("parameters", payload)
        self.assertNotIn("rendered_statement", payload)

    def test_litellm_wrapper_redacts_prompt_and_is_idempotent(self):
        litellm = types.ModuleType("litellm")

        def completion(**kwargs):
            return {"usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}, "choices": [{"message": {"content": "secret"}}]}

        async def acompletion(**kwargs):
            return {"usage": {"input_tokens": 1, "output_tokens": 2}}

        litellm.completion = completion
        litellm.acompletion = acompletion
        with patch.dict(sys.modules, {"litellm": litellm}):
            observer = DummyObserver()
            self.assertTrue(instrument_litellm(observer))
            first = litellm.completion
            self.assertTrue(instrument_litellm(observer))
            self.assertIs(litellm.completion, first)
            litellm.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "password=abc"}])
            event = observer.events[-1]
            self.assertEqual(event["kind"], "llm_call")
            self.assertEqual(event["payload"]["provider"], "openai")
            self.assertTrue(event["payload"]["prompt"]["redacted"])
            self.assertNotIn("password=abc", str(event["payload"]))


if __name__ == "__main__":
    unittest.main()
