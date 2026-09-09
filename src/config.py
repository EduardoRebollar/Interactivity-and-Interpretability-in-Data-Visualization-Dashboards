"""Study configuration: the condition toggle and the locked data scope.

Visual constants (palette, fonts, chart sizing) are deliberately NOT defined here yet. They are
gated on `docs/visual-spec.md`, which does not exist, and every colour needs a WCAG 2.1 AA contrast
check plus a matching change in the Tableau build. Add them here once that spec is written.
"""

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
# NOTE: CLAUDE.md specifies "~10" countries — these 8 are the named ones. The remaining 1-2 are an
# open scope decision and must be chosen deliberately, not defaulted in.
COUNTRIES: list[str] = [
    "United States",
    "United Kingdom",
    "Brazil",
    "India",
    "Nigeria",
    "Ethiopia",
    "Indonesia",
    "Ukraine",
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
