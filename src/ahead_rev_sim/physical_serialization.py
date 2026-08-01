"""Canonical JSON and SHA-256 helpers for physical-compute artifacts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping


def jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    return value


def sha256_json(value: Any) -> str:
    payload = json.dumps(
        jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def blocker_code(message: str) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in message)
    normalized = "_".join(part for part in normalized.upper().split("_") if part)
    return normalized[:96] or "SUBSTRATE_EXECUTION_REFUSED"
