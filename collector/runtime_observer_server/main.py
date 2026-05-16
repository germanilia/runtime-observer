from __future__ import annotations

import argparse
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .api import create_router, session_user
from .config import Settings
from .db import Database
from .ingest_queue import build_ingest_backend
from .store import CollectorStore

LOGGER = logging.getLogger(__name__)

def _requires_session(path: str) -> bool:
    if path.startswith("/api/auth/") or path.startswith("/api/admin/"):
        return False
    return path.startswith("/api/") or path in {"/docs", "/redoc", "/openapi.json"}


async def _cleanup_loop(app_state: Any, settings: Settings) -> None:
    while True:
        await asyncio.sleep(max(30, settings.cleanup_interval_seconds))
        try:
            await asyncio.to_thread(
                app_state.store.cleanup,
                settings.retention_days,
                min_log_minutes=settings.retention_min_log_minutes,
                exception_window_minutes=settings.retention_exception_window_minutes,
                raw_event_retention_hours=settings.raw_event_retention_hours,
                regular_log_retention_hours=settings.regular_log_retention_hours,
                trace_retention_days=settings.trace_retention_days,
                duration_retention_days=settings.duration_retention_days,
                exception_retention_days=settings.exception_retention_days,
                aggregate_retention_days=settings.aggregate_retention_days,
            )
        except Exception:
            LOGGER.exception("retention cleanup failed")
            continue


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    database = Database(resolved.database_url or resolved.database_path)
    store = CollectorStore(database)
    ingest_backend = build_ingest_backend(store, resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ingest_backend.start()
        cleanup_task = asyncio.create_task(_cleanup_loop(app.state, resolved))
        try:
            yield
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            ingest_backend.stop()

    app = FastAPI(title="Runtime Observer Collector", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = resolved
    app.state.database = database
    app.state.store = store
    app.state.ingest_backend = ingest_backend

    @app.middleware("http")
    async def dashboard_session_auth(request: Request, call_next):
        if not resolved.insecure_dev_mode and _requires_session(request.url.path):
            if not session_user(request, database):
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return await call_next(request)

    app.include_router(create_router())
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Runtime Observer local collector")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--api-key", default=None, help="Legacy collector-wide ingest key. Prefer project keys generated in the UI.")
    parser.add_argument("--secrets", default=None, help="Path to secrets.yml containing the database connection string.")
    parser.add_argument("--db", default=None, help="Override database URL/path for local development.")
    parser.add_argument("--insecure-dev", action="store_true")
    parser.add_argument("--retention-days", type=int, default=None)
    args = parser.parse_args()

    env = Settings.from_env()
    settings = Settings(
        host=args.host or env.host,
        port=args.port or env.port,
        api_key=args.api_key or env.api_key,
        dashboard_username=env.dashboard_username,
        dashboard_password=env.dashboard_password,
        database_path=Path(args.db) if args.db and not args.db.startswith(("postgres://", "postgresql://")) else env.database_path,
        database_url=args.db or env.database_url,
        secrets_path=Path(args.secrets) if args.secrets else env.secrets_path,
        insecure_dev_mode=args.insecure_dev or env.insecure_dev_mode,
        retention_days=args.retention_days or env.retention_days,
        retention_min_log_minutes=env.retention_min_log_minutes,
        retention_exception_window_minutes=env.retention_exception_window_minutes,
        raw_event_retention_hours=env.raw_event_retention_hours,
        regular_log_retention_hours=env.regular_log_retention_hours,
        trace_retention_days=env.trace_retention_days,
        duration_retention_days=env.duration_retention_days,
        exception_retention_days=env.exception_retention_days,
        aggregate_retention_days=env.aggregate_retention_days,
        cleanup_interval_seconds=env.cleanup_interval_seconds,
        ingest_queue_backend=env.ingest_queue_backend,
        ingest_queue_max_batches=env.ingest_queue_max_batches,
        ingest_worker_batch_size=env.ingest_worker_batch_size,
        ingest_worker_flush_interval_seconds=env.ingest_worker_flush_interval_seconds,
        sqs_queue_url=env.sqs_queue_url,
        sqs_endpoint_url=env.sqs_endpoint_url,
        aws_region=env.aws_region,
    )
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
