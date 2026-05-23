#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hexafe-plotstats-matplotlib")

import matplotlib  # noqa: E402

matplotlib.use("Agg", force=True)

import matplotlib.image as mpimg  # noqa: E402
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
from hexafe_plotstats.models import ChartRenderResult, RenderResult  # noqa: E402
from hexafe_plotstats.renderers.rust import native_backend_available, native_backend_module_name  # noqa: E402


@dataclass(frozen=True)
class ComparisonCase:
    name: str
    payload: Any
    matplotlib_renderer: Callable[[Any], RenderResult]
    rust_renderer: Callable[[Any], ChartRenderResult]


@dataclass(frozen=True)
class ComparisonResult:
    chart: str
    width: int
    height: int
    mean_abs_diff: float
    max_abs_diff: int
    threshold: float
    passed: bool
    matplotlib_png: str
    rust_png: str
    diff_png: str
    comparison_png: str


def _cases() -> dict[str, ComparisonCase]:
    rng = np.random.default_rng(20260510)
    limits = SpecLimits(lsl=42.0, nominal=50.0, usl=58.0)
    histogram_values = rng.normal(loc=50.0, scale=2.4, size=260)
    plain_x = np.linspace(0.0, 30.0, 80)
    plain_y = 10.0 + np.sin(plain_x / 3.0) * 3.0 + rng.normal(0.0, 0.5, plain_x.size)
    trend_x = np.linspace(0.0, 100.0, 250)
    trend_y = 0.72 * trend_x + rng.normal(loc=0.0, scale=7.0, size=trend_x.size)
    groups = {
        "A": rng.normal(loc=47.0, scale=2.2, size=90),
        "B": rng.normal(loc=50.0, scale=2.6, size=90),
        "C": rng.normal(loc=53.0, scale=2.8, size=90),
    }

    return {
        "histogram": ComparisonCase(
            name="histogram",
            payload=build_histogram_payload(
                histogram_values,
                limits,
                HistogramConfig(bins=18, density=False, include_fit=True),
                metadata={"title": "Renderer comparison", "axis_labels": {"x": "measurement", "y": "count"}},
            ),
            matplotlib_renderer=render_histogram,
            rust_renderer=render_histogram_png,
        ),
        "scatter": ComparisonCase(
            name="scatter",
            payload=build_scatter_payload(plain_x, plain_y, ScatterConfig(include_trend=False)),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_png,
        ),
        "scatter_trend": ComparisonCase(
            name="scatter_trend",
            payload=build_scatter_payload(trend_x, trend_y, ScatterConfig(include_trend=True)),
            matplotlib_renderer=render_scatter,
            rust_renderer=render_scatter_png,
        ),
        "iqr": ComparisonCase(
            name="iqr",
            payload=build_iqr_payload(groups, limits, IQRConfig(whis=1.5, showfliers=True)),
            matplotlib_renderer=render_iqr,
            rust_renderer=render_iqr_png,
        ),
        "violin": ComparisonCase(
            name="violin",
            payload=build_violin_payload(groups, limits),
            matplotlib_renderer=render_violin,
            rust_renderer=render_violin_png,
        ),
    }


def _matplotlib_png(case: ComparisonCase) -> bytes:
    result = case.matplotlib_renderer(case.payload)
    buffer = BytesIO()
    try:
        result.fig.canvas.draw()
        result.fig.savefig(buffer, format="png", dpi=100)
    finally:
        plt.close(result.fig)
    return buffer.getvalue()


def _read_png(data: bytes) -> np.ndarray:
    image = mpimg.imread(BytesIO(data), format="png")
    if image.dtype.kind == "f":
        image = np.clip(image * 255.0, 0.0, 255.0).astype(np.uint8)
    if image.ndim == 2:
        image = np.repeat(image[:, :, None], 3, axis=2)
    if image.shape[2] == 3:
        alpha = np.full((*image.shape[:2], 1), 255, dtype=np.uint8)
        image = np.concatenate([image, alpha], axis=2)
    return image[:, :, :4].astype(np.uint8)


def _write_png(path: Path, image: np.ndarray) -> None:
    plt.imsave(path, image)


def _comparison_strip(matplotlib_image: np.ndarray, rust_image: np.ndarray, diff_image: np.ndarray) -> np.ndarray:
    separator = np.full((matplotlib_image.shape[0], 8, 4), 255, dtype=np.uint8)
    separator[:, :, :3] = 229
    return np.concatenate([matplotlib_image, separator, rust_image, separator, diff_image], axis=1)


def _compare_case(case: ComparisonCase, output_dir: Path, *, threshold: float) -> ComparisonResult:
    matplotlib_png = _matplotlib_png(case)
    rust_png = case.rust_renderer(case.payload).png_bytes
    matplotlib_image = _read_png(matplotlib_png)
    rust_image = _read_png(rust_png)
    if matplotlib_image.shape != rust_image.shape:
        raise RuntimeError(f"{case.name}: image shapes differ: {matplotlib_image.shape} vs {rust_image.shape}")

    delta = np.abs(matplotlib_image.astype(np.int16) - rust_image.astype(np.int16)).astype(np.uint8)
    diff_rgb = np.zeros_like(matplotlib_image)
    diff_rgb[:, :, 0] = np.minimum(delta[:, :, :3].max(axis=2) * 6, 255)
    diff_rgb[:, :, 3] = 255

    mean_abs_diff = float(np.mean(delta))
    max_abs_diff = int(np.max(delta))
    matplotlib_path = output_dir / f"{case.name}_matplotlib.png"
    rust_path = output_dir / f"{case.name}_rust.png"
    diff_path = output_dir / f"{case.name}_diff.png"
    comparison_path = output_dir / f"{case.name}_comparison.png"
    matplotlib_path.write_bytes(matplotlib_png)
    rust_path.write_bytes(rust_png)
    _write_png(diff_path, diff_rgb)
    _write_png(comparison_path, _comparison_strip(matplotlib_image, rust_image, diff_rgb))

    return ComparisonResult(
        chart=case.name,
        width=int(matplotlib_image.shape[1]),
        height=int(matplotlib_image.shape[0]),
        mean_abs_diff=mean_abs_diff,
        max_abs_diff=max_abs_diff,
        threshold=threshold,
        passed=mean_abs_diff <= threshold,
        matplotlib_png=str(matplotlib_path),
        rust_png=str(rust_path),
        diff_png=str(diff_path),
        comparison_png=str(comparison_path),
    )


def _write_summary(output_dir: Path, results: list[ComparisonResult]) -> None:
    (output_dir / "summary.json").write_text(
        json.dumps([asdict(result) for result in results], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "| Chart | Size | Mean abs diff | Max diff | Pass | Comparison |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result.chart} | {result.width}x{result.height} | {result.mean_abs_diff:.3f} | "
            f"{result.max_abs_diff} | {'yes' if result.passed else 'no'} | {result.comparison_png} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Matplotlib/Rust comparison PNGs for each plot family.")
    parser.add_argument("--chart", choices=("histogram", "scatter", "scatter_trend", "iqr", "violin", "all"), default="all")
    parser.add_argument("--output", default="/tmp/hexafe_plotstats_renderer_comparisons")
    parser.add_argument("--threshold", type=float, default=15.0)
    args = parser.parse_args()

    if not native_backend_available():
        raise RuntimeError("native renderer extension is unavailable; build/install hexafe-plotstats-native first")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = _cases()
    selected = cases.values() if args.chart == "all" else (cases[args.chart],)
    results = [_compare_case(case, output_dir, threshold=args.threshold) for case in selected]
    _write_summary(output_dir, results)

    print(f"native module: {native_backend_module_name()}")
    print((output_dir / "summary.md").read_text(encoding="utf-8"))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
