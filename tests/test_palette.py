"""Accessibility floors for the palette, enforced at build time.

CLAUDE.md requires WCAG 2.1 AA contrast and forbids proposing colors without checking them. These
tests are that check: if anyone edits a swatch in config.py and drops below the floor, the suite
fails rather than the study shipping with an inaccessible chart.
"""

from __future__ import annotations

import re

import pytest

from src import config, contrast
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


# --- Colour-vision deficiency (visual-spec.md section 4, 2026-09-23) -----------------------------


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
        ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ],
)
def test_ciede2000_matches_the_published_test_data(first, second, expected):
    """Pairs 1, 7 and 17 of Sharma, Wu and Dalal (2005). A floor measured with a wrong formula
    would hold nothing."""
    assert contrast.delta_e2000(first, second) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("vision", list(contrast.CVD_MATRICES))
def test_simulation_leaves_a_neutral_grey_neutral(vision):
    """Each Machado row sums to 1, so a grey is seen as the same grey."""
    grey = contrast.simulate("#777777", vision)
    assert max(grey) - min(grey) == pytest.approx(0.0, abs=1e-5)


def test_series_colors_stay_apart_under_colour_vision_deficiency():
    """WCAG contrast says each colour stands out from white, not that two colours can be told
    apart. The floor holds in normal vision and under simulated deuteranopia and protanopia."""
    distance, first, second = contrast.weakest_pair(config.SERIES_COLORS)
    assert distance >= config.MIN_CVD_DISTANCE, (
        f"{first} and {second} are {distance:.1f} dE apart; the floor is {config.MIN_CVD_DISTANCE}"
    )


def test_the_dropped_orange_was_indistinguishable_from_vermillion():
    """Why the five-colour palette lost its darkened Okabe-Ito orange (2026-09-23)."""
    assert contrast.cvd_distance("#9C6C00", "#D55E00", ("protan",)) < 2.0
    assert "#9C6C00" not in config.SERIES_COLORS


def test_no_series_colour_can_be_mistaken_for_the_world_reference():
    for color in config.SERIES_COLORS:
        distance = contrast.cvd_distance(color, config.REFERENCE_COLOR)
        assert distance >= config.MIN_CVD_DISTANCE, f"{color} is {distance:.1f} dE from black"


def test_marker_symbols_give_every_scatter_series_its_own_shape():
    """The scatter's second channel: colour is never the only one (visual-spec.md section 6)."""
    assert len(config.MARKER_SYMBOLS) >= config.MAX_SERIES
    assert len(set(config.MARKER_SYMBOLS)) == len(config.MARKER_SYMBOLS)


# --- The sequential scale (heatmap and map) ------------------------------------------------------


def _lightness(color: str, vision: str = "normal") -> float:
    return contrast.to_lab(contrast.simulate(color, vision))[0]


@pytest.mark.parametrize("vision", ["normal", "deutan", "protan"])
def test_the_sequential_scale_is_dark_for_low_coverage_and_lightens_steadily(vision):
    """The prompts say darker means lower. That must stay true, step by step, with colour-vision
    deficiency too: cividis was chosen because it does."""
    stops = [color for _position, color in config.SEQUENTIAL_SCALE]
    lightness = [_lightness(color, vision) for color in stops]
    assert lightness == sorted(lightness)
    assert len(set(lightness)) == len(lightness)


def test_the_sequential_scale_runs_the_full_range():
    positions = [position for position, _color in config.SEQUENTIAL_SCALE]
    assert positions[0] == 0.0 and positions[-1] == 1.0
    assert positions == sorted(positions)


def test_the_sequential_exemption_is_declared_and_bounded():
    """The light end is below 3:1 on white on purpose (visual-spec.md section 4). What must hold
    instead: the white borders between countries stand out from every fill a country below 50%
    can have, which are the countries the map question counts."""
    assert config.SEQUENTIAL_EXEMPT
    lightest = config.SEQUENTIAL_SCALE[-1][1]
    assert contrast_ratio(lightest, BG) < GRAPHIC_MIN, "the scale now passes; drop the exemption"
    for position, color in config.SEQUENTIAL_SCALE:
        if position <= 0.5:
            ratio = contrast_ratio(config.MAP_BORDER_COLOR, color)
            assert ratio >= GRAPHIC_MIN, f"border vs {color}: {ratio:.2f}:1"


# --- The page chrome: study.css (docs/visual-spec.md section 10) ----------------------------------

STYLESHEET = config.PROJECT_ROOT / "src" / "assets" / "study.css"
GROUNDS = ("c-card", "c-page", "c-band")

# Text, on every ground the stylesheet sets it on. Names are study.css's `--c-*` tokens.
CHROME_TEXT = [
    *[("c-ink", ground) for ground in (*GROUNDS, "c-soft-hov")],
    *[("c-muted", ground) for ground in (*GROUNDS, "c-disabled-bg")],
    *[("c-accent", ground) for ground in GROUNDS],
    *[("c-accent-hov", ground) for ground in GROUNDS],  # a hovered link
    *[("c-error-text", ground) for ground in GROUNDS],
    ("#FFFFFF", "c-accent"),  # the primary button, a done step's tick, the step numbers
    ("#FFFFFF", "c-accent-hov"),  # the primary button, hovered
    ("#FFFFFF", "c-error"),  # the pending-approval banner
    ("#000000", "#FFFFFF"),  # the consent sheet
]

# Control edges, focus rings, selected edges and error borders, on the grounds they sit on.
CHROME_GRAPHIC = [
    *[("c-line", ground) for ground in GROUNDS],
    *[("c-focus", ground) for ground in ("c-card", "c-page")],
    *[("c-accent", ground) for ground in GROUNDS],
    *[("c-error", ground) for ground in GROUNDS],
]

# Never text, and never the only edge of a control: dividers, group outlines, the background's
# shapes. Grouped controls keep their own edges.
CHROME_DECORATIVE = {"c-line-soft", "c-group", "c-deco-1", "c-deco-2"}

# The one exemption: Submit's fill while saving (see the test below).
CHROME_EXEMPT = {"c-accent-busy"}


def _stylesheet() -> str:
    return re.sub(r"/\*.*?\*/", "", STYLESHEET.read_text(encoding="utf-8"), flags=re.S)


def _tokens() -> dict[str, str]:
    """study.css's colour tokens as it ships: `c-page` -> `#F8F3EE`."""
    return dict(re.findall(r"--(c-[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\b", _stylesheet()))


def _hex(name: str) -> str:
    return name if name.startswith("#") else _tokens()[name]


@pytest.mark.parametrize(("foreground", "ground"), CHROME_TEXT)
def test_chrome_text_meets_the_text_floor(foreground, ground):
    ratio = contrast_ratio(_hex(foreground), _hex(ground))
    assert ratio >= TEXT_MIN, f"{foreground} on {ground}: {ratio:.2f}:1"


@pytest.mark.parametrize(("foreground", "ground"), CHROME_GRAPHIC)
def test_chrome_edges_meet_the_graphical_floor(foreground, ground):
    ratio = contrast_ratio(_hex(foreground), _hex(ground))
    assert ratio >= GRAPHIC_MIN, f"{foreground} on {ground}: {ratio:.2f}:1"


def test_every_chrome_colour_is_measured_or_declared():
    """A token added to study.css must be put in one of the lists above before it can ship."""
    measured = {name for pair in CHROME_TEXT + CHROME_GRAPHIC for name in pair}
    assert set(_tokens()) <= measured | CHROME_DECORATIVE | CHROME_EXEMPT


def test_every_text_colour_in_the_stylesheet_is_measured():
    """Whatever study.css sets as `color` must be one of the measured foregrounds."""
    used = set(
        re.findall(
            r"(?<![\w-])color:\s*(?:var\(--(c-[a-z0-9-]+)\)|(#[0-9A-Fa-f]{6}))", _stylesheet()
        )
    )
    foregrounds = {foreground for foreground, _ground in CHROME_TEXT}
    for token, literal in used:
        assert (token or literal.upper()) in foregrounds, token or literal
        assert token not in CHROME_DECORATIVE


def test_the_saving_fill_exemption_is_declared_and_bounded():
    """Submit's fill while saving gives its white label less than 4.5:1. The button is disabled at
    that moment, and WCAG 1.4.3 exempts inactive controls (visual-spec.md section 10). It must stay
    the busy state's fill and nothing else, and stay legible."""
    ratio = contrast_ratio("#FFFFFF", _tokens()["c-accent-busy"])
    assert ratio < TEXT_MIN, "the fill now passes; drop the exemption"
    assert ratio >= GRAPHIC_MIN
    selectors = re.findall(r"([^{}]+)\{[^{}]*var\(--c-accent-busy\)", _stylesheet())
    assert selectors
    assert all('[aria-busy="true"]' in selector for selector in selectors), selectors
