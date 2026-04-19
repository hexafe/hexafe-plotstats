from __future__ import annotations

from collections.abc import Iterable

from ..models.common import SupportProfile
from ..models.fits import DistributionCandidate


_CANDIDATES: tuple[DistributionCandidate, ...] = (
    DistributionCandidate(name="norm", support=("real", "positive", "non_negative")),
    DistributionCandidate(name="skewnorm", support=("real", "positive", "non_negative")),
    DistributionCandidate(name="johnsonsu", support=("real", "positive", "non_negative")),
    DistributionCandidate(name="lognorm", support=("positive",)),
    DistributionCandidate(name="weibull_min", support=("positive", "non_negative")),
    DistributionCandidate(name="gamma", support=("positive", "non_negative")),
)

_CANDIDATES_BY_NAME = {candidate.name: candidate for candidate in _CANDIDATES}


def get_distribution_candidates(
    support: SupportProfile,
    requested: Iterable[str] | None = None,
) -> tuple[DistributionCandidate, ...]:
    """Return supported scipy distribution candidates for empirical support."""

    if support.kind in {"empty", "constant"}:
        return ()

    if requested is None:
        names = tuple(candidate.name for candidate in _CANDIDATES)
    else:
        names = tuple(requested)

    unknown = tuple(name for name in names if name not in _CANDIDATES_BY_NAME)
    if unknown:
        raise ValueError(f"unknown distribution candidate(s): {', '.join(unknown)}")

    return tuple(
        _CANDIDATES_BY_NAME[name]
        for name in names
        if support.kind in _CANDIDATES_BY_NAME[name].support
    )


def known_distribution_names() -> tuple[str, ...]:
    return tuple(candidate.name for candidate in _CANDIDATES)

