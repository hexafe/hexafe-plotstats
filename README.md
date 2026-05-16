# hexafe-plotstats

`hexafe-plotstats` is a library-first package for statistical chart payloads and renderer backends.

It is designed to extract the reusable plotting/statistical layer from `metroliza` without carrying over workbook,
Qt, thread, Google export, or dashboard orchestration concerns.

## Philosophy

- Build typed payloads first.
- Render payloads through an explicit backend.
- Default to `backend="matplotlib"`.
- Keep Rust/native rendering opt-in behind `backend="rust"`.
- Keep adapters thin and optional.

## Install

```bash
pip install -e .
pip install -e .[pandas]
pip install -e .[plotly]
```

The core package depends on `numpy`, `scipy`, and `matplotlib`.
The `pandas` extra enables pandas adapter helpers.
The `plotly` extra enables the interactive scatter backend.

## Quick start

```python
from hexafe_plotstats import (
    SpecLimits,
    build_histogram_payload,
    render_histogram,
    summarize_distribution,
)

values = [9.8, 10.0, 10.1, 9.9, 10.2, 10.3]
limits = SpecLimits(lsl=9.5, nominal=10.0, usl=10.5)

summary = summarize_distribution(values, limits)
payload = build_histogram_payload(values, limits)

print(summary.count, summary.mean)

result = render_histogram(payload)  # defaults to backend="matplotlib"
result.fig.canvas.draw()
```

## Renderer selection

The high-level render functions accept a `backend` argument:

```python
render_histogram(payload, backend="matplotlib")
render_histogram(payload, backend="rust")
render_scatter(payload, backend="plotly")
```

Current state:

- `backend="matplotlib"` is the default and returns `RenderResult(fig, ax, metadata)`.
- `backend="rust"` is an explicit opt-in and returns PNG bytes when the optional native module is installed.
- `backend="plotly"` is optional. The first scaffold supports scatter through
  Plotly-compatible trace/layout dictionaries and `go.Figure` creation when the
  `plotly` extra is installed.

This keeps the user-facing API stable while Rust parity work proceeds behind the backend boundary.

You can inspect renderer availability without attempting a render:

```python
from hexafe_plotstats import renderer_backend_capabilities

for backend in renderer_backend_capabilities():
    print(backend.backend, backend.available, backend.default)
```

## Large Interactive Scatter

Large interactive scatter output should use an aggregated interaction layer by
default. `build_scatter_interactive_spec(...)` prepares that renderer-neutral
contract without requiring Plotly at import time:

```python
from hexafe_plotstats import build_scatter_interactive_spec

spec = build_scatter_interactive_spec(
    timestamps,
    values,
    x_view=("2026-01-01T00:00", "2026-01-08T00:00"),
    target_interactive_points=500,
)
```

For temporal X axes, the bucket is selected automatically from `minute`,
`hour`, `day`, or `week` based on the requested X-axis range and the target
interactive point count. The interactive layer contains aggregated buckets only.
Raw points are represented as a separate static-raster layer with its own legend
group, so a Plotly/HTML consumer can let users hide raw data without removing
the aggregated interactive trace.

## Supported charts

| Chart family | Payload builder | Default renderer | Rust/native status | Notes |
| --- | --- | --- | --- | --- |
| Histogram | `build_histogram_payload(...)` | `render_histogram(..., backend="matplotlib")` | explicit opt-in when `_hexafe_plotstats_native` is installed | Includes Metroliza-style summary rows, capability, normality, fitted distribution, and resolved-spec support. |
| Violin | `build_violin_payload(...)` | `render_violin(..., backend="matplotlib")` | explicit opt-in when `_hexafe_plotstats_native` is installed | Grouped distribution view with mean/quartile/extrema annotations and resolved-spec support. |
| IQR | `build_iqr_payload(...)` | `render_iqr(..., backend="matplotlib")` | explicit opt-in when `_hexafe_plotstats_native` is installed | Grouped boxplot view with outlier policy in payload metadata and resolved-spec support. |
| Scatter | `build_scatter_payload(...)` | `render_scatter(..., backend="matplotlib")` | explicit opt-in when `_hexafe_plotstats_native` is installed | Automatically switches between normal scatter, rasterized scatter, and hexbin based on data volume; resolved-spec support is available. |
| Scatter trend | `build_scatter_payload(..., ScatterConfig(include_trend=True))` | `render_scatter(..., backend="matplotlib")` | explicit opt-in PNG helper when `_hexafe_plotstats_native` is installed | Trend is currently a scatter mode, not a separate first-class chart family. |

## Resolved spec boundary

The parity handoff is the resolved spec, not a matplotlib figure.

Python is responsible for resolving:

- layout
- ticks
- bars, boxes, lines, and other chart primitives
- table rows
- annotations
- chart-specific render metadata

The Rust PNG entry points convert payloads into that resolved mapping before calling the optional native module. If `_hexafe_plotstats_native` is not installed, Rust paths raise `RendererBackendUnavailable`.

Current resolved-spec helpers:

```python
from hexafe_plotstats.specs import (
    histogram_payload_to_resolved_spec,
    iqr_payload_to_resolved_spec,
    scatter_payload_to_resolved_spec,
    to_mapping,
    violin_payload_to_resolved_spec,
)

mapping = to_mapping(histogram_payload_to_resolved_spec(payload))
```

## Payload builders

Use payload builders when you want a structured intermediate object that can be rendered or inspected:

```python
from hexafe_plotstats import (
    build_histogram_payload,
    build_iqr_payload,
    build_scatter_payload,
    build_violin_payload,
)
```

Payloads are plain typed dataclasses. They are not tied to Excel, xlsxwriter, Qt, or a workbook layout.

Histogram options:

```python
from hexafe_plotstats import HistogramConfig, build_histogram_payload

payload = build_histogram_payload(
    values,
    config=HistogramConfig(bins=24, density=False, include_fit=False),
    metadata={
        "title": "Diameter",
        "axis_labels": {"x": "Measurement", "y": "Count"},
    },
)
```

Empty or all-nonfinite input resolves to a single zero-height fallback bin over `0.0..1.0`. Constant input resolves to one bin centered on the constant value. These fallbacks keep renderers and resolved-spec consumers deterministic.

Grouped chart example:

```python
from hexafe_plotstats import (
    SpecLimits,
    build_iqr_payload,
    build_scatter_payload,
    build_violin_payload,
    render_iqr,
    render_scatter,
    render_violin,
)
from hexafe_plotstats.models import ScatterConfig

limits = SpecLimits(lsl=0.0, nominal=2.5, usl=5.0)

violin = build_violin_payload({"A": [1, 2, 3], "B": [2, 3, 4]}, limits)
iqr = build_iqr_payload({"A": [1, 2, 3], "B": [2, 3, 7]}, limits)
scatter = build_scatter_payload([1, 2, 3, 4], [2, 4, 6, 8], ScatterConfig(include_trend=True))

render_violin(violin)
render_iqr(iqr)
render_scatter(scatter)
```

## Matplotlib renderers

Matplotlib-specific functions remain available when a caller wants to bypass backend dispatch:

```python
from hexafe_plotstats import render_histogram_matplotlib
```

## Rust/native renderer

Rust/native rendering is an explicit backend target, not the default.
Matplotlib remains the default. When `_hexafe_plotstats_native` is installed, `backend="rust"` and the PNG helpers render through the native Rust extension; otherwise they raise `RendererBackendUnavailable`.

The byte-oriented native helpers are exposed separately from matplotlib figure renderers:

```python
from hexafe_plotstats import render_histogram_png

result = render_histogram_png(payload, profile="fast")
result.png_bytes
```

Native profiles are explicit:

- `fast`: default, direct text rasterization, RGBA PNG, no debug SVG metadata.
- `compact`: RGB PNG with fast compression for smaller files.
- `debug`: includes debug SVG metadata and uses balanced PNG compression.

The native package is built from `native/hexafe-plotstats-native` with maturin:

```bash
cd native/hexafe-plotstats-native
python -m maturin build --release --locked
```

For PyPI-safe Linux wheels, build inside a manylinux container or maturin action;
host-built Linux wheels may use the non-uploadable `linux_x86_64` tag.

Renderer parity and timing helpers are available under `scripts/`:

```bash
python scripts/compare_renderers.py
python scripts/benchmark_renderers.py --chart synthetic
python scripts/benchmark_renderers.py --chart realistic --profile compact
```

## Optional adapters

- `hexafe_plotstats.adapters.pandas`: series and frame helpers when pandas is installed
- `hexafe_plotstats.adapters.metroliza`: duck-typed helpers for metroliza-style objects
- `hexafe_plotstats.adapters.groupstats`: duck-typed helpers for groupstats-style objects

Adapters extract values and limits, then call the same core payload/stat/render functions.

The Metroliza adapter also accepts the enriched native histogram payload shape used by Metroliza export code:

```python
from hexafe_plotstats.adapters import histogram_from_metroliza_native_payload

payload = histogram_from_metroliza_native_payload(native_payload)
```

It preserves title, count-space histogram settings, x-view, axis labels, mean-line metadata, specification lines, annotation rows, summary table rows, and visual metadata for resolved-spec/native handoff tests.

## Resume notes

Current session state and the active implementation plan are tracked in `docs/session_state.md`.
