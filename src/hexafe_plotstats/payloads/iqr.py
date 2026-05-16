from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from ..models.common import IQRConfig, SpecLimits
from ..models.payloads import IQRGroupPayload, IQRPayload
from ..utils import as_float_tuple
from ._common import normalize_group_arrays, summarize_distribution


_ARRAY_PAYLOAD_THRESHOLD = 50_000


def build_iqr_payload(
    groups: Mapping[str, Iterable[Any]] | Sequence[tuple[str, Iterable[Any]]],
    spec_limits: SpecLimits | None = None,
    config: IQRConfig | None = None,
) -> IQRPayload:
    config = config or IQRConfig()
    payload_groups: list[IQRGroupPayload] = []
    for label, array in normalize_group_arrays(groups):
        summary = summarize_distribution(array, spec_limits)
        if array.size == 0:
            outliers: tuple[float, ...] = ()
        else:
            q1 = summary.q1 if summary.q1 is not None else float(np.quantile(array, 0.25))
            q3 = summary.q3 if summary.q3 is not None else float(np.quantile(array, 0.75))
            iqr = q3 - q1
            lower = q1 - config.whis * iqr
            upper = q3 + config.whis * iqr
            outliers = tuple(float(value) for value in array[(array < lower) | (array > upper)]) if config.showfliers else ()
        values = array if array.size >= _ARRAY_PAYLOAD_THRESHOLD else as_float_tuple(array)
        payload_groups.append(IQRGroupPayload(label=label, values=values, summary=summary, outliers=outliers))

    return IQRPayload(groups=tuple(payload_groups), spec_limits=spec_limits, metadata={"whis": config.whis, "showfliers": config.showfliers})
