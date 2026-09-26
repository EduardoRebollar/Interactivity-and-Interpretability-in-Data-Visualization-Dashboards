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
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, NamedTuple

import dash
from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src import config, consent, db, figures, flow, layout, tasks
from src.flow import SessionState, Stage
from src.logging import FULL, NO_RETRY, LogError, RetryPolicy, StudyLogger, call_with_retry

# The consent form's wording, and its hash, live in src/consent.py (docs/study-design.md section 9).
CONSENT_TEXT = consent.CONSENT_TEXT
CONSENT_VERSION = consent.CONSENT_VERSION

# Shown when the signed consent could not be stored. The participant stays on the consent screen:
# the session must not continue on a consent that was not recorded (IRB form item 12B).
CONSENT_UNSAVED = (
    "We could not record your consent. Please wait a moment and press "
    '"I agree to participate" again.'
)

# The participant-ID screen's refusal of an empty ID (the handoff's S2), which marks the field.
ID_MISSING = "Please enter your participant ID."

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
            # The drawn signature, written by src/assets/signature.js. Memory, so a signature never
            # outlives the page it was drawn on, and never sits in sessionStorage.
            dcc.Store(id="signature-strokes"),
            # The participant's own signed copy of the consent form, and the component that hands
            # it to them. Memory: identifying, so it is not kept a moment longer than the page.
            dcc.Store(id="consent-copy"),
            dcc.Download(id="consent-download"),
            # Continue on the demographics and survey screens. Like submit-clock: written only
            # once the browser has confirmed any skipped questions; memory, so a reload cannot
            # fire it.
            dcc.Store(id="demographics-clock"),
            dcc.Store(id="survey-clock"),
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


# The page's background behind each stage's screen, as the design handoff's Screens file draws it:
# none behind a chart, a slow sand fade on the other screens, and a warmer one at the practice's
# end, the break and the finish. Its README calls the survey and About you plain; the Screens file
# outranks it (docs/study-redesign.md section 1).
SCREEN_BACKGROUND = {
    Stage.CONSENT: "deco",
    Stage.DECLINED: "deco",
    Stage.PARTICIPANT_ID: "deco",
    Stage.INSTRUCTIONS: "deco",
    Stage.PRACTICE: "plain",
    Stage.PRACTICE_COMPLETE: "celebrate",
    Stage.TASK: "plain",
    Stage.LOAD: "deco",
    Stage.BREAK: "celebrate",
    Stage.DEMOGRAPHICS: "deco",
    Stage.COMPLETE: "celebrate",
}


def render(state: SessionState) -> html.Div:
    """The screen for the current stage, in the shell: header, stepper, background. Pure: stage in,
    layout out.

    Total over `Stage` — every member has a screen and a background, and `tests/test_app.py` proves
    it, so adding a stage without one fails the suite rather than a participant's session.
    """
    return layout.shell(flow.step_index(state), SCREEN_BACKGROUND[state.stage], _screen(state))


def _screen(state: SessionState) -> html.Main:
    """The current stage's screen, without the shell."""
    if state.stage is Stage.CONSENT:
        return layout.consent_screen()
    if state.stage is Stage.DECLINED:
        return layout.declined_screen()
    if state.stage is Stage.PARTICIPANT_ID:
        return layout.participant_screen()
    if state.stage is Stage.DEMOGRAPHICS:
        return layout.demographics_screen()
    if state.stage is Stage.PRACTICE_COMPLETE:
        return layout.practice_complete_screen()
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
        # The controls are rated after the interactive condition only, and the two versions compared
        # after the second only (docs/study-design.md section 6.1).
        return layout.load_screen(
            interactive=flow.is_interactive(state), second_half=state.condition_index == 1
        )
    if state.stage is Stage.BREAK:
        return layout.break_screen()
    if state.stage is Stage.COMPLETE:
        return layout.complete_screen(state.participant_id)
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
    survey: dict[str, Any] | None = None,
    demographics: dict[str, Any] | None = None,
    duration_ms: float | None = None,
    duration_invalid: str | None = None,
    consented_at: str | None = None,
    consent_record: dict[str, Any] | None = None,
    spool: dict[str, Any] | None = None,
    log_dir: Path | None = None,
    consent_dir: Path | None = None,
) -> tuple[Any, Any, Any, str, Any]:
    """Advance the session one click.

    Returns (session state, log state, screen, error message, spool). Any of them may be
    `dash.no_update`, which leaves that store untouched — that is how a validation failure
    re-renders nothing and only fills the error slot.

    **Any question may be skipped** (IRB form item 10). The browser asks the participant to confirm
    before a skip reaches here, so a missing answer, justification or rating is recorded as absent,
    never refused. Only consent and the participant ID are required.

    `survey` maps each survey item on screen to its value: "paas", a1-a9, and b1-b3 or c1-c3 where
    they are asked. `demographics` maps each About-you field on screen to its value, as
    `_demographic_answers` reads them.

    `consent_dir` is for tests, like `log_dir`; when only `log_dir` is given, consent records go to
    a `consent/` folder inside it, never beside the event files.
    """
    if consent_dir is None and log_dir is not None:
        consent_dir = log_dir / "consent"
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
            message = consent.problem(consent_record)
            if message:
                return refuse(message)
            # Transition first: a stale tab that is no longer on the consent screen must be refused
            # before a signed record is stored for it.
            state = flow.give_consent(state, consented_at, consent_record["signature_method"])
            # The signed record goes to its own store, never the event log, and it must be stored
            # before the participant moves on. Retried, because no task clock runs here.
            try:
                call_with_retry(lambda: consent.save(consent_record, consent_dir), FULL)
            except (db.DatabaseError, consent.ConsentError, OSError) as exc:
                print(f"[study] consent could not be stored: {exc}", file=sys.stderr)
                return refuse(CONSENT_UNSAVED)

        elif triggered == "decline-button":
            state = flow.decline(state)

        elif triggered == "reconsider-button":
            state = flow.reconsider(state)

        elif triggered == "participant-button":
            if not (participant_id or "").strip():
                return refuse(ID_MISSING)
            condition, form = _assign(participant_id.strip())
            state = flow.set_participant(state, participant_id.strip(), condition, form)

        elif triggered == "demographics-clock":
            # About you, at the very end (docs/study-design.md section 6.2). Transition first, so a
            # stale tab that is not on this screen is refused before anything is written; then read
            # every answer before writing any of them.
            finished = flow.submit_demographics(state)
            answers = _demographic_answers(demographics)
            # Into the second condition's session, which its survey has already closed: stopping
            # here must still leave two complete sessions.
            logger = _logger(state, log_state, log_dir, carried)
            logger.record_demographics(answers)
            carried.take(logger)
            state = finished
            log_state = {}

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
                logger.record_consent(state.consent_at, CONSENT_VERSION, state.consent_method)
            logger.event(
                "condition_start",
                interactive=flow.is_interactive(state),
                condition_order=flow.condition_order(state),
            )
            carried.take(logger)
            log_state = {"session_id": logger.session_id}

        elif triggered == "resume-button":
            state = flow.resume_after_break(state)

        elif triggered == "practice-done-button":
            state = flow.begin_tasks(state)

        elif triggered == "submit-clock":
            # No refusal for a blank answer or justification: the browser has already asked the
            # participant to confirm the skip, and `submit_answer` records it as such.
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
                    justification=justification,
                    duration_ms=duration_ms,
                    duration_invalid=duration_invalid,
                )
                state = flow.finish_practice(state)
            else:
                items = tasks.for_form(flow.current_form(state))
                task = flow.current_task(state, items)
                logger.submit_answer(
                    task.task_id,
                    answer=answer,
                    justification=justification,
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

        elif triggered == "survey-clock":
            # `condition_index` advances in `flow.submit_load`, below — so the state here still
            # names the condition being rated, and no rewind is needed to find it. A None rating
            # is a confirmed skip.
            if state.stage is not Stage.LOAD:
                raise flow.FlowError(f"Expected stage load, got {state.stage.value}")
            # Read every value before writing anything, so a malformed one refuses the step
            # without leaving half the survey in the log.
            answers = survey or {}
            paas = _rating(answers.get("paas"), 9)
            ratings = {key: _rating(answers.get(key), 7) for key in tasks.LIKERT_ITEMS}
            controls = (
                {key: _rating(answers.get(key), 7) for key in tasks.CONTROLS_ITEMS}
                if flow.is_interactive(state)
                else None
            )
            comparison = _comparison(answers) if flow.condition_order(state) == 2 else None
            logger = _logger(state, log_state, log_dir, carried)
            logger.rate_load(paas)
            logger.rate_survey(ratings)
            if controls is not None:
                logger.rate_controls(controls)
            if comparison is not None:
                logger.record_comparison(comparison)
            logger.event(
                "condition_end",
                interactive=flow.is_interactive(state),
                condition_order=flow.condition_order(state),
            )
            # Closed at the end of BOTH conditions. Closing only at COMPLETE left every participant
            # with one session carrying a session_end and one without.
            logger.close()
            carried.take(logger)
            state = flow.submit_load(state)
            # About you follows the second survey and is written into that session, so its id is
            # kept; after the first survey nothing more belongs to the session.
            log_state = (
                {"session_id": logger.session_id} if state.stage is Stage.DEMOGRAPHICS else {}
            )

    except flow.FlowError as exc:
        return refuse(str(exc))
    except (ValueError, TypeError) as exc:
        # A rating that is not a number cannot come from the radio buttons. Refuse, never crash.
        print(f"[study] malformed input in step {triggered!r}: {exc}", file=sys.stderr)
        return refuse("That answer could not be read. Please choose again.")
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


def consent_step(
    consented_at: str | None,
    name: str | None,
    signed_date: str | None,
    paper: list[str] | None,
    strokes: Any,
    stored: dict[str, Any] | None,
    log_state: dict[str, Any] | None,
    spool: dict[str, Any] | None,
    *,
    consent_dir: Path | None = None,
) -> tuple[Any, ...]:
    """ "I agree to participate": build the signed record, store it, advance.

    Returns `step`'s five outputs plus the participant's signed copy (HTML), which is `no_update`
    unless the record was actually stored and the session moved on.
    """
    record = consent.build_record(
        consented_at, name, signed_date, strokes, paper=bool(paper and "paper" in paper)
    )
    outputs = step(
        "consent-clock",
        stored,
        log_state,
        consented_at=consented_at,
        consent_record=record,
        spool=spool,
        consent_dir=consent_dir,
    )
    advanced = outputs[0] is not no_update
    return (*outputs, consent.copy_html(record) if advanced else no_update)


def _rating(value: Any, top: int) -> int | None:
    """A radio value as a point on a 1-`top` scale. None stays None: that is a skip, not a zero.

    A value off the scale cannot come from the radio buttons. It is refused here, as a ValueError,
    before anything is written -- not left for the logger to reject after the survey is half in.
    """
    if value is None:
        return None
    if isinstance(value, bool) or int(value) != value or not 1 <= int(value) <= top:
        raise ValueError(f"{value!r} is not on a 1-{top} scale")
    return int(value)


# The About-you "Other" boxes: long enough for any answer, short enough that nothing pasted in can
# swell the log.
MAX_OTHER = 200

AGE_MESSAGE = "Please enter your age as a whole number from 18 to 99, or tick Prefer not to say."


def _text(value: Any, limit: int) -> str | None:
    """Typed text, trimmed and capped. Blank is None: a skip, not an empty answer."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"expected text, got {value!r}")
    return value.strip()[:limit] or None


def _comparison(raw: dict[str, Any]) -> dict[str, str | None]:
    """c1 and c2, each one of the offered options or None, and c3's free text."""
    answers: dict[str, str | None] = {}
    for key in tasks.COMPARISON_CHOICES:
        value = raw.get(key)
        if value is not None and value not in tasks.COMPARISON_OPTIONS:
            raise flow.FlowError("Unrecognised answer. Please choose again.")
        answers[key] = value
    answers[tasks.COMPARISON_TEXT_KEY] = _text(raw.get(tasks.COMPARISON_TEXT_KEY), tasks.MAX_TEXT)
    return answers


def _age(raw: dict[str, Any]) -> int | str | None:
    """B1: a whole number in `tasks.AGE_RANGE`, "Prefer not to say" when its box is ticked, or None.

    The only About-you answer typed as a number. Anything else is refused with a message the
    participant can act on, rather than stored: an age of 7 or 700 cannot be analysed.
    """
    if raw.get("age_prefer_not"):
        return tasks.PREFER_NOT
    value = raw.get("age")
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise flow.FlowError(AGE_MESSAGE) from None
    low, high = tasks.AGE_RANGE
    if isinstance(value, bool) or number != int(number) or not low <= number <= high:
        raise flow.FlowError(AGE_MESSAGE)
    return int(number)


def _demographic_answers(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Every About-you key (`tasks.DEMOGRAPHIC_KEYS`), each an offered option or None (skipped).

    `raw` maps each field on screen to its value: a question's key, `<key>_other` for the text
    beside "Other", `age` and `age_prefer_not`, and `tools/<tool>` for each row of the tools matrix.

    A value that is not one of the options cannot come from the radio buttons, so it is refused
    rather than stored: this is study data, and an unrecognised category cannot be analysed. Text
    typed beside "Other" is kept only when "Other" is the answer.
    """
    raw = raw or {}
    answers: dict[str, Any] = {}
    for question in tasks.ABOUT_QUESTIONS:
        if question.kind == "age":
            answers[question.key] = _age(raw)
        elif question.kind == "matrix":
            rows = {}
            for row in question.rows:
                value = raw.get(f"{question.key}/{row}")
                if value is not None and value not in question.options:
                    raise flow.FlowError(f"Unrecognised answer for {row}. Please choose again.")
                rows[row] = value
            answers[question.key] = rows
        else:
            value = raw.get(question.key)
            if value is not None and value not in question.options:
                raise flow.FlowError(
                    f"Unrecognised answer for {question.code}. Please choose again."
                )
            answers[question.key] = value
            if question.other_key is not None:
                typed = _text(raw.get(question.other_key), MAX_OTHER)
                answers[question.other_key] = typed if value == tasks.OTHER else None
    return answers


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
# The country chips on every chart; the line chart's View, Show all, legend and line clicks; the bar
# and heatmap sorts; the map's highlight; Reset view; zoom and pan (visual-spec.md section 7). They
# exist ONLY in the interactive condition -- the static condition renders none of the controls, and
# `staticPlot: True` means its chart can be neither clicked nor zoomed -- so every event below is,
# by construction, an interactive-condition event. The static chart does still send Plotly's
# render-time relayout, which carries no axis range and is ignored below exactly as it is in the
# interactive condition. That is the study's independent variable, and this is where it gets
# recorded. Hovers are not logged (decided 2026-09-21).

# Zoom and pan arrive as axis-range keys. Plotly also sends relayout on resize and on render, which
# is not a participant action and must not be logged as one.
_VIEW_KEYS = ("xaxis.range", "yaxis.range", "xaxis.autorange", "yaxis.autorange")

# The controls under the chart, by the `control` of their pattern id (`layout.control_id`). The
# chart's own events are named by their prop id: "chart.clickData", "chart.relayoutData" and
# "chart.restyleData" (a legend click).
CONTROLS = ("chips", "sort", "show-all", "threshold", "reset")

# `sort_change.direction` for each sort key: which way the new order runs.
_SORT_DIRECTION = {
    "listed": "none",
    "coverage": "desc",
    "alpha": "none",
    "desc": "desc",
    "asc": "asc",
    "default": "none",
    "min": "asc",
    "mean": "asc",
}


class ControlResult(NamedTuple):
    """What one control interaction changes. Any field may be `no_update`.

    `chips` is a list of rows, each {"options", "value"}, as `layout.chip_rows` makes them.
    `group` is the Countries group rebuilt, when the chips' order changed (`layout.chip_group`
    says why a reorder cannot be sent as new options). `sort` and `threshold` are the values the
    sort control and the highlight box must be set to, which only Reset view, and a refused box,
    ever change.
    """

    figure: Any
    chips: Any
    group: Any
    sort: Any
    threshold: Any
    control: Any
    spool: Any


UNCHANGED = ControlResult(*(no_update,) * 7)


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
    survives filtering only because hidden series are made invisible rather than removed -- see
    `figures.set_visible`.
    """
    points = (click_data or {}).get("points") or []
    if not points:
        return None
    index = points[0].get("curveNumber")
    if not isinstance(index, int) or not 0 <= index < len(task.entities):
        return None
    return task.entities[index]


def _legend_change(restyle: Any, task, shown: list[str]) -> tuple[list[str], str] | None:
    """The countries a legend click leaves on the chart, and the click as a `filter_change` action.

    Plotly reports it as `restyleData`: `[{"visible": [...]}, [trace indices]]`, one value per
    index, or one value for them all. A single index is a click, hiding or showing that line; more
    than one is a double click, which shows one line alone ("only") or, on the only line left,
    brings every line back. World has no legend entry, so it never counts. None when the payload
    changes no line's visibility.
    """
    if not isinstance(restyle, (list, tuple)) or len(restyle) != 2:
        return None
    update, indices = restyle
    if not isinstance(update, dict) or "visible" not in update or not isinstance(indices, list):
        return None
    values = update["visible"]
    if not isinstance(values, list):
        values = [values] * len(indices)
    elif len(values) == 1 and len(indices) > 1:
        values = values * len(indices)
    if len(values) != len(indices):
        return None
    after = set(shown)
    for index, value in zip(indices, values, strict=True):
        if not isinstance(index, int) or not 0 <= index < len(task.entities):
            return None
        name = task.entities[index]
        if value is True or value == "true":
            after.add(name)
        else:
            after.discard(name)
    options = layout.filterable(list(task.entities))
    result = [name for name in options if name in after]
    if len(indices) == 1:
        action = "show" if len(result) > len(shown) else "hide"
    else:
        action = "only" if len(result) == 1 else "show"
    return result, action


def _threshold(raw: Any) -> tuple[bool, int | None]:
    """The highlight box's value: (True, a whole number 0-100), (True, None) when the box is empty,
    or (False, None) for anything else. A typed decimal is rounded to the nearest whole number, the
    box's step."""
    if raw is None or raw == "":
        return True, None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return False, None
    if not 0 <= value <= 100:
        return False, None
    return True, int(value + 0.5)


def _shown(control: dict[str, Any]) -> list[str]:
    """The countries on the chart: the isolated line alone, or every ticked chip."""
    return [control["isolated"]] if control["isolated"] else list(control["selected"])


def _view_figure(task, control: dict[str, Any]):
    """The task's figure with the participant's current view applied.

    Built fresh, then sorted, hidden or faded -- never rebuilt from a shorter list, which would
    recolour what remains. The view functions in `src/figures.py` say why. Rows are sorted before
    any are faded, because a faded row is covered where it is drawn.
    """
    figure = figures.task_figure(task)
    if control.get("xrange"):
        # The participant's zoom, kept through every redraw (see `_zoomed_range`).
        figure.update_xaxes(range=control["xrange"])
    shown = _shown(control)
    if task.chart == "line" and "World" in task.entities:
        shown.append("World")
    if task.chart == "bar":
        figures.sort_bars(figure, control["sort"])
    elif task.chart == "heatmap":
        figures.sort_rows(figure, control["sort"])
    figures.set_visible(figure, shown)
    if task.chart == "line":
        order = _chip_order(task, control) if control["sort"] == "coverage" else None
        figures.order_legend(figure, order)
    elif task.chart == "map":
        figures.set_threshold(figure, control["threshold"])
    return figure


def _chip_order(task, control: dict[str, Any]) -> list[str]:
    """The chips' order: the task's own, or, on a line chart viewed by coverage, highest first."""
    options = layout.filterable(list(task.entities))
    if task.chart != "line":
        return options
    return layout.sorted_entities(options, task.vaccine, control["sort"])


def _fresh_control(task, screen: str) -> dict[str, Any]:
    """The view a task's chart opens on: every country, the first sort, no highlight."""
    return {
        "screen": screen,
        "selected": layout.filterable(list(task.entities)),
        "isolated": None,
        "sort": layout.default_sort(task.chart),
        "threshold": None,
        "xrange": None,
    }


def _stored_control(task, screen: str, control_state: dict[str, Any] | None) -> dict[str, Any]:
    """The view held in the `control-state` store, if it belongs to this task in this half.

    The store outlives the screen. Any other key -- the previous task, the same task id in the other
    condition, or none -- is discarded, which is what gives every task the fresh view its screen was
    rendered with. What survives is checked against this task, so a malformed store cannot name a
    country, sort or highlight the chart does not have.
    """
    control = _fresh_control(task, screen)
    stored = control_state or {}
    if stored.get("screen") != screen:
        return control
    options = control["selected"]
    stored_selected = stored.get("selected")
    # A list, never a string: `"China" in "China"` would pass a string off as a choice.
    ticked = stored_selected if isinstance(stored_selected, list) else []
    control["selected"] = [e for e in options if e in ticked] or list(options)
    if stored.get("isolated") in options and task.chart == "line":
        control["isolated"] = stored["isolated"]
    sorts = [value for value, _label in layout.SORTS.get(task.chart, ("", ()))[1]]
    if stored.get("sort") in sorts:
        control["sort"] = stored["sort"]
    valid, threshold = _threshold(stored.get("threshold"))
    if task.chart == "map" and valid and threshold is not None and threshold < 100:
        control["threshold"] = threshold
    if task.chart == "line":
        control["xrange"] = _range(stored.get("xrange"))
    return control


def _range(raw: Any) -> list[float] | None:
    """An axis range as [low, high], low below high, or None if it is not one."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw):
        return None
    low, high = (float(value) for value in raw)
    return [low, high] if math.isfinite(low) and math.isfinite(high) and low < high else None


def _zoomed_range(relayout: dict[str, Any]) -> tuple[bool, list[float] | None]:
    """What a relayout does to the line chart's x axis: (True, a range) for a zoom or pan, (True,
    None) when Plotly's own reset puts it back, (False, None) when it says nothing about it."""
    if relayout.get("xaxis.autorange") is True:
        return True, None
    if "xaxis.range" in relayout:
        return True, _range(relayout["xaxis.range"])
    if "xaxis.range[0]" in relayout and "xaxis.range[1]" in relayout:
        return True, _range([relayout["xaxis.range[0]"], relayout["xaxis.range[1]"]])
    return False, None


def control_step(
    triggered: str | None,
    stored: dict[str, Any] | None,
    log_state: dict[str, Any] | None,
    control_state: dict[str, Any] | None,
    *,
    chips: list[str] | None = None,
    sort_key: str | None = None,
    threshold: Any = None,
    click_data: dict[str, Any] | None = None,
    relayout: dict[str, Any] | None = None,
    restyle: Any = None,
    spool: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> ControlResult:
    """Apply one control interaction; see `ControlResult` for what comes back.

    `triggered` is one of CONTROLS, or a chart event by its **prop id** -- "chart.clickData", not
    "chart". The chart raises several inputs and the component id alone cannot tell them apart:
    `clickData` stays set on the component after a click, so a later zoom arrives with a stale
    `click_data` still populated and would be read as the participant clicking the same line a
    second time. `chips` is every ticked chip, both rows together.

    Returns UNCHANGED when nothing actually changed. Dash fires input callbacks when a component is
    recreated, which happens on every task render, and logging those would fill the interaction
    record with events no participant caused.

    Some changes are refused: unticking the last chip, a legend click that would leave no line, a
    highlight that is not a number from 0 to 100. The browser has already moved the control by
    then, so a refusal puts it back rather than leaving it saying something the chart does not.
    Nothing is logged for one.
    """
    state = SessionState.from_dict(stored)
    task = _active_task(state)
    if task is None:
        return UNCHANGED

    screen = f"{state.condition_index}/{task.task_id}"
    control = _stored_control(task, screen, control_state)
    options = layout.filterable(list(task.entities))
    default_sort = layout.default_sort(task.chart)
    before = _shown(control)
    order_before = _chip_order(task, control)
    event: tuple[str, dict[str, Any]] | None = None
    sort_value: Any = no_update
    threshold_value: Any = no_update

    if triggered == "chips":
        chosen = [e for e in options if e in (chips or [])]
        if chosen == before:
            return UNCHANGED
        if chosen:
            event = (
                "filter_change",
                {
                    "control": "chips",
                    "action": "hide" if set(chosen) < set(before) else "show",
                    "value": chosen,
                    "previous": before,
                },
            )
            control["selected"] = chosen
            # A chip supersedes an isolation; otherwise the chart would ignore the click.
            control["isolated"] = None
        # Unticking the last chip is refused: the chips are set back to what the chart shows.

    elif triggered == "sort":
        sorts = [value for value, _label in layout.SORTS.get(task.chart, ("", ()))[1]]
        if sort_key not in sorts or sort_key == control["sort"]:
            return UNCHANGED
        event = ("sort_change", {"key": sort_key, "direction": _SORT_DIRECTION[sort_key]})
        control["sort"] = sort_key

    elif triggered == "show-all":
        if task.chart != "line" or before == options:
            return UNCHANGED
        event = (
            "filter_change",
            {"control": "show-all", "action": "show", "value": list(options), "previous": before},
        )
        control["selected"] = list(options)
        control["isolated"] = None

    elif triggered == "threshold":
        if task.chart != "map":
            return UNCHANGED
        valid, typed = _threshold(threshold)
        chosen = typed if valid and typed is not None and typed < 100 else None
        if not valid:
            # Put the box back to what the map shows.
            threshold_value = control["threshold"] or layout.THRESHOLD_START
        elif chosen == control["threshold"]:
            return UNCHANGED
        else:
            event = (
                "filter_change",
                {
                    "control": "threshold",
                    "action": "clear" if chosen is None else "highlight",
                    "value": chosen,
                    "previous": control["threshold"],
                },
            )
            control["threshold"] = chosen

    elif triggered == "reset":
        if before == options and control["sort"] == default_sort and control["threshold"] is None:
            return UNCHANGED
        event = (
            "view_reset",
            {
                "previous": {
                    "selected": before,
                    "sort": control["sort"],
                    "isolated": control["isolated"],
                    "threshold": control["threshold"],
                }
            },
        )
        control.update(selected=list(options), isolated=None, sort=default_sort, threshold=None)
        sort_value = default_sort if default_sort is not None else no_update
        threshold_value = layout.THRESHOLD_START if task.chart == "map" else no_update

    elif triggered == "chart.clickData":
        # Only a line can be isolated. A click on a bar, dot, cell or country does nothing.
        entity = _clicked_entity(click_data, task) if task.chart == "line" else None
        # World is the reference every line is read against; isolating to it alone would hide the
        # very series the question is about.
        if entity is None or entity == "World":
            return UNCHANGED
        isolate = control["isolated"] != entity
        event = ("line_isolate", {"entity": entity, "isolated": isolate})
        control["isolated"] = entity if isolate else None

    elif triggered == "chart.restyleData":
        # A legend click (line charts only: the scatter's legend takes no clicks). Plotly has
        # already redrawn the chart by the time this arrives.
        change = _legend_change(restyle, task, before) if task.chart == "line" else None
        if change is None:
            return UNCHANGED
        chosen, action = change
        if chosen and chosen != before:
            event = (
                "filter_change",
                {"control": "legend", "action": action, "value": chosen, "previous": before},
            )
            control["selected"] = chosen
            control["isolated"] = None
        # Otherwise refused, or a click that changed no country (World, say): the figure sent
        # back redraws the chart as the app has it, undoing what Plotly did by itself.

    elif triggered == "chart.relayoutData":
        if not relayout or not any(key.startswith(_VIEW_KEYS) for key in relayout):
            return UNCHANGED
        # Logged, and no figure sent back: Plotly has already drawn it, and a figure in reply
        # put the axis back where it was, undoing every zoom the moment it reached the server.
        # The range is kept in the view instead, so the next redraw -- a chip, the View, Reset
        # view -- draws the chart zoomed as the participant left it (visual-spec.md section 7.3).
        # Plotly's own `uirevision` cannot: dcc.Graph redraws after every zoom with a figure
        # Plotly has already edited, which wipes Plotly's record of the range it replaced
        # (headless Chrome, 2026-09-26).
        zoom = ("view_change", {"control": "chart", "value": relayout, "previous": None})
        spool_out = _log_control(state, log_state, log_dir, spool, task, zoom)
        says, xrange = _zoomed_range(relayout)
        if task.chart == "line" and says:
            control["xrange"] = xrange
            return UNCHANGED._replace(control=control, spool=spool_out)
        return UNCHANGED._replace(spool=spool_out)

    else:
        return UNCHANGED

    figure = _view_figure(task, control)
    order = _chip_order(task, control)
    chip_rows = layout.chip_rows(order, _shown(control))
    group = layout.chip_group(task, order, _shown(control)) if order != order_before else no_update
    # Logged AFTER the figure is built. Logged first, a database failure left the participant's
    # click with no visible effect -- the chart simply did not change.
    return ControlResult(
        figure,
        chip_rows,
        group,
        sort_value,
        threshold_value,
        control,
        _log_control(state, log_state, log_dir, spool, task, event),
    )


def _log_control(
    state: SessionState,
    log_state: dict[str, Any] | None,
    log_dir: Path | None,
    spool: dict[str, Any] | None,
    task,
    event: tuple[str, dict[str, Any]] | None,
) -> Any:
    """Log one control's event, if it has one, and return the browser spool's new state.

    NO_RETRY: this runs inside the task's measured window, and only in the interactive condition.
    A retry here would inflate time-on-task in one condition only. A failed write spools at once,
    and the circuit breaker sends the next click straight to the spool.
    """
    carried = _Spool(spool)
    if event is not None:
        name, payload = event
        logger = _logger(state, log_state, log_dir, carried, policy=NO_RETRY)
        try:
            logger.event(name, task_id=task.task_id, **payload)
        except db.DatabaseError as exc:
            print(f"[study] could not log {name}: {exc}", file=sys.stderr)
        carried.take(logger)
    return carried.output()


def _control_trigger(prop_id: str) -> str:
    """A fired input as `control_step` names it: a control by its pattern id's `control`, the
    chart's own events by prop id."""
    component, _dot, _prop = prop_id.rpartition(".")
    if component.startswith("{"):
        return str(json.loads(component).get("control"))
    return prop_id


def view_outputs(result: ControlResult, counts: list[int]) -> tuple[Any, ...]:
    """The `view` callback's outputs for a result, given how many components each of its four
    `ALL` outputs matched on this screen (the chips' group, the chips, sort, threshold).

    An `ALL` output must be a list with one entry per component, `no_update` entries included:
    Dash 4 refuses a bare `no_update` there with a server error, which the tests calling
    `control_step` could never see (found in headless Chrome). When the group is rebuilt, the
    checklists it replaces are left alone.
    """
    groups, chips, sorts, thresholds = counts
    if result.group is not no_update:
        group, values = [result.group] * groups, [no_update] * chips
    elif result.chips is not no_update:
        group, values = [no_update] * groups, [row["value"] for row in result.chips][:chips]
    else:
        group, values = [no_update] * groups, [no_update] * chips
    return (
        result.figure,
        group,
        values,
        [result.sort] * sorts,
        [result.threshold] * thresholds,
        result.control,
        result.spool,
    )


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
    #
    # Also writes the participant's signed copy into `consent-copy`, for the download button on the
    # next screen -- only once the record has been stored and the session has advanced.
    @app.callback(
        *_step_outputs(),
        Output("consent-copy", "data"),
        Input("consent-clock", "data"),
        State("consent-name", "value"),
        State("consent-date", "value"),
        State("consent-paper", "value"),
        State("signature-strokes", "data"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def agree(consented_at, name, signed_date, paper, strokes, stored, log_state, spool):
        return consent_step(
            consented_at, name, signed_date, paper, strokes, stored, log_state, spool
        )

    @app.callback(
        *_step_outputs(),
        Input("decline-button", "n_clicks"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def decline(n, stored, log_state, spool):
        if not n:
            raise PreventUpdate
        return step("decline-button", stored, log_state, spool=spool)

    @app.callback(
        *_step_outputs(),
        Input("reconsider-button", "n_clicks"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def reconsider(n, stored, log_state, spool):
        if not n:
            raise PreventUpdate
        return step("reconsider-button", stored, log_state, spool=spool)

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

    # About you and the survey read their fields by PATTERN (`ALL`), not by listing each id. The
    # survey's fields differ between conditions and halves (b1-b3 after the interactive condition,
    # c1-c3 after the second), and a State naming a component that is not on the page kills the
    # callback in the browser; a pattern collects whatever is there.
    @app.callback(
        *_step_outputs(),
        Input("demographics-clock", "data"),
        State({"type": "about", "item": ALL}, "value"),
        State({"type": "about", "item": ALL}, "id"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def demographics(clock, values, ids, stored, log_state, spool):
        if not clock:
            raise PreventUpdate
        return step(
            "demographics-clock",
            stored,
            log_state,
            demographics=_by_item(values, ids),
            spool=spool,
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

    # Its own id, like the break's: this leads from the practice-complete screen to the first task.
    @app.callback(
        *_step_outputs(),
        Input("practice-done-button", "n_clicks"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def practice_done(n, stored, log_state, spool):
        if not n:
            raise PreventUpdate
        return step("practice-done-button", stored, log_state, spool=spool)

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

    # Triggered by the survey CLOCK, which the browser writes only after confirming any skips.
    @app.callback(
        *_step_outputs(),
        Input("survey-clock", "data"),
        State({"type": "survey", "item": ALL}, "value"),
        State({"type": "survey", "item": ALL}, "id"),
        *_session_states(),
        prevent_initial_call=True,
    )
    def rate_survey(clock, values, ids, stored, log_state, spool):
        if not clock:
            raise PreventUpdate
        return step("survey-clock", stored, log_state, survey=_by_item(values, ids), spool=spool)

    # Every control under the chart, and the chart's own clicks, zooms and legend clicks, in ONE
    # callback. Each chart type has a different set of controls and the static condition has none,
    # and the browser renderer refuses to run a callback whose Inputs are only partly on the page.
    # So the controls are read by pattern (`ALL`), which matches none of them without complaint, and
    # the chart, on every task screen in both conditions, supplies the rest.
    @app.callback(
        Output("chart", "figure", allow_duplicate=True),
        Output(layout.control_id("chip-group", ALL), "children"),
        Output(layout.control_id("chips", ALL), "value"),
        Output(layout.control_id("sort", ALL), "value"),
        Output(layout.control_id("threshold", ALL), "value"),
        Output("control-state", "data", allow_duplicate=True),
        Output("spool-state", "data", allow_duplicate=True),
        Input("chart", "clickData"),
        Input("chart", "relayoutData"),
        Input("chart", "restyleData"),
        Input(layout.control_id("chips", ALL), "value"),
        Input(layout.control_id("sort", ALL), "value"),
        Input(layout.control_id("show-all", ALL), "n_clicks"),
        Input(layout.control_id("threshold", ALL), "value"),
        Input(layout.control_id("reset", ALL), "n_clicks"),
        State("session-state", "data"),
        State("log-state", "data"),
        State("control-state", "data"),
        State("spool-state", "data"),
        prevent_initial_call=True,
    )
    def view(
        click_data,
        relayout,
        restyle,
        chips,
        sorts,
        _show_all,
        thresholds,
        _reset,
        stored,
        log,
        control_state,
        spool,
    ):
        """Thin wrapper over `control_step`, which says what each control does.

        Passes the **prop id**, not `triggered_id`: the chart raises three inputs, and the
        component id alone cannot separate a zoom from a stale click.
        """
        fired = callback_context.triggered
        result = control_step(
            _control_trigger(fired[0]["prop_id"]) if fired else None,
            stored,
            log,
            control_state,
            chips=[name for row in chips or [] for name in row or []],
            sort_key=sorts[0] if sorts else None,
            threshold=thresholds[0] if thresholds else None,
            click_data=click_data,
            relayout=relayout,
            restyle=restyle,
            spool=spool,
        )
        if result == UNCHANGED:
            # Most calls: a screen being built, or a render-time relayout. Nothing to send.
            raise PreventUpdate
        counts = [len(outputs) for outputs in callback_context.outputs_list[1:5]]
        return view_outputs(result, counts)

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
    #
    # The same function asks the participant to confirm a skip, and disables Submit. One callback,
    # not three: a cancelled skip must neither stamp the clock nor leave the button disabled, and
    # two callbacks on one click could not agree on that. Disabling matters because two rapid clicks
    # send two requests that both read the same pre-click session state, so no server-side check can
    # tell them apart; stopping the second click in the browser is the only complete guard. The
    # database's unique index is the backstop.
    app.clientside_callback(
        SUBMIT_JS,
        Output("submit-clock", "data"),
        Output("submit-button", "disabled"),
        Output("submit-button", "aria-busy"),
        Input("submit-button", "n_clicks"),
        State("answer-input", "value"),
        State("justification-input", "value"),
        prevent_initial_call=True,
    )

    # The survey and About you, one question per page (layout.pager_screen). Back, Next and the
    # rail move between pages in the browser; Next confirms a skip on the page it leaves and checks
    # the age. No page change reaches the server, and nothing is logged until Continue.
    app.clientside_callback(
        PAGER_JS,
        Output("pager-state", "data"),
        Output(layout.pager_id("page", ALL), "hidden"),
        Output(layout.pager_id("section", ALL), "className"),
        Output(layout.pager_id("section", ALL), "disabled"),
        Output(layout.pager_id("mark", ALL), "children"),
        Output(layout.pager_id("sub", ALL), "children"),
        Output(layout.pager_id("bar", ALL), "value"),
        Output(layout.pager_id("bar", ALL), "hidden"),
        Output("pager-position", "children"),
        Output("pager-back", "disabled"),
        Output("pager-next", "hidden"),
        Output("pager-finish", "hidden"),
        Output(layout.pager_id("error", ALL), "children"),
        Input("pager-back", "n_clicks"),
        Input("pager-next", "n_clicks"),
        Input(layout.pager_id("section", ALL), "n_clicks"),
        State("pager-state", "data"),
        State({"type": "survey", "item": ALL}, "value"),
        State({"type": "survey", "item": ALL}, "id"),
        State({"type": "about", "item": ALL}, "value"),
        State({"type": "about", "item": ALL}, "id"),
        prevent_initial_call=True,
    )

    # Typing beside "Other" chooses "Other". The box sits inside that option, and text typed there
    # with no option chosen would otherwise be dropped (`_demographic_answers` keeps it only for
    # "Other").
    for question in tasks.ABOUT_QUESTIONS:
        if question.other_key is not None:
            app.clientside_callback(
                OTHER_CHOSEN_JS,
                Output(layout.about_id(question.key), "value"),
                Input(layout.about_id(question.other_key), "value"),
                State(layout.about_id(question.key), "value"),
                prevent_initial_call=True,
            )

    # Continue, on the last page of the demographics and survey screens: confirm a skip there, then
    # trigger the server. Disabled on the way, like Submit, so a double click cannot record the
    # survey twice.
    app.clientside_callback(
        confirm_js("demographics-button"),
        Output("demographics-clock", "data"),
        Output("demographics-button", "disabled"),
        Input("demographics-button", "n_clicks"),
        State({"type": "about", "item": ALL}, "value"),
        State({"type": "about", "item": ALL}, "id"),
        State("pager-state", "data"),
        prevent_initial_call=True,
    )
    app.clientside_callback(
        confirm_js("load-button"),
        Output("survey-clock", "data"),
        Output("load-button", "disabled"),
        Input("load-button", "n_clicks"),
        State({"type": "survey", "item": ALL}, "value"),
        State({"type": "survey", "item": ALL}, "id"),
        State("pager-state", "data"),
        prevent_initial_call=True,
    )
    for button in ("demographics-button", "load-button"):
        app.clientside_callback(
            SUBMIT_ENABLE_JS,
            Output(button, "disabled", allow_duplicate=True),
            Input("flow-error", "children"),
            prevent_initial_call=True,
        )

    # The participant's own signed copy of the consent form. Clientside: the copy is already in the
    # browser, so it never needs to go back to the server.
    app.clientside_callback(
        COPY_DOWNLOAD_JS,
        Output("consent-download", "data"),
        Input("consent-copy-button", "n_clicks"),
        State("consent-copy", "data"),
        prevent_initial_call=True,
    )

    # ...and re-enable it when the step is refused. A refusal ("Please choose an answer") does not
    # re-render the screen, so without this the participant would be left with a dead button.
    app.clientside_callback(
        SUBMIT_REFUSED_JS,
        Output("submit-button", "disabled", allow_duplicate=True),
        Output("submit-button", "aria-busy", allow_duplicate=True),
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

# Returns [submit-clock, submit-button.disabled, submit-button.aria-busy].
#
# While the answer is saving, Submit is disabled and marked busy, which study.css draws in its
# saving fill (the handoff's state S1). The label does not change and nothing moves.
#
# The stamp is taken at the click, BEFORE any skip popup: time spent reading the popup is not time
# spent on the task. Cancelling the popup changes nothing -- no stamp, no disabled button -- and the
# participant is back on the task. A skip is confirmed with the browser's own dialog, which is
# keyboard-operable (CLAUDE.md accessibility baseline).
#
# The watchdog re-enables the button if no response ever arrives (a killed function, a dropped
# connection), so a lost request can never strand a participant. By the time it fires on a
# successful step the screen has been replaced, and re-enabling a fresh button is harmless -- but
# only if there is one. After the last task the survey is on screen, with no Submit, and the
# renderer threw on `set_props` for a missing id (found in headless Chrome, 2026-09-23). So every
# watchdog checks that its button is still on the page first.
SUBMIT_JS = """function(n, answer, justification) {
    var no = window.dash_clientside.no_update;
    if (!n) { return [no, no, no]; }
    var stamp = {t: window.performance.now(), origin: window.performance.timeOrigin};
    var missing = [];
    if (answer === null || answer === undefined || answer === "") {
        missing.push("the multiple-choice question");
    }
    if (!justification || !String(justification).trim()) {
        missing.push("how you decided");
    }
    if (missing.length && !window.confirm(
        "You have not answered " + missing.join(" or ") + ". Continue without answering?"
    )) {
        return [no, no, no];
    }
    window.setTimeout(function () {
        if (document.getElementById("submit-button")) {
            window.dash_clientside.set_props(
                "submit-button", {disabled: false, "aria-busy": "false"}
            );
        }
    }, 15000);
    return [stamp, true, "true"];
}"""


# How many of a page's fields are unanswered, by the rules every questionnaire screen shares: a
# field that is null, empty or an empty checklist is skipped, except the text box beside "Other"
# (not a question of its own) and the age's "Prefer not to say", which answers the age when ticked.
# `byItem` maps each field's item to its value. Shared by the pager's Next and by Continue.
_SKIPS_JS = """
    var blank = function (v) {
        return v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length);
    };
    var skippedAmong = function (items, byItem) {
        var ageDeclined = !blank(byItem.age_prefer_not);
        return items.filter(function (item) {
            if (/_other$/.test(item) || item === "age_prefer_not") { return false; }
            if (item === "age" && ageDeclined) { return false; }
            return blank(byItem[item]);
        }).length;
    };
    var confirmSkips = function (skipped) {
        return !skipped || window.confirm(
            "You have left " + skipped + (skipped === 1 ? " question" : " questions") +
            " unanswered. Continue without answering?"
        );
    };
"""


def confirm_js(button: str) -> str:
    """Continue on a questionnaire screen: confirm any skipped questions, then fire.

    Returns [clock, button.disabled]. Called with the screen's field values and their pattern ids,
    in matching order, and the pager's state. On a paged screen Continue is on the last page, and
    only that page's skips are asked about: Next asked about every earlier page as it was left.
    Without a pager, every field counts. The clock carries the time, so every press is a distinct
    value -- the survey screen's button starts again at n_clicks 1 in the second condition, and the
    store must not look unchanged.
    """
    return f"""function(n, values, ids, pager) {{
    var no = window.dash_clientside.no_update;
    if (!n) {{ return [no, no]; }}
    values = values || [];
    ids = ids || [];
    {_SKIPS_JS}
    var byItem = {{}};
    ids.forEach(function (id, i) {{ byItem[id.item] = values[i]; }});
    var items = pager && pager.pages
        ? pager.pages[pager.page]
        : ids.map(function (id) {{ return id.item; }});
    var skipped = skippedAmong(items, byItem);
    if (!confirmSkips(skipped)) {{
        return [no, no];
    }}
    window.setTimeout(function () {{
        if (document.getElementById("{button}")) {{
            window.dash_clientside.set_props("{button}", {{disabled: false}});
        }}
    }}, 15000);
    return [{{n: n, skipped: skipped, at: Date.now()}}, true];
}}"""


# The pager on the survey and About-you screens (layout.pager_screen): Back, Next and the rail's
# sections. Returns, in order, the pager's state, each page's `hidden`, each section's class,
# `disabled`, number or tick, subtitle, progress and its `hidden`, the position label, Back's
# `disabled`, Next's and Continue's `hidden`, and the age message. Next confirms a skip on the page
# it leaves, and refuses an age outside the range, marking the field, where the server would refuse
# it only at Continue, pages later. A reached section can be reopened; one not reached cannot.
PAGER_JS = (
    """function(back, next, rail, pager, surveyValues, surveyIds, aboutValues, aboutIds) {
    var context = window.dash_clientside.callback_context || {};
    var trigger = (context.triggered || [])[0] || {};
    var fired = trigger.prop_id || "";
    // Only a click: Dash also fires this when the screen's buttons first appear, at n_clicks 0.
    if (!pager || !pager.pages || !fired || !trigger.value) {
        throw window.dash_clientside.PreventUpdate;
    }
    var source = fired.slice(0, fired.lastIndexOf("."));
    """
    + _SKIPS_JS
    + """
    var byItem = {};
    [[surveyValues, surveyIds], [aboutValues, aboutIds]].forEach(function (pair) {
        (pair[1] || []).forEach(function (id, i) { byItem[id.item] = (pair[0] || [])[i]; });
    });
    var pages = pager.pages, sectionOf = pager.sections, last = pages.length - 1;
    var target = pager.page, error = "";
    if (source === "pager-back") {
        target = Math.max(0, pager.page - 1);
    } else if (source === "pager-next") {
        var items = pages[pager.page];
        if (items.indexOf("age") >= 0 && blank(byItem.age_prefer_not) && !blank(byItem.age)) {
            var age = Number(byItem.age);
            if (!(isFinite(age) && Math.floor(age) === age && age >= AGE_LOW && age <= AGE_HIGH)) {
                error = AGE_MESSAGE;
            }
        }
        if (!error) {
            if (!confirmSkips(skippedAmong(items, byItem))) {
                throw window.dash_clientside.PreventUpdate;
            }
            target = Math.min(last, pager.page + 1);
        }
    } else {
        var section = JSON.parse(source).index;
        target = sectionOf[pager.page] === section ? pager.page : sectionOf.indexOf(section);
    }
    var ageField = document.getElementById(JSON.stringify({item: "age", type: "about"}));
    if (ageField) {
        if (error) {
            ageField.setAttribute("aria-invalid", "true");
            ageField.setAttribute("aria-describedby", JSON.stringify({index: 0, pager: "error"}));
        } else {
            ageField.removeAttribute("aria-invalid");
        }
    }
    var reached = Math.max(pager.max, target);
    var current = sectionOf[target];
    var count = Math.max.apply(null, sectionOf) + 1;
    var classes = [], locked = [], marks = [], subs = [], bars = [], barsHidden = [];
    for (var s = 0; s < count; s++) {
        var first = sectionOf.indexOf(s), end = sectionOf.lastIndexOf(s), size = end - first + 1;
        var here = s === current, done = target > end;
        classes.push("pager-go" + (here ? " pager-go--current" : done ? " pager-go--done"
            : reached >= first ? " pager-go--reached" : ""));
        locked.push(reached < first);
        marks.push(done ? "\u2713" : String(s + 1));
        subs.push(here ? "Question " + (target - first + 1) + " of " + size
            : size === 1 ? "1 question" : size + " questions");
        bars.push(here ? target - first + 1 : 0);
        barsHidden.push(!here);
    }
    // A button that disappears or goes dead under the keyboard hands its focus on, once Dash has
    // drawn the one that takes it over (a hidden button cannot take focus).
    var focusSoon = function (id) {
        var tries = 0;
        var attempt = function () {
            var element = document.getElementById(id);
            if (element && element.offsetParent !== null && !element.disabled) {
                element.focus();
            } else if (++tries < 40) {
                window.setTimeout(attempt, 25);
            }
        };
        window.setTimeout(attempt, 0);
    };
    if (source === "pager-next" && target === last && target !== pager.page) {
        focusSoon(pager.finish);
    }
    if (source === "pager-back" && target === 0) { focusSoon("pager-next"); }
    return [
        {page: target, max: reached, pages: pages, sections: sectionOf, errors: pager.errors,
         finish: pager.finish},
        pages.map(function (_, k) { return k !== target; }),
        classes, locked, marks, subs, bars, barsHidden,
        "Question " + (target + 1) + " of " + pages.length,
        target === 0,
        target === last,
        target !== last,
        Array.apply(null, Array(pager.errors)).map(function () { return error; })
    ];
}""".replace("AGE_LOW", str(tasks.AGE_RANGE[0]))
    .replace("AGE_HIGH", str(tasks.AGE_RANGE[1]))
    .replace("AGE_MESSAGE", json.dumps(AGE_MESSAGE))
)


OTHER_CHOSEN_JS = (
    """function(text, chosen) {
    var typed = typeof text === "string" && text.trim() !== "";
    return typed && chosen !== OTHER ? OTHER : window.dash_clientside.no_update;
}"""
).replace("OTHER", json.dumps(tasks.OTHER))

COPY_DOWNLOAD_JS = """function(n, copy) {
    if (!n || !copy) { return window.dash_clientside.no_update; }
    return {content: copy, filename: "signed-consent-form.html", type: "text/html"};
}"""

SUBMIT_ENABLE_JS = """function(message) {
    return message ? false : window.dash_clientside.no_update;
}"""

# Submit's version, which also clears the busy mark. Returns [disabled, aria-busy].
SUBMIT_REFUSED_JS = """function(message) {
    var no = window.dash_clientside.no_update;
    return message ? [false, "false"] : [no, no];
}"""

# The watchdog is longer than Submit's: assignment retries under the FULL policy before refusing,
# which took ~11 s against an unreachable database (an 8 s budget, plus a 5 s connect attempt that
# starts just inside it). The refusal re-enables the button; this only covers a lost response.
PARTICIPANT_DISABLE_JS = """function(n, nSubmit) {
    if (!n && !nSubmit) { return window.dash_clientside.no_update; }
    window.setTimeout(function () {
        if (document.getElementById("participant-button")) {
            window.dash_clientside.set_props("participant-button", {disabled: false});
        }
    }, 25000);
    return true;
}"""

# A refusal also marks the field (S2): invalid when the ID is what was refused, not when the
# database was, and described by the message under it. By hand, because dcc.Input takes no aria-*
# property; React leaves attributes it does not manage alone, and a refusal does not re-render the
# screen.
PARTICIPANT_ENABLE_JS = """function(message) {
    var field = document.getElementById("participant-input");
    if (field) {
        field.setAttribute("aria-describedby", "flow-error");
        if (message === ID_MISSING) { field.setAttribute("aria-invalid", "true"); }
        else { field.removeAttribute("aria-invalid"); }
    }
    return message ? false : window.dash_clientside.no_update;
}""".replace("ID_MISSING", json.dumps(ID_MISSING))

CONSENT_CLOCK_JS = """function(n) {
    return n ? new Date().toISOString() : window.dash_clientside.no_update;
}"""


def _by_item(values: list[Any] | None, ids: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Pattern-matched fields as {item: value}. Dash hands the two lists over in the same order."""
    return {pattern["item"]: value for pattern, value in zip(ids or [], values or [], strict=True)}


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
        except db.WithdrawnParticipantError as exc:
            # Their data was deleted at their request; a new session under the ID would undo that.
            raise flow.FlowError(
                "This participant ID can no longer be used. Please contact the researcher."
            ) from exc
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
