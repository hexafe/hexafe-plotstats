#!/usr/bin/env python
from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import sys
import tracemalloc
from collections.abc import Callable
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from time import perf_counter_ns
from typing import Any

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
    render_scatter_trend_png,
    render_violin,
    render_violin_png,
)
from hexafe_plotstats.models import ChartRenderResult, RenderResult  # noqa: E402
from hexafe_plotstats.renderers.plotly import (  # noqa: E402
    histogram_payload_to_plotly_spec,
    iqr_payload_to_plotly_spec,
    scatter_payload_to_plotly_spec,
    violin_payload_to_plotly_spec,
)
from hexafe_plotstats.renderers.rust import native_backend_available, native_backend_module_name  # noqa: E402

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class TimedResult:
    seconds: float
    peak_mb: float | None
    output_size: int | None = None
    stage_ms: dict[str, float] | None = None


@dataclass(frozen=True)
class BenchmarkRow:
    chart: str
    backend: str
    build_seconds: float
    render_seconds_median: float | None
    render_seconds_min: float | None
    render_seconds_mean: float | None
    build_peak_mb: float | None
    render_peak_mb: float | None
    output_size: int | None
    repeats: int
    available: bool
    note: str = ""
    stage_ms: dict[str, float] | None = None


@dataclass(frozen=True)
class ChartCase:
    name: str
    build_payload: Callable[[], Any]
    matplotlib_renderer: Callable[[Any], RenderResult]
    rust_renderer: Callable[..., ChartRenderResult]
    plotly_spec: Callable[[Any], dict[str, Any]]


def _seconds_since(start_ns: int) -> float:
    return (perf_counter_ns() - start_ns) / 1_000_000_000


def _run_timed(func: Callable[[], Any], *, track_memory: bool = False) -> tuple[Any, TimedResult]:
    gc.collect()
    if track_memory:
        tracemalloc.start()
    start = perf_counter_ns()
    try:
        value = func()
    finally:
        seconds = _seconds_since(start)
        if track_memory:
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_mb = peak / (1024 * 1024)
        else:
            peak_mb = None
    return value, TimedResult(seconds=seconds, peak_mb=peak_mb)


def _render_matplotlib_png(renderer: Callable[[Any], RenderResult], payload: Any) -> int:
    result = renderer(payload)
    buffer = BytesIO()
    try:
        result.fig.canvas.draw()
        result.fig.savefig(buffer, format="png", dpi=100)
    finally:
        plt.close(result.fig)
    data = buffer.getvalue()
    if not data.startswith(PNG_SIGNATURE):
        raise RuntimeError("matplotlib renderer did not return PNG bytes")
    return len(data)


def _render_rust_png(renderer: Callable[..., ChartRenderResult], payload: Any, *, profile: str) -> tuple[int, dict[str, float]]:
    result = renderer(payload, profile=profile)
    if not result.png_bytes.startswith(PNG_SIGNATURE):
        raise RuntimeError("rust renderer did not return PNG bytes")
    raw = result.metadata.get("timings_ms", {})
    stage_ms = {str(key): float(value) for key, value in raw.items()} if isinstance(raw, dict) else {}
    return len(result.png_bytes), stage_ms


def _plotly_spec_size(factory: Callable[[Any], dict[str, Any]], payload: Any) -> int:
    spec = factory(payload)
    return len(json.dumps(spec, allow_nan=False, separators=(",", ":")))


def _time_repeated(
    func: Callable[[], tuple[int, dict[str, float]] | int],
    *,
    repeats: int,
    track_memory: bool,
) -> tuple[list[TimedResult], int | None, dict[str, float] | None, str]:
    timings: list[TimedResult] = []
    output_size: int | None = None
    stage_ms: dict[str, float] | None = None
    for _ in range(repeats):
        try:
            value, timed = _run_timed(func, track_memory=track_memory)
        except Exception as exc:  # noqa: BLE001
            return timings, output_size, stage_ms, str(exc)
        if isinstance(value, tuple):
            output_size, stage_ms = value
        else:
            output_size = int(value)
        timings.append(TimedResult(seconds=timed.seconds, peak_mb=timed.peak_mb, output_size=output_size, stage_ms=stage_ms))
    return timings, output_size, stage_ms, ""


def _benchmark_renderer(
    *,
    chart: str,
    backend: str,
    build: TimedResult,
    payload: Any,
    repeats: int,
    render: Callable[[], tuple[int, dict[str, float]] | int],
    available: bool = True,
    note: str = "",
    track_memory: bool = False,
) -> BenchmarkRow:
    if not available:
        return BenchmarkRow(
            chart=chart,
            backend=backend,
            build_seconds=build.seconds,
            render_seconds_median=None,
            render_seconds_min=None,
            render_seconds_mean=None,
            build_peak_mb=build.peak_mb,
            render_peak_mb=None,
            output_size=None,
            repeats=repeats,
            available=False,
            note=note,
        )
    del payload
    timings, output_size, stage_ms, error = _time_repeated(render, repeats=repeats, track_memory=track_memory)
    if error:
        return BenchmarkRow(
            chart=chart,
            backend=backend,
            build_seconds=build.seconds,
            render_seconds_median=None,
            render_seconds_min=None,
            render_seconds_mean=None,
            build_peak_mb=build.peak_mb,
            render_peak_mb=None,
            output_size=output_size,
            repeats=repeats,
            available=False,
            note=error,
            stage_ms=stage_ms,
        )

    seconds = [timing.seconds for timing in timings]
    peak_values = [timing.peak_mb for timing in timings if timing.peak_mb is not None]
    peak_mb = max(peak_values) if peak_values else None
    return BenchmarkRow(
        chart=chart,
        backend=backend,
        build_seconds=build.seconds,
        render_seconds_median=statistics.median(seconds),
        render_seconds_min=min(seconds),
        render_seconds_mean=statistics.fmean(seconds),
        build_peak_mb=build.peak_mb,
        render_peak_mb=peak_mb,
        output_size=output_size,
        repeats=repeats,
        available=True,
        stage_ms=stage_ms,
    )


def _cases(data: np.ndarray, *, scatter_gridsize: int) -> list[ChartCase]:
    groups = {f"col_{index + 1}": data[:, index] for index in range(data.shape[1])}
    scatter_x = data[:, 0]
    scatter_y = data[:, 1] if data.shape[1] > 1 else data[:, 0]

    return [
        ChartCase(
            name="histogram",
            build_payload=lambda: build_histogram_payload(
                data[:, 0],
                config=HistogramConfig(bins=100, density=False, include_fit=False),
                metadata={"title": "Large histogram"},
            ),
            matplotlib_renderer=render_histogram,
            rust_renderer=render_histogram_png,
            plotly_spec=histogram_payload_to_plotly_spec,
        ),
        ChartCase(
            name="scatter_hexbin",
            build_payload=lambda: build_scatter_payload(scatter_x, scatter_y, ScatterConfig(mode="hexbin", gridsize=scatter_gridsize)),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_png,
            plotly_spec=scatter_payload_to_plotly_spec,
        ),
        ChartCase(
            name="scatter_hexbin_trend",
            build_payload=lambda: build_scatter_payload(
                scatter_x,
                scatter_y,
                ScatterConfig(mode="hexbin", gridsize=scatter_gridsize, include_trend=True),
            ),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_trend_png,
            plotly_spec=scatter_payload_to_plotly_spec,
        ),
        ChartCase(
            name="iqr",
            build_payload=lambda: build_iqr_payload(groups, config=IQRConfig(whis=1.5, showfliers=True)),
            matplotlib_renderer=render_iqr,
            rust_renderer=render_iqr_png,
            plotly_spec=iqr_payload_to_plotly_spec,
        ),
        ChartCase(
            name="violin",
            build_payload=lambda: build_violin_payload(groups),
            matplotlib_renderer=render_violin,
            rust_renderer=render_violin_png,
            plotly_spec=violin_payload_to_plotly_spec,
        ),
    ]


def run_benchmarks(
    *,
    rows: int,
    columns: int,
    repeats: int,
    seed: int,
    scatter_gridsize: int,
    profile: str,
    track_memory: bool = False,
) -> list[BenchmarkRow]:
    rng = np.random.default_rng(seed)
    data = rng.normal(loc=0.0, scale=1.0, size=(rows, columns))
    if columns >= 2:
        data[:, 1] = 0.42 * data[:, 0] + rng.normal(loc=0.0, scale=0.8, size=rows)

    rows_out: list[BenchmarkRow] = []
    rust_available = native_backend_available()
    rust_note = f"native module: {native_backend_module_name()}" if rust_available else "native renderer extension is unavailable"

    for case in _cases(data, scatter_gridsize=scatter_gridsize):
        payload, build = _run_timed(case.build_payload, track_memory=track_memory)
        rows_out.append(
            _benchmark_renderer(
                chart=case.name,
                backend="matplotlib",
                build=build,
                payload=payload,
                repeats=repeats,
                render=lambda case=case, payload=payload: _render_matplotlib_png(case.matplotlib_renderer, payload),
                track_memory=track_memory,
            )
        )
        rows_out.append(
            _benchmark_renderer(
                chart=case.name,
                backend="rust",
                build=build,
                payload=payload,
                repeats=repeats,
                available=rust_available,
                note=rust_note if not rust_available else "",
                render=lambda case=case, payload=payload: _render_rust_png(case.rust_renderer, payload, profile=profile),
                track_memory=track_memory,
            )
        )
        rows_out.append(
            _benchmark_renderer(
                chart=case.name,
                backend="plotly_spec",
                build=build,
                payload=payload,
                repeats=repeats,
                render=lambda case=case, payload=payload: _plotly_spec_size(case.plotly_spec, payload),
                track_memory=track_memory,
            )
        )
    return rows_out


def _print_table(rows: list[BenchmarkRow]) -> None:
    header = (
        f"{'chart':<22} {'backend':<13} {'avail':<5} {'build_s':>9} {'render_s':>9} "
        f"{'build_mb':>9} {'render_mb':>9} {'size':>10} note"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        render = f"{row.render_seconds_median:.3f}" if row.render_seconds_median is not None else "-"
        build_mb = f"{row.build_peak_mb:.2f}" if row.build_peak_mb is not None else "-"
        render_mb = f"{row.render_peak_mb:.2f}" if row.render_peak_mb is not None else "-"
        output_size = str(row.output_size) if row.output_size is not None else "-"
        print(
            f"{row.chart:<22} {row.backend:<13} {str(row.available):<5} {row.build_seconds:>9.3f} "
            f"{render:>9} {build_mb:>9} {render_mb:>9} {output_size:>10} {row.note}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark large 1M x 5 datasets across plot types and renderer backends.")
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260516)
    parser.add_argument("--scatter-gridsize", type=int, default=120)
    parser.add_argument("--profile", choices=("fast", "compact", "debug"), default="fast")
    parser.add_argument("--track-memory", action="store_true", help="measure peak Python allocations with tracemalloc; this can inflate timings")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.rows < 1:
        parser.error("--rows must be at least 1")
    if args.columns < 1:
        parser.error("--columns must be at least 1")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    rows = run_benchmarks(
        rows=args.rows,
        columns=args.columns,
        repeats=args.repeats,
        seed=args.seed,
        scatter_gridsize=args.scatter_gridsize,
        profile=args.profile,
        track_memory=args.track_memory,
    )
    if args.json:
        print(json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True))
    else:
        _print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
