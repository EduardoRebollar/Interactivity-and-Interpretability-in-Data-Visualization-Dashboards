"""Study session flow. Pure state transitions, no Dash and no I/O.

consent -> participant id -> instructions -> condition A tasks -> break -> condition B tasks -> done

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
    PARTICIPANT_ID = "participant_id"
    INSTRUCTIONS = "instructions"
    TASK = "task"
    BREAK = "break"
    COMPLETE = "complete"


class FlowError(RuntimeError):
    """Raised on an invalid transition or malformed state."""


@dataclass(frozen=True, slots=True)
class Task:
    """One task presented to a participant.

    `answer_kind` drives which input is rendered; `options` is used by choice kinds.
    Correct answers are deliberately NOT stored here — scoring happens offline against the rubric,
    so the answer key is never shipped to the browser where a participant could read it.
    """

    task_id: str
    form: str  # "A" | "B"
    kind: str  # "reference" | "trend" | "crossing" | "gap" | "practice"
    prompt: str
    vaccine: str
    entities: tuple[str, ...]
    options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionState:
    """A participant's position in the session. Serialisable to and from a dcc.Store."""

    stage: Stage = Stage.CONSENT
    participant_id: str | None = None
    first_condition: str | None = None
    first_form: str | None = None
    condition_index: int = 0  # 0 = first condition, 1 = second
    task_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "participant_id": self.participant_id,
            "first_condition": self.first_condition,
            "first_form": self.first_form,
            "condition_index": self.condition_index,
            "task_index": self.task_index,
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


def give_consent(state: SessionState) -> SessionState:
    _require(state, Stage.CONSENT)
    return replace(state, stage=Stage.PARTICIPANT_ID)


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
        stage=Stage.INSTRUCTIONS,
        participant_id=cleaned,
        first_condition=first_condition,
        first_form=first_form,
    )


def begin_tasks(state: SessionState) -> SessionState:
    """Leave instructions (or the mid-session break) and start this condition's first task."""
    _require(state, Stage.INSTRUCTIONS, Stage.BREAK)
    if state.first_condition is None:
        raise FlowError("Cannot begin tasks before a condition is assigned")
    return replace(state, stage=Stage.TASK, task_index=0)


def complete_task(state: SessionState, tasks: Sequence[Task]) -> SessionState:
    """Finish the current task and move on.

    Ends the condition when the tasks run out: to the break after the first condition, to completion
    after the second.
    """
    _require(state, Stage.TASK)
    if not tasks:
        raise FlowError("No tasks supplied")

    next_index = state.task_index + 1
    if next_index < len(tasks):
        return replace(state, task_index=next_index)

    if state.condition_index + 1 < CONDITIONS_PER_SESSION:
        return replace(
            state, stage=Stage.BREAK, condition_index=state.condition_index + 1, task_index=0
        )
    return replace(state, stage=Stage.COMPLETE, task_index=0)


def _require(state: SessionState, *allowed: Stage) -> None:
    if state.stage not in allowed:
        names = " or ".join(s.value for s in allowed)
        raise FlowError(f"Expected stage {names}, got {state.stage.value}")
