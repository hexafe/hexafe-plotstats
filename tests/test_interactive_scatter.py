from __future__ import annotations

import json

import numpy as np

from hexafe_plotstats import ScatterConfig, build_scatter_interactive_spec, build_scatter_payload, select_temporal_bucket
from hexafe_plotstats.renderers.plotly import scatter_payload_to_plotly_spec
from hexafe_plotstats.specs import to_mapping


def test_temporal_bucket_selection_uses_requested_range_and_target_points() -> None:
    assert select_temporal_bucket("2026-01-01T00:00:00", "2026-01-01T02:00:00", target_points=180) == "minute"
    assert select_temporal_bucket("2026-01-01", "2026-01-03", target_points=48) == "hour"
    assert select_temporal_bucket("2026-01-01", "2026-02-15", target_points=80) == "day"
    assert select_temporal_bucket("2026-01-01", "2027-01-01", target_points=60) == "week"


def test_large_temporal_scatter_interactive_spec_aggregates_and_keeps_raw_static() -> None:
    x = np.arange(np.datetime64("2026-01-01T00:00"), np.datetime64("2026-01-08T00:00"), np.timedelta64(1, "m"))
    y = np.sin(np.linspace(0.0, 12.0, x.size))

    spec = build_scatter_interactive_spec(
        x,
        y,
        x_view=("2026-01-01T00:00", "2026-01-08T00:00"),
        target_interactive_points=48,
        large_threshold=1_000,
    )
    mapping = to_mapping(spec)

    assert mapping["metadata"]["x_axis_type"] == "temporal"
    assert mapping["metadata"]["data_policy"] == "aggregated_temporal"
    assert mapping["metadata"]["interactive_contains_raw_points"] is False
    assert mapping["metadata"]["large_dataset"] is True
    assert [layer["role"] for layer in mapping["layers"]] == ["interactive_aggregate", "static_raw_overlay"]

    aggregate = mapping["layers"][0]
    raw = mapping["layers"][1]
    assert aggregate["metadata"]["bucket"] == "day"
    assert aggregate["metadata"]["generated_x_points"] <= 8
    assert aggregate["metadata"]["contains_raw_points"] is False
    assert "x" not in aggregate and "y" not in aggregate
    assert len(json.dumps(aggregate["points"])) < 20_000

    assert raw["metadata"]["rendering"] == "static_raster"
    assert raw["metadata"]["contains_raw_points"] is False
    assert raw["legend"]["show"] is True
    assert raw["legend"]["group"] == "scatter_raw"
    assert raw["legend"]["group"] != aggregate["legend"]["group"]


def test_numeric_scatter_interactive_spec_uses_bounded_aggregate_points() -> None:
    x = np.linspace(0.0, 100.0, 25_000)
    y = np.cos(x)

    spec = build_scatter_interactive_spec(x, y, target_interactive_points=75, large_threshold=1_000)
    mapping = to_mapping(spec)
    aggregate = mapping["layers"][0]

    assert mapping["metadata"]["x_axis_type"] == "numeric"
    assert mapping["metadata"]["data_policy"] == "aggregated_numeric"
    assert mapping["metadata"]["interactive_contains_raw_points"] is False
    assert aggregate["metadata"]["generated_x_points"] <= 75
    assert len(aggregate["points"]) <= 75
    assert mapping["layers"][1]["role"] == "static_raw_overlay"


def test_large_plotly_scatter_spec_uses_aggregate_trace_and_static_raw_legend() -> None:
    count = 100_000
    payload = build_scatter_payload(
        np.linspace(0.0, 100.0, count),
        np.sin(np.linspace(0.0, 30.0, count)),
        ScatterConfig(mode="hexbin", gridsize=50),
    )

    spec = scatter_payload_to_plotly_spec(payload)

    assert spec["metadata"]["data_policy"] == "aggregated_hexbin"
    assert spec["metadata"]["interactive_contains_raw_points"] is False
    assert spec["metadata"]["source_point_count"] == count
    assert "staticPlot" not in spec["config"]
    raw, aggregate = spec["data"]
    assert aggregate["name"] == "Aggregated density"
    assert len(aggregate["x"]) < 2_000
    assert len(aggregate["x"]) == len(aggregate["customdata"])
    assert aggregate["meta"]["contains_raw_points"] is False
    assert aggregate["marker"]["colorbar"]["title"] == "points per cell"
    assert raw["name"] == "Raw points"
    assert raw["type"] == "heatmap"
    assert raw["legendgroup"] == "scatter_raw"
    assert len(raw["x"]) < 300
    assert len(raw["y"]) < 300
    assert raw["showlegend"] is True
    assert raw["meta"]["role"] == "static_raw_overlay"
    assert raw["meta"]["contains_raw_points"] is False
    assert raw["meta"]["rendering"] == "static_raster_heatmap"
    assert raw["meta"]["source_point_count"] == count
    assert raw["meta"]["raster_payload_cell_count"] < count
