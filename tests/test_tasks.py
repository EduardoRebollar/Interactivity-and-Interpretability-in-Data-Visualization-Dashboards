"""Integrity of the task set.

Forms A and B must be genuinely isomorphic — same item types, on the same chart types, in the same
order — or the parallel forms design does not hold. And every entity a task names must actually be
chartable, or the task will fail in front of a participant rather than here.
"""

from __future__ import annotations

import re

import pytest

from src import config, figures, runtime_data, tasks
from src.flow import Task

FORMS = ("A", "B")
EXPECTED_KINDS = ("lowest", "rank", "improved", "cell", "threshold", "crossing")
# One affordance per item, each on the chart type it helps most (study-design.md section 4).
EXPECTED_CHARTS = ("line", "bar", "scatter", "heatmap", "map", "line")
# The options are countries for these kinds, years for the line items, counts for the map.
COUNTRY_OPTION_KINDS = ("rank", "improved", "cell")
YEAR_OPTION_KINDS = ("lowest",)


# --- Form equivalence ----------------------------------------------------------------------------


@pytest.mark.parametrize("form", FORMS)
def test_each_form_has_six_scored_tasks(form):
    assert len(tasks.for_form(form)) == 6


def test_both_forms_cover_the_same_types_on_the_same_charts_in_the_same_order():
    """Isomorphic means matched item for matched item, not merely the same set of types."""
    for form in FORMS:
        assert tuple(t.kind for t in tasks.for_form(form)) == EXPECTED_KINDS, form
        assert tuple(t.chart for t in tasks.for_form(form)) == EXPECTED_CHARTS, form


def test_matched_items_share_task_ids_across_forms():
    """T2 in form A must be the counterpart of T2 in form B, so analysis can pair them."""
    a_ids = [t.task_id for t in tasks.for_form("A")]
    b_ids = [t.task_id for t in tasks.for_form("B")]
    assert a_ids == b_ids == ["T1", "T2", "T3", "T4", "T5", "T6"]


def test_matched_items_offer_the_same_number_of_options():
    """An item with more options is harder by construction; that would unbalance the forms."""
    for a, b in zip(tasks.for_form("A"), tasks.for_form("B"), strict=True):
        assert len(a.options) == len(b.options), (
            f"{a.task_id}: {len(a.options)} vs {len(b.options)}"
        )


@pytest.mark.parametrize("form", FORMS)
def test_every_scored_item_offers_six_options(form):
    """The design handoff gives every item six answer tiles (2026-09-25). Chance is one in six on
    every item, so no item is easier to guess than another."""
    for task in tasks.for_form(form):
        assert len(task.options) == 6, f"{form}-{task.task_id}"


def test_the_isolation_item_draws_no_world_line():
    """T1 dropped World in the redesign, in both forms, so both draw eight lines
    (study-design.md section 4)."""
    for form in FORMS:
        (t1,) = [t for t in tasks.for_form(form) if t.task_id == "T1"]
        assert "World" not in t1.entities, form
        assert len(t1.entities) == 8, form


def test_matched_items_draw_the_same_number_of_entities():
    """A chart with more lines, dots, bars or rows is a harder read. The map is the exception:
    each form colours the countries clear of the threshold in its own year (study-design.md
    section 4)."""
    for a, b in zip(tasks.for_form("A"), tasks.for_form("B"), strict=True):
        if a.chart != "map":
            assert len(a.entities) == len(b.entities), a.task_id


def test_forms_never_ask_the_same_question_of_the_same_chart():
    """A repeated item would defeat the whole point of parallel forms.

    The heatmap prompt is word for word the same in both forms, which is what isomorphic means
    once the parameters live on the chart rather than in the wording. What must differ is the
    item: the question together with the data it is asked of.
    """
    for a, b in zip(tasks.for_form("A"), tasks.for_form("B"), strict=True):
        assert (a.prompt, a.entities, a.years) != (b.prompt, b.entities, b.years), a.task_id
        # Counts and year bands are the same options in both forms by design.
        assert a.options != b.options or a.kind in ("threshold", "crossing"), a.task_id


@pytest.mark.parametrize("form", FORMS)
def test_tasks_declare_their_own_form(form):
    assert all(t.form == form for t in tasks.for_form(form))


# --- Answer key must not ship --------------------------------------------------------------------


def test_no_task_carries_a_correct_answer():
    """This module is serialised to the browser. An answer key would be in the page source."""
    for form in FORMS:
        for task in tasks.for_form(form):
            serialised = repr(task).lower()
            assert "correct" not in serialised, f"{task.task_id} may leak an answer key"
    assert not hasattr(tasks, "ANSWERS")
    assert not hasattr(tasks, "ANSWER_KEY")


# --- Every task must actually render --------------------------------------------------------------


def _all_tasks() -> list[Task]:
    return [tasks.PRACTICE, *tasks.for_form("A"), *tasks.for_form("B")]


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_task_names_only_known_entities_and_vaccines(task):
    unknown = [e for e in task.entities if e not in config.ENTITIES]
    assert not unknown, f"{task.task_id} names unknown entities: {unknown}"
    assert task.vaccine in config.VACCINES, f"{task.task_id} uses unknown vaccine {task.vaccine}"
    assert task.chart in figures.CHART_TYPES, task.task_id


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_task_respects_the_series_cap(task):
    """More coloured series than the palette supports would be unreadable. Only lines and dots are
    told apart by colour: bars share one colour; cells and countries use the sequential scale."""
    if task.chart not in ("line", "scatter"):
        return
    coloured = [e for e in task.entities if e != "World"]
    assert len(coloured) <= config.MAX_SERIES, (
        f"{task.task_id} asks for {len(coloured)} coloured series, cap is {config.MAX_SERIES}"
    )


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_each_chart_gets_the_years_it_draws(task):
    """A line spans the whole range; a bar chart and a map show one year; a scatter two; a heatmap
    its columns. The key is derived from the same `years` field the chart is drawn from."""
    expected = {"line": 0, "bar": 1, "map": 1, "scatter": 2}
    if task.chart == "heatmap":
        assert len(task.years) >= 2
    else:
        assert len(task.years) == expected[task.chart], task.task_id
    assert list(task.years) == sorted(set(task.years))
    assert all(config.YEAR_MIN <= year <= config.YEAR_MAX for year in task.years)


@pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)
@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_every_task_builds_a_figure(task):
    """Catch an unchartable task here rather than in front of a participant."""
    figure = figures.task_figure(task)
    one_trace_per_entity = task.chart in ("line", "scatter")
    assert len(figure.data) == (len(task.entities) if one_trace_per_entity else 1)


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_tasks_have_a_prompt_and_options(task):
    assert task.prompt.strip()
    assert len(task.options) >= 2, f"{task.task_id} needs at least two options"
    assert len(set(task.options)) == len(task.options), f"{task.task_id} has duplicate options"


# --- Design-document constraints ------------------------------------------------------------------


def test_no_task_asks_for_an_exact_value():
    """Static has no hover, so an exact-value item would measure hover rather than reading."""
    banned = ("exactly what", "what percentage", "what was the value", "to the nearest")
    for task in _all_tasks():
        lowered = task.prompt.lower()
        assert not any(phrase in lowered for phrase in banned), task.task_id


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_entities_are_alphabetical_with_world_last(task):
    """docs/study-design.md section 5. Entity order sets each line's and dot's colour, and the order
    of bars and rows, so an order chosen by the answer would put the answer in the same place every
    time."""
    countries = [e for e in task.entities if e != "World"]
    assert countries == sorted(countries), task.task_id
    if "World" in task.entities:
        assert task.entities[-1] == "World", task.task_id
        assert task.chart == "line", "World is the line chart's reference and nothing else"


def test_country_options_are_alphabetical_and_on_the_chart():
    """They used to be sorted by effect size, which put the correct answer first in every trend
    item (section 5)."""
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.kind in COUNTRY_OPTION_KINDS:
                assert list(task.options) == sorted(task.options), task.task_id
                assert set(task.options) <= set(task.entities), task.task_id


def test_year_options_are_in_calendar_order_and_on_the_chart():
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.kind in YEAR_OPTION_KINDS:
                years = [int(option) for option in task.options]
                assert years == sorted(years), task.task_id
                assert all(config.YEAR_MIN <= year <= config.YEAR_MAX for year in years)


def test_counts_stay_in_their_natural_order():
    assert tasks.COUNT_OPTIONS == ("0", "1", "2", "3", "4", "5 or more")
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.kind == "threshold":
                assert task.options == tasks.COUNT_OPTIONS, task.task_id


def test_crossing_options_are_the_bands_in_calendar_order():
    """Contiguous, inclusive at both ends, and spanning the data's whole range, so every crossing
    year has exactly one band."""
    spans = [tuple(int(y) for y in band.split("-")) for band in tasks.CROSSING_BANDS]
    assert all(start <= end for start, end in spans)
    assert all(nxt[0] == prev[1] + 1 for prev, nxt in zip(spans, spans[1:], strict=False))
    assert spans[0][0] == config.YEAR_MIN
    assert spans[-1][1] == config.YEAR_MAX
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.kind == "crossing":
                assert task.options == tasks.CROSSING_BANDS, task.task_id


def test_line_items_ask_about_a_country_on_the_chart():
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.kind == "crossing":
                named = re.match(
                    r"(.+)'s coverage became higher than (?:the )?(.+)'s at some point\.",
                    task.prompt,
                )
                assert named, task.task_id
                assert set(named.groups()) <= set(task.entities), task.task_id
            elif task.chart == "line":
                named = re.match(r"Focus on (.+)'s line\.", task.prompt)
                assert named and named.group(1) in task.entities, task.task_id


def test_each_map_prompt_counts_the_countries_it_colours():
    """The map prompt says how many countries are coloured. A pool edited without the prompt would
    tell participants to look for countries that are not there."""
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.chart == "map":
                stated = re.search(r"colours (\d+) countries", task.prompt)
                assert stated and int(stated.group(1)) == len(task.entities), task.task_id
                (year,) = task.years
                assert str(year) in task.prompt, task.task_id


def test_no_task_depends_on_a_continent_in_2024():
    """Continent aggregates have no 2024 data; an item turning on it would be unanswerable."""
    continents = {"Africa", "Asia", "Europe", "North America", "South America", "Oceania"}
    for task in _all_tasks():
        if continents & set(task.entities):
            assert "2024" not in task.prompt and 2024 not in task.years, task.task_id


def test_the_practice_asks_about_no_scored_items_country():
    """The practice once showed Ukraine's collapse, then A-T1 asked for Ukraine's lowest year: the
    practice would have answered it. Its country must not be the subject of any scored prompt."""
    practised = [e for e in tasks.PRACTICE.entities if e != "World"]
    for form in FORMS:
        for task in tasks.for_form(form):
            assert not any(country in task.prompt for country in practised), task.task_id


def test_practice_task_shows_no_missing_data():
    """The practice teaches the interface on a complete line. A gap would need explaining first."""
    rows = runtime_data.load_rows()
    for entity in tasks.PRACTICE.entities:
        series = runtime_data.series(entity, tasks.PRACTICE.vaccine, rows)
        assert all(r.coverage_pct is not None for r in series), f"practice shows a gap in {entity}"


def test_load_scale_is_the_paas_nine_point():
    assert set(tasks.LOAD_ANCHORS) == {1, 9}
    assert tasks.LOAD_PROMPT.strip()


# --- The task screen's copy ---------------------------------------------------------------------


def test_every_item_kind_says_what_to_choose():
    kinds = {task.kind for form in FORMS for task in tasks.for_form(form)} | {"practice"}
    assert kinds <= set(tasks.CHOOSE_PROMPTS)
    assert tasks.CHOOSE_PROMPTS["crossing"] == "Choose a range:"


def test_the_justification_prompt_is_a_sentence_not_a_question():
    """docs/study-redesign.md section 5: the handoff's label ended in a question mark."""
    assert tasks.JUSTIFICATION_PROMPT == "In one sentence, describe why you chose your answer."


# --- The survey and About you (study-design.md section 6) ----------------------------------------


def test_the_survey_is_the_handoffs_three_sections():
    assert list(tasks.LIKERT_ITEMS) == [f"a{n}" for n in range(1, 10)]
    assert list(tasks.CONTROLS_ITEMS) == ["b1", "b2", "b3"]
    assert tasks.COMPARISON_KEYS == ("c1", "c2", "c3")
    assert tasks.LIKERT_POINTS == 7
    assert set(tasks.LIKERT_ANCHORS) == set(range(1, 8)), "every point is labelled"
    assert len(tasks.COMPARISON_OPTIONS) == 3


def test_about_you_is_ten_questions_in_four_sections():
    assert [title for title, _ in tasks.ABOUT_SECTIONS] == [
        "Session setup",
        "Background",
        "Experience with data visualization",
        "Topic familiarity",
    ]
    codes = [q.code for q in tasks.ABOUT_QUESTIONS]
    assert codes == ["A1", "B1", "B2", "B3", "C1", "C2", "C3", "C4", "D1", "D2"]
    assert len({q.key for q in tasks.ABOUT_QUESTIONS}) == 10


@pytest.mark.parametrize("question", tasks.ABOUT_QUESTIONS, ids=lambda q: q.code)
def test_each_about_you_question_is_well_formed(question):
    assert question.text.strip()
    assert question.kind in ("choice", "age", "matrix")
    if question.kind == "age":
        assert question.options == ()
        return
    assert len(set(question.options)) == len(question.options)
    if tasks.PREFER_NOT in question.options:
        assert question.options[-1] == tasks.PREFER_NOT, "Prefer not to say comes last"
    if question.kind == "matrix":
        assert question.rows and len(set(question.rows)) == len(question.rows)
    if tasks.OTHER in question.options:
        assert question.other_key == f"{question.key}_other"
        assert question.other_key in tasks.DEMOGRAPHIC_KEYS
    else:
        assert question.other_key is None


def test_only_the_pointer_question_lacks_prefer_not_to_say():
    """The handoff offers no "Prefer not to say" for the pointer device, which identifies no one.
    Age offers it as a checkbox beside the number box, not as an option."""
    lacking = [
        q.code
        for q in tasks.ABOUT_QUESTIONS
        if q.kind != "age" and tasks.PREFER_NOT not in q.options
    ]
    assert lacking == ["A1"]
