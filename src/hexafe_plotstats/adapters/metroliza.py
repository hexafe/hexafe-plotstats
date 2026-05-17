from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from io import BytesIO
from typing import Any
from typing import Literal

from ._core import histogram_payload, summarize
from ..models.common import HistogramConfig, IQRConfig, ScatterConfig, SpecLimits, ViolinConfig
from ..models.payloads import HistogramPayload, TableRow
from ..payloads import build_histogram_payload, build_iqr_payload, build_scatter_payload, build_violin_payload
from ..renderers import renderer_backend_available, render_histogram, render_iqr, render_scatter, render_violin
from ..renderers.plotly import (
    histogram_payload_to_plotly_spec,
    iqr_payload_to_plotly_spec,
    scatter_payload_to_plotly_spec,
    violin_payload_to_plotly_spec,
)

MetrolizaArtifactTarget = Literal["html_dashboard", "workbook_image", "excel_chart_data"]
MetrolizaArtifactBackend = Literal["auto", "matplotlib", "rust"]


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


def histogram_from_metroliza_native_payload(payload: Mapping[str, Any]) -> HistogramPayload:
    """Build a reusable histogram payload from Metroliza's enriched native payload."""

    values = payload.get("values") or []
    limits = _spec_limits_from_payload(payload)
    bin_count = payload.get("bin_count")
    config = HistogramConfig(
        bins=max(1, int(bin_count)) if _is_positive_int_like(bin_count) else "auto",
        density=False,
        include_fit=False,
    )
    metadata = _histogram_metadata_from_native_payload(payload)
    hist = build_histogram_payload(values, limits, config=config, metadata=metadata)
    table_rows = _table_rows_from_payload(payload)
    if table_rows:
        hist = replace(hist, table_rows=table_rows)
    return hist


def chart_artifact_from_metroliza_payload(
    payload: Mapping[str, Any],
    *,
    target: MetrolizaArtifactTarget,
    theme: str | Mapping[str, Any] | None = None,
    backend: MetrolizaArtifactBackend = "auto",
    include_plotly: bool = True,
    include_png: bool = False,
    static: bool | None = None,
) -> dict[str, Any]:
    """Build a complete chart artifact from a Metroliza export payload.

    The artifact is intentionally plain data so Metroliza can place it in HTML
    dashboards, workbook images, or editable workbook chart data without owning
    renderer-specific chart construction.
    """

    if not isinstance(payload, Mapping):
        return _empty_artifact("unknown", "payload must be a mapping")

    chart_type = _normalized_chart_type(payload)
    artifact = _base_artifact(chart_type, target=target, backend="hexafe-plotstats")
    static_mode = _default_static_mode(chart_type, target=target) if static is None else bool(static)

    try:
        if chart_type == "histogram":
            artifact.update(
                _histogram_artifact(
                    payload,
                    target=target,
                    theme=theme,
                    backend=backend,
                    include_plotly=include_plotly,
                    include_png=include_png,
                    static=static_mode,
                )
            )
        elif chart_type == "distribution":
            artifact.update(
                _distribution_artifact(
                    payload,
                    target=target,
                    theme=theme,
                    backend=backend,
                    include_plotly=include_plotly,
                    include_png=include_png,
                    static=static_mode,
                )
            )
        elif chart_type == "iqr":
            artifact.update(
                _iqr_artifact(
                    payload,
                    target=target,
                    theme=theme,
                    backend=backend,
                    include_plotly=include_plotly,
                    include_png=include_png,
                    static=static_mode,
                )
            )
        elif chart_type in {"trend", "time_series", "time_series_raw_aggregate"}:
            artifact.update(
                _scatter_like_artifact(
                    payload,
                    chart_type=chart_type,
                    target=target,
                    theme=theme,
                    backend=backend,
                    include_plotly=include_plotly,
                    include_png=include_png,
                )
            )
        else:
            artifact["diagnostics"].append(f"unsupported chart type: {chart_type or 'unknown'}")
    except Exception as exc:
        artifact["diagnostics"].append(f"plotstats artifact failed: {exc}")

    return artifact


def plotly_spec_from_metroliza_dashboard_payload(
    payload: Mapping[str, Any],
    *,
    title: str = "",
    theme: str | Mapping[str, Any] | None = None,
    static: bool = False,
) -> dict[str, Any]:
    """Convert Metroliza dashboard chart payloads into plotstats Plotly specs.

    This adapter intentionally accepts plain mappings so Metroliza can pass the
    payload dictionaries it already stores in HTML dashboard manifests.
    Unsupported payloads return an empty mapping, allowing callers to keep their
    existing fallback renderer.
    """

    payload_with_title = {**dict(payload), "title": title or payload.get("title") or ""}
    artifact = chart_artifact_from_metroliza_payload(
        payload_with_title,
        target="html_dashboard",
        theme=theme,
        include_plotly=True,
        include_png=False,
        static=static,
    )
    spec = artifact.get("plotly_spec")
    return spec if isinstance(spec, dict) else {}


def _histogram_artifact(
    payload: Mapping[str, Any],
    *,
    target: MetrolizaArtifactTarget,
    theme: str | Mapping[str, Any] | None,
    backend: MetrolizaArtifactBackend,
    include_plotly: bool,
    include_png: bool,
    static: bool,
) -> dict[str, Any]:
    grouped = _groups_from_histogram_payload(payload)
    if grouped:
        return _grouped_histogram_artifact(
            payload,
            grouped,
            target=target,
            theme=theme,
            include_plotly=include_plotly,
            include_png=include_png,
            static=static,
        )

    histogram = histogram_from_metroliza_native_payload(payload)
    histogram = replace(
        histogram,
        metadata=_histogram_metadata_for_dashboard(
            histogram.metadata,
            theme=theme,
            target=target,
            static=static,
        ),
    )
    result = {
        "stats_tables": [_stats_table_from_histogram_payload(histogram, title=_summary_title(payload))],
        "payload_summary": _histogram_summary(histogram, payload),
        "payload_details": _histogram_details(histogram, payload),
        "excel_chart_data": _histogram_excel_chart_data(histogram, title=str(payload.get("title") or "")),
    }
    if include_plotly:
        result["plotly_spec"] = histogram_payload_to_plotly_spec(histogram, static=static)
    if include_png:
        result["png_bytes"], result["backend"] = _render_png_bytes(
            histogram,
            chart_type="histogram",
            backend=backend,
        )
    return result


def _grouped_histogram_artifact(
    payload: Mapping[str, Any],
    groups: dict[str, Sequence[Any]],
    *,
    target: MetrolizaArtifactTarget,
    theme: str | Mapping[str, Any] | None,
    include_plotly: bool,
    include_png: bool,
    static: bool,
) -> dict[str, Any]:
    excel_data = _grouped_histogram_excel_data(payload, groups)
    stats_tables = []
    for label, values in groups.items():
        group_payload = build_histogram_payload(
            values,
            _spec_limits_from_payload(payload),
            config=HistogramConfig(bins=payload.get("bin_count") or "auto", density=False),
            metadata={"title": str(payload.get("title") or ""), "theme": theme},
        )
        stats_tables.append(_stats_table_from_histogram_payload(group_payload, title=label))

    result: dict[str, Any] = {
        "stats_tables": stats_tables,
        "payload_summary": {
            "type": "histogram",
            "group_count": len(groups),
            "sample_count": sum(len(values) for values in groups.values()),
            "bin_count": len(excel_data.get("bins") or ()),
        },
        "payload_details": {"groups": list(groups.keys())},
        "excel_chart_data": excel_data,
    }
    if include_plotly:
        result["plotly_spec"] = _grouped_histogram_plotly_spec(
            payload,
            groups,
            excel_data=excel_data,
            theme=theme,
            static=static,
        )
    if include_png:
        # A grouped histogram PNG is currently represented by the Plotly-ready
        # artifact plus editable data; Metroliza can fall back to its legacy PNG
        # path until the package grows a dedicated grouped PNG renderer.
        result["diagnostics"] = ["grouped histogram PNG is not implemented in plotstats yet"]
    return result


def _distribution_artifact(
    payload: Mapping[str, Any],
    *,
    target: MetrolizaArtifactTarget,
    theme: str | Mapping[str, Any] | None,
    backend: MetrolizaArtifactBackend,
    include_plotly: bool,
    include_png: bool,
    static: bool,
) -> dict[str, Any]:
    render_mode = str(payload.get("render_mode") or "violin").strip().lower()
    if render_mode == "scatter":
        return _scatter_like_artifact(
            payload,
            chart_type="distribution",
            target=target,
            theme=theme,
            backend=backend,
            include_plotly=include_plotly,
            include_png=include_png,
        )

    groups = _groups_from_series_payload(payload)
    if not groups:
        return _empty_artifact("distribution", "distribution payload contains no groups")
    violin = build_violin_payload(
        groups,
        spec_limits=_spec_limits_from_payload(payload),
        config=ViolinConfig(
            show_mean=True,
            show_extrema=True,
            show_quartiles=True,
            sigma_policy="both_3_sigma",
        ),
    )
    violin = replace(violin, metadata=_metadata_with_theme(violin.metadata, theme))
    result: dict[str, Any] = {
        "payload_summary": _grouped_series_summary("distribution", groups),
        "payload_details": {"groups": list(groups.keys())},
        "excel_chart_data": _series_excel_chart_data(groups),
    }
    if include_plotly:
        spec = violin_payload_to_plotly_spec(violin, static=static)
        _set_plotly_title(spec, str(payload.get("title") or "Violin"))
        result["plotly_spec"] = spec
    if include_png:
        result["png_bytes"], result["backend"] = _render_png_bytes(
            violin,
            chart_type="distribution",
            backend=backend,
        )
    return result


def _iqr_artifact(
    payload: Mapping[str, Any],
    *,
    target: MetrolizaArtifactTarget,
    theme: str | Mapping[str, Any] | None,
    backend: MetrolizaArtifactBackend,
    include_plotly: bool,
    include_png: bool,
    static: bool,
) -> dict[str, Any]:
    groups = _groups_from_series_payload(payload)
    if not groups:
        return _empty_artifact("iqr", "iqr payload contains no groups")
    iqr = build_iqr_payload(
        groups,
        spec_limits=_spec_limits_from_payload(payload),
        config=IQRConfig(showfliers=True),
    )
    iqr = replace(iqr, metadata=_metadata_with_theme(iqr.metadata, theme))
    result: dict[str, Any] = {
        "payload_summary": _grouped_series_summary("iqr", groups),
        "payload_details": {"groups": list(groups.keys())},
        "excel_chart_data": _series_excel_chart_data(groups),
    }
    if include_plotly:
        spec = iqr_payload_to_plotly_spec(iqr, static=static)
        _set_plotly_title(spec, str(payload.get("title") or "IQR"))
        result["plotly_spec"] = spec
    if include_png:
        result["png_bytes"], result["backend"] = _render_png_bytes(
            iqr,
            chart_type="iqr",
            backend=backend,
        )
    return result


def _scatter_like_artifact(
    payload: Mapping[str, Any],
    *,
    chart_type: str,
    target: MetrolizaArtifactTarget,
    theme: str | Mapping[str, Any] | None,
    backend: MetrolizaArtifactBackend,
    include_plotly: bool,
    include_png: bool,
) -> dict[str, Any]:
    if isinstance(payload.get("traces"), Sequence):
        spec = _trace_payload_to_plotly_spec(payload, theme=theme)
        return {
            "plotly_spec": spec if include_plotly else {},
            "payload_summary": {
                "type": chart_type,
                "trace_count": len(payload.get("traces") or ()),
            },
            "payload_details": {},
            "excel_chart_data": _trace_excel_chart_data(payload),
        }

    x_values = payload.get("x_values") or payload.get("x") or []
    y_values = payload.get("y_values") or payload.get("y") or []
    scatter = build_scatter_payload(
        x_values,
        y_values,
        config=ScatterConfig(include_trend=chart_type == "trend"),
        metadata={"title": str(payload.get("title") or ""), "theme": theme},
    )
    result: dict[str, Any] = {
        "payload_summary": {
            "type": chart_type,
            "point_count": len(scatter.x),
            "data_policy": scatter.metadata.get("finite_point_count"),
        },
        "payload_details": {},
        "excel_chart_data": {
            "series": [
                {
                    "name": str(payload.get("title") or chart_type),
                    "x": list(scatter.x),
                    "y": list(scatter.y),
                }
            ]
        },
    }
    if include_plotly:
        spec = scatter_payload_to_plotly_spec(scatter)
        _decorate_scatter_layout(spec, payload, chart_type=chart_type, theme=theme)
        result["plotly_spec"] = spec
    if include_png:
        result["png_bytes"], result["backend"] = _render_png_bytes(
            scatter,
            chart_type="scatter",
            backend=backend,
        )
    return result


def _render_png_bytes(payload: Any, *, chart_type: str, backend: MetrolizaArtifactBackend) -> tuple[bytes, str]:
    preferred_backend = "rust" if backend == "rust" and renderer_backend_available("rust") else "matplotlib"
    renderers = {
        "histogram": render_histogram,
        "distribution": render_violin,
        "iqr": render_iqr,
        "scatter": render_scatter,
    }
    renderer = renderers[chart_type]
    result = renderer(payload, backend=preferred_backend)  # type: ignore[arg-type]
    if hasattr(result, "png_bytes"):
        return bytes(result.png_bytes), f"hexafe-plotstats:{preferred_backend}"
    fig = result.fig
    buffer = BytesIO()
    try:
        fig.savefig(buffer, format="png", dpi=150)
        return buffer.getvalue(), "hexafe-plotstats:matplotlib"
    finally:
        if hasattr(fig, "clf"):
            fig.clf()


def _normalized_chart_type(payload: Mapping[str, Any]) -> str:
    chart_type = str(payload.get("type") or payload.get("chart_type") or "").strip().lower()
    if chart_type == "box":
        return "iqr"
    return chart_type


def _base_artifact(chart_type: str, *, target: str, backend: str) -> dict[str, Any]:
    return {
        "chart_type": chart_type,
        "target": target,
        "backend": backend,
        "plotly_spec": {},
        "png_bytes": None,
        "excel_chart_data": {},
        "stats_tables": [],
        "payload_summary": {},
        "payload_details": {},
        "notes": [],
        "diagnostics": [],
        "metadata": {},
    }


def _empty_artifact(chart_type: str, message: str) -> dict[str, Any]:
    artifact = _base_artifact(chart_type, target="", backend="hexafe-plotstats")
    artifact["diagnostics"].append(message)
    return artifact


def _default_static_mode(chart_type: str, *, target: str) -> bool:
    if chart_type in {"trend", "time_series", "time_series_raw_aggregate"}:
        return False
    return target not in {"html_dashboard", "html_dashboard_interactive"}


def _groups_from_histogram_payload(payload: Mapping[str, Any]) -> dict[str, Sequence[Any]]:
    groups = payload.get("groups")
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)):
        return {}
    output: dict[str, Sequence[Any]] = {}
    for index, raw in enumerate(groups, start=1):
        if not isinstance(raw, Mapping):
            continue
        label = str(raw.get("group") or raw.get("label") or f"Group {index}")
        values = raw.get("values") or raw.get("series") or []
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            output[label] = values
        elif isinstance(values, Iterable):
            output[label] = tuple(values)
    return output


def _stats_table_from_histogram_payload(payload: HistogramPayload, *, title: str) -> dict[str, Any]:
    return {
        "title": title,
        "backend": "hexafe-plotstats",
        "rows": [{"label": row.label, "value": row.value} for row in payload.table_rows],
    }


def _summary_title(payload: Mapping[str, Any]) -> str:
    visual = payload.get("visual_metadata") if isinstance(payload.get("visual_metadata"), Mapping) else {}
    table = visual.get("summary_stats_table") if isinstance(visual.get("summary_stats_table"), Mapping) else {}
    return str(table.get("title") or payload.get("summary_table_title") or "Parameter")


def _histogram_summary(payload: HistogramPayload, raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "histogram",
        "sample_count": payload.summary.count,
        "bin_count": max(len(payload.bin_edges) - 1, 0),
        "limits": {
            "lsl": payload.spec_limits.lsl,
            "nominal": payload.spec_limits.nominal,
            "usl": payload.spec_limits.usl,
        },
        "summary_row_count": len(payload.table_rows),
        "title": str(raw.get("title") or payload.metadata.get("title") or ""),
    }


def _histogram_details(payload: HistogramPayload, raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "summary_stats_table": _stats_table_from_histogram_payload(payload, title=_summary_title(raw)),
        "warnings": list(payload.warnings),
    }


def _histogram_excel_chart_data(payload: HistogramPayload, *, title: str) -> dict[str, Any]:
    bins = []
    for index, value in enumerate(payload.bin_values):
        if index + 1 >= len(payload.bin_edges):
            break
        bins.append(
            {
                "label": f"{payload.bin_edges[index]:.3g} - {payload.bin_edges[index + 1]:.3g}",
                "start": float(payload.bin_edges[index]),
                "end": float(payload.bin_edges[index + 1]),
                "value": float(value),
            }
        )
    return {"title": title, "bins": bins, "series": [{"name": title or "Histogram", "values": bins}]}


def _grouped_histogram_excel_data(
    payload: Mapping[str, Any],
    groups: dict[str, Sequence[Any]],
) -> dict[str, Any]:
    import numpy as np

    all_values = [float(value) for values in groups.values() for value in values]
    if not all_values:
        return {"bins": [], "series": []}
    bin_count = payload.get("bin_count")
    try:
        bins = max(1, int(bin_count))
    except (TypeError, ValueError):
        bins = "auto"  # type: ignore[assignment]
    counts, edges = np.histogram(all_values, bins=bins)
    labels = [f"{edges[index]:.3g} - {edges[index + 1]:.3g}" for index in range(len(edges) - 1)]
    series = []
    for label, values in groups.items():
        group_counts, _ = np.histogram([float(value) for value in values], bins=edges)
        total = float(np.sum(group_counts))
        series.append(
            {
                "name": label,
                "values": [
                    {
                        "label": bin_label,
                        "count": int(count),
                        "share": float(count) / total if total > 0 else 0.0,
                    }
                    for bin_label, count in zip(labels, group_counts, strict=False)
                ],
            }
        )
    return {
        "bins": [{"label": label, "start": float(edges[i]), "end": float(edges[i + 1])} for i, label in enumerate(labels)],
        "series": series,
        "total_counts": [int(value) for value in counts],
    }


def _grouped_histogram_plotly_spec(
    payload: Mapping[str, Any],
    groups: dict[str, Sequence[Any]],
    *,
    excel_data: Mapping[str, Any],
    theme: str | Mapping[str, Any] | None,
    static: bool,
) -> dict[str, Any]:
    traces = []
    for group in excel_data.get("series") or []:
        values = group.get("values") if isinstance(group, Mapping) else []
        traces.append(
            {
                "type": "bar",
                "name": str(group.get("name") or "Group"),
                "x": [row["label"] for row in values],
                "y": [row["share"] for row in values],
                "customdata": [[row["count"]] for row in values],
                "hovertemplate": "%{x}<br>frequency=%{y:.2%}<br>count=%{customdata[0]}<extra></extra>",
            }
        )
    shapes, annotations = _vertical_reference_shapes_and_annotations(payload)
    config: dict[str, Any] = {"responsive": True, "displaylogo": False}
    if static:
        config["staticPlot"] = True
        config["displayModeBar"] = False
    return {
        "data": traces,
        "layout": {
            "title": {"text": str(payload.get("title") or "Grouped histogram")},
            "barmode": "overlay",
            "yaxis": {"tickformat": ".0%", "title": {"text": "Frequency (%)"}},
            "xaxis": {"title": {"text": "Measurement"}},
            "shapes": shapes,
            "annotations": annotations,
            "meta": {
                "theme": theme,
                "data_policy": "grouped_histogram_bins",
                "histogram_y_mode": "relative_percent",
            },
        },
        "config": config,
        "metadata": {
            "kind": "histogram",
            "backend": "plotly",
            "group_count": len(groups),
            "data_policy": "grouped_histogram_bins",
            "histogram_y_mode": "relative_percent",
            "interactive_enabled": not static,
            "theme": theme,
        },
    }


def _grouped_series_summary(chart_type: str, groups: Mapping[str, Sequence[Any]]) -> dict[str, Any]:
    return {
        "type": chart_type,
        "group_count": len(groups),
        "series_sizes": [len(values) for values in groups.values()],
        "sample_count": sum(len(values) for values in groups.values()),
    }


def _series_excel_chart_data(groups: Mapping[str, Sequence[Any]]) -> dict[str, Any]:
    return {
        "series": [
            {"name": label, "values": [float(value) for value in values]}
            for label, values in groups.items()
        ]
    }


def _trace_excel_chart_data(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "series": [
            {
                "name": str(trace.get("name") or f"Series {index}"),
                "x": list(trace.get("x") or []),
                "y": list(trace.get("y") or []),
            }
            for index, trace in enumerate(payload.get("traces") or (), start=1)
            if isinstance(trace, Mapping)
        ]
    }


def _trace_payload_to_plotly_spec(
    payload: Mapping[str, Any],
    *,
    theme: str | Mapping[str, Any] | None,
) -> dict[str, Any]:
    layout = dict(payload.get("layout") or {}) if isinstance(payload.get("layout"), Mapping) else {}
    layout.setdefault("title", {"text": str(payload.get("title") or "")})
    layout.setdefault("meta", {})["theme"] = theme
    return {
        "data": [dict(trace) for trace in payload.get("traces") or () if isinstance(trace, Mapping)],
        "layout": layout,
        "config": {"responsive": True, "displaylogo": False, "scrollZoom": False},
        "metadata": {
            "kind": _normalized_chart_type(payload),
            "backend": "plotly",
            "trace_count": len(payload.get("traces") or ()),
            "theme": theme,
        },
    }


def _decorate_scatter_layout(
    spec: dict[str, Any],
    payload: Mapping[str, Any],
    *,
    chart_type: str,
    theme: str | Mapping[str, Any] | None,
) -> None:
    metadata = spec.setdefault("metadata", {})
    metadata.setdefault("kind", "scatter")
    metadata.setdefault("chart_type", chart_type)
    metadata.setdefault("theme", theme)
    layout = spec.setdefault("layout", {})
    layout.setdefault("title", {"text": str(payload.get("title") or chart_type)})
    layout.setdefault("xaxis", {}).setdefault("title", {"text": str(payload.get("x_label") or "X")})
    layout.setdefault("yaxis", {}).setdefault("title", {"text": str(payload.get("y_label") or "Measurement")})
    layout.setdefault("meta", {})["theme"] = theme
    horizontal_limits = _horizontal_reference_lines_from_payload(payload)
    shapes = list(layout.get("shapes") or [])
    annotations = list(layout.get("annotations") or [])
    for label, value, color in horizontal_limits:
        number = _coerce_float(value)
        if number is None:
            continue
        shapes.append(
            {
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": number,
                "y1": number,
                "line": {"color": color, "width": 1, "dash": "dash"},
            }
        )
        annotations.append(
            {
                "xref": "paper",
                "yref": "y",
                "x": 1.0,
                "y": number,
                "xanchor": "right",
                "text": f"{label}={number:.3f}",
                "showarrow": False,
                "font": {"size": 11, "color": color},
                "bgcolor": "rgba(255,255,255,0.86)",
            }
        )
    if shapes:
        layout["shapes"] = shapes
    if annotations:
        layout["annotations"] = annotations


def _histogram_metadata_for_dashboard(
    metadata: Mapping[str, Any],
    *,
    theme: str | Mapping[str, Any] | None,
    target: MetrolizaArtifactTarget,
    static: bool,
) -> dict[str, Any]:
    resolved = _metadata_with_theme(metadata, theme)
    if target.startswith("html_dashboard") and not static:
        resolved["histogram_y_mode"] = "relative_percent"
        axis_labels = dict(resolved.get("axis_labels") or {})
        axis_labels["y"] = "Frequency (%)"
        resolved["axis_labels"] = axis_labels
    return resolved


def _vertical_reference_shapes_and_annotations(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    shapes: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    for label, value, color in _vertical_reference_lines_from_payload(payload):
        number = _coerce_float(value)
        if number is None:
            continue
        shapes.append(
            {
                "type": "line",
                "xref": "x",
                "yref": "paper",
                "x0": number,
                "x1": number,
                "y0": 0,
                "y1": 1,
                "line": {"color": color, "width": 1, "dash": "dash"},
            }
        )
        annotations.append(
            {
                "xref": "x",
                "yref": "paper",
                "x": number,
                "y": 1.06,
                "text": f"{label}={number:.3f}",
                "showarrow": False,
                "font": {"size": 11, "color": color},
                "bgcolor": "rgba(255,255,255,0.86)",
            }
        )
    return shapes, annotations


def _vertical_reference_lines_from_payload(payload: Mapping[str, Any]) -> list[tuple[str, Any, str]]:
    limits = payload.get("limits") if isinstance(payload.get("limits"), Mapping) else payload
    return [
        ("LSL", limits.get("lsl"), "#dc2626"),
        ("Nominal", limits.get("nominal"), "#16a34a"),
        ("USL", limits.get("usl"), "#dc2626"),
    ]


def _horizontal_reference_lines_from_payload(payload: Mapping[str, Any]) -> list[tuple[str, Any, str]]:
    limits = payload.get("limits") if isinstance(payload.get("limits"), Mapping) else payload
    references = [
        ("LSL", limits.get("lsl"), "#dc2626"),
        ("Nominal", limits.get("nominal"), "#16a34a"),
        ("USL", limits.get("usl"), "#dc2626"),
    ]
    named_values = [(label, value, color) for label, value, color in references if _coerce_float(value) is not None]
    if named_values:
        return named_values
    fallback = []
    for index, value in enumerate(payload.get("horizontal_limits") or (), start=1):
        fallback.append((f"Limit {index}", value, "#B45309"))
    return fallback


def _metadata_with_theme(metadata: Mapping[str, Any], theme: str | Mapping[str, Any] | None) -> dict[str, Any]:
    resolved = dict(metadata)
    if theme is not None:
        resolved["theme"] = theme
    return resolved


def _groups_from_series_payload(payload: Mapping[str, Any]) -> dict[str, Sequence[Any]]:
    labels = [str(label) for label in (payload.get("labels") or ())]
    series = payload.get("series") or ()
    groups: dict[str, Sequence[Any]] = {}
    for index, values in enumerate(series):
        label = labels[index] if index < len(labels) and labels[index] else f"Group {index + 1}"
        if isinstance(values, Sequence):
            groups[label] = values
        elif isinstance(values, Iterable):
            groups[label] = tuple(values)
    return groups


def _set_plotly_title(spec: dict[str, Any], title: str) -> None:
    layout = spec.get("layout")
    if isinstance(layout, dict):
        layout["title"] = {"text": title}


def _spec_limits_from_payload(payload: Mapping[str, Any]) -> SpecLimits:
    limits = payload.get("limits") if isinstance(payload.get("limits"), Mapping) else payload
    return SpecLimits(
        lsl=_coerce_float(limits.get("lsl")),
        nominal=_coerce_float(limits.get("nominal")),
        usl=_coerce_float(limits.get("usl")),
    )


def _histogram_metadata_from_native_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    style = payload.get("style") if isinstance(payload.get("style"), Mapping) else {}
    visual_metadata = payload.get("visual_metadata") if isinstance(payload.get("visual_metadata"), Mapping) else {}
    summary_table = visual_metadata.get("summary_stats_table") if isinstance(visual_metadata.get("summary_stats_table"), Mapping) else {}
    x_view = payload.get("x_view") if isinstance(payload.get("x_view"), Mapping) else None

    metadata = {
        "title": str(payload.get("title") or ""),
        "axis_labels": {
            "x": str(style.get("axis_label_x") or "Measurement"),
            "y": str(style.get("axis_label_y") or "Count"),
        },
        "summary_table_title": str(summary_table.get("title") or payload.get("summary_table_title") or "Parameter"),
        "mean_line": dict(payload.get("mean_line") or {}) if isinstance(payload.get("mean_line"), Mapping) else {},
        "annotation_rows": list(visual_metadata.get("annotation_rows") or payload.get("annotation_rows") or []),
        "specification_lines": list(visual_metadata.get("specification_lines") or payload.get("specification_lines") or []),
        "modeled_overlay_rows": list(
            ((visual_metadata.get("modeled_overlays") or {}).get("rows") if isinstance(visual_metadata.get("modeled_overlays"), Mapping) else None)
            or payload.get("modeled_overlay_rows")
            or []
        ),
        "visual_metadata": dict(visual_metadata),
    }
    if x_view is not None:
        metadata["x_view"] = {"min": _coerce_float(x_view.get("min")), "max": _coerce_float(x_view.get("max"))}
    return metadata


def _table_rows_from_payload(payload: Mapping[str, Any]) -> tuple[TableRow, ...]:
    raw_rows = payload.get("summary_table_rows") or []
    rows = []
    for raw in raw_rows:
        if isinstance(raw, Mapping):
            rows.append(
                TableRow(
                    label=str(raw.get("label") or ""),
                    value=str(raw.get("value") or ""),
                    kind=str(raw.get("row_kind") or "summary_metric"),
                    metadata={
                        key: value
                        for key, value in {
                            "badge_palette": raw.get("badge_palette"),
                            "section_break_before": bool(raw.get("section_break_before")),
                        }.items()
                        if value not in (None, "", False)
                    },
                )
            )
        elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
            rows.append(TableRow(label=str(raw[0]), value=str(raw[1]), kind="summary_metric"))
    return tuple(rows)


def _is_positive_int_like(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _coerce_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None
