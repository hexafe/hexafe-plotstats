from __future__ import annotations

import numpy as np

from ...models.payloads import HistogramPayload
from ...models.render import RenderResult
from .._common import style_spec_limits


def render_histogram_matplotlib(payload: HistogramPayload) -> RenderResult:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    edges = np.asarray(payload.bin_edges, dtype=float)
    heights = np.asarray(payload.bin_values, dtype=float)

    if edges.size >= 2 and heights.size:
        widths = np.diff(edges)
        ax.bar(edges[:-1], heights, width=widths, align="edge", alpha=0.8, color="tab:blue")

    if payload.fit and payload.fit.curve is not None:
        ax.plot(payload.fit.curve.x, payload.fit.curve.y, color="tab:orange", linewidth=1.5)
    if payload.fit and payload.fit.kde_reference is not None:
        ax.plot(payload.fit.kde_reference.x, payload.fit.kde_reference.y, color="tab:gray", linewidth=1.0, linestyle="--")

    style_spec_limits(ax, payload.spec_limits)
    ax.set_ylabel("density" if payload.density else "count")
    ax.set_xlabel("value")
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "histogram", "warnings": payload.warnings})

