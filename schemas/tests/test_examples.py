"""Minimal stdlib validation for Runtime Observer schema examples."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SCHEMA_DIR / "runtime_observer_schema.json"
EXAMPLES_DIR = SCHEMA_DIR / "examples"


class RuntimeObserverExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text())
        cls.kinds = set(cls.schema["properties"]["kind"]["enum"])
        cls.required_envelope = set(cls.schema["required"])

    def test_schema_has_payload_definition_for_every_kind(self) -> None:
        defs = self.schema["$defs"]
        missing = sorted(kind for kind in self.kinds if kind not in defs)
        self.assertEqual([], missing)

    def test_examples_exist_for_every_kind(self) -> None:
        example_kinds = {path.stem for path in EXAMPLES_DIR.glob("*.json")}
        self.assertEqual(self.kinds, example_kinds)

    def test_examples_have_required_envelope_and_payload_fields(self) -> None:
        for path in sorted(EXAMPLES_DIR.glob("*.json")):
            with self.subTest(example=path.name):
                event = json.loads(path.read_text())
                self.assertTrue(self.required_envelope.issubset(event))
                self.assertEqual("1.0", event["schema_version"])
                self.assertEqual(path.stem, event["kind"])
                self.assertIn(event["kind"], self.kinds)
                self.assertIsInstance(event["payload"], dict)
                service = event["service"]
                self.assertEqual(
                    {"name", "language", "runtime_version", "sdk_version"},
                    set(service).intersection(
                        {"name", "language", "runtime_version", "sdk_version"}
                    ),
                )
                payload_schema = self.schema["$defs"][event["kind"]]
                required_payload = set(payload_schema.get("required", []))
                self.assertTrue(required_payload.issubset(event["payload"]))

    def test_log_record_example_contains_correlation_context(self) -> None:
        event = json.loads((EXAMPLES_DIR / "log_record.json").read_text())
        payload = event["payload"]
        self.assertEqual("log_record", event["kind"])
        self.assertEqual("INFO", payload["level"])
        self.assertIn("route", payload)
        self.assertEqual(event["trace_id"], "018f4d7d-1111-7000-8000-000000000001")
        self.assertEqual(payload["correlation_id"], "corr_01")

    def test_examples_do_not_contain_obvious_secrets(self) -> None:
        forbidden = ("password", "authorization", "bearer ", "api_key", "secret")
        for path in sorted(EXAMPLES_DIR.glob("*.json")):
            with self.subTest(example=path.name):
                body = path.read_text().lower()
                self.assertFalse(any(token in body for token in forbidden))


if __name__ == "__main__":
    unittest.main()
