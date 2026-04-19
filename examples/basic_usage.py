from __future__ import annotations

from hexafe_plotstats import (
    SpecLimits,
    build_histogram_payload,
    compute_capability,
    fit_distribution,
    render_histogram,
    summarize_distribution,
)
from hexafe_plotstats.stats import detect_support


def main() -> None:
    values = [9.8, 10.0, 10.1, 9.9, 10.2, 10.3]
    limits = SpecLimits(lsl=9.5, nominal=10.0, usl=10.5)

    summary = summarize_distribution(values, limits)
    cap = compute_capability(values, limits)
    support = detect_support(values)
    fit = fit_distribution(values, limits)
    payload = build_histogram_payload(values, limits)

    print(f"count={summary.count} cpk={cap.cpk:.3f} support={support.kind} fit={fit.selected}")

    result = render_histogram(payload, backend="matplotlib")
    result.fig.canvas.draw()
    print(f"rendered={len(result.fig.axes)} axes")


if __name__ == "__main__":
    main()
