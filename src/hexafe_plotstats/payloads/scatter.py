from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..models.common import ScatterConfig
from ..models.payloads import ScatterPayload
from ._common import paired_finite_arrays
from ..policies.scatter_mode import resolve_alpha, resolve_marker_size, resolve_scatter_mode


def build_scatter_payload(
    x: Iterable[Any],
    y: Iterable[Any],
    config: ScatterConfig | None = None,
) -> ScatterPayload:
    config = config or ScatterConfig()
    x_values, y_values = paired_finite_arrays(x, y)

    count = int(x_values.size)
    mode = resolve_scatter_mode(config, count)
    marker_size = resolve_marker_size(config, count)
    alpha = resolve_alpha(config, count)
    rasterized = mode == "scatter_rasterized"
    simplified_annotations = count >= config.simplified_annotation_threshold

    return ScatterPayload(
        x=tuple(float(value) for value in x_values),
        y=tuple(float(value) for value in y_values),
        mode=mode,
        marker_size=marker_size,
        alpha=alpha,
        rasterized=rasterized,
        edgecolors=config.edgecolors,
        gridsize=config.gridsize,
        include_trend=config.include_trend,
        simplified_annotations=simplified_annotations,
    )
