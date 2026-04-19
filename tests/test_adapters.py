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
    fit_distribution,
    histogram_payload,
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
from hexafe_plotstats.specs import histogram_payload_to_resolved_spec, to_mapping
from hexafe_plotstats.adapters.pandas import series_summary
from hexafe_plotstats.models.common import DistributionConfig, ScatterConfig, SpecLimits


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
    assert payload.bin_edges
    assert payload.bin_values
    assert any(row.label == "count" for row in payload.table_rows)


def test_histogram_resolved_spec_mapping_tracks_payload_parity_contract() -> None:
    payload = histogram_payload([1.0, 1.2, 1.4, 1.6, 2.0], SpecLimits(lsl=0.8, usl=2.2))

    resolved_spec = histogram_payload_to_resolved_spec(payload)
    mapping = to_mapping(resolved_spec)

    assert mapping["chart_type"] == "histogram"
    assert mapping["bars"][0]["x0"] == pytest.approx(payload.bin_edges[0])
    assert mapping["bars"][-1]["x1"] == pytest.approx(payload.bin_edges[-1])
    assert mapping["table"]["rows"][0]["cells"][0]["text"] == "count"
    assert mapping["metadata"]["spec_limits"]["lsl"] == 0.8
    assert mapping["metadata"]["spec_limits"]["usl"] == 2.2
    assert json.loads(json.dumps(mapping)) == mapping


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

    with pytest.raises(RendererBackendUnavailable):
        render_histogram(hist, backend="rust")


def test_render_histogram_png_unavailable_behavior() -> None:
    payload = histogram_payload([1, 2, 3, 4, 5], SpecLimits(lsl=0.5, usl=5.5))

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
