from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from runtime_observer_server.config import Settings
from runtime_observer_server.db import Database
from runtime_observer_server.ingest_queue import IngestPayloadTooLarge, MemoryIngestBackend, SqsIngestBackend
from runtime_observer_server.main import create_app
from runtime_observer_server.store import CollectorStore


def iso_at(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sample_event(event_id: str = "queued-finish") -> dict[str, object]:
    service = {"project_name": "queue", "name": "api", "language": "python"}
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "timestamp": iso_at(timedelta()),
        "service": service,
        "trace_id": event_id,
        "kind": "request_finished",
        "payload": {"method": "GET", "route_pattern": "/queued", "duration_ms": 12, "status_code": 200},
    }


def test_duplicate_events_do_not_increment_aggregates(tmp_path):
    db = Database(tmp_path / "collector.sqlite3")
    event = sample_event("same-event")

    result = CollectorStore(db).ingest([event, event])

    assert result["accepted"] == 2
    with db.connect() as conn:
        route = conn.execute("SELECT call_count FROM routes WHERE route_pattern='/queued'").fetchone()
        metric = conn.execute("SELECT request_count FROM route_metrics_hourly").fetchone()
    assert route["call_count"] == 1
    assert metric["request_count"] == 1


def test_route_counts_are_not_capped_by_recent_duration_window(tmp_path):
    db = Database(tmp_path / "collector.sqlite3")
    service = {"project_name": "load", "name": "api", "language": "python"}
    events = [
        {
            "schema_version": "1.0",
            "event_id": f"load-{index}",
            "timestamp": iso_at(timedelta(seconds=index)),
            "service": service,
            "trace_id": f"trace-{index}",
            "kind": "request_finished",
            "payload": {"method": "GET", "route_pattern": "/hot", "duration_ms": index % 100, "status_code": 500 if index % 1000 == 0 else 200},
        }
        for index in range(10_005)
    ]

    result = CollectorStore(db).ingest(events)

    assert result["accepted"] == 10_005
    with db.connect() as conn:
        route = conn.execute("SELECT call_count, error_count FROM routes WHERE route_pattern='/hot'").fetchone()
    assert route["call_count"] == 10_005
    assert route["error_count"] == 11


def test_memory_ingest_backend_buffers_and_drains(tmp_path):
    db = Database(tmp_path / "collector.sqlite3")
    backend = MemoryIngestBackend(CollectorStore(db), max_batches=10, worker_batch_size=100, flush_interval_seconds=0.05)
    backend.start()
    try:
        result = backend.enqueue([sample_event()])
        assert result.queued is True
        deadline = time.time() + 2
        while time.time() < deadline:
            with db.connect() as conn:
                count = conn.execute("SELECT COUNT(*) AS count FROM routes").fetchone()["count"]
            if count == 1:
                break
            time.sleep(0.05)
    finally:
        backend.stop()

    with db.connect() as conn:
        route = conn.execute("SELECT route_pattern, call_count FROM routes").fetchone()
        metric = conn.execute("SELECT request_count FROM route_metrics_hourly").fetchone()
    assert route["route_pattern"] == "/queued"
    assert route["call_count"] == 1
    assert metric["request_count"] == 1


class FakeSqsClient:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, *, QueueUrl: str, MessageBody: str) -> None:
        self.messages.append(MessageBody)


def test_sqs_backend_splits_large_batches(tmp_path):
    backend = SqsIngestBackend.__new__(SqsIngestBackend)
    backend.store = CollectorStore(Database(tmp_path / "collector.sqlite3"))
    backend.queue_url = "queue"
    backend.client = FakeSqsClient()
    backend.worker_batch_size = 10
    backend.flush_interval_seconds = 1.0
    large_message = "x" * 70_000
    events = [sample_event(f"evt-{index}") | {"payload": {"message": large_message}} for index in range(6)]

    result = backend.enqueue(events)

    assert result.accepted == 6
    assert len(backend.client.messages) > 1
    assert all(len(message.encode("utf-8")) <= 240 * 1024 for message in backend.client.messages)


def test_sqs_backend_rejects_single_oversized_event(tmp_path):
    backend = SqsIngestBackend.__new__(SqsIngestBackend)
    backend.store = CollectorStore(Database(tmp_path / "collector.sqlite3"))
    backend.queue_url = "queue"
    backend.client = FakeSqsClient()
    backend.worker_batch_size = 10
    backend.flush_interval_seconds = 1.0
    event = sample_event("too-large") | {"payload": {"message": "x" * 300_000}}

    try:
        backend.enqueue([event])
    except IngestPayloadTooLarge:
        pass
    else:
        raise AssertionError("expected IngestPayloadTooLarge")


def test_ingest_endpoint_can_use_memory_queue(tmp_path):
    settings = Settings(
        api_key="test-key",
        database_path=tmp_path / "collector.sqlite3",
        ingest_queue_backend="memory",
        ingest_worker_flush_interval_seconds=0.05,
        insecure_dev_mode=True,
    )
    with TestClient(create_app(settings)) as client:
        project_key = client.post("/api/projects/queue/api-keys").json()["api_key"]
        response = client.post("/v1/ingest", headers={"Authorization": f"Bearer {project_key}"}, json={"events": [sample_event("via-api")]})
        assert response.status_code == 200
        assert response.json()["queued"] is True
        deadline = time.time() + 2
        while time.time() < deadline:
            apps = client.get("/api/apps", headers={"X-Runtime-Observer-User": "dev"})
            if apps.status_code == 401:
                break
            if apps.json():
                break
            time.sleep(0.05)
