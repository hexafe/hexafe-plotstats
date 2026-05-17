from __future__ import annotations

import inspect
import json
import math

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg", force=True)

from hexafe_plotstats.adapters import (
    capability,
    chart_artifact_from_metroliza_payload,
    fit_distribution,
    histogram_from_metroliza_native_payload,
    histogram_payload,
    plotly_spec_from_metroliza_dashboard_payload,
    render_histogram,
    render_scatter,
    render_violin,
    scatter_payload,
    summarize,
    support_profile,
    violin_payload,
)
from hexafe_plotstats.renderers import RendererBackendUnavailable
from hexafe_plotstats.renderers import render_histogram_png
from hexafe_plotstats.renderers.rust import native_backend_available
from hexafe_plotstats.specs import histogram_payload_to_resolved_spec, to_mapping
from hexafe_plotstats.adapters.pandas import series_summary
from hexafe_plotstats.models.common import DistributionConfig, ScatterConfig, SpecLimits
from hexafe_plotstats.stats.capability import compute_capability


def test_support_profile_kinds() -> None:
    assert support_profile([]).kind == "empty"
    assert support_profile([1.0, 2.0, 3.0]).kind == "positive"
    assert support_profile([0.0, 2.0, 4.0]).kind == "non_negative"
    assert support_profile([-1.0, 0.0, 2.0]).kind == "real"
    assert support_profile([5.0, 5.0, 5.0]).kind == "constant"


def test_summary_and_capability_use_spec_limits() -> None:
    values = [9.8, 10.0, 10.1, 9.9, 10.2, 10.3]
    limits = SpecLimits(lsl=9.5, nominal=10.0, usl=10.5)

    summary = summarize(values, limits)
    cap = capability(values, limits)

    assert summary.count == 6
    assert math.isclose(summary.mean, 10.05, rel_tol=1e-12)
    assert summary.nok_count == 0
    assert cap.cp is not None and cap.cpk is not None
    assert cap.cp >= cap.cpk


def test_capability_handles_missing_and_one_sided_spec_limits() -> None:
    values = [1.0, 2.0, 3.0]

    no_limits = compute_capability(values)
    lower_only = compute_capability(values, SpecLimits(lsl=0.0))
    upper_only = compute_capability(values, SpecLimits(usl=10.0))
    two_sided = compute_capability(values, SpecLimits(lsl=0.0, usl=10.0))

    assert no_limits.cp is None
    assert no_limits.cpk is None
    assert no_limits.sample_std == pytest.approx(1.0)
    assert "no specification limits supplied" in no_limits.warnings

    assert lower_only.cp is None
    assert lower_only.cpl == pytest.approx(2.0 / 3.0)
    assert lower_only.cpu is None
    assert lower_only.cpk == pytest.approx(lower_only.cpl)

    assert upper_only.cp is None
    assert upper_only.cpl is None
    assert upper_only.cpu == pytest.approx(8.0 / 3.0)
    assert upper_only.cpk == pytest.approx(upper_only.cpu)

    assert two_sided.cp == pytest.approx(10.0 / 6.0)
    assert two_sided.cpk == pytest.approx(lower_only.cpl)


def test_distribution_fit_selects_reasonable_candidate() -> None:
    values = np.array([-1.5, -0.7, -0.2, 0.0, 0.4, 0.9, 1.3, 2.1, 2.8, 3.5])
    result = fit_distribution(values, SpecLimits(lsl=-2.0, usl=4.0), DistributionConfig(kde_points=64))

    assert result.selected == "norm"
    assert result.quality == "selected"
    assert result.curve is not None
    assert len(result.curve.x) == 64
    assert result.aic is not None and result.bic is not None


def test_histogram_payload_includes_fit_and_rows() -> None:
    values = [9.8, 10.0, 10.1, 9.9, 10.2, 10.3, 10.4, 10.1]
    payload = histogram_payload(values, SpecLimits(lsl=9.5, usl=10.6))

    assert payload.summary.count == 8
    assert payload.fit is not None
    assert payload.normality is not None
    assert payload.bin_edges
    assert payload.bin_values
    labels = [row.label for row in payload.table_rows]
    assert labels[:5] == ["Min", "Max", "Mean", "Median", "Std Dev"]
    assert {"Cp", "Cpk", "NOK", "NOK %", "Samples", "Model", "Fit quality"}.issubset(labels)


def test_histogram_resolved_spec_mapping_tracks_payload_parity_contract() -> None:
    payload = histogram_payload([1.0, 1.2, 1.4, 1.6, 2.0], SpecLimits(lsl=0.8, usl=2.2))

    resolved_spec = histogram_payload_to_resolved_spec(payload)
    mapping = to_mapping(resolved_spec)

    assert mapping["chart_type"] == "histogram"
    assert mapping["bars"][0]["x0"] == pytest.approx(payload.bin_edges[0])
    assert mapping["bars"][-1]["x1"] == pytest.approx(payload.bin_edges[-1])
    assert mapping["table"]["rows"][0]["cells"][0]["text"] == "Min"
    assert mapping["table"]["rows"][0]["cells"][1]["text"] == "1.000"
    assert mapping["metadata"]["spec_limits"]["lsl"] == 0.8
    assert mapping["metadata"]["spec_limits"]["usl"] == 2.2
    assert mapping["metadata"]["normality"]["method"] in {"shapiro", "normaltest"}
    assert json.loads(json.dumps(mapping)) == mapping


def test_metroliza_native_histogram_payload_adapter_preserves_enriched_metadata() -> None:
    payload = histogram_from_metroliza_native_payload(
        {
            "values": [1.0, 2.0, 2.5, 3.0, 4.0],
            "title": "Diameter",
            "bin_count": 4,
            "x_view": {"min": 0.0, "max": 5.0},
            "limits": {"lsl": 0.5, "nominal": 2.5, "usl": 4.5},
            "style": {"axis_label_x": "Measurement", "axis_label_y": "Count"},
            "mean_line": {"value": 2.5, "color": "#111111", "linewidth": 1.3, "dash": [8, 5]},
            "summary_table_rows": [
                {"label": "Count", "value": "5", "row_kind": "summary_metric"},
                {"label": "Model", "value": "Normal", "row_kind": "summary_metric", "section_break_before": True},
            ],
            "visual_metadata": {
                "summary_stats_table": {"title": "Parameter"},
                "annotation_rows": [{"text": "LSL", "kind": "lsl", "x": 0.5, "row_index": 0}],
                "specification_lines": [
                    {"id": "lsl", "label": "LSL", "value": 0.5, "enabled": True},
                    {"id": "nominal", "label": "Nominal", "value": 2.5, "enabled": True},
                    {"id": "usl", "label": "USL", "value": 4.5, "enabled": True},
                ],
                "modeled_overlays": {"rows": [{"kind": "curve_note", "label": "Dashed KDE: descriptive only"}]},
            },
        }
    )

    mapping = to_mapping(histogram_payload_to_resolved_spec(payload))

    assert payload.density is False
    assert len(payload.bin_values) == 4
    assert mapping["title"]["text"] == "Diameter"
    assert mapping["axes"][0]["label"] == "Measurement bins"
    assert mapping["axes"][1]["label"] == "Count"
    assert mapping["axes"][0]["minimum"] == 0.0
    assert mapping["axes"][0]["maximum"] == 5.0
    assert [row["cells"][0]["text"] for row in mapping["table"]["rows"]] == [
        "Count",
        "Model",
        "Dashed KDE: descriptive only",
    ]
    assert mapping["table"]["rows"][1]["metadata"]["section_break_before"] is True
    assert mapping["table"]["rows"][2]["metadata"]["source"] == "modeled_overlay_rows"
    assert mapping["annotations"][0]["text"] == "LSL"
    assert mapping["metadata"]["payload_metadata"]["modeled_overlay_rows"][0]["label"] == "Dashed KDE: descriptive only"


def test_metroliza_native_histogram_payload_adapter_preserves_overlay_curves_and_leaders() -> None:
    payload = histogram_from_metroliza_native_payload(
        {
            "values": [1.0, 2.0, 2.5, 3.0, 4.0],
            "title": "Diameter",
            "bin_count": 4,
            "x_view": {"min": 0.0, "max": 5.0},
            "limits": {"lsl": 0.5, "nominal": 2.5, "usl": 4.5},
            "visual_metadata": {
                "annotation_rows": [{"text": "USL", "kind": "usl", "x": 4.5, "row_index": 1, "text_y_axes": 1.05}],
                "modeled_overlays": {
                    "rows": [
                        {"kind": "curve", "x": [0.0, 1.0, 2.0], "y": [0.0, 2.0, 0.0], "color": "#f97316", "linewidth": 1.4},
                        {
                            "kind": "curve",
                            "x": [4.0, 4.5, 5.0],
                            "y": [0.0, 0.4, 0.0],
                            "color": "#dc2626",
                            "fill_color": "#dc2626",
                            "fill_alpha": 0.12,
                            "fill_to_baseline": True,
                            "alpha": 0.0,
                        },
                        {"kind": "curve_note", "label": "Dashed KDE: descriptive only"},
                    ]
                },
            },
        }
    )

    mapping = to_mapping(histogram_payload_to_resolved_spec(payload))

    assert [curve["kind"] for curve in mapping["curves"]] == ["modeled_overlay", "modeled_overlay"]
    assert mapping["curves"][1]["fill_to_baseline"] is True
    assert mapping["curves"][1]["fill_color"] == "#dc2626"
    assert mapping["curves"][1]["fill_alpha"] == 0.12
    assert mapping["annotation_lines"][0]["kind"] == "annotation_leader"
    assert mapping["annotation_lines"][0]["coordinate_space"] == "canvas"
    assert mapping["annotations"][0]["metadata"]["box_y"] == 1.05
    assert mapping["annotations"][1]["role"] == "curve_note"


def test_metroliza_dashboard_payload_adapter_builds_interactive_plotly_specs() -> None:
    violin_spec = plotly_spec_from_metroliza_dashboard_payload(
        {
            "type": "distribution",
            "render_mode": "violin",
            "labels": ["A", "B"],
            "series": [[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]],
            "limits": {"lsl": 0.0, "nominal": 2.5, "usl": 5.0},
        },
        title="Diameter violin",
        theme="dark",
    )
    iqr_spec = plotly_spec_from_metroliza_dashboard_payload(
        {
            "type": "iqr",
            "labels": ["A", "B"],
            "series": [[1.0, 2.0, 3.0, 100.0], [2.0, 3.0, 4.0, 5.0]],
            "limits": {"lsl": 0.0, "nominal": 2.5, "usl": 5.0},
        },
        title="Diameter IQR",
    )

    assert violin_spec["metadata"]["backend"] == "plotly"
    assert violin_spec["metadata"]["interactive_enabled"] is True
    assert violin_spec["metadata"]["theme"]["name"] == "dark"
    assert all(trace.get("meta", {}).get("contains_raw_points") is not True for trace in violin_spec["data"])
    violin_kinds = {trace.get("meta", {}).get("kind") for trace in violin_spec["data"]}
    assert {"mean", "minimum", "maximum", "sigma_lower", "sigma_upper"}.issubset(violin_kinds)
    assert iqr_spec["metadata"]["kind"] == "iqr"
    assert "staticPlot" not in iqr_spec["config"]
    assert any(trace.get("name") == "Outliers" for trace in iqr_spec["data"])


def test_metroliza_chart_artifact_builds_histogram_plotly_png_and_stats() -> None:
    artifact = chart_artifact_from_metroliza_payload(
        {
            "type": "histogram",
            "title": "Diameter distribution",
            "values": [9.8, 10.0, 10.2, 10.1, 9.9],
            "limits": {"lsl": 9.5, "nominal": 10.0, "usl": 10.5},
        },
        target="workbook_image",
        include_plotly=True,
        include_png=True,
    )

    assert artifact["chart_type"] == "histogram"
    assert artifact["backend"] == "hexafe-plotstats:matplotlib"
    assert artifact["plotly_spec"]["metadata"]["kind"] == "histogram"
    assert artifact["png_bytes"].startswith(b"\x89PNG")
    assert artifact["stats_tables"][0]["backend"] == "hexafe-plotstats"
    assert artifact["payload_summary"]["sample_count"] == 5


def test_metroliza_chart_artifact_builds_grouped_histogram_spec_and_excel_data() -> None:
    artifact = chart_artifact_from_metroliza_payload(
        {
            "type": "histogram",
            "title": "Grouped diameter",
            "groups": [
                {"group": "A", "values": [1.0, 1.2, 1.4]},
                {"group": "B", "values": [2.0, 2.2, 2.4]},
            ],
            "limits": {"lsl": 0.5, "nominal": 1.5, "usl": 2.8},
        },
        target="html_dashboard",
        include_plotly=True,
    )

    assert artifact["plotly_spec"]["metadata"]["data_policy"] == "grouped_histogram_bins"
    assert artifact["plotly_spec"]["metadata"]["histogram_y_mode"] == "relative_percent"
    assert artifact["plotly_spec"]["metadata"]["interactive_enabled"] is True
    assert "staticPlot" not in artifact["plotly_spec"]["config"]
    group_shares = {
        trace["name"]: sum(trace["y"])
        for trace in artifact["plotly_spec"]["data"]
    }
    assert group_shares == {"A": pytest.approx(1.0), "B": pytest.approx(1.0)}
    assert [trace["name"] for trace in artifact["plotly_spec"]["data"]] == ["A", "B"]
    assert len(artifact["excel_chart_data"]["series"]) == 2
    assert artifact["payload_summary"]["group_count"] == 2


def test_metroliza_chart_artifact_builds_trend_and_trace_payload_specs() -> None:
    trend_artifact = chart_artifact_from_metroliza_payload(
        {
            "type": "trend",
            "title": "Diameter trend",
            "x_values": [1, 2, 3],
            "y_values": [10.0, 10.1, 10.2],
            "horizontal_limits": [9.5, 10.5],
            "limits": {"lsl": 9.5, "usl": 10.5},
            "x_label": "Datetime",
            "y_label": "Diameter",
        },
        target="html_dashboard",
        include_plotly=True,
    )
    time_series_artifact = chart_artifact_from_metroliza_payload(
        {
            "type": "time_series",
            "title": "Process values",
            "traces": [{"type": "scatter", "mode": "markers", "name": "Line A", "x": [1], "y": [2]}],
        },
        target="html_dashboard",
        include_plotly=True,
    )

    assert trend_artifact["plotly_spec"]["metadata"]["kind"] == "scatter"
    assert trend_artifact["plotly_spec"]["layout"]["xaxis"]["title"]["text"] == "Datetime"
    assert trend_artifact["plotly_spec"]["layout"]["yaxis"]["title"]["text"] == "Diameter"
    reference_names = {
        trace.get("name")
        for trace in trend_artifact["plotly_spec"]["data"]
        if str(trace.get("meta", {}).get("kind", "")).startswith("reference_")
    }
    assert {"LSL", "USL", "Mean"}.issubset(reference_names)
    assert any(
        trace.get("meta", {}).get("kind") == "trend" and trace["opacity"] <= 0.35
        for trace in trend_artifact["plotly_spec"]["data"]
    )
    assert time_series_artifact["plotly_spec"]["metadata"]["trace_count"] == 1


def test_renderer_backend_default_behavior_stays_matplotlib_first() -> None:
    assert inspect.signature(render_histogram).parameters["backend"].default == "matplotlib"

    payload = histogram_payload([1, 2, 3, 4, 5], SpecLimits(lsl=0.5, usl=5.5))
    result = render_histogram(payload)

    assert result.metadata["kind"] == "histogram"
    result.fig.clf()


def test_violin_payload_keeps_group_metadata() -> None:
    payload = violin_payload({"left": [1, 2, 3], "right": [4, 5, 6]}, SpecLimits(lsl=0.0, usl=10.0))

    assert [group.label for group in payload.groups] == ["left", "right"]
    assert payload.groups[0].summary.count == 3
    assert "mean" in payload.groups[0].annotations


def test_scatter_payload_auto_mode_and_trend_flag() -> None:
    payload = scatter_payload(range(12), range(12), config=ScatterConfig(include_trend=True, rasterized_threshold=5, hexbin_threshold=10))

    assert payload.mode == "hexbin"
    assert payload.include_trend is True
    assert payload.simplified_annotations is False


def test_matplotlib_renderers_smoke() -> None:
    hist = histogram_payload([1, 2, 3, 4, 5], SpecLimits(lsl=0.5, usl=5.5))
    violin = violin_payload({"a": [1, 2, 3], "b": [2, 3, 4]})
    scatter = scatter_payload([1, 2, 3], [3, 2, 1], config=ScatterConfig(include_trend=True))

    hist_result = render_histogram(hist)
    violin_result = render_violin(violin)
    scatter_result = render_scatter(scatter)

    for result in (hist_result, violin_result, scatter_result):
        result.fig.canvas.draw()
        assert result.fig is not None
        assert result.ax is not None
        result.fig.clf()


def test_renderer_backend_selection_defaults_to_matplotlib_and_exposes_rust() -> None:
    hist = histogram_payload([1, 2, 3, 4, 5], SpecLimits(lsl=0.5, usl=5.5))

    result = render_histogram(hist)
    result.fig.canvas.draw()
    assert result.metadata["kind"] == "histogram"
    result.fig.clf()

    if native_backend_available():
        rust_result = render_histogram(hist, backend="rust")
        assert rust_result.backend == "rust"
        assert rust_result.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    else:
        with pytest.raises(RendererBackendUnavailable):
            render_histogram(hist, backend="rust")


def test_render_histogram_png_unavailable_behavior() -> None:
    payload = histogram_payload([1, 2, 3, 4, 5], SpecLimits(lsl=0.5, usl=5.5))

    if native_backend_available():
        result = render_histogram_png(payload)
        assert result.backend == "rust"
        assert result.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    else:
        with pytest.raises(RendererBackendUnavailable, match="rust renderer for histogram is not installed yet"):
            render_histogram_png(payload)


def test_pandas_adapter_if_installed() -> None:
    pd = pytest.importorskip("pandas")

    from hexafe_plotstats.adapters.pandas import scatter_from_frame, series_histogram_payload

    frame = pd.DataFrame({"x": [1.0, 2.0, None, 4.0], "y": [4.0, 3.0, 2.0, None], "value": [1.0, 2.0, 3.0, 4.0]})
    limits = SpecLimits(lsl=0.5, usl=4.5)

    summary = series_summary(frame["value"], limits)
    hist = series_histogram_payload(frame["value"], limits)
    scatter = scatter_from_frame(frame, "x", "y")

    assert summary.count == 4
    assert hist.summary.count == 4
    assert scatter.x == (1.0, 2.0)
    assert scatter.y == (4.0, 3.0)
