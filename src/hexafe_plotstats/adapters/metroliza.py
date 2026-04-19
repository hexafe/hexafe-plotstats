from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ._core import histogram_payload, summarize
from ..models.common import SpecLimits


def _values_from_object(obj: Any) -> tuple[float, ...]:
    for attribute in ("values", "data", "series"):
        if hasattr(obj, attribute):
            candidate = getattr(obj, attribute)
            try:
                return tuple(float(value) for value in candidate)
            except Exception:
                pass
    if hasattr(obj, "to_numpy"):
        try:
            return tuple(float(value) for value in obj.to_numpy().tolist())
        except Exception:
            pass
    if isinstance(obj, Iterable):
        return tuple(float(value) for value in obj)
    raise TypeError("could not extract numeric values from metroliza object")


def summarize_metroliza(obj: Any, spec_limits: SpecLimits | None = None):
    return summarize(_values_from_object(obj), spec_limits)


def histogram_from_metroliza(obj: Any, spec_limits: SpecLimits | None = None):
    return histogram_payload(_values_from_object(obj), spec_limits)

