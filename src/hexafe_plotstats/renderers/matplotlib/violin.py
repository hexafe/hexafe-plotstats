from __future__ import annotations

import numpy as np

from ...models.payloads import ViolinPayload
from ...models.render import RenderResult
from .._common import style_spec_limits


def render_violin_matplotlib(payload: ViolinPayload) -> RenderResult:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    data = [np.asarray(group.values, dtype=float) for group in payload.groups]
    positions = np.arange(1, len(data) + 1)

    if data:
        parts = ax.violinplot(data, positions=positions, showmeans=False, showextrema=False, showmedians=False)
        for body in parts["bodies"]:
            body.set_facecolor("tab:blue")
            body.set_alpha(0.75)

        show_mean = bool(payload.metadata.get("show_mean", True))
        show_quartiles = bool(payload.metadata.get("show_quartiles", True))
        show_extrema = bool(payload.metadata.get("show_extrema", True))

        for position, group in zip(positions, payload.groups):
            if show_mean and group.summary.mean is not None:
                ax.scatter([position], [group.summary.mean], color="black", s=12, zorder=3)
            if show_quartiles:
                if group.summary.q1 is not None:
                    ax.hlines(group.summary.q1, position - 0.12, position + 0.12, color="tab:orange", linewidth=1.2, zorder=3)
                if group.summary.median is not None:
                    ax.scatter([position], [group.summary.median], color="tab:orange", s=12, zorder=3)
                if group.summary.q3 is not None:
                    ax.hlines(group.summary.q3, position - 0.12, position + 0.12, color="tab:orange", linewidth=1.2, zorder=3)
            if show_extrema and group.summary.minimum is not None and group.summary.maximum is not None:
                ax.vlines(position, group.summary.minimum, group.summary.maximum, color="tab:gray", linewidth=1, alpha=0.8)

    style_spec_limits(ax, payload.spec_limits)
    ax.set_xticks(positions, [group.label for group in payload.groups])
    ax.set_xlabel("group")
    ax.set_ylabel("value")
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "violin", "metadata": payload.metadata})
