from __future__ import annotations

import math
import json
from dataclasses import replace

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg", force=True)

from hexafe_plotstats import (
    RendererBackendUnavailable,
    SpecLimits,
    build_histogram_payload,
    build_iqr_payload,
    build_scatter_payload,
    build_violin_payload,
    get_locale,
    get_theme,
    renderer_backend_available,
    renderer_backend_capabilities,
    render_histogram,
    render_histogram_png,
    render_iqr,
    render_iqr_png,
    render_scatter,
    render_scatter_png,
    render_scatter_trend_png,
    render_violin,
    render_violin_png,
    set_locale,
    set_theme,
    translate,
)
from hexafe_plotstats.models import ChartRenderResult, HistogramConfig, IQRConfig, ScatterConfig, TableRow, ViolinConfig
from hexafe_plotstats.specs import (
    histogram_payload_to_resolved_spec,
    iqr_payload_to_resolved_spec,
    scatter_payload_to_resolved_spec,
    to_mapping,
    violin_payload_to_resolved_spec,
)
from hexafe_plotstats.renderers.plotly import (
    histogram_payload_to_plotly_spec,
    iqr_payload_to_plotly_spec,
    scatter_payload_to_plotly_spec,
    violin_payload_to_plotly_spec,
)
import hexafe_plotstats.renderers.rust.backend as rust_backend


def _close_result(result) -> None:
    result.fig.canvas.draw()
    result.fig.clf()


def test_backend_capabilities_keep_matplotlib_default_and_rust_optional() -> None:
    capabilities = {entry.backend: entry for entry in renderer_backend_capabilities()}
    rust_available = rust_backend.native_backend_available()

    assert renderer_backend_available("matplotlib") is True
    assert renderer_backend_available("rust") is rust_available
    assert isinstance(renderer_backend_available("plotly"), bool)
    assert capabilities["matplotlib"].available is True
    assert capabilities["matplotlib"].default is True
    assert capabilities["rust"].available is rust_available
    assert capabilities["rust"].default is False
    assert capabilities["plotly"].default is False
    if rust_available:
        assert "installed" in capabilities["rust"].message
    else:
        assert "explicit opt-in" in capabilities["rust"].message


def test_matplotlib_public_renderers_cover_supported_chart_families() -> None:
    limits = SpecLimits(lsl=0.0, nominal=2.5, usl=5.0)
    histogram = build_histogram_payload([1, 2, 2, 3, 4], limits)
    violin = build_violin_payload({"A": [1, 2, 3], "B": [2, 3, 4]}, limits)
    iqr = build_iqr_payload({"A": [1, 2, 3], "B": [2, 3, 7]}, limits)
    scatter = build_scatter_payload([1, 2, 3, 4], [2, 4, 6, 8], ScatterConfig(include_trend=True))

    results = (
        render_histogram(histogram),
        render_violin(violin),
        render_iqr(iqr),
        render_scatter(scatter),
    )

    assert [result.metadata["kind"] for result in results] == ["histogram", "violin", "iqr", "scatter"]
    for result in results:
        _close_result(result)


def test_matplotlib_iqr_and_violin_spec_limits_are_horizontal() -> None:
    limits = SpecLimits(lsl=0.0, nominal=2.5, usl=5.0)
    iqr = build_iqr_payload({"A": [1, 2, 3], "B": [2, 3, 7]}, limits)
    violin = build_violin_payload({"A": [1, 2, 3], "B": [2, 3, 4]}, limits)

    results = (render_iqr(iqr), render_violin(violin))

    try:
        for result in results:
            horizontal_values = []
            for line in result.ax.lines:
                ydata = [float(value) for value in line.get_ydata()]
                if len(ydata) >= 2 and math.isclose(ydata[0], ydata[1], rel_tol=0.0, abs_tol=1e-12):
                    horizontal_values.append(ydata[0])
            for expected in (limits.lsl, limits.nominal, limits.usl):
                assert any(math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-12) for value in horizontal_values)
    finally:
        for result in results:
            _close_result(result)


def test_histogram_payload_handles_empty_nonfinite_and_constant_inputs() -> None:
    empty = build_histogram_payload([], config=HistogramConfig(density=False, include_fit=False))
    nonfinite = build_histogram_payload([math.nan, math.inf, -math.inf], config=HistogramConfig(density=False, include_fit=False))
    constant = build_histogram_payload([5, 5, 5], config=HistogramConfig(density=False, include_fit=False))
    constant_with_specs = build_histogram_payload(
        [5, 5, 5],
        SpecLimits(lsl=4.0, usl=6.0),
        config=HistogramConfig(density=False, include_fit=False),
    )

    assert empty.summary.count == 0
    assert empty.bin_edges == (0.0, 1.0)
    assert empty.bin_values == (0.0,)
    assert "capability requires at least two finite numeric values" in empty.warnings

    assert nonfinite.summary.count == 0
    assert nonfinite.bin_edges == (0.0, 1.0)
    assert nonfinite.bin_values == (0.0,)

    assert constant.summary.count == 3
    assert constant.bin_edges == (4.5, 5.5)
    assert constant.bin_values == (3.0,)
    assert "no specification limits supplied" in constant.warnings
    assert "capability is undefined for zero sample standard deviation" in constant_with_specs.warnings


def test_histogram_resolved_spec_preserves_metroliza_style_metadata() -> None:
    payload = build_histogram_payload(
        [1, 2, 2, 3, 4],
        SpecLimits(lsl=0.5, nominal=2.5, usl=4.5),
        config=HistogramConfig(density=False, include_fit=False),
        metadata={
            "title": "Diameter",
            "axis_labels": {"x": "Measurement", "y": "Count"},
            "x_view": {"min": 0.0, "max": 5.0},
            "summary_table_title": "Parameter",
            "mean_line": {"value": 2.4, "color": "#111111", "linewidth": 1.3, "dash": [8, 5]},
            "annotation_rows": [
                {"text": "LSL", "kind": "lsl", "color": "#dc2626", "x": 0.5, "row_index": 0, "text_y_axes": 1.01},
                {"text": "USL", "kind": "usl", "color": "#dc2626", "x": 4.5, "row_index": 1, "text_y_axes": 1.055},
            ],
        },
    )
    payload = type(payload)(
        **{
            **payload.__dict__,
            "table_rows": (
                TableRow("Count", "5", kind="summary_metric"),
                TableRow("Model", "Normal", kind="summary_metric", metadata={"section_break_before": True}),
            ),
        }
    )

    mapping = to_mapping(histogram_payload_to_resolved_spec(payload))

    assert mapping["schema_version"] == 1
    assert mapping["title"]["text"] == "Diameter"
    assert mapping["axes"][0]["label"] == "Measurement"
    assert mapping["axes"][1]["label"] == "Count"
    assert mapping["axes"][0]["minimum"] == 0.0
    assert mapping["axes"][0]["maximum"] == 5.0
    assert [line["label"] for line in mapping["spec_lines"]] == ["LSL", "Nominal", "USL"]
    assert mapping["mean_line"]["x0"] == 2.4
    assert mapping["mean_line"]["dash"] == [8.0, 5.0]
    assert [row["cells"][0]["text"] for row in mapping["table"]["rows"]] == ["Count", "Model"]
    assert mapping["table"]["rows"][1]["metadata"]["section_break_before"] is True
    assert [annotation["text"] for annotation in mapping["annotations"]] == ["LSL", "USL"]
    assert [line["kind"] for line in mapping["annotation_lines"]] == ["annotation_leader", "annotation_leader"]
    assert mapping["metadata"]["summary"]["count"] == 5
    assert mapping["metadata"]["capability"]["cpk"] is not None
    assert mapping["metadata"]["payload_metadata"]["x_view"] == {"min": 0.0, "max": 5.0}


def test_histogram_matplotlib_renderer_reflects_payload_semantics() -> None:
    payload = build_histogram_payload(
        [1, 2, 2, 3, 4],
        SpecLimits(lsl=0.5, usl=4.5),
        config=HistogramConfig(density=False, include_fit=False),
        metadata={"axis_labels": {"x": "Measurement", "y": "Count"}, "title": "Diameter"},
    )

    result = render_histogram(payload)

    assert result.ax.get_xlabel() == "Measurement"
    assert result.ax.get_ylabel() == "Count"
    assert result.ax.get_title() == "Diameter"
    assert len(result.ax.patches) == max(len(payload.bin_edges) - 1, 0)
    assert len(result.ax.lines) >= 2
    assert result.metadata["warnings"] == payload.warnings
    _close_result(result)


def test_histogram_native_dispatch_receives_resolved_mapping(monkeypatch) -> None:
    payload = build_histogram_payload(
        [1, 2, 3, 4],
        SpecLimits(lsl=0.5, usl=4.5),
        config=HistogramConfig(density=False, include_fit=False),
        metadata={"title": "Native handoff"},
    )
    captured = {}

    class NativeModule:
        @staticmethod
        def render_histogram_png(mapping):
            captured["mapping"] = mapping
            return {"png_bytes": b"png", "backend": "rust", "metadata": {"chart": "histogram", "source": "test"}}

    monkeypatch.setattr(rust_backend, "_load_native_module", lambda: NativeModule)

    result = render_histogram_png(payload)

    assert result.png_bytes == b"png"
    assert result.backend == "rust"
    assert result.metadata["chart"] == "histogram"
    assert result.metadata["source"] == "test"
    assert set(result.metadata["timings_ms"]) == {
        "python_native_arg_ms",
        "python_native_call_ms",
        "python_resolve_ms",
        "python_total_ms",
    }
    assert isinstance(captured["mapping"], dict)
    assert captured["mapping"] == to_mapping(histogram_payload_to_resolved_spec(payload))


def test_histogram_native_dispatch_can_select_render_profile(monkeypatch) -> None:
    payload = build_histogram_payload(
        [1, 2, 3, 4],
        SpecLimits(lsl=0.5, usl=4.5),
        config=HistogramConfig(density=False, include_fit=False),
        metadata={"title": "Native profile"},
    )
    captured = {}

    class NativeModule:
        @staticmethod
        def render_histogram_png(mapping):
            captured["mapping"] = mapping
            return {"png_bytes": b"png", "backend": "rust", "metadata": {"chart": "histogram"}}

    monkeypatch.setattr(rust_backend, "_load_native_module", lambda: NativeModule)

    result = render_histogram_png(payload, profile="compact")

    assert result.png_bytes == b"png"
    assert captured["mapping"]["metadata"]["render_profile"] == "compact"

    render_histogram(payload, backend="rust", profile="debug")
    assert captured["mapping"]["metadata"]["render_profile"] == "debug"


def test_native_render_profile_rejects_unknown_values(monkeypatch) -> None:
    payload = build_histogram_payload([1, 2, 3])

    class NativeModule:
        @staticmethod
        def render_histogram_png(mapping):
            return {"png_bytes": b"png", "backend": "rust", "metadata": {"chart": "histogram"}}

    monkeypatch.setattr(rust_backend, "_load_native_module", lambda: NativeModule)

    with pytest.raises(ValueError, match="unsupported native render profile"):
        render_histogram_png(payload, profile="tiny")  # type: ignore[arg-type]


def test_iqr_payload_resolves_to_pure_chart_spec_mapping() -> None:
    payload = build_iqr_payload(
        {"A": [1, 2, 3, 100], "B": [2, 3, 4, 5]},
        SpecLimits(lsl=0.0, nominal=2.5, usl=6.0),
    )

    mapping = to_mapping(iqr_payload_to_resolved_spec(payload))

    assert mapping["schema_version"] == 1
    assert mapping["chart_type"] == "iqr"
    assert mapping["boxes"][0]["label"] == "A"
    assert mapping["boxes"][0]["position"] == 1.0
    assert mapping["outlier_markers"][0]["kind"] == "outlier"
    assert mapping["outlier_markers"][0]["y"] == 100.0
    assert [line["label"] for line in mapping["spec_lines"]] == ["LSL", "Nominal", "USL"]
    assert mapping["metadata"]["group_count"] == 2


def test_violin_payload_resolves_to_pure_chart_spec_mapping() -> None:
    payload = build_violin_payload(
        {"A": [1, 2, 3], "B": [2, 3, 4]},
        SpecLimits(lsl=0.0, nominal=2.5, usl=5.0),
    )

    mapping = to_mapping(violin_payload_to_resolved_spec(payload))

    assert mapping["schema_version"] == 1
    assert mapping["chart_type"] == "violin"
    assert mapping["groups"][0]["label"] == "A"
    assert mapping["groups"][0]["values"] == []
    assert mapping["groups"][0]["metadata"]["raw_values_omitted"] is True
    assert len(mapping["groups"][0]["body_points"]) >= 3
    assert mapping["annotation_markers"][0]["kind"] == "mean"
    assert [line["label"] for line in mapping["spec_lines"]] == ["LSL", "Nominal", "USL"]
    assert mapping["metadata"]["group_count"] == 2


def test_large_grouped_payloads_keep_arrays_and_resolved_violin_omits_raw_values() -> None:
    values = np.linspace(1.0, 10.0, 60_000)

    iqr_payload = build_iqr_payload({"A": values})
    violin_payload = build_violin_payload({"A": values})

    assert isinstance(iqr_payload.groups[0].values, np.ndarray)
    assert isinstance(violin_payload.groups[0].values, np.ndarray)

    mapping = to_mapping(violin_payload_to_resolved_spec(violin_payload))

    assert mapping["groups"][0]["values"] == []
    assert mapping["groups"][0]["metadata"]["source_count"] == 60_000
    assert mapping["groups"][0]["metadata"]["density_method"] == "histogram_density"
    assert len(json.dumps(mapping)) < 50_000


def test_violin_sigma_policy_resolves_to_explicit_lines_and_extrema_markers() -> None:
    payload = build_violin_payload(
        {"A": [1, 2, 3, 4, 5], "B": [2, 4, 6, 8, 10]},
        SpecLimits(lsl=0.0, nominal=5.0, usl=12.0),
        config=ViolinConfig(sigma_policy="both_3_sigma"),
    )

    mapping = to_mapping(violin_payload_to_resolved_spec(payload))

    sigma_lines = [line for line in mapping["spec_lines"] if str(line["kind"]).startswith("sigma_")]
    assert [line["kind"] for line in sigma_lines] == ["sigma_lower", "sigma_upper", "sigma_lower", "sigma_upper"]
    assert all(line["stroke"] == "#7c3aed" for line in sigma_lines)
    marker_kinds = [marker["kind"] for marker in mapping["annotation_markers"]]
    assert "minimum" in marker_kinds
    assert "maximum" in marker_kinds


def test_iqr_sigma_policy_resolves_annotations_and_axis_labels() -> None:
    payload = build_iqr_payload(
        {"Line A": [1, 2, 3, 4, 5]},
        config=IQRConfig(sigma_policy="both_3_sigma"),
    )
    payload = replace(payload, metadata={**payload.metadata, "axis_labels": {"x": "Groups", "y": "Diameter"}})

    mapping = to_mapping(iqr_payload_to_resolved_spec(payload))

    sigma_lines = [line for line in mapping["spec_lines"] if str(line["kind"]).startswith("sigma_")]
    marker_kinds = {marker["kind"] for marker in mapping["annotation_markers"]}
    assert {axis["orientation"]: axis["label"] for axis in mapping["axes"]} == {"x": "Groups", "y": "Diameter"}
    assert [line["kind"] for line in sigma_lines] == ["sigma_lower", "sigma_upper"]
    assert {"mean", "minimum", "maximum"}.issubset(marker_kinds)


def test_theme_tick_and_locale_api_resolve_into_specs() -> None:
    original_theme = get_theme()
    original_locale = get_locale()
    try:
        set_theme("dark")
        payload = build_histogram_payload([1, 2, 3, 4], metadata={"ticks_count": 4})
        mapping = to_mapping(histogram_payload_to_resolved_spec(payload))

        assert mapping["canvas"]["background"] == "#111827"
        assert mapping["metadata"]["theme"]["name"] == "dark"
        assert len(mapping["axes"][0]["tick_values"]) == 4

        set_locale("pl")
        localized = build_histogram_payload([1, 2, 3, 4])
        labels = [row.label for row in localized.table_rows]

        assert translate("mean") == "Srednia"
        assert "Srednia" in labels
    finally:
        set_theme(original_theme)
        set_locale(original_locale)


def test_histogram_plotly_spec_preserves_bars_limits_and_table() -> None:
    payload = build_histogram_payload(
        [1, 2, 2, 3, 4],
        SpecLimits(lsl=0.5, nominal=2.5, usl=4.5),
        config=HistogramConfig(density=False, include_fit=False),
        metadata={"title": "Diameter", "axis_labels": {"x": "Measurement", "y": "Count"}},
    )

    spec = histogram_payload_to_plotly_spec(payload)

    assert spec["metadata"]["kind"] == "histogram"
    assert spec["metadata"]["default_render_mode"] == "static"
    assert spec["metadata"]["interactive_enabled"] is False
    assert spec["config"]["staticPlot"] is True
    assert spec["layout"]["xaxis"]["title"]["text"] == "Measurement"
    assert spec["layout"]["yaxis"]["title"]["text"] == "Count"
    traces_by_type = {trace["type"]: trace for trace in spec["data"]}
    assert traces_by_type["bar"]["name"] == "Histogram"
    assert len(traces_by_type["bar"]["x"]) == len(payload.bin_values)
    assert any(trace.get("name") == "LSL" for trace in spec["data"])
    assert any(trace.get("type") == "table" and trace["meta"]["row_count"] >= 3 for trace in spec["data"])


def test_iqr_plotly_spec_uses_resolved_box_statistics() -> None:
    payload = build_iqr_payload(
        {"A": [1, 2, 3, 100], "B": [2, 3, 4, 5]},
        SpecLimits(lsl=0.0, nominal=2.5, usl=6.0),
    )

    spec = iqr_payload_to_plotly_spec(payload)

    box_trace = next(trace for trace in spec["data"] if trace["type"] == "box")
    assert box_trace["meta"]["data_policy"] == "resolved_box_statistics"
    assert box_trace["meta"]["contains_raw_points"] is False
    assert box_trace["x"] == [1.0, 2.0]
    assert spec["layout"]["xaxis"]["ticktext"] == ["A", "B"]
    assert len(box_trace["q1"]) == 2
    assert "y" not in box_trace
    assert "whisker low=%{customdata[5]}" in box_trace["hovertemplate"]
    assert any(trace.get("name") == "Mean" for trace in spec["data"])
    assert any(trace.get("name") == "Outliers" for trace in spec["data"])


def test_violin_plotly_spec_uses_resolved_body_polygons() -> None:
    payload = build_violin_payload(
        {"A": [1, 2, 3], "B": [2, 3, 4]},
        SpecLimits(lsl=0.0, nominal=2.5, usl=5.0),
    )

    spec = violin_payload_to_plotly_spec(payload)

    body_traces = [trace for trace in spec["data"] if trace.get("fill") == "toself"]
    assert spec["metadata"]["default_render_mode"] == "static"
    assert spec["metadata"]["interactive_enabled"] is False
    assert spec["config"]["staticPlot"] is True
    assert len(body_traces) == 2
    assert all(trace["meta"]["data_policy"] == "resolved_violin_body" for trace in body_traces)
    assert all(trace["meta"]["contains_raw_points"] is False for trace in body_traces)
    assert all(len(trace["x"]) < 250 for trace in body_traces)
    assert any(trace["meta"].get("kind") == "mean" for trace in spec["data"])
    assert any(trace["meta"].get("kind") == "minimum" for trace in spec["data"])
    assert any(trace["meta"].get("kind") == "maximum" for trace in spec["data"])


def test_violin_plotly_spec_exposes_sigma_reference_lines() -> None:
    payload = build_violin_payload(
        {"A": [1, 2, 3, 4, 5], "B": [2, 3, 4, 5, 6]},
        config=ViolinConfig(sigma_policy="both_3_sigma"),
    )

    spec = violin_payload_to_plotly_spec(payload)
    line_kinds = {trace.get("meta", {}).get("kind") for trace in spec["data"] if trace.get("mode") == "lines"}

    assert "sigma_lower" in line_kinds
    assert "sigma_upper" in line_kinds


def test_histogram_and_violin_plotly_specs_can_opt_into_interactivity() -> None:
    histogram = build_histogram_payload([1, 2, 3])
    violin = build_violin_payload({"A": [1, 2, 3]})

    histogram_spec = histogram_payload_to_plotly_spec(histogram, static=False)
    violin_spec = violin_payload_to_plotly_spec(violin, static=False)

    assert histogram_spec["metadata"]["default_render_mode"] == "interactive"
    assert violin_spec["metadata"]["default_render_mode"] == "interactive"
    assert "staticPlot" not in histogram_spec["config"]
    assert "staticPlot" not in violin_spec["config"]
    assert not any(trace.get("type") == "table" for trace in histogram_spec["data"])


def test_histogram_plotly_spec_can_normalize_dashboard_frequency() -> None:
    payload = build_histogram_payload(
        [1, 1, 2, 3],
        config=HistogramConfig(density=False, include_fit=False),
        metadata={"histogram_y_mode": "relative_percent"},
    )

    spec = histogram_payload_to_plotly_spec(payload, static=False)
    bar_trace = next(trace for trace in spec["data"] if trace["type"] == "bar")

    assert spec["metadata"]["histogram_y_mode"] == "relative_percent"
    assert spec["layout"]["yaxis"]["title"]["text"] == "Frequency (%)"
    assert spec["layout"]["yaxis"]["tickformat"] == ".0%"
    assert spec["layout"]["yaxis"]["range"][1] <= 1.0
    assert sum(bar_trace["y"]) == pytest.approx(1.0)
    assert "frequency=%{customdata[3]:.2%}" in bar_trace["hovertemplate"]


def test_histogram_plotly_relative_frequency_uses_counts_for_density_payloads() -> None:
    payload = build_histogram_payload(
        [1, 1, 1, 2, 3],
        config=HistogramConfig(bins=3, density=True, include_fit=False),
        metadata={"histogram_y_mode": "relative_percent"},
    )

    spec = histogram_payload_to_plotly_spec(payload, static=False)
    bar_trace = next(trace for trace in spec["data"] if trace["type"] == "bar")

    assert max(bar_trace["y"]) == pytest.approx(0.6)
    assert spec["layout"]["yaxis"]["range"][1] < 0.8


def test_scatter_payload_resolves_to_pure_chart_spec_mapping_with_trend() -> None:
    payload = build_scatter_payload(
        [1, 2, 3, 4],
        [2, 4, 6, 8],
        ScatterConfig(include_trend=True),
    )

    mapping = to_mapping(scatter_payload_to_resolved_spec(payload))

    assert mapping["schema_version"] == 1
    assert mapping["chart_type"] == "scatter"
    assert len(mapping["markers"]) == 4
    assert mapping["markers"][0]["x"] == 1.0
    assert mapping["markers"][0]["y"] == 2.0
    assert mapping["trend_line"]["kind"] == "trend"
    assert mapping["trend_line"]["y0"] == pytest.approx(2.0)
    assert mapping["trend_line"]["y1"] == pytest.approx(8.0)
    assert mapping["metadata"]["include_trend"] is True


def test_scatter_plotly_spec_renders_subtle_trend_when_enabled() -> None:
    payload = build_scatter_payload(
        [1, 2, 3, 4],
        [2, 4, 6, 8],
        ScatterConfig(include_trend=True),
        metadata={
            "x_label": "Datetime",
            "y_label": "Diameter",
            "reference_lines": [
                {"label": "LSL", "kind": "lsl", "value": 1.5},
                {"label": "USL", "kind": "usl", "value": 8.5},
            ],
        },
    )

    spec = scatter_payload_to_plotly_spec(payload)
    trend_trace = next(trace for trace in spec["data"] if trace.get("meta", {}).get("kind") == "trend")
    reference_names = {trace.get("name") for trace in spec["data"] if str(trace.get("meta", {}).get("kind", "")).startswith("reference_")}

    assert trend_trace["line"]["width"] <= 1.1
    assert trend_trace["opacity"] <= 0.35
    assert spec["layout"]["xaxis"]["title"]["text"] == "Datetime"
    assert spec["layout"]["yaxis"]["title"]["text"] == "Diameter"
    assert {"LSL", "USL"}.issubset(reference_names)


def test_hexbin_scatter_resolves_explicit_cells() -> None:
    payload = build_scatter_payload(
        range(20),
        range(20),
        ScatterConfig(mode="hexbin", gridsize=5),
    )

    mapping = to_mapping(scatter_payload_to_resolved_spec(payload))

    assert mapping["schema_version"] == 1
    assert mapping["chart_type"] == "scatter"
    assert mapping["markers"] == []
    assert mapping["hex_cells"]
    assert all(len(cell["points"]) == 6 for cell in mapping["hex_cells"])
    assert mapping["metadata"]["mode"] == "hexbin"
    assert mapping["metadata"]["data_policy"] == "aggregated_hexbin"
    assert [layer["role"] for layer in mapping["metadata"]["interactive_layers"]] == [
        "interactive_aggregate",
        "static_raw_overlay",
    ]
    assert mapping["metadata"]["interactive_layers"][1]["legend"]["group"] == "scatter_raw"


def test_large_hexbin_scatter_resolved_mapping_is_bounded_by_cell_count() -> None:
    count = 100_000
    payload = build_scatter_payload(
        np.linspace(0.0, 100.0, count),
        np.sin(np.linspace(0.0, 30.0, count)),
        ScatterConfig(mode="hexbin", gridsize=50),
    )

    mapping = to_mapping(scatter_payload_to_resolved_spec(payload))

    assert mapping["markers"] == []
    assert mapping["marker_batches"] == []
    assert len(mapping["hex_cells"]) <= 50 * int(round(50 / math.sqrt(3.0)))
    assert mapping["metadata"]["point_count"] == count
    assert mapping["metadata"]["data_policy"] == "aggregated_hexbin"
    assert mapping["metadata"]["interactive_layers"][0]["contains_raw_points"] is False
    assert mapping["metadata"]["interactive_layers"][1]["contains_raw_points"] is False
    assert len(json.dumps(mapping["hex_cells"])) < 500_000


@pytest.mark.parametrize(
    ("renderer", "payload", "chart_name"),
    [
        (render_histogram, build_histogram_payload([1, 2, 3]), "histogram"),
        (render_violin, build_violin_payload({"A": [1, 2, 3]}), "violin"),
        (render_iqr, build_iqr_payload({"A": [1, 2, 3]}), "iqr"),
        (render_scatter, build_scatter_payload([1, 2, 3], [3, 2, 1]), "scatter"),
    ],
)
def test_rust_backend_flag_reports_install_state(renderer, payload, chart_name: str) -> None:
    if not rust_backend.native_backend_available():
        with pytest.raises(RendererBackendUnavailable, match=f"rust renderer for {chart_name} is not installed yet"):
            renderer(payload, backend="rust")
        return

    result = renderer(payload, backend="rust")

    assert isinstance(result, ChartRenderResult)
    assert result.backend == "rust"
    assert result.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    ("renderer", "payload", "chart_name"),
    [
        (render_histogram_png, build_histogram_payload([1, 2, 3]), "histogram"),
        (render_violin_png, build_violin_payload({"A": [1, 2, 3]}), "violin"),
        (render_iqr_png, build_iqr_payload({"A": [1, 2, 3]}), "iqr"),
        (render_scatter_png, build_scatter_payload([1, 2, 3], [3, 2, 1]), "scatter"),
        (
            render_scatter_trend_png,
            build_scatter_payload([1, 2, 3], [3, 2, 1], ScatterConfig(include_trend=True)),
            "scatter trend",
        ),
    ],
)
def test_rust_png_backend_is_explicit_and_reports_install_state(renderer, payload, chart_name: str) -> None:
    if not rust_backend.native_backend_available():
        with pytest.raises(RendererBackendUnavailable, match=f"rust renderer for {chart_name} is not installed yet"):
            renderer(payload)
        return

    result = renderer(payload)

    assert isinstance(result, ChartRenderResult)
    assert result.backend == "rust"
    assert result.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_unsupported_backend_names_raise_clear_errors() -> None:
    payload = build_histogram_payload([1, 2, 3])

    with pytest.raises(ValueError, match="unsupported renderer backend"):
        render_histogram(payload, backend="plotnine")

    with pytest.raises(ValueError, match="unsupported renderer backend"):
        render_histogram_png(payload, backend="matplotlib")


@pytest.mark.parametrize(
    ("renderer", "payload", "chart_name"),
    [
        (render_histogram, build_histogram_payload([1, 2, 3]), "histogram"),
        (render_violin, build_violin_payload({"A": [1, 2, 3]}), "violin"),
        (render_iqr, build_iqr_payload({"A": [1, 2, 3]}), "iqr"),
        (render_scatter, build_scatter_payload([1, 2, 3], [3, 2, 1]), "scatter"),
    ],
)
def test_plotly_backend_reports_optional_dependency_when_missing(renderer, payload, chart_name: str) -> None:
    if renderer_backend_available("plotly"):
        result = renderer(payload, backend="plotly")
        assert result.metadata["kind"] == chart_name
        assert result.metadata["backend"] == "plotly"
        return

    with pytest.raises(RendererBackendUnavailable, match="plotly renderer is not installed"):
        renderer(payload, backend="plotly")
