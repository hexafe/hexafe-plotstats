from __future__ import annotations

import numpy as np

from ...models.payloads import ViolinPayload
from ...models.render import RenderResult
from ...specs import violin_payload_to_resolved_spec
from .._common import apply_resolved_layout, style_spec_limits_y


def render_violin_matplotlib(payload: ViolinPayload) -> RenderResult:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    data = [np.asarray(group.values, dtype=float) for group in payload.groups]
    positions = np.arange(1, len(data) + 1)

    resolved = violin_payload_to_resolved_spec(payload)

    if data:
        for group_spec in resolved.groups:
            if not group_spec.body_points:
                continue
            x_values, y_values = zip(*group_spec.body_points, strict=False)
            ax.fill(x_values, y_values, facecolor="tab:blue", edgecolor="tab:blue", alpha=0.75)

        show_mean = bool(payload.metadata.get("show_mean", True))
        show_quartiles = bool(payload.metadata.get("show_quartiles", True))
        show_extrema = bool(payload.metadata.get("show_extrema", True))

        for position, group in zip(positions, payload.groups):
            if show_mean and group.summary.mean is not None:
                ax.scatter([position], [group.summary.mean], color="black", s=12, zorder=3)
                _annotate_value(ax, position, group.summary.mean, "mean", "black", y_offset=8)
            if show_quartiles:
                if group.summary.q1 is not None:
                    ax.hlines(group.summary.q1, position - 0.12, position + 0.12, color="tab:orange", linewidth=1.2, zorder=3)
                if group.summary.median is not None:
                    ax.scatter([position], [group.summary.median], color="tab:orange", s=12, zorder=3)
                if group.summary.q3 is not None:
                    ax.hlines(group.summary.q3, position - 0.12, position + 0.12, color="tab:orange", linewidth=1.2, zorder=3)
            if show_extrema and group.summary.minimum is not None and group.summary.maximum is not None:
                ax.vlines(position, group.summary.minimum, group.summary.maximum, color="tab:gray", linewidth=1, alpha=0.8)
                ax.scatter([position], [group.summary.minimum], color="tab:gray", marker="_", s=42, zorder=3)
                ax.scatter([position], [group.summary.maximum], color="tab:gray", marker="_", s=42, zorder=3)
                _annotate_value(ax, position, group.summary.minimum, "min", "tab:gray", y_offset=-8)
                _annotate_value(ax, position, group.summary.maximum, "max", "tab:gray", y_offset=8)

        for line in resolved.spec_lines:
            if line.kind.startswith("sigma_"):
                ax.hlines(line.y0, line.x0, line.x1, color=line.stroke, linewidth=line.stroke_width, linestyle="--", zorder=3)
                _annotate_value(ax, line.x1, line.y0, line.label, line.stroke, x_offset=5)

    style_spec_limits_y(ax, payload.spec_limits)
    ax.set_xticks(positions, [group.label for group in payload.groups])
    ax.set_xlabel("group")
    ax.set_ylabel("value")
    apply_resolved_layout(fig, ax, resolved)
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "violin", "metadata": payload.metadata})


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
