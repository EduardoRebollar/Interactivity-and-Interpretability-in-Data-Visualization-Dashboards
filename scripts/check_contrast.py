"""Print a WCAG 2.1 contrast report for the locked palette.

The floors are enforced by `tests/test_palette.py`; this script is for reading the actual numbers,
e.g. when writing up the accessibility section or considering a palette change.

Usage:
    uv run python scripts/check_contrast.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402
from src.contrast import (  # noqa: E402
    CVD_MATRICES,
    GRAPHIC_MIN,
    PRIMARY_VISION,
    TEXT_MIN,
    contrast_ratio,
    weakest_pair,
)


def report() -> int:
    """Print every palette color with its measured ratio. Returns a process exit code."""
    background = config.BACKGROUND
    failures = 0

    def line(label: str, color: str, floor: float | None) -> None:
        nonlocal failures
        ratio = contrast_ratio(color, background)
        if floor is None:
            verdict = "exempt"
        elif ratio >= floor:
            verdict = "pass"
        else:
            verdict = "FAIL"
            failures += 1
        print(f"  {label:22s} {color}  {ratio:6.2f}:1  {verdict}")

    print(f"Background: {background}\n")

    print(f"Series colors (floor {GRAPHIC_MIN}:1)")
    for index, color in enumerate(config.SERIES_COLORS):
        line(f"series {index + 1}", color, GRAPHIC_MIN)
    line("reference (World)", config.REFERENCE_COLOR, GRAPHIC_MIN)

    print(f"\nText (floor {TEXT_MIN}:1)")
    line("primary", config.TEXT_PRIMARY, TEXT_MIN)
    line("muted", config.TEXT_MUTED, TEXT_MIN)
    line("axis", config.AXIS_COLOR, TEXT_MIN)
    # UI chrome, not a series colour, but it is text and so takes the text floor.
    line("error", config.ERROR_COLOR, TEXT_MIN)

    print("\nStructural")
    line("gridline", config.GRIDLINE_COLOR, None if config.GRIDLINE_EXEMPT else GRAPHIC_MIN)

    print(
        f"\nSeries colours told apart (CIEDE2000, floor {config.MIN_CVD_DISTANCE} under normal, "
        "deutan and protan)"
    )
    for vision in CVD_MATRICES:
        distance, first, second = weakest_pair(config.SERIES_COLORS, (vision,))
        floor = config.MIN_CVD_DISTANCE if vision in PRIMARY_VISION else None
        verdict = "reported" if floor is None else ("pass" if distance >= floor else "FAIL")
        if verdict == "FAIL":
            failures += 1
        print(f"  weakest pair, {vision:7s} {first} / {second}  {distance:5.1f} dE  {verdict}")

    print(
        f"\nSequential scale, heatmap and map: exempt on the background, but the map's borders "
        f"({config.MAP_BORDER_COLOR}) must reach {GRAPHIC_MIN}:1 against every fill up to 50%"
    )
    separate_border = background != config.MAP_BORDER_COLOR
    for position, color in config.SEQUENTIAL_SCALE:
        border = contrast_ratio(config.MAP_BORDER_COLOR, color)
        needs_border = position <= 0.5
        if needs_border and border < GRAPHIC_MIN:
            failures += 1
        flag = ("pass" if border >= GRAPHIC_MIN else "FAIL") if needs_border else "exempt"
        against = f"  on background {contrast_ratio(color, background):5.2f}:1" * separate_border
        print(f"  {position:5.3f} {color}  against border {border:5.2f}:1{against}  {flag}")

    print(f"\nMax simultaneous series: {config.MAX_SERIES}")
    if failures:
        print(f"\n{failures} color(s) below floor", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(report())
