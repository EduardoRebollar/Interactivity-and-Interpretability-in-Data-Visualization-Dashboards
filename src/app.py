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
import os
import sys
from pathlib import Path
from typing import Any

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
                return refuse("Please enter your participant ID.")
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
# Filtering, sorting and line isolation on line charts; sorting bars; filtering the map by a
# coverage range; zoom/pan. These exist ONLY in the interactive condition — the static condition
# never renders the controls, and `staticPlot: True` means its chart can be neither clicked nor
# zoomed — so every event below is, by construction, an interactive-condition event. The static
# chart does still send Plotly's render-time relayout, which carries no axis range and is ignored
# below exactly as it is in the interactive condition.
# That is the study's independent variable, and this is where it gets recorded. Hovers are not
# logged (decided 2026-09-21), so the scatter and heatmap items, whose affordance is hover, leave
# no interaction record.

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


def _band(raw: Any) -> list[int] | None:
    """A coverage range from the slider, as [low, high] within 0-100, or None if it is not one."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    try:
        low, high = (round(float(value)) for value in raw)
    except (TypeError, ValueError):
        return None
    if not layout.BAND_FULL[0] <= low <= high <= layout.BAND_FULL[1]:
        return None
    return [low, high]


def _view_figure(task, control: dict[str, Any]):
    """The task's figure with the participant's current view applied.

    Built fresh and then hidden, sorted or faded -- never rebuilt from a shorter list, which would
    recolour what remains. The view functions in `src/figures.py` say why.
    """
    figure = figures.task_figure(task)
    if task.chart == "line":
        shown = [control["isolated"]] if control["isolated"] else list(control["selected"])
        if "World" in task.entities:
            shown.append("World")
        figures.set_visible(figure, shown)
    elif task.chart == "bar":
        figures.sort_bars(figure, by_coverage=control["sort"] == "coverage")
    elif task.chart == "map":
        figures.set_band(figure, *control["band"])
    return figure


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
    band: list[float] | None = None,
    spool: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Apply one control interaction.

    Returns (figure, control options, control value, control state, spool). On a line chart the
    middle two are the filter checklist's options and ticked values. On the map they are
    `no_update` and the slider's range, which Show all has to move back. Elsewhere they are
    `no_update`.

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
    control = {
        "selected": list(options),
        "sort": "listed",
        "isolated": None,
        "band": list(layout.BAND_FULL),
        "screen": screen,
    }
    if (control_state or {}).get("screen") == screen:
        control.update(control_state)
    # A stale store from the previous task would name entities this one does not have.
    control["selected"] = [e for e in control["selected"] if e in options] or list(options)
    if control["isolated"] not in task.entities:
        control["isolated"] = None
    control["band"] = _band(control["band"]) or list(layout.BAND_FULL)

    unchanged: tuple[Any, ...] = (no_update,) * 5
    event: tuple[str, dict[str, Any]] | None = None
    # What the triggering control's own value must become. Only Show all on the map sets one: it
    # has to move the slider's handles back to the ends.
    control_value: Any = no_update

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

    elif triggered == "bar-sort.value":
        # Logged as the line chart's sort is, with the same payload: `task_id` says which chart.
        if task.chart != "bar" or sort_key not in layout.SORT_KEYS or sort_key == control["sort"]:
            return unchanged
        event = (
            "sort_change",
            {"key": sort_key, "direction": "desc" if sort_key == "coverage" else "none"},
        )
        control["sort"] = sort_key

    elif triggered == "coverage-band.value":
        chosen = _band(band)
        if task.chart != "map" or chosen is None or chosen == control["band"]:
            return unchanged
        # A filter, so a `filter_change` -- whose `value` here is the range, not a list of names.
        event = (
            "filter_change",
            {
                "control": "coverage-band",
                "action": "band",
                "value": chosen,
                "previous": list(control["band"]),
            },
        )
        control["band"] = chosen

    elif triggered == "band-reset.n_clicks":
        if task.chart != "map" or control["band"] == layout.BAND_FULL:
            return unchanged
        event = (
            "filter_change",
            {
                "control": "band-reset",
                "action": "show",
                "value": list(layout.BAND_FULL),
                "previous": list(control["band"]),
            },
        )
        control["band"] = list(layout.BAND_FULL)
        control_value = list(layout.BAND_FULL)

    elif triggered == "chart.clickData":
        # Only a line can be isolated. A click on a bar, dot, cell or country does nothing.
        entity = _clicked_entity(click_data, task) if task.chart == "line" else None
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

    figure = _view_figure(task, control)
    if task.chart == "line":
        ordered = layout.sorted_entities(options, task.vaccine, control["sort"])
        values = (
            layout.latest_values(ordered, task.vaccine) if control["sort"] == "coverage" else {}
        )
        filter_options: Any = [
            {
                "label": layout.control_label(entity, values.get(entity), control["sort"]),
                "value": entity,
            }
            for entity in ordered
        ]
        control_value = list(control["selected"])
    else:
        filter_options = no_update

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
    return figure, filter_options, control_value, control, carried.output()


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

    # The bar chart's sort and the map's coverage range, each in a callback of its own. Every Input
    # of a callback must be on the page together or the browser renderer refuses to run it, so a
    # control that exists on one chart type cannot share a callback with another type's controls.
    @app.callback(
        Output("chart", "figure", allow_duplicate=True),
        Output("control-state", "data", allow_duplicate=True),
        Output("spool-state", "data", allow_duplicate=True),
        Input("bar-sort", "value"),
        State("session-state", "data"),
        State("log-state", "data"),
        State("control-state", "data"),
        State("spool-state", "data"),
        prevent_initial_call=True,
    )
    def bar_sort(sort_key, stored, log, control_state, spool):
        """Thin wrapper over `control_step` for the bar chart's Order control."""
        fired = callback_context.triggered
        figure, _options, _value, control, spool_out = control_step(
            fired[0]["prop_id"] if fired else None,
            stored,
            log,
            control_state,
            sort_key=sort_key,
            spool=spool,
        )
        return figure, control, spool_out

    # Writes the slider it reads: Show all has to move the handles back. Dash allows a property to
    # be both an Input and an Output of one callback, and does not re-fire it on its own write.
    @app.callback(
        Output("chart", "figure", allow_duplicate=True),
        Output("coverage-band", "value"),
        Output("control-state", "data", allow_duplicate=True),
        Output("spool-state", "data", allow_duplicate=True),
        Input("coverage-band", "value"),
        Input("band-reset", "n_clicks"),
        State("session-state", "data"),
        State("log-state", "data"),
        State("control-state", "data"),
        State("spool-state", "data"),
        prevent_initial_call=True,
    )
    def coverage_band(band, _reset, stored, log, control_state, spool):
        """Thin wrapper over `control_step` for the map's coverage range and its Show all."""
        fired = callback_context.triggered
        figure, _options, value, control, spool_out = control_step(
            fired[0]["prop_id"] if fired else None,
            stored,
            log,
            control_state,
            band=band,
            spool=spool,
        )
        return figure, value, control, spool_out

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
        Input("submit-button", "n_clicks"),
        State("answer-input", "value"),
        State("justification-input", "value"),
        prevent_initial_call=True,
    )

    # Continue on the demographics and survey screens: confirm any skips, then trigger the server.
    # Disabled on the way, like Submit, so a double click cannot record the survey twice.
    app.clientside_callback(
        confirm_js("demographics-button"),
        Output("demographics-clock", "data"),
        Output("demographics-button", "disabled"),
        Input("demographics-button", "n_clicks"),
        State({"type": "about", "item": ALL}, "value"),
        State({"type": "about", "item": ALL}, "id"),
        prevent_initial_call=True,
    )
    app.clientside_callback(
        confirm_js("load-button"),
        Output("survey-clock", "data"),
        Output("load-button", "disabled"),
        Input("load-button", "n_clicks"),
        State({"type": "survey", "item": ALL}, "value"),
        State({"type": "survey", "item": ALL}, "id"),
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

# Returns [submit-clock, submit-button.disabled].
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
    if (!n) { return [no, no]; }
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
        return [no, no];
    }
    window.setTimeout(function () {
        if (document.getElementById("submit-button")) {
            window.dash_clientside.set_props("submit-button", {disabled: false});
        }
    }, 15000);
    return [stamp, true];
}"""


def confirm_js(button: str) -> str:
    """Continue on a questionnaire screen: confirm any skipped questions, then fire.

    Returns [clock, button.disabled]. Called with the screen's field values and their pattern ids,
    in matching order. A field that is null, empty or an empty checklist counts as skipped, except
    the text box beside "Other" (not a question of its own) and the age box's "Prefer not to say",
    which answers the age question when ticked. The clock carries the time, so every press is a
    distinct value -- the survey screen's button starts again at n_clicks 1 in the second condition,
    and the store must not look unchanged.
    """
    return f"""function(n, values, ids) {{
    var no = window.dash_clientside.no_update;
    if (!n) {{ return [no, no]; }}
    values = values || [];
    ids = ids || [];
    var blank = function (v) {{
        return v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length);
    }};
    var ageDeclined = false;
    ids.forEach(function (id, i) {{
        if (id.item === "age_prefer_not" && !blank(values[i])) {{ ageDeclined = true; }}
    }});
    var skipped = values.filter(function (v, i) {{
        var item = (ids[i] || {{}}).item || "";
        if (/_other$/.test(item) || item === "age_prefer_not") {{ return false; }}
        if (item === "age" && ageDeclined) {{ return false; }}
        return blank(v);
    }}).length;
    if (skipped && !window.confirm(
        "You have left " + skipped + (skipped === 1 ? " question" : " questions") +
        " unanswered. Continue without answering?"
    )) {{
        return [no, no];
    }}
    window.setTimeout(function () {{
        if (document.getElementById("{button}")) {{
            window.dash_clientside.set_props("{button}", {{disabled: false}});
        }}
    }}, 15000);
    return [{{n: n, skipped: skipped, at: Date.now()}}, true];
}}"""


COPY_DOWNLOAD_JS = """function(n, copy) {
    if (!n || !copy) { return window.dash_clientside.no_update; }
    return {content: copy, filename: "signed-consent-form.html", type: "text/html"};
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
        if (document.getElementById("participant-button")) {
            window.dash_clientside.set_props("participant-button", {disabled: false});
        }
    }, 25000);
    return true;
}"""

PARTICIPANT_ENABLE_JS = """function(message) {
    return message ? false : window.dash_clientside.no_update;
}"""

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
