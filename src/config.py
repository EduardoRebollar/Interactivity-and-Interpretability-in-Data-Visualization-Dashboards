"""Study configuration: the condition toggle, the locked data scope, and the locked visuals.

`docs/visual-spec.md` is the source of truth for everything in the VISUAL section below; change the
spec first, then these values. Every color here has a measured WCAG 2.1 contrast ratio recorded
alongside it, and `tests/test_palette.py` fails the build if any of them drifts below its floor.
"""

import os
from pathlib import Path

# --- Condition toggle -------------------------------------------------------------------------
# The ONLY difference between the two study conditions. Interactive-only features: filtering,
# sorting, line isolation, year-over-year directional change indicators, and hover everywhere.
INTERACTIVE: bool = False

# --- Paths ------------------------------------------------------------------------------------
# Resolved relative to this file so the project runs from any working directory or clone location.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
STUDY_LOGS_DIR = DATA_DIR / "study_logs"
# Signed consent records from local runs (no database). Deliberately NOT under study_logs/: IRB form
# items 15 and 17 require signed consent to be kept apart from the study data. Gitignored.
CONSENT_DIR = DATA_DIR / "consent"


def spool_dir() -> Path:
    """Where events go when the database refuses them, besides the browser store.

    A function, not a constant, so the environment is read at call time: `STUDY_SPOOL_DIR`
    overrides it (tests point it at a temporary directory), and on Vercel -- where everything
    outside /tmp is read-only -- it is /tmp. /tmp there is per-instance and not retrievable, which
    is why the browser store, not this directory, is the copy that counts in production.
    """
    override = os.environ.get("STUDY_SPOOL_DIR")
    if override:
        return Path(override)
    if os.environ.get("VERCEL"):
        return Path("/tmp/study_spool")
    return STUDY_LOGS_DIR / "spool"


# --- Source -----------------------------------------------------------------------------------
# Our World in Data grapher export of the WHO/UNICEF (WUENIC) coverage estimates.
OWID_SLUG = "global-vaccination-coverage"
OWID_CSV_URL = (
    f"https://ourworldindata.org/grapher/{OWID_SLUG}.csv?csvType=full&useColumnShortNames=true"
)
RAW_CSV = RAW_DIR / f"{OWID_SLUG}.csv"
PROCESSED_PARQUET = PROCESSED_DIR / "coverage.parquet"

# --- Locked scope -----------------------------------------------------------------------------
# From 1985 since 2026-10-12 (2000 until then), so the line charts, which draw every year, give the
# Years slider years to set aside. Every line item still asks about 2000 onward
# (`tasks.ASKED_FROM`); no other chart shows a year before 2000. docs/study-design.md section 4.
YEAR_MIN = 1985
YEAR_MAX = 2024

# Short code -> OWID column name in the grapher export.
VACCINES: dict[str, str] = {
    "DTP3": "coverage__antigen_dtpcv3",
    "MCV1": "coverage__antigen_mcv1",
    "Polio3": "coverage__antigen_pol3",
    "HepB3": "coverage__antigen_hepb3",
}

# Names are exact OWID entity strings; verified present in the grapher export.
COUNTRIES: list[str] = [
    "United States",
    "United Kingdom",
    "Brazil",
    "India",
    "Nigeria",
    "Ethiopia",
    "Indonesia",
    "Ukraine",
    # Added 2026-09-09 to give tasks genuine contrast: Pakistan is one of the last
    # polio-endemic countries, China the largest high-coverage system.
    "Pakistan",
    "China",
    # Added 2026-09-23 for the redesigned task bank (docs/study-design.md section 4): the bar,
    # scatter, heatmap and map items need countries the original ten do not provide. Every one is
    # used by at least one item; none is here for completeness.
    "Afghanistan",
    "Bangladesh",
    "Burkina Faso",
    "Cambodia",
    "Cameroon",
    "Central African Republic",
    "Chad",
    "Colombia",
    "Democratic Republic of Congo",
    "Egypt",
    "Kenya",
    "Madagascar",
    "Mali",
    "Mozambique",
    "Myanmar",
    "Nepal",
    "Niger",
    "Somalia",
    "Tanzania",
    "Uganda",
    "Vietnam",
    "Zambia",
    # Added 2026-10-11 for T3's sixteen dots, and used by nothing else (docs/study-design.md section
    # 4): each scatter gained ten dots, and Asia in the scope above had only two that fit the rule.
    "Benin",
    "Libya",
    "Sudan",
    "Iraq",
    "Jordan",
    "Kyrgyzstan",
    "Laos",
    "Lebanon",
    "Oman",
    "Philippines",
    "Syria",
    "Thailand",
    "Yemen",
    # Added 2026-10-11 for B-T5's map, and used by nothing else (docs/study-design.md section 4):
    # Form B colours eighteen countries, as Form A does, mostly different ones, and only Chad and
    # Somalia of the countries above fall clear below 50% in 2007. Each is at least 13 points
    # above the line; Togo, Sierra Leone and Liberia, the smallest that also pass, were left out.
    "Algeria",
    "Botswana",
    "Congo",
    "Cote d'Ivoire",
    "Eritrea",
    "Gabon",
    "Ghana",
    "Guinea",
    "Malawi",
    "Mauritania",
    "Morocco",
    "Namibia",
    "Senegal",
    "South Africa",
    "Tunisia",
    "Zimbabwe",
]

# Aggregate reference series.
AGGREGATES: list[str] = [
    "World",
    "Africa",
    "Asia",
    "Europe",
    "North America",
    "South America",
    "Oceania",
]

ENTITIES: list[str] = COUNTRIES + AGGREGATES

# --- Visual (locked; see docs/visual-spec.md) --------------------------------------------------

BACKGROUND = "#FFFFFF"

# Eight colours, extended 2026-09-23 from five (docs/visual-spec.md section 4). The first four are
# Okabe-Ito, unmodified. The other four were chosen by search: every candidate >=3:1 on white and
# >=0.02 from every other colour in luminance, picking the four that keep every pair furthest apart
# (CIEDE2000) under normal vision and simulated deuteranopia and protanopia (`src/contrast.py`).
#
# The five-colour palette this replaces had a defect the extension exposed: Okabe-Ito orange,
# darkened to #9C6C00 to pass contrast, sat 1.1 dE from vermillion under simulated protanopia --
# the same colour. It was dropped. The weakest pair now is 12.2 dE (blue and reddish purple, both
# unmodified Okabe-Ito, under protanopia); `tests/test_palette.py` holds that floor.
#
# Every pair clears the floor, so any subset does: since 2026-10-11 colour goes by country
# (COUNTRY_COLORS below), not by position, and a chart uses whichever colours its countries hold.
SERIES_COLORS: list[str] = [
    "#0072B2",  # blue            5.19:1   L 0.152   Okabe-Ito
    "#D55E00",  # vermillion      3.87:1   L 0.222   Okabe-Ito
    "#009E73",  # bluish green    3.42:1   L 0.257   Okabe-Ito
    "#CC79A7",  # reddish purple  3.06:1   L 0.293   Okabe-Ito
    "#960600",  # dark red        9.04:1   L 0.066
    "#062AA8",  # royal blue     11.03:1   L 0.045
    "#246648",  # forest green    6.84:1   L 0.103
    "#845472",  # mauve           6.01:1   L 0.125
]

# Colour by country (visual-spec.md section 4, the chart handoff, 2026-10-11). Each of Form A's
# T1 countries owns one colour and keeps it on every line chart; any other country on a line chart
# takes the first colour its chart does not already use (`figures.series_colors`). A hidden line
# keeps its colour, and so does every other line. Since 2026-10-12 Gabon stands on A-T1 where
# Nigeria stood, and takes Nigeria's colour as the one A-T1 leaves unused; Nigeria keeps it on B-T1
# and A-T6, so no other chart changes.
COUNTRY_COLORS: dict[str, str] = {
    "Brazil": SERIES_COLORS[0],
    "China": SERIES_COLORS[1],
    "Ethiopia": SERIES_COLORS[2],
    "India": SERIES_COLORS[3],
    "Indonesia": SERIES_COLORS[4],
    "Nigeria": SERIES_COLORS[5],
    "Pakistan": SERIES_COLORS[6],
    "Ukraine": SERIES_COLORS[7],
}

# The aggregate reference series ("World") is black and dashed, so it reads as a baseline rather
# than as one more country competing for attention.
REFERENCE_COLOR = "#000000"  # 21.00:1
REFERENCE_DASH = "dash"

# Hard ceiling on lines, excluding the World reference. It is the size of the palette: the largest
# set found that is >=3:1 on white, separated in luminance, and at least MIN_CVD_DISTANCE apart
# under simulated colour-vision deficiency. The scatter has its own ceiling, MAX_SCATTER_DOTS.
MAX_SERIES = len(SERIES_COLORS)
MIN_LUMINANCE_GAP = 0.02
# The weakest pair in SERIES_COLORS, in CIEDE2000, under normal vision, deuteranopia and
# protanopia. A floor, not a target: the test fails if an edit lowers it.
MIN_CVD_DISTANCE = 12.0

# The chart's text and structure (visual-spec.md section 4, the chart handoff, 2026-10-11): the page
# chrome's ink and muted tokens, with a warm axis and gridline to match.
TEXT_PRIMARY = "#241C18"  # 16.74:1
TEXT_MUTED = "#5F544D"  # 7.34:1
AXIS_COLOR = "#4A3F38"  # 10.20:1

# Validation-error text. UI chrome, NOT a series color: it never appears on a chart, so it does not
# count against MAX_SERIES and does not need luminance separation from the palette.
#
# Derived from the vermillion series color by `contrast.darken_to_ratio`, which scales all three
# channels equally and so holds the hue. #D55E00 itself is 3.87:1 — fine for a 2.5px line at the 3:1
# graphic floor, but below the 4.5:1 floor that applies to text.
ERROR_COLOR = "#C35600"  # 4.51:1

# DELIBERATE EXEMPTION from the 3:1 floor. No grey reaches 3:1 against white while still reading as
# a gridline rather than as data. This is darker than a typical default because the static condition
# has no hover, so participants estimate values against the grid. The values themselves are carried
# by the tick labels at 10.20:1, so no information depends on the gridline alone.
GRIDLINE_COLOR = "#BBAEA4"  # 2.16:1
GRIDLINE_EXEMPT = True

FONT_FAMILY = "Helvetica, Arial, sans-serif"
FONT_SIZE_BASE = 14
FONT_SIZE_TITLE = 18
FONT_SIZE_AXIS = 13
FONT_SIZE_SOURCE = 12
# Axis numbers and names are drawn at weight 500 (visual-spec.md section 5). Helvetica and Arial
# have no 500 on most computers, so the browser would draw them regular; the handoff draws the
# weight as a 0.45 px stroke in the text's colour. A text shadow a quarter of that each way is the
# same, and it is part of the figure, so both conditions carry it. `figures.medium` builds it.
MEDIUM_STROKE = 0.45

# The card (visual-spec.md section 5): title band 0-30 px, the chart, the source line at 502 px.
TITLE_X = 16
TITLE_BASELINE = 21
SOURCE_BASELINE = 514
SOURCE_TEXT = (
    "Source: WHO/UNICEF coverage estimates (WUENIC), via Our World in Data. These are estimates; "
    "how reliably coverage is measured varies by country."
)

# Y axis is pinned; never auto-scale. A y range that changes between tasks or conditions silently
# changes how steep a trend looks, which would confound interpretation accuracy.
Y_RANGE = (0, 100)
LINE_WIDTH = 2.5
# Plotly sizes a marker by its diameter: a dot of radius 2.6 px at every year, and at the line's
# last point a 4.6 px dot with a 2 px white ring (visual-spec.md section 1).
MARKER_SIZE = 5.2
END_DOT_SIZE = 9.2
END_DOT_RING = 2
CHART_HEIGHT = 520
# Fixed, in the figure's own layout (visual-spec.md section 5, 2026-09-25).
CHART_WIDTH = 1050
# The line chart's x axis runs 8 px past the first and last years, so the first and last dots, the
# ringed end dot included (5.6 px to the ring's outer edge), are not cut by the plot's edge
# (visual-spec.md section 1). Over 1985-2024 that is 0.4 year; over 2000-2024, until 2026-10-12,
# it was a quarter year, which drawn from 1985 is 5 px and would cut the ring.
LINE_X_PAD = 0.4
# Name tags (visual-spec.md section 6): centres at least 23 px apart, between 10 px above the plot's
# top and 4 px above its bottom; 20 px tall pills at x 860 in the card.
TAG_GAP = 23
TAG_X = 860
TAG_HEIGHT = 20
TAG_EDGE_COLOR = "#E4D8CC"  # 1.40:1, decorative: the tag's name carries it

# --- Chart types beyond the line chart (docs/visual-spec.md section 1) --------------------------

# The scatter (visual-spec.md sections 1 and 4, the chart handoff, 2026-10-11). Every dot is named
# beside it and coloured by its change from the first year to the second, so it needs no legend and
# no shape of its own; at most sixteen dots, T3's number.
MAX_SCATTER_DOTS = 16
SCATTER_MARKER_SIZE = 9
# The change scale: seven steps, three blues for a rise, grey within 5 points, three reds for a
# fall. (upper bound of the step, colour), from the largest rise down; a change exactly on a
# boundary takes the step nearer zero. Every step clears 3:1 on white. Exempt from the 12 dE
# floor, like the sequential scale: the change is also the dot's height above the diagonal, and the
# name beside the dot, not its colour, says which country it is.
CHANGE_STEPS: list[tuple[float, str]] = [
    (40, "#0F3F78"),  # more than +40     10.49:1
    (20, "#1C5FAF"),  # +20 to +40         6.35:1
    (5, "#3A80CF"),  # +5 to +20           4.06:1
    (-5, "#8E8781"),  # -5 to +5, no change 3.54:1
    (-20, "#D9473F"),  # -5 to -20          4.27:1
    (-40, "#A3262C"),  # -20 to -40         7.31:1
    (None, "#6E1D20"),  # less than -40    11.29:1
]
# Where a dot's name goes when the right would collide, as the handoff places them per form.
SCATTER_LABEL_SIDES: dict[str, str] = {
    "Niger": "left",
    "Ethiopia": "left",
    "Nigeria": "left",
    "Central African Republic": "left",
    "Madagascar": "left",
    "Kenya": "left",
    "Tanzania": "left",
    "Nepal": "left",
    "Iraq": "left",
    "India": "left",
    "Philippines": "left",
    "Bangladesh": "above",
}

# A colour per bar, by country (visual-spec.md section 4, the chart handoff, 2026-10-11). A country
# in COUNTRY_COLORS keeps its line colour; these are the T2 countries without one. Chosen by search
# (C* 30-70, so no bar reads as grey land or as neon; 3:1 to 10:1 on white), each as near the
# handoff's colour as the floor allows where the handoff gave one: every pair of bars on A-T2 and
# on B-T2 is at least MIN_CVD_DISTANCE apart under normal vision, deuteranopia and protanopia, the
# floor the series colours meet. The handoff's own Afghanistan, #B07A00, was 1.1 dE from China's
# vermillion under protanopia. The name under each bar, not its colour, says which country it is.
#
# When T2 moved to MCV1 (2026-10-11), Guinea's bar replaced Brazil's on A-T2 and Algeria's
# Cambodia's on B-T2. Each takes the colour of the bar it replaced, so both charts keep the colour
# sets measured above. Guinea's line on B-T6 (since 2026-10-12) takes a line colour as any country
# outside COUNTRY_COLORS does, and Brazil is not on that chart.
BAR_COLORS: dict[str, str] = {
    "Afghanistan": "#705000",  # 7.40:1   handoff #B07A00
    "Guinea": "#0072B2",  # 5.19:1   Brazil's series colour
    "Kenya": "#0098E8",  # 3.15:1   handoff #2C8DBF
    "Mali": "#108078",  # 4.79:1   handoff #7A5C00
    "Vietnam": "#683860",  # 9.04:1   handoff #5E5E9E
    "Algeria": "#A080F8",  # 3.03:1   Cambodia's until 2026-10-11
    "Cameroon": "#C06000",  # 4.27:1
    "Colombia": "#703040",  # 9.61:1
    "Egypt": "#1070A8",  # 5.38:1
    "Mozambique": "#30A0A8",  # 3.13:1
    "United States": "#A84848",  # 5.70:1
}

# The heatmap and the map encode value as colour, on this sequential scale (visual-spec.md section
# 4, the chart handoff, 2026-10-11; it replaces cividis): ten stops built in OKLCH, lightness rising
# at every stop in normal vision and under deuteranopia, protanopia and tritanopia, no yellow. Dark
# is LOW coverage, as the prompts say. Neither chart blends it: each draws flat BANDS (below).
#
# DELIBERATE EXEMPTION from the 3:1 floor, like the gridline: the light end (#CCE9FF) is 1.26:1 on
# white. No sequential scale can put every step at 3:1 on white and still span enough lightness to
# read differences in. No cell or country is found by its colour alone: heatmap cells sit on a grid
# labelled by country and year, and map countries are named on the map and bounded by white
# borders. See visual-spec.md section 4.
SEQUENTIAL_SCALE: list[tuple[float, str]] = [
    (0.0, "#0A2347"),
    (0.111, "#0A3569"),
    (0.222, "#08498A"),
    (0.333, "#095EA9"),
    (0.444, "#1A75C3"),
    (0.556, "#348DD8"),
    (0.667, "#54A5E8"),
    (0.778, "#78BDF4"),
    (0.889, "#9ED4FD"),
    (1.0, "#CCE9FF"),
]
SEQUENTIAL_EXEMPT = True

# The heatmap's nine bands, sampled evenly along the scale: (lower bound, colour). A value takes the
# band whose lower bound it reaches. Two values in one band look identical; T4's key sits a band
# clear of every other row's lowest cell (docs/study-design.md section 4).
HEATMAP_BANDS: list[tuple[int, str]] = [
    (0, "#0A2347"),
    (20, "#0A386D"),
    (30, "#084E92"),
    (40, "#0F67B3"),
    (50, "#2781CE"),
    (60, "#489CE2"),
    (70, "#6FB7F1"),
    (80, "#99D1FC"),
    (90, "#CCE9FF"),
]
# The map's seven: stops 1, 2, 3, 4, 6, 8 and 9 of the scale. 50 is a boundary, so T5's count is a
# count of the two darkest.
MAP_BANDS: list[tuple[int, str]] = [
    (0, "#0A3569"),
    (40, "#08498A"),
    (50, "#095EA9"),
    (60, "#1A75C3"),
    (70, "#54A5E8"),
    (80, "#9ED4FD"),
    (90, "#CCE9FF"),
]
# An empty heatmap cell, and plain land on the map: a surface, never a mark (1.22:1, exempt).
NO_DATA_COLOR = "#EEE8E2"
# Colour-key ticks, every 10 points so 50% is marked.
COLOR_KEY_DTICK = 10

# The map (visual-spec.md sections 1 and 4, the chart handoff's africa map.png). Countries the
# question is not about are plain land, so the ones it is about are the coloured ones. Borders are
# white: the question counts DARK countries, and two adjacent dark countries (CAR and Chad) need a
# border that contrasts with dark fills -- white is 9.01:1 against the 40-50 band. The coast is a
# 2 px outline in the gridline colour.
MAP_LAND_COLOR = NO_DATA_COLOR
MAP_BORDER_COLOR = "#FFFFFF"
MAP_COAST_COLOR = GRIDLINE_COLOR
# The whole continent, Madagascar included, on Plotly's Africa scope (Mercator). The latitudes set
# the scale; the longitudes run wider, to give the names beside the coast their room.
MAP_LAT_RANGE = (-36, 38)
MAP_LON_RANGE = (-30, 64)
# Each coloured country is named on the map (visual-spec.md section 1). A name sits inside its
# country unless placed here: (longitude, latitude) of the label, and the side of that point the
# text runs to ("left", "right", "above", "below"), with a leader from the country's centre.
# A pair of numbers alone nudges an inside label by that many degrees. Set per form, by eye.
MAP_LABEL_NUDGE: dict[str, tuple[float, float]] = {
    "Chad": (0, 2.0),
    "Mali": (1.5, -1.5),
    "Niger": (0.8, -0.8),
    "Democratic Republic of Congo": (-1.2, 0),
    "Kenya": (0.2, -0.8),
    "Tanzania": (0, -0.8),
    "Zambia": (-1.7, -0.8),
    "Algeria": (0, -1.0),
    "Mauritania": (0.5, -1.5),
    "Namibia": (-1.5, 0.5),
    "Botswana": (1.0, -0.8),
}
MAP_LABEL_OUTSIDE: dict[str, tuple[float, float, str]] = {
    "Cameroon": (6.5, -1.0, "left"),
    "Benin": (2.3, 3.6, "below"),
    "Burkina Faso": (-7.5, 5.5, "left"),
    "Uganda": (31.3, 6.5, "above"),
    "Mozambique": (40.5, -29.0, "right"),
    "Madagascar": (50.5, -19.4, "right"),
    "Somalia": (50.5, 4.0, "right"),
    "Eritrea": (43.5, 18.5, "right"),
    "Tunisia": (14.5, 36.0, "right"),
    "Morocco": (-12.5, 34.5, "left"),
    "Senegal": (-19.0, 16.5, "left"),
    "Guinea": (-16.0, 8.5, "left"),
    "Cote d'Ivoire": (-9.0, 2.0, "left"),
    "Ghana": (-1.0, 2.0, "below"),
    "Gabon": (6.0, -4.0, "left"),
    "Congo": (9.0, -7.5, "left"),
    "Malawi": (40.5, -11.5, "right"),
    "Zimbabwe": (36.5, -22.5, "right"),
}
MAP_SHORT_NAMES = {"Central African Republic": "CAR", "Democratic Republic of Congo": "DR Congo"}
# A bar, heatmap row or map country the controls hide fades rather than disappears
# (visual-spec.md sections 7.3 and 7.4), so it keeps its place and nothing else moves.
FADED_OPACITY = 0.15
