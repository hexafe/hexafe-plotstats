from __future__ import annotations

import numpy as np

from ...models.payloads import IQRPayload
from ...models.render import RenderResult
from ...specs import iqr_payload_to_resolved_spec
from .._common import apply_resolved_layout, style_spec_limits_y


def render_iqr_matplotlib(payload: IQRPayload) -> RenderResult:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    resolved = iqr_payload_to_resolved_spec(payload)
    data = [np.asarray(group.values, dtype=float) for group in payload.groups]
    positions = np.arange(1, len(data) + 1)
    whis = float(payload.metadata.get("whis", 1.5))
    showfliers = bool(payload.metadata.get("showfliers", True))

    if data:
        bp = ax.boxplot(
            data,
            positions=positions,
            whis=whis,
            showfliers=showfliers,
            widths=0.55,
            patch_artist=True,
        )
        for box in bp["boxes"]:
            box.set_facecolor("tab:blue")
            box.set_alpha(0.6)
        for line in bp["medians"]:
            line.set_color("tab:orange")

    style_spec_limits_y(ax, payload.spec_limits)
    ax.set_xticks(positions, [group.label for group in payload.groups])
    ax.set_xlabel("group")
    ax.set_ylabel("value")
    apply_resolved_layout(fig, ax, resolved)
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "iqr", "metadata": payload.metadata})
