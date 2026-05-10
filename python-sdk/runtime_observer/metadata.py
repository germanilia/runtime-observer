from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from typing import Any

COMMON_PACKAGES = ("fastapi", "starlette", "flask", "django", "sqlalchemy", "requests", "httpx", "litellm", "loguru")


def _git_value(args: list[str]) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=Path.cwd(), capture_output=True, text=True, timeout=1, check=False)
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def collect_app_metadata() -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "cwd": str(Path.cwd()),
        "environment": os.getenv("RUNTIME_OBSERVER_ENVIRONMENT"),
        "container": {"docker": Path("/.dockerenv").exists(), "kubernetes": bool(os.getenv("KUBERNETES_SERVICE_HOST"))},
        "git": {"branch": _git_value(["rev-parse", "--abbrev-ref", "HEAD"]), "commit": _git_value(["rev-parse", "HEAD"])},
        "frameworks": {},
    }
    for package in COMMON_PACKAGES:
        try:
            metadata["frameworks"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    return metadata


def collect_dependency_inventory() -> dict[str, Any]:
    installed = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if name:
            installed.append({"name": name, "version": dist.version})
    installed.sort(key=lambda item: item["name"].lower())
    files = []
    for filename in ("pyproject.toml", "requirements.txt", "requirements.lock", "poetry.lock", "uv.lock"):
        path = Path.cwd() / filename
        if path.exists():
            files.append({"path": filename, "size": path.stat().st_size})
    return {"dependencies": installed[:500], "dependency_count": len(installed), "files": files}
