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
from typing import Any

import dash
from dash import Input, Output, State, callback_context, dcc, html, no_update

from src import config, db, flow, layout, tasks
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
    """The screen for the current stage. Pure: stage in, layout out."""
    if state.stage is Stage.CONSENT:
        return layout.consent_screen(CONSENT_TEXT)
    if state.stage is Stage.PARTICIPANT_ID:
        return layout.participant_screen()
    if state.stage is Stage.INSTRUCTIONS:
        return layout.instructions_screen(flow.is_interactive(state), practice=True)
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


def _logger(state: SessionState, log: dict[str, Any] | None) -> StudyLogger:
    """Rebuild the logger for this request from browser-held session state.

    Serverless containers do not persist between callbacks, so the logger is reconstructed each
    time and resumed via `session_id` rather than held in memory.
    """
    log = log or {}
    return StudyLogger(
        state.participant_id or "unknown",
        condition_order=flow.condition_order(state),
        interactive=flow.is_interactive(state),
        form=flow.current_form(state),
        session_id=log.get("session_id"),
        task_id=log.get("task_id"),
    )


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
        Output("participant-error", "children"),
        Output("task-error", "children"),
        Output("load-error", "children"),
        Input("consent-button", "n_clicks"),
        Input("participant-button", "n_clicks"),
        Input("begin-button", "n_clicks"),
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
        triggered = callback_context.triggered_id
        state = SessionState.from_dict(stored)
        log_state = dict(log_state or {})
        duration = _elapsed(started_at, submitted_at)

        try:
            if triggered == "consent-button":
                state = flow.give_consent(state)

            elif triggered == "participant-button":
                if not (participant_id or "").strip():
                    return (no_update,) * 3 + ("Please enter your participant ID.", "", "")
                condition, form = _assign(participant_id.strip())
                state = flow.set_participant(state, participant_id.strip(), condition, form)

            elif triggered == "begin-button":
                state = flow.begin_tasks(state)
                logger = _logger(state, log_state)
                logger.event(
                    "condition_start",
                    interactive=flow.is_interactive(state),
                    condition_order=flow.condition_order(state),
                )
                log_state = {"session_id": logger.session_id}

            elif triggered == "submit-clock":
                if not answer:
                    return (no_update,) * 3 + ("", "Please choose an answer.", "")
                if not (justification or "").strip():
                    return (no_update,) * 3 + ("", "Please say briefly how you decided.", "")

                items = tasks.for_form(flow.current_form(state))
                task = flow.current_task(state, items)
                logger = _logger(state, log_state)
                logger.submit_answer(
                    task.task_id,
                    answer=answer,
                    justification=justification.strip(),
                    duration_ms=duration,
                )
                log_state["session_id"] = logger.session_id

                # Last task of the condition goes to the load rating, not straight to the break.
                if state.task_index + 1 >= len(items):
                    state = flow.complete_task(state, items)
                    return (
                        state.to_dict(),
                        log_state,
                        layout.load_screen(tasks.LOAD_PROMPT, tasks.LOAD_ANCHORS),
                        "",
                        "",
                        "",
                    )
                state = flow.complete_task(state, items)

            elif triggered == "load-button":
                if load is None:
                    return (no_update,) * 3 + ("", "", "Please choose a number.")
                # The state has already advanced past the tasks, so report the condition just
                # finished rather than the one about to start.
                finished = (
                    SessionState.from_dict({**state.to_dict(), "condition_index": 0})
                    if state.stage is Stage.BREAK
                    else state
                )
                logger = _logger(finished, log_state)
                logger.rate_load(int(load))
                logger.event(
                    "condition_end",
                    interactive=flow.is_interactive(finished),
                    condition_order=flow.condition_order(finished),
                )
                if state.stage is Stage.COMPLETE:
                    logger.close()
                log_state = {}

        except flow.FlowError as exc:
            return (no_update,) * 3 + ("", str(exc), "")

        return state.to_dict(), log_state, render(state), "", "", ""

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


__all__ = ["app", "server", "create_app", "render"]
