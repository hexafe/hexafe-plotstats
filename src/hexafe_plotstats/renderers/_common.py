from __future__ import annotations

from ..models.common import SpecLimits


def style_spec_limits(ax, spec_limits: SpecLimits | None) -> None:
    if spec_limits is None:
        return
    if spec_limits.lsl is not None:
        ax.axvline(spec_limits.lsl, color="tab:red", linestyle="--", linewidth=1)
    if spec_limits.nominal is not None:
        ax.axvline(spec_limits.nominal, color="tab:green", linestyle=":", linewidth=1)
    if spec_limits.usl is not None:
        ax.axvline(spec_limits.usl, color="tab:red", linestyle="--", linewidth=1)

