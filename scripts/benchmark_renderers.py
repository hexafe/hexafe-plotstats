#!/usr/bin/env python
from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import sys
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("MPLCONFIGDIR", "/tmp/hexafe-plotstats-matplotlib")

import matplotlib  # noqa: E402

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from hexafe_plotstats import (  # noqa: E402
    HistogramConfig,
    IQRConfig,
    ScatterConfig,
    SpecLimits,
    build_histogram_payload,
    build_iqr_payload,
    build_scatter_payload,
    build_violin_payload,
    render_histogram,
    render_histogram_png,
    render_iqr,
    render_iqr_png,
    render_scatter,
    render_scatter_png,
    render_violin,
    render_violin_png,
)
from hexafe_plotstats.adapters.metroliza import histogram_from_metroliza_native_payload  # noqa: E402
from hexafe_plotstats.models import ChartRenderResult, RenderResult  # noqa: E402
from hexafe_plotstats.models import TableRow  # noqa: E402
from hexafe_plotstats.renderers.rust import native_backend_available, native_backend_module_name  # noqa: E402

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class BenchmarkResult:
    chart: str
    backend: str
    available: bool
    repeats: int
    warmups: int
    min_ms: float | None
    median_ms: float | None
    mean_ms: float | None
    png_bytes: int | None
    note: str = ""
    stage_ms: dict[str, float] | None = None


@dataclass(frozen=True)
class ChartCase:
    name: str
    suite: str
    payload: Any
    matplotlib_renderer: Callable[[Any], RenderResult]
    rust_renderer: Callable[..., ChartRenderResult]
    width: int
    height: int


def _build_cases() -> dict[str, ChartCase]:
    rng = np.random.default_rng(20260510)
    limits = SpecLimits(lsl=42.0, nominal=50.0, usl=58.0)
    histogram_values = rng.normal(loc=50.0, scale=2.4, size=2_500)
    metroliza_histogram_values = np.concatenate(
        [
            rng.normal(loc=49.2, scale=1.35, size=3_000),
            rng.normal(loc=52.8, scale=0.95, size=1_700),
            rng.normal(loc=45.5, scale=0.55, size=180),
        ]
    )
    large_histogram_values = np.concatenate(
        [
            rng.normal(loc=50.0, scale=1.9, size=90_000),
            rng.normal(loc=53.2, scale=1.1, size=10_000),
        ]
    )
    scatter_x = np.linspace(0.0, 100.0, 2_500)
    scatter_y = 0.7 * scatter_x + rng.normal(loc=0.0, scale=8.0, size=scatter_x.size)
    dense_x = rng.normal(loc=0.0, scale=2.1, size=25_000)
    dense_y = 0.42 * dense_x + np.sin(dense_x * 2.0) + rng.normal(loc=0.0, scale=0.85, size=dense_x.size)
    hex_x = rng.normal(loc=0.0, scale=2.6, size=80_000)
    hex_y = 0.28 * hex_x + rng.normal(loc=0.0, scale=1.6, size=hex_x.size)
    groups = {
        "A": rng.normal(loc=47.0, scale=2.2, size=700),
        "B": rng.normal(loc=50.0, scale=2.6, size=700),
        "C": rng.normal(loc=53.0, scale=2.8, size=700),
    }
    many_groups = {
        f"G{idx:02d}": rng.normal(loc=46.0 + idx * 0.42, scale=1.5 + (idx % 4) * 0.18, size=360)
        for idx in range(1, 17)
    }
    violin_groups = {
        f"V{idx:02d}": np.concatenate(
            [
                rng.normal(loc=47.5 + idx * 0.38, scale=1.0 + (idx % 3) * 0.2, size=260),
                rng.normal(loc=49.0 + idx * 0.31, scale=0.75, size=90),
            ]
        )
        for idx in range(1, 13)
    }

    metroliza_histogram = build_histogram_payload(
        metroliza_histogram_values,
        limits,
        HistogramConfig(bins=42, density=False, include_fit=True),
        metadata={
            "title": "Diameter capability summary",
            "axis_labels": {"x": "measurement", "y": "count"},
            "summary_table_title": "Parameter",
            "x_view": {"min": 39.0, "max": 61.0},
            "mean_line": {"value": float(np.mean(metroliza_histogram_values)), "color": "#111827", "linewidth": 1.1, "dash": [7, 4]},
            "annotation_rows": [
                {"text": "LSL", "kind": "lsl", "color": "#dc2626", "x": 42.0, "row_index": 0, "text_y_axes": 1.02},
                {"text": "Target", "kind": "nominal", "color": "#7c3aed", "x": 50.0, "row_index": 1, "text_y_axes": 1.055},
                {"text": "USL", "kind": "usl", "color": "#dc2626", "x": 58.0, "row_index": 2, "text_y_axes": 1.09},
            ],
            "modeled_overlay_rows": [
                {"label": "Normal", "value": "AIC 1024.1", "badge_palette": "fit"},
                {"label": "Lognormal", "value": "AIC 1058.6", "badge_palette": "fit"},
                {"label": "Weibull", "value": "AIC 1081.3", "badge_palette": "fit"},
            ],
        },
    )
    overlay_x = np.linspace(39.0, 61.0, 220)
    overlay_y = np.exp(-0.5 * ((overlay_x - 50.0) / 2.6) ** 2)
    overlay_y = overlay_y / max(float(np.max(overlay_y)), 1.0) * 360.0
    metroliza_adapter_histogram = histogram_from_metroliza_native_payload(
        {
            "values": metroliza_histogram_values.tolist(),
            "title": "Metroliza adapter capability",
            "bin_count": 42,
            "x_view": {"min": 39.0, "max": 61.0},
            "limits": {"lsl": 42.0, "nominal": 50.0, "usl": 58.0},
            "style": {"axis_label_x": "measurement", "axis_label_y": "count"},
            "mean_line": {"value": float(np.mean(metroliza_histogram_values)), "color": "#111827", "linewidth": 1.2, "dash": [8, 5]},
            "summary_table_rows": [
                {"label": "Count", "value": str(int(metroliza_histogram_values.size)), "row_kind": "summary_metric"},
                {"label": "Mean", "value": f"{float(np.mean(metroliza_histogram_values)):.3f}", "row_kind": "summary_metric"},
                {"label": "Model", "value": "Normal", "row_kind": "summary_metric", "section_break_before": True},
            ],
            "visual_metadata": {
                "summary_stats_table": {"title": "Parameter"},
                "annotation_rows": [
                    {"text": "LSL", "kind": "lsl", "color": "#dc2626", "x": 42.0, "row_index": 0, "text_y_axes": 1.02},
                    {"text": "USL", "kind": "usl", "color": "#dc2626", "x": 58.0, "row_index": 1, "text_y_axes": 1.06},
                ],
                "specification_lines": [
                    {"id": "lsl", "label": "LSL", "value": 42.0, "enabled": True},
                    {"id": "nominal", "label": "Nominal", "value": 50.0, "enabled": True},
                    {"id": "usl", "label": "USL", "value": 58.0, "enabled": True},
                ],
                "modeled_overlays": {
                    "rows": [
                        {"kind": "curve", "x": overlay_x.tolist(), "y": overlay_y.tolist(), "color": "#f97316", "linewidth": 1.4},
                        {
                            "kind": "curve",
                            "x": overlay_x[overlay_x <= 42.0].tolist(),
                            "y": overlay_y[overlay_x <= 42.0].tolist(),
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
    metroliza_histogram = type(metroliza_histogram)(
        **{
            **metroliza_histogram.__dict__,
            "table_rows": metroliza_histogram.table_rows
            + (
                TableRow("Dataset", "synthetic capability", kind="summary_metric", metadata={"section_break_before": True}),
                TableRow("Shift", "mixed production lots", kind="summary_metric"),
                TableRow("Rule", "model overlay rows", kind="summary_metric"),
            ),
        }
    )

    return {
        "histogram": ChartCase(
            name="histogram",
            suite="synthetic",
            payload=build_histogram_payload(
                histogram_values,
                limits,
                HistogramConfig(bins=32, density=False, include_fit=True),
                metadata={"title": "Renderer benchmark", "axis_labels": {"x": "measurement", "y": "count"}},
            ),
            matplotlib_renderer=render_histogram,
            rust_renderer=render_histogram_png,
            width=900,
            height=520,
        ),
        "histogram_metroliza_table": ChartCase(
            name="histogram_metroliza_table",
            suite="realistic",
            payload=metroliza_histogram,
            matplotlib_renderer=render_histogram,
            rust_renderer=render_histogram_png,
            width=900,
            height=520,
        ),
        "histogram_metroliza_adapter": ChartCase(
            name="histogram_metroliza_adapter",
            suite="realistic",
            payload=metroliza_adapter_histogram,
            matplotlib_renderer=render_histogram,
            rust_renderer=render_histogram_png,
            width=900,
            height=520,
        ),
        "histogram_large_process": ChartCase(
            name="histogram_large_process",
            suite="realistic",
            payload=build_histogram_payload(
                large_histogram_values,
                limits,
                HistogramConfig(bins=80, density=False, include_fit=False),
                metadata={"title": "Large process export", "axis_labels": {"x": "measurement", "y": "count"}},
            ),
            matplotlib_renderer=render_histogram,
            rust_renderer=render_histogram_png,
            width=900,
            height=520,
        ),
        "scatter": ChartCase(
            name="scatter",
            suite="synthetic",
            payload=build_scatter_payload(scatter_x, scatter_y, ScatterConfig(include_trend=True)),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_png,
            width=760,
            height=480,
        ),
        "scatter_dense": ChartCase(
            name="scatter_dense",
            suite="realistic",
            payload=build_scatter_payload(dense_x, dense_y, ScatterConfig(mode="scatter_rasterized", include_trend=True)),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_png,
            width=760,
            height=480,
        ),
        "scatter_hexbin": ChartCase(
            name="scatter_hexbin",
            suite="realistic",
            payload=build_scatter_payload(hex_x, hex_y, ScatterConfig(mode="hexbin", gridsize=72)),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_png,
            width=760,
            height=480,
        ),
        "iqr": ChartCase(
            name="iqr",
            suite="synthetic",
            payload=build_iqr_payload(groups, limits, IQRConfig(whis=1.5, showfliers=True)),
            matplotlib_renderer=render_iqr,
            rust_renderer=render_iqr_png,
            width=760,
            height=480,
        ),
        "iqr_many_groups": ChartCase(
            name="iqr_many_groups",
            suite="realistic",
            payload=build_iqr_payload(many_groups, limits, IQRConfig(whis=1.5, showfliers=True)),
            matplotlib_renderer=render_iqr,
            rust_renderer=render_iqr_png,
            width=900,
            height=520,
        ),
        "violin": ChartCase(
            name="violin",
            suite="synthetic",
            payload=build_violin_payload(groups, limits),
            matplotlib_renderer=render_violin,
            rust_renderer=render_violin_png,
            width=760,
            height=480,
        ),
        "violin_many_groups": ChartCase(
            name="violin_many_groups",
            suite="realistic",
            payload=build_violin_payload(violin_groups, limits),
            matplotlib_renderer=render_violin,
            rust_renderer=render_violin_png,
            width=900,
            height=520,
        ),
    }


def _assert_png(data: bytes) -> None:
    if not data.startswith(PNG_SIGNATURE):
        raise RuntimeError("renderer did not return PNG bytes")


def _render_matplotlib_png(case: ChartCase) -> int:
    result = case.matplotlib_renderer(case.payload)
    buffer = BytesIO()
    try:
        result.fig.set_size_inches(case.width / 100.0, case.height / 100.0, forward=True)
        result.fig.canvas.draw()
        result.fig.savefig(buffer, format="png", dpi=100)
    finally:
        plt.close(result.fig)
    data = buffer.getvalue()
    _assert_png(data)
    return len(data)


def _render_rust_png(case: ChartCase, *, profile: str) -> int:
    result = case.rust_renderer(case.payload, profile=profile)
    _assert_png(result.png_bytes)
    return len(result.png_bytes)


def _render_rust_stage_timings(case: ChartCase, *, profile: str) -> dict[str, float]:
    result = case.rust_renderer(case.payload, profile=profile)
    _assert_png(result.png_bytes)
    raw_timings = result.metadata.get("timings_ms", {})
    if not isinstance(raw_timings, dict):
        return {}
    return {str(key): float(value) for key, value in raw_timings.items()}


def _time_call(func: Callable[[], int], *, repeats: int, warmups: int) -> tuple[list[float], int]:
    last_size = 0
    for _ in range(warmups):
        last_size = func()

    timings: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = perf_counter_ns()
            last_size = func()
            timings.append((perf_counter_ns() - start) / 1_000_000)
    finally:
        if gc_was_enabled:
            gc.enable()
    return timings, last_size


def _result_from_timings(
    *,
    chart: str,
    backend: str,
    repeats: int,
    warmups: int,
    timings: list[float],
    png_bytes: int,
    stage_ms: dict[str, float] | None = None,
) -> BenchmarkResult:
    return BenchmarkResult(
        chart=chart,
        backend=backend,
        available=True,
        repeats=repeats,
        warmups=warmups,
        min_ms=min(timings),
        median_ms=statistics.median(timings),
        mean_ms=statistics.fmean(timings),
        png_bytes=png_bytes,
        stage_ms=stage_ms,
    )


def _unavailable_result(*, chart: str, repeats: int, warmups: int, note: str) -> BenchmarkResult:
    return BenchmarkResult(
        chart=chart,
        backend="rust",
        available=False,
        repeats=repeats,
        warmups=warmups,
        min_ms=None,
        median_ms=None,
        mean_ms=None,
        png_bytes=None,
        note=note,
        stage_ms=None,
    )


def run_benchmarks(charts: list[str], *, repeats: int, warmups: int, profile: str = "fast") -> list[BenchmarkResult]:
    cases = _build_cases()
    selected_cases = [cases[name] for name in charts]
    results: list[BenchmarkResult] = []
    rust_available = native_backend_available()
    rust_note = (
        f"native module: {native_backend_module_name()}"
        if rust_available
        else "native renderer extension is unavailable"
    )

    for case in selected_cases:
        timings, png_bytes = _time_call(lambda case=case: _render_matplotlib_png(case), repeats=repeats, warmups=warmups)
        results.append(
            _result_from_timings(
                chart=case.name,
                backend="matplotlib",
                repeats=repeats,
                warmups=warmups,
                timings=timings,
                png_bytes=png_bytes,
            )
        )

        if not rust_available:
            results.append(_unavailable_result(chart=case.name, repeats=repeats, warmups=warmups, note=rust_note))
            continue

        timings, png_bytes = _time_call(lambda case=case: _render_rust_png(case, profile=profile), repeats=repeats, warmups=warmups)
        stage_ms = _render_rust_stage_timings(case, profile=profile)
        results.append(
            _result_from_timings(
                chart=case.name,
                backend="rust",
                repeats=repeats,
                warmups=warmups,
                timings=timings,
                png_bytes=png_bytes,
                stage_ms=stage_ms,
            )
        )
    return results


_STAGE_LABELS = (
    ("py_resolve", "python_resolve_ms"),
    ("py_json", "python_native_arg_ms"),
    ("native_call", "python_native_call_ms"),
    ("input", "native_input_decode_ms"),
    ("parse", "native_resolved_parse_ms"),
    ("draw", "native_draw_ms"),
    ("text", "native_text_overlay_ms"),
    ("png", "native_png_encode_ms"),
    ("h_axes", "native_histogram_axes_ms"),
    ("h_bars", "native_histogram_bars_ms"),
    ("h_curves", "native_histogram_curves_ms"),
    ("h_table", "native_histogram_table_ms"),
)


def _format_stages(stage_ms: dict[str, float] | None) -> str:
    if not stage_ms:
        return "-"
    return " ".join(
        f"{label}={stage_ms[key]:.1f}"
        for label, key in _STAGE_LABELS
        if key in stage_ms
    )


def _print_table(results: list[BenchmarkResult]) -> None:
    header = (
        f"{'chart':<24} {'backend':<11} {'available':<9} {'median_ms':>10} {'mean_ms':>10} "
        f"{'min_ms':>10} {'png_bytes':>10} {'stages_ms':<96} note"
    )
    print(header)
    print("-" * len(header))
    for result in results:
        median = f"{result.median_ms:.2f}" if result.median_ms is not None else "-"
        mean = f"{result.mean_ms:.2f}" if result.mean_ms is not None else "-"
        minimum = f"{result.min_ms:.2f}" if result.min_ms is not None else "-"
        png_bytes = str(result.png_bytes) if result.png_bytes is not None else "-"
        stages = _format_stages(result.stage_ms)
        print(
            f"{result.chart:<24} {result.backend:<11} {str(result.available):<9} "
            f"{median:>10} {mean:>10} {minimum:>10} {png_bytes:>10} {stages:<96} {result.note}"
        )


def _selected_chart_names(selection: str, cases: dict[str, ChartCase]) -> list[str]:
    if selection == "all":
        return list(cases)
    if selection in {"synthetic", "realistic"}:
        return [name for name, case in cases.items() if case.suite == selection]
    if selection not in cases:
        valid = ", ".join((*cases.keys(), "synthetic", "realistic", "all"))
        raise ValueError(f"unknown chart selection {selection!r}; choose one of: {valid}")
    return [selection]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Matplotlib PNG render time with Rust native PNG render time.")
    parser.add_argument("--chart", default="all", help="chart case name, or one of: synthetic, realistic, all")
    parser.add_argument("--profile", choices=("fast", "compact", "debug"), default="fast", help="native render profile to benchmark")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of a table")
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.warmups < 0:
        parser.error("--warmups must be zero or greater")

    cases = _build_cases()
    try:
        charts = _selected_chart_names(args.chart, cases)
    except ValueError as exc:
        parser.error(str(exc))
    results = run_benchmarks(charts, repeats=args.repeats, warmups=args.warmups, profile=args.profile)
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        _print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
