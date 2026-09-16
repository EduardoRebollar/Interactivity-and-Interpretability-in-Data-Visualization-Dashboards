"""Dash entry point and study flow wiring. No pandas — this ships to production.

Run locally:
    uv run python -m src.app          # http://127.0.0.1:8050

The condition and form come from per-session state, never from `config.INTERACTIVE`: one URL serves
both conditions, so a module-level flag would be shared across concurrent participants.

`server` is the deployment entrypoint, pinned by `tool.vercel.entrypoint = "src.app:server"`.

**Timing is measured in the browser.** Each event is its own HTTP request, so a server clock would
fold network latency and cold starts into task duration — a dependent variable. Clientside callbacks
stamp `performance.now()` at screen render and at submit; the server only subtracts them.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import dash
from dash import Input, Output, State, callback_context, dcc, html, no_update

from src import config, db, figures, flow, layout, tasks
from src.flow import SessionState, Stage
from src.logging import StudyLogger

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
            dcc.Store(id="submit-clock", storage_type="session"),
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


def _logger(
    state: SessionState, log: dict[str, Any] | None, log_dir: Path | None = None
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
    log_dir: Path | None = None,
) -> tuple[Any, Any, Any, str]:
    """Advance the session one click. Returns (session state, log state, screen, error message).

    Any of the first three may be `dash.no_update`, which leaves that store untouched — that is how
    a validation failure re-renders nothing and only fills the error slot.
    """
    state = SessionState.from_dict(stored)
    log_state = dict(log_state or {})

    def refuse(message: str) -> tuple[Any, Any, Any, str]:
        return (no_update, no_update, no_update, message)

    try:
        if triggered == "consent-button":
            state = flow.give_consent(state)

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
            logger = _logger(state, {}, log_dir)
            logger.event(
                "condition_start",
                interactive=flow.is_interactive(state),
                condition_order=flow.condition_order(state),
            )
            log_state = {"session_id": logger.session_id}

        elif triggered == "resume-button":
            state = flow.resume_after_break(state)

        elif triggered == "submit-clock":
            if not answer:
                return refuse("Please choose an answer.")
            if not (justification or "").strip():
                return refuse("Please say briefly how you decided.")

            logger = _logger(state, log_state, log_dir)
            open_task = log_state.pop("task_id", None)
            if state.stage is Stage.PRACTICE:
                # Recorded like any other answer under task_id "P0". Not scored — analysis drops
                # P0 — but the timing and the justification are still worth having.
                logger.submit_answer(
                    tasks.PRACTICE.task_id,
                    answer=answer,
                    justification=justification.strip(),
                    duration_ms=duration_ms,
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
                )
                state = flow.complete_task(state, items)
            # Closes the span opened when this screen appeared, so the interaction events in
            # between are bracketed by the task they happened on.
            if open_task is not None:
                logger.end_task(duration_ms=duration_ms)
            log_state["session_id"] = logger.session_id

        elif triggered == "load-button":
            if load is None:
                return refuse("Please choose a number.")
            # `condition_index` advances in `flow.submit_load`, below — so the state here still
            # names the condition being rated, and no rewind is needed to find it.
            logger = _logger(state, log_state, log_dir)
            logger.rate_load(int(load))
            logger.event(
                "condition_end",
                interactive=flow.is_interactive(state),
                condition_order=flow.condition_order(state),
            )
            # Closed at the end of BOTH conditions. Closing only at COMPLETE left every participant
            # with one session carrying a session_end and one without.
            logger.close()
            log_state = {}
            state = flow.submit_load(state)

    except flow.FlowError as exc:
        return refuse(str(exc))

    log_state = _open_task(state, log_state, log_dir)
    return state.to_dict(), log_state, render(state), ""


def _open_task(
    state: SessionState, log_state: dict[str, Any], log_dir: Path | None
) -> dict[str, Any]:
    """Emit `task_start` for the task now on screen, and remember that it is open.

    The span is opened here, where the screen is built, rather than on the next click — so the
    interaction events a participant generates while reading fall inside their task rather than
    being attributed to the one before.
    """
    task = _active_task(state)
    if task is None or not log_state.get("session_id") or log_state.get("task_id"):
        return log_state
    logger = _logger(state, {**log_state, "task_id": None}, log_dir)
    logger.start_task(task.task_id)
    return {**log_state, "task_id": task.task_id}


# --- The interactive controls ---------------------------------------------------------------------
#
# Filtering, sorting, line isolation and zoom/pan. These exist ONLY in the interactive condition —
# the static condition never renders the controls and `staticPlot: True` means its chart emits no
# click or relayout data — so every event below is, by construction, an interactive-condition event.
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
    log_dir: Path | None = None,
) -> tuple[Any, Any, Any, Any]:
    """Apply one control interaction. Returns (figure, filter options, filter value, control state).

    `triggered` is a Dash **prop id** — "chart.clickData", not "chart". The chart raises two
    different inputs and the component id alone cannot tell them apart: `clickData` stays set on the
    component after a click, so a later zoom arrives with a stale `click_data` still populated and
    would be read as the participant clicking the same line a second time. The property name is the
    only thing that distinguishes them.

    Returns `no_update` throughout when nothing actually changed. Dash fires input callbacks when a
    component is recreated, which happens on every task render, and logging those would fill the
    interaction record with events no participant caused.
    """
    state = SessionState.from_dict(stored)
    task = _active_task(state)
    if task is None:
        return (no_update,) * 4

    options = layout.filterable(list(task.entities))
    control = {"selected": list(options), "sort": "listed", "isolated": None}
    control.update(control_state or {})
    # A stale store from the previous task would name entities this one does not have.
    control["selected"] = [e for e in control["selected"] if e in options] or list(options)
    if control["isolated"] not in task.entities:
        control["isolated"] = None

    unchanged: tuple[Any, ...] = (no_update,) * 4
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

    if event is not None:
        name, payload = event
        _logger(state, log_state, log_dir).event(name, task_id=task.task_id, **payload)

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
    return figure, filter_options, list(control["selected"]), control


# --- Callbacks ------------------------------------------------------------------------------------


def _register_callbacks(app: dash.Dash) -> None:
    @app.callback(
        Output("page", "children"),
        Input("url", "pathname"),
        State("session-state", "data"),
    )
    def show_page(_pathname, stored):
        return render(SessionState.from_dict(stored))

    @app.callback(
        Output("session-state", "data"),
        Output("log-state", "data"),
        Output("page", "children", allow_duplicate=True),
        # One error slot, emitted by `layout.page` on every screen. Outputs that exist on only some
        # screens are a latent failure on the rest; see the note in `layout.page`.
        Output("flow-error", "children"),
        Input("consent-button", "n_clicks"),
        Input("participant-button", "n_clicks"),
        Input("begin-button", "n_clicks"),
        Input("resume-button", "n_clicks"),
        # Triggered by the submit CLOCK, not the button: the clientside callback below stamps the
        # browser time first, so by the time this runs the timestamp is guaranteed fresh rather
        # than racing the button click.
        Input("submit-clock", "data"),
        Input("load-button", "n_clicks"),
        State("session-state", "data"),
        State("log-state", "data"),
        State("participant-input", "value"),
        State("answer-input", "value"),
        State("justification-input", "value"),
        State("load-input", "value"),
        State("task-clock", "data"),
        prevent_initial_call=True,
    )
    def advance(
        _c,
        _p,
        _b,
        _r,
        submitted_at,
        _l,
        stored,
        log_state,
        participant_id,
        answer,
        justification,
        load,
        started_at,
    ):
        """Thin wrapper: unpack Dash's arguments and hand them to `step`, which holds the logic."""
        return step(
            callback_context.triggered_id,
            stored,
            log_state,
            participant_id=participant_id,
            answer=answer,
            justification=justification,
            load=load,
            duration_ms=_elapsed(started_at, submitted_at),
        )

    @app.callback(
        Output("chart", "figure"),
        Output("entity-filter", "options"),
        Output("entity-filter", "value"),
        Output("control-state", "data"),
        Input("entity-filter", "value"),
        Input("entity-sort", "value"),
        Input("chart", "clickData"),
        Input("chart", "relayoutData"),
        Input("reset-view", "n_clicks"),
        State("session-state", "data"),
        State("log-state", "data"),
        State("control-state", "data"),
        prevent_initial_call=True,
    )
    def controls(selected, sort_key, click_data, relayout, _reset, stored, log, control_state):
        """Thin wrapper over `control_step`.

        Interactive condition only: the static condition renders none of these components, so this
        callback has nothing to fire on there.

        Passes the **prop id**, not `triggered_id`: the chart raises both `clickData` and
        `relayoutData`, and the component id alone cannot separate a zoom from a stale click.
        """
        fired = callback_context.triggered
        return control_step(
            fired[0]["prop_id"] if fired else None,
            stored,
            log,
            control_state,
            selected=selected,
            sort_key=sort_key,
            click_data=click_data,
            relayout=relayout,
        )

    # Stamps the browser clock when a screen appears. Clientside so it never touches the server
    # clock, which would include network and cold-start time.
    app.clientside_callback(
        "function(_) { return window.performance.now(); }",
        Output("task-clock", "data"),
        Input("page", "children"),
    )

    # Stamps the browser clock when Submit is pressed, and *this* is what triggers the server
    # callback above. Chaining that way means the timestamp is taken in the browser before the
    # request leaves, so no network or cold-start time can leak into the measurement.
    app.clientside_callback(
        "function(n) { return n ? window.performance.now() : window.dash_clientside.no_update; }",
        Output("submit-clock", "data"),
        Input("submit-button", "n_clicks"),
        prevent_initial_call=True,
    )


def _elapsed(started_at: float | None, submitted_at: float | None) -> float | None:
    """Browser-measured milliseconds on task.

    Both timestamps come from the same `performance.now()` clock in the participant's browser; the
    server only subtracts them. Returns None when either is missing, because a missing value must
    be visibly absent in the data rather than silently recorded as zero.
    """
    if started_at is None or submitted_at is None:
        return None
    elapsed = submitted_at - started_at
    # A monotonic clock cannot go backwards; a negative value means the stores are out of step.
    return round(elapsed, 3) if elapsed >= 0 else None


def _assign(participant_id: str) -> tuple[str, str]:
    """Counterbalanced assignment, from the database when configured.

    Without a database (local development) fall back to a deterministic hash so a given ID always
    gets the same cell and local walkthroughs are reproducible.
    """
    if db.configured():
        _seq, condition, form = db.register_participant(participant_id)
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
