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
from dash.exceptions import PreventUpdate

from src import app, consent, db, figures, flow, layout, runtime_data, tasks
from src.flow import SessionState, Stage
from src.logging import SCHEMA_VERSION

pytestmark = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)

CONSENTED_AT = "2026-09-16T10:00:00.000Z"
ANSWER_KWARGS = {"answer": "1", "justification": "because the line is higher"}
# A drawn signature: two strokes, comfortably over consent.MIN_POINTS.
SIGNATURE = [[[10 + 4 * i, 40 + (i % 3)] for i in range(12)], [[30, 60], [80, 64], [120, 58]]]
DEMOGRAPHICS = {
    "age_range": "18–24",
    "field": "Engineering",
    "chart_frequency": None,
    "dashboard_familiarity": "Slightly familiar",
}
SURVEY_KWARGS = {"load": 5, "survey": {"clarity": 6, "ease_of_use": 5, "confidence": 4}}


def _consent_kwargs(**overrides) -> dict:
    """What the consent callback hands `step`: the browser time and a complete signed record."""
    fields = {"name": "Test Participant", "date": "2026-09-16", "signature": SIGNATURE}
    fields.update(overrides)
    record = consent.build_record(
        CONSENTED_AT,
        fields["name"],
        fields["date"],
        fields["signature"],
        fields.get("paper", False),
    )
    return {"consented_at": CONSENTED_AT, "consent_record": record}


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
        session, log, screen, error, _spool = app.step(
            trigger, session, log, log_dir=log_dir, **kwargs
        )
        assert error == "", f"{trigger} was refused: {error}"
        assert session is not no_update
        return screen

    click("consent-clock", **_consent_kwargs())
    click("participant-button", participant_id=participant_id)
    click("demographics-clock", demographics=DEMOGRAPHICS)

    for condition in range(2):
        click("begin-button")
        if condition == 0:
            # The practice item, which uses the same screen as a scored task.
            click("submit-clock", **ANSWER_KWARGS, duration_ms=1234.5)
        for _ in range(len(tasks.for_form("A"))):
            click("submit-clock", **ANSWER_KWARGS, duration_ms=1000.0)
        click("survey-clock", **SURVEY_KWARGS)
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
        (Stage.CONSENT, "decline-button"),
        (Stage.DECLINED, "reconsider-button"),
        (Stage.PARTICIPANT_ID, "participant-button"),
        (Stage.DEMOGRAPHICS, "demographics-button"),
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


def _every_screen():
    """Every distinct screen a participant can see: each stage, in each condition, in each half --
    and, at the task stage, every item of both forms. The bar chart and the map carry controls no
    other screen has, so a check that saw only the first task would never see their callbacks."""
    for stage in Stage:
        for condition in ("static", "interactive"):
            for index in (0, 1):
                forms = ("A", "B") if stage is Stage.TASK else ("A",)
                for form in forms:
                    positions = range(len(tasks.for_form(form))) if stage is Stage.TASK else (0,)
                    for position in positions:
                        state = _state(
                            stage,
                            first_condition=condition,
                            first_form=form,
                            condition_index=index,
                            task_index=position,
                        )
                        shown = "interactive" if flow.is_interactive(state) else "static"
                        yield f"{stage.value}/{shown}/{index}/{form}{position}", app.render(state)


def test_no_callback_is_dead_on_the_screens_that_trigger_it():
    """Dash's browser renderer will not run a callback whose Inputs are only partly on the page.

    It throws a ReferenceError to the console and sends nothing, so the button simply does nothing.
    One callback wired to every screen's button was dead on every screen -- "I agree" did nothing
    in a browser -- while every test calling `step` directly passed. This checks the rule itself:
    on any screen showing one of a callback's Inputs, all its Inputs and States must be present.
    """
    instance = app.create_app()
    base = _ids(instance.layout)
    problems = []
    for name, screen in _every_screen():
        present = base | _ids(screen)
        for key, callback in instance.callback_map.items():
            inputs = {i["id"] for i in callback["inputs"]}
            states = {s["id"] for s in callback["state"]}
            if not (inputs - base) & present:
                continue  # nothing on this screen can trigger it
            missing = (inputs | states) - present
            if missing:
                problems.append(f"{name}: {key} is missing {sorted(missing)}")
    assert not problems, "\n".join(problems)


def test_button_callbacks_ignore_the_click_count_of_a_freshly_rendered_button():
    """Dash fires a callback when its Input is inserted with a new screen, whatever
    `prevent_initial_call` says. Unguarded, the instructions screen pressed its own Begin button."""
    triggers = {
        "participant-button",
        "begin-button",
        "resume-button",
        "decline-button",
        "reconsider-button",
        "demographics-clock",
        "survey-clock",
    }
    guarded = set()
    for callback in app.create_app().callback_map.values():
        inputs = [i["id"] for i in callback["inputs"]]
        if "callback" not in callback or not inputs or inputs[0] not in triggers:
            continue  # clientside callbacks have no Python function, and guard themselves in JS
        # A fresh screen: n_clicks 0, any other trigger (Enter's n_submit) and every State unset.
        # It must change nothing at all.
        args = [0] + [None] * (len(inputs) - 1 + len(callback["state"]))
        with pytest.raises(PreventUpdate):
            callback["callback"].__wrapped__(*args)
        guarded.add(inputs[0])
    assert guarded == triggers


def _participant_callback():
    for callback in app.create_app().callback_map.values():
        inputs = [i["id"] for i in callback["inputs"]]
        if "callback" in callback and inputs[:1] == ["participant-button"]:
            return callback
    raise AssertionError("no participant callback")


def test_enter_in_the_id_box_submits_it(monkeypatch):
    """Enter did nothing, and a participant got no response until they found the button."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    callback = _participant_callback()
    assert {"id": "participant-input", "property": "n_submit"} in callback["inputs"]
    at_id_screen = _state(Stage.PARTICIPANT_ID, participant_id=None).to_dict()
    # Enter pressed once, Continue never clicked.
    session, _log, _screen, error, _spool = callback["callback"].__wrapped__(
        0, 1, "P01", at_id_screen, None, None
    )
    assert error == ""
    assert SessionState.from_dict(session).stage is Stage.DEMOGRAPHICS


def test_the_id_screen_does_not_promise_a_resume_that_does_not_exist():
    text = json.dumps(app.render(_state(Stage.PARTICIPANT_ID)).to_plotly_json(), default=str)
    assert "left off" not in text
    assert "one sitting" in text


def test_the_chart_holds_its_height_before_plotly_has_loaded():
    """dcc.Graph renders at zero height until Plotly arrives; the page jumped 520 px under a click.
    The container must reserve the height in both conditions, identically."""
    task = tasks.for_form("A")[0]
    containers = []
    for interactive in (False, True):
        wrapper = layout.chart(list(task.entities), task.vaccine, interactive)
        assert wrapper.children.id == "chart"
        containers.append(wrapper.style)
    assert containers[0] == containers[1] == {"height": f"{layout.config.CHART_HEIGHT}px"}


def test_inputs_the_callback_reads_exist_on_the_screens_that_supply_them():
    assert "participant-input" in _ids(app.render(_state(Stage.PARTICIPANT_ID)))
    load = _ids(app.render(_state(Stage.LOAD)))
    assert {"load-input", *(f"likert-{key}" for key in tasks.LIKERT_ITEMS)} <= load
    demographics = _ids(app.render(_state(Stage.DEMOGRAPHICS)))
    assert {f"demo-{key}" for key in tasks.DEMOGRAPHIC_ITEMS} <= demographics
    consent_ids = _ids(app.render(_state(Stage.CONSENT)))
    assert {"consent-name", "consent-date", "consent-paper", "signature-pad"} <= consent_ids
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
    """Run one control interaction and return (the four chart outputs, events logged by it).

    The fifth output, the spool, is `no_update` whenever the database is healthy; the tests that
    care about it call `control_step` directly.
    """
    log_state = {"session_id": str(uuid.uuid4())}
    result = app.control_step(
        triggered, _task_state(), log_state, control_state, log_dir=tmp_path, **kwargs
    )
    assert result[4] is no_update, "a healthy write must not touch the spool store"
    return result[:4], [e for e in _events(tmp_path) if e["event"] != "session_start"]


def _first_task():
    return tasks.for_form("A")[0]


def _view(**kwargs):
    """A control state belonging to the task `_task_state` is on: first half, first scored task."""
    return {"screen": f"0/{_first_task().task_id}", **kwargs}


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
        "entity-filter.value", tmp_path, selected=["China"]
    )
    assert {t.name for t in figure.data if t.visible} == {"China", "World"}


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
    isolated = _view(selected=layout.filterable(list(task.entities)), isolated=task.entities[0])
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
    narrowed = _view(selected=["China"], isolated="Nigeria")
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
    already_isolated = _view(
        selected=layout.filterable(list(task.entities)), isolated=task.entities[0]
    )
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
        "entity-filter.value", tmp_path, control_state=_view(selected=options), selected=options
    )
    assert result == (no_update,) * 4
    assert events == []


def test_every_interaction_event_is_attributed_to_the_task_it_happened_on(tmp_path):
    _result, events = _interact("entity-filter.value", tmp_path, selected=["China"])
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
            selected=["China"],
            log_dir=tmp_path,
        )
        assert result == (no_update,) * 5, f"{stage.value} has no chart to control"


def test_a_stale_control_state_from_the_previous_task_is_discarded(tmp_path):
    """Entities from the previous task must not leak into this one's filter or chart."""
    stale = {"selected": ["Ukraine", "Pakistan"], "isolated": "Ukraine"}
    (figure, _options, _value, control), _events = _interact(
        "entity-filter.value", tmp_path, control_state=stale, selected=["China", "India"]
    )
    assert control["isolated"] is None, "an isolation on an absent series must not survive"
    assert control["selected"] == ["China", "India"]
    assert {t.name for t in figure.data if t.visible} == {"China", "India", "World"}


def test_a_view_from_another_task_is_discarded_even_when_its_entities_fit(tmp_path):
    """The store outlives the screen. Only its key tells one task's view from the next one's.

    The previous task's isolation names an entity this task also has, so filtering by entity alone
    would carry it over -- and the participant's first click here would appear to do nothing.
    """
    task = _first_task()
    for screen in ("0/P0", f"1/{task.task_id}", None):
        leftover = {"screen": screen, "selected": ["China"], "isolated": task.entities[0]}
        (figure, _options, _value, control), events = _interact(
            "chart.clickData",
            tmp_path,
            control_state=leftover,
            click_data={"points": [{"curveNumber": 0}]},
        )
        # Fresh view, so the click isolates rather than releases.
        assert events[-1]["payload"] == {"entity": task.entities[0], "isolated": True}, screen
        assert control["selected"] == layout.filterable(list(task.entities)), screen
        assert control["screen"] == f"0/{task.task_id}"


def test_the_chart_callback_has_nothing_the_static_condition_lacks():
    """The chart is rendered in both conditions, so its callback must be complete in both."""
    instance = app.create_app()
    base = _ids(instance.layout)
    static = _ids(app.render(_state(Stage.TASK, first_condition="static")))
    for callback in instance.callback_map.values():
        if "chart" in {i["id"] for i in callback["inputs"]}:
            ids = {i["id"] for i in callback["inputs"]} | {s["id"] for s in callback["state"]}
            assert ids <= base | static
            assert not {"entity-filter", "entity-sort", "reset-view"} & ids


def test_the_chart_callback_changes_nothing_on_a_static_render(tmp_path):
    """Plotly's render-time relayout reaches the server in the static condition too. It must be
    ignored there, as in the interactive condition: no event, no change to the chart."""
    static = _state(Stage.TASK, first_condition="static").to_dict()
    for relayout in ({"autosize": True}, {}, None):
        result = app.control_step(
            "chart.relayoutData",
            static,
            {"session_id": "s"},
            None,
            relayout=relayout,
            log_dir=tmp_path,
        )
        assert result == (no_update,) * 5
    assert _events(tmp_path) == []


# --- The bar chart's sort and the map's coverage range ------------------------------------------


def _position(chart: str) -> int:
    return next(i for i, task in enumerate(tasks.for_form("A")) if task.chart == chart)


def _view_at(chart: str, **kwargs):
    """A control state belonging to form A's `chart` item, first half."""
    return {"screen": f"0/{tasks.for_form('A')[_position(chart)].task_id}", **kwargs}


def _interact_on(chart, triggered, tmp_path, control_state=None, **kwargs):
    """Run one control interaction on form A's `chart` item. Returns (all five outputs, events)."""
    state = _state(Stage.TASK, first_condition="interactive", task_index=_position(chart))
    result = app.control_step(
        triggered,
        state.to_dict(),
        {"session_id": str(uuid.uuid4())},
        control_state,
        log_dir=tmp_path,
        **kwargs,
    )
    return result, [e for e in _events(tmp_path) if e["event"] != "session_start"]


def test_sorting_the_bars_reorders_them_and_logs_it(tmp_path):
    (figure, options, value, control, _spool), events = _interact_on(
        "bar", "bar-sort.value", tmp_path, sort_key="coverage"
    )
    assert [e["event"] for e in events] == ["sort_change"]
    assert events[0]["payload"] == {"key": "coverage", "direction": "desc"}
    assert events[0]["task_id"] == tasks.for_form("A")[_position("bar")].task_id
    values = dict(zip(figure.data[0].x, figure.data[0].y, strict=True))
    order = list(figure.layout.xaxis.categoryarray)
    assert order == sorted(order, key=lambda name: -values[name])
    assert control["sort"] == "coverage"
    assert options is no_update and value is no_update, "the bar screen has no filter list"


def test_sorting_the_bars_back_restores_the_listed_order(tmp_path):
    task = tasks.for_form("A")[_position("bar")]
    (figure, *_rest), events = _interact_on(
        "bar",
        "bar-sort.value",
        tmp_path,
        control_state=_view_at("bar", sort="coverage"),
        sort_key="listed",
    )
    assert list(figure.layout.xaxis.categoryarray) == list(task.entities)
    assert events[0]["payload"] == {"key": "listed", "direction": "none"}


def test_a_freshly_rendered_bar_sort_logs_nothing(tmp_path):
    """Dash fires the radio's callback when each bar screen is built. That is not a sort."""
    result, events = _interact_on("bar", "bar-sort.value", tmp_path, sort_key="listed")
    assert result == (no_update,) * 5
    assert events == []


def test_narrowing_the_coverage_range_fades_the_map_and_logs_it(tmp_path):
    (figure, _options, value, control, _spool), events = _interact_on(
        "map", "coverage-band.value", tmp_path, band=[0, 49]
    )
    assert [e["event"] for e in events] == ["filter_change"]
    assert events[0]["payload"] == {
        "control": "coverage-band",
        "action": "band",
        "value": [0, 49],
        "previous": [0, 100],
    }
    assert control["band"] == [0, 49]
    assert value is no_update, "the slider already shows what the participant set"
    shown = [z for z, kept in zip(figure.data[0].z, figures.in_band(figure), strict=True) if kept]
    assert shown and all(z <= 49 for z in shown)


def test_show_all_on_the_map_moves_the_slider_back_and_logs_it(tmp_path):
    (figure, _options, value, control, _spool), events = _interact_on(
        "map", "band-reset.n_clicks", tmp_path, control_state=_view_at("map", band=[0, 49])
    )
    assert value == [0, 100], "Show all must move the handles back to the ends"
    assert control["band"] == [0, 100]
    assert events[0]["payload"]["control"] == "band-reset"
    assert events[0]["payload"]["previous"] == [0, 49]
    assert all(figures.in_band(figure))


def test_the_slider_moving_back_after_show_all_is_not_a_second_event(tmp_path):
    """Show all writes the slider, and Dash then reports the slider's new value. Logged again, one
    click would count as two interactions."""
    result, events = _interact_on(
        "map",
        "coverage-band.value",
        tmp_path,
        control_state=_view_at("map", band=[0, 100]),
        band=[0, 100],
    )
    assert result == (no_update,) * 5
    assert events == []


def test_show_all_on_an_unfiltered_map_logs_nothing(tmp_path):
    result, events = _interact_on("map", "band-reset.n_clicks", tmp_path)
    assert result == (no_update,) * 5
    assert events == []


@pytest.mark.parametrize("band", [None, [60, 40], [0], ["a", "b"], [-5, 200]])
def test_a_malformed_range_is_ignored(tmp_path, band):
    result, events = _interact_on("map", "coverage-band.value", tmp_path, band=band)
    assert result == (no_update,) * 5
    assert events == []


@pytest.mark.parametrize("chart", ["bar", "scatter", "heatmap", "map"])
def test_a_click_on_anything_but_a_line_isolates_nothing(tmp_path, chart):
    result, events = _interact_on(
        chart, "chart.clickData", tmp_path, click_data={"points": [{"curveNumber": 0}]}
    )
    assert result == (no_update,) * 5
    assert events == []


@pytest.mark.parametrize("chart", ["line", "scatter", "heatmap"])
def test_a_control_for_another_chart_type_changes_nothing(tmp_path, chart):
    """A sort or range arriving on a screen whose chart has no such control is not an action."""
    for triggered, kwargs in (
        ("bar-sort.value", {"sort_key": "coverage"}),
        ("coverage-band.value", {"band": [0, 40]}),
        ("band-reset.n_clicks", {}),
    ):
        result, events = _interact_on(chart, triggered, tmp_path, **kwargs)
        assert result == (no_update,) * 5, triggered
        assert events == [], triggered


def test_the_bar_and_map_controls_have_callbacks_of_their_own():
    """Each set of Inputs lives on one chart type's screen, so each needs its own callback."""
    callbacks = {
        tuple(sorted(f"{i['id']}.{i['property']}" for i in callback["inputs"])): callback
        for callback in app.create_app().callback_map.values()
    }
    assert ("bar-sort.value",) in callbacks
    band = callbacks[("band-reset.n_clicks", "coverage-band.value")]
    outputs = {f"{o.component_id}.{o.component_property}" for o in band["output"]}
    assert "coverage-band.value" in outputs, "Show all has to move the slider back"


# --- Validation refuses rather than advancing -----------------------------------------------------


@pytest.mark.parametrize(
    ("stage", "trigger", "kwargs", "expected"),
    [
        (Stage.PARTICIPANT_ID, "participant-button", {"participant_id": "  "}, "participant ID"),
        (Stage.CONSENT, "consent-clock", _consent_kwargs(name=" "), "your full name"),
        (Stage.CONSENT, "consent-clock", _consent_kwargs(date=""), "today's date"),
        (Stage.CONSENT, "consent-clock", _consent_kwargs(signature=None), "sign in the box"),
        (Stage.CONSENT, "consent-clock", _consent_kwargs(signature=[[[1, 1]]]), "sign in the box"),
        (
            Stage.CONSENT,
            "consent-clock",
            _consent_kwargs(signature=[[["x", 1]] * 20]),
            "could not be read",
        ),
        (Stage.CONSENT, "consent-clock", {"consented_at": CONSENTED_AT}, "sign"),
        (Stage.LOAD, "survey-clock", {"load": "lots"}, "could not be read"),
    ],
)
def test_incomplete_input_is_refused_without_advancing(stage, trigger, kwargs, expected, tmp_path):
    session, log, screen, error, _spool = app.step(
        trigger, _state(stage).to_dict(), {}, log_dir=tmp_path, **kwargs
    )
    assert expected in error
    assert session is no_update, "a refused step must not advance the session"
    assert screen is no_update
    assert not list(tmp_path.glob("*.jsonl")), "a refused step must not log an answer"


def test_an_invalid_transition_becomes_a_message_not_a_crash(tmp_path):
    """A participant who double-clicks, or resumes a stale tab, must see a message."""
    session, _log, _screen, error, _spool = app.step(
        "consent-clock",
        _state(Stage.TASK).to_dict(),
        {},
        **_consent_kwargs(),
        log_dir=tmp_path,
    )
    assert "Expected stage consent" in error
    assert not (tmp_path / "consent").exists(), "a refused consent must not be stored"
    assert session is no_update


def test_a_log_that_cannot_be_written_is_a_message_not_a_dead_button(tmp_path, monkeypatch):
    """Found in a browser: on a read-only filesystem, Begin raised OSError and returned HTTP 500.

    The renderer shows nothing for a 500, so the participant pressed a button that did nothing.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def read_only(*_args, **_kwargs):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr("src.logging.JsonlSink.__init__", read_only)
    session, _log, screen, error, _spool = app.step(
        "begin-button", _state(Stage.INSTRUCTIONS).to_dict(), {}, log_dir=tmp_path
    )
    assert error == app.UNSAVEABLE
    assert session is no_update, "the session must not advance past a log that was never written"
    assert screen is no_update


def test_a_deployment_without_a_database_refuses_instead_of_losing_the_data(monkeypatch):
    """On Vercel a JSONL file is unwritable or lost with the instance, so it is never the sink."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    session, _log, screen, error, _spool = app.step(
        "begin-button", _state(Stage.INSTRUCTIONS).to_dict(), {}
    )
    assert error == app.UNSAVEABLE
    assert session is no_update
    assert screen is no_update


# --- Timing ---------------------------------------------------------------------------------------


def test_elapsed_subtracts_two_browser_timestamps():
    assert app._elapsed(1000.0, 2500.5) == (1500.5, None)


def test_elapsed_subtracts_stamps_from_the_same_page_load():
    origin = 1_758_000_000_000.25
    started = {"t": 1000.0, "origin": origin}
    submitted = {"t": 2500.5, "origin": origin}
    assert app._elapsed(started, submitted) == (1500.5, None)


@pytest.mark.parametrize(("started", "submitted"), [(None, 1.0), (1.0, None), (None, None)])
def test_elapsed_is_none_when_a_timestamp_is_missing(started, submitted):
    """Absent must stay visibly absent; recording it as zero would corrupt a dependent variable."""
    assert app._elapsed(started, submitted) == (None, "missing")


def test_elapsed_rejects_a_clock_that_ran_backwards():
    """performance.now() is monotonic, so a negative span means the stores are out of step."""
    assert app._elapsed(2000.0, 1000.0) == (None, "negative")


def test_elapsed_rejects_a_clock_origin_change():
    """A reload restarts performance.now() at zero. The span is plausible, positive and wrong.

    Here the task appeared 40 s into the first page load and Submit came 3 s after a reload: plain
    subtraction would record a 37-second task as a fast, believable number rather than as absent.
    """
    started = {"t": 40_000.0, "origin": 1_758_000_000_000.0}
    submitted = {"t": 3_000.0, "origin": 1_758_000_050_000.0}
    assert app._elapsed(started, submitted) == (None, "clock_reset")
    # Positive-looking case too: the undercount that plain subtraction could not have caught.
    started = {"t": 500.0, "origin": 1_758_000_000_000.0}
    submitted = {"t": 3_000.0, "origin": 1_758_000_050_000.0}
    assert app._elapsed(started, submitted) == (None, "clock_reset")


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


# --- Consent --------------------------------------------------------------------------------------


def test_consent_is_logged_once_per_participant_with_the_browser_timestamp(tmp_path):
    events = _run_session(tmp_path)
    consents = [e for e in events if e["event"] == "consent"]
    assert len(consents) == 1, "once per participant, not once per condition"
    consent = consents[0]
    assert consent["payload"]["consented_at"] == CONSENTED_AT, "the browser time, not server_ts"
    assert consent["payload"]["consent_version"] == app.CONSENT_VERSION
    assert consent["condition_order"] == 1


def test_consent_precedes_the_first_condition(tmp_path):
    events = _run_session(tmp_path)
    consent = next(e for e in events if e["event"] == "consent")
    names = [e["event"] for e in events if e["session_id"] == consent["session_id"]]
    assert names.index("consent") < names.index("condition_start")


def test_consent_without_a_browser_timestamp_is_refused(tmp_path):
    session, _log, screen, error, _spool = app.step(
        "consent-clock", _state(Stage.CONSENT).to_dict(), {}, consented_at=None, log_dir=tmp_path
    )
    assert error
    assert session is no_update


def test_the_consent_version_is_a_hash_of_the_displayed_text():
    import hashlib

    expected = hashlib.sha256(app.CONSENT_TEXT.encode()).hexdigest()[:16]
    assert expected == app.CONSENT_VERSION


# --- Duplicate submission -------------------------------------------------------------------------


def _through_practice(log_dir):
    """Consent, ID, instructions and the practice item. Returns (session, log) on task T1."""
    session = log = None
    for trigger, kwargs in [
        ("consent-clock", _consent_kwargs()),
        ("participant-button", {"participant_id": "P01"}),
        ("demographics-clock", {"demographics": DEMOGRAPHICS}),
        ("begin-button", {}),
        ("submit-clock", {**ANSWER_KWARGS, "duration_ms": 1000.0}),
    ]:
        session, log, _screen, error, _spool = app.step(
            trigger, session, log, log_dir=log_dir, **kwargs
        )
        assert error == ""
    return session, log


def test_an_answer_already_recorded_is_not_recorded_again(tmp_path):
    session, log = _through_practice(tmp_path)
    before = session
    session, log, _screen, error, _spool = app.step(
        "submit-clock", before, log, log_dir=tmp_path, **ANSWER_KWARGS, duration_ms=900.0
    )
    assert error == ""

    # The same Submit arriving again with the stale session state it was sent with.
    repeat = app.step(
        "submit-clock", before, log, log_dir=tmp_path, **ANSWER_KWARGS, duration_ms=950.0
    )
    answers = [e for e in _events(tmp_path) if e["event"] == "answer_submit"]
    assert [a["task_id"] for a in answers] == ["P0", "T1"], "T1 must be recorded exactly once"
    assert repeat == (no_update, no_update, no_update, "", no_update)


def test_a_duplicate_submit_does_not_re_render_the_page(tmp_path):
    """Re-rendering would restamp task-clock and silently reset the timing of the task now on
    screen, so the refusal must leave the page untouched."""
    session, log = _through_practice(tmp_path)
    before = session
    _session, log, _screen, _error, _spool = app.step(
        "submit-clock", before, log, log_dir=tmp_path, **ANSWER_KWARGS, duration_ms=900.0
    )
    _s, _l, screen, _e, _sp = app.step(
        "submit-clock", before, log, log_dir=tmp_path, **ANSWER_KWARGS, duration_ms=950.0
    )
    assert screen is no_update


def test_submit_with_no_task_on_screen_is_a_message_not_a_crash(tmp_path):
    _session, _log, _screen, error, _spool = app.step(
        "submit-clock", _state(Stage.BREAK).to_dict(), {}, log_dir=tmp_path, **ANSWER_KWARGS
    )
    assert "No task to answer" in error


def test_an_invalid_duration_is_recorded_absent_and_flagged(tmp_path):
    session, log = _through_practice(tmp_path)
    app.step(
        "submit-clock",
        session,
        log,
        log_dir=tmp_path,
        **ANSWER_KWARGS,
        duration_ms=None,
        duration_invalid="clock_reset",
    )
    events = _events(tmp_path)
    answer = next(e for e in events if e["event"] == "answer_submit" and e["task_id"] == "T1")
    end = next(e for e in events if e["event"] == "task_end" and e["task_id"] == "T1")
    for record in (answer, end):
        assert record["payload"]["duration_ms"] is None
        assert record["payload"]["duration_invalid"] == "clock_reset"


# --- Database outage ------------------------------------------------------------------------------


@pytest.fixture
def database(monkeypatch, tmp_path):
    """A configured database whose writes can be switched between failing and succeeding."""
    from src import logging as study_logging

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    monkeypatch.setenv("STUDY_SPOOL_DIR", str(tmp_path / "spool"))
    monkeypatch.setattr(study_logging, "BREAKER", study_logging.CircuitBreaker())
    # No real waiting: the retry loop's sleeps are recorded instead.
    sleeps: list[float] = []
    monkeypatch.setattr(study_logging.time, "sleep", sleeps.append)
    monkeypatch.setattr(db, "register_participant", lambda pid: (1, "static", "A"))

    class Database:
        up = False
        written: list[dict] = []
        slept = sleeps
        breaker_module = study_logging

        @staticmethod
        def insert(record, **kwargs):
            if not Database.up:
                raise db.TransientDatabaseError("Neon compute is suspended")
            Database.written.append(record)

    Database.written = []
    Database.consents = []
    monkeypatch.setattr(db, "insert_event", Database.insert)
    # The consent record is written at the consent click, before an outage in these tests begins.
    monkeypatch.setattr(db, "insert_consent", Database.consents.append)
    return Database


def _drive_with_spool(steps):
    """Run `step` through a sequence, threading every store the way the browser would."""
    session = log = spool = None
    errors = []
    for trigger, kwargs in steps:
        new_session, new_log, _screen, error, new_spool = app.step(
            trigger, session, log, spool=spool, **kwargs
        )
        errors.append(error)
        if new_session is not no_update:
            session = new_session
        if new_log is not no_update:
            log = new_log
        if new_spool is not no_update:
            spool = new_spool
    return session, log, spool, errors


def _full_session_steps():
    steps = [
        ("consent-clock", _consent_kwargs()),
        ("participant-button", {"participant_id": "P01"}),
        ("demographics-clock", {"demographics": DEMOGRAPHICS}),
    ]
    for condition in range(2):
        steps.append(("begin-button", {}))
        if condition == 0:
            steps.append(("submit-clock", {**ANSWER_KWARGS, "duration_ms": 1234.5}))
        steps += [("submit-clock", {**ANSWER_KWARGS, "duration_ms": 1000.0})] * len(
            tasks.for_form("A")
        )
        steps.append(("survey-clock", SURVEY_KWARGS))
        if condition == 0:
            steps.append(("resume-button", {}))
    return steps


def test_a_session_completes_through_a_database_outage(database, tmp_path):
    """The failure this whole layer exists for: Neon unreachable for an entire session.

    Before, the first write raised out of the callback, Dash returned a 500, and the participant was
    left pressing a Submit button that did nothing while their answer was lost.
    """
    session, _log, spool, errors = _drive_with_spool(_full_session_steps())

    assert errors == [""] * len(errors), "no step may be refused because the database is down"
    assert SessionState.from_dict(session).stage is Stage.COMPLETE
    assert database.written == []

    pending = spool["pending"]
    names = [record["event"] for record in pending]
    assert names.count("answer_submit") == 2 * len(tasks.for_form("A")) + 1
    assert names.count("consent") == 1
    assert names.count("load_rating") == 2
    assert len({record["event_uid"] for record in pending}) == len(pending)

    envelopes = database.breaker_module.read_spool(tmp_path / "spool")
    # Same events, and the same order within each session. Across the two sessions a shared clock
    # tick can interleave them (see `read_spool`), which no analysis depends on.
    for session_id in {r["session_id"] for r in pending}:
        spooled = [
            e["record"]["event_uid"] for e in envelopes if e["record"]["session_id"] == session_id
        ]
        held = [r["event_uid"] for r in pending if r["session_id"] == session_id]
        assert spooled == held, "the file copy must hold the same events, in the same order"
    assert len(envelopes) == len(pending)


def test_an_outage_costs_retry_time_once_not_on_every_event(database):
    """The circuit breaker: after the first exhausted retry, events go straight to the spool."""
    _drive_with_spool(_full_session_steps())
    assert 0 < sum(database.slept) <= database.breaker_module.FULL.budget_s


def test_spooled_events_are_replayed_in_order_when_the_database_returns(database):
    steps = _full_session_steps()
    session, log, spool, _errors = _drive_with_spool(steps[:4])
    backlog = [record["event_uid"] for record in spool["pending"]]
    assert backlog

    database.up = True
    database.breaker_module.BREAKER.reset()
    _new_session, _new_log, _screen, error, new_spool = app.step(
        "submit-clock", session, log, spool=spool, **ANSWER_KWARGS, duration_ms=900.0
    )

    assert error == ""
    assert [r["event_uid"] for r in database.written][: len(backlog)] == backlog
    marker = next(r for r in database.written if r["event"] == "sink_recovered")
    assert marker["payload"]["spooled"] == len(backlog)
    assert marker["participant_id"] == "P01"
    assert new_spool == {"pending": [], "dropped": 0}


def test_a_healthy_database_never_touches_the_spool_store(database):
    database.up = True
    session = log = None
    for trigger, kwargs in _full_session_steps():
        session, log, _screen, error, spool = app.step(trigger, session, log, **kwargs)
        assert error == ""
        assert spool is no_update, f"{trigger} wrote the spool store with nothing to spool"


def test_assignment_failure_is_a_retryable_message(database, monkeypatch):
    """Assignment cannot be spooled or invented without breaking the counterbalancing."""

    def unavailable(pid):
        raise db.TransientDatabaseError("Neon compute is suspended")

    monkeypatch.setattr(db, "register_participant", unavailable)
    session, _log, screen, error, _spool = app.step(
        "participant-button",
        _state(Stage.PARTICIPANT_ID).to_dict(),
        {},
        participant_id="P01",
    )
    assert "could not start your session" in error
    assert session is no_update
    assert screen is no_update
    assert database.slept, "assignment is outside any task window, so it retries"


def test_a_control_still_updates_the_chart_when_logging_fails(database, monkeypatch):
    """Logging used to run before the figure was built, so a failed write swallowed the click."""

    def no_sleeping(_seconds):
        raise AssertionError("interaction events must never retry: it would inflate task time")

    monkeypatch.setattr(database.breaker_module.time, "sleep", no_sleeping)
    figure, _options, value, _control, spool = app.control_step(
        "entity-filter.value",
        _task_state(),
        {"session_id": str(uuid.uuid4())},
        None,
        selected=["China"],
    )
    assert figure is not no_update
    assert value == ["China"]
    assert [r["event"] for r in spool["pending"]] == ["filter_change"]


# --- Clientside JavaScript ------------------------------------------------------------------------
#
# Nothing in this suite runs a browser, and these functions are the whole of the study's timing
# instrumentation. Node executes them against a stub `window`, which is enough to catch a syntax
# error, a wrong return shape, or a guard that would leave a participant with a dead button.

_NODE_HARNESS = r"""
const calls = [];
const timers = [];
const window = {
  performance: { now: () => 1234.5, timeOrigin: 1758000000000.25 },
  dash_clientside: { no_update: "NO_UPDATE", set_props: (id, props) => calls.push([id, props]) },
  setTimeout: (fn, ms) => timers.push([fn, ms]),
  confirm: (message) => { calls.push(["confirm", message]); return window.confirmAnswer; },
};
// Every id is on the page unless a case lists it as gone, as when the screen has moved on.
const document = { getElementById: (id) => (window.gone.includes(id) ? null : { id }) };
const cases = JSON.parse(process.argv[1]);
const out = cases.map(([source, arg, fireTimers, extra, confirmAnswer, gone]) => {
  window.confirmAnswer = confirmAnswer !== false;
  window.gone = gone || [];
  const fn = eval("(" + source + ")");
  const result = fn(arg, ...(extra || []));
  if (fireTimers) { timers.forEach(([f]) => f()); }
  return { result, timers: timers.map(([, ms]) => ms), calls: calls.slice() };
});
console.log(JSON.stringify(out));
"""


def _run_js(cases):
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, "-e", _NODE_HARNESS, json.dumps(cases)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def test_the_clock_stamps_carry_their_origin():
    task, submit, no_click = _run_js(
        [
            [app.CLOCK_JS, None, False],
            [app.SUBMIT_JS, 1, False, ["1", "why"]],
            [app.SUBMIT_JS, 0, False, ["1", "why"]],
        ]
    )
    assert {k: task["result"][k] for k in ("t", "origin")} == {
        "t": 1234.5,
        "origin": 1758000000000.25,
    }
    assert submit["result"] == [{"t": 1234.5, "origin": 1758000000000.25}, True]
    assert no_click["result"] == ["NO_UPDATE", "NO_UPDATE"]
    # The browser's stamps are exactly what the server subtracts.
    assert app._elapsed(task["result"], submit["result"][0]) == (0.0, None)


_SESSION = {"participant_id": "P01", "condition_index": 0, "stage": "task", "task_index": 2}


def test_the_task_clock_stamps_each_screen_once():
    """A reload re-renders the screen already showing. Restamping it measured from the reload."""
    first, same, next_task, other_participant = _run_js(
        [
            [app.CLOCK_JS, None, False, [_SESSION, None]],
            # The stamp taken before a reload: same screen, a different page load's origin.
            [
                app.CLOCK_JS,
                None,
                False,
                [_SESSION, {"t": 9.0, "origin": 1.0, "screen": "P01/0/task/2"}],
            ],
            [
                app.CLOCK_JS,
                None,
                False,
                [
                    {**_SESSION, "task_index": 3},
                    {"t": 9.0, "origin": 1.0, "screen": "P01/0/task/2"},
                ],
            ],
            [
                app.CLOCK_JS,
                None,
                False,
                [
                    {**_SESSION, "participant_id": "P02"},
                    {"t": 9.0, "origin": 1.0, "screen": "P01/0/task/2"},
                ],
            ],
        ]
    )
    assert first["result"]["screen"] == "P01/0/task/2"
    assert same["result"] == "NO_UPDATE"
    assert next_task["result"]["screen"] == "P01/0/task/3"
    assert other_participant["result"]["screen"] == "P02/0/task/2"


def test_a_reload_mid_task_is_recorded_as_a_clock_reset():
    """End to end across the JS and the server: the kept stamp and a post-reload Submit disagree
    on their origin, so the duration is absent and flagged rather than a quiet undercount."""
    kept = {"t": 800.0, "origin": 1758000000000.0, "screen": "P01/0/task/2"}
    after_reload, submitted = _run_js(
        [[app.CLOCK_JS, None, False, [_SESSION, kept]], [app.SUBMIT_JS, 1, False, ["1", "x"]]]
    )
    assert after_reload["result"] == "NO_UPDATE"
    assert app._elapsed(kept, submitted["result"][0]) == (None, "clock_reset")


def test_submit_is_disabled_on_click_and_the_watchdog_re_enables_it():
    (clicked,) = _run_js([[app.SUBMIT_JS, 1, True, ["1", "why"]]])
    assert clicked["result"][1] is True
    assert clicked["timers"] == [15000]
    assert clicked["calls"] == [["submit-button", {"disabled": False}]], "no popup when complete"


def test_a_watchdog_whose_button_has_gone_leaves_the_page_alone():
    """After the sixth task the survey is on screen and Submit is gone. Re-enabling a missing id
    made the Dash renderer throw (headless Chrome, 2026-09-23), in every participant's session."""
    # One harness run each: the harness fires every timer armed so far, so cases would mix.
    cases = [
        [app.SUBMIT_JS, 1, True, ["1", "why"], True, ["submit-button"]],
        [app.confirm_js("load-button"), 1, True, [5], True, ["load-button"]],
        [app.PARTICIPANT_DISABLE_JS, 1, True, [None], True, ["participant-button"]],
    ]
    for case in cases:
        (fired,) = _run_js([case])
        assert fired["timers"], "the watchdog is still armed"
        assert not [call for call in fired["calls"] if call[0] != "confirm"]


def test_an_unclicked_submit_is_not_disabled():
    (initial,) = _run_js([[app.SUBMIT_JS, 0, True, [None, None]]])
    assert initial["result"] == ["NO_UPDATE", "NO_UPDATE"]
    assert initial["timers"] == []


def test_a_skip_asks_for_confirmation_naming_what_is_missing():
    (skipped,) = _run_js([[app.SUBMIT_JS, 1, False, [None, "  "], True]])
    ((kind, message),) = [call for call in skipped["calls"] if call[0] == "confirm"]
    assert "multiple-choice question" in message
    assert "how you decided" in message
    assert skipped["result"][0]["t"] == 1234.5, "a confirmed skip still submits"
    assert skipped["result"][1] is True


def test_cancelling_the_skip_popup_leaves_the_participant_on_the_task():
    """No stamp, no disabled button: the task simply carries on."""
    (cancelled,) = _run_js([[app.SUBMIT_JS, 1, True, ["1", ""], False]])
    assert cancelled["result"] == ["NO_UPDATE", "NO_UPDATE"]
    assert cancelled["timers"] == []


def test_the_questionnaire_screens_confirm_skips_and_count_them():
    source = app.confirm_js("load-button")
    complete, partial, cancelled = _run_js(
        [
            [source, 1, False, [5, 6, 7, 1]],
            [source, 1, False, [5, None, "", 1], True],
            [source, 2, False, [None, 6, 7, 1], False],
        ]
    )
    assert complete["result"][0]["skipped"] == 0
    assert complete["result"][1] is True
    assert partial["result"][0]["skipped"] == 2
    assert ["confirm", "You have left 2 questions unanswered. Continue without answering?"] in (
        partial["calls"]
    )
    assert cancelled["result"] == ["NO_UPDATE", "NO_UPDATE"]


def test_the_signed_copy_downloads_from_the_browser():
    clicked, empty = _run_js(
        [
            [app.COPY_DOWNLOAD_JS, 1, False, ["<html>copy</html>"]],
            [app.COPY_DOWNLOAD_JS, 1, False, [None]],
        ]
    )
    assert clicked["result"] == {
        "content": "<html>copy</html>",
        "filename": "signed-consent-form.html",
        "type": "text/html",
    }
    assert empty["result"] == "NO_UPDATE"


def test_a_refusal_re_enables_submit():
    """A refusal does not re-render the screen. Without this the button stays disabled for good."""
    refused, succeeded = _run_js(
        [
            [app.SUBMIT_ENABLE_JS, "Please choose an answer.", False],
            [app.SUBMIT_ENABLE_JS, "", False],
        ]
    )
    assert refused["result"] is False
    assert succeeded["result"] == "NO_UPDATE"


def test_continue_is_disabled_on_click_or_enter_and_the_watchdog_re_enables_it():
    clicked, entered, fresh = _run_js(
        [
            [app.PARTICIPANT_DISABLE_JS, 1, True, [None]],
            [app.PARTICIPANT_DISABLE_JS, None, False, [1]],
            [app.PARTICIPANT_DISABLE_JS, 0, False, [None]],
        ]
    )
    assert clicked["result"] is True
    assert clicked["calls"] == [["participant-button", {"disabled": False}]]
    assert entered["result"] is True
    assert fresh["result"] == "NO_UPDATE"
    # Longer than the slowest assignment against an unreachable database.
    assert clicked["timers"] == [25000]


def test_a_refused_id_re_enables_continue():
    refused, cleared = _run_js(
        [
            [app.PARTICIPANT_ENABLE_JS, "Please enter your participant ID.", False],
            [app.PARTICIPANT_ENABLE_JS, "", False],
        ]
    )
    assert refused["result"] is False
    assert cleared["result"] == "NO_UPDATE"


def test_the_consent_clock_is_an_iso_timestamp():
    from datetime import datetime

    clicked, initial = _run_js([[app.CONSENT_CLOCK_JS, 1, False], [app.CONSENT_CLOCK_JS, 0, False]])
    assert datetime.fromisoformat(clicked["result"].replace("Z", "+00:00"))
    assert initial["result"] == "NO_UPDATE"


def _wired(output: str, input_: str) -> bool:
    """True when some callback writes `output` and is triggered by `input_`.

    Dash keys `callback_map` by its outputs, as "id.prop", or "..a.prop...b.prop.." for several,
    with an "@hash" suffix on an allow_duplicate output.
    """
    for key, callback in app.create_app().callback_map.items():
        outputs = {part.split("@")[0] for part in key.strip(".").split("...")}
        inputs = {f"{i['id']}.{i['property']}" for i in callback["inputs"]}
        if output in outputs and input_ in inputs:
            return True
    return False


def test_the_disable_and_re_enable_callbacks_are_registered():
    assert _wired("submit-button.disabled", "submit-button.n_clicks")
    assert _wired("submit-button.disabled", "flow-error.children")


def test_advance_is_triggered_by_the_consent_clock_not_the_button():
    """Chaining off the clock is what guarantees the timestamp exists when the step runs."""
    assert _wired("consent-clock.data", "consent-button.n_clicks")
    assert _wired("session-state.data", "consent-clock.data")
    assert not _wired("session-state.data", "consent-button.n_clicks")


def test_both_callbacks_that_log_can_write_the_spool():
    assert _wired("spool-state.data", "submit-clock.data")
    assert _wired("spool-state.data", "chart.clickData")


def test_the_new_stores_are_in_the_base_layout():
    assert {"consent-clock", "spool-state"} <= _ids(app.create_app().layout)


def test_the_click_clocks_do_not_survive_a_reload():
    """A session store restores itself on mount, and Dash counts the restore as a change -- so a
    persisted click clock would re-fire its callback on every page load, with a stale stamp."""
    clocks = {"consent-clock", "submit-clock", "demographics-clock", "survey-clock"}
    stores = {
        child.id: getattr(child, "storage_type", "memory")
        for child in app.create_app().layout.children
        if getattr(child, "id", None) in clocks
    }
    assert stores == dict.fromkeys(clocks, "memory")


def test_the_signature_and_the_signed_copy_never_reach_session_storage():
    """Identifying: they live only as long as the page, never in sessionStorage."""
    layout_children = app.create_app().layout.children
    stores = {
        child.id: getattr(child, "storage_type", "memory")
        for child in layout_children
        if getattr(child, "id", None) in {"signature-strokes", "consent-copy"}
    }
    assert stores == {"signature-strokes": "memory", "consent-copy": "memory"}


# --- IRB alignment: consent, decline, skipping, surveys, withdrawal (2026-09-21) -----------------


def test_a_skipped_task_advances_and_is_recorded_as_a_skip(tmp_path):
    """IRB form item 10: any question may be skipped. The popup confirms; the server records it."""
    session, log = _through_practice(tmp_path)
    session, log, _screen, error, _spool = app.step(
        "submit-clock", session, log, log_dir=tmp_path, answer=None, justification="  "
    )
    assert error == ""
    assert SessionState.from_dict(session).task_index == 1, "a skip moves on to the next task"
    answer = next(
        e for e in _events(tmp_path) if e["event"] == "answer_submit" and e["task_id"] == "T1"
    )
    assert answer["payload"]["answer"] is None
    assert answer["payload"]["justification"] is None
    assert answer["payload"]["skipped"] == ["answer", "justification"]


def test_a_skipped_survey_is_recorded_as_null_not_refused(tmp_path):
    state = _state(Stage.LOAD)
    session, _log, _screen, error, _spool = app.step(
        "survey-clock",
        state.to_dict(),
        {"session_id": str(uuid.uuid4())},
        log_dir=tmp_path,
        load=None,
        survey={"clarity": 3},
    )
    assert error == ""
    assert SessionState.from_dict(session).stage is Stage.BREAK
    events = {e["event"]: e["payload"] for e in _events(tmp_path)}
    assert events["load_rating"]["value"] is None
    assert events["survey_rating"] == {
        "scale": "likert7",
        "clarity": 3,
        "ease_of_use": None,
        "confidence": None,
    }


def test_the_survey_is_logged_once_per_condition(tmp_path):
    names = [e["event"] for e in _run_session(tmp_path)]
    assert names.count("survey_rating") == 2
    assert names.count("load_rating") == 2


def test_demographics_are_logged_once_right_after_consent(tmp_path):
    events = _run_session(tmp_path)
    demographics = [e for e in events if e["event"] == "demographics"]
    assert len(demographics) == 1
    assert demographics[0]["payload"] == DEMOGRAPHICS
    first = [e["event"] for e in events if e["session_id"] == demographics[0]["session_id"]]
    assert first.index("consent") < first.index("demographics") < first.index("condition_start")


def test_an_unrecognised_demographic_answer_is_refused(tmp_path):
    _session, _log, _screen, error, _spool = app.step(
        "demographics-clock",
        _state(Stage.DEMOGRAPHICS).to_dict(),
        {},
        log_dir=tmp_path,
        demographics={"age_range": "12"},
    )
    assert "Unrecognised answer" in error


def test_declining_writes_nothing_anywhere(tmp_path):
    """IRB form item 12B: the declined screen says no data was collected, so none may be."""
    session, _log, screen, error, _spool = app.step("decline-button", None, None, log_dir=tmp_path)
    assert error == ""
    assert SessionState.from_dict(session).stage is Stage.DECLINED
    assert "No data has been collected" in json.dumps(screen.to_plotly_json(), default=str)
    assert list(tmp_path.rglob("*")) == []
    session, _log, _screen, _error, _spool = app.step(
        "reconsider-button", session, None, log_dir=tmp_path
    )
    assert SessionState.from_dict(session).stage is Stage.CONSENT


def test_the_signed_record_is_stored_apart_from_the_study_log(tmp_path):
    """IRB form items 15 and 17: the name and signature never enter the study data."""
    events = _run_session(tmp_path)
    log_text = json.dumps(events)
    assert "Test Participant" not in log_text
    assert "signature" not in json.dumps([e["payload"] for e in events if e["event"] != "consent"])
    consent_event = next(e for e in events if e["event"] == "consent")
    assert consent_event["payload"]["signature_method"] == "drawn"

    (record,) = consent.read_local(tmp_path / "consent")
    assert record["printed_name"] == "Test Participant"
    assert record["signature"] == SIGNATURE
    assert "participant_id" not in record, "the consent record must not be joinable to answers"


def test_a_paper_signature_is_accepted_without_a_drawing(tmp_path):
    session, _log, _screen, error, _spool = app.step(
        "consent-clock",
        None,
        None,
        log_dir=tmp_path,
        **_consent_kwargs(signature=None, paper=True),
    )
    assert error == ""
    assert SessionState.from_dict(session).consent_method == "paper"
    (record,) = consent.read_local(tmp_path / "consent")
    assert record["signature"] is None


def test_consent_is_refused_while_the_record_cannot_be_stored(database, monkeypatch):
    """Nothing continues on a consent that was not recorded -- unlike an event, it never spools."""

    def down(_record):
        raise db.TransientDatabaseError("Neon compute is suspended")

    monkeypatch.setattr(db, "insert_consent", down)
    session, _log, _screen, error, _spool = app.step(
        "consent-clock", None, None, **_consent_kwargs()
    )
    assert error == app.CONSENT_UNSAVED
    assert session is no_update


def test_the_participant_gets_their_signed_copy_only_once_it_is_stored(tmp_path):
    kwargs = _consent_kwargs()
    record = kwargs["consent_record"]
    outputs = app.consent_step(
        CONSENTED_AT,
        record["printed_name"],
        record["signed_date"],
        [],
        SIGNATURE,
        None,
        None,
        None,
        consent_dir=tmp_path,
    )
    copy = outputs[-1]
    assert "Test Participant" in copy and "<svg" in copy
    refused = app.consent_step(
        CONSENTED_AT, "", "2026-09-16", [], SIGNATURE, None, None, None, consent_dir=tmp_path
    )
    assert refused[-1] is no_update


def test_a_withdrawn_id_is_turned_away_with_a_message(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")

    def withdrawn(_pid):
        raise db.WithdrawnParticipantError("withdrawn")

    monkeypatch.setattr(db, "register_participant", withdrawn)
    _session, _log, _screen, error, _spool = app.step(
        "participant-button",
        _state(Stage.PARTICIPANT_ID, participant_id=None).to_dict(),
        {},
        participant_id="P01",
    )
    assert "can no longer be used" in error


def test_the_final_screen_explains_withdrawal_with_the_participant_id():
    """IRB form item 13 promises this reminder at the end of every session."""
    text = json.dumps(app.render(_state(Stage.COMPLETE)).to_plotly_json(), default=str)
    assert "two weeks" in text
    assert "rebollar@oxy.edu" in text
    assert "P01" in text


def test_the_consent_screen_warns_until_the_form_is_approved():
    text = json.dumps(app.render(_state(Stage.CONSENT)).to_plotly_json(), default=str)
    assert ("PENDING HSRRC APPROVAL" in text) is (not consent.APPROVED)
