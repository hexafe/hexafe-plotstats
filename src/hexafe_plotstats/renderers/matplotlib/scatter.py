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
        if payload.include_trend and x.size > 1:
            slope, intercept = np.polyfit(x, y, 1)
            xx = np.linspace(float(np.min(x)), float(np.max(x)), 2)
            ax.plot(xx, slope * xx + intercept, color="tab:orange", linewidth=1.25)

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    apply_resolved_layout(fig, ax, resolved)
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "scatter", "mode": payload.mode})
