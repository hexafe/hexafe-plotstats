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

import matplotlib
import numpy as np
import matplotlib.pyplot as plt

matplotlib.use("Agg", force=True)

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
from hexafe_plotstats.models import ChartRenderResult, RenderResult  # noqa: E402
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


@dataclass(frozen=True)
class ChartCase:
    name: str
    payload: Any
    matplotlib_renderer: Callable[[Any], RenderResult]
    rust_renderer: Callable[[Any], ChartRenderResult]
    width: int
    height: int


def _build_cases() -> dict[str, ChartCase]:
    rng = np.random.default_rng(20260510)
    limits = SpecLimits(lsl=42.0, nominal=50.0, usl=58.0)
    histogram_values = rng.normal(loc=50.0, scale=2.4, size=2_500)
    scatter_x = np.linspace(0.0, 100.0, 2_500)
    scatter_y = 0.7 * scatter_x + rng.normal(loc=0.0, scale=8.0, size=scatter_x.size)
    groups = {
        "A": rng.normal(loc=47.0, scale=2.2, size=700),
        "B": rng.normal(loc=50.0, scale=2.6, size=700),
        "C": rng.normal(loc=53.0, scale=2.8, size=700),
    }

    return {
        "histogram": ChartCase(
            name="histogram",
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
        "scatter": ChartCase(
            name="scatter",
            payload=build_scatter_payload(scatter_x, scatter_y, ScatterConfig(include_trend=True)),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_png,
            width=760,
            height=480,
        ),
        "iqr": ChartCase(
            name="iqr",
            payload=build_iqr_payload(groups, limits, IQRConfig(whis=1.5, showfliers=True)),
            matplotlib_renderer=render_iqr,
            rust_renderer=render_iqr_png,
            width=760,
            height=480,
        ),
        "violin": ChartCase(
            name="violin",
            payload=build_violin_payload(groups, limits),
            matplotlib_renderer=render_violin,
            rust_renderer=render_violin_png,
            width=760,
            height=480,
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


def _render_rust_png(case: ChartCase) -> int:
    result = case.rust_renderer(case.payload)
    _assert_png(result.png_bytes)
    return len(result.png_bytes)


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
    )


def run_benchmarks(charts: list[str], *, repeats: int, warmups: int) -> list[BenchmarkResult]:
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

        timings, png_bytes = _time_call(lambda case=case: _render_rust_png(case), repeats=repeats, warmups=warmups)
        results.append(
            _result_from_timings(
                chart=case.name,
                backend="rust",
                repeats=repeats,
                warmups=warmups,
                timings=timings,
                png_bytes=png_bytes,
            )
        )
    return results


def _print_table(results: list[BenchmarkResult]) -> None:
    header = f"{'chart':<10} {'backend':<11} {'available':<9} {'median_ms':>10} {'mean_ms':>10} {'min_ms':>10} {'png_bytes':>10} note"
    print(header)
    print("-" * len(header))
    for result in results:
        median = f"{result.median_ms:.2f}" if result.median_ms is not None else "-"
        mean = f"{result.mean_ms:.2f}" if result.mean_ms is not None else "-"
        minimum = f"{result.min_ms:.2f}" if result.min_ms is not None else "-"
        png_bytes = str(result.png_bytes) if result.png_bytes is not None else "-"
        print(
            f"{result.chart:<10} {result.backend:<11} {str(result.available):<9} "
            f"{median:>10} {mean:>10} {minimum:>10} {png_bytes:>10} {result.note}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Matplotlib PNG render time with Rust native PNG render time.")
    parser.add_argument("--chart", choices=("histogram", "scatter", "iqr", "violin", "all"), default="all")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of a table")
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.warmups < 0:
        parser.error("--warmups must be zero or greater")

    charts = ["histogram", "scatter", "iqr", "violin"] if args.chart == "all" else [args.chart]
    results = run_benchmarks(charts, repeats=args.repeats, warmups=args.warmups)
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        _print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
