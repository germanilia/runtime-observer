from __future__ import annotations

from typing import Any

from . import init_runtime_observer, RuntimeObserver


def init_from_env(app: Any | None = None, **kwargs: Any) -> RuntimeObserver:
    observer = init_runtime_observer.from_env(**kwargs)
    if app is not None:
        observer.instrument_fastapi(app)
    return observer
