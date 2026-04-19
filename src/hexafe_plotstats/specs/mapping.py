from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def to_mapping(value: Any) -> Any:
    """Return only Python primitives, lists, and dictionaries."""

    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_mapping(getattr(value, field.name))
            for field in fields(value)
        }

    if isinstance(value, dict):
        return {str(key): to_mapping(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [to_mapping(item) for item in value]

    if isinstance(value, Enum):
        return to_mapping(value.value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, bool) or value is None:
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, str):
        return value

    return str(value)


def asdict(value: Any) -> Any:
    """Alias for callers that expect a dataclasses-style helper name."""

    return to_mapping(value)
