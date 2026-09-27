"""Tests for the derived answer key, and for keeping it out of production.

The key is the study's ground truth. These guard the three ways it goes wrong silently:

- **It is wrong.** `docs/study-design.md` once said an item's answer was 2 when the data said 1.
  Every key here is derived from the deploy CSV and must agree with the transcribed table, and each
  rule refuses an item that has stopped being well-posed (a tie, a missing bar, a hidden dot).
- **It is fragile.** A key that is right only for a reader who can see exact values measures hover,
  not interpretation. Each rule also enforces the item acceptance rule in section 4: a close call on
  a value axis, a closer one on a colour scale, and a one-year slip that lands on another option.
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


def _rows(series: dict[str, dict[int, float | None]]) -> tuple[Row, ...]:
    """Synthetic DTP3 data: every listed entity over 2000-2024, None where a year is absent."""
    return tuple(
        Row(entity, "XXX", year, "DTP3", values.get(year))
        for entity, values in series.items()
        for year in range(2000, 2025)
    )


def _task(kind: str, entities, options, *, chart="line", years=(), task_id="T1") -> Task:
    return Task(
        task_id, "Z", kind, "prompt", "DTP3", tuple(entities), tuple(options), chart, tuple(years)
    )


@pytest.fixture
def params(monkeypatch):
    table: dict = {}
    monkeypatch.setattr(keys, "PARAMS", table)
    return table


# --- The real keys ------------------------------------------------------------------------------


@needs_data
def test_derived_keys_match_the_expected_table():
    """A wrong key in study-design.md section 4 fails here."""
    assert keys.check() == []


@needs_data
def test_a_wrong_transcription_is_caught():
    wrong = {**keys.EXPECTED, ("A", "T2"): "Vietnam"}
    problems = keys.check(wrong)
    assert len(problems) == 1
    assert "A-T2" in problems[0] and "'India'" in problems[0] and "'Vietnam'" in problems[0]


@needs_data
def test_a_written_item_transcribed_as_a_key_is_caught():
    """T1 is scored by rubric. A table claiming an option key for it disagrees with the data."""
    problems = keys.check({**keys.EXPECTED, ("B", "T1"): "2021"})
    assert len(problems) == 1 and "B-T1" in problems[0] and "'rubric'" in problems[0]


def test_expected_covers_every_scored_item():
    items = {(t.form, t.task_id) for form in tasks.FORMS for t in tasks.for_form(form)}
    assert set(keys.EXPECTED) == items
    assert set(keys.PARAMS) == items


@needs_data
def test_every_key_is_one_of_the_task_options():
    for (form, task_id), key in keys.key_table().items():
        task = next(t for t in tasks.for_form(form) if t.task_id == task_id)
        if tasks.is_written(task):
            assert key.correct == keys.RUBRIC, (form, task_id)
        else:
            assert key.correct in task.options, (form, task_id)


@needs_data
def test_the_margins_are_the_ones_study_design_records():
    """Section 4 matches the forms on these margins. A data refresh must not move them unnoticed."""
    table = keys.key_table()
    margins = {
        item: key.evidence.get("margin_pp", key.evidence.get("closest_pp"))
        for item, key in table.items()
        if key.kind not in ("rank", "crossing", "describe")
    }
    assert margins == {
        ("A", "T3"): 6.0,
        ("A", "T4"): 11.0,
        ("A", "T5"): 11.0,
        ("B", "T3"): 8.0,
        ("B", "T4"): 10.0,
        ("B", "T5"): 10.0,
    }
    for form in ("A", "B"):
        assert table[(form, "T2")].evidence["gaps_pp"] == {"above": 5.0, "below": 6.0}, form
    # T1's are the sizes of the shapes its rubric names, and how close another line runs.
    t1 = {form: table[(form, "T1")].evidence for form in ("A", "B")}
    assert (t1["A"]["drop_pp"], t1["A"]["rise_pp"], t1["A"]["recovery_pp"]) == (80.0, 36.0, 69.0)
    assert (t1["B"]["drop_pp"], t1["B"]["rise_pp"], t1["B"]["recovery_pp"]) == (31.0, 39.0, 23.0)
    assert t1["A"]["faller_trough"] == (2016, 19.0)
    assert t1["B"]["faller_trough"] == (2021, 68.0)
    assert t1["A"]["clearly_ahead_from"] == 2010
    assert t1["B"]["clearly_ahead_from"] == 2017
    assert t1["A"]["longest_close_run_years"] == t1["B"]["longest_close_run_years"] == 4
    # T6's margin is in years: how far inside the key band the two lines meet.
    assert table[("A", "T6")].evidence["intersection"] == 2006.71
    assert table[("A", "T6")].evidence["band_inset_years"] == 1.79
    assert table[("B", "T6")].evidence["intersection"] == 2019.1
    assert table[("B", "T6")].evidence["band_inset_years"] == 1.4


@needs_data
def test_no_answer_position_holds_more_than_a_third_of_the_keys():
    """Section 5. Options were once sorted by effect size, which put the key first in 7 of the 12
    items; a participant who noticed could score without reading a chart. T1 is written, so ten
    keys have a position (2026-09-27)."""
    positions = []
    for (form, task_id), key in keys.key_table().items():
        task = next(t for t in tasks.for_form(form) if t.task_id == task_id)
        if not tasks.is_written(task):
            positions.append(task.options.index(key.correct))
    assert len(positions) == 10
    most = max(positions.count(p) for p in set(positions))
    assert most <= len(positions) / 3, f"one position holds {most} of {len(positions)} keys"
    # The spread section 5 records, first to sixth.
    assert [positions.count(p) for p in range(6)] == [1, 2, 3, 2, 2, 0]


def test_scoring_is_strict_and_the_practice_is_unscored():
    table = {("A", "T2"): keys.DerivedKey("T2", "A", "rank", "India", "rule", {})}
    assert keys.is_correct("A", "T2", "India", table) is True
    assert keys.is_correct("A", "T2", "Vietnam", table) is False
    assert keys.is_correct("A", "T2", None, table) is False, "a skip scores incorrect"
    assert keys.is_correct("A", "P0", "It fell", table) is None, "practice is unscored"


def test_the_written_item_is_scored_by_the_coders_verdict():
    """T1 has no option key. Its score is the settled rubric verdict, None while uncoded, and a
    skipped description is incorrect without a coder, like any skip (study-design.md section 7)."""
    table = {("A", "T1"): keys.DerivedKey("T1", "A", "describe", keys.RUBRIC, "rule", {})}
    text = "India rose steadily; Ukraine fell sharply and recovered; India passed it."
    assert keys.is_correct("A", "T1", text, table, verdict=True) is True
    assert keys.is_correct("A", "T1", text, table, verdict=False) is False
    assert keys.is_correct("A", "T1", text, table) is None, "uncoded is not a score"
    assert keys.is_correct("A", "T1", None, table) is False, "a skip scores incorrect"
    assert keys.is_correct("A", "T1", "   ", table) is False
    # Even a text that happens to equal the sentinel is not scored by matching it.
    assert keys.is_correct("A", "T1", keys.RUBRIC, table) is None


# --- The items as first specified, 2026-09-23 ---------------------------------------------------
#
# The task bank was specified with near-equal bars, near-identical dark cells and countries a few
# points from the threshold, so that only the interactive condition could answer. The acceptance
# rule was kept instead, and these items were re-tuned (study-design.md section 4). Run on the real
# data, each original must still be refused -- that is what the rule is for.


@needs_data
@pytest.mark.parametrize(
    ("kind", "entities", "options", "chart", "years", "extra", "reason"),
    [
        (
            "rank",
            ("Bangladesh", "Brazil", "China", "Egypt", "India", "Nigeria", "Vietnam"),
            ("Bangladesh", "Brazil", "Egypt", "India", "Vietnam"),
            "bar",
            (2015,),
            {"rank": 3},
            "cannot be ranked",
        ),
        (
            "improved",
            ("Afghanistan", "Bangladesh", "Cambodia", "India", "Indonesia", "Nepal", "Pakistan"),
            ("Bangladesh", "Cambodia", "India", "Nepal", "Pakistan"),
            "scatter",
            (2000, 2024),
            {},
            "only 1 pts more than Afghanistan",
        ),
        (
            "cell",
            ("Chad", "Ethiopia", "India", "Indonesia", "Niger", "Nigeria", "Pakistan"),
            ("Chad", "Ethiopia", "Niger", "Nigeria", "Pakistan"),
            "heatmap",
            tasks.HEATMAP_YEARS,
            {},
            "only 3 pts below Nigeria",
        ),
        (
            "threshold",
            ("Chad", "Central African Republic", "Nigeria", "Somalia", "Tanzania"),
            tasks.COUNT_OPTIONS,
            "map",
            (2013,),
            {"threshold": 50},
            "Somalia",
        ),
    ],
    ids=["A-T2 bars", "B-T3 with Afghanistan", "A-T4 rows", "A-T5 pool"],
)
def test_the_items_as_first_specified_are_refused(
    params, kind, entities, options, chart, years, extra, reason
):
    params[("Z", "T1")] = extra
    task = _task(kind, sorted(entities), options, chart=chart, years=years)
    with pytest.raises(keys.KeyDerivationError, match=reason):
        keys.derive(task)


# The handoff's map set reaches three countries outside the locked scope, so their 2013 values are
# injected here, as the Our World in Data export gives them.
_OUTSIDE_SCOPE_2013 = {
    "Guinea": ("GIN", 56.0),
    "Senegal": ("SEN", 92.0),
    "South Sudan": ("SSD", 53.0),
}


@needs_data
def test_the_design_handoffs_map_set_is_refused(params):
    """The handoff's 13 for A-T5. South Sudan (53), Guinea (56) and Ethiopia (59) sit within 10
    points of 50% in 2013; Eduardo kept the existing 13 (study-design.md section 4)."""
    params[("Z", "T1")] = {"threshold": 50}
    rows = runtime_data.load_rows() + tuple(
        Row(name, code, 2013, "DTP3", value) for name, (code, value) in _OUTSIDE_SCOPE_2013.items()
    )
    handoff = (
        "Burkina Faso",
        "Cameroon",
        "Central African Republic",
        "Chad",
        "Ethiopia",
        "Guinea",
        "Kenya",
        "Mali",
        "Niger",
        "Nigeria",
        "Senegal",
        "South Sudan",
        "Uganda",
    )
    task = _task("threshold", handoff, tasks.COUNT_OPTIONS, **MAP)
    with pytest.raises(keys.KeyDerivationError, match=r"South Sudan \(53\)"):
        keys.derive(task, rows)
    # Each of the three is too close on its own, not only the closest.
    for name in ("South Sudan", "Guinea", "Ethiopia"):
        alone = ("Central African Republic", "Kenya", name)
        with pytest.raises(keys.KeyDerivationError, match=name):
            keys.derive(_task("threshold", alone, tasks.COUNT_OPTIONS, **MAP), rows)


# --- T1: two trends, written ------------------------------------------------------------------

RISER = {2000 + i: 50.0 + 1.5 * i for i in range(25)}  # 50 -> 86, steadily
FALLER = (
    {year: 95.0 for year in range(2000, 2008)}
    | {2008: 80.0, 2009: 60.0, 2010: 40.0, 2011: 35.0, 2012: 40.0, 2013: 55.0}
    | {year: 65.0 for year in range(2014, 2025)}
)  # 95, down to 35 in 2011, back to 65: one crossing, the riser 5 points clear from 2010
FAR_BELOW = {year: 10.0 for year in range(2000, 2025)}


def _describe(series: dict, entities=("R", "F", "X")) -> tuple[Task, tuple[Row, ...]]:
    return _task("describe", entities, ()), _rows(series)


def test_describe_accepts_a_rise_a_fall_and_recovery_and_one_crossing(params):
    params[("Z", "T1")] = {"riser": "R", "faller": "F"}
    task, rows = _describe({"R": RISER, "F": FALLER, "X": FAR_BELOW})
    key = keys.derive(task, rows)
    assert key.correct == keys.RUBRIC
    assert key.evidence["rise_pp"] == 36.0
    assert key.evidence["drop_pp"] == 60.0 and key.evidence["recovery_pp"] == 30.0
    assert key.evidence["faller_peak"] == (2007, 95.0)
    assert key.evidence["clearly_ahead_from"] == 2010


@pytest.mark.parametrize(
    ("riser", "faller", "reason"),
    [
        ({y: 70.0 + 0.5 * (y - 2000) for y in range(2000, 2025)}, FALLER, "rises 12 pts"),
        (RISER | {2012: 50.0}, FALLER, "dips 16.5"),
        (RISER, {y: max(v, 75.0) for y, v in FALLER.items()}, "drops 20 pts"),
        (RISER, FALLER | {y: 40.0 for y in range(2014, 2025)}, "recovers 5"),
        (RISER, FALLER | {2023: 99.0, 2024: 99.0}, "change places 2 times"),
        ({y: v + 50.0 for y, v in RISER.items()}, FALLER, "starting with R above"),
    ],
    ids=["flat riser", "riser dips", "shallow fall", "no recovery", "crosses back", "riser above"],
)
def test_describe_refuses_a_shape_the_rubric_names_that_is_not_there(params, riser, faller, reason):
    params[("Z", "T1")] = {"riser": "R", "faller": "F"}
    task, rows = _describe({"R": riser, "F": faller, "X": FAR_BELOW})
    with pytest.raises(keys.KeyDerivationError, match=reason):
        keys.derive(task, rows)


def test_describe_refuses_a_line_running_alongside_a_named_one(params):
    """Five years within 5 points of the riser: it could be followed by mistake."""
    params[("Z", "T1")] = {"riser": "R", "faller": "F"}
    shadow = FAR_BELOW | {y: RISER[y] + 3 for y in range(2015, 2020)}
    task, rows = _describe({"R": RISER, "F": FALLER, "X": shadow})
    with pytest.raises(keys.KeyDerivationError, match="X's line runs within 5 pts of R's for 5"):
        keys.derive(task, rows)
    # Four years is allowed.
    shadow = FAR_BELOW | {y: RISER[y] + 3 for y in range(2015, 2019)}
    task, rows = _describe({"R": RISER, "F": FALLER, "X": shadow})
    assert keys.derive(task, rows).evidence["longest_close_run_years"] == 4


def test_describe_counts_closeness_to_the_faller_only_from_its_last_peak(params):
    """Before the fall both lines can sit together at the top; the story starts at the peak."""
    params[("Z", "T1")] = {"riser": "R", "faller": "F"}
    beside_early = FAR_BELOW | {y: 95.0 for y in range(2000, 2007)}
    task, rows = _describe({"R": RISER, "F": FALLER, "X": beside_early})
    assert keys.derive(task, rows).evidence["clearance"]["X"]["F"][0] == 0


def test_describe_refuses_a_gap_in_a_named_line(params):
    params[("Z", "T1")] = {"riser": "R", "faller": "F"}
    task, rows = _describe({"R": RISER | {2012: None}, "F": FALLER, "X": FAR_BELOW})
    with pytest.raises(keys.KeyDerivationError, match=r"R is not reported in \[2012\]"):
        keys.derive(task, rows)


def test_describe_refuses_a_country_not_on_the_chart(params):
    params[("Z", "T1")] = {"riser": "R", "faller": "F"}
    task, rows = _describe({"R": RISER, "F": FALLER, "X": FAR_BELOW}, entities=("R", "X"))
    with pytest.raises(keys.KeyDerivationError, match="F is not on the chart"):
        keys.derive(task, rows)


@needs_data
def test_b_t1_with_india_on_the_chart_is_refused(params):
    """India runs within 5 points of Uganda for years, which is why B's chart dropped it
    (study-design.md section 4, 2026-09-27)."""
    params[("Z", "T1")] = {"riser": "Uganda", "faller": "Brazil"}
    b_t1 = next(t for t in tasks.for_form("B") if t.task_id == "T1")
    with_india = tuple(sorted({*b_t1.entities, "India"} - {"Nepal"}))
    with pytest.raises(keys.KeyDerivationError, match="India's line runs within 5 pts of Uganda"):
        keys.derive(_task("describe", with_india, ()))


@needs_data
def test_myanmar_and_ethiopia_are_refused_as_a_b_t1_pair(params):
    """The first candidate for form B: their lines change places twice around Myanmar's 2021 dip."""
    params[("Z", "T1")] = {"riser": "Ethiopia", "faller": "Myanmar"}
    with pytest.raises(keys.KeyDerivationError, match="change places 2 times"):
        keys.derive(_task("describe", ("Ethiopia", "Myanmar"), ()))


def test_the_rubric_names_the_forms_own_countries():
    assert keys.rubric_parts("A") == {
        "a": "India's coverage rose over the period",
        "b": "Ukraine's coverage fell and then recovered",
        "c": "India overtook or passed Ukraine, or the two ended close or level",
    }
    assert "Uganda" in keys.rubric_parts("B")["a"] and "Brazil" in keys.rubric_parts("B")["b"]
    for form in ("A", "B"):
        (t1,) = [t for t in tasks.for_form(form) if t.task_id == "T1"]
        params = keys.PARAMS[(form, "T1")]
        assert params["riser"] in t1.prompt and params["faller"] in t1.prompt, form


# --- T2: the third-highest bar ------------------------------------------------------------------


def _bars(values: dict[str, float | None], year: int = 2017) -> tuple[Row, ...]:
    return _rows({name: {year: value} for name, value in values.items()})


def test_rank_finds_the_third_highest_bar(params):
    params[("Z", "T1")] = {"rank": 3}
    rows = _bars({"A": 99.0, "B": 94.0, "C": 89.0, "D": 83.0, "E": 60.0})
    key = keys.derive(_task("rank", "ABCDE", "ABCDE", chart="bar", years=(2017,)), rows)
    assert key.correct == "C"
    assert key.evidence["gaps_pp"] == {"above": 5.0, "below": 6.0}


@pytest.mark.parametrize(("above", "below"), [(90.0, 83.0), (94.0, 86.0)])
def test_rank_refuses_a_neighbour_within_five_points(params, above, below):
    """A-T2 as specified: 99, 98, 97, 96 cannot be ranked by bar height."""
    params[("Z", "T1")] = {"rank": 3}
    rows = _bars({"A": 99.0, "B": above, "C": 89.0, "D": below, "E": 60.0})
    with pytest.raises(keys.KeyDerivationError, match="cannot be ranked"):
        keys.derive(_task("rank", "ABCDE", "ABCDE", chart="bar", years=(2017,)), rows)


def test_rank_refuses_a_missing_bar(params):
    params[("Z", "T1")] = {"rank": 3}
    rows = _bars({"A": 99.0, "B": 94.0, "C": 89.0, "D": None, "E": 60.0})
    with pytest.raises(keys.KeyDerivationError, match="not reported"):
        keys.derive(_task("rank", "ABCDE", "ABCDE", chart="bar", years=(2017,)), rows)


# --- T3: the most improved dot ------------------------------------------------------------------


def _dots(points: dict[str, tuple[float, float]]) -> tuple[Row, ...]:
    return _rows({name: {2000: x, 2024: y} for name, (x, y) in points.items()})


SCATTER = {"chart": "scatter", "years": (2000, 2024)}


def test_improved_finds_the_dot_furthest_above_the_diagonal(params):
    params[("Z", "T1")] = {}
    rows = _dots({"A": (34.0, 86.0), "B": (45.0, 91.0), "C": (30.0, 60.0)})
    key = keys.derive(_task("improved", "ABC", "ABC", **SCATTER), rows)
    assert key.correct == "A"
    assert key.evidence["margin_pp"] == 6.0


def test_improved_refuses_a_near_tie(params):
    """B-T3 with Afghanistan: its +35 against India's +36."""
    params[("Z", "T1")] = {}
    rows = _dots({"A": (58.0, 94.0), "B": (24.0, 59.0), "C": (80.0, 90.0)})
    with pytest.raises(keys.KeyDerivationError, match="only 1 pts more"):
        keys.derive(_task("improved", "ABC", "ABC", **SCATTER), rows)


def test_improved_refuses_dots_that_hide_each_other(params):
    """A-T3 as specified: Angola (31, 64) and DR Congo (30, 65) are 1.4 points apart."""
    params[("Z", "T1")] = {}
    rows = _dots({"A": (34.0, 86.0), "B": (31.0, 64.0), "C": (30.0, 65.0)})
    with pytest.raises(keys.KeyDerivationError, match="hides the other"):
        keys.derive(_task("improved", "ABC", "ABC", **SCATTER), rows)


# --- T4: the lowest heatmap cell ----------------------------------------------------------------


def _grid(rows_by_name: dict[str, list[float | None]]) -> tuple[Row, ...]:
    return _rows(
        {
            name: dict(zip(tasks.HEATMAP_YEARS, cells, strict=True))
            for name, cells in rows_by_name.items()
        }
    )


HEATMAP = {"chart": "heatmap", "years": tasks.HEATMAP_YEARS}


def test_cell_finds_the_row_holding_the_lowest_cell(params):
    params[("Z", "T1")] = {}
    rows = _grid({"A": [40, 26, 45, 50, 60, 70], "B": [37, 50, 60, 70, 80, 90], "C": [80] * 6})
    key = keys.derive(_task("cell", "ABC", "ABC", **HEATMAP), rows)
    assert key.correct == "A"
    assert key.evidence["row_minima"]["A"] == (26, 2005)
    assert key.evidence["margin_pp"] == 11


def test_cell_refuses_two_colours_under_ten_points_apart(params):
    """A-T4 as specified: Chad's 26 against Nigeria's 29 -- the same colour, to the eye."""
    params[("Z", "T1")] = {}
    rows = _grid({"A": [40, 26, 45, 50, 60, 70], "B": [29, 50, 60, 70, 80, 90], "C": [80] * 6})
    with pytest.raises(keys.KeyDerivationError, match="cannot be told apart"):
        keys.derive(_task("cell", "ABC", "ABC", **HEATMAP), rows)


def test_cell_refuses_an_empty_cell(params):
    params[("Z", "T1")] = {}
    rows = _grid({"A": [40, 26, 45, 50, 60, 70], "B": [None, 50, 60, 70, 80, 90], "C": [80] * 6})
    with pytest.raises(keys.KeyDerivationError, match="not reported"):
        keys.derive(_task("cell", "ABC", "ABC", **HEATMAP), rows)


# --- T5: countries below the threshold ----------------------------------------------------------


def _map(values: dict[str, float | None], year: int = 2013) -> tuple[Row, ...]:
    return _rows({name: {year: value} for name, value in values.items()})


MAP = {"chart": "map", "years": (2013,)}


def test_threshold_counts_the_countries_strictly_below(params):
    params[("Z", "T1")] = {"threshold": 50}
    rows = _map({"A": 23.0, "B": 39.0, "C": 39.0, "D": 64.0, "E": 91.0})
    key = keys.derive(_task("threshold", "ABCDE", tasks.COUNT_OPTIONS, **MAP), rows)
    assert key.correct == "3"
    assert key.evidence["below"] == ["A", "B", "C"]
    assert key.evidence["closest_pp"] == 11.0


def test_threshold_counts_five_or_more_as_one_option(params):
    params[("Z", "T1")] = {"threshold": 50}
    rows = _map({"A": 20.0, "B": 25.0, "C": 30.0, "D": 35.0, "E": 38.0, "F": 80.0})
    key = keys.derive(_task("threshold", "ABCDEF", tasks.COUNT_OPTIONS, **MAP), rows)
    assert key.correct == "5 or more"
    rows = _map({"A": 20.0, "B": 25.0, "C": 30.0, "D": 35.0, "F": 80.0})
    assert keys.derive(_task("threshold", "ABCDF", tasks.COUNT_OPTIONS, **MAP), rows).correct == "4"


@pytest.mark.parametrize("value", [53.0, 47.0, 50.0], ids=["3 above", "3 below", "on the line"])
def test_threshold_refuses_a_country_near_the_line(params, value):
    """A-T5 as specified: South Sudan at 53 against 50%, a colour judgement nobody can make."""
    params[("Z", "T1")] = {"threshold": 50}
    rows = _map({"A": 23.0, "B": value, "C": 80.0})
    with pytest.raises(keys.KeyDerivationError, match="too fine"):
        keys.derive(_task("threshold", "ABC", tasks.COUNT_OPTIONS, **MAP), rows)


def test_a_key_that_is_not_an_option_is_refused(params):
    params[("Z", "T1")] = {"threshold": 50}
    rows = _map({"A": 23.0, "B": 80.0})
    task = _task("threshold", "AB", ("0", "2"), **MAP)
    with pytest.raises(keys.KeyDerivationError, match="not one of the options"):
        keys.derive(task, rows)


# --- T6: the crossing ---------------------------------------------------------------------------


def _rising(start: float, slope: float) -> dict[int, float]:
    return {year: start + slope * (year - 2000) for year in range(2000, 2025)}


FLAT_50 = {year: 50.0 for year in range(2000, 2025)}


def _crossing_task(entities=("A", "B")) -> Task:
    return _task("crossing", entities, tasks.CROSSING_BANDS)


@pytest.fixture
def race(params):
    """A overtakes B, the parameters every crossing test below uses."""
    params[("Z", "T1")] = {"overtaker": "A", "overtaken": "B"}
    return params


def test_crossing_finds_the_band_of_the_first_year_above(race):
    """A rises 2 points a year from 37 against a flat 50: 49 in 2006, 51 in 2007."""
    rows = _rows({"A": _rising(37.0, 2.0), "B": FLAT_50})
    key = keys.derive(_crossing_task(), rows)
    assert key.correct == "2004-2008"
    assert key.evidence["cross_year"] == 2007
    assert key.evidence["intersection"] == 2006.5
    assert key.evidence["band_inset_years"] == 2.0
    assert key.evidence["trailed_by_pp"] == 13.0
    assert key.evidence["adjacent_bands"] == ["2004-2008"]


def test_crossing_keys_a_tie_to_the_year_after(race):
    """Level in 2006, above in 2007: strictly above is 2007, no longer below 2006. One band."""
    rows = _rows({"A": _rising(38.0, 2.0), "B": FLAT_50})
    key = keys.derive(_crossing_task(), rows)
    assert (key.evidence["cross_year"], key.evidence["not_below_year"]) == (2007, 2006)
    assert key.correct == "2004-2008"


def test_crossing_refuses_a_plateau_of_ties_across_two_bands(race):
    """Level with B through 2007 and 2008, above from 2009: 2007 and 2009 are different bands."""
    a = {year: 40.0 if year < 2007 else 50.0 if year < 2009 else 60.0 for year in range(2000, 2025)}
    rows = _rows({"A": a, "B": FLAT_50})
    with pytest.raises(keys.KeyDerivationError, match="different bands"):
        keys.derive(_crossing_task(), rows)


def test_crossing_refuses_lines_that_meet_near_a_band_edge(race):
    """2 behind in 2009, 8 ahead in 2010: they meet at 2009.2, 0.7 years into 2009-2012."""
    a = {year: 45.0 if year < 2009 else 58.0 for year in range(2000, 2025)} | {2009: 48.0}
    rows = _rows({"A": a, "B": FLAT_50})
    with pytest.raises(keys.KeyDerivationError, match="only 0.70 years inside 2009-2012"):
        keys.derive(_crossing_task(), rows)


def test_crossing_refuses_a_second_crossing(race):
    rows = _rows({"A": _rising(37.0, 2.0) | {2015: 45.0}, "B": FLAT_50})
    with pytest.raises(keys.KeyDerivationError, match="falls back"):
        keys.derive(_crossing_task(), rows)


def test_crossing_refuses_a_line_that_led_before(race):
    """Above in 2000, then below, then above again: when did it "first" happen? In 2000."""
    rows = _rows({"A": _rising(37.0, 2.0) | {2000: 60.0}, "B": FLAT_50})
    with pytest.raises(keys.KeyDerivationError, match="already above"):
        keys.derive(_crossing_task(), rows)


def test_crossing_refuses_lines_that_touch_rather_than_cross(race):
    """Never more than 3 points apart: two lines drawn on top of each other, not a crossing."""
    a = {year: 47.0 if year < 2007 else 53.0 for year in range(2000, 2025)}
    rows = _rows({"A": a, "B": FLAT_50})
    with pytest.raises(keys.KeyDerivationError, match="touch rather than cross"):
        keys.derive(_crossing_task(), rows)


def test_crossing_refuses_a_line_that_never_overtakes(race):
    rows = _rows({"A": {year: 40.0 for year in range(2000, 2025)}, "B": FLAT_50})
    with pytest.raises(keys.KeyDerivationError, match="never overtakes"):
        keys.derive(_crossing_task(), rows)


def test_crossing_refuses_a_third_line_through_the_meeting_point(race):
    """B-T6 with World: a third line 2 points from the crossing would be taken for one of them."""
    rows = _rows({"A": _rising(37.0, 2.0), "B": FLAT_50, "C": {y: 52.0 for y in range(2000, 2025)}})
    with pytest.raises(keys.KeyDerivationError, match="C's line passes 2.0 pts"):
        keys.derive(_crossing_task(("A", "B", "C")), rows)


def test_crossing_allows_a_third_line_well_clear(race):
    rows = _rows({"A": _rising(37.0, 2.0), "B": FLAT_50, "C": {y: 80.0 for y in range(2000, 2025)}})
    key = keys.derive(_crossing_task(("A", "B", "C")), rows)
    assert key.evidence["other_lines_clearance_pp"] == {"C": 30.0}


def test_crossing_refuses_a_line_not_on_the_chart(race):
    rows = _rows({"A": _rising(37.0, 2.0), "B": FLAT_50})
    with pytest.raises(keys.KeyDerivationError, match="B is not on the chart"):
        keys.derive(_crossing_task(("A",)), rows)


def test_crossing_is_judged_only_on_years_both_lines_report(race):
    """B unreported in 2006: the lines are drawn from 2005 to 2007 there, and meet in between."""
    rows = _rows({"A": _rising(37.0, 2.0), "B": FLAT_50 | {2006: None}})
    key = keys.derive(_crossing_task(), rows)
    assert 2006 not in key.evidence["differences"]
    assert key.evidence["intersection"] == 2006.5
    assert key.correct == "2004-2008"


@needs_data
def test_b_t7_is_refused_with_the_world_line_and_a_t7_is_not(params):
    """Why neither T6 chart draws World (study-design.md section 4): in B it runs through the
    crossing. In A it would pass, and is left out so the two forms draw the same chart."""
    params[("Z", "T1")] = {"overtaker": "Pakistan", "overtaken": "Mozambique"}
    with pytest.raises(keys.KeyDerivationError, match="World's line passes 2.1 pts"):
        keys.derive(_crossing_task(("Mozambique", "Pakistan", "World")))
    params[("Z", "T1")] = {"overtaker": "Ethiopia", "overtaken": "Central African Republic"}
    key = keys.derive(_crossing_task(("Central African Republic", "Ethiopia", "World")))
    assert key.evidence["other_lines_clearance_pp"]["World"] > 25


def test_band_for_refuses_a_year_no_band_covers():
    assert keys.band_for(2000) == "2000-2003"
    assert keys.band_for(2004) == "2004-2008"
    assert keys.band_for(2024) == "2021-2024"
    with pytest.raises(keys.KeyDerivationError, match="No answer band contains 2025"):
        keys.band_for(2025)
    with pytest.raises(keys.KeyDerivationError, match="No answer band contains 2003"):
        keys.band_for(2003, bands=("2004-2008", "2009-2012"))


@pytest.mark.parametrize(
    ("year", "accepted"),
    [
        (2007, {"2004-2008"}),
        (2020, {"2017-2020", "2021-2024"}),
        (2013, {"2009-2012", "2013-2016"}),
        (2004, {"2000-2003", "2004-2008"}),
        (2000, {"2000-2003"}),
        (2024, {"2021-2024"}),
    ],
    ids=["mid-band", "band end", "band start", "after 2000-2003", "first year", "last year"],
)
def test_adjacent_bands_credit_the_band_a_year_either_side(year, accepted):
    assert keys.adjacent_bands(year) == accepted


def test_adjacent_scoring_applies_to_the_crossing_item_only():
    """The pre-registered secondary (section 7). B-T6's key year, 2020, closes its band."""
    evidence = {"adjacent_bands": ["2017-2020", "2021-2024"]}
    table = {
        ("B", "T6"): keys.DerivedKey("T6", "B", "crossing", "2017-2020", "rule", evidence),
        ("B", "T2"): keys.DerivedKey("T2", "B", "rank", "Colombia", "rule", {}),
    }
    assert keys.is_correct_adjacent("B", "T6", "2017-2020", table) is True
    assert keys.is_correct_adjacent("B", "T6", "2021-2024", table) is True
    assert keys.is_correct("B", "T6", "2021-2024", table) is False, "strict stays strict"
    assert keys.is_correct_adjacent("B", "T6", "2013-2016", table) is False
    assert keys.is_correct_adjacent("B", "T6", None, table) is False, "a skip is still incorrect"
    assert keys.is_correct_adjacent("B", "T2", "Colombia", table) is None
    assert keys.is_correct_adjacent("B", "P0", "It fell", table) is None


def test_an_unknown_kind_has_no_rule(params):
    params[("Z", "T1")] = {}
    with pytest.raises(keys.KeyDerivationError, match="No scoring rule"):
        keys.derive(_task("gap", "A", "A"), _rows({"A": {}}))


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


def test_identifying_material_never_ships():
    """Local signed consent records and the IRB paperwork carry names; neither may be uploaded."""
    manifest = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    excluded = manifest["functions"]["src/app.py"]["excludeFiles"].strip("{}").split(",")
    assert {"data/consent/**", "irb/**"} <= set(excluded)


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
