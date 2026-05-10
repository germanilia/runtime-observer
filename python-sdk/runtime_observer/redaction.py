from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

SECRET_KEY_RE = re.compile(r"password|passwd|secret|token|api[_-]?key|apikey|authorization|cookie|set-cookie|credential|private[_-]?key|access[_-]?key|refresh[_-]?token|id[_-]?token", re.I)
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}")
AWS_KEY_RE = re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b")
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I)
PEM_RE = re.compile(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.S)
LONG_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")
KEY_VALUE_SECRET_RE = re.compile(r"\b(password|passwd|secret|token|api[_-]?key|apikey|authorization|cookie|credential|private[_-]?key|access[_-]?key|refresh[_-]?token|id[_-]?token)\s*[:=]\s*([^\s,;]+)", re.I)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(slots=True)
class RedactionConfig:
    max_string_length: int = 512
    max_depth: int = 3
    max_keys: int = 25


def stable_hash(value: Any) -> str:
    raw = str(value).encode("utf-8", errors="ignore")
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    return -sum((count / len(value)) * math.log2(count / len(value)) for count in counts.values())


def redact_string(value: str, *, max_length: int = 512) -> str:
    redacted = PEM_RE.sub("<redacted:pem>", str(value))
    redacted = BEARER_RE.sub("Bearer <redacted:token>", redacted)
    redacted = JWT_RE.sub("<redacted:jwt>", redacted)
    redacted = AWS_KEY_RE.sub("<redacted:aws_access_key>", redacted)
    redacted = LONG_B64_RE.sub(lambda m: "<redacted:high_entropy>" if _entropy(m.group(0)) > 4.0 else m.group(0), redacted)
    redacted = KEY_VALUE_SECRET_RE.sub(lambda m: f"{m.group(1)}=<redacted>", redacted)
    if len(redacted) > max_length:
        redacted = redacted[:max_length] + "…<truncated>"
    return redacted


redact_text = redact_string


def classify_value(value: Any) -> str | None:
    if isinstance(value, str) and EMAIL_RE.match(value):
        return "email"
    if isinstance(value, str) and (JWT_RE.search(value) or BEARER_RE.search(value) or AWS_KEY_RE.search(value)):
        return "secret"
    return None


def summarize_value(value: Any, *, name: str | None = None, config: RedactionConfig | None = None, depth: int = 0) -> Any:
    config = config or RedactionConfig()
    if name and SECRET_KEY_RE.search(name):
        return {"type": type(value).__name__, "value": "<redacted:secret>", "hash": stable_hash(value), "length": len(str(value))}
    if depth >= config.max_depth:
        return {"type": type(value).__name__, "value": "<max-depth>"}
    if value is None or isinstance(value, bool | int | float):
        return {"type": type(value).__name__, "value": value}
    if isinstance(value, str):
        classification = classify_value(value)
        if classification in {"email", "secret"}:
            return {"type": "str", "classification": classification, "value": f"<redacted:{classification}>", "length": len(value), "hash": stable_hash(value)}
        return {"type": "str", "value": redact_string(value, max_length=config.max_string_length), "length": len(value)}
    if isinstance(value, Mapping):
        items = list(value.items())[: config.max_keys]
        return {"type": type(value).__name__, "size": len(value), "keys": [redact_string(str(key), max_length=64) for key, _ in items], "items": {redact_string(str(key), max_length=64): summarize_value(val, name=str(key), config=config, depth=depth + 1) for key, val in items}}
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        values = list(value)[: config.max_keys]
        return {"type": type(value).__name__, "size": len(value), "items": [summarize_value(item, config=config, depth=depth + 1) for item in values]}
    return {"type": type(value).__name__, "value": redact_string(repr(value), max_length=config.max_string_length)}


def redact_value(value: Any, key: str | None = None) -> Any:
    if key and SECRET_KEY_RE.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(k): redact_value(v, str(k)) for k, v in list(value.items())[:25]}
    if isinstance(value, str):
        redacted = redact_string(value).replace("Bearer <redacted:token>", "Bearer <redacted>")
        if redacted != value or len(value) > 80:
            return {"type": "str", "length": len(value), "hash": stable_hash(value), "value": redacted if redacted != value else "<truncated>"}
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return [redact_value(item) for item in list(value)[:25]]
    return value


def safe_value(key: str | None, value: Any, depth: int = 0) -> Any:
    if key and SECRET_KEY_RE.search(key):
        return "<redacted>"
    return redact_value(value, key)


def redact_mapping(value: Mapping[str, Any], *, config: RedactionConfig | None = None) -> dict[str, Any]:
    return {str(k): redact_value(v, str(k)) for k, v in list(value.items())[: (config.max_keys if config else 25)]}


def summarize_params(values: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): summarize_value(v, name=str(k)) for k, v in list(values.items())[:25]}
