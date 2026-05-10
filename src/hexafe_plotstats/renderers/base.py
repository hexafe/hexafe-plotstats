from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RendererBackend = Literal["matplotlib", "rust"]
NativeRendererBackend = Literal["rust"]


@dataclass(frozen=True)
class RendererBackendCapability:
    backend: str
    available: bool
    default: bool
    message: str = ""


class RendererBackendUnavailable(RuntimeError):
    """Raised when a selected renderer backend is not installed or not wired yet."""
