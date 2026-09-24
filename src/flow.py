"""Study session flow. Pure state transitions, no Dash and no I/O.

    consent -> participant id -> demographics -> instructions -> practice -> tasks -> load -> break
       |  ^                                          ^                                        |
       v  |                                          +-------------- resume ------------------+
     declined                                   instructions -> tasks -> load -> done

`load` is the whole post-condition survey: the Paas rating and the three Likert items.

Two asymmetries are deliberate, and both implement `docs/study-design.md` section 8:

- **Practice runs only before the first condition.** It teaches the interface, and a participant who
  has already done it does not need it again.
- **Instructions are shown again before the second condition.** The conditions differ in what the
  chart can do, so a participant entering their second condition has to be told what changed.
  Showing them once would leave whoever gets interactive second unaware the controls exist, which is
  a procedural difference between conditions rather than a difference in interactivity.

Kept free of framework code so the order of a within-subjects session can be tested exhaustively
without a browser: which condition a participant sees, in which order, and how many tasks each.

The task *content* (prompts, answer formats, rubric) is a study-protocol decision and lives in
`docs/study-design.md`. This module takes tasks as input and never invents them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

CONDITIONS = ("static", "interactive")
FORMS = ("A", "B")
CONDITIONS_PER_SESSION = 2


class Stage(StrEnum):
    """Where a participant is. A string enum so it serialises straight into a dcc.Store."""

    CONSENT = "consent"
    # "I do not agree". Terminal unless the participant goes back to the form: nothing is written
    # anywhere before consent, so the screen can truthfully say no data was collected.
    DECLINED = "declined"
    PARTICIPANT_ID = "participant_id"
    # Broad-category questions, once per participant. docs/study-design.md section 6.2.
    DEMOGRAPHICS = "demographics"
    INSTRUCTIONS = "instructions"
    PRACTICE = "practice"
    TASK = "task"
    # The Paas mental-effort rating, asked once per condition. A stage rather than a screen the
    # callback conjures mid-flight, so that `condition_index` can advance here — at LOAD the state
    # still names the condition just finished, which is the one being rated.
    LOAD = "load"
    BREAK = "break"
    COMPLETE = "complete"


class FlowError(RuntimeError):
    """Raised on an invalid transition or malformed state."""


@dataclass(frozen=True, slots=True)
class Task:
    """One task presented to a participant.

    `kind` names the item type, which is what `analysis/keys.py` scores by; `chart` names the chart
    it is asked about; `options` are the multiple-choice answers. `years` are the years the chart
    shows: empty for a line chart, which always spans the whole range; one for a bar chart or map;
    the two axes of a scatter; the columns of a heatmap.

    Correct answers are deliberately NOT stored here — scoring happens offline against the rubric,
    so the answer key is never shipped to the browser where a participant could read it.
    """

    task_id: str
    form: str  # "A" | "B" | "both"
    kind: str  # "lowest" | "rise" | "rank" | "improved" | "cell" | "threshold" | "crossing"
    #            | "practice"
    prompt: str
    vaccine: str
    entities: tuple[str, ...]
    options: tuple[str, ...] = ()
    chart: str = "line"  # "line" | "bar" | "scatter" | "heatmap" | "map"
    years: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionState:
    """A participant's position in the session. Serialisable to and from a dcc.Store."""

    stage: Stage = Stage.CONSENT
    participant_id: str | None = None
    first_condition: str | None = None
    first_form: str | None = None
    condition_index: int = 0  # 0 = first condition, 1 = second
    task_index: int = 0
    # Browser ISO timestamp from the moment "I agree" was pressed. Held here because consent comes
    # before the participant ID, and a log record cannot be written until the ID exists.
    consent_at: str | None = None
    # "drawn" or "paper": how the consent form was signed. The signature itself never enters session
    # state or the study log -- it lives only in the separate consent record. See src/consent.py.
    consent_method: str | None = None
    # The demographic answers, held for the same reason as `consent_at`: they are given before any
    # logger can exist, and are written when condition 1's logger opens.
    demographics: dict[str, str | None] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "participant_id": self.participant_id,
            "first_condition": self.first_condition,
            "first_form": self.first_form,
            "condition_index": self.condition_index,
            "task_index": self.task_index,
            "consent_at": self.consent_at,
            "consent_method": self.consent_method,
            "demographics": self.demographics,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> SessionState:
        if not raw:
            return cls()
        try:
            return cls(
                stage=Stage(raw["stage"]),
                participant_id=raw.get("participant_id"),
                first_condition=raw.get("first_condition"),
                first_form=raw.get("first_form"),
                condition_index=int(raw.get("condition_index", 0)),
                task_index=int(raw.get("task_index", 0)),
                consent_at=raw.get("consent_at"),
                consent_method=raw.get("consent_method"),
                demographics=raw.get("demographics"),
            )
        except (KeyError, ValueError) as exc:
            raise FlowError(f"Malformed session state: {exc}") from exc


def other_condition(condition: str) -> str:
    if condition not in CONDITIONS:
        raise FlowError(f"Unknown condition {condition!r}")
    return "interactive" if condition == "static" else "static"


def other_form(form: str) -> str:
    if form not in FORMS:
        raise FlowError(f"Unknown form {form!r}")
    return "B" if form == "A" else "A"


def current_form(state: SessionState) -> str:
    """Which task form the participant is working through right now.

    The form flips with the condition, so nobody answers the same question twice — which is what a
    plain order-counterbalance cannot achieve on its own.
    """
    if state.first_form is None:
        raise FlowError("No form assigned yet")
    if state.condition_index == 0:
        return state.first_form
    return other_form(state.first_form)


def current_condition(state: SessionState) -> str:
    """Which condition the participant is in right now."""
    if state.first_condition is None:
        raise FlowError("No condition assigned yet")
    if state.condition_index == 0:
        return state.first_condition
    return other_condition(state.first_condition)


def is_interactive(state: SessionState) -> bool:
    """The single boolean that separates the conditions, derived from session state.

    This is what replaced the module-level `config.INTERACTIVE` at deploy time: one URL serves both
    conditions, so the flag has to be per-session rather than per-process.
    """
    return current_condition(state) == "interactive"


def condition_order(state: SessionState) -> int:
    """1 if this is the participant's first condition, 2 if their second."""
    return state.condition_index + 1


def current_task(state: SessionState, tasks: Sequence[Task]) -> Task:
    if state.stage is not Stage.TASK:
        raise FlowError(f"Not on a task; stage is {state.stage.value}")
    if not 0 <= state.task_index < len(tasks):
        raise FlowError(f"Task index {state.task_index} out of range for {len(tasks)} tasks")
    return tasks[state.task_index]


# --- Transitions --------------------------------------------------------------------------------


def give_consent(
    state: SessionState, consent_at: str | None = None, method: str | None = None
) -> SessionState:
    """Accept consent. `consent_at` is the browser timestamp, logged once the logger can open."""
    _require(state, Stage.CONSENT)
    return replace(state, stage=Stage.PARTICIPANT_ID, consent_at=consent_at, consent_method=method)


def decline(state: SessionState) -> SessionState:
    """'I do not agree' (IRB form item 12B). Nothing has been recorded, and nothing will be."""
    _require(state, Stage.CONSENT)
    return replace(state, stage=Stage.DECLINED)


def reconsider(state: SessionState) -> SessionState:
    """Back to the consent form from the declined screen, in case the choice was a mis-click."""
    _require(state, Stage.DECLINED)
    return replace(state, stage=Stage.CONSENT)


def set_participant(
    state: SessionState, participant_id: str, first_condition: str, first_form: str
) -> SessionState:
    """Record the identity and the 2x2 assignment from `db.register_participant`."""
    _require(state, Stage.PARTICIPANT_ID)
    cleaned = (participant_id or "").strip()
    if not cleaned:
        raise FlowError("participant_id must be a non-empty string")
    if first_condition not in CONDITIONS:
        raise FlowError(f"Unknown condition {first_condition!r}")
    if first_form not in FORMS:
        raise FlowError(f"Unknown form {first_form!r}")
    return replace(
        state,
        stage=Stage.DEMOGRAPHICS,
        participant_id=cleaned,
        first_condition=first_condition,
        first_form=first_form,
    )


def submit_demographics(state: SessionState, answers: dict[str, str | None]) -> SessionState:
    """Hold the demographic answers until a logger exists, and move on to the instructions.

    Any answer may be None: every question may be skipped (IRB form item 10).
    """
    _require(state, Stage.DEMOGRAPHICS)
    return replace(state, stage=Stage.INSTRUCTIONS, demographics=dict(answers))


def begin_practice(state: SessionState) -> SessionState:
    """Leave instructions for the unscored practice item.

    First condition only: practice exists to teach the interface, and a participant reaching their
    second condition has already used it.
    """
    _require(state, Stage.INSTRUCTIONS)
    if state.first_condition is None:
        raise FlowError("Cannot begin practice before a condition is assigned")
    if state.condition_index != 0:
        raise FlowError("Practice runs only before the first condition")
    return replace(state, stage=Stage.PRACTICE)


def begin_tasks(state: SessionState) -> SessionState:
    """Leave practice (or, in the second condition, instructions) for the first scored task."""
    _require(state, Stage.INSTRUCTIONS, Stage.PRACTICE)
    if state.first_condition is None:
        raise FlowError("Cannot begin tasks before a condition is assigned")
    return replace(state, stage=Stage.TASK, task_index=0)


def complete_task(state: SessionState, tasks: Sequence[Task]) -> SessionState:
    """Finish the current task and move on.

    When the tasks run out the condition goes to its load rating, not straight to the break: the
    rating is about the condition just finished, so it has to be collected before the session moves
    on to the next one.
    """
    _require(state, Stage.TASK)
    if not tasks:
        raise FlowError("No tasks supplied")

    next_index = state.task_index + 1
    if next_index < len(tasks):
        return replace(state, task_index=next_index)
    return replace(state, stage=Stage.LOAD, task_index=0)


def submit_load(state: SessionState) -> SessionState:
    """Record that the load rating is in and end the condition.

    **This is where `condition_index` advances.** Keeping it here rather than in `complete_task` is
    what lets every event from the last task through the load rating be attributed to the condition
    that produced it, without the caller having to rewind the state to work out which that was.
    """
    _require(state, Stage.LOAD)
    if state.condition_index + 1 < CONDITIONS_PER_SESSION:
        return replace(state, stage=Stage.BREAK, condition_index=state.condition_index + 1)
    return replace(state, stage=Stage.COMPLETE)


def resume_after_break(state: SessionState) -> SessionState:
    """Leave the mid-session break for the second condition's instructions.

    Not straight to the tasks: the second condition's affordances differ from the first's and the
    participant has to be told so. See the module docstring.
    """
    _require(state, Stage.BREAK)
    return replace(state, stage=Stage.INSTRUCTIONS)


def _require(state: SessionState, *allowed: Stage) -> None:
    if state.stage not in allowed:
        names = " or ".join(s.value for s in allowed)
        raise FlowError(f"Expected stage {names}, got {state.stage.value}")
