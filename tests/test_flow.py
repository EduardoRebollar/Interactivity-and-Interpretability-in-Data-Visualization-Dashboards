"""Tests for the session flow and the 2x2 counterbalancing.

The property that matters most: every participant sees both conditions and both forms, exactly once
each, and the four orderings fill evenly. If that breaks, a practice effect becomes
indistinguishable from an effect of interactivity and the within-subjects design is worthless.
"""

from __future__ import annotations

from collections import Counter

import pytest

from src import db, flow
from src.flow import FlowError, SessionState, Stage, Task

TASKS = tuple(
    Task(
        task_id=f"T{n}",
        form="A",
        kind="trend",
        prompt=f"Placeholder prompt {n}",
        vaccine="DTP3",
        entities=("Nigeria", "India"),
        options=("Nigeria", "India"),
    )
    for n in range(1, 4)
)


def _started(first_condition: str = "static", first_form: str = "A") -> SessionState:
    state = flow.give_consent(SessionState())
    return flow.set_participant(state, "P01", first_condition, first_form)


# --- Counterbalancing ---------------------------------------------------------------------------


def test_assignment_cycles_through_all_four_cells():
    assert db.assignment_for(1) == ("static", "A")
    assert db.assignment_for(2) == ("interactive", "A")
    assert db.assignment_for(3) == ("static", "B")
    assert db.assignment_for(4) == ("interactive", "B")
    assert db.assignment_for(5) == db.assignment_for(1), "should repeat every four"


def test_assignment_is_balanced_over_a_realistic_cohort():
    """n >= 25 is the target; no cell may be more than one ahead of another."""
    cells = Counter(db.assignment_for(seq) for seq in range(1, 26))
    assert len(cells) == 4, f"only {len(cells)} of 4 cells used"
    assert max(cells.values()) - min(cells.values()) <= 1, cells


def test_condition_and_form_are_independently_balanced():
    """Condition must not correlate with form, or the two are confounded."""
    assignments = [db.assignment_for(seq) for seq in range(1, 25)]
    conditions = Counter(c for c, _ in assignments)
    forms = Counter(f for _, f in assignments)
    assert conditions["static"] == conditions["interactive"]
    assert forms["A"] == forms["B"]


# --- Condition and form sequencing ---------------------------------------------------------------


@pytest.mark.parametrize("first_condition", ["static", "interactive"])
@pytest.mark.parametrize("first_form", ["A", "B"])
def test_participant_sees_both_conditions_and_both_forms_once(first_condition, first_form):
    state = flow.begin_tasks(_started(first_condition, first_form))

    seen = [(flow.current_condition(state), flow.current_form(state))]
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    assert state.stage is Stage.BREAK

    state = flow.begin_tasks(state)
    seen.append((flow.current_condition(state), flow.current_form(state)))
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)

    assert state.stage is Stage.COMPLETE
    assert sorted(c for c, _ in seen) == ["interactive", "static"]
    assert sorted(f for _, f in seen) == ["A", "B"]
    assert seen[0] == (first_condition, first_form)


def test_form_never_repeats_within_a_session():
    """The whole point of parallel forms: nobody answers the same question twice."""
    for seq in range(1, 9):
        condition, form = db.assignment_for(seq)
        state = flow.begin_tasks(_started(condition, form))
        first = flow.current_form(state)
        for _ in range(len(TASKS)):
            state = flow.complete_task(state, TASKS)
        second = flow.current_form(flow.begin_tasks(state))
        assert first != second, f"seq {seq} would show form {first} twice"


def test_is_interactive_tracks_the_current_condition():
    state = flow.begin_tasks(_started("static"))
    assert flow.is_interactive(state) is False
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    assert flow.is_interactive(state) is True


def test_other_condition_and_other_form_are_involutions():
    for condition in flow.CONDITIONS:
        assert flow.other_condition(flow.other_condition(condition)) == condition
    for form in flow.FORMS:
        assert flow.other_form(flow.other_form(form)) == form


def test_condition_order_is_one_then_two():
    state = flow.begin_tasks(_started())
    assert flow.condition_order(state) == 1
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    assert flow.condition_order(state) == 2


def test_accessors_before_assignment_are_errors():
    with pytest.raises(FlowError, match="No condition assigned"):
        flow.current_condition(SessionState())
    with pytest.raises(FlowError, match="No form assigned"):
        flow.current_form(SessionState())


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
        flow.set_participant(fresh, "P01", "static", "A")
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
        flow.set_participant(state, "   ", "static", "A")


def test_unknown_condition_or_form_rejected():
    state = flow.give_consent(SessionState())
    with pytest.raises(FlowError, match="Unknown condition"):
        flow.set_participant(state, "P01", "semi-interactive", "A")
    with pytest.raises(FlowError, match="Unknown form"):
        flow.set_participant(state, "P01", "static", "C")


# --- Serialisation ------------------------------------------------------------------------------


def test_state_round_trips_through_a_store():
    """State lives in a browser dcc.Store, so it must survive JSON and back unchanged."""
    state = flow.begin_tasks(_started("interactive", "B"))
    state = flow.complete_task(state, TASKS)
    assert SessionState.from_dict(state.to_dict()) == state


def test_empty_store_yields_a_fresh_session():
    assert SessionState.from_dict(None) == SessionState()
    assert SessionState.from_dict({}).stage is Stage.CONSENT


def test_malformed_store_is_rejected():
    with pytest.raises(FlowError, match="Malformed session state"):
        SessionState.from_dict({"stage": "nonsense"})


def test_task_carries_no_answer_key():
    """A correct answer on the Task object would be readable in the page source."""
    assert "answer" not in Task.__slots__
    assert "correct" not in Task.__slots__
