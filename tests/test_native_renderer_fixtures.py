from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hexafe_plotstats import (
    HistogramConfig,
    IQRConfig,
    ScatterConfig,
    SpecLimits,
    ViolinConfig,
    build_histogram_payload,
    build_iqr_payload,
    build_scatter_payload,
    build_violin_payload,
)
from hexafe_plotstats.models import TableRow
from hexafe_plotstats.specs import (
    histogram_payload_to_resolved_spec,
    iqr_payload_to_resolved_spec,
    scatter_payload_to_resolved_spec,
    to_mapping,
    violin_payload_to_resolved_spec,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "native_renderer_resolved_specs.json"
UPDATE_FIXTURES_ENV = "HEXAFE_PLOTSTATS_UPDATE_NATIVE_FIXTURES"


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(_canonical_fixture_value(value), indent=2, sort_keys=True) + "\n"


def _canonical_fixture_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_fixture_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_fixture_value(item) for item in value]
    if isinstance(value, float):
        return round(value, 8)
    return value


def _build_resolved_spec_fixtures() -> dict[str, Any]:
    limits = SpecLimits(lsl=0.5, nominal=2.5, usl=4.5)
    histogram_simple = build_histogram_payload(
        [1.0, 1.2, 1.8, 2.4, 2.9, 3.3, 3.9, 4.2],
        limits,
        config=HistogramConfig(bins=4, density=False, include_fit=False),
        metadata={"title": "Simple histogram", "axis_labels": {"x": "measurement", "y": "count"}},
    )
    histogram_metroliza = build_histogram_payload(
        [0.9, 1.1, 1.8, 2.2, 2.7, 3.4, 3.8, 4.1],
        limits,
        config=HistogramConfig(bins=4, density=False, include_fit=False),
        metadata={
            "title": "Metroliza enriched histogram",
            "axis_labels": {"x": "diameter", "y": "parts"},
            "x_view": {"min": 0.0, "max": 5.0},
            "mean_line": {"value": 2.5, "color": "#111111", "linewidth": 1.2, "dash": [8, 4]},
            "annotation_rows": [
                {"text": "LSL", "kind": "lsl", "color": "#dc2626", "x": 0.5, "row_index": 0, "text_y_axes": 1.01},
                {"text": "USL", "kind": "usl", "color": "#dc2626", "x": 4.5, "row_index": 1, "text_y_axes": 1.05},
            ],
            "summary_table_title": "Summary",
        },
    )
    histogram_metroliza = type(histogram_metroliza)(
        **{
            **histogram_metroliza.__dict__,
            "table_rows": (
                TableRow("Count", "8", kind="summary_metric"),
                TableRow("Mean", "2.500", kind="summary_metric"),
                TableRow("Model", "Normal", kind="summary_metric", metadata={"section_break_before": True}),
            ),
        }
    )
    scatter_trend = build_scatter_payload(
        [0.0, 1.0, 2.0, 3.0, 4.0],
        [1.0, 1.8, 3.2, 4.1, 5.0],
        ScatterConfig(include_trend=True),
    )
    iqr_outliers = build_iqr_payload(
        {"A": [1.0, 1.1, 1.2, 1.3, 5.0], "B": [2.0, 2.1, 2.2, 2.3, 2.4]},
        limits,
        IQRConfig(whis=1.0, showfliers=True),
    )
    violin_groups = build_violin_payload(
        {"A": [1.0, 1.4, 1.8, 2.0], "B": [2.2, 2.5, 2.9, 3.1], "C": [3.0, 3.4, 3.7, 4.0]},
        limits,
        ViolinConfig(show_mean=True, show_extrema=True, show_quartiles=True, sigma_policy="both_3_sigma"),
    )

    return {
        "schema": "hexafe_plotstats.native_renderer_resolved_specs",
        "schema_version": 1,
        "fixtures": {
            "histogram_simple": to_mapping(histogram_payload_to_resolved_spec(histogram_simple)),
            "histogram_metroliza": to_mapping(histogram_payload_to_resolved_spec(histogram_metroliza)),
            "scatter_trend": to_mapping(scatter_payload_to_resolved_spec(scatter_trend)),
            "iqr_outliers": to_mapping(iqr_payload_to_resolved_spec(iqr_outliers)),
            "violin_groups": to_mapping(violin_payload_to_resolved_spec(violin_groups)),
        },
    }


def load_resolved_spec_fixtures() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_native_renderer_resolved_spec_json_fixture_is_current() -> None:
    expected = _build_resolved_spec_fixtures()
    if os.environ.get(UPDATE_FIXTURES_ENV) == "1":
        FIXTURE_PATH.write_text(_canonical_json(expected), encoding="utf-8")

    actual = load_resolved_spec_fixtures()

    assert _canonical_json(actual) == _canonical_json(expected)


def test_native_renderer_resolved_spec_fixture_contract_shape() -> None:
    fixtures = load_resolved_spec_fixtures()["fixtures"]

    assert set(fixtures) == {
        "histogram_simple",
        "histogram_metroliza",
        "scatter_trend",
        "iqr_outliers",
        "violin_groups",
    }
    for name, mapping in fixtures.items():
        assert mapping["schema_version"] == 1, name
        assert mapping["chart_type"] in {"histogram", "scatter", "iqr", "violin"}, name
        assert mapping["canvas"]["size"]["width"] > 0, name
        assert mapping["canvas"]["size"]["height"] > 0, name
        assert mapping["plot_rect"]["width"] > 0, name
        assert mapping["plot_rect"]["height"] > 0, name
