"""Tests for the session as a participant actually experiences it.

This file exists because the participant-facing layer shipped with no coverage at all and had never
been run. Everything it asserts is something that was, or could silently become, wrong in a way no
other test in the suite would notice:

- a `Stage` with no screen,
- a callback output bound to an id that is not on the screen that triggers it,
- a condition whose log session never gets a `session_end`,
- an event attributed to the wrong condition.

`src.app.step` is the whole session state machine and is driven here directly, with the logger
pointed at a tmp_path so a test run never touches `data/study_logs/`.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter

import pytest
from dash import no_update

from src import app, db, layout, runtime_data, tasks
from src.flow import SessionState, Stage
from src.logging import SCHEMA_VERSION

pytestmark = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)

ANSWER_KWARGS = {"answer": "1", "justification": "because the line is higher"}


# --- Helpers --------------------------------------------------------------------------------------


def _ids(component) -> set[str]:
    """Every component id anywhere in a rendered tree."""
    found: set[str] = set()

    def walk(node) -> None:
        component_id = getattr(node, "id", None)
        if isinstance(component_id, str):
            found.add(component_id)
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                walk(child)
        elif children is not None:
            walk(children)

    walk(component)
    return found


def _state(stage: Stage, **kwargs) -> SessionState:
    """A session parked at `stage` with an assignment already made."""
    base = {
        "stage": stage.value,
        "participant_id": "P01",
        "first_condition": "static",
        "first_form": "A",
        "condition_index": 0,
        "task_index": 0,
    }
    return SessionState.from_dict({**base, **kwargs})


def _events(log_dir) -> list[dict]:
    """Every logged record, in file-then-line order."""
    records = []
    for path in sorted(log_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def _run_session(log_dir, participant_id: str = "P01") -> list[dict]:
    """Drive one complete session from consent to the final screen. Returns the logged events."""
    session, log = None, None

    def click(trigger, **kwargs):
        nonlocal session, log
        session, log, screen, error = app.step(trigger, session, log, log_dir=log_dir, **kwargs)
        assert error == "", f"{trigger} was refused: {error}"
        assert session is not no_update
        return screen

    click("consent-button")
    click("participant-button", participant_id=participant_id)

    for condition in range(2):
        click("begin-button")
        if condition == 0:
            # The practice item, which uses the same screen as a scored task.
            click("submit-clock", **ANSWER_KWARGS, duration_ms=1234.5)
        for _ in range(len(tasks.for_form("A"))):
            click("submit-clock", **ANSWER_KWARGS, duration_ms=1000.0)
        click("load-button", load=5)
        if condition == 0:
            click("resume-button")

    assert SessionState.from_dict(session).stage is Stage.COMPLETE
    return _events(log_dir)


# --- Every stage renders --------------------------------------------------------------------------


@pytest.mark.parametrize("stage", list(Stage))
@pytest.mark.parametrize("condition", ["static", "interactive"])
@pytest.mark.parametrize("form", ["A", "B"])
def test_every_stage_has_a_screen(stage, condition, form):
    """`render` must be total over Stage. Adding a stage without a screen fails here, not live."""
    screen = app.render(_state(stage, first_condition=condition, first_form=form))
    assert screen is not None


def test_every_stage_carries_the_error_slot():
    """The callback writes `flow-error` on every screen, so every screen must have it."""
    for stage in Stage:
        assert "flow-error" in _ids(app.render(_state(stage))), f"{stage.value} has no error slot"


@pytest.mark.parametrize(
    ("stage", "trigger_id"),
    [
        (Stage.CONSENT, "consent-button"),
        (Stage.PARTICIPANT_ID, "participant-button"),
        (Stage.INSTRUCTIONS, "begin-button"),
        (Stage.PRACTICE, "submit-button"),
        (Stage.TASK, "submit-button"),
        (Stage.LOAD, "load-button"),
        (Stage.BREAK, "resume-button"),
    ],
)
def test_each_screen_carries_the_control_that_advances_it(stage, trigger_id):
    """A screen with no way forward is a dead end; a trigger with no screen never fires."""
    assert trigger_id in _ids(app.render(_state(stage)))


def test_the_break_does_not_reuse_the_begin_button():
    """Sharing an id is what let the break skip the second condition's instructions."""
    assert "begin-button" not in _ids(app.render(_state(Stage.BREAK)))


def test_inputs_the_callback_reads_exist_on_the_screens_that_supply_them():
    assert "participant-input" in _ids(app.render(_state(Stage.PARTICIPANT_ID)))
    assert "load-input" in _ids(app.render(_state(Stage.LOAD)))
    for stage in (Stage.PRACTICE, Stage.TASK):
        ids = _ids(app.render(_state(stage)))
        assert {"answer-input", "justification-input"} <= ids


# --- Practice and the second condition's instructions ---------------------------------------------


def test_practice_renders_the_practice_item():
    screen = app.render(_state(Stage.PRACTICE))
    assert "chart" in _ids(screen)
    assert "Practice" in json.dumps(screen.to_plotly_json(), default=str)


def test_practice_is_offered_before_the_first_condition_only():
    first = app.render(_state(Stage.INSTRUCTIONS, condition_index=0))
    second = app.render(_state(Stage.INSTRUCTIONS, condition_index=1))
    assert "practice" in json.dumps(first.to_plotly_json(), default=str).lower()
    assert "practice" not in json.dumps(second.to_plotly_json(), default=str).lower()


def test_the_second_conditions_instructions_describe_the_condition_about_to_start():
    """Whoever gets interactive second must be told the controls exist."""
    screen = app.render(_state(Stage.INSTRUCTIONS, first_condition="static", condition_index=1))
    text = json.dumps(screen.to_plotly_json(), default=str)
    assert "hover" in text, "the second condition is interactive; its affordances must be described"


# --- A whole session ------------------------------------------------------------------------------


def test_a_full_session_runs_end_to_end(tmp_path):
    events = _run_session(tmp_path)
    assert events, "a complete session logged nothing"
    assert {e["schema_version"] for e in events} == {SCHEMA_VERSION}


def test_both_conditions_are_logged_and_both_are_closed(tmp_path):
    """Closing only at COMPLETE left one session per participant with no session_end."""
    events = _run_session(tmp_path)
    sessions = {e["session_id"] for e in events}
    assert len(sessions) == 2, "one log session per condition"

    for session_id in sessions:
        names = [e["event"] for e in events if e["session_id"] == session_id]
        assert names[0] == "session_start"
        assert names[-1] == "session_end", "every condition must close its session"
        assert names.count("condition_start") == 1
        assert names.count("condition_end") == 1
        assert names.count("load_rating") == 1


def test_a_session_covers_both_conditions_and_both_forms(tmp_path):
    events = _run_session(tmp_path)
    assert {e["condition"] for e in events} == {"static", "interactive"}
    assert {e["form"] for e in events} == {"A", "B"}
    assert {e["condition_order"] for e in events} == {1, 2}


def test_the_load_rating_is_attributed_to_the_condition_it_rates(tmp_path):
    """The rating is about the half just finished. Misattributing it inverts the RQ3 result."""
    events = _run_session(tmp_path)
    ratings = [e for e in events if e["event"] == "load_rating"]
    assert len(ratings) == 2

    for rating in ratings:
        same_session = [
            e
            for e in events
            if e["session_id"] == rating["session_id"] and e["event"] == "answer_submit"
        ]
        assert same_session, "a rating with no answers before it is attributed to the wrong session"
        assert {e["condition"] for e in same_session} == {rating["condition"]}
        assert {e["condition_order"] for e in same_session} == {rating["condition_order"]}


def test_every_scored_task_is_answered_once_per_condition(tmp_path):
    events = _run_session(tmp_path)
    answers = [e for e in events if e["event"] == "answer_submit"]
    # Six scored items per condition, plus the single unscored practice item.
    assert len(answers) == 2 * len(tasks.for_form("A")) + 1

    scored = Counter(e["task_id"] for e in answers if e["task_id"] != tasks.PRACTICE.task_id)
    assert set(scored) == {t.task_id for t in tasks.for_form("A")}
    assert set(scored.values()) == {2}, "each item answered once per condition"


def test_the_practice_answer_is_recorded_and_marked_unscored(tmp_path):
    """Kept for its timing, but it must be identifiable so analysis can drop it."""
    events = _run_session(tmp_path)
    practice = [e for e in events if e["task_id"] == tasks.PRACTICE.task_id]
    assert [e["event"] for e in practice] == ["task_start", "answer_submit", "task_end"]
    assert {e["condition_order"] for e in practice} == {1}, "practice is first condition only"


def test_every_task_is_bracketed_by_a_start_and_an_end(tmp_path):
    """The span is what places an interaction event on the task it happened during."""
    events = _run_session(tmp_path)
    spans = [e for e in events if e["event"] in ("task_start", "task_end")]
    assert spans, "task_start and task_end are declared events and must actually be emitted"

    open_task = None
    for event in spans:
        if event["event"] == "task_start":
            assert open_task is None, f"{event['task_id']} started while {open_task} was open"
            open_task = event["task_id"]
        else:
            assert open_task == event["task_id"], "a task ended that was not the one open"
            open_task = None
    assert open_task is None, "a session ended with a task still open"


def test_task_end_carries_the_browser_measured_duration(tmp_path):
    events = _run_session(tmp_path)
    ends = [e for e in events if e["event"] == "task_end"]
    assert ends
    for event in ends:
        assert event["payload"]["duration_ms"] is not None
        assert event["task_elapsed_ms"] == event["payload"]["duration_ms"]


def test_answers_carry_their_justification_and_browser_timing(tmp_path):
    events = _run_session(tmp_path)
    for event in (e for e in events if e["event"] == "answer_submit"):
        assert event["payload"]["justification"] == ANSWER_KWARGS["justification"]
        assert event["payload"]["duration_ms"] is not None
        assert event["client_elapsed_ms"] is None or event["client_elapsed_ms"] >= 0


def test_no_interaction_events_are_logged_before_the_controls_exist(tmp_path):
    """Guards the claim in the other direction: unbuilt affordances must log nothing."""
    events = _run_session(tmp_path)
    interaction = {"filter_change", "sort_change", "line_isolate"}
    assert not (interaction & {e["event"] for e in events})


# --- The interactive controls ---------------------------------------------------------------------


def _task_state():
    """A participant partway through the interactive condition, on the first scored task."""
    return _state(Stage.TASK, first_condition="interactive").to_dict()


def _interact(triggered, tmp_path, control_state=None, **kwargs):
    """Run one control interaction and return (result tuple, events logged by it)."""
    log_state = {"session_id": str(uuid.uuid4())}
    result = app.control_step(
        triggered, _task_state(), log_state, control_state, log_dir=tmp_path, **kwargs
    )
    return result, [e for e in _events(tmp_path) if e["event"] != "session_start"]


def _first_task():
    return tasks.for_form("A")[0]


def test_filtering_hides_a_series_and_logs_it(tmp_path):
    keep = [e for e in layout.filterable(list(_first_task().entities)) if e != "Nigeria"]
    (figure, options, value, control), events = _interact(
        "entity-filter.value", tmp_path, selected=keep
    )

    assert [e["event"] for e in events] == ["filter_change"]
    payload = events[0]["payload"]
    # The keys are declared in src/logging.py; analysis reads them by name.
    assert set(payload) == {"control", "action", "value", "previous"}
    assert payload["action"] == "hide"
    assert "Nigeria" not in payload["value"]
    assert "Nigeria" in payload["previous"]

    assert control["selected"] == keep
    assert {t.name for t in figure.data if t.visible} == set(keep) | {"World"}
    assert value == keep
    assert [o["value"] for o in options] == layout.filterable(list(_first_task().entities))


def test_the_filter_cannot_empty_the_chart(tmp_path):
    """build_figure refuses an empty entity list; the control must refuse before it gets there."""
    result, events = _interact("entity-filter.value", tmp_path, selected=[])
    assert result == (no_update,) * 4, "unchecking the last series keeps the previous view"
    assert events == [], "refusing to empty the chart is not a participant action to log"


def test_the_world_reference_is_never_filterable():
    """Several items ask about the dashed line; it must not be possible to switch it off."""
    for form in ("A", "B"):
        for task in tasks.for_form(form):
            assert "World" not in layout.filterable(list(task.entities))


def test_the_world_reference_stays_on_the_chart_when_countries_are_hidden(tmp_path):
    (figure, _options, _value, _ctl), _events = _interact(
        "entity-filter.value", tmp_path, selected=["Brazil"]
    )
    assert {t.name for t in figure.data if t.visible} == {"Brazil", "World"}


def test_sorting_reorders_the_control_list_and_logs_it(tmp_path):
    (figure, options, _value, control), events = _interact(
        "entity-sort.value", tmp_path, sort_key="coverage"
    )

    assert [e["event"] for e in events] == ["sort_change"]
    assert set(events[0]["payload"]) == {"key", "direction"}
    assert events[0]["payload"] == {"key": "coverage", "direction": "desc"}
    assert control["sort"] == "coverage"

    ordered = [o["value"] for o in options]
    values = layout.latest_values(ordered, _first_task().vaccine)
    assert ordered == sorted(ordered, key=lambda e: -(values[e] or 0))
    assert all("%" in o["label"] for o in options), (
        "sorting by coverage must show what it sorted on"
    )


def test_sorting_does_not_change_which_series_are_shown(tmp_path):
    """The chart is untouched by sorting; only the control list reorders."""
    (figure, _options, _value, _ctl), _events = _interact(
        "entity-sort.value", tmp_path, sort_key="coverage"
    )
    assert all(trace.visible for trace in figure.data)


def test_clicking_a_line_isolates_it_and_logs_it(tmp_path):
    task = _first_task()
    (figure, _options, _value, control), events = _interact(
        "chart.clickData", tmp_path, click_data={"points": [{"curveNumber": 0}]}
    )

    assert [e["event"] for e in events] == ["line_isolate"]
    assert set(events[0]["payload"]) == {"entity", "isolated"}
    assert events[0]["payload"] == {"entity": task.entities[0], "isolated": True}
    assert control["isolated"] == task.entities[0]
    assert {t.name for t in figure.data if t.visible} == {task.entities[0], "World"}


def test_clicking_an_isolated_line_again_releases_it(tmp_path):
    task = _first_task()
    isolated = {"selected": layout.filterable(list(task.entities)), "isolated": task.entities[0]}
    (figure, _options, _value, control), events = _interact(
        "chart.clickData",
        tmp_path,
        control_state=isolated,
        click_data={"points": [{"curveNumber": 0}]},
    )
    assert events[0]["payload"] == {"entity": task.entities[0], "isolated": False}
    assert control["isolated"] is None
    assert all(trace.visible for trace in figure.data)


def test_clicking_the_world_reference_does_nothing(tmp_path):
    task = _first_task()
    world_index = list(task.entities).index("World")
    result, events = _interact(
        "chart.clickData", tmp_path, click_data={"points": [{"curveNumber": world_index}]}
    )
    assert result == (no_update,) * 4
    assert events == []


def test_show_all_restores_everything_and_logs_it(tmp_path):
    task = _first_task()
    narrowed = {"selected": ["Brazil"], "isolated": "Nigeria"}
    (figure, _options, _value, control), events = _interact(
        "reset-view.n_clicks", tmp_path, control_state=narrowed
    )

    assert [e["event"] for e in events] == ["filter_change"]
    assert events[0]["payload"]["control"] == "reset-view"
    assert control["isolated"] is None
    assert control["selected"] == layout.filterable(list(task.entities))
    assert all(trace.visible for trace in figure.data)


def test_zoom_and_pan_are_logged_as_a_view_change(tmp_path):
    _result, events = _interact(
        "chart.relayoutData",
        tmp_path,
        relayout={"xaxis.range[0]": 2005.2, "xaxis.range[1]": 2015.8},
    )
    assert [e["event"] for e in events] == ["view_change"]
    assert set(events[0]["payload"]) == {"control", "value", "previous"}


def test_zooming_after_a_click_is_not_read_as_a_second_click(tmp_path):
    """Regression: `clickData` stays set on the component after a click.

    A zoom therefore arrives with the previous click still in `click_data`. Dispatching on the
    component id alone read that as the participant clicking the same line again, which both logged
    a phantom `line_isolate` and silently un-isolated their chart. The prop id separates them.
    """
    task = _first_task()
    already_isolated = {
        "selected": layout.filterable(list(task.entities)),
        "isolated": task.entities[0],
    }
    (figure, _options, _value, control), events = _interact(
        "chart.relayoutData",
        tmp_path,
        control_state=already_isolated,
        # Exactly what Dash sends: the stale click alongside the new zoom.
        click_data={"points": [{"curveNumber": 0}]},
        relayout={"xaxis.range[0]": 2005.0, "xaxis.range[1]": 2015.0},
    )

    assert [e["event"] for e in events] == ["view_change"]
    assert control["isolated"] == task.entities[0], "a zoom must not release the isolation"
    assert {t.name for t in figure.data if t.visible} == {task.entities[0], "World"}


def test_a_render_time_relayout_is_not_logged_as_an_interaction(tmp_path):
    """Plotly sends relayout on resize and on first paint. Neither is a participant action."""
    result, events = _interact("chart.relayoutData", tmp_path, relayout={"autosize": True})
    assert result == (no_update,) * 4
    assert events == []


def test_re_rendering_a_task_does_not_log_a_phantom_filter_change(tmp_path):
    """Dash fires input callbacks when a component is recreated, which happens every task."""
    options = layout.filterable(list(_first_task().entities))
    result, events = _interact(
        "entity-filter.value", tmp_path, control_state={"selected": options}, selected=options
    )
    assert result == (no_update,) * 4
    assert events == []


def test_every_interaction_event_is_attributed_to_the_task_it_happened_on(tmp_path):
    _result, events = _interact("entity-filter.value", tmp_path, selected=["Brazil"])
    assert events[0]["task_id"] == _first_task().task_id
    assert events[0]["condition"] == "interactive"


def test_the_controls_do_nothing_off_a_task_screen(tmp_path):
    """No chart is showing at consent or the break, so nothing can be interacted with."""
    for stage in (Stage.CONSENT, Stage.INSTRUCTIONS, Stage.LOAD, Stage.BREAK, Stage.COMPLETE):
        result = app.control_step(
            "entity-filter.value",
            _state(stage, first_condition="interactive").to_dict(),
            {},
            None,
            selected=["Brazil"],
            log_dir=tmp_path,
        )
        assert result == (no_update,) * 4, f"{stage.value} has no chart to control"


def test_a_stale_control_state_from_the_previous_task_is_discarded(tmp_path):
    """Entities from the previous task must not leak into this one's filter or chart."""
    stale = {"selected": ["Ukraine", "Pakistan"], "isolated": "Ukraine"}
    (figure, _options, _value, control), _events = _interact(
        "entity-filter.value", tmp_path, control_state=stale, selected=["Brazil", "India"]
    )
    assert control["isolated"] is None, "an isolation on an absent series must not survive"
    assert control["selected"] == ["Brazil", "India"]
    assert {t.name for t in figure.data if t.visible} == {"Brazil", "India", "World"}


# --- Validation refuses rather than advancing -----------------------------------------------------


@pytest.mark.parametrize(
    ("stage", "trigger", "kwargs", "expected"),
    [
        (Stage.PARTICIPANT_ID, "participant-button", {"participant_id": "  "}, "participant ID"),
        (Stage.TASK, "submit-clock", {"justification": "x"}, "choose an answer"),
        (Stage.TASK, "submit-clock", {"answer": "1", "justification": " "}, "how you decided"),
        (Stage.PRACTICE, "submit-clock", {"justification": "x"}, "choose an answer"),
        (Stage.LOAD, "load-button", {"load": None}, "choose a number"),
    ],
)
def test_incomplete_input_is_refused_without_advancing(stage, trigger, kwargs, expected, tmp_path):
    session, log, screen, error = app.step(
        trigger, _state(stage).to_dict(), {}, log_dir=tmp_path, **kwargs
    )
    assert expected in error
    assert session is no_update, "a refused step must not advance the session"
    assert screen is no_update
    assert not list(tmp_path.glob("*.jsonl")), "a refused step must not log an answer"


def test_an_invalid_transition_becomes_a_message_not_a_crash(tmp_path):
    """A participant who double-clicks, or resumes a stale tab, must see a message."""
    session, _log, _screen, error = app.step(
        "consent-button", _state(Stage.TASK).to_dict(), {}, log_dir=tmp_path
    )
    assert "Expected stage consent" in error
    assert session is no_update


# --- Timing ---------------------------------------------------------------------------------------


def test_elapsed_subtracts_two_browser_timestamps():
    assert app._elapsed(1000.0, 2500.5) == 1500.5


@pytest.mark.parametrize(("started", "submitted"), [(None, 1.0), (1.0, None), (None, None)])
def test_elapsed_is_none_when_a_timestamp_is_missing(started, submitted):
    """Absent must stay visibly absent; recording it as zero would corrupt a dependent variable."""
    assert app._elapsed(started, submitted) is None


def test_elapsed_rejects_a_clock_that_ran_backwards():
    """performance.now() is monotonic, so a negative span means the stores are out of step."""
    assert app._elapsed(2000.0, 1000.0) is None


# --- Assignment without a database ----------------------------------------------------------------


def test_assignment_is_deterministic_without_a_database():
    """Local walkthroughs must be reproducible for a given participant ID."""
    assert app._assign("P07") == app._assign("P07")


def test_assignment_uses_every_cell():
    cells = {app._assign(f"P{n:02d}") for n in range(40)}
    assert cells == set(db.ASSIGNMENTS.values())


# --- Layout helpers used by the task screen -------------------------------------------------------


def test_gap_note_names_the_series_with_unreported_years():
    """Static participants have no tooltip, so this caption is the only channel for a break."""
    note = layout.gap_note(["United Kingdom", "World"], "HepB3")
    assert note is not None
    text = note.children
    assert "United Kingdom" in text
    assert "2000-2018" in text
    assert "not the same as zero coverage" in text


def test_gap_note_is_absent_when_nothing_is_missing():
    assert layout.gap_note(["Brazil", "World"], "DTP3") is None


def test_the_practice_item_shows_no_gap_note():
    """It must not teach gap reasoning, which is what T6 measures."""
    assert layout.gap_note(list(tasks.PRACTICE.entities), tasks.PRACTICE.vaccine) is None


@pytest.mark.parametrize(
    ("years", "expected"),
    [
        ([2000], "2000"),
        ([2000, 2001, 2002], "2000-2002"),
        ([2000, 2001, 2002, 2005], "2000-2002, 2005"),
        ([2005, 2000, 2001], "2000-2001, 2005"),
        ([], ""),
    ],
)
def test_year_ranges_compress_runs(years, expected):
    assert layout._year_ranges(years) == expected


# --- The app itself -------------------------------------------------------------------------------


def test_the_app_builds_and_registers_its_callbacks():
    instance = app.create_app()
    assert instance.layout is not None
    assert instance.callback_map, "no callbacks registered"


def test_the_stores_the_callback_reads_are_in_the_base_layout():
    """`step` reads these every click; a missing store is a silent None, not an error."""
    assert {"session-state", "log-state", "task-clock", "submit-clock", "page"} <= _ids(
        app.create_app().layout
    )


def test_the_deployment_entrypoint_is_a_flask_instance():
    """Vercel resolves `src.app:server` and expects Flask, not the dash.Dash named `app`."""
    from flask import Flask

    assert isinstance(app.server, Flask)
