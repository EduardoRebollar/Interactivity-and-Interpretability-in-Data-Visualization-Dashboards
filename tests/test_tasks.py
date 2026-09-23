"""Integrity of the task set.

Forms A and B must be genuinely isomorphic — same types, same order, same shape — or the parallel
forms design does not hold. And every entity a task names must actually be chartable, or the task
will fail in front of a participant rather than here.
"""

from __future__ import annotations

import pytest

from src import config, figures, runtime_data, tasks
from src.flow import Task

FORMS = ("A", "B")
EXPECTED_KINDS = ("reference", "trend", "trend", "crossing", "crossing", "gap")


# --- Form equivalence ----------------------------------------------------------------------------


@pytest.mark.parametrize("form", FORMS)
def test_each_form_has_six_scored_tasks(form):
    assert len(tasks.for_form(form)) == 6


def test_both_forms_cover_the_same_types_in_the_same_order():
    """Isomorphic means matched item for matched item, not merely the same set of types."""
    for form in FORMS:
        assert tuple(t.kind for t in tasks.for_form(form)) == EXPECTED_KINDS, form


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


def test_forms_do_not_reuse_prompts():
    """A repeated prompt would defeat the whole point of parallel forms."""
    a_prompts = {t.prompt for t in tasks.for_form("A")}
    b_prompts = {t.prompt for t in tasks.for_form("B")}
    assert not (a_prompts & b_prompts)


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


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_task_respects_the_series_cap(task):
    """More coloured series than the palette supports would be unreadable."""
    coloured = [e for e in task.entities if e != "World"]
    assert len(coloured) <= config.MAX_SERIES, (
        f"{task.task_id} asks for {len(coloured)} coloured series, cap is {config.MAX_SERIES}"
    )


@pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)
@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_every_task_builds_a_figure(task):
    """Catch an unchartable task here rather than in front of a participant."""
    figure = figures.build_figure(list(task.entities), task.vaccine)
    assert len(figure.data) == len(task.entities)


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
    """docs/study-design.md section 5. Entity order sets each line's colour, so an order chosen by
    the answer puts the answer on the same colour every time."""
    countries = [e for e in task.entities if e != "World"]
    assert countries == sorted(countries), task.task_id
    if "World" in task.entities:
        assert task.entities[-1] == "World", task.task_id


def test_country_options_are_alphabetical():
    """They used to be sorted by effect size, which put the correct answer first in every trend
    item (section 5)."""
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.kind == "trend":
                assert list(task.options) == sorted(task.options), task.task_id
                assert set(task.options) == set(task.entities) - {"World"}, task.task_id


def test_ordinal_options_stay_in_their_natural_order():
    assert list(tasks.CROSSING_BANDS) == sorted(tasks.CROSSING_BANDS)
    assert tasks.COUNT_OPTIONS == ("0", "1", "2", "3", "4 or more")


def test_crossing_options_are_bands_not_years():
    """Same reason: a precise crossing year is not readable without hover."""
    for form in FORMS:
        for task in tasks.for_form(form):
            if task.kind == "crossing":
                assert all("-" in option for option in task.options), task.task_id


def test_no_task_depends_on_a_continent_in_2024():
    """Continent aggregates have no 2024 data; an item turning on it would be unanswerable."""
    continents = {"Africa", "Asia", "Europe", "North America", "South America", "Oceania"}
    for task in _all_tasks():
        if continents & set(task.entities):
            assert "2024" not in task.prompt, f"{task.task_id} mixes a continent with 2024"


def test_practice_task_shows_no_missing_data():
    """The practice item must not teach gap reasoning, or it contaminates T6."""
    rows = runtime_data.load_rows()
    for entity in tasks.PRACTICE.entities:
        series = runtime_data.series(entity, tasks.PRACTICE.vaccine, rows)
        assert all(r.coverage_pct is not None for r in series), (
            f"practice task shows a gap in {entity}, which would prime participants for T6"
        )


def test_load_scale_is_the_paas_nine_point():
    assert set(tasks.LOAD_ANCHORS) == {1, 9}
    assert tasks.LOAD_PROMPT.strip()
