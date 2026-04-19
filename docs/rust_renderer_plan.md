# Rust/native renderer plan

Last updated: 2026-04-19

## Current decision

`hexafe-plotstats` supports explicit renderer selection:

```python
render_histogram(payload, backend="matplotlib")
render_histogram(payload, backend="rust")
```

Current state:

- `backend="matplotlib"` is implemented.
- `backend="rust"` is scaffolded and raises `RendererBackendUnavailable`.
- The public API is intentionally stable before the Rust/native implementation is ported.

## Metroliza extraction map

Read-only audit source: `/home/hexaf/Projects/metroliza`

Key source files:

- `modules/chart_renderer.py`
  - runtime backend boundary
  - contains `ChartRenderer`, `MatplotlibChartRenderer`, `NativeChartRenderer`, `build_chart_renderer()`, and backend resolution helpers
- `modules/chart_render_spec.py`
  - resolved spec layer
  - builds canonical specs for histogram, distribution, IQR, and trend charts
  - includes mapping builders such as `histogram_spec_to_mapping()`
- `modules/native_chart_compositor.py`
  - current native draw contract
  - exports `render_histogram_png()`, `render_distribution_png()`, `render_iqr_png()`, and `render_trend_png()`
- `modules/native/chart_renderer/src/lib.rs`
  - PyO3 wrapper
  - currently forwards into `modules.native_chart_compositor`
- `modules/matplotlib_distribution_geometry.py`
  - parity/oracle extraction from matplotlib artists
  - should stay out of the native backend core
- `modules/matplotlib_iqr_trend_geometry.py`
  - parity/oracle extraction from matplotlib artists
  - should stay out of the native backend core

## Backend boundary

The Rust/native backend should consume pure data specs, not matplotlib figures.

Recommended handoff:

- `ResolvedChartSpec`
- JSON-like `dict`/`Mapping`
- fields such as:
  - `chart_type`
  - `canvas`
  - `title`
  - `plot_area`
  - `axes`
  - chart-specific primitives
  - `resolved_render_spec`

`resolved_render_spec` is the important parity boundary. Python should resolve layout, ticks, density, table rows, annotations, and chart primitives. Rust should draw those primitives.

## API target

High-level user API:

```python
render_histogram(payload, backend="matplotlib")
render_histogram(payload, backend="rust")
render_violin(payload, backend="matplotlib")
render_violin(payload, backend="rust")
render_iqr(payload, backend="matplotlib")
render_iqr(payload, backend="rust")
render_scatter(payload, backend="matplotlib")
render_scatter(payload, backend="rust")
```

Lower-level Rust/native target:

```python
render_histogram_png(spec: Mapping[str, object]) -> ChartRenderResult
render_distribution_png(spec: Mapping[str, object]) -> ChartRenderResult
render_iqr_png(spec: Mapping[str, object]) -> ChartRenderResult
render_trend_png(spec: Mapping[str, object]) -> ChartRenderResult
```

The Rust/native result should expose:

- `png_bytes`
- `backend`
- optional render metadata

## Dependencies to keep out of Rust/native backend

- matplotlib figures and artists
- `pyplot`
- `Line2D`, `Patch`, `Rectangle`
- artist geometry extraction modules
- workbook geometry and Excel anchors
- Qt or thread state
- Google/export orchestration

## Porting sequence

1. Add resolved spec models in `hexafe_plotstats.models.render` or `hexafe_plotstats.models.specs`.
2. Add mapping conversion for existing payloads.
3. Port histogram native path first because it has the richest resolved spec and table/annotation requirements.
4. Add byte-oriented `ChartRenderResult` for Rust/native PNG output.
5. Wire `backend="rust"` to the native extension when available.
6. Add parity tests chart by chart using matplotlib as oracle, but avoid pixel-perfect tests at first.
7. Tune Rust output toward 1:1 matplotlib parity.

## Non-goals

- Do not make Rust the default backend.
- Do not require Rust for normal package import.
- Do not require matplotlib artist extraction in normal Rust rendering.
- Do not port workbook/export thread orchestration.

