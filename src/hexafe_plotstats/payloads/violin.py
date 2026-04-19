from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ..models.common import SpecLimits, ViolinConfig
from ..models.payloads import ViolinGroupPayload, ViolinPayload
from ._common import normalize_group_values, summarize_distribution


def build_violin_payload(
    groups: Mapping[str, Iterable[Any]] | Sequence[tuple[str, Iterable[Any]]],
    spec_limits: SpecLimits | None = None,
    config: ViolinConfig | None = None,
) -> ViolinPayload:
    config = config or ViolinConfig()
    payload_groups: list[ViolinGroupPayload] = []
    for label, values in normalize_group_values(groups):
        summary = summarize_distribution(values, spec_limits)
        annotations: dict[str, float] = {}
        if config.show_mean and summary.mean is not None:
            annotations["mean"] = summary.mean
        if config.show_quartiles and summary.q1 is not None and summary.q3 is not None:
            annotations["q1"] = summary.q1
            annotations["q3"] = summary.q3
        if config.show_extrema and summary.minimum is not None and summary.maximum is not None:
            annotations["minimum"] = summary.minimum
            annotations["maximum"] = summary.maximum
        payload_groups.append(ViolinGroupPayload(label=label, values=values, summary=summary, annotations=annotations))

    return ViolinPayload(
        groups=tuple(payload_groups),
        spec_limits=spec_limits,
        metadata={
            "show_mean": config.show_mean,
            "show_extrema": config.show_extrema,
            "show_quartiles": config.show_quartiles,
            "sigma_policy": config.sigma_policy,
        },
    )

