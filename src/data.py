"""Load and clean WHO/UNICEF coverage data into the canonical long format.

Canonical schema (one row per entity x year x vaccine):
    country       str    OWID entity name
    iso_code      str    ISO-3; OWID aggregates use OWID_* codes (e.g. OWID_WRL)
    year          int
    vaccine       str    "DTP3" | "MCV1" | "Polio3" | "HepB3"
    coverage_pct  float  0-100, may be NaN

Missing data is preserved, never filled. The frame is reindexed to the complete
entity x year x vaccine grid so that an unreported value is always an explicit NaN row rather than
an absent one — gaps are part of what participants are asked to interpret, so they must be visible
and consistent across entities.
"""

from __future__ import annotations

import itertools

import pandas as pd

from src import config

SCHEMA: dict[str, str] = {
    "country": "str",
    "iso_code": "str",
    "year": "int64",
    "vaccine": "str",
    "coverage_pct": "float64",
}


class DataError(RuntimeError):
    """Raised when source data is absent or does not match the expected schema."""


def build() -> pd.DataFrame:
    """Read the raw OWID CSV and reshape it to the canonical long format."""
    if not config.RAW_CSV.exists():
        raise DataError(
            f"Raw data not found at {config.RAW_CSV}. Run: uv run python scripts/download_data.py"
        )

    raw = pd.read_csv(config.RAW_CSV)

    expected = {"entity", "code", "year", *config.VACCINES.values()}
    missing = expected - set(raw.columns)
    if missing:
        raise DataError(f"Raw CSV is missing expected columns: {sorted(missing)}")

    scoped = raw[
        raw["entity"].isin(config.ENTITIES) & raw["year"].between(config.YEAR_MIN, config.YEAR_MAX)
    ]

    found = set(scoped["entity"])
    if absent := [e for e in config.ENTITIES if e not in found]:
        raise DataError(f"Entities in scope but absent from source: {absent}")

    # One column per vaccine -> one row per vaccine.
    long = scoped.melt(
        id_vars=["entity", "code", "year"],
        value_vars=list(config.VACCINES.values()),
        var_name="owid_column",
        value_name="coverage_pct",
    )
    column_to_code = {v: k for k, v in config.VACCINES.items()}
    long["vaccine"] = long["owid_column"].map(column_to_code)
    long = long.rename(columns={"entity": "country", "code": "iso_code"})
    long = long.drop(columns=["owid_column"])

    frame = _complete_grid(long)
    _validate(frame)
    return frame


def _complete_grid(long: pd.DataFrame) -> pd.DataFrame:
    """Reindex to every entity x year x vaccine combination, leaving absent values as NaN."""
    # iso_code is a property of the entity, so recover it after reindexing rather than
    # letting it go NaN on rows the source never reported.
    iso_by_country = (
        long.dropna(subset=["iso_code"]).drop_duplicates("country").set_index("country")["iso_code"]
    )

    index = pd.MultiIndex.from_tuples(
        list(
            itertools.product(
                config.ENTITIES,
                range(config.YEAR_MIN, config.YEAR_MAX + 1),
                config.VACCINES.keys(),
            )
        ),
        names=["country", "year", "vaccine"],
    )

    frame = (
        long.set_index(["country", "year", "vaccine"])["coverage_pct"].reindex(index).reset_index()
    )
    frame["iso_code"] = frame["country"].map(iso_by_country)
    return frame[list(SCHEMA)].sort_values(["country", "vaccine", "year"], ignore_index=True)


def _validate(frame: pd.DataFrame) -> None:
    """Assert the canonical schema and value ranges. Raises DataError on violation."""
    if list(frame.columns) != list(SCHEMA):
        raise DataError(f"Column mismatch: {list(frame.columns)} != {list(SCHEMA)}")

    if frame["year"].dtype.kind != "i":
        raise DataError(f"year must be integer, got {frame['year'].dtype}")
    if frame["coverage_pct"].dtype.kind != "f":
        raise DataError(f"coverage_pct must be float, got {frame['coverage_pct'].dtype}")

    expected_rows = (
        len(config.ENTITIES) * (config.YEAR_MAX - config.YEAR_MIN + 1) * len(config.VACCINES)
    )
    if len(frame) != expected_rows:
        raise DataError(f"Expected {expected_rows} rows, got {len(frame)}")

    if frame.duplicated(["country", "year", "vaccine"]).any():
        raise DataError("Duplicate country/year/vaccine rows")

    observed = frame["coverage_pct"].dropna()
    if not observed.between(0, 100).all():
        bad = observed[~observed.between(0, 100)]
        raise DataError(f"coverage_pct outside 0-100: {bad.unique()[:5]}")

    if unknown := set(frame["vaccine"]) - set(config.VACCINES):
        raise DataError(f"Unexpected vaccine codes: {unknown}")


def load(refresh: bool = False) -> pd.DataFrame:
    """Return the cleaned frame, using the parquet cache when available.

    Set `refresh=True` to rebuild from the raw CSV and overwrite the cache.
    """
    if config.PROCESSED_PARQUET.exists() and not refresh:
        frame = pd.read_parquet(config.PROCESSED_PARQUET, engine="pyarrow")
        _validate(frame)
        return frame

    frame = build()
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(config.PROCESSED_PARQUET, engine="pyarrow", index=False)
    return frame


if __name__ == "__main__":
    df = load(refresh=True)
    total = len(df)
    present = int(df["coverage_pct"].notna().sum())
    print(f"Rows: {total}  observed: {present}  missing: {total - present}")
    print(df.head())
