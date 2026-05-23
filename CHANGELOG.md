# Changelog

## Unreleased

- Add semi-opaque backgrounds behind static Matplotlib scatter reference-line
  annotations so LSL, Nominal, and USL labels stay readable over the plotted
  lines.

## 0.1.0a1 - 2026-05-16

- Add Plotly backend coverage for histogram, scatter, IQR, and violin.
- Keep histogram, IQR, and violin Plotly output static by default for dashboards.
- Aggregate large Plotly scatter output by default, with raw points represented as a static legend-controlled raster layer.
- Optimize 1M-row grouped IQR and violin payload/spec paths by keeping large arrays internally and serializing bounded resolved geometry.
- Add reusable 1M x 5 benchmark tooling.
- Add serializable theme tokens, configurable tick counts, and basic locale APIs.
- Add Metroliza dashboard payload adapter for plotstats-backed Plotly specs.
