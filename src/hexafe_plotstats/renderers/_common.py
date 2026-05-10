from __future__ import annotations

from ..models.common import SpecLimits


def apply_resolved_layout(fig, ax, spec) -> None:
    canvas = spec.canvas
    plot = spec.plot_rect
    width = float(canvas.size.width)
    height = float(canvas.size.height)
    if width > 0.0 and height > 0.0:
        fig.set_size_inches(width / 100.0, height / 100.0, forward=True)
        ax.set_position(
            [
                plot.x / width,
                1.0 - ((plot.y + plot.height) / height),
                plot.width / width,
                plot.height / height,
            ]
        )

    axes = {axis.orientation: axis for axis in spec.axes}
    if x_axis := axes.get("x"):
        ax.set_xlim(x_axis.minimum, x_axis.maximum)
        if x_axis.tick_values:
            ax.set_xticks(x_axis.tick_values, x_axis.tick_labels or None)
        ax.set_xlabel(x_axis.label)
    if y_axis := axes.get("y"):
        ax.set_ylim(y_axis.minimum, y_axis.maximum)
        if y_axis.tick_values:
            ax.set_yticks(y_axis.tick_values, y_axis.tick_labels or None)
        ax.set_ylabel(y_axis.label)
    if spec.title is not None and spec.title.text:
        ax.set_title(spec.title.text)


def style_spec_limits(ax, spec_limits: SpecLimits | None) -> None:
    if spec_limits is None:
        return
    if spec_limits.lsl is not None:
        ax.axvline(spec_limits.lsl, color="tab:red", linestyle="--", linewidth=1)
    if spec_limits.nominal is not None:
        ax.axvline(spec_limits.nominal, color="tab:green", linestyle=":", linewidth=1)
    if spec_limits.usl is not None:
        ax.axvline(spec_limits.usl, color="tab:red", linestyle="--", linewidth=1)


def style_spec_limits_y(ax, spec_limits: SpecLimits | None) -> None:
    if spec_limits is None:
        return
    if spec_limits.lsl is not None:
        ax.axhline(spec_limits.lsl, color="tab:red", linestyle="--", linewidth=1)
    if spec_limits.nominal is not None:
        ax.axhline(spec_limits.nominal, color="tab:green", linestyle=":", linewidth=1)
    if spec_limits.usl is not None:
        ax.axhline(spec_limits.usl, color="tab:red", linestyle="--", linewidth=1)
