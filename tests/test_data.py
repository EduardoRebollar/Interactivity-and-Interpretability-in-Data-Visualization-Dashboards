"""Tests for the data layer.

Schema tests run on synthetic frames so they need no network. Tests over the real export are
skipped when `data/raw/` has not been populated yet.
"""

from __future__ import annotations

import itertools

import pandas as pd
import pytest

from src import config, data


def _valid_frame(value: float = 90.0) -> pd.DataFrame:
    """A complete, schema-valid frame covering the full locked scope.

    Sized to the real scope so that value-level checks in `_validate` are actually reached rather
    than short-circuited by the row-count guard.
    """
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
    frame = index.to_frame(index=False)
    frame["iso_code"] = "XXX"
    frame["coverage_pct"] = value
    return frame[list(data.SCHEMA)]


# --- Schema validation ------------------------------------------------------------------------


def test_validate_accepts_a_valid_frame():
    data._validate(_valid_frame())


def test_validate_accepts_nan_coverage():
    """NaN is a legitimate value, not an out-of-range one."""
    frame = _valid_frame()
    frame.loc[0, "coverage_pct"] = float("nan")
    data._validate(frame)


def test_validate_rejects_wrong_columns():
    frame = _valid_frame().rename(columns={"coverage_pct": "coverage"})
    with pytest.raises(data.DataError, match="Column mismatch"):
        data._validate(frame)


def test_validate_rejects_non_integer_year():
    frame = _valid_frame()
    frame["year"] = frame["year"].astype(float)
    with pytest.raises(data.DataError, match="year must be integer"):
        data._validate(frame)


def test_validate_rejects_out_of_range_coverage():
    frame = _valid_frame()
    frame.loc[0, "coverage_pct"] = 140.0
    with pytest.raises(data.DataError, match="outside 0-100"):
        data._validate(frame)


def test_validate_rejects_incomplete_grid():
    frame = _valid_frame().drop(index=0)
    with pytest.raises(data.DataError, match="Expected"):
        data._validate(frame)


def test_validate_rejects_duplicate_rows():
    frame = _valid_frame()
    frame.loc[0, ["country", "year", "vaccine"]] = frame.loc[1, ["country", "year", "vaccine"]]
    with pytest.raises(data.DataError, match="Duplicate"):
        data._validate(frame)


# --- Real export ------------------------------------------------------------------------------

requires_raw = pytest.mark.skipif(
    not config.RAW_CSV.exists(),
    reason="raw export absent; run scripts/download_data.py",
)


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    return data.build()


@pytest.fixture(scope="module")
def raw_scoped() -> pd.DataFrame:
    raw = pd.read_csv(config.RAW_CSV)
    return raw[
        raw["entity"].isin(config.ENTITIES) & raw["year"].between(config.YEAR_MIN, config.YEAR_MAX)
    ]


@requires_raw
def test_schema_and_dtypes(frame):
    assert list(frame.columns) == list(data.SCHEMA)
    assert frame["year"].dtype.kind == "i"
    assert frame["coverage_pct"].dtype.kind == "f"


@requires_raw
def test_grid_is_complete(frame):
    """Every entity x year x vaccine cell exists, so gaps are explicit NaN, not absent rows."""
    years = config.YEAR_MAX - config.YEAR_MIN + 1
    assert len(frame) == len(config.ENTITIES) * years * len(config.VACCINES)
    assert not frame.duplicated(["country", "year", "vaccine"]).any()


@requires_raw
def test_scope_is_locked(frame):
    assert set(frame["country"]) == set(config.ENTITIES)
    assert set(frame["vaccine"]) == set(config.VACCINES)
    assert frame["year"].min() == config.YEAR_MIN
    assert frame["year"].max() == config.YEAR_MAX


@requires_raw
def test_observed_value_count_matches_source(frame, raw_scoped):
    """No value invented and none dropped: cleaning must not fill or discard observations."""
    for code, column in config.VACCINES.items():
        expected = int(raw_scoped[column].notna().sum())
        actual = int(frame.loc[frame["vaccine"] == code, "coverage_pct"].notna().sum())
        assert actual == expected, f"{code}: {actual} observations vs {expected} in source"


@requires_raw
def test_observed_values_match_source(frame, raw_scoped):
    """Every non-null cleaned value equals the source value for that entity/year/vaccine."""
    for code, column in config.VACCINES.items():
        source = raw_scoped.set_index(["entity", "year"])[column].dropna()
        cleaned = (
            frame[frame["vaccine"] == code]
            .dropna(subset=["coverage_pct"])
            .set_index(["country", "year"])["coverage_pct"]
        )
        aligned = cleaned.reindex(source.index)
        pd.testing.assert_series_equal(aligned, source, check_names=False, check_index_type=False)


@requires_raw
def test_missing_data_is_preserved(frame):
    """Gaps are meaningful to participants; cleaning must not fill or drop them."""
    assert frame["coverage_pct"].isna().any(), "expected genuine gaps in the source"
    # The UK reports HepB3 only from the year universal infant vaccination began.
    uk_hepb = frame[(frame["country"] == "United Kingdom") & (frame["vaccine"] == "HepB3")]
    assert uk_hepb["coverage_pct"].isna().sum() > 0


@requires_raw
def test_iso_code_present_for_every_entity(frame):
    """Reindexing must not leave iso_code NaN on rows the source never reported."""
    assert frame["iso_code"].notna().all()
    assert frame.groupby("country")["iso_code"].nunique().eq(1).all()


@requires_raw
def test_parquet_round_trip_preserves_gaps(frame, tmp_path):
    path = tmp_path / "coverage.parquet"
    frame.to_parquet(path, engine="pyarrow", index=False)
    back = pd.read_parquet(path, engine="pyarrow")
    assert back["coverage_pct"].isna().sum() == frame["coverage_pct"].isna().sum()
    assert back["year"].dtype.kind == "i"
    pd.testing.assert_frame_equal(frame, back)
