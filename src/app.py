"""Dash entry point and study flow wiring. No pandas — this ships to production.

Run locally:
    uv run python -m src.app          # http://127.0.0.1:8050

The condition and form come from per-session state, never from `config.INTERACTIVE`: one URL serves
both conditions, so a module-level flag would be shared across concurrent participants.

`server` is the deployment entrypoint, pinned by `tool.vercel.entrypoint = "src.app:server"`.

**Timing is measured in the browser.** Each event is its own HTTP request, so a server clock would
fold network latency and cold starts into task duration — a dependent variable. Clientside callbacks
stamp `performance.now()` at screen render and at submit; the server only subtracts them. Each stamp
carries `performance.timeOrigin`, because a reload restarts that clock: two stamps from different
origins cannot be subtracted, and the duration is recorded absent and flagged instead.

**A database failure never leaves a dead button.** Event writes go through `logging.ResilientSink`,
which retries and then spools. The browser copy of the spool lives in the `spool-state` store and is
handed back to the sink on the next callback, where it is replayed before anything new.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Any

import dash
from dash import Input, Output, State, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src import config, db, figures, flow, layout, tasks
from src.flow import SessionState, Stage
from src.logging import FULL, NO_RETRY, LogError, RetryPolicy, StudyLogger, call_with_retry

# Consent wording lives in docs/study-design.md section 9 and is a DRAFT until IRB approves it.
CONSENT_TEXT = """\
You are invited to take part in a study run by a senior Computer Science student at Occidental \
College. It takes about 20-25 minutes.

You will read charts of childhood vaccination coverage and answer questions about them. There are \
no right-or-wrong consequences for you; we are studying the charts, not you.

What is recorded: your answers, how long each task takes, and how you interact with the charts. A \
participant ID that you enter, which is not linked to your name. No personal information is \
collected.

Voluntary: you may stop at any time by closing the tab, with no consequence.

DRAFT CONSENT TEXT - pending IRB review. Do not run participants on this wording."""

# Recorded on every consent event, so a change to the wording mid-study shows up in the data rather
# than depending on anyone's memory of when the text was edited.
CONSENT_VERSION = hashlib.sha256(CONSENT_TEXT.encode("utf-8")).hexdigest()[:16]

# Shown when responses cannot be saved at all, as opposed to a database that is briefly unreachable.
UNSAVEABLE = (
    "The study cannot save responses right now, so it cannot continue. "
    "Please contact the researcher."
)


def create_app() -> dash.Dash:
    """Build the Dash app. A factory so tests and the deployment share one construction path."""
    app = dash.Dash(
        __name__,
        title="Vaccination coverage study",
        # Screens are rendered dynamically, so most component ids are absent from the initial
        # layout. Without this, Dash refuses to register the callbacks that target them.
        suppress_callback_exceptions=True,
    )

    app.layout = html.Div(
        [
            dcc.Location(id="url"),
            # Browser-held state: nothing per-participant lives in the server process, which is what
            # makes a stateless serverless container safe here.
            dcc.Store(id="session-state", storage_type="session"),
            dcc.Store(id="log-state", storage_type="session"),
            # Two browser timestamps: when the task screen appeared, and when Submit was pressed.
            # The server only subtracts them, so the measurement is entirely the browser's clock.
            dcc.Store(id="task-clock", storage_type="session"),
            # The two click clocks are MEMORY stores, unlike everything else here. Each exists only
            # to trigger one server callback. A session store restores itself when the page mounts,
            # and that restore counts as a change: a reload would re-fire Submit with the previous
            # task's stamp, before any screen existed to receive it.
            dcc.Store(id="submit-clock"),
            # The consent timestamp, stamped in the browser when "I agree" is pressed.
            dcc.Store(id="consent-clock"),
            # Events the database refused, kept in the browser until they can be replayed. Its own
            # store, not a key on log-state: both callbacks write it, and letting the controls
            # callback write log-state would let a slow click response overwrite the task
            # attribution a later Submit had just set.
            dcc.Store(id="spool-state", storage_type="session"),
            # The interactive controls' view: filter, sort, isolation. In the base layout, not on
            # the task screen, so the chart's callback can read it in BOTH conditions -- see
            # `chart_interaction`. Memory, because a reload re-renders the screen with every series
            # shown, and the store must agree with what is on screen. `control_step` keys it to the
            # task, which is what resets the view between tasks.
            dcc.Store(id="control-state"),
            html.Div(id="page"),
        ]
    )

    _register_callbacks(app)
    return app


# --- Rendering ------------------------------------------------------------------------------------


def render(state: SessionState) -> html.Div:
    """The screen for the current stage. Pure: stage in, layout out.

    Total over `Stage` — every member has a branch, and `tests/test_app.py` proves it, so adding a
    stage without a screen fails the suite rather than a participant's session.
    """
    if state.stage is Stage.CONSENT:
        return layout.consent_screen(CONSENT_TEXT)
    if state.stage is Stage.PARTICIPANT_ID:
        return layout.participant_screen()
    if state.stage is Stage.INSTRUCTIONS:
        # Practice precedes the first condition only; the second reaches this screen from the break.
        return layout.instructions_screen(
            flow.is_interactive(state), practice=state.condition_index == 0
        )
    if state.stage is Stage.PRACTICE:
        return layout.task_screen(
            tasks.PRACTICE, flow.is_interactive(state), index=0, total=0, practice=True
        )
    if state.stage is Stage.LOAD:
        return layout.load_screen(tasks.LOAD_PROMPT, tasks.LOAD_ANCHORS)
    if state.stage is Stage.BREAK:
        return layout.break_screen()
    if state.stage is Stage.COMPLETE:
        return layout.complete_screen()
    if state.stage is Stage.TASK:
        items = tasks.for_form(flow.current_form(state))
        task = flow.current_task(state, items)
        return layout.task_screen(
            task, flow.is_interactive(state), state.task_index + 1, len(items)
        )
    raise flow.FlowError(f"No screen for stage {state.stage}")


class _Spool:
    """The browser-held spool, carried across the loggers one request builds.

    A request can construct more than one logger (a Submit writes the answer, then opens the next
    task), and each wraps its own sink. Whatever one leaves pending must be handed to the next, and
    the final state written back to the browser -- but only when it changed, so an ordinary request
    never touches the store.
    """

    def __init__(self, raw: dict[str, Any] | None) -> None:
        raw = raw or {}
        self.pending: list[dict[str, Any]] = list(raw.get("pending") or [])
        self.dropped = int(raw.get("dropped") or 0)
        self._initial = (len(self.pending), self.dropped, _uids(self.pending))

    def take(self, logger: StudyLogger) -> None:
        if logger.resilient:
            self.pending = logger.pending
            self.dropped = logger.dropped

    def output(self) -> Any:
        if (len(self.pending), self.dropped, _uids(self.pending)) == self._initial:
            return no_update
        return {"pending": self.pending, "dropped": self.dropped}


def _uids(records: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(record.get("event_uid")) for record in records)


def _logger(
    state: SessionState,
    log: dict[str, Any] | None,
    log_dir: Path | None = None,
    spool: _Spool | None = None,
    policy: RetryPolicy = FULL,
) -> StudyLogger:
    """Rebuild the logger for this request from browser-held session state.

    Serverless containers do not persist between callbacks, so the logger is reconstructed each
    time and resumed via `session_id` rather than held in memory.

    `log_dir` is for tests: production passes None and the logger picks its own sink — Postgres when
    `DATABASE_URL` is set, otherwise JSONL under `config.STUDY_LOGS_DIR`.
    """
    log = log or {}
    return StudyLogger(
        state.participant_id or "unknown",
        condition_order=flow.condition_order(state),
        interactive=flow.is_interactive(state),
        form=flow.current_form(state),
        session_id=log.get("session_id"),
        task_id=log.get("task_id"),
        log_dir=log_dir,
        policy=policy,
        pending=spool.pending if spool else None,
        dropped=spool.dropped if spool else 0,
    )


# --- The session step ----------------------------------------------------------------------------
#
# Module level, not a closure inside `_register_callbacks`. A callback defined inside the registrar
# is reachable only through Dash, which is why none of this logic had a test: `step` is the whole
# state machine of a session and is exercised directly by `tests/test_app.py`.


def step(
    triggered: str | None,
    stored: dict[str, Any] | None,
    log_state: dict[str, Any] | None,
    *,
    participant_id: str | None = None,
    answer: str | None = None,
    justification: str | None = None,
    load: int | None = None,
    duration_ms: float | None = None,
    duration_invalid: str | None = None,
    consented_at: str | None = None,
    spool: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> tuple[Any, Any, Any, str, Any]:
    """Advance the session one click.

    Returns (session state, log state, screen, error message, spool). Any of them may be
    `dash.no_update`, which leaves that store untouched — that is how a validation failure
    re-renders nothing and only fills the error slot.
    """
    state = SessionState.from_dict(stored)
    log_state = dict(log_state or {})
    carried = _Spool(spool)

    def refuse(message: str) -> tuple[Any, Any, Any, str, Any]:
        # The spool is still returned: a refusal can follow writes that spooled.
        return (no_update, no_update, no_update, message, carried.output())

    try:
        if triggered == "consent-clock":
            if not consented_at:
                # The clock is what triggers this branch, so a missing value means the browser
                # failed to stamp it. Consent without a time is not a record of consent.
                return refuse("Please press the button again.")
            state = flow.give_consent(state, consented_at)

        elif triggered == "participant-button":
            if not (participant_id or "").strip():
                return refuse("Please enter your participant ID.")
            condition, form = _assign(participant_id.strip())
            state = flow.set_participant(state, participant_id.strip(), condition, form)

        elif triggered == "begin-button":
            # Leaving the instructions starts the condition, practice included — so the log session
            # opens here rather than at the first scored task.
            state = (
                flow.begin_practice(state)
                if state.condition_index == 0
                else flow.begin_tasks(state)
            )
            logger = _logger(state, {}, log_dir, carried)
            if state.condition_index == 0 and state.consent_at:
                # Once per participant, first in their record. It could not be written at the
                # consent click itself, before any participant ID existed.
                logger.record_consent(state.consent_at, CONSENT_VERSION)
            logger.event(
                "condition_start",
                interactive=flow.is_interactive(state),
                condition_order=flow.condition_order(state),
            )
            carried.take(logger)
            log_state = {"session_id": logger.session_id}

        elif triggered == "resume-button":
            state = flow.resume_after_break(state)

        elif triggered == "submit-clock":
            if not answer:
                return refuse("Please choose an answer.")
            if not (justification or "").strip():
                return refuse("Please say briefly how you decided.")

            on_screen = _active_task(state)
            if on_screen is None:
                raise flow.FlowError(f"No task to answer at stage {state.stage.value}")
            answered_id = on_screen.task_id
            if answered_id in log_state.get("answered", []):
                # Already recorded in this session. Change nothing — and in particular do not
                # re-render: a fresh screen would restamp task-clock and corrupt the timing of the
                # task that is now actually on screen.
                return (no_update, no_update, no_update, "", no_update)

            logger = _logger(state, log_state, log_dir, carried)
            open_task = log_state.pop("task_id", None)
            if state.stage is Stage.PRACTICE:
                # Recorded like any other answer under task_id "P0". Not scored — analysis drops
                # P0 — but the timing and the justification are still worth having.
                logger.submit_answer(
                    tasks.PRACTICE.task_id,
                    answer=answer,
                    justification=justification.strip(),
                    duration_ms=duration_ms,
                    duration_invalid=duration_invalid,
                )
                state = flow.begin_tasks(state)
            else:
                items = tasks.for_form(flow.current_form(state))
                task = flow.current_task(state, items)
                logger.submit_answer(
                    task.task_id,
                    answer=answer,
                    justification=justification.strip(),
                    duration_ms=duration_ms,
                    duration_invalid=duration_invalid,
                )
                state = flow.complete_task(state, items)
            # Closes the span opened when this screen appeared, so the interaction events in
            # between are bracketed by the task they happened on.
            if open_task is not None:
                logger.end_task(duration_ms=duration_ms, duration_invalid=duration_invalid)
            carried.take(logger)
            log_state["session_id"] = logger.session_id
            log_state["answered"] = [*log_state.get("answered", []), answered_id]

        elif triggered == "load-button":
            if load is None:
                return refuse("Please choose a number.")
            # `condition_index` advances in `flow.submit_load`, below — so the state here still
            # names the condition being rated, and no rewind is needed to find it.
            logger = _logger(state, log_state, log_dir, carried)
            logger.rate_load(int(load))
            logger.event(
                "condition_end",
                interactive=flow.is_interactive(state),
                condition_order=flow.condition_order(state),
            )
            # Closed at the end of BOTH conditions. Closing only at COMPLETE left every participant
            # with one session carrying a session_end and one without.
            logger.close()
            carried.take(logger)
            log_state = {}
            state = flow.submit_load(state)

    except flow.FlowError as exc:
        return refuse(str(exc))
    except db.DatabaseError as exc:
        # A safety net, not the expected path: event writes spool rather than raise, and assignment
        # failures become FlowErrors in `_assign`. If something still escapes, say so and let the
        # participant retry, rather than advancing on a half-applied step or failing silently.
        print(f"[study] database error in step {triggered!r}: {exc}", file=sys.stderr)
        return refuse("Something went wrong saving that. Please wait a moment and try again.")
    except (LogError, OSError) as exc:
        # The log sink itself could not be opened or written: no DATABASE_URL on a deployment, or a
        # JSONL file that cannot be created. Uncaught, this was an HTTP 500 -- a button that did
        # nothing and said nothing. Retrying will not help, so the message does not suggest it.
        print(f"[study] logging failed in step {triggered!r}: {exc}", file=sys.stderr)
        return refuse(UNSAVEABLE)

    log_state = _open_task(state, log_state, log_dir, carried)
    return state.to_dict(), log_state, render(state), "", carried.output()


def _open_task(
    state: SessionState,
    log_state: dict[str, Any],
    log_dir: Path | None,
    spool: _Spool | None = None,
) -> dict[str, Any]:
    """Emit `task_start` for the task now on screen, and remember that it is open.

    The span is opened here, where the screen is built, rather than on the next click — so the
    interaction events a participant generates while reading fall inside their task rather than
    being attributed to the one before.
    """
    task = _active_task(state)
    if task is None or not log_state.get("session_id") or log_state.get("task_id"):
        return log_state
    logger = _logger(state, {**log_state, "task_id": None}, log_dir, spool)
    try:
        logger.start_task(task.task_id)
    except (db.DatabaseError, LogError, OSError) as exc:
        # The answer that got the participant here is already written. Leave the task unopened
        # rather than fail the whole step: the matching task_end is then skipped too, so the record
        # stays consistently bracketed instead of half-open.
        print(f"[study] could not open task {task.task_id}: {exc}", file=sys.stderr)
        return log_state
    if spool is not None:
        spool.take(logger)
    return {**log_state, "task_id": task.task_id}


# --- The interactive controls ---------------------------------------------------------------------
#
# Filtering, sorting, line isolation and zoom/pan. These exist ONLY in the interactive condition —
# the static condition never renders the controls, and `staticPlot: True` means its chart can be
# neither clicked nor zoomed — so every event below is, by construction, an interactive-condition
# event. The static chart does still send Plotly's render-time relayout, which carries no axis range
# and is ignored below exactly as it is in the interactive condition.
# That is the study's independent variable, and this is where it gets recorded.

# Zoom and pan arrive as axis-range keys. Plotly also sends relayout on resize and on render, which
# is not a participant action and must not be logged as one.
_VIEW_KEYS = ("xaxis.range", "yaxis.range", "xaxis.autorange", "yaxis.autorange")


def _active_task(state: SessionState):
    """The task on screen, practice included, or None when no chart is showing."""
    if state.stage is Stage.PRACTICE:
        return tasks.PRACTICE
    if state.stage is Stage.TASK:
        return flow.current_task(state, tasks.for_form(flow.current_form(state)))
    return None


def _clicked_entity(click_data: dict[str, Any] | None, task) -> str | None:
    """Which series a click landed on.

    `curveNumber` indexes the figure's traces, which are in `task.entities` order. That mapping
    survives filtering only because hidden series are made invisible rather than removed — see
    `figures.set_visible`.
    """
    points = (click_data or {}).get("points") or []
    if not points:
        return None
    index = points[0].get("curveNumber")
    if not isinstance(index, int) or not 0 <= index < len(task.entities):
        return None
    return task.entities[index]


def control_step(
    triggered: str | None,
    stored: dict[str, Any] | None,
    log_state: dict[str, Any] | None,
    control_state: dict[str, Any] | None,
    *,
    selected: list[str] | None = None,
    sort_key: str | None = None,
    click_data: dict[str, Any] | None = None,
    relayout: dict[str, Any] | None = None,
    spool: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Apply one control interaction.

    Returns (figure, filter options, filter value, control state, spool).

    `triggered` is a Dash **prop id** — "chart.clickData", not "chart". The chart raises two
    different inputs and the component id alone cannot tell them apart: `clickData` stays set on the
    component after a click, so a later zoom arrives with a stale `click_data` still populated and
    would be read as the participant clicking the same line a second time. The property name is the
    only thing that distinguishes them.

    Returns `no_update` throughout when nothing actually changed. Dash fires input callbacks when a
    component is recreated, which happens on every task render, and logging those would fill the
    interaction record with events no participant caused.

    A chart click or zoom never changes the filter list, so `chart_interaction` writes only the
    figure, the control state and the spool, and discards the other two outputs.
    """
    state = SessionState.from_dict(stored)
    task = _active_task(state)
    if task is None:
        return (no_update,) * 5

    options = layout.filterable(list(task.entities))
    # The store outlives the screen, so its view belongs to one task in one half. Any other key --
    # the previous task, the same task id in the other condition, or none -- is discarded, which is
    # what gives every task the fresh view its screen was rendered with.
    screen = f"{state.condition_index}/{task.task_id}"
    control = {"selected": list(options), "sort": "listed", "isolated": None, "screen": screen}
    if (control_state or {}).get("screen") == screen:
        control.update(control_state)
    # A stale store from the previous task would name entities this one does not have.
    control["selected"] = [e for e in control["selected"] if e in options] or list(options)
    if control["isolated"] not in task.entities:
        control["isolated"] = None

    unchanged: tuple[Any, ...] = (no_update,) * 5
    event: tuple[str, dict[str, Any]] | None = None

    if triggered == "entity-filter.value":
        chosen = [e for e in options if e in (selected or [])]
        if not chosen:
            # Refuse rather than raise: an empty chart is a FigureError, and a participant who
            # unchecks everything should simply keep the last series rather than see an error.
            return unchanged
        if chosen == list(control["selected"]) and control["isolated"] is None:
            return unchanged
        event = (
            "filter_change",
            {
                "control": "entity-filter",
                "action": "hide" if len(chosen) < len(control["selected"]) else "show",
                "value": chosen,
                "previous": list(control["selected"]),
            },
        )
        control["selected"] = chosen
        # A filter choice supersedes an isolation; otherwise the chart would ignore the click.
        control["isolated"] = None

    elif triggered == "entity-sort.value":
        if sort_key not in layout.SORT_KEYS or sort_key == control["sort"]:
            return unchanged
        event = (
            "sort_change",
            {"key": sort_key, "direction": "desc" if sort_key == "coverage" else "none"},
        )
        control["sort"] = sort_key

    elif triggered == "reset-view.n_clicks":
        if control["isolated"] is None and list(control["selected"]) == options:
            return unchanged
        event = (
            "filter_change",
            {
                "control": "reset-view",
                "action": "show",
                "value": list(options),
                "previous": list(control["selected"]),
            },
        )
        control["selected"] = list(options)
        control["isolated"] = None

    elif triggered == "chart.clickData":
        entity = _clicked_entity(click_data, task)
        # World is the reference every task is read against; isolating to it alone would hide the
        # very series the question is about.
        if entity is None or entity == "World":
            return unchanged
        isolate = control["isolated"] != entity
        event = ("line_isolate", {"entity": entity, "isolated": isolate})
        control["isolated"] = entity if isolate else None

    elif triggered == "chart.relayoutData":
        if not relayout or not any(key.startswith(_VIEW_KEYS) for key in relayout):
            return unchanged
        event = ("view_change", {"control": "chart", "value": relayout, "previous": None})

    else:
        return unchanged

    shown = [control["isolated"]] if control["isolated"] else list(control["selected"])
    if "World" in task.entities:
        shown.append("World")

    figure = figures.set_visible(figures.build_figure(list(task.entities), task.vaccine), shown)
    ordered = layout.sorted_entities(options, task.vaccine, control["sort"])
    values = layout.latest_values(ordered, task.vaccine) if control["sort"] == "coverage" else {}
    filter_options = [
        {
            "label": layout.control_label(entity, values.get(entity), control["sort"]),
            "value": entity,
        }
        for entity in ordered
    ]

    # Logged AFTER the figure is built. Logged first, a database failure left the participant's
    # click with no visible effect -- the chart simply did not change.
    #
    # NO_RETRY: this runs inside the task's measured window, and only in the interactive
    # condition. A retry here would inflate time-on-task in one condition only. A failed write
    # spools at once, and the circuit breaker sends the next click straight to the spool.
    carried = _Spool(spool)
    if event is not None:
        name, payload = event
        logger = _logger(state, log_state, log_dir, carried, policy=NO_RETRY)
        try:
            logger.event(name, task_id=task.task_id, **payload)
        except db.DatabaseError as exc:
            print(f"[study] could not log {name}: {exc}", file=sys.stderr)
        carried.take(logger)
    return figure, filter_options, list(control["selected"]), control, carried.output()


# --- Callbacks ------------------------------------------------------------------------------------


def _step_outputs() -> list[Output]:
    """What every advancing callback writes. Built fresh for each, as they are duplicate writers."""
    return [
        Output("session-state", "data", allow_duplicate=True),
        Output("log-state", "data", allow_duplicate=True),
        Output("page", "children", allow_duplicate=True),
        # One error slot, emitted by `layout.page` on every screen. Outputs that exist on only some
        # screens are a latent failure on the rest; see the note in `layout.page`.
        Output("flow-error", "children", allow_duplicate=True),
        Output("spool-state", "data", allow_duplicate=True),
    ]


def _session_states() -> list[State]:
    """The browser-held stores `step` reads. All in the base layout, so present on every screen."""
    return [
        State("session-state", "data"),
        State("log-state", "data"),
        State("spool-state", "data"),
    ]


def _register_callbacks(app: dash.Dash) -> None:
    @app.callback(
        Output("page", "children"),
        Input("url", "pathname"),
        State("session-state", "data"),
    )
    def show_page(_pathname, stored):
        return render(SessionState.from_dict(stored))

    # --- Advancing the session: ONE CALLBACK PER SCREEN ---
    #
    # Each screen's control gets its own callback, whose Inputs and States all live on that screen
    # or in the base layout. This is not style. Dash's browser renderer refuses to run a callback
    # when some of its Inputs are on the page and others are not: it throws a ReferenceError to the
    # console and sends nothing. A single callback listening to every screen's button was therefore
    # dead on every screen -- "I agree" did nothing -- while `step`, called directly by the tests,
    # worked perfectly. `tests/test_app.py` now checks every callback against every screen.
    #
    # The button callbacks refuse `n_clicks` of 0. Dash fires a callback when its Input is inserted
    # with a new screen, and `prevent_initial_call` does not stop that -- which is why the
    # clientside callbacks below guard on `!n` too. Without it, the instructions screen pressed its
    # own Begin button the moment it appeared.

    # Triggered by the consent CLOCK, like Submit below, so the browser timestamp is taken before
    # the request leaves and is guaranteed to be present.
    @app.callback(
        *_step_outputs(),
        Input("consent-clock", "data"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def consent(consented_at, stored, log_state, spool):
        return step("consent-clock", stored, log_state, consented_at=consented_at, spool=spool)

    # Continue, or Enter in the ID box: both on the ID screen, so both may be Inputs here.
    @app.callback(
        *_step_outputs(),
        Input("participant-button", "n_clicks"),
        Input("participant-input", "n_submit"),
        State("participant-input", "value"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def participant(n, n_submit, participant_id, stored, log_state, spool):
        if not n and not n_submit:
            raise PreventUpdate
        return step(
            "participant-button", stored, log_state, participant_id=participant_id, spool=spool
        )

    @app.callback(
        *_step_outputs(),
        Input("begin-button", "n_clicks"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def begin(n, stored, log_state, spool):
        if not n:
            raise PreventUpdate
        return step("begin-button", stored, log_state, spool=spool)

    @app.callback(
        *_step_outputs(),
        Input("resume-button", "n_clicks"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def resume(n, stored, log_state, spool):
        if not n:
            raise PreventUpdate
        return step("resume-button", stored, log_state, spool=spool)

    # Triggered by the submit CLOCK, not the button: the clientside callback below stamps the
    # browser time first, so by the time this runs the timestamp is guaranteed fresh rather than
    # racing the button click.
    @app.callback(
        *_step_outputs(),
        Input("submit-clock", "data"),
        State("answer-input", "value"),
        State("justification-input", "value"),
        State("task-clock", "data"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def submit(submitted_at, answer, justification, started_at, stored, log_state, spool):
        duration_ms, duration_invalid = _elapsed(started_at, submitted_at)
        return step(
            "submit-clock",
            stored,
            log_state,
            answer=answer,
            justification=justification,
            duration_ms=duration_ms,
            duration_invalid=duration_invalid,
            spool=spool,
        )

    @app.callback(
        *_step_outputs(),
        Input("load-button", "n_clicks"),
        State("load-input", "value"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def rate_load(n, load, stored, log_state, spool):
        if not n:
            raise PreventUpdate
        return step("load-button", stored, log_state, load=load, spool=spool)

    @app.callback(
        Output("chart", "figure", allow_duplicate=True),
        Output("entity-filter", "options"),
        Output("entity-filter", "value"),
        Output("control-state", "data", allow_duplicate=True),
        Output("spool-state", "data", allow_duplicate=True),
        Input("entity-filter", "value"),
        Input("entity-sort", "value"),
        Input("reset-view", "n_clicks"),
        State("session-state", "data"),
        State("log-state", "data"),
        State("control-state", "data"),
        State("spool-state", "data"),
        prevent_initial_call=True,
    )
    def controls(selected, sort_key, _reset, stored, log, control_state, spool):
        """Thin wrapper over `control_step` for the controls above the chart.

        Interactive condition only: the static condition renders none of these components, so this
        callback has nothing to fire on there.
        """
        fired = callback_context.triggered
        return control_step(
            fired[0]["prop_id"] if fired else None,
            stored,
            log,
            control_state,
            selected=selected,
            sort_key=sort_key,
            spool=spool,
        )

    # The chart's own events, in a callback of their own. The chart is rendered in BOTH conditions,
    # so everything this callback touches must be too: were it wired to the interactive-only
    # controls, the renderer would refuse it on every static screen with a console ReferenceError.
    # Its Inputs are on every task screen and its States and other Outputs are in the base layout.
    @app.callback(
        Output("chart", "figure", allow_duplicate=True),
        Output("control-state", "data", allow_duplicate=True),
        Output("spool-state", "data", allow_duplicate=True),
        Input("chart", "clickData"),
        Input("chart", "relayoutData"),
        State("session-state", "data"),
        State("log-state", "data"),
        State("control-state", "data"),
        State("spool-state", "data"),
        prevent_initial_call=True,
    )
    def chart_interaction(click_data, relayout, stored, log, control_state, spool):
        """Thin wrapper over `control_step` for clicks and zooms on the chart itself.

        Passes the **prop id**, not `triggered_id`: the chart raises both `clickData` and
        `relayoutData`, and the component id alone cannot separate a zoom from a stale click.
        """
        fired = callback_context.triggered
        figure, _options, _value, control, spool_out = control_step(
            fired[0]["prop_id"] if fired else None,
            stored,
            log,
            control_state,
            click_data=click_data,
            relayout=relayout,
            spool=spool,
        )
        return figure, control, spool_out

    # Stamps the browser clock when a screen appears. Clientside so it never touches the server
    # clock, which would include network and cold-start time.
    # The origin travels with the reading: a reload restarts performance.now() at zero, and without
    # the origin a post-reload stamp is indistinguishable from a genuine one.
    #
    # It stamps a screen ONCE. A reload re-renders the same screen, and restamping it then would
    # measure from the reload -- a plausible, wrong undercount, which is exactly what happened
    # before this guard. Keeping the first stamp keeps its old origin, so `_elapsed` sees two
    # origins and records the duration absent and flagged `clock_reset`, as study-design section 6
    # says it must.
    app.clientside_callback(
        CLOCK_JS,
        Output("task-clock", "data"),
        Input("page", "children"),
        State("session-state", "data"),
        State("task-clock", "data"),
    )

    # Stamps the browser clock when Submit is pressed, and *this* is what triggers the server
    # callback above. Chaining that way means the timestamp is taken in the browser before the
    # request leaves, so no network or cold-start time can leak into the measurement.
    app.clientside_callback(
        SUBMIT_CLOCK_JS,
        Output("submit-clock", "data"),
        Input("submit-button", "n_clicks"),
        prevent_initial_call=True,
    )

    # Disable Submit the moment it is pressed. Two rapid clicks send two requests that both read the
    # same pre-click session state, so no server-side check can tell them apart; stopping the second
    # click in the browser is the only complete guard. The database's unique index is the backstop.
    app.clientside_callback(
        SUBMIT_DISABLE_JS,
        Output("submit-button", "disabled"),
        Input("submit-button", "n_clicks"),
        prevent_initial_call=True,
    )

    # ...and re-enable it when the step is refused. A refusal ("Please choose an answer") does not
    # re-render the screen, so without this the participant would be left with a dead button.
    app.clientside_callback(
        SUBMIT_ENABLE_JS,
        Output("submit-button", "disabled", allow_duplicate=True),
        Input("flow-error", "children"),
        prevent_initial_call=True,
    )

    # Continue gets the same guard as Submit. A double-click sent two registrations for one ID,
    # and before `db.register_participant` looked the ID up first, the second burned a sequence
    # number and skipped the next participant's counterbalancing cell. The lookup is the fix; this
    # stops the duplicate request being sent at all. Re-enabled by a refusal or the watchdog.
    app.clientside_callback(
        PARTICIPANT_DISABLE_JS,
        Output("participant-button", "disabled"),
        Input("participant-button", "n_clicks"),
        Input("participant-input", "n_submit"),
        prevent_initial_call=True,
    )
    app.clientside_callback(
        PARTICIPANT_ENABLE_JS,
        Output("participant-button", "disabled", allow_duplicate=True),
        Input("flow-error", "children"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        CONSENT_CLOCK_JS,
        Output("consent-clock", "data"),
        Input("consent-button", "n_clicks"),
        prevent_initial_call=True,
    )


# --- Clientside JavaScript ------------------------------------------------------------------------
#
# Module constants so tests can assert on them; nothing in the suite runs a browser.

# `screen` names what is on screen. `session-state` is written by the same response that wrote
# `page`, so it already describes the new screen when this runs.
CLOCK_JS = """function(_, session, previous) {
    var s = session || {};
    var screen = [s.participant_id, s.condition_index, s.stage, s.task_index].join("/");
    if (previous && previous.screen === screen) {
        return window.dash_clientside.no_update;
    }
    return {t: window.performance.now(), origin: window.performance.timeOrigin, screen: screen};
}"""

SUBMIT_CLOCK_JS = """function(n) {
    if (!n) { return window.dash_clientside.no_update; }
    return {t: window.performance.now(), origin: window.performance.timeOrigin};
}"""

# The watchdog re-enables the button if no response ever arrives (a killed function, a dropped
# connection), so a lost request can never strand a participant. By the time it fires on a
# successful step the screen has been replaced, and re-enabling a fresh button is harmless.
SUBMIT_DISABLE_JS = """function(n) {
    if (!n) { return window.dash_clientside.no_update; }
    window.setTimeout(function () {
        window.dash_clientside.set_props("submit-button", {disabled: false});
    }, 15000);
    return true;
}"""

SUBMIT_ENABLE_JS = """function(message) {
    return message ? false : window.dash_clientside.no_update;
}"""

# The watchdog is longer than Submit's: assignment retries under the FULL policy before refusing,
# which took ~11 s against an unreachable database (an 8 s budget, plus a 5 s connect attempt that
# starts just inside it). The refusal re-enables the button; this only covers a lost response.
PARTICIPANT_DISABLE_JS = """function(n, nSubmit) {
    if (!n && !nSubmit) { return window.dash_clientside.no_update; }
    window.setTimeout(function () {
        window.dash_clientside.set_props("participant-button", {disabled: false});
    }, 25000);
    return true;
}"""

PARTICIPANT_ENABLE_JS = """function(message) {
    return message ? false : window.dash_clientside.no_update;
}"""

CONSENT_CLOCK_JS = """function(n) {
    return n ? new Date().toISOString() : window.dash_clientside.no_update;
}"""


def _elapsed(started_at: Any, submitted_at: Any) -> tuple[float | None, str | None]:
    """Browser-measured milliseconds on task, and why the value is absent when it is.

    Stamps are `{"t": performance.now(), "origin": performance.timeOrigin}`; bare numbers are
    accepted as readings from an unknown but shared clock. The server only subtracts.

    Returns `(None, reason)` whenever the result cannot be trusted, because a missing value must be
    visibly absent rather than silently wrong:

    - `"missing"` — a stamp was never taken.
    - `"clock_reset"` — the two stamps come from different page loads. A reload restarts
      `performance.now()` at zero, so the difference would be a plausible, wrong undercount.
    - `"negative"` — the stores are out of step; a monotonic clock cannot run backwards.
    """
    start, start_origin = _reading(started_at)
    end, end_origin = _reading(submitted_at)
    if start is None or end is None:
        return None, "missing"
    if start_origin is not None and end_origin is not None and start_origin != end_origin:
        return None, "clock_reset"
    elapsed = end - start
    if elapsed < 0:
        return None, "negative"
    return round(elapsed, 3), None


def _reading(stamp: Any) -> tuple[float | None, float | None]:
    """Split a clock stamp into (time, origin). Unrecognised shapes read as missing."""
    if isinstance(stamp, bool):
        return None, None
    if isinstance(stamp, int | float):
        return float(stamp), None
    if isinstance(stamp, dict) and isinstance(stamp.get("t"), int | float):
        origin = stamp.get("origin")
        return float(stamp["t"]), float(origin) if isinstance(origin, int | float) else None
    return None, None


def _assign(participant_id: str) -> tuple[str, str]:
    """Counterbalanced assignment, from the database when configured.

    Without a database (local development) fall back to a deterministic hash so a given ID always
    gets the same cell and local walkthroughs are reproducible.
    """
    if db.configured():
        # The one database call that must not degrade: inventing an assignment locally would break
        # the sequence-based counterbalancing. Retry -- no task clock runs on this screen, so the
        # wait costs nothing measured -- then stop with a message the participant can act on.
        try:
            _seq, condition, form = call_with_retry(
                lambda: db.register_participant(participant_id), FULL
            )
        except db.DatabaseError as exc:
            print(f"[study] assignment failed: {exc}", file=sys.stderr)
            raise flow.FlowError(
                "We could not start your session. Please wait a moment and press Continue again."
            ) from exc
        return condition, form
    return db.assignment_for(sum(participant_id.encode()) % 4)


# Module-level so Vercel and the local dev server share one instance. Building it at import time
# also means a warm serverless container skips the work entirely.
#
# `server` is the deployment entrypoint, pinned by `tool.vercel.entrypoint = "src.app:server"`.
# This matters: Vercel auto-detects `src/app.py` (its patterns include `app.py` inside `src/`) and
# looks there for a FLASK instance named `app` — but `app` here is a dash.Dash. It happens to be
# WSGI-callable because Dash.__call__ proxies to the backend, but relying on that is a trap.
app = create_app()
server = app.server


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the study locally.")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    sink = "Postgres" if db.configured() else f"JSONL under {config.STUDY_LOGS_DIR}"
    print(f"Logging to: {sink}")
    print(f"Open http://127.0.0.1:{args.port}/")
    app.run(debug=bool(os.environ.get("DASH_DEBUG")), port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["app", "server", "create_app", "render", "step"]
