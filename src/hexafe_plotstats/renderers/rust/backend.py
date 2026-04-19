from __future__ import annotations

from ...models.payloads import HistogramPayload, IQRPayload, ScatterPayload, ViolinPayload
from ...models.render import RenderResult
from ..base import RendererBackendUnavailable


def _unavailable(chart: str) -> RenderResult:
    raise RendererBackendUnavailable(
        f"rust renderer for {chart} is not installed yet; use backend='matplotlib' "
        "or install the future rust backend extra once it is available"
    )


def render_histogram_rust(payload: HistogramPayload) -> RenderResult:
    return _unavailable("histogram")


def render_violin_rust(payload: ViolinPayload) -> RenderResult:
    return _unavailable("violin")


def render_iqr_rust(payload: IQRPayload) -> RenderResult:
    return _unavailable("iqr")


def render_scatter_rust(payload: ScatterPayload) -> RenderResult:
    return _unavailable("scatter")

