from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import stats

from ..models.common import DistributionConfig, SpecLimits, SupportProfile
from ..models.fits import CurvePayload, DistributionFitResult, TailRiskEstimate
from ..utils.numeric import as_float_tuple
from ._cleaning import clean_numeric_with_warnings
from .distribution_registry import get_distribution_candidates
from .fit_ranking import FitRecord, rank_fit_records
from .kde import build_kde_curve
from .support_detection import detect_support


_SCIPY_DISTRIBUTIONS: dict[str, Any] = {
    "norm": stats.norm,
    "skewnorm": stats.skewnorm,
    "johnsonsu": stats.johnsonsu,
    "lognorm": stats.lognorm,
    "weibull_min": stats.weibull_min,
    "gamma": stats.gamma,
}


@dataclass(frozen=True)
class _FitAttempt:
    name: str
    distribution: Any
    scipy_params: tuple[float, ...]
    params: dict[str, float]
    log_likelihood: float
    aic: float
    bic: float


def fit_distribution(
    values: object,
    spec_limits: SpecLimits | None = None,
    config: DistributionConfig | None = None,
) -> DistributionFitResult:
    """Fit candidate scipy distributions and select the best by AIC or BIC."""

    config = config or DistributionConfig()
    cleaned, warnings = clean_numeric_with_warnings(values)  # type: ignore[arg-type]
    support = detect_support(cleaned)

    if cleaned.size < 2:
        return DistributionFitResult(
            selected=None,
            quality="not_run",
            warnings=warnings + ("distribution fitting requires at least two finite numeric values",),
        )

    if support.kind == "constant":
        return DistributionFitResult(
            selected=None,
            quality="not_run",
            kde_reference=_maybe_kde(cleaned, support, config),
            warnings=warnings + ("distribution fitting is undefined for constant values",),
        )

    try:
        candidates = get_distribution_candidates(support, requested=config.candidates)
    except ValueError as exc:
        return DistributionFitResult(
            selected=None,
            quality="failed",
            kde_reference=_maybe_kde(cleaned, support, config),
            warnings=warnings + (str(exc),),
        )

    if not candidates:
        return DistributionFitResult(
            selected=None,
            quality="not_run",
            kde_reference=_maybe_kde(cleaned, support, config),
            warnings=warnings + ("no distribution candidates are compatible with the detected support",),
        )

    fit_warnings: list[str] = []
    attempts: list[_FitAttempt] = []
    for candidate in candidates:
        distribution = _SCIPY_DISTRIBUTIONS[candidate.name]
        try:
            params = _fit_scipy_distribution(candidate.name, distribution, cleaned, support)
            log_likelihood = _log_likelihood(distribution, cleaned, params)
        except Exception as exc:  # pragma: no cover - scipy failures differ by version
            fit_warnings.append(f"{candidate.name} fit failed: {exc}")
            continue

        if not np.isfinite(log_likelihood):
            fit_warnings.append(f"{candidate.name} fit failed: non-finite log likelihood")
            continue

        param_count = len(params)
        aic = float((2 * param_count) - (2.0 * log_likelihood))
        bic = float((param_count * np.log(cleaned.size)) - (2.0 * log_likelihood))
        attempts.append(
            _FitAttempt(
                name=candidate.name,
                distribution=distribution,
                scipy_params=params,
                params=_param_dict(distribution, params),
                log_likelihood=float(log_likelihood),
                aic=aic,
                bic=bic,
            )
        )

    ranked_records = rank_fit_records(
        (
            FitRecord(
                name=attempt.name,
                log_likelihood=attempt.log_likelihood,
                aic=attempt.aic,
                bic=attempt.bic,
            )
            for attempt in attempts
        ),
        config.criterion,
    )

    if not attempts:
        return DistributionFitResult(
            selected=None,
            quality="failed",
            kde_reference=_maybe_kde(cleaned, support, config),
            warnings=warnings + tuple(fit_warnings) + ("all distribution fits failed",),
            candidates_ranked=tuple(_record_as_public_dict(record) for record in ranked_records),
        )

    selected_name = ranked_records[0]["name"]
    selected = next(attempt for attempt in attempts if attempt.name == selected_name)
    gof_statistic = None
    gof_p_value = None
    if config.run_gof:
        if not config.validate_selected_only:
            fit_warnings.append("only selected-distribution GOF is supported")
        gof_statistic, gof_p_value = _selected_gof(selected, cleaned, config, fit_warnings)

    if gof_p_value is not None and gof_p_value < 0.05:
        fit_warnings.append("selected-distribution GOF rejected at alpha=0.05")

    return DistributionFitResult(
        selected=selected.name,
        scipy_params=selected.scipy_params,
        params=selected.params,
        log_likelihood=selected.log_likelihood,
        aic=selected.aic,
        bic=selected.bic,
        quality="selected",
        gof_statistic=gof_statistic,
        gof_p_value=gof_p_value,
        tail_risk=_tail_risk(selected, spec_limits),
        curve=_fit_curve(selected, cleaned, support, config.kde_points),
        kde_reference=_maybe_kde(cleaned, support, config),
        warnings=warnings + tuple(fit_warnings),
        candidates_ranked=tuple(_record_as_public_dict(record) for record in ranked_records),
    )


def _maybe_kde(
    values: np.ndarray,
    support: SupportProfile,
    config: DistributionConfig,
) -> CurvePayload | None:
    if not config.include_kde_reference:
        return None
    return build_kde_curve(values, support=support, points=config.kde_points, label="KDE")


def _fit_scipy_distribution(
    name: str,
    distribution: Any,
    values: np.ndarray,
    support: SupportProfile,
) -> tuple[float, ...]:
    if name in {"lognorm", "weibull_min", "gamma"} and support.kind in {"positive", "non_negative"}:
        return tuple(float(value) for value in distribution.fit(values, floc=0.0))
    return tuple(float(value) for value in distribution.fit(values))


def _log_likelihood(distribution: Any, values: np.ndarray, params: tuple[float, ...]) -> float:
    log_pdf = distribution.logpdf(values, *params)
    if np.any(np.isnan(log_pdf)):
        return float("nan")
    return float(np.sum(log_pdf))


def _param_dict(distribution: Any, params: tuple[float, ...]) -> dict[str, float]:
    shape_names = _shape_names(distribution)
    names = shape_names + ("loc", "scale")
    return {name: float(value) for name, value in zip(names, params)}


def _shape_names(distribution: Any) -> tuple[str, ...]:
    if not distribution.shapes:
        return ()
    return tuple(part.strip() for part in distribution.shapes.split(","))


def _record_as_public_dict(record: FitRecord) -> dict[str, float | str]:
    return {
        "name": record["name"],
        "log_likelihood": float(record["log_likelihood"]),
        "aic": float(record["aic"]),
        "bic": float(record["bic"]),
    }


def _fit_curve(
    fit: _FitAttempt,
    values: np.ndarray,
    support: SupportProfile,
    points: int,
) -> CurvePayload:
    x_min, x_max = _curve_bounds(values, support)
    x = np.linspace(x_min, x_max, max(points, 2))
    y = fit.distribution.pdf(x, *fit.scipy_params)
    y = np.where(np.isfinite(y), y, 0.0)
    if support.kind in {"positive", "non_negative"}:
        y = np.where(x < 0.0, 0.0, y)

    return CurvePayload(
        x=as_float_tuple(x),
        y=as_float_tuple(y),
        label=fit.name,
        kind="pdf",
        metadata={"distribution": fit.name},
    )


def _curve_bounds(values: np.ndarray, support: SupportProfile) -> tuple[float, float]:
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    span = maximum - minimum
    margin = max(span * 0.1, float(np.std(values, ddof=1)) * 0.25, 1e-9)
    lower = minimum - margin
    upper = maximum + margin
    if support.kind == "positive":
        lower = max(np.nextafter(0.0, 1.0), lower)
    elif support.kind == "non_negative":
        lower = max(0.0, lower)
    if upper <= lower:
        upper = lower + max(abs(lower) * 0.1, 1.0)
    return float(lower), float(upper)


def _tail_risk(fit: _FitAttempt, spec_limits: SpecLimits | None) -> TailRiskEstimate | None:
    if spec_limits is None or (not spec_limits.has_lower and not spec_limits.has_upper):
        return None

    below_lsl_probability = None
    above_usl_probability = None
    if spec_limits.lsl is not None:
        below_lsl_probability = _clip_probability(
            float(fit.distribution.cdf(spec_limits.lsl, *fit.scipy_params))
        )
    if spec_limits.usl is not None:
        above_usl_probability = _clip_probability(
            float(fit.distribution.sf(spec_limits.usl, *fit.scipy_params))
        )

    probabilities = [
        probability
        for probability in (below_lsl_probability, above_usl_probability)
        if probability is not None
    ]
    total_probability = _clip_probability(float(sum(probabilities))) if probabilities else None
    ppm = total_probability * 1_000_000.0 if total_probability is not None else None
    return TailRiskEstimate(
        below_lsl_probability=below_lsl_probability,
        above_usl_probability=above_usl_probability,
        total_probability=total_probability,
        ppm=ppm,
    )


def _clip_probability(value: float) -> float | None:
    if not np.isfinite(value):
        return None
    return float(np.clip(value, 0.0, 1.0))


def _selected_gof(
    fit: _FitAttempt,
    values: np.ndarray,
    config: DistributionConfig,
    warnings: list[str],
) -> tuple[float | None, float | None]:
    statistic_name = config.gof_statistic.lower()
    if statistic_name in {"ks", "kolmogorov", "kolmogorov-smirnov"}:
        statistic = _ks_statistic(fit, values)
    elif statistic_name in {"ad", "anderson", "anderson-darling"}:
        statistic = _anderson_darling_statistic(fit, values)
    else:
        warnings.append(f"unsupported GOF statistic: {config.gof_statistic}")
        return None, None

    if not np.isfinite(statistic):
        warnings.append("selected-distribution GOF returned a non-finite statistic")
        return None, None

    p_value = _monte_carlo_gof_p_value(fit, values.size, statistic, statistic_name, config, warnings)
    return float(statistic), p_value


def _ks_statistic(fit: _FitAttempt, values: np.ndarray) -> float:
    sorted_values = np.sort(values)
    cdf = fit.distribution.cdf(sorted_values, *fit.scipy_params)
    count = sorted_values.size
    empirical_upper = np.arange(1, count + 1) / count
    empirical_lower = np.arange(0, count) / count
    return float(np.max(np.maximum(empirical_upper - cdf, cdf - empirical_lower)))


def _anderson_darling_statistic(fit: _FitAttempt, values: np.ndarray) -> float:
    sorted_values = np.sort(values)
    cdf = fit.distribution.cdf(sorted_values, *fit.scipy_params)
    cdf = np.clip(cdf, np.finfo(float).tiny, 1.0 - np.finfo(float).eps)
    count = sorted_values.size
    index = np.arange(1, count + 1)
    return float(
        -count
        - np.mean((2 * index - 1) * (np.log(cdf) + np.log1p(-cdf[::-1])))
    )


def _monte_carlo_gof_p_value(
    fit: _FitAttempt,
    sample_size: int,
    observed: float,
    statistic_name: str,
    config: DistributionConfig,
    warnings: list[str],
) -> float | None:
    samples = max(int(config.gof_samples), 0)
    if samples == 0:
        return None

    rng = np.random.default_rng(config.random_state)
    exceedances = 0
    try:
        for _index in range(samples):
            simulated = fit.distribution.rvs(*fit.scipy_params, size=sample_size, random_state=rng)
            if statistic_name in {"ks", "kolmogorov", "kolmogorov-smirnov"}:
                simulated_statistic = _ks_statistic(fit, np.asarray(simulated, dtype=float))
            else:
                simulated_statistic = _anderson_darling_statistic(
                    fit, np.asarray(simulated, dtype=float)
                )
            if simulated_statistic >= observed:
                exceedances += 1
    except Exception as exc:  # pragma: no cover - scipy failures differ by version
        warnings.append(f"selected-distribution GOF simulation failed: {exc}")
        return None

    return float((exceedances + 1) / (samples + 1))
