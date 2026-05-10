"""Minimal FastAPI app for Runtime Observer SDK + collector validation."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("runtime_observer.example.fastapi")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="Runtime Observer FastAPI Minimal")


def _try_install_runtime_observer(application: FastAPI) -> None:
    """Install the SDK if it is available, otherwise keep the sample runnable."""
    if os.getenv("RUNTIME_OBSERVER_ENABLED", "true").lower() == "false":
        logger.info("runtime observer disabled by environment")
        return

    try:
        from runtime_observer import init_runtime_observer  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("runtime_observer SDK is not installed; running without instrumentation")
        return

    observer = init_runtime_observer.from_env(
        service_name="python-fastapi-minimal",
        default_endpoint="http://127.0.0.1:4319",
    )
    observer.instrument_fastapi(application)
    logger.info("runtime observer instrumentation installed")


_try_install_runtime_observer(app)


class Item(BaseModel):
    item_id: int
    name: str
    source: str


@app.on_event("startup")
def setup_database() -> None:
    db_path = _database_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("INSERT OR IGNORE INTO items (id, name) VALUES (?, ?)", (1, "demo-widget"))
    logger.info("sample database ready", extra={"db_path": str(db_path)})


@app.get("/health")
def health() -> dict[str, str]:
    logger.info("health check handled")
    return {"status": "ok"}


@app.get("/items/{item_id}", response_model=Item)
def read_item(item_id: int) -> Item:
    logger.info("loading item", extra={"item_id": item_id})
    with sqlite3.connect(_database_path()) as conn:
        row = conn.execute("SELECT id, name FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        logger.warning("item not found", extra={"item_id": item_id})
        raise HTTPException(status_code=404, detail="item not found")
    return Item(item_id=row[0], name=row[1], source="sqlite")


@app.get("/outbound")
def outbound() -> dict[str, Any]:
    logger.info("making outbound http call")
    with httpx.Client(timeout=5.0) as client:
        response = client.get("https://httpbin.org/status/204")
    return {"host": "httpbin.org", "status_code": response.status_code}


@app.get("/boom")
def boom() -> dict[str, str]:
    logger.error("about to raise sample exception")
    raise RuntimeError("sample runtime observer exception")


@app.post("/llm-simulated")
def llm_simulated(prompt_size: int = 42) -> dict[str, Any]:
    logger.info("simulated llm call", extra={"prompt_size": prompt_size, "prompt": "<redacted>"})
    return {
        "provider": "simulated",
        "model": "example-model",
        "prompt_size": prompt_size,
        "response_size": 17,
    }


def _database_path() -> Path:
    configured = os.getenv("RUNTIME_OBSERVER_EXAMPLE_DB")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "example.sqlite3"
