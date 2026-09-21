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


DEMOGRAPHICS = {
    "age_range": "18–24",
    "field": None,
    "chart_frequency": None,
    "dashboard_familiarity": None,
}


def _started(first_condition: str = "static", first_form: str = "A") -> SessionState:
    """Consent, ID and demographics done: parked on the first condition's instructions."""
    state = flow.give_consent(SessionState(), "2026-09-21T10:00:00Z", "drawn")
    state = flow.set_participant(state, "P01", first_condition, first_form)
    return flow.submit_demographics(state, DEMOGRAPHICS)


def _first_tasks(state: SessionState) -> SessionState:
    """Instructions -> practice -> the first scored task of the FIRST condition."""
    return flow.begin_tasks(flow.begin_practice(state))


def _through_tasks(state: SessionState) -> SessionState:
    """Answer every scored task, leaving the state on that condition's load rating."""
    for _ in range(len(TASKS)):
        state = flow.complete_task(state, TASKS)
    return state


def _second_tasks(state: SessionState) -> SessionState:
    """Load rating -> break -> instructions -> the first task of the SECOND condition."""
    return flow.begin_tasks(flow.resume_after_break(flow.submit_load(state)))


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
    state = _first_tasks(_started(first_condition, first_form))

    seen = [(flow.current_condition(state), flow.current_form(state))]
    state = _through_tasks(state)
    assert state.stage is Stage.LOAD
    assert flow.submit_load(state).stage is Stage.BREAK

    state = _second_tasks(state)
    seen.append((flow.current_condition(state), flow.current_form(state)))
    state = flow.submit_load(_through_tasks(state))

    assert state.stage is Stage.COMPLETE
    assert sorted(c for c, _ in seen) == ["interactive", "static"]
    assert sorted(f for _, f in seen) == ["A", "B"]
    assert seen[0] == (first_condition, first_form)


def test_form_never_repeats_within_a_session():
    """The whole point of parallel forms: nobody answers the same question twice."""
    for seq in range(1, 9):
        condition, form = db.assignment_for(seq)
        state = _first_tasks(_started(condition, form))
        first = flow.current_form(state)
        second = flow.current_form(_second_tasks(_through_tasks(state)))
        assert first != second, f"seq {seq} would show form {first} twice"


def test_is_interactive_tracks_the_current_condition():
    state = _first_tasks(_started("static"))
    assert flow.is_interactive(state) is False
    state = _through_tasks(state)
    assert flow.is_interactive(state) is False, (
        "the load rating is ABOUT the condition just finished, so the state must still name it"
    )
    assert flow.is_interactive(flow.submit_load(state)) is True


def test_other_condition_and_other_form_are_involutions():
    for condition in flow.CONDITIONS:
        assert flow.other_condition(flow.other_condition(condition)) == condition
    for form in flow.FORMS:
        assert flow.other_form(flow.other_form(form)) == form


def test_condition_order_is_one_then_two():
    state = _first_tasks(_started())
    assert flow.condition_order(state) == 1
    state = _through_tasks(state)
    assert flow.condition_order(state) == 1, "still the first condition until the load rating is in"
    assert flow.condition_order(flow.submit_load(state)) == 2


def test_accessors_before_assignment_are_errors():
    with pytest.raises(FlowError, match="No condition assigned"):
        flow.current_condition(SessionState())
    with pytest.raises(FlowError, match="No form assigned"):
        flow.current_form(SessionState())


# --- Task progression ---------------------------------------------------------------------------


def test_tasks_advance_in_order():
    state = _first_tasks(_started())
    seen = []
    for _ in range(len(TASKS)):
        seen.append(flow.current_task(state, TASKS).task_id)
        state = flow.complete_task(state, TASKS)
    assert seen == ["T1", "T2", "T3"]


def test_task_index_resets_for_the_second_condition():
    state = _second_tasks(_through_tasks(_first_tasks(_started())))
    assert state.task_index == 0
    assert flow.current_task(state, TASKS).task_id == "T1"


def test_last_task_goes_to_the_load_rating_not_the_break():
    """The Paas rating is about the condition just finished, so it precedes the handover."""
    state = _through_tasks(_first_tasks(_started()))
    assert state.stage is Stage.LOAD


def test_condition_index_advances_at_the_load_rating():
    state = _through_tasks(_first_tasks(_started()))
    assert state.condition_index == 0
    assert flow.submit_load(state).condition_index == 1


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
    with pytest.raises(FlowError, match="Expected stage instructions or practice"):
        flow.begin_tasks(fresh)
    with pytest.raises(FlowError, match="Expected stage task"):
        flow.complete_task(fresh, TASKS)
    with pytest.raises(FlowError, match="Expected stage load"):
        flow.submit_load(fresh)
    with pytest.raises(FlowError, match="Expected stage break"):
        flow.resume_after_break(fresh)


# --- Practice and the second condition's instructions --------------------------------------------


def test_practice_precedes_the_first_condition():
    state = flow.begin_practice(_started())
    assert state.stage is Stage.PRACTICE
    assert flow.begin_tasks(state).stage is Stage.TASK


def test_practice_does_not_run_before_the_second_condition():
    """It teaches the interface; a participant reaching their second condition has used it."""
    second = flow.resume_after_break(flow.submit_load(_through_tasks(_first_tasks(_started()))))
    assert second.stage is Stage.INSTRUCTIONS
    with pytest.raises(FlowError, match="only before the first condition"):
        flow.begin_practice(second)


def test_the_break_leads_back_to_instructions_not_to_the_tasks():
    """Whoever gets the interactive version second must be told the controls exist."""
    state = flow.submit_load(_through_tasks(_first_tasks(_started())))
    assert state.stage is Stage.BREAK
    assert flow.resume_after_break(state).stage is Stage.INSTRUCTIONS


def test_the_second_conditions_instructions_describe_the_second_condition():
    """The re-shown instructions describe the condition about to start, not the one just done."""
    finished = _through_tasks(_first_tasks(_started("static")))
    state = flow.resume_after_break(flow.submit_load(finished))
    assert flow.is_interactive(state) is True


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


# --- Consent, decline and demographics (IRB form items 12A, 12B, 17) ---------------------------


def test_declining_leads_to_the_declined_screen_and_back():
    declined = flow.decline(SessionState())
    assert declined.stage is Stage.DECLINED
    assert flow.reconsider(declined).stage is Stage.CONSENT


def test_nothing_but_the_consent_screen_can_decline():
    with pytest.raises(FlowError, match="Expected stage consent"):
        flow.decline(_started())
    with pytest.raises(FlowError, match="Expected stage declined"):
        flow.reconsider(SessionState())


def test_a_declined_participant_cannot_enter_an_id():
    with pytest.raises(FlowError, match="Expected stage participant_id"):
        flow.set_participant(flow.decline(SessionState()), "P01", "static", "A")


def test_consent_records_how_the_form_was_signed():
    assert flow.give_consent(SessionState(), "t", "paper").consent_method == "paper"


def test_demographics_come_between_the_id_and_the_instructions():
    state = flow.set_participant(flow.give_consent(SessionState(), "t"), "P01", "static", "A")
    assert state.stage is Stage.DEMOGRAPHICS
    with pytest.raises(FlowError, match="Expected stage instructions"):
        flow.begin_practice(state)
    state = flow.submit_demographics(state, DEMOGRAPHICS)
    assert state.stage is Stage.INSTRUCTIONS
    assert state.demographics == DEMOGRAPHICS


def test_demographics_survive_the_store():
    """Held in browser session state until condition 1's logger opens, so they must round-trip."""
    state = _started()
    assert SessionState.from_dict(state.to_dict()).demographics == DEMOGRAPHICS
