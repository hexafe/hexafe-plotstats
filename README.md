# hexafe-plotstats

`hexafe-plotstats` is a library-first package for statistical chart payloads and renderer backends.

It is designed to extract the reusable plotting/statistical layer from `metroliza` without carrying over workbook,
Qt, thread, Google export, or dashboard orchestration concerns.

## Philosophy

- Build typed payloads first.
- Render payloads through an explicit backend.
- Default to matplotlib.
- Keep Rust/native rendering optional and backend-selectable.
- Keep adapters thin and optional.

## Install

```bash
pip install -e .
pip install -e .[pandas]
```

The core package depends on `numpy`, `scipy`, and `matplotlib`.
The `pandas` extra enables pandas adapter helpers.

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
```

Current state:

- `backend="matplotlib"` works and returns `RenderResult(fig, ax, metadata)`.
- `backend="rust"` is scaffolded and raises `RendererBackendUnavailable` until the Rust/native renderer is ported from `metroliza`.

This keeps the user-facing API stable while Rust parity work proceeds behind the backend boundary.

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

## Matplotlib renderers

Matplotlib-specific functions remain available when a caller wants to bypass backend dispatch:

```python
from hexafe_plotstats import render_histogram_matplotlib
```

## Rust/native renderer

Rust/native rendering is an explicit backend target, not the default.

The porting plan is:

1. keep chart payloads backend-neutral
2. port the metroliza Rust/native rendering boundary behind `backend="rust"`
3. tune Rust output against matplotlib output chart by chart
4. keep workbook and thread orchestration outside this package

## Optional adapters

- `hexafe_plotstats.adapters.pandas`: series and frame helpers when pandas is installed
- `hexafe_plotstats.adapters.metroliza`: duck-typed helpers for metroliza-style objects
- `hexafe_plotstats.adapters.groupstats`: duck-typed helpers for groupstats-style objects

Adapters extract values and limits, then call the same core payload/stat/render functions.

## Resume notes

Current session state and the active implementation plan are tracked in `docs/session_state.md`.
