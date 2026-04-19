from __future__ import annotations

from typing import Literal


RendererBackend = Literal["matplotlib", "rust"]


class RendererBackendUnavailable(RuntimeError):
    """Raised when a selected renderer backend is not installed or not wired yet."""

