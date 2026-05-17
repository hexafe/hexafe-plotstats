from __future__ import annotations

import numpy as np

from ...models.payloads import ScatterPayload
from ...models.render import RenderResult
from ...specs import scatter_payload_to_resolved_spec
from .._common import apply_resolved_layout


def render_scatter_matplotlib(payload: ScatterPayload) -> RenderResult:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    fig, ax = plt.subplots()
    x = np.asarray(payload.x, dtype=float)
    y = np.asarray(payload.y, dtype=float)
    resolved = scatter_payload_to_resolved_spec(payload)

    if payload.mode == "hexbin":
        for cell in resolved.hex_cells:
            ax.add_patch(
                Polygon(
                    cell.points,
                    closed=True,
                    facecolor=cell.fill,
                    edgecolor=cell.stroke,
                    alpha=cell.opacity,
                    linewidth=0.35,
                )
            )
    else:
        ax.scatter(
            x,
            y,
            s=payload.marker_size,
            alpha=payload.alpha,
            edgecolors=payload.edgecolors,
            rasterized=payload.rasterized,
        )
        if resolved.trend_line is not None:
            line = resolved.trend_line
            ax.plot(
                [line.x0, line.x1],
                [line.y0, line.y1],
                color=line.stroke,
                linewidth=1.1,
                alpha=0.35,
                linestyle="--",
                label=line.label,
            )

    for line in resolved.reference_lines:
        ax.hlines(
            line.y0,
            line.x0,
            line.x1,
            color=line.stroke,
            linewidth=line.stroke_width,
            linestyle="--",
            label=line.label,
            zorder=3,
        )
        ax.annotate(
            f"{line.label}={line.y0:.4g}",
            xy=(line.x1, line.y0),
            xytext=(-4, 0),
            textcoords="offset points",
            va="center",
            ha="right",
            fontsize=8,
            color=line.stroke,
        )

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    apply_resolved_layout(fig, ax, resolved)
    if resolved.trend_line is not None or resolved.reference_lines:
        ax.legend(loc="best")
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "scatter", "mode": payload.mode})
