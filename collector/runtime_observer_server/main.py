from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .api import create_router, session_user
from .config import Settings
from .db import Database
from .store import CollectorStore


def _requires_session(path: str) -> bool:
    if path.startswith("/api/auth/") or path.startswith("/api/admin/"):
        return False
    return path.startswith("/api/") or path in {"/docs", "/redoc", "/openapi.json"}


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    database = Database(resolved.database_url or resolved.database_path)
    store = CollectorStore(database)
    store.cleanup(
        resolved.retention_days,
        min_log_minutes=resolved.retention_min_log_minutes,
        exception_window_minutes=resolved.retention_exception_window_minutes,
    )

    app = FastAPI(title="Runtime Observer Collector", version="0.1.0")
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
    )
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
