from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Protocol

from .store import CollectorStore, now_iso

MAX_SQS_MESSAGE_BYTES = 240 * 1024
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestResult:
    accepted: int
    rejected: int = 0
    queued: bool = False
    server_time: str = ""

    def to_response(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "queued": self.queued,
            "server_time": self.server_time or now_iso(),
        }


class IngestQueueError(RuntimeError):
    status_code = 503


class IngestQueueFull(IngestQueueError):
    status_code = 429


class IngestPayloadTooLarge(IngestQueueError):
    status_code = 413


class IngestBackend(Protocol):
    def enqueue(self, events: list[dict[str, Any]]) -> IngestResult:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


class DirectIngestBackend:
    def __init__(self, store: CollectorStore):
        self.store = store

    def enqueue(self, events: list[dict[str, Any]]) -> IngestResult:
        result = self.store.ingest(events)
        return IngestResult(
            accepted=int(result.get("accepted", 0)),
            rejected=int(result.get("rejected", 0)),
            queued=False,
            server_time=str(result.get("server_time") or now_iso()),
        )

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class MemoryIngestBackend:
    def __init__(self, store: CollectorStore, *, max_batches: int, worker_batch_size: int, flush_interval_seconds: float):
        self.store = store
        self.queue: queue.Queue[list[dict[str, Any]]] = queue.Queue(maxsize=max_batches)
        self.worker_batch_size = max(1, worker_batch_size)
        self.flush_interval_seconds = max(0.05, flush_interval_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="runtime-observer-ingest-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._drain_once()

    def enqueue(self, events: list[dict[str, Any]]) -> IngestResult:
        try:
            self.queue.put_nowait(events)
        except queue.Full as exc:
            raise IngestQueueFull("ingest queue is full") from exc
        return IngestResult(accepted=len(events), queued=True, server_time=now_iso())

    def _run(self) -> None:
        while not self._stop.is_set():
            self._drain_once()
            self._stop.wait(self.flush_interval_seconds)

    def _drain_once(self) -> None:
        events: list[dict[str, Any]] = []
        while len(events) < self.worker_batch_size:
            try:
                events.extend(self.queue.get_nowait())
            except queue.Empty:
                break
        if events:
            self.store.ingest(events)


class SqsIngestBackend:
    def __init__(self, store: CollectorStore, *, queue_url: str, endpoint_url: str | None, region_name: str, worker_batch_size: int, flush_interval_seconds: float):
        if not queue_url:
            raise ValueError("SQS ingest backend requires queue_url")
        self.store = store
        self.queue_url = queue_url
        self.worker_batch_size = max(1, min(worker_batch_size, 10))
        self.flush_interval_seconds = max(0.05, flush_interval_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("SQS ingest backend requires boto3") from exc
        self.client = boto3.client("sqs", endpoint_url=endpoint_url or None, region_name=region_name)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="runtime-observer-sqs-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def enqueue(self, events: list[dict[str, Any]]) -> IngestResult:
        try:
            for chunk in self._message_chunks(events):
                self.client.send_message(QueueUrl=self.queue_url, MessageBody=chunk)
        except IngestPayloadTooLarge:
            raise
        except Exception as exc:
            raise IngestQueueError("failed to enqueue ingest batch") from exc
        return IngestResult(accepted=len(events), queued=True, server_time=now_iso())

    def _message_chunks(self, events: list[dict[str, Any]]) -> list[str]:
        chunks: list[str] = []
        current: list[dict[str, Any]] = []
        for event in events:
            candidate = [*current, event]
            body = json.dumps({"events": candidate}, default=str, separators=(",", ":"))
            if len(body.encode("utf-8")) <= MAX_SQS_MESSAGE_BYTES:
                current = candidate
                continue
            if not current:
                raise IngestPayloadTooLarge("single telemetry event exceeds SQS message size")
            chunks.append(json.dumps({"events": current}, default=str, separators=(",", ":")))
            current = [event]
        if current:
            chunks.append(json.dumps({"events": current}, default=str, separators=(",", ":")))
        return chunks

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                response = self.client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=self.worker_batch_size,
                    WaitTimeSeconds=1,
                    VisibilityTimeout=30,
                )
            except Exception:
                LOGGER.exception("failed to receive ingest messages from SQS")
                self._stop.wait(self.flush_interval_seconds)
                continue
            messages = response.get("Messages", [])
            if not messages:
                self._stop.wait(self.flush_interval_seconds)
                continue
            for message in messages:
                if self._process_message(message):
                    self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"])

    def _process_message(self, message: dict[str, Any]) -> bool:
        try:
            payload = json.loads(message.get("Body") or "{}")
            events = payload.get("events") if isinstance(payload, dict) else None
            if not isinstance(events, list):
                return True
            self.store.ingest([event for event in events if isinstance(event, dict)])
            return True
        except Exception:
            LOGGER.exception("failed to process ingest message")
            return False


def build_ingest_backend(store: CollectorStore, settings: Any) -> IngestBackend:
    backend = str(getattr(settings, "ingest_queue_backend", "direct") or "direct").lower()
    if backend == "direct":
        return DirectIngestBackend(store)
    if backend == "memory":
        return MemoryIngestBackend(
            store,
            max_batches=int(getattr(settings, "ingest_queue_max_batches", 1000)),
            worker_batch_size=int(getattr(settings, "ingest_worker_batch_size", 1000)),
            flush_interval_seconds=float(getattr(settings, "ingest_worker_flush_interval_seconds", 1.0)),
        )
    if backend == "sqs":
        return SqsIngestBackend(
            store,
            queue_url=str(getattr(settings, "sqs_queue_url", "")),
            endpoint_url=getattr(settings, "sqs_endpoint_url", None),
            region_name=str(getattr(settings, "aws_region", "us-east-1")),
            worker_batch_size=int(getattr(settings, "ingest_worker_batch_size", 10)),
            flush_interval_seconds=float(getattr(settings, "ingest_worker_flush_interval_seconds", 1.0)),
        )
    raise ValueError(f"Unsupported ingest queue backend: {backend}")
