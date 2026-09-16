"""Accessibility floors for the palette, enforced at build time.

CLAUDE.md requires WCAG 2.1 AA contrast and forbids proposing colors without checking them. These
tests are that check: if anyone edits a swatch in config.py and drops below the floor, the suite
fails rather than the study shipping with an inaccessible chart.
"""

from __future__ import annotations

import pytest

from src import config
from src.contrast import (
    GRAPHIC_MIN,
    TEXT_MIN,
    contrast_ratio,
    darken_to_ratio,
    hex_to_rgb,
    relative_luminance,
)

BG = config.BACKGROUND


# --- The math itself --------------------------------------------------------------------------


def test_known_contrast_anchors():
    """Black on white is 21:1 and identical colors are 1:1, by definition."""
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=0.01)


def test_contrast_is_symmetric():
    assert contrast_ratio("#0072B2", "#FFFFFF") == pytest.approx(
        contrast_ratio("#FFFFFF", "#0072B2")
    )


def test_luminance_bounds():
    assert relative_luminance("#000000") == pytest.approx(0.0, abs=1e-9)
    assert relative_luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-9)


def test_hex_parsing_accepts_both_forms():
    assert hex_to_rgb("#0072B2") == hex_to_rgb("0072B2") == (0, 114, 178)


def test_hex_parsing_rejects_malformed():
    with pytest.raises(ValueError, match="6-digit"):
        hex_to_rgb("#FFF")


def test_darken_leaves_passing_colors_alone():
    assert darken_to_ratio("#0072B2", BG, GRAPHIC_MIN) == "#0072B2"


def test_darken_fixes_failing_colors():
    """Okabe-Ito sky blue fails on white; the corrected form must pass."""
    assert contrast_ratio("#56B4E9", BG) < GRAPHIC_MIN
    assert contrast_ratio(darken_to_ratio("#56B4E9", BG, GRAPHIC_MIN), BG) >= GRAPHIC_MIN


# --- The palette in use -----------------------------------------------------------------------


@pytest.mark.parametrize("color", config.SERIES_COLORS)
def test_series_colors_meet_graphical_floor(color):
    ratio = contrast_ratio(color, BG)
    assert ratio >= GRAPHIC_MIN, f"{color} is {ratio:.2f}:1, below {GRAPHIC_MIN}:1"


def test_reference_color_meets_graphical_floor():
    assert contrast_ratio(config.REFERENCE_COLOR, BG) >= GRAPHIC_MIN


@pytest.mark.parametrize(
    "color",
    [config.TEXT_PRIMARY, config.TEXT_MUTED, config.AXIS_COLOR, config.ERROR_COLOR],
)
def test_text_colors_meet_text_floor(color):
    ratio = contrast_ratio(color, BG)
    assert ratio >= TEXT_MIN, f"{color} is {ratio:.2f}:1, below {TEXT_MIN}:1"


def test_the_error_colour_is_not_a_series_colour():
    """It is UI chrome. Reusing a series colour would put a data colour on non-data text — and the
    vermillion it derives from is 3.87:1, fine for a 2.5px line but below the 4.5:1 text floor."""
    assert config.ERROR_COLOR not in config.SERIES_COLORS
    assert contrast_ratio(config.ERROR_COLOR, BG) >= TEXT_MIN


def test_series_colors_are_distinct():
    assert len(set(config.SERIES_COLORS)) == len(config.SERIES_COLORS)
    assert config.REFERENCE_COLOR not in config.SERIES_COLORS


def test_series_colors_are_separated_in_luminance():
    """Hue alone is not enough.

    Darkening several colors to the same contrast target makes them luminance-identical, which
    defeats greyscale printing and severe color-vision deficiency. This test caught exactly that:
    an earlier palette had three swatches all corrected to 3.2:1, leaving luminance gaps of 0.0008.
    """
    ranked = sorted((relative_luminance(c), c) for c in config.SERIES_COLORS)
    for (dark_l, dark_c), (light_l, light_c) in zip(ranked[:-1], ranked[1:], strict=True):
        gap = light_l - dark_l
        assert gap >= config.MIN_LUMINANCE_GAP, (
            f"{dark_c} and {light_c} differ by only {gap:.4f} in luminance"
        )


def test_max_series_matches_available_colors():
    """The display cap must never exceed the number of accessible colors we actually have."""
    assert len(config.SERIES_COLORS) == config.MAX_SERIES
    assert config.MAX_SERIES <= 8, "beyond ~8 series, lines cannot be told apart"


def test_gridline_exemption_is_declared_and_bounded():
    """The gridline sits below the graphical floor on purpose; keep that explicit and bounded."""
    ratio = contrast_ratio(config.GRIDLINE_COLOR, BG)
    assert config.GRIDLINE_EXEMPT
    assert ratio < GRAPHIC_MIN, "gridline now passes; drop the exemption flag"
    assert ratio >= 1.8, f"gridline at {ratio:.2f}:1 is too faint to estimate values against"


def test_y_range_is_pinned_full_scale():
    """A y-axis that rescales would change apparent steepness between tasks or conditions."""
    assert config.Y_RANGE == (0, 100)
