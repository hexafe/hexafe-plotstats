from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RenderResult:
    fig: Any
    ax: Any
    metadata: dict[str, Any] = field(default_factory=dict)

