from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[0:1] in {"'", '"'} and value[-1:] == value[0]:
        return value[1:-1]
    return value


def load_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(errors="ignore").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            key = line[:-1].strip()
            current = {}
            data[key] = current
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        target = current if raw_line.startswith(" ") and current is not None else data
        target[key.strip()] = _parse_scalar(value)
    return data


def sqlite_path_from_url(value: str) -> Path:
    if not value:
        return Path("runtime_observer.sqlite3")
    if value.startswith("sqlite:///"):
        parsed = urlparse(value)
        path = unquote(parsed.path)
        if path.startswith("//"):
            path = path[1:]
        return Path(path)
    if value.startswith("sqlite://"):
        parsed = urlparse(value)
        path = unquote(parsed.path.lstrip("/"))
        return Path(path or "runtime_observer.sqlite3")
    return Path(value)
