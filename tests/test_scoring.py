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

YEAR_OPTIONS = ("2008", "2016", "2019", "2022", "2024")


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
    wrong = {**keys.EXPECTED, ("A", "T1"): "2019"}
    problems = keys.check(wrong)
    assert len(problems) == 1
    assert "A-T1" in problems[0] and "'2016'" in problems[0] and "'2019'" in problems[0]


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
def test_the_margins_are_the_ones_study_design_records():
    """Section 4 matches the forms on these margins. A data refresh must not move them unnoticed."""
    table = keys.key_table()
    margins = {
        item: key.evidence.get("margin_pp", key.evidence.get("closest_pp"))
        for item, key in table.items()
        if key.kind not in ("rank", "crossing")
    }
    assert margins == {
        ("A", "T1"): 54.0,
        ("A", "T2"): 6.0,
        ("A", "T4"): 6.0,
        ("A", "T5"): 11.0,
        ("A", "T6"): 11.0,
        ("B", "T1"): 34.0,
        ("B", "T2"): 8.0,
        ("B", "T4"): 8.0,
        ("B", "T5"): 10.0,
        ("B", "T6"): 10.0,
    }
    for form in ("A", "B"):
        assert table[(form, "T3")].evidence["gaps_pp"] == {"above": 5.0, "below": 6.0}, form
    # T7's margin is in years: how far inside the key band the two lines meet.
    assert table[("A", "T7")].evidence["intersection"] == 2006.71
    assert table[("A", "T7")].evidence["band_inset_years"] == 1.79
    assert table[("B", "T7")].evidence["intersection"] == 2019.1
    assert table[("B", "T7")].evidence["band_inset_years"] == 1.4


@needs_data
def test_no_answer_position_holds_more_than_a_third_of_the_keys():
    """Section 5. Options were once sorted by effect size, which put the key first in 7 of the 12
    items; a participant who noticed could score without reading a chart."""
    positions = []
    for (form, task_id), key in keys.key_table().items():
        task = next(t for t in tasks.for_form(form) if t.task_id == task_id)
        positions.append(task.options.index(key.correct))
    most = max(positions.count(p) for p in set(positions))
    assert most <= len(positions) / 3, f"one position holds {most} of {len(positions)} keys"


def test_scoring_is_strict_and_the_practice_is_unscored():
    table = {("A", "T3"): keys.DerivedKey("T3", "A", "rank", "India", "rule", {})}
    assert keys.is_correct("A", "T3", "India", table) is True
    assert keys.is_correct("A", "T3", "Vietnam", table) is False
    assert keys.is_correct("A", "T3", None, table) is False, "a skip scores incorrect"
    assert keys.is_correct("A", "P0", "It fell", table) is None, "practice is unscored"


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
            "lowest",
            ("Brazil", "China", "Ethiopia", "India", "Indonesia", "Nigeria", "Pakistan", "Ukraine"),
            ("2010", "2013", "2016", "2019", "2022"),
            "line",
            (),
            {"entity": "Ukraine"},
            "nearest 2013",
        ),
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
    ids=["A-T1 options", "A-T3 bars", "B-T4 with Afghanistan", "A-T5 rows", "A-T6 pool"],
)
def test_the_items_as_first_specified_are_refused(
    params, kind, entities, options, chart, years, extra, reason
):
    params[("Z", "T1")] = extra
    task = _task(kind, sorted(entities), options, chart=chart, years=years)
    with pytest.raises(keys.KeyDerivationError, match=reason):
        keys.derive(task)


# --- T1: the lowest point -----------------------------------------------------------------------


def _collapse(low_years: dict[int, float]) -> dict[int, float]:
    """A line at 90 with a collapse wherever `low_years` says."""
    return {year: 90.0 for year in range(2000, 2025)} | low_years


def test_lowest_finds_the_year_of_the_minimum(params):
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _collapse({2014: 23.0, 2015: 23.0, 2016: 19.0})})
    key = keys.derive(_task("lowest", ("A",), YEAR_OPTIONS), rows)
    assert key.correct == "2016"
    assert key.evidence["near_lowest_years"] == [2014, 2015, 2016]


def test_lowest_refuses_a_near_minimum_year_nearest_another_option(params):
    """A-T1 as specified: Ukraine is 23 in 2014, 4 points off its low, and 2014 is nearer 2013."""
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _collapse({2014: 23.0, 2015: 23.0, 2016: 19.0})})
    task = _task("lowest", ("A",), ("2010", "2013", "2016", "2019", "2022"))
    with pytest.raises(keys.KeyDerivationError, match="read as 2013, is nearest 2013"):
        keys.derive(task, rows)


def test_lowest_refuses_an_option_a_year_off_the_low_point(params):
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _collapse({2016: 20.0})})
    task = _task("lowest", ("A",), ("2008", "2015", "2016", "2020", "2024"))
    with pytest.raises(keys.KeyDerivationError, match="nearest 2015"):
        keys.derive(task, rows)


def test_lowest_refuses_a_reading_halfway_between_two_options(params):
    """2016 read a year late is 2017, exactly between the 2016 and 2018 options: a coin toss."""
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _collapse({2016: 20.0})})
    task = _task("lowest", ("A",), ("2004", "2008", "2016", "2018", "2024"))
    with pytest.raises(keys.KeyDerivationError, match="read as 2017, is nearest no single option"):
        keys.derive(task, rows)


def test_lowest_refuses_a_tie_at_the_minimum(params):
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _collapse({2008: 20.0, 2016: 20.0})})
    with pytest.raises(keys.KeyDerivationError, match="lowest"):
        keys.derive(_task("lowest", ("A",), YEAR_OPTIONS), rows)


def test_lowest_refuses_a_country_not_on_the_chart(params):
    params[("Z", "T1")] = {"entity": "B"}
    rows = _rows({"A": _collapse({2016: 20.0})})
    with pytest.raises(keys.KeyDerivationError, match="not on the chart"):
        keys.derive(_task("lowest", ("A",), YEAR_OPTIONS), rows)


# --- T2: the largest one-year rise --------------------------------------------------------------


def _steps(rises: dict[int, float]) -> dict[int, float]:
    """A line starting at 40 that rises by `rises[year]` into each listed year, flat otherwise."""
    values, level = {}, 40.0
    for year in range(2000, 2025):
        level += rises.get(year, 0.0)
        values[year] = level
    return values


RISE_OPTIONS = ("2005", "2011", "2015", "2018", "2021")


def test_rise_finds_the_year_of_the_steepest_rise(params):
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _steps({2011: 11.0, 2018: 5.0})})
    key = keys.derive(_task("rise", ("A",), RISE_OPTIONS), rows)
    assert key.correct == "2011"
    assert key.evidence["runner_up"] == (2018, 5.0)
    assert key.evidence["margin_pp"] == 6.0


def test_rise_refuses_a_runner_up_within_five_points(params):
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _steps({2011: 11.0, 2018: 7.0})})
    with pytest.raises(keys.KeyDerivationError, match="only 4 pts"):
        keys.derive(_task("rise", ("A",), RISE_OPTIONS), rows)


def test_rise_refuses_an_option_at_the_start_of_the_steep_segment(params):
    """The rise into 2011 starts in 2010; a participant may take either end for "the year"."""
    params[("Z", "T1")] = {"entity": "A"}
    rows = _rows({"A": _steps({2011: 11.0})})
    task = _task("rise", ("A",), ("2005", "2010", "2011", "2018", "2021"))
    with pytest.raises(keys.KeyDerivationError, match="nearest 2010"):
        keys.derive(task, rows)


# --- T3: the third-highest bar ------------------------------------------------------------------


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
    """A-T3 as specified: 99, 98, 97, 96 cannot be ranked by bar height."""
    params[("Z", "T1")] = {"rank": 3}
    rows = _bars({"A": 99.0, "B": above, "C": 89.0, "D": below, "E": 60.0})
    with pytest.raises(keys.KeyDerivationError, match="cannot be ranked"):
        keys.derive(_task("rank", "ABCDE", "ABCDE", chart="bar", years=(2017,)), rows)


def test_rank_refuses_a_missing_bar(params):
    params[("Z", "T1")] = {"rank": 3}
    rows = _bars({"A": 99.0, "B": 94.0, "C": 89.0, "D": None, "E": 60.0})
    with pytest.raises(keys.KeyDerivationError, match="not reported"):
        keys.derive(_task("rank", "ABCDE", "ABCDE", chart="bar", years=(2017,)), rows)


# --- T4: the most improved dot ------------------------------------------------------------------


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
    """B-T4 with Afghanistan: its +35 against India's +36."""
    params[("Z", "T1")] = {}
    rows = _dots({"A": (58.0, 94.0), "B": (24.0, 59.0), "C": (80.0, 90.0)})
    with pytest.raises(keys.KeyDerivationError, match="only 1 pts more"):
        keys.derive(_task("improved", "ABC", "ABC", **SCATTER), rows)


def test_improved_refuses_dots_that_hide_each_other(params):
    """A-T4 as specified: Angola (31, 64) and DR Congo (30, 65) are 1.4 points apart."""
    params[("Z", "T1")] = {}
    rows = _dots({"A": (34.0, 86.0), "B": (31.0, 64.0), "C": (30.0, 65.0)})
    with pytest.raises(keys.KeyDerivationError, match="hides the other"):
        keys.derive(_task("improved", "ABC", "ABC", **SCATTER), rows)


# --- T5: the lowest heatmap cell ----------------------------------------------------------------


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
    """A-T5 as specified: Chad's 26 against Nigeria's 29 -- the same colour, to the eye."""
    params[("Z", "T1")] = {}
    rows = _grid({"A": [40, 26, 45, 50, 60, 70], "B": [29, 50, 60, 70, 80, 90], "C": [80] * 6})
    with pytest.raises(keys.KeyDerivationError, match="cannot be told apart"):
        keys.derive(_task("cell", "ABC", "ABC", **HEATMAP), rows)


def test_cell_refuses_an_empty_cell(params):
    params[("Z", "T1")] = {}
    rows = _grid({"A": [40, 26, 45, 50, 60, 70], "B": [None, 50, 60, 70, 80, 90], "C": [80] * 6})
    with pytest.raises(keys.KeyDerivationError, match="not reported"):
        keys.derive(_task("cell", "ABC", "ABC", **HEATMAP), rows)


# --- T6: countries below the threshold ----------------------------------------------------------


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


def test_threshold_counts_four_or_more_as_one_option(params):
    params[("Z", "T1")] = {"threshold": 50}
    rows = _map({"A": 20.0, "B": 25.0, "C": 30.0, "D": 35.0, "E": 38.0, "F": 80.0})
    key = keys.derive(_task("threshold", "ABCDEF", tasks.COUNT_OPTIONS, **MAP), rows)
    assert key.correct == "4 or more"


@pytest.mark.parametrize("value", [53.0, 47.0, 50.0], ids=["3 above", "3 below", "on the line"])
def test_threshold_refuses_a_country_near_the_line(params, value):
    """A-T6 as specified: South Sudan at 53 against 50%, a colour judgement nobody can make."""
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


# --- T7: the crossing ---------------------------------------------------------------------------


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
    """B-T7 with World: a third line 2 points from the crossing would be taken for one of them."""
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
    """Why neither T7 chart draws World (study-design.md section 4): in B it runs through the
    crossing. In A it would pass, and is left out so the two forms draw the same chart."""
    params[("Z", "T1")] = {"overtaker": "Pakistan", "overtaken": "Mozambique"}
    with pytest.raises(keys.KeyDerivationError, match="World's line passes 2.1 pts"):
        keys.derive(_crossing_task(("Mozambique", "Pakistan", "World")))
    params[("Z", "T1")] = {"overtaker": "Ethiopia", "overtaken": "Central African Republic"}
    key = keys.derive(_crossing_task(("Central African Republic", "Ethiopia", "World")))
    assert key.evidence["other_lines_clearance_pp"]["World"] > 25


def test_band_for_refuses_a_year_no_band_covers():
    assert keys.band_for(2004) == "2004-2008"
    assert keys.band_for(2024) == "2021-2024"
    with pytest.raises(keys.KeyDerivationError, match="No answer band contains 2003"):
        keys.band_for(2003)


@pytest.mark.parametrize(
    ("year", "accepted"),
    [
        (2007, {"2004-2008"}),
        (2020, {"2017-2020", "2021-2024"}),
        (2013, {"2009-2012", "2013-2016"}),
        (2004, {"2004-2008"}),
        (2024, {"2021-2024"}),
    ],
    ids=["mid-band", "band end", "band start", "first year", "last year"],
)
def test_adjacent_bands_credit_the_band_a_year_either_side(year, accepted):
    assert keys.adjacent_bands(year) == accepted


def test_adjacent_scoring_applies_to_the_crossing_item_only():
    """The pre-registered secondary (section 7). B-T7's key year, 2020, closes its band."""
    evidence = {"adjacent_bands": ["2017-2020", "2021-2024"]}
    table = {
        ("B", "T7"): keys.DerivedKey("T7", "B", "crossing", "2017-2020", "rule", evidence),
        ("B", "T3"): keys.DerivedKey("T3", "B", "rank", "Colombia", "rule", {}),
    }
    assert keys.is_correct_adjacent("B", "T7", "2017-2020", table) is True
    assert keys.is_correct_adjacent("B", "T7", "2021-2024", table) is True
    assert keys.is_correct("B", "T7", "2021-2024", table) is False, "strict stays strict"
    assert keys.is_correct_adjacent("B", "T7", "2013-2016", table) is False
    assert keys.is_correct_adjacent("B", "T7", None, table) is False, "a skip is still incorrect"
    assert keys.is_correct_adjacent("B", "T3", "Colombia", table) is None
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
