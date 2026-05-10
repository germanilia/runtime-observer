from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS apps (
  id TEXT PRIMARY KEY, project_name TEXT, service_name TEXT NOT NULL, display_name TEXT, language TEXT,
  runtime_version TEXT, sdk_version TEXT, first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL, metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, trace_id TEXT, span_id TEXT,
  parent_span_id TEXT, kind TEXT NOT NULL, timestamp TEXT NOT NULL,
  payload_json TEXT NOT NULL, raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_app_kind_time ON events(app_id, kind, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_trace ON events(app_id, trace_id);
CREATE TABLE IF NOT EXISTS routes (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, method TEXT NOT NULL,
  route_pattern TEXT NOT NULL, call_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0, p50_ms REAL NOT NULL DEFAULT 0,
  p95_ms REAL NOT NULL DEFAULT 0, last_seen TEXT NOT NULL,
  UNIQUE(app_id, method, route_pattern)
);
CREATE TABLE IF NOT EXISTS route_durations (
  route_id TEXT NOT NULL, trace_id TEXT, duration_ms REAL NOT NULL, status_code INTEGER, timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_route_durations_route ON route_durations(route_id, timestamp);
CREATE TABLE IF NOT EXISTS traces (
  id TEXT NOT NULL, app_id TEXT NOT NULL, route_id TEXT, started_at TEXT,
  finished_at TEXT, duration_ms REAL, status_code INTEGER, has_error INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(id, app_id)
);
CREATE TABLE IF NOT EXISTS spans (
  id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT, app_id TEXT NOT NULL,
  span_id TEXT, parent_span_id TEXT, name TEXT, kind TEXT, started_at TEXT,
  finished_at TEXT, duration_ms REAL, status TEXT, payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(app_id, trace_id);
CREATE TABLE IF NOT EXISTS exceptions (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
  type TEXT NOT NULL, normalized_message TEXT NOT NULL, first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, sample_trace_id TEXT,
  sample_payload_json TEXT NOT NULL, UNIQUE(app_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, trace_id TEXT, span_id TEXT,
  route_id TEXT, timestamp TEXT NOT NULL, level TEXT, logger_name TEXT,
  message TEXT, source_file TEXT, source_function TEXT, source_line INTEGER,
  structured_json TEXT NOT NULL, exception_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_search ON logs(app_id, timestamp, level, logger_name, trace_id, route_id);
CREATE TABLE IF NOT EXISTS dependencies (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, dependency_type TEXT NOT NULL,
  target TEXT NOT NULL, operation TEXT, call_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0, avg_duration_ms REAL NOT NULL DEFAULT 0,
  p95_duration_ms REAL NOT NULL DEFAULT 0, UNIQUE(app_id, dependency_type, target, operation)
);
CREATE TABLE IF NOT EXISTS dependency_durations (
  dependency_id TEXT NOT NULL, duration_ms REAL NOT NULL, timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_usage (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
  route_id TEXT, call_count INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0, error_count INTEGER NOT NULL DEFAULT 0,
  total_duration_ms REAL NOT NULL DEFAULT 0, UNIQUE(app_id, provider, model, route_id)
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'admin', created_at TEXT NOT NULL, last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS user_preferences (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, project_name TEXT, app_id TEXT,
  preference_type TEXT NOT NULL, target_kind TEXT NOT NULL, target_id TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(user_id, project_name, app_id, preference_type, target_kind, target_id)
);
CREATE INDEX IF NOT EXISTS idx_user_preferences_lookup ON user_preferences(user_id, preference_type, target_kind, app_id, target_id);
CREATE TABLE IF NOT EXISTS project_api_keys (
  id TEXT PRIMARY KEY, project_name TEXT NOT NULL, name TEXT NOT NULL,
  key_hash TEXT NOT NULL UNIQUE, prefix TEXT NOT NULL, created_by TEXT,
  created_at TEXT NOT NULL, last_used_at TEXT, revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_project_api_keys_project ON project_api_keys(project_name, revoked_at);
CREATE TABLE IF NOT EXISTS project_settings (
  project_name TEXT PRIMARY KEY, display_name TEXT,
  created_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(apps)").fetchall()}
            if "project_name" not in columns:
                conn.execute("ALTER TABLE apps ADD COLUMN project_name TEXT")
            if "display_name" not in columns:
                conn.execute("ALTER TABLE apps ADD COLUMN display_name TEXT")

    def clear(self) -> None:
        tables = ["events", "apps", "routes", "route_durations", "traces", "spans", "exceptions", "logs", "dependencies", "dependency_durations", "llm_usage", "user_preferences", "project_api_keys"]
        with self.connect() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
