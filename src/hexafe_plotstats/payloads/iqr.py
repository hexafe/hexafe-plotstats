from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from ..models.common import IQRConfig, SpecLimits
from ..models.payloads import IQRGroupPayload, IQRPayload
from ._common import normalize_group_values, summarize_distribution


def build_iqr_payload(
    groups: Mapping[str, Iterable[Any]] | Sequence[tuple[str, Iterable[Any]]],
    spec_limits: SpecLimits | None = None,
    config: IQRConfig | None = None,
) -> IQRPayload:
    config = config or IQRConfig()
    payload_groups: list[IQRGroupPayload] = []
    for label, values in normalize_group_values(groups):
        array = np.asarray(values, dtype=float)
        summary = summarize_distribution(array, spec_limits)
        if array.size == 0:
            outliers: tuple[float, ...] = ()
        else:
            q1 = float(np.quantile(array, 0.25))
            q3 = float(np.quantile(array, 0.75))
            iqr = q3 - q1
            lower = q1 - config.whis * iqr
            upper = q3 + config.whis * iqr
            outliers = tuple(float(value) for value in array[(array < lower) | (array > upper)]) if config.showfliers else ()
        payload_groups.append(IQRGroupPayload(label=label, values=values, summary=summary, outliers=outliers))

    return IQRPayload(groups=tuple(payload_groups), spec_limits=spec_limits, metadata={"whis": config.whis, "showfliers": config.showfliers})

