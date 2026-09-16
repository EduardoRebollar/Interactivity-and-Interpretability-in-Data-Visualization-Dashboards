"""Tests for the session flow and the counterbalancing rule.

The property that matters most: every participant sees both conditions, exactly once each, and the
order alternates across participants. If that breaks, a practice effect becomes indistinguishable
from an effect of interactivity and the within-subjects design is worthless.
"""

from __future__ import annotations

import pytest

from src import db, flow
from src.flow import FlowError, SessionState, Stage, Task

TASKS = tuple(
    Task(
        task_id=f"T{n}",
        prompt=f"Placeholder prompt {n}",
        vaccine="DTP3",
        entities=("Nigeria", "India"),
        answer_kind="text",
    )
    for n in range(1, 4)
)


def _started(first_condition: str = "static") -> SessionState:
    state = flow.give_consent(SessionState())
    return flow.set_participant(state, "P01", first_condition)


# --- Counterbalancing ---------------------------------------------------------------------------


def test_assignment_alternates_by_sequence():
    assert db.first_condition_for(1) == "static"
    assert db.first_condition_for(2) == "interactive"
    assert db.first_condition_for(3) == "static"


def test_assignment_is_balanced_over_a_realistic_cohort():
    """n >= 25 is the target; the two orders must come out within one of each other."""
    assigned = [db.first_condition_for(seq) for seq in range(1, 26)]
    static = assigned.count("static")
    interactive = assigned.count("interactive")
    assert abs(static - interactive) <= 1, f"{static} static vs {interactive} interactive"


# --- Condition sequencing -----------------------------------------------------------------------


@pytest.mark.parametrize("first", ["static", "interactive"])
def test_participant_sees_both_conditions_exactly_once(first):
    state = _started(first)
    state = flow.begin_tasks(state)

    seen = [flow.current_condition(state)]
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    assert state.stage is Stage.BREAK

    state = flow.begin_tasks(state)
    seen.append(flow.current_condition(state))
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)

    assert state.stage is Stage.COMPLETE
    assert sorted(seen) == ["interactive", "static"]
    assert seen[0] == first


@pytest.mark.parametrize("first", ["static", "interactive"])
def test_condition_order_is_one_then_two(first):
    state = flow.begin_tasks(_started(first))
    assert flow.condition_order(state) == 1
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    assert flow.condition_order(state) == 2


def test_is_interactive_tracks_the_current_condition():
    state = flow.begin_tasks(_started("static"))
    assert flow.is_interactive(state) is False
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    assert flow.is_interactive(state) is True


def test_other_condition_is_an_involution():
    for condition in flow.CONDITIONS:
        assert flow.other_condition(flow.other_condition(condition)) == condition


def test_condition_before_assignment_is_an_error():
    with pytest.raises(FlowError, match="No condition assigned"):
        flow.current_condition(SessionState())


# --- Task progression ---------------------------------------------------------------------------


def test_tasks_advance_in_order():
    state = flow.begin_tasks(_started())
    seen = []
    for _ in range(len(TASKS)):
        seen.append(flow.current_task(state, TASKS).task_id)
        state = flow.complete_task(state, TASKS)
    assert seen == ["T1", "T2", "T3"]


def test_task_index_resets_for_the_second_condition():
    state = flow.begin_tasks(_started())
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    state = flow.begin_tasks(state)
    assert state.task_index == 0
    assert flow.current_task(state, TASKS).task_id == "T1"


def test_current_task_outside_task_stage_is_an_error():
    with pytest.raises(FlowError, match="Not on a task"):
        flow.current_task(_started(), TASKS)


def test_complete_task_with_no_tasks_is_an_error():
    state = flow.begin_tasks(_started())
    with pytest.raises(FlowError, match="No tasks supplied"):
        flow.complete_task(state, ())


# --- Stage guards -------------------------------------------------------------------------------


def test_stages_must_be_entered_in_order():
    fresh = SessionState()
    with pytest.raises(FlowError, match="Expected stage participant_id"):
        flow.set_participant(fresh, "P01", "static")
    with pytest.raises(FlowError, match="Expected stage instructions or break"):
        flow.begin_tasks(fresh)
    with pytest.raises(FlowError, match="Expected stage task"):
        flow.complete_task(fresh, TASKS)


def test_consent_cannot_be_given_twice():
    state = flow.give_consent(SessionState())
    with pytest.raises(FlowError, match="Expected stage consent"):
        flow.give_consent(state)


def test_participant_id_must_not_be_blank():
    state = flow.give_consent(SessionState())
    with pytest.raises(FlowError, match="non-empty"):
        flow.set_participant(state, "   ", "static")


def test_unknown_condition_rejected():
    state = flow.give_consent(SessionState())
    with pytest.raises(FlowError, match="Unknown condition"):
        flow.set_participant(state, "P01", "semi-interactive")


# --- Serialisation ------------------------------------------------------------------------------


def test_state_round_trips_through_a_store():
    """State lives in a browser dcc.Store, so it must survive JSON and back unchanged."""
    state = flow.begin_tasks(_started("interactive"))
    state = flow.complete_task(state, TASKS)
    assert SessionState.from_dict(state.to_dict()) == state


def test_empty_store_yields_a_fresh_session():
    assert SessionState.from_dict(None) == SessionState()
    assert SessionState.from_dict({}).stage is Stage.CONSENT


def test_malformed_store_is_rejected():
    with pytest.raises(FlowError, match="Malformed session state"):
        SessionState.from_dict({"stage": "nonsense"})


def test_answer_key_is_not_shipped_to_the_browser():
    """A correct answer in the task object would be readable in the page source."""
    assert not any("answer" in f and f != "answer_kind" for f in Task.__slots__), (
        "Task must not carry a correct answer; scoring happens offline"
    )
