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

        for marker in resolved.annotation_markers:
            color = marker.fill or marker.stroke or "black"
            symbol = "D" if marker.kind == "mean" else "_"
            ax.scatter([marker.x], [marker.y], color=color, marker=symbol, s=max(marker.size * 8.0, 16.0), zorder=3)
            if marker.kind in {"mean", "minimum", "maximum"}:
                label = {"minimum": "min", "maximum": "max"}.get(marker.kind, marker.kind)
                y_offset = {"minimum": -8, "mean": 8, "maximum": 8}.get(marker.kind, 0)
                _annotate_value(ax, marker.x, marker.y, label, color, y_offset=y_offset)

        for line in resolved.spec_lines:
            if line.kind.startswith("sigma_"):
                ax.hlines(line.y0, line.x0, line.x1, color=line.stroke, linewidth=line.stroke_width, linestyle="--", zorder=3)
                _annotate_value(ax, line.x1, line.y0, line.label, line.stroke, x_offset=5)

    style_spec_limits_y(ax, payload.spec_limits)
    ax.set_xticks(positions, [group.label for group in payload.groups])
    ax.set_xlabel("group")
    ax.set_ylabel("value")
    apply_resolved_layout(fig, ax, resolved)
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "iqr", "metadata": payload.metadata})


def _annotate_value(
    ax,
    x_value: float,
    y_value: float | None,
    label: str,
    color: str,
    *,
    x_offset: int = 4,
    y_offset: int = 0,
) -> None:
    if y_value is None:
        return
    try:
        number = float(y_value)
    except (TypeError, ValueError):
        return
    if not np.isfinite(number):
        return
    ax.annotate(
        f"{label}={_format_annotation_number(number)}",
        xy=(x_value, number),
        xytext=(x_offset, y_offset),
        textcoords="offset points",
        va="center",
        ha="left",
        fontsize=7,
        color=color,
        zorder=7,
        bbox={
            "boxstyle": "round,pad=0.14",
            "facecolor": "#ffffff",
            "edgecolor": "#d1d5db",
            "alpha": 0.9,
        },
    )


def _format_annotation_number(value: float) -> str:
    return f"{value:.4g}"
