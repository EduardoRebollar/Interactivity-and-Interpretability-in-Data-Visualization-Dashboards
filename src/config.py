"""Study configuration: the condition toggle, the locked data scope, and the locked visuals.

`docs/visual-spec.md` is the source of truth for everything in the VISUAL section below; change the
spec first, then these values. Every color here has a measured WCAG 2.1 contrast ratio recorded
alongside it, and `tests/test_palette.py` fails the build if any of them drifts below its floor.
"""

import os
from pathlib import Path

# --- Condition toggle -------------------------------------------------------------------------
# The ONLY difference between the two study conditions. Interactive-only features: filtering,
# sorting, line isolation, year-over-year directional change indicators.
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
YEAR_MIN = 2000
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

# Derived from Okabe-Ito, which is built for color-vision deficiency. Four are unmodified, keeping
# Okabe-Ito's validated separability intact; only orange is darkened, and to a level chosen for
# luminance spread rather than to the bare floor.
#
# Three swatches were dropped, each for a measured reason:
#   yellow    #F0E442  1.32:1 — the passing form (#9F972C) reads as olive and collides with green
#   sky blue  #56B4E9  2.31:1 — any passing form lands at L~0.291, indistinguishable from purple
#   black     #000000         — reserved for the World reference series
#
# Colors are separated in LUMINANCE as well as hue (min gap 0.025). Darkening several colors to the
# same contrast target makes them luminance-identical, which defeats greyscale printing and severe
# color-vision deficiency; ordering below is light-to-dark by luminance.
SERIES_COLORS: list[str] = [
    "#0072B2",  # blue            5.19:1   L 0.153
    "#9C6C00",  # orange          4.61:1   L 0.178  (darkened from #E69F00, 2.25:1)
    "#D55E00",  # vermillion      3.87:1   L 0.222
    "#009E73",  # bluish green    3.42:1   L 0.257
    "#CC79A7",  # reddish purple  3.06:1   L 0.293
]

# The aggregate reference series ("World") is black and dashed, so it reads as a baseline rather
# than as one more country competing for attention.
REFERENCE_COLOR = "#000000"  # 21.00:1
REFERENCE_DASH = "dash"

# Hard ceiling on simultaneous series, excluding the World reference. Five is not a style choice: it
# is the largest set that is simultaneously >=3:1 on white, color-blind separable, and separated in
# luminance. A sixth color collides with an existing one on at least one of those three axes. Beyond
# this, reading the legend becomes the task instead of reading the data.
MAX_SERIES = len(SERIES_COLORS)
MIN_LUMINANCE_GAP = 0.02

TEXT_PRIMARY = "#1A1A1A"  # 17.40:1
TEXT_MUTED = "#595959"  # 7.00:1
AXIS_COLOR = "#404040"  # 10.37:1

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
# by the tick labels at 10.37:1, so no information depends on the gridline alone.
GRIDLINE_COLOR = "#B3B3B3"  # 2.10:1
GRIDLINE_EXEMPT = True

FONT_FAMILY = "Helvetica, Arial, sans-serif"
FONT_SIZE_BASE = 14
FONT_SIZE_TITLE = 18
FONT_SIZE_AXIS = 13

# Y axis is pinned; never auto-scale. A y range that changes between tasks or conditions silently
# changes how steep a trend looks, which would confound interpretation accuracy.
Y_RANGE = (0, 100)
LINE_WIDTH = 2.5
MARKER_SIZE = 5
CHART_HEIGHT = 520
# End labels closer than this, in percentage points, are spread apart (visual-spec.md section 6).
# The plot area is CHART_HEIGHT minus 120 px of margins over Y_RANGE: 4 px a point, so 4.5 points
# is 18 px, about what a FONT_SIZE_AXIS label needs.
LABEL_MIN_GAP = 4.5
