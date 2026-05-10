from __future__ import annotations

import atexit
import json
import queue
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from .config import RuntimeObserverConfig


class BatchExporter:
    def __init__(self, config: RuntimeObserverConfig):
        self.config = config
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=config.max_queue_size)
        self._queue = self.queue
        self.dropped_events = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread or not self.config.exporting_enabled:
            return
        self._thread = threading.Thread(target=self._run, name="runtime-observer-exporter", daemon=True)
        self._thread.start()
        atexit.register(self.shutdown)

    def enqueue(self, event: dict[str, Any]) -> None:
        if not self.config.exporting_enabled:
            return
        try:
            raw = json.dumps(event, default=str)
            if len(raw.encode("utf-8")) > self.config.max_event_size_bytes:
                event = {**event, "payload": {"truncated": True, "original_kind": event.get("kind")}}
            self.queue.put_nowait(event)
        except queue.Full:
            self.dropped_events += 1
            return

    def _run(self) -> None:
        while not self._stop.is_set():
            self.flush(timeout=self.config.flush_interval_seconds)

    def flush(self, timeout: float | None = None) -> None:
        batch: list[dict[str, Any]] = []
        deadline = time.time() + (timeout or 0)
        while len(batch) < self.config.batch_size:
            try:
                if not batch and timeout:
                    item = self.queue.get(timeout=max(0.0, deadline - time.time()))
                else:
                    item = self.queue.get_nowait()
                batch.append(item)
            except queue.Empty:
                break
        if batch:
            self._send(batch)

    def _send(self, events: list[dict[str, Any]]) -> None:
        url = self.config.endpoint.rstrip("/") + "/v1/ingest"
        data = json.dumps({"batch_id": events[0].get("event_id"), "events": events}, default=str).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key or 'local-dev-key'}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            return

    def shutdown(self, timeout: float = 5.0) -> None:
        self._stop.set()
        end = time.time() + timeout
        while not self.queue.empty() and time.time() < end:
            self.flush(timeout=0.05)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2)


Exporter = BatchExporter
