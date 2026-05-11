from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import os
from pathlib import Path

_LOG_LEVEL_ORDER = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_LOG_LEVEL_RANK = {level: index for index, level in enumerate(_LOG_LEVEL_ORDER)}


class CaptureMode(StrEnum):
    DEV = "dev"
    PROD = "prod"
    OFF = "off"


@dataclass(slots=True)
class RuntimeObserverConfig:
    api_key: str | None = None
    endpoint: str = "http://127.0.0.1:4319"
    project_name: str | None = None
    service_name: str | None = None
    display_name: str | None = None
    environment: str = "development"
    enabled: bool = True
    capture_mode: CaptureMode = CaptureMode.DEV
    batch_size: int = 100
    flush_interval_seconds: float = 2.0
    max_queue_size: int = 1000
    max_event_size_bytes: int = 64 * 1024
    max_string_length: int = 512
    max_parameter_depth: int = 3
    max_object_keys: int = 25
    capture_logs: bool = True
    capture_db_query_values: bool = True
    db_query_max_length: int = 8192
    log_levels: set[str] = field(default_factory=lambda: {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
    log_message_max_length: int = 2048
    log_rate_limit_per_minute: int = 120
    debug_schema_validation: bool = False
    insecure_local_dev: bool = False

    @property
    def exporting_enabled(self) -> bool:
        if not self.enabled or self.capture_mode == CaptureMode.OFF:
            return False
        if not self.project_name:
            return False
        return bool(self.api_key) or self.insecure_local_dev


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_log_levels(value: object | None) -> set[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parts = [part.strip().upper() for part in value.replace(";", ",").split(",") if part.strip()]
    elif isinstance(value, (set, list, tuple)):
        parts = [str(part).strip().upper() for part in value if str(part).strip()]
    else:
        parts = [str(value).strip().upper()]
    selected = {part for part in parts if part in _LOG_LEVEL_RANK}
    return selected or None


def _levels_at_or_above(value: object | None) -> set[str] | None:
    levels = _parse_log_levels(value)
    if not levels:
        return None
    minimum = min(_LOG_LEVEL_RANK[level] for level in levels)
    return {level for level in _LOG_LEVEL_ORDER if _LOG_LEVEL_RANK[level] >= minimum}


def _service_name(default: str | None = None) -> str:
    if default:
        return default
    env_name = os.getenv("RUNTIME_OBSERVER_SERVICE_NAME")
    if env_name:
        return env_name
    pyproject = Path.cwd() / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(errors="ignore").splitlines():
            if line.strip().startswith("name") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"\'')
    return Path.cwd().name or "python-service"


def resolve_config(**overrides: object) -> RuntimeObserverConfig:
    mode = str(overrides.get("capture_mode") or os.getenv("RUNTIME_OBSERVER_CAPTURE_MODE") or "dev").lower()
    if mode not in {"dev", "prod", "off"}:
        mode = "dev"
    environment = str(overrides.get("environment") or os.getenv("RUNTIME_OBSERVER_ENVIRONMENT") or ("production" if mode == "prod" else "development"))
    config = RuntimeObserverConfig(
        api_key=overrides.get("api_key") if "api_key" in overrides else os.getenv("RUNTIME_OBSERVER_API_KEY"),
        endpoint=str(overrides.get("endpoint") or os.getenv("RUNTIME_OBSERVER_ENDPOINT") or overrides.get("default_endpoint") or "http://127.0.0.1:4319"),
        project_name=str(overrides.get("project_name") or os.getenv("RUNTIME_OBSERVER_PROJECT_NAME") or "") or None,
        service_name=_service_name(overrides.get("service_name") if isinstance(overrides.get("service_name"), str) else None),
        display_name=str(overrides.get("display_name") or os.getenv("RUNTIME_OBSERVER_DISPLAY_NAME") or overrides.get("app_name") or os.getenv("RUNTIME_OBSERVER_APP_NAME") or "") or None,
        environment=environment,
        enabled=_bool(str(overrides["enabled"]) if "enabled" in overrides else os.getenv("RUNTIME_OBSERVER_ENABLED"), True),
        capture_mode=CaptureMode(mode),
        batch_size=_int(str(overrides["batch_size"]) if "batch_size" in overrides else os.getenv("RUNTIME_OBSERVER_BATCH_SIZE"), 100),
        flush_interval_seconds=_float(str(overrides["flush_interval_seconds"]) if "flush_interval_seconds" in overrides else os.getenv("RUNTIME_OBSERVER_FLUSH_INTERVAL_SECONDS"), 2.0),
        max_queue_size=_int(str(overrides["max_queue_size"]) if "max_queue_size" in overrides else os.getenv("RUNTIME_OBSERVER_MAX_QUEUE_SIZE"), 1000),
        capture_logs=_bool(str(overrides["capture_logs"]) if "capture_logs" in overrides else os.getenv("RUNTIME_OBSERVER_CAPTURE_LOGS"), True),
        capture_db_query_values=_bool(str(overrides["capture_db_query_values"]) if "capture_db_query_values" in overrides else os.getenv("RUNTIME_OBSERVER_CAPTURE_DB_QUERY_VALUES"), mode != "prod"),
        db_query_max_length=_int(str(overrides["db_query_max_length"]) if "db_query_max_length" in overrides else os.getenv("RUNTIME_OBSERVER_DB_QUERY_MAX_LENGTH"), 8192),
        log_message_max_length=_int(str(overrides["log_message_max_length"]) if "log_message_max_length" in overrides else os.getenv("RUNTIME_OBSERVER_LOG_MESSAGE_MAX_LENGTH"), 2048),
        insecure_local_dev=_bool(str(overrides["insecure_local_dev"]) if "insecure_local_dev" in overrides else os.getenv("RUNTIME_OBSERVER_INSECURE_LOCAL_DEV"), False),
    )
    configured_levels = _parse_log_levels(overrides.get("log_levels") if "log_levels" in overrides else os.getenv("RUNTIME_OBSERVER_LOG_LEVELS"))
    configured_min_level = _levels_at_or_above(overrides.get("log_level") if "log_level" in overrides else os.getenv("RUNTIME_OBSERVER_LOG_LEVEL"))
    if configured_levels:
        config.log_levels = configured_levels
    elif configured_min_level:
        config.log_levels = configured_min_level
    elif mode == "prod":
        config.log_levels = {"INFO", "WARNING", "ERROR", "CRITICAL"}
    if mode == "prod" and "capture_db_query_values" not in overrides and os.getenv("RUNTIME_OBSERVER_CAPTURE_DB_QUERY_VALUES") is None:
        config.capture_db_query_values = False
    return config
