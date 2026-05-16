from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any


SQLITE_SCHEMA = """
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
CREATE INDEX IF NOT EXISTS idx_events_trace_time ON events(trace_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_kind_time ON events(kind, timestamp);
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
CREATE INDEX IF NOT EXISTS idx_traces_route_app ON traces(route_id, app_id);
CREATE TABLE IF NOT EXISTS spans (
  id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT, app_id TEXT NOT NULL,
  span_id TEXT, parent_span_id TEXT, name TEXT, kind TEXT, started_at TEXT,
  finished_at TEXT, duration_ms REAL, status TEXT, payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(app_id, trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_trace_time ON spans(trace_id, started_at);
CREATE TABLE IF NOT EXISTS exceptions (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
  type TEXT NOT NULL, normalized_message TEXT NOT NULL, first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, sample_trace_id TEXT,
  sample_payload_json TEXT NOT NULL, UNIQUE(app_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_exceptions_sample_trace ON exceptions(sample_trace_id, last_seen);
CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, trace_id TEXT, span_id TEXT,
  route_id TEXT, timestamp TEXT NOT NULL, level TEXT, logger_name TEXT,
  message TEXT, source_file TEXT, source_function TEXT, source_line INTEGER,
  structured_json TEXT NOT NULL, exception_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_search ON logs(app_id, timestamp, level, logger_name, trace_id, route_id);
CREATE INDEX IF NOT EXISTS idx_logs_trace_time ON logs(trace_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_time_trace ON logs(timestamp, trace_id);
CREATE INDEX IF NOT EXISTS idx_logs_route_app ON logs(route_id, app_id);
CREATE TABLE IF NOT EXISTS dependencies (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, dependency_type TEXT NOT NULL,
  target TEXT NOT NULL, operation TEXT, call_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0, avg_duration_ms REAL NOT NULL DEFAULT 0,
  p95_duration_ms REAL NOT NULL DEFAULT 0, UNIQUE(app_id, dependency_type, target, operation)
);
CREATE TABLE IF NOT EXISTS dependency_durations (
  dependency_id TEXT NOT NULL, duration_ms REAL NOT NULL, timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dependency_durations_dep ON dependency_durations(dependency_id, timestamp);
CREATE TABLE IF NOT EXISTS route_metrics_hourly (
  route_id TEXT NOT NULL, app_id TEXT NOT NULL, bucket_start TEXT NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0, error_count INTEGER NOT NULL DEFAULT 0,
  total_duration_ms REAL NOT NULL DEFAULT 0, min_duration_ms REAL, max_duration_ms REAL,
  PRIMARY KEY(route_id, bucket_start)
);
CREATE TABLE IF NOT EXISTS dependency_metrics_hourly (
  dependency_id TEXT NOT NULL, app_id TEXT NOT NULL, bucket_start TEXT NOT NULL,
  call_count INTEGER NOT NULL DEFAULT 0, error_count INTEGER NOT NULL DEFAULT 0,
  total_duration_ms REAL NOT NULL DEFAULT 0, min_duration_ms REAL, max_duration_ms REAL,
  PRIMARY KEY(dependency_id, bucket_start)
);
CREATE TABLE IF NOT EXISTS log_metrics_hourly (
  app_id TEXT NOT NULL, route_id TEXT, level TEXT NOT NULL, bucket_start TEXT NOT NULL,
  log_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(app_id, route_id, level, bucket_start)
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
CREATE TABLE IF NOT EXISTS collector_settings (
  key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL, updated_by TEXT
);
CREATE TABLE IF NOT EXISTS retention_pins (
  id TEXT PRIMARY KEY, app_id TEXT NOT NULL, target_kind TEXT NOT NULL,
  target_id TEXT NOT NULL, trace_id TEXT, start_time TEXT, end_time TEXT,
  reason TEXT, created_at TEXT NOT NULL, expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_retention_pins_target ON retention_pins(app_id, target_kind, target_id);
CREATE INDEX IF NOT EXISTS idx_retention_pins_trace ON retention_pins(trace_id);
CREATE INDEX IF NOT EXISTS idx_retention_pins_window ON retention_pins(start_time, end_time, expires_at);
"""

POSTGRES_SCHEMA = SQLITE_SCHEMA.replace("PRAGMA journal_mode=WAL;", "CREATE EXTENSION IF NOT EXISTS vector;").replace(
    "id INTEGER PRIMARY KEY AUTOINCREMENT", "id BIGSERIAL PRIMARY KEY"
)

APP_COLUMNS = [
    "id",
    "project_name",
    "service_name",
    "display_name",
    "language",
    "runtime_version",
    "sdk_version",
    "first_seen",
    "last_seen",
    "metadata_json",
]


def _is_postgres_url(value: str) -> bool:
    return value.startswith(("postgres://", "postgresql://"))


def _translate_sql(sql: str) -> str:
    translated = sql.replace("?", "%s")
    translated = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO\s+(.+?)\s+VALUES", r"INSERT INTO \1 VALUES", translated, flags=re.I | re.S)
    if re.search(r"INSERT\s+INTO\s+", translated, flags=re.I) and "ON CONFLICT" not in translated.upper():
        translated += " ON CONFLICT DO NOTHING"
    return translated


class PostgresCursor:
    def __init__(self, cursor: Any):
        self.cursor = cursor

    @property
    def rowcount(self) -> int:
        return self.cursor.rowcount

    def fetchone(self) -> Any:
        return self.cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self.cursor.fetchall()


class PostgresConnection:
    def __init__(self, conn: Any):
        self.conn = conn

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> PostgresCursor:
        cursor = self.conn.execute(_translate_sql(sql), params or ())
        return PostgresCursor(cursor)

    def executescript(self, script: str) -> None:
        for statement in [part.strip() for part in script.split(";") if part.strip()]:
            self.conn.execute(_translate_sql(statement))

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


class Database:
    def __init__(self, path_or_url: str | Path):
        self.url = str(path_or_url)
        self.is_postgres = _is_postgres_url(self.url)
        if not self.is_postgres:
            self.path = Path(path_or_url)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            raw_conn = psycopg.connect(self.url, row_factory=dict_row)
            conn: Any = PostgresConnection(raw_conn)
        else:
            # Self-heal: if the SQLite file is missing or empty (e.g. deleted out
            # from under us in tests or dev), re-apply the schema. We don't run
            # _apply_schema on every connect anymore because the migration check
            # is expensive when multiplied across every API request.
            needs_init = not self.path.exists() or self.path.stat().st_size == 0
            conn = sqlite3.connect(self.path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000")
            if needs_init:
                self._apply_schema(conn)
                conn.execute("ANALYZE")
                conn.commit()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            raw_conn = psycopg.connect(self.url, row_factory=dict_row)
            conn: Any = PostgresConnection(raw_conn)
            try:
                self._apply_schema(conn)
                conn.commit()
            finally:
                conn.close()
            return
        with sqlite3.connect(self.path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000")
            self._apply_schema(conn)
            # Populate query planner statistics so SQLite picks the right indexes
            # for aggregations on events/logs (otherwise it falls back to scanning
            # the wrong index, e.g. idx_events_trace for kind GROUP BYs).
            conn.execute("ANALYZE")
            conn.commit()

    def optimize(self) -> None:
        """Refresh query planner stats. Cheap incremental analyze."""
        if self.is_postgres:
            with self.connect() as conn:
                conn.execute("ANALYZE")
            return
        with self.connect() as conn:
            conn.execute("PRAGMA optimize")

    def _apply_schema(self, conn: Any) -> None:
        if self.is_postgres:
            conn.executescript(POSTGRES_SCHEMA)
            self._apply_postgres_column_migrations(conn)
            return
        self._migrate_apps_unique_service_name(conn)
        conn.executescript(SQLITE_SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(apps)").fetchall()}
        if "project_name" not in columns:
            conn.execute("ALTER TABLE apps ADD COLUMN project_name TEXT")
        if "display_name" not in columns:
            conn.execute("ALTER TABLE apps ADD COLUMN display_name TEXT")

    def _apply_postgres_column_migrations(self, conn: Any) -> None:
        conn.execute("ALTER TABLE apps ADD COLUMN IF NOT EXISTS project_name TEXT")
        conn.execute("ALTER TABLE apps ADD COLUMN IF NOT EXISTS display_name TEXT")

    def _migrate_apps_unique_service_name(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='apps'").fetchone()
        create_sql = str(row[0]) if row and row[0] else ""
        if "service_name TEXT NOT NULL UNIQUE" not in create_sql:
            return

        columns = {column[1] for column in conn.execute("PRAGMA table_info(apps)").fetchall()}
        select_parts = []
        for column in APP_COLUMNS:
            if column in columns:
                select_parts.append(column)
            elif column == "project_name":
                select_parts.append("'default' AS project_name")
            elif column == "display_name":
                select_parts.append("service_name AS display_name")
            else:
                select_parts.append(f"NULL AS {column}")

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE apps RENAME TO apps_legacy_unique_service_name")
        conn.execute(
            """
            CREATE TABLE apps (
              id TEXT PRIMARY KEY, project_name TEXT, service_name TEXT NOT NULL, display_name TEXT, language TEXT,
              runtime_version TEXT, sdk_version TEXT, first_seen TEXT NOT NULL,
              last_seen TEXT NOT NULL, metadata_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            f"INSERT OR REPLACE INTO apps({', '.join(APP_COLUMNS)}) SELECT {', '.join(select_parts)} FROM apps_legacy_unique_service_name"
        )
        conn.execute("DROP TABLE apps_legacy_unique_service_name")

    def clear(self) -> None:
        tables = ["events", "apps", "routes", "route_durations", "traces", "spans", "exceptions", "logs", "dependencies", "dependency_durations", "route_metrics_hourly", "dependency_metrics_hourly", "log_metrics_hourly", "llm_usage", "user_preferences", "project_api_keys", "retention_pins"]
        with self.connect() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
