from __future__ import annotations

from ..models.payloads import HistogramPayload, IQRPayload, ScatterPayload, ViolinPayload
from ..models.render import RenderResult
from .base import RendererBackend


def render_histogram(payload: HistogramPayload, *, backend: RendererBackend = "matplotlib") -> RenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_histogram_matplotlib

        return render_histogram_matplotlib(payload)
    if backend == "rust":
        from .rust import render_histogram_rust

        return render_histogram_rust(payload)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_violin(payload: ViolinPayload, *, backend: RendererBackend = "matplotlib") -> RenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_violin_matplotlib

        return render_violin_matplotlib(payload)
    if backend == "rust":
        from .rust import render_violin_rust

        return render_violin_rust(payload)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_iqr(payload: IQRPayload, *, backend: RendererBackend = "matplotlib") -> RenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_iqr_matplotlib

        return render_iqr_matplotlib(payload)
    if backend == "rust":
        from .rust import render_iqr_rust

        return render_iqr_rust(payload)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_scatter(payload: ScatterPayload, *, backend: RendererBackend = "matplotlib") -> RenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_scatter_matplotlib

        return render_scatter_matplotlib(payload)
    if backend == "rust":
        from .rust import render_scatter_rust

        return render_scatter_rust(payload)
    raise ValueError(f"unsupported renderer backend: {backend}")

