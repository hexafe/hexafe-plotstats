from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from ..models.payloads import TableRow
from ..models.common import SpecLimits
from ..models.fits import DistributionFitResult
from ..models.summaries import CapabilitySummary, DistributionSummary, NormalitySummary
from ..stats import compute_capability, fit_distribution, summarize_distribution
from ..utils import as_float_tuple, compact_float, normalize_label

__all__ = [
    "build_table_rows",
    "compute_capability",
    "finite_array",
    "fit_distribution",
    "histogram_bins",
    "normalize_group_values",
    "paired_finite_arrays",
    "summarize_distribution",
]


def finite_array(values: Iterable[Any]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float).reshape(-1)
    return array[np.isfinite(array)]


def paired_finite_arrays(left: Iterable[Any], right: Iterable[Any]) -> tuple[np.ndarray, np.ndarray]:
    left_values = np.asarray(list(left), dtype=float).reshape(-1)
    right_values = np.asarray(list(right), dtype=float).reshape(-1)
    if left_values.size != right_values.size:
        raise ValueError("x and y must have the same length")

    mask = np.isfinite(left_values) & np.isfinite(right_values)
    return left_values[mask], right_values[mask]


def normalize_group_values(
    groups: Mapping[str, Iterable[Any]] | Sequence[tuple[str, Iterable[Any]]],
) -> tuple[tuple[str, tuple[float, ...]], ...]:
    items = groups.items() if isinstance(groups, Mapping) else groups
    normalized: list[tuple[str, tuple[float, ...]]] = []
    for label, values in items:
        array = finite_array(values)
        normalized.append((normalize_label(label), as_float_tuple(array)))
    return tuple(normalized)


def build_table_rows(
    summary: DistributionSummary,
    capability: CapabilitySummary,
    *,
    normality: NormalitySummary | None = None,
    fit: DistributionFitResult | None = None,
    spec_limits: SpecLimits | None = None,
) -> tuple[TableRow, ...]:
    """Build Metroliza-style histogram summary rows for renderer-agnostic payloads."""

    rows: list[TableRow] = [
        _metric_row("Min", _measurement(summary.minimum)),
        _metric_row("Max", _measurement(summary.maximum)),
        _metric_row("Mean", _measurement(summary.mean)),
        _metric_row("Median", _measurement(summary.median)),
        _metric_row("Std Dev", _measurement(summary.std)),
    ]

    limits = spec_limits or SpecLimits()
    spec_type = _spec_type(limits)
    if spec_type == "two_sided":
        rows.append(_capability_row("Cp", capability.cp))
        rows.append(_capability_row("Cpk", capability.cpk))
    elif spec_type == "lower_only":
        rows.append(_capability_row("Cpl", capability.cpl))
    elif spec_type == "upper_only":
        rows.append(_capability_row("Cpu", capability.cpu))
    else:
        rows.append(_capability_row("Cpk", capability.cpk))

    rows.extend(
        [
            _metric_row("NOK", _observed_nok(summary, spec_type), badge_palette=_nok_palette(summary.nok_rate)),
            _metric_row("NOK %", _percent(summary.nok_rate), badge_palette=_nok_palette(summary.nok_rate)),
            _metric_row(
                "Samples",
                str(summary.count),
                badge_palette=_sample_palette(summary.count),
                metadata={"sample_confidence": _sample_confidence(summary.count)},
            ),
        ]
    )

    if normality is not None:
        rows.append(
            _metric_row(
                "Normality",
                _normality_value(normality),
                badge_palette=_normality_palette(normality),
                metadata={"method": normality.method, "p_value": normality.p_value},
            )
        )

    if fit is not None:
        rows.extend(_fit_rows(summary, fit))

    return tuple(row for row in rows if row.value)


def _metric_row(
    label: str,
    value: str,
    *,
    badge_palette: str | None = None,
    section_break_before: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> TableRow:
    row_metadata = dict(metadata or {})
    if badge_palette:
        row_metadata["badge_palette"] = badge_palette
    if section_break_before:
        row_metadata["section_break_before"] = True
    return TableRow(label=label, value=value, kind="summary_metric", metadata=row_metadata)


def _capability_row(label: str, value: float | None) -> TableRow:
    return _metric_row(label, _capability_value(value), badge_palette=_capability_palette(value))


def _fit_rows(summary: DistributionSummary, fit: DistributionFitResult) -> tuple[TableRow, ...]:
    fit_quality = _fit_quality_key(fit.quality, summary.count)
    rows: list[TableRow] = [
        _metric_row(
            "Model",
            _fit_name(fit.selected),
            badge_palette=_fit_palette(fit_quality),
            section_break_before=True,
        )
    ]

    if fit.tail_risk is not None and fit_quality not in {"weak", "unreliable"}:
        tail = fit.tail_risk
        total = tail.total_probability
        if total is not None:
            parts: list[str] = []
            if tail.below_lsl_probability is not None:
                parts.append(f"L: {_probability_percent(tail.below_lsl_probability)}")
            if tail.above_usl_probability is not None:
                parts.append(f"U: {_probability_percent(tail.above_usl_probability)}")
            suffix = f" ({', '.join(parts)})" if parts else ""
            rows.append(_metric_row("Est. NOK %", f"{_probability_percent(total)}{suffix}", badge_palette=_nok_palette(total)))
    if fit.quality and fit.quality != "not_run":
        rows.append(_metric_row("Fit quality", _fit_quality_value(fit_quality), badge_palette=_fit_palette(fit_quality)))

    warning = _fit_warning(summary, fit_quality)
    if warning:
        rows.append(_metric_row("Warning", warning, badge_palette="quality_risk"))

    return tuple(rows)


def _measurement(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.3f}"


def _capability_value(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100.0:.2f}%"


def _probability_percent(value: float | None, *, decimals: int = 4) -> str:
    if value is None:
        return "N/A"
    percent = max(0.0, min(1.0, value)) * 100.0
    if 0.0 < percent < 0.0001:
        return "<0.0001%"
    return f"{percent:.{int(decimals)}f}%"


def _observed_nok(summary: DistributionSummary, spec_type: str) -> str:
    total = str(summary.nok_count)
    if summary.nok_count <= 0:
        return total
    side_parts: list[str] = []
    if spec_type in {"two_sided", "lower_only"} and summary.below_lsl_count > 0:
        side_parts.append(f"L: {summary.below_lsl_count}")
    if spec_type in {"two_sided", "upper_only"} and summary.above_usl_count > 0:
        side_parts.append(f"U: {summary.above_usl_count}")
    if not side_parts:
        return total
    return f"{total} ({', '.join(side_parts)})"


def _sample_confidence(count: int) -> dict[str, Any]:
    if count <= 0:
        return {"sample_size": count, "is_low_n": False, "severity": "none", "badge": "", "rationale": ""}
    if count < 10:
        return {
            "sample_size": count,
            "is_low_n": True,
            "severity": "severe",
            "badge": "!!",
            "rationale": "n<10: capability and fit estimates are highly unstable.",
        }
    if count < 25:
        return {
            "sample_size": count,
            "is_low_n": True,
            "severity": "warning",
            "badge": "!",
            "rationale": "n<25: capability and fit estimates have broad uncertainty.",
        }
    return {"sample_size": count, "is_low_n": False, "severity": "none", "badge": "", "rationale": ""}


def _fit_name(value: str | None) -> str:
    if not value:
        return "N/A"
    names = {
        "norm": "Normal",
        "lognorm": "Lognormal",
        "expon": "Exponential",
        "gamma": "Gamma",
        "weibull_min": "Weibull",
        "beta": "Beta",
    }
    return names.get(value, value)


def _fit_quality_key(value: str, count: int) -> str:
    normalized = {
        "selected": "strong",
        "high": "strong",
        "strong": "strong",
        "medium": "medium",
        "low": "weak",
        "weak": "weak",
        "unreliable": "unreliable",
    }.get(value, value)
    if normalized in {"strong", "medium", "weak", "unreliable"}:
        if 0 < count < 10:
            return "unreliable"
        if count < 25 and normalized == "strong":
            return "medium"
    return normalized


def _fit_quality_value(value: str) -> str:
    labels = {
        "strong": "Strong",
        "medium": "Medium",
        "weak": "Weak",
        "unreliable": "Unreliable",
        "not_run": "Not run",
    }
    return labels.get(value, value.replace("_", " ").title())


def _normality_value(normality: NormalitySummary) -> str:
    if normality.is_normal is True:
        status = "Normal"
    elif normality.is_normal is False:
        status = "Not normal"
    else:
        status = "Not run"
    if normality.p_value is None:
        return status
    return f"{status} (p={compact_float(normality.p_value, digits=3)})"


def _spec_type(spec_limits: SpecLimits) -> str:
    if spec_limits.lsl is not None and spec_limits.usl is not None:
        return "two_sided"
    if spec_limits.lsl is not None:
        return "lower_only"
    if spec_limits.usl is not None:
        return "upper_only"
    return "none"


def _capability_palette(value: float | None) -> str:
    if value is None:
        return "quality_unknown"
    if value >= 1.67:
        return "quality_capable"
    if value >= 1.33:
        return "quality_good"
    if value >= 1.0:
        return "quality_marginal"
    return "quality_risk"


def _nok_palette(value: float | None) -> str:
    if value is None:
        return "quality_unknown"
    if value <= 0.003:
        return "quality_capable"
    if value <= 0.05:
        return "quality_marginal"
    return "quality_risk"


def _sample_palette(count: int) -> str | None:
    if count < 10:
        return "quality_risk"
    if count < 25:
        return "quality_marginal"
    return None


def _normality_palette(normality: NormalitySummary) -> str:
    if normality.is_normal is True:
        return "normality_normal"
    if normality.is_normal is False:
        return "normality_not_normal"
    return "quality_unknown"


def _fit_palette(quality: str) -> str:
    if quality == "strong":
        return "fit_quality_high"
    if quality == "medium":
        return "fit_quality_medium"
    if quality in {"weak", "unreliable"}:
        return "fit_quality_low"
    return "quality_unknown"


def _fit_warning(summary: DistributionSummary, fit_quality: str) -> str | None:
    if fit_quality == "unreliable":
        return "fit unreliable; observed NOK only"
    if fit_quality == "weak":
        return "fit weak"
    if summary.count < 25:
        return "small sample; capability uncertain"
    return None


def histogram_bins(
    values: np.ndarray,
    bins: int | str,
    density: bool,
) -> tuple[np.ndarray, np.ndarray]:
    if values.size == 0:
        return np.zeros(1, dtype=float), np.asarray([0.0, 1.0], dtype=float)

    if bool(np.all(values == values[0])):
        center = float(values[0])
        height = 1.0 if density else float(values.size)
        return np.asarray([height], dtype=float), np.asarray([center - 0.5, center + 0.5], dtype=float)

    counts, edges = np.histogram(values, bins=bins, density=density)
    return np.asarray(counts, dtype=float), np.asarray(edges, dtype=float)
