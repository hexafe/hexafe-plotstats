from __future__ import annotations

from hexafe_plotstats.adapters.pandas import grouped_violin_payload, series_capability, series_summary
from hexafe_plotstats.models.common import SpecLimits


def main() -> None:
    try:
        import pandas as pd
    except Exception as exc:
        raise SystemExit(f"pandas is not available: {exc}")

    frame = pd.DataFrame(
        {
            "group": ["a", "a", "b", "b"],
            "value": [1.0, 2.0, 3.0, 4.0],
        }
    )
    limits = SpecLimits(lsl=0.5, usl=4.5)

    print(series_summary(frame["value"], limits))
    print(series_capability(frame["value"], limits))
    print(grouped_violin_payload(frame, "value", "group", spec_limits=limits))


if __name__ == "__main__":
    main()
