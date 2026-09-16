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
from src.contrast import GRAPHIC_MIN, TEXT_MIN, contrast_ratio  # noqa: E402


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

    print("\nStructural")
    line("gridline", config.GRIDLINE_COLOR, None if config.GRIDLINE_EXEMPT else GRAPHIC_MIN)

    print(f"\nMax simultaneous series: {config.MAX_SERIES}")
    if failures:
        print(f"\n{failures} color(s) below floor", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(report())
