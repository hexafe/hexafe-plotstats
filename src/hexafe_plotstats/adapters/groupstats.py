from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ._core import capability, summarize, violin_payload
from ..models.common import SpecLimits


def _values_from_object(obj: Any) -> tuple[float, ...]:
    for attribute in ("values", "data", "sample"):
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
    raise TypeError("could not extract numeric values from groupstats object")


def summarize_groupstats(obj: Any, spec_limits: SpecLimits | None = None):
    return summarize(_values_from_object(obj), spec_limits)


def capability_groupstats(obj: Any, spec_limits: SpecLimits | None = None):
    return capability(_values_from_object(obj), spec_limits)


def violin_from_groups(groups: dict[str, Any], spec_limits: SpecLimits | None = None):
    normalized = [(label, _values_from_object(values)) for label, values in groups.items()]
    return violin_payload(normalized, spec_limits)

