from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from ..models.common import SupportProfile
from ..models.fits import CurvePayload
from ..utils.numeric import as_float_tuple
from ._cleaning import clean_numeric_with_warnings
from .support_detection import detect_support


def build_kde_curve(
    values: object,
    support: SupportProfile | None = None,
    points: int = 256,
    bw_method: str | float | Any | None = None,
    label: str = "KDE",
) -> CurvePayload:
    """Build a gaussian KDE curve, clipping the x-grid for positive support."""

    if points < 2:
        raise ValueError("points must be at least 2")

    cleaned, warnings = clean_numeric_with_warnings(values)  # type: ignore[arg-type]
    support = support or detect_support(cleaned)
    metadata: dict[str, Any] = {
        "support": support.kind,
        "points": points,
    }
    if bw_method is not None:
        metadata["bw_method"] = str(bw_method)

    if cleaned.size < 2:
        metadata["warnings"] = warnings + ("KDE requires at least two finite numeric values",)
        return CurvePayload(x=(), y=(), label=label, kind="kde", metadata=metadata)

    if bool(np.all(cleaned == cleaned[0])):
        metadata["warnings"] = warnings + ("KDE is undefined for constant values",)
        return CurvePayload(x=(), y=(), label=label, kind="kde", metadata=metadata)

    x_min, x_max = _curve_bounds(cleaned, support)
    try:
        kde = stats.gaussian_kde(cleaned, bw_method=bw_method)
        x = np.linspace(x_min, x_max, points)
        y = kde(x)
    except Exception as exc:  # pragma: no cover - scipy error messages vary by version
        metadata["warnings"] = warnings + (f"KDE failed: {exc}",)
        return CurvePayload(x=(), y=(), label=label, kind="kde", metadata=metadata)

    y = np.where(np.isfinite(y), y, 0.0)
    if support.kind in {"positive", "non_negative"}:
        y = np.where(x < 0.0, 0.0, y)

    if warnings:
        metadata["warnings"] = warnings
    return CurvePayload(
        x=as_float_tuple(x),
        y=as_float_tuple(y),
        label=label,
        kind="kde",
        metadata=metadata,
    )


def _curve_bounds(values: np.ndarray, support: SupportProfile) -> tuple[float, float]:
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    span = maximum - minimum
    if span <= 0.0:
        margin = max(abs(minimum) * 0.1, 0.5)
    else:
        margin = max(span * 0.1, float(np.std(values, ddof=1)) * 0.25)

    lower = minimum - margin
    upper = maximum + margin
    if support.kind == "positive":
        lower = max(np.nextafter(0.0, 1.0), lower)
    elif support.kind == "non_negative":
        lower = max(0.0, lower)

    if upper <= lower:
        upper = lower + max(abs(lower) * 0.1, 1.0)

    return float(lower), float(upper)

