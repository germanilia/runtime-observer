from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .secrets import load_simple_yaml, sqlite_path_from_url


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 4319
    api_key: str = ""
    dashboard_username: str = "admin"
    dashboard_password: str = ""
    database_path: Path = Path("runtime_observer.sqlite3")
    database_url: str = ""
    secrets_path: Path = Path("secrets.yml")
    insecure_dev_mode: bool = False
    retention_days: int = 7
    retention_min_log_minutes: int = 60
    retention_exception_window_minutes: int = 180
    raw_event_retention_hours: int = 24
    regular_log_retention_hours: int = 4
    trace_retention_days: int = 3
    duration_retention_days: int = 3
    exception_retention_days: int = 90
    aggregate_retention_days: int = 365
    cleanup_interval_seconds: int = 300
    ingest_queue_backend: str = "direct"
    ingest_queue_max_batches: int = 1000
    ingest_worker_batch_size: int = 1000
    ingest_worker_flush_interval_seconds: float = 1.0
    sqs_queue_url: str = ""
    sqs_endpoint_url: str = ""
    aws_region: str = "us-east-1"

    @classmethod
    def from_env(cls) -> "Settings":
        secrets_path = Path(os.getenv("RUNTIME_OBSERVER_SECRETS", "secrets.yml"))
        secrets = load_simple_yaml(secrets_path)
        database = secrets.get("database", {}) if isinstance(secrets.get("database"), dict) else {}
        auth = secrets.get("auth", {}) if isinstance(secrets.get("auth"), dict) else {}
        database_url = os.getenv("RUNTIME_OBSERVER_DATABASE_URL") or str(database.get("url") or database.get("path") or "runtime_observer.sqlite3")
        return cls(
            host=os.getenv("RUNTIME_OBSERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("RUNTIME_OBSERVER_PORT", "4319")),
            api_key=str(auth.get("admin_api_key") or ""),
            dashboard_username="admin",
            dashboard_password="",
            database_path=sqlite_path_from_url(database_url),
            database_url=database_url,
            secrets_path=secrets_path,
            insecure_dev_mode=os.getenv("RUNTIME_OBSERVER_INSECURE_DEV", "false").lower() in {"1", "true", "yes"},
            retention_days=int(os.getenv("RUNTIME_OBSERVER_RETENTION_DAYS", "7")),
            retention_min_log_minutes=int(os.getenv("RUNTIME_OBSERVER_RETENTION_MIN_LOG_MINUTES", "60")),
            retention_exception_window_minutes=int(os.getenv("RUNTIME_OBSERVER_RETENTION_EXCEPTION_WINDOW_MINUTES", "180")),
            raw_event_retention_hours=int(os.getenv("RUNTIME_OBSERVER_RAW_EVENT_RETENTION_HOURS", "24")),
            regular_log_retention_hours=int(os.getenv("RUNTIME_OBSERVER_REGULAR_LOG_RETENTION_HOURS", "4")),
            trace_retention_days=int(os.getenv("RUNTIME_OBSERVER_TRACE_RETENTION_DAYS", "3")),
            duration_retention_days=int(os.getenv("RUNTIME_OBSERVER_DURATION_RETENTION_DAYS", "3")),
            exception_retention_days=int(os.getenv("RUNTIME_OBSERVER_EXCEPTION_RETENTION_DAYS", "90")),
            aggregate_retention_days=int(os.getenv("RUNTIME_OBSERVER_AGGREGATE_RETENTION_DAYS", "365")),
            cleanup_interval_seconds=int(os.getenv("RUNTIME_OBSERVER_CLEANUP_INTERVAL_SECONDS", "300")),
            ingest_queue_backend=os.getenv("RUNTIME_OBSERVER_INGEST_QUEUE_BACKEND", "direct"),
            ingest_queue_max_batches=int(os.getenv("RUNTIME_OBSERVER_INGEST_QUEUE_MAX_BATCHES", "1000")),
            ingest_worker_batch_size=int(os.getenv("RUNTIME_OBSERVER_INGEST_WORKER_BATCH_SIZE", "1000")),
            ingest_worker_flush_interval_seconds=float(os.getenv("RUNTIME_OBSERVER_INGEST_WORKER_FLUSH_INTERVAL_SECONDS", "1.0")),
            sqs_queue_url=os.getenv("RUNTIME_OBSERVER_SQS_QUEUE_URL", ""),
            sqs_endpoint_url=os.getenv("RUNTIME_OBSERVER_SQS_ENDPOINT_URL", ""),
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        )
