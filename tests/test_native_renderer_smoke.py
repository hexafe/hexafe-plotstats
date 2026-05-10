from __future__ import annotations

import struct
import zlib
import os
from collections.abc import Callable
from io import BytesIO
from typing import Any

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg", force=True)

from hexafe_plotstats import (
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
    render_scatter_trend_png,
    render_violin,
    render_violin_png,
)
from hexafe_plotstats.models import ChartRenderResult
from hexafe_plotstats.renderers.rust import native_backend_available, native_backend_module_name

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth_predictor(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def _png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    assert data.startswith(PNG_SIGNATURE), "PNG signature is missing"
    offset = len(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(data):
        assert offset + 8 <= len(data), "PNG chunk header is truncated"
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        chunk_end = chunk_data_end + 4
        assert chunk_end <= len(data), f"PNG chunk {chunk_type!r} is truncated"
        chunks.append((chunk_type, data[chunk_data_start:chunk_data_end]))
        offset = chunk_end
        if chunk_type == b"IEND":
            break
    return chunks


def _decode_png_pixels(data: bytes) -> tuple[int, int, bytes]:
    chunks = _png_chunks(data)
    ihdr = next(chunk_data for chunk_type, chunk_data in chunks if chunk_type == b"IHDR")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", ihdr)
    assert width > 0 and height > 0
    assert bit_depth == 8, f"unsupported PNG bit depth: {bit_depth}"
    assert color_type in {0, 2, 6}, f"unsupported PNG color type: {color_type}"
    assert compression == 0 and filter_method == 0 and interlace == 0

    channels = {0: 1, 2: 3, 6: 4}[color_type]
    bytes_per_pixel = channels
    row_length = width * channels
    compressed = b"".join(chunk_data for chunk_type, chunk_data in chunks if chunk_type == b"IDAT")
    raw = zlib.decompress(compressed)
    assert len(raw) == height * (row_length + 1)

    rows: list[bytes] = []
    previous = bytes(row_length)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = bytearray(raw[cursor : cursor + row_length])
        cursor += row_length
        reconstructed = bytearray(row_length)
        for index, value in enumerate(scanline):
            left = reconstructed[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            up = previous[index]
            upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            if filter_type == 0:
                reconstructed[index] = value
            elif filter_type == 1:
                reconstructed[index] = (value + left) & 0xFF
            elif filter_type == 2:
                reconstructed[index] = (value + up) & 0xFF
            elif filter_type == 3:
                reconstructed[index] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                reconstructed[index] = (value + _paeth_predictor(left, up, upper_left)) & 0xFF
            else:
                raise AssertionError(f"unsupported PNG filter type: {filter_type}")
        previous = bytes(reconstructed)
        rows.append(previous)
    return width, height, b"".join(rows)


def assert_valid_nonblank_png(data: bytes) -> tuple[int, int]:
    width, height, pixels = _decode_png_pixels(data)
    first_pixel = pixels[: len(pixels) // (width * height)]
    assert first_pixel, "PNG has no pixels"
    distinct_pixels = {
        pixels[index : index + len(first_pixel)]
        for index in range(0, len(pixels), len(first_pixel))
    }
    assert len(distinct_pixels) > 1, "PNG pixels are all identical"
    return width, height


def assert_title_text_pixels_present(data: bytes) -> None:
    width, height, pixels = _decode_png_pixels(data)
    channels = len(pixels) // (width * height)
    assert channels in {1, 3, 4}

    dark_pixels = 0
    y_stop = min(height, 44)
    x_stop = min(width, 280)
    for y in range(8, y_stop):
        row_offset = y * width * channels
        for x in range(20, x_stop):
            index = row_offset + x * channels
            rgb = pixels[index : index + min(channels, 3)]
            if rgb and min(rgb) < 230:
                dark_pixels += 1

    assert dark_pixels > 10, "native PNG title text was not rasterized"


def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)


def _make_test_png(width: int, height: int, pixels: list[bytes]) -> bytes:
    assert len(pixels) == width * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    rows = []
    for row in range(height):
        start = row * width
        rows.append(b"\x00" + b"".join(pixels[start : start + width]))
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(b"".join(rows))) + _chunk(b"IEND", b"")


def _native_smoke_cases() -> tuple[tuple[str, Callable[[Any], ChartRenderResult], Any], ...]:
    limits = SpecLimits(lsl=0.5, nominal=2.5, usl=4.5)
    return (
        (
            "histogram",
            render_histogram_png,
            build_histogram_payload(
                [1.0, 1.2, 1.8, 2.4, 2.9, 3.3, 3.9, 4.2],
                limits,
                HistogramConfig(bins=4, density=False, include_fit=False),
            ),
        ),
        (
            "scatter",
            render_scatter_png,
            build_scatter_payload([0.0, 1.0, 2.0, 3.0], [1.0, 1.5, 3.0, 3.8], ScatterConfig(include_trend=False)),
        ),
        (
            "scatter_trend",
            render_scatter_trend_png,
            build_scatter_payload([0.0, 1.0, 2.0, 3.0], [1.0, 1.5, 3.0, 3.8], ScatterConfig(include_trend=True)),
        ),
        (
            "iqr",
            render_iqr_png,
            build_iqr_payload({"A": [1.0, 1.1, 1.2, 3.0], "B": [2.0, 2.1, 2.2, 2.3]}, limits, IQRConfig(whis=1.0)),
        ),
        (
            "violin",
            render_violin_png,
            build_violin_payload({"A": [1.0, 1.4, 1.8, 2.0], "B": [2.2, 2.5, 2.9, 3.1]}, limits),
        ),
    )


def _native_parity_cases() -> tuple[tuple[str, Callable[[Any], Any], Callable[[Any], ChartRenderResult], Any], ...]:
    limits = SpecLimits(lsl=0.5, nominal=2.5, usl=4.5)
    return (
        (
            "histogram",
            render_histogram,
            render_histogram_png,
            build_histogram_payload(
                [1.0, 1.2, 1.8, 2.4, 2.9, 3.3, 3.9, 4.2],
                limits,
                HistogramConfig(bins=4, density=False, include_fit=False),
            ),
        ),
        (
            "scatter",
            render_scatter,
            render_scatter_png,
            build_scatter_payload([0.0, 1.0, 2.0, 3.0], [1.0, 1.5, 3.0, 3.8], ScatterConfig(include_trend=True)),
        ),
        (
            "iqr",
            render_iqr,
            render_iqr_png,
            build_iqr_payload({"A": [1.0, 1.1, 1.2, 3.0], "B": [2.0, 2.1, 2.2, 2.3]}, limits, IQRConfig(whis=1.0)),
        ),
        (
            "violin",
            render_violin,
            render_violin_png,
            build_violin_payload({"A": [1.0, 1.4, 1.8, 2.0], "B": [2.2, 2.5, 2.9, 3.1]}, limits),
        ),
    )


def _matplotlib_png(renderer: Callable[[Any], Any], payload: Any) -> bytes:
    import matplotlib.pyplot as plt

    result = renderer(payload)
    buffer = BytesIO()
    try:
        result.fig.canvas.draw()
        result.fig.savefig(buffer, format="png", dpi=100)
    finally:
        plt.close(result.fig)
    return buffer.getvalue()


def test_png_validity_helper_accepts_nonblank_png() -> None:
    png = _make_test_png(
        2,
        1,
        [
            bytes((255, 255, 255, 255)),
            bytes((0, 0, 0, 255)),
        ],
    )

    assert assert_valid_nonblank_png(png) == (2, 1)


def test_png_validity_helper_rejects_blank_png() -> None:
    png = _make_test_png(2, 1, [bytes((255, 255, 255, 255)), bytes((255, 255, 255, 255))])

    with pytest.raises(AssertionError, match="all identical"):
        assert_valid_nonblank_png(png)


def test_native_renderer_availability_probe_is_stable() -> None:
    available = native_backend_available()

    assert isinstance(available, bool)
    if available:
        assert native_backend_module_name() in {"_hexafe_plotstats_native", "hexafe_plotstats_native"}
    else:
        assert native_backend_module_name() is None


@pytest.mark.parametrize(("chart_name", "renderer", "payload"), _native_smoke_cases())
def test_native_renderer_returns_valid_nonblank_png_or_skips_cleanly(
    chart_name: str,
    renderer: Callable[[Any], ChartRenderResult],
    payload: Any,
) -> None:
    if not native_backend_available():
        pytest.skip("native renderer extension is unavailable")

    result = renderer(payload)

    assert result.backend == "rust"
    width, height = assert_valid_nonblank_png(result.png_bytes)
    assert width > 0
    assert height > 0
    assert_title_text_pixels_present(result.png_bytes)
    if "chart" in result.metadata:
        assert result.metadata["chart"] in {chart_name, chart_name.replace("_trend", "")}
    assert result.metadata.get("render_profile") == "fast"
    if os.environ.get("HEXAFE_PLOTSTATS_NATIVE_TEXT", "").lower() == "resvg":
        assert str(result.metadata.get("svg", "")).startswith("<?xml")
    else:
        assert "svg" not in result.metadata
    assert result.metadata.get("png_compression") in {None, "none", "fastest", "fast", "balanced", "high"}


def test_native_debug_profile_returns_svg_or_skips_cleanly() -> None:
    if not native_backend_available():
        pytest.skip("native renderer extension is unavailable")

    payload = build_histogram_payload([1, 2, 3], metadata={"title": "Debug SVG"})
    result = render_histogram_png(payload, profile="debug")

    assert result.metadata.get("render_profile") == "debug"
    assert str(result.metadata.get("svg", "")).startswith("<?xml")
    assert result.metadata.get("png_compression") == "balanced"


@pytest.mark.parametrize(("chart_name", "matplotlib_renderer", "rust_renderer", "payload"), _native_parity_cases())
def test_native_renderer_is_visually_close_to_matplotlib_or_skips_cleanly(
    chart_name: str,
    matplotlib_renderer: Callable[[Any], Any],
    rust_renderer: Callable[[Any], ChartRenderResult],
    payload: Any,
) -> None:
    if not native_backend_available():
        pytest.skip("native renderer extension is unavailable")

    rust_png = rust_renderer(payload).png_bytes
    matplotlib_png = _matplotlib_png(matplotlib_renderer, payload)

    rust_width, rust_height, rust_pixels = _decode_png_pixels(rust_png)
    matplotlib_width, matplotlib_height, matplotlib_pixels = _decode_png_pixels(matplotlib_png)
    assert (rust_width, rust_height) == (matplotlib_width, matplotlib_height), chart_name

    rust_array = np.frombuffer(rust_pixels, dtype=np.uint8).astype(np.int16)
    matplotlib_array = np.frombuffer(matplotlib_pixels, dtype=np.uint8).astype(np.int16)
    mean_abs_diff = float(np.mean(np.abs(rust_array - matplotlib_array)))
    assert mean_abs_diff < 15.0, chart_name
