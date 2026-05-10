from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 4319
    api_key: str = "local-dev-key"
    dashboard_username: str = "admin"
    dashboard_password: str = "local-dev-key"
    database_path: Path = Path("runtime_observer.sqlite3")
    insecure_dev_mode: bool = False
    retention_days: int = 7

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("RUNTIME_OBSERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("RUNTIME_OBSERVER_PORT", "4319")),
            api_key=os.getenv("RUNTIME_OBSERVER_API_KEY", "local-dev-key"),
            dashboard_username=os.getenv("RUNTIME_OBSERVER_DASHBOARD_USERNAME", "admin"),
            dashboard_password=os.getenv("RUNTIME_OBSERVER_DASHBOARD_PASSWORD", os.getenv("RUNTIME_OBSERVER_API_KEY", "local-dev-key")),
            database_path=Path(os.getenv("RUNTIME_OBSERVER_DB", "runtime_observer.sqlite3")),
            insecure_dev_mode=os.getenv("RUNTIME_OBSERVER_INSECURE_DEV", "false").lower() in {"1", "true", "yes"},
            retention_days=int(os.getenv("RUNTIME_OBSERVER_RETENTION_DAYS", "7")),
        )
