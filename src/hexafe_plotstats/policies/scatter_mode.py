from __future__ import annotations

from ..models.common import ScatterConfig, ScatterMode


def resolve_scatter_mode(config: ScatterConfig | None, count: int) -> ScatterMode:
    config = config or ScatterConfig()
    mode = config.mode
    if mode != "auto":
        return mode
    if count >= config.hexbin_threshold:
        return "hexbin"
    if count >= config.rasterized_threshold:
        return "scatter_rasterized"
    return "scatter"


def resolve_marker_size(config: ScatterConfig | None, count: int) -> float:
    config = config or ScatterConfig()
    if config.marker_size is not None:
        return float(config.marker_size)
    return 12.0 if count < 1_000 else 6.0


def resolve_alpha(config: ScatterConfig | None, count: int) -> float:
    config = config or ScatterConfig()
    if config.alpha is not None:
        return float(config.alpha)
    return 0.75 if count < 10_000 else 0.35

