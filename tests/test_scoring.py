"""Tests for the derived answer key, and for keeping it out of production.

The key is the study's ground truth. These guard the two ways it goes wrong silently:

- **It is wrong.** `docs/study-design.md` said T1's answer was 2 for days; the data says 1. Every
  key here is derived from the deploy CSV and must agree with the transcribed table, and each rule
  refuses an item that has stopped being well-posed (a tie, a double crossing, a zero in a gap).
- **It ships.** `src/` is uploaded to Vercel and much of it reaches the browser. The key lives in
  `analysis/`, which must stay excluded from the bundle and unimported by any runtime module.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from analysis import keys
from src import runtime_data, tasks
from src.flow import Task
from src.runtime_data import Row

ROOT = Path(__file__).resolve().parent.parent

needs_data = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)


def _rows(series: dict[tuple[str, str], dict[int, float | None]]) -> tuple[Row, ...]:
    """Synthetic data: every listed entity x vaccine over 2000-2024, None where a year is absent."""
    return tuple(
        Row(entity, "XXX", year, vaccine, values.get(year))
        for (entity, vaccine), values in series.items()
        for year in range(2000, 2025)
    )


def _task(task_id: str, kind: str, entities: tuple[str, ...], options, vaccine="DTP3") -> Task:
    return Task(task_id, "Z", kind, "prompt", vaccine, entities, tuple(options))


# --- The real keys ------------------------------------------------------------------------------


@needs_data
def test_derived_keys_match_the_expected_table():
    """The T1 regression test: a wrong key in study-design.md section 4 fails here."""
    assert keys.check() == []


@needs_data
def test_a_wrong_transcription_is_caught():
    """Exactly the error that happened: section 4 said T1 was 2."""
    wrong = {**keys.EXPECTED, ("A", "T1"): "2"}
    problems = keys.check(wrong)
    assert len(problems) == 1
    assert "A-T1" in problems[0] and "'1'" in problems[0] and "'2'" in problems[0]


def test_expected_covers_every_scored_item():
    items = {(t.form, t.task_id) for form in tasks.FORMS for t in tasks.for_form(form)}
    assert set(keys.EXPECTED) == items
    assert set(keys.PARAMS) == items


@needs_data
def test_every_key_is_one_of_the_task_options():
    for (form, task_id), key in keys.key_table().items():
        task = next(t for t in tasks.for_form(form) if t.task_id == task_id)
        assert key.correct in task.options


@needs_data
def test_trend_margins_match_study_design():
    """Section 4's form matching rests on these margins; a data refresh must not move them."""
    table = keys.key_table()
    margins = {item: table[item].evidence["margin_pp"] for item in table if item[1] in ("T2", "T3")}
    assert margins == {("A", "T2"): 11, ("A", "T3"): 7, ("B", "T2"): 16, ("B", "T3"): 8}


@needs_data
def test_the_a_t5_plateau_is_detected_and_both_rules_agree_on_the_band():
    """China and Brazil are both exactly 99.0 in 2009-2011. The two definitions of the crossing year
    disagree (2012 vs 2009) and the key is only safe because both land in 2009-2012."""
    evidence = keys.key_table()[("A", "T5")].evidence
    assert evidence["cross_year"] == 2012
    assert evidence["not_below_year"] == 2009
    assert keys.band_for(2012) == keys.band_for(2009) == "2009-2012"


@needs_data
def test_t6_gaps_are_unreported_not_zero():
    table = keys.key_table()
    assert table[("A", "T6")].evidence["missing_years"] == {
        "United Kingdom": list(range(2000, 2019))
    }
    assert table[("B", "T6")].evidence["missing_years"] == {
        "Ethiopia": list(range(2000, 2007)),
        "Nigeria": list(range(2000, 2004)),
        "India": list(range(2000, 2004)),
    }


@needs_data
def test_t5_keys_sit_on_the_last_year_of_their_band():
    """The band-edge asymmetry ruled on in section 4. If this stops being true, the secondary
    analysis pre-registered for T5 no longer targets the right item; the ruling needs revisiting."""
    table = keys.key_table()
    for form in ("A", "B"):
        t4_year = table[(form, "T4")].evidence["cross_year"]
        t5_year = table[(form, "T5")].evidence["cross_year"]
        assert keys.band_for(t4_year).startswith(str(t4_year)), "T4 keys are first-year"
        assert keys.band_for(t5_year).endswith(str(t5_year)), "T5 keys are last-year"


# --- Bands --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "band"),
    [
        (2004, "2004-2008"),
        (2008, "2004-2008"),
        (2009, "2009-2012"),
        (2012, "2009-2012"),
        (2017, "2017-2020"),
        (2024, "2021-2024"),
    ],
)
def test_bands_are_inclusive_at_both_ends(year, band):
    assert keys.band_for(year) == band


@pytest.mark.parametrize("year", [2003, 2025])
def test_a_year_outside_every_band_is_refused(year):
    with pytest.raises(keys.KeyDerivationError, match=str(year)):
        keys.band_for(year)


def test_adjacent_band_credit_for_the_t5_keys():
    assert keys.adjacent_bands(2012) == {"2009-2012", "2013-2016"}
    assert keys.adjacent_bands(2008) == {"2004-2008", "2009-2012"}


def test_adjacent_bands_ignore_years_outside_every_band():
    assert keys.adjacent_bands(2004) == {"2004-2008"}


def test_strict_and_adjacent_scoring():
    table = {
        ("A", "T5"): keys.DerivedKey(
            "T5",
            "A",
            "crossing",
            "2009-2012",
            "rule",
            {"adjacent_bands": ["2009-2012", "2013-2016"]},
        )
    }
    assert keys.is_correct("A", "T5", "2013-2016", table) is False
    assert keys.is_correct_adjacent("A", "T5", "2013-2016", table) is True
    assert keys.is_correct_adjacent("A", "T5", "2017-2020", table) is False
    assert keys.is_correct_adjacent("A", "T4", "2017-2020", table) is None, "T5 only"
    assert keys.is_correct("A", "P0", "It fell", table) is None, "practice is unscored"


# --- Each rule refuses an item that is no longer well-posed -------------------------------------


@pytest.fixture
def params(monkeypatch):
    table: dict = {}
    monkeypatch.setattr(keys, "PARAMS", table)
    return table


def test_reference_counts_strictly_above_and_treats_a_tie_as_not_above(params):
    params[("Z", "T1")] = {"year": 2010}
    rows = _rows(
        {
            ("World", "DTP3"): {2010: 80.0},
            ("A", "DTP3"): {2010: 90.0},
            ("B", "DTP3"): {2010: 80.0},
            ("C", "DTP3"): {2010: 70.0},
        }
    )
    task = _task("T1", "reference", ("A", "B", "C", "World"), tasks.COUNT_OPTIONS)
    key = keys.derive(task, rows)
    assert key.correct == "1"
    assert key.evidence["above"] == ["A"]


def test_reference_refuses_a_missing_value(params):
    params[("Z", "T1")] = {"year": 2010}
    rows = _rows({("World", "DTP3"): {2010: 80.0}, ("A", "DTP3"): {}})
    task = _task("T1", "reference", ("A", "World"), tasks.COUNT_OPTIONS)
    with pytest.raises(keys.KeyDerivationError, match="not reported"):
        keys.derive(task, rows)


def test_trend_refuses_a_margin_too_small_to_have_one_answer(params):
    params[("Z", "T2")] = {"window": (2010, 2014), "direction": "fall"}
    rows = _rows(
        {
            ("A", "DTP3"): {2010: 90.0, 2014: 70.0},
            ("B", "DTP3"): {2010: 90.0, 2014: 72.0},
        }
    )
    task = _task("T2", "trend", ("A", "B"), ("A", "B"))
    with pytest.raises(keys.KeyDerivationError, match="defensible"):
        keys.derive(task, rows)


def test_trend_direction_decides_the_winner(params):
    params[("Z", "T3")] = {"window": (2010, 2014), "direction": "rise"}
    rows = _rows(
        {
            ("A", "DTP3"): {2010: 50.0, 2014: 90.0},
            ("B", "DTP3"): {2010: 90.0, 2014: 60.0},
        }
    )
    assert keys.derive(_task("T3", "trend", ("A", "B"), ("A", "B")), rows).correct == "A"


def _crossing_rows(differences: dict[int, float]) -> tuple[Row, ...]:
    return _rows(
        {
            ("Up", "DTP3"): {y: 50.0 + d for y, d in differences.items()},
            ("Down", "DTP3"): dict.fromkeys(differences, 50.0),
        }
    )


def test_crossing_refuses_an_overtaker_that_falls_back(params):
    params[("Z", "T4")] = {"overtaker": "Up", "overtaken": "Down"}
    differences = {y: -5.0 for y in range(2000, 2025)} | {2010: 5.0, 2011: 5.0, 2015: -1.0}
    task = _task("T4", "crossing", ("Up", "Down"), tasks.CROSSING_BANDS)
    with pytest.raises(keys.KeyDerivationError, match="more than one crossing"):
        keys.derive(task, _crossing_rows(differences))


def test_crossing_refuses_a_plateau_that_spans_two_bands(params):
    """Tied 2008-2010, above from 2011: 'no longer below' says 2008, 'strictly above' says 2011."""
    params[("Z", "T4")] = {"overtaker": "Up", "overtaken": "Down"}
    differences = {y: -5.0 for y in range(2000, 2008)}
    differences |= {2008: 0.0, 2009: 0.0, 2010: 0.0} | {y: 5.0 for y in range(2011, 2025)}
    task = _task("T4", "crossing", ("Up", "Down"), tasks.CROSSING_BANDS)
    with pytest.raises(keys.KeyDerivationError, match="different bands"):
        keys.derive(task, _crossing_rows(differences))


def test_crossing_refuses_a_series_that_never_overtakes(params):
    params[("Z", "T4")] = {"overtaker": "Up", "overtaken": "Down"}
    task = _task("T4", "crossing", ("Up", "Down"), tasks.CROSSING_BANDS)
    with pytest.raises(keys.KeyDerivationError, match="never overtakes"):
        keys.derive(task, _crossing_rows({y: -5.0 for y in range(2000, 2025)}))


def test_gap_refuses_a_recorded_zero_inside_the_window(params):
    """A 0.0 would make 'coverage was zero' true. That is the distinction the item tests."""
    params[("Z", "T6")] = {"series": ("A",), "before": 2019}
    values = {y: 90.0 for y in range(2019, 2025)} | {2005: 0.0}
    task = _task("T6", "gap", ("A",), tasks.GAP_OPTIONS, vaccine="HepB3")
    with pytest.raises(keys.KeyDerivationError, match="reported values inside the gap"):
        keys.derive(task, _rows({("A", "HepB3"): values}))


def test_gap_refuses_a_series_with_no_gap(params):
    params[("Z", "T6")] = {"series": ("A",), "before": None}
    task = _task("T6", "gap", ("A",), tasks.GAP_OPTIONS, vaccine="HepB3")
    with pytest.raises(keys.KeyDerivationError, match="no gap"):
        keys.derive(task, _rows({("A", "HepB3"): {y: 90.0 for y in range(2000, 2025)}}))


def test_a_key_that_is_not_an_option_is_refused(params):
    params[("Z", "T1")] = {"year": 2010}
    rows = _rows({("World", "DTP3"): {2010: 10.0}, ("A", "DTP3"): {2010: 90.0}})
    task = _task("T1", "reference", ("A", "World"), ("0", "2"))
    with pytest.raises(keys.KeyDerivationError, match="not one of the options"):
        keys.derive(task, rows)


# --- It never ships -----------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_analysis_is_excluded_from_the_vercel_bundle():
    """Without this, the answer key is uploaded with the app."""
    manifest = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    excluded = manifest["functions"]["src/app.py"]["excludeFiles"]
    assert "analysis/**" in excluded.strip("{}").split(",")


@pytest.mark.parametrize("module", sorted((ROOT / "src").glob("*.py")), ids=lambda p: p.name)
def test_no_src_module_imports_analysis(module):
    """Everything in src/ ships; the key must not be reachable from any of it."""
    assert "analysis" not in _imports(module)


def test_the_key_module_does_not_use_pandas():
    """The key must come from the same loader as the participant's chart, not a second read path."""
    assert not ({"pandas", "numpy", "pyarrow"} & _imports(ROOT / "analysis" / "keys.py"))


def test_the_key_module_reads_through_the_runtime_loader():
    assert "src" in _imports(ROOT / "analysis" / "keys.py")
    source = (ROOT / "analysis" / "keys.py").read_text(encoding="utf-8")
    assert "runtime_data.series" in source
    assert "open(" not in source and "read_csv" not in source
