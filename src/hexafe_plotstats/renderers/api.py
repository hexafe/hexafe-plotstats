from __future__ import annotations

from importlib.util import find_spec

from .base import (
    NativeRendererBackend,
    NativeRenderProfile,
    RendererBackend,
    RendererBackendCapability,
    RendererBackendUnavailable,
)
from ..models.payloads import HistogramPayload, IQRPayload, ScatterPayload, ViolinPayload
from ..models.render import ChartRenderResult, RenderResult


def renderer_backend_available(backend: RendererBackend) -> bool:
    if backend == "matplotlib":
        return True
    if backend == "rust":
        from .rust import native_backend_available

        return native_backend_available()
    if backend == "plotly":
        return find_spec("plotly") is not None
    raise ValueError(f"unsupported renderer backend: {backend}")


def renderer_backend_capabilities() -> tuple[RendererBackendCapability, ...]:
    rust_available = renderer_backend_available("rust")
    rust_message = (
        "rust native module is installed"
        if rust_available
        else "rust renderer is explicit opt-in and no native module is installed"
    )
    plotly_available = renderer_backend_available("plotly")
    plotly_message = "plotly is installed" if plotly_available else "plotly renderer requires the optional plotly extra"
    return (
        RendererBackendCapability(
            backend="matplotlib",
            available=True,
            default=True,
            message="default renderer backend",
        ),
        RendererBackendCapability(
            backend="rust",
            available=rust_available,
            default=False,
            message=rust_message,
        ),
        RendererBackendCapability(
            backend="plotly",
            available=plotly_available,
            default=False,
            message=plotly_message,
        ),
    )


def render_histogram(
    payload: HistogramPayload,
    *,
    backend: RendererBackend = "matplotlib",
    profile: NativeRenderProfile = "fast",
) -> RenderResult | ChartRenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_histogram_matplotlib

        return render_histogram_matplotlib(payload)
    if backend == "rust":
        from .rust import render_histogram_rust

        return render_histogram_rust(payload, profile=profile)
    if backend == "plotly":
        raise RendererBackendUnavailable("plotly renderer for histogram is not implemented yet")
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_violin(
    payload: ViolinPayload,
    *,
    backend: RendererBackend = "matplotlib",
    profile: NativeRenderProfile = "fast",
) -> RenderResult | ChartRenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_violin_matplotlib

        return render_violin_matplotlib(payload)
    if backend == "rust":
        from .rust import render_violin_rust

        return render_violin_rust(payload, profile=profile)
    if backend == "plotly":
        raise RendererBackendUnavailable("plotly renderer for violin is not implemented yet")
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_iqr(
    payload: IQRPayload,
    *,
    backend: RendererBackend = "matplotlib",
    profile: NativeRenderProfile = "fast",
) -> RenderResult | ChartRenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_iqr_matplotlib

        return render_iqr_matplotlib(payload)
    if backend == "rust":
        from .rust import render_iqr_rust

        return render_iqr_rust(payload, profile=profile)
    if backend == "plotly":
        raise RendererBackendUnavailable("plotly renderer for iqr is not implemented yet")
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_scatter(
    payload: ScatterPayload,
    *,
    backend: RendererBackend = "matplotlib",
    profile: NativeRenderProfile = "fast",
) -> RenderResult | ChartRenderResult:
    if backend == "matplotlib":
        from .matplotlib import render_scatter_matplotlib

        return render_scatter_matplotlib(payload)
    if backend == "rust":
        from .rust import render_scatter_rust

        return render_scatter_rust(payload, profile=profile)
    if backend == "plotly":
        from .plotly import render_scatter_plotly

        return render_scatter_plotly(payload)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_histogram_png(
    payload: HistogramPayload,
    *,
    backend: NativeRendererBackend = "rust",
    profile: NativeRenderProfile = "fast",
) -> ChartRenderResult:
    if backend == "rust":
        from .rust import render_histogram_png as render_histogram_png_rust

        return render_histogram_png_rust(payload, profile=profile)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_violin_png(
    payload: ViolinPayload,
    *,
    backend: NativeRendererBackend = "rust",
    profile: NativeRenderProfile = "fast",
) -> ChartRenderResult:
    if backend == "rust":
        from .rust import render_violin_png as render_violin_png_rust

        return render_violin_png_rust(payload, profile=profile)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_iqr_png(
    payload: IQRPayload,
    *,
    backend: NativeRendererBackend = "rust",
    profile: NativeRenderProfile = "fast",
) -> ChartRenderResult:
    if backend == "rust":
        from .rust import render_iqr_png as render_iqr_png_rust

        return render_iqr_png_rust(payload, profile=profile)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_scatter_png(
    payload: ScatterPayload,
    *,
    backend: NativeRendererBackend = "rust",
    profile: NativeRenderProfile = "fast",
) -> ChartRenderResult:
    if backend == "rust":
        from .rust import render_scatter_png as render_scatter_png_rust

        return render_scatter_png_rust(payload, profile=profile)
    raise ValueError(f"unsupported renderer backend: {backend}")


def render_scatter_trend_png(
    payload: ScatterPayload,
    *,
    backend: NativeRendererBackend = "rust",
    profile: NativeRenderProfile = "fast",
) -> ChartRenderResult:
    if backend == "rust":
        from .rust import render_scatter_trend_png as render_scatter_trend_png_rust

        return render_scatter_trend_png_rust(payload, profile=profile)
    raise ValueError(f"unsupported renderer backend: {backend}")
