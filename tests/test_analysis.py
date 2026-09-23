"""Tests for the scoring pipeline: events to tidy frames, exclusions, the RQ2 harness, the report.

The most important tests here run real sessions through `src.app.step` -- the same function the
deployed callbacks call -- and score what the app actually logged. A pipeline tested only on
hand-built frames would pass while disagreeing with the data the instrument produces.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pandas as pd
import pytest

from analysis import coding, exclusions, keys, reshape
from analysis import report as study_report
from src import app, consent, db, flow, runtime_data, tasks
from src import logging as study_logging
from src.flow import SessionState, Stage

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


# --- Real sessions ------------------------------------------------------------------------------


def _participant_for(first_condition: str, first_form: str) -> str:
    """A participant id the local (no-database) assignment puts in the requested cell."""
    for n in range(1000):
        candidate = f"P{n:03d}"
        if db.assignment_for(sum(candidate.encode()) % 4) == (first_condition, first_form):
            return candidate
    raise AssertionError("no id found")


def run_session(log_dir, participant_id, answer_for, duration_ms=5000.0, load=5):
    """Drive a complete session through app.step. `answer_for(form, task_id)` picks each answer."""
    session = log = None

    def click(trigger, **kwargs):
        nonlocal session, log
        session, log, _screen, error, _spool = app.step(
            trigger, session, log, log_dir=log_dir, **kwargs
        )
        assert error == "", error

    record = consent.build_record(
        "2026-09-16T10:00:00.000Z", "Test Participant", "2026-09-16", [[[1, 1]] * 12]
    )
    click("consent-clock", consented_at=record["consented_at"], consent_record=record)
    click("participant-button", participant_id=participant_id)
    click("demographics-clock", demographics={"age_range": "25–34"})
    for condition in range(2):
        click("begin-button")
        if condition == 0:
            click("submit-clock", answer="It fell", justification="Practice.", duration_ms=4000.0)
        for _ in range(len(tasks.for_form("A"))):
            state = SessionState.from_dict(session)
            form = flow.current_form(state)
            task = flow.current_task(state, tasks.for_form(form))
            click(
                "submit-clock",
                answer=answer_for(form, task.task_id),
                justification=f"Because of the {task.task_id} lines.",
                duration_ms=duration_ms(form, task.task_id)
                if callable(duration_ms)
                else duration_ms,
            )
        click("survey-clock", load=load, survey={"clarity": 5, "ease_of_use": 5, "confidence": 5})
        if condition == 0:
            click("resume-button")
    assert SessionState.from_dict(session).stage is Stage.COMPLETE


def correct_answer(form, task_id):
    return keys.EXPECTED[(form, task_id)]


def wrong_answer(form, task_id):
    task = next(t for t in tasks.for_form(form) if t.task_id == task_id)
    return next(option for option in task.options if option != keys.EXPECTED[(form, task_id)])


def _score(log_dir):
    events = reshape.events_frame(study_logging.read_all(log_dir))
    tasks_frame = reshape.tidy_tasks(events)
    conditions = reshape.tidy_conditions(events, tasks_frame)
    return events, tasks_frame, conditions


def test_a_real_session_scores_all_correct(tmp_path):
    run_session(tmp_path, _participant_for("static", "A"), correct_answer)
    _events, tasks_frame, conditions = _score(tmp_path)

    assert len(tasks_frame) == 12, "six scored answers per condition, practice dropped"
    assert tasks_frame["correct"].all()
    assert set(tasks_frame["task_id"]) == {"T1", "T2", "T3", "T4", "T5", "T6"}
    assert len(conditions) == 2
    assert set(conditions["prop_correct"]) == {1.0}
    assert set(conditions["paas"]) == {5}
    charts = {(t.form, t.task_id): t.chart for f in tasks.FORMS for t in tasks.for_form(f)}
    assert all(
        charts[(form, task_id)] == chart
        for form, task_id, chart in tasks_frame[["form", "task_id", "chart"]].itertuples(
            index=False
        )
    ), "each answer carries the chart type it was given on"
    assert conditions["ended"].all()


def test_a_real_session_scores_all_wrong(tmp_path):
    run_session(tmp_path, _participant_for("interactive", "B"), wrong_answer)
    _events, tasks_frame, conditions = _score(tmp_path)
    assert not tasks_frame["correct"].any()
    assert set(conditions["prop_correct"]) == {0.0}


def test_correctness_is_attributed_to_the_right_condition_and_form(tmp_path):
    """Right in static/A, wrong in interactive/B. A swapped attribution would invert RQ1."""
    participant = _participant_for("static", "A")

    def answers(form, task_id):
        return correct_answer(form, task_id) if form == "A" else wrong_answer(form, task_id)

    run_session(tmp_path, participant, answers)
    _events, tasks_frame, _conditions = _score(tmp_path)
    by_cell = tasks_frame.groupby(["condition", "form"])["correct"].mean().to_dict()
    assert by_cell == {("static", "A"): 1.0, ("interactive", "B"): 0.0}


def test_the_practice_answer_is_never_scored(tmp_path):
    run_session(tmp_path, _participant_for("static", "B"), correct_answer)
    _events, tasks_frame, _conditions = _score(tmp_path)
    assert tasks.PRACTICE.task_id not in set(tasks_frame["task_id"])


def test_the_csv_export_route_matches_the_record_route(tmp_path, monkeypatch):
    """export_logs.py writes the payload as a JSON string; the database returns a dict. The two
    routes must score identically, or a CSV-based and a database-based analysis could disagree."""
    logs = tmp_path / "logs"
    run_session(logs, _participant_for("interactive", "A"), wrong_answer)
    records = study_logging.read_all(logs)

    export_logs = _script("export_logs")
    monkeypatch.setattr(export_logs.study_logging, "read_all", lambda: records)
    csv_path = tmp_path / "events.csv"
    monkeypatch.setattr("sys.argv", ["export_logs", "--out", str(csv_path)])
    assert export_logs.main() == 0

    from_records = reshape.tidy_tasks(reshape.events_frame(records))
    from_csv = reshape.tidy_tasks(reshape.events_frame(reshape.read_export(csv_path)))
    pd.testing.assert_frame_equal(from_records, from_csv)


def test_mixed_schema_versions_are_refused(tmp_path):
    run_session(tmp_path, _participant_for("static", "A"), correct_answer)
    records = study_logging.read_all(tmp_path)
    records[0] = {**records[0], "schema_version": 3}
    with pytest.raises(reshape.ReshapeError, match="schema versions"):
        reshape.events_frame(records)


def test_an_interactive_event_in_the_static_condition_fails_the_manipulation_check(tmp_path):
    run_session(tmp_path, _participant_for("static", "A"), correct_answer)
    records = study_logging.read_all(tmp_path)
    answer = next(
        r
        for r in records
        if r["event"] == "answer_submit" and r["condition"] == "static" and r["task_id"] == "T1"
    )
    records.append({**answer, "event": "line_isolate", "payload": {"entity": "Brazil"}})
    with pytest.raises(reshape.ReshapeError, match="manipulation check"):
        reshape.tidy_tasks(reshape.events_frame(records))


def test_view_change_in_the_static_condition_is_allowed(tmp_path):
    """The schema documents view_change as possible in both conditions."""
    run_session(tmp_path, _participant_for("static", "A"), correct_answer)
    records = study_logging.read_all(tmp_path)
    answer = next(
        r
        for r in records
        if r["event"] == "answer_submit" and r["condition"] == "static" and r["task_id"] == "T1"
    )
    records.append({**answer, "event": "view_change", "payload": {"control": "chart"}})
    tasks_frame = reshape.tidy_tasks(reshape.events_frame(records))
    assert tasks_frame["n_view_change"].sum() == 1


def test_interaction_counts_attach_to_the_task_they_happened_on(tmp_path):
    run_session(tmp_path, _participant_for("interactive", "A"), correct_answer)
    records = study_logging.read_all(tmp_path)
    t3 = next(
        r
        for r in records
        if r["event"] == "answer_submit"
        and r["task_id"] == "T3"
        and r["condition"] == "interactive"
    )
    for _ in range(2):
        records.append({**t3, "event": "filter_change", "payload": {}})
    tasks_frame = reshape.tidy_tasks(reshape.events_frame(records))
    counts = tasks_frame.set_index(["session_id", "task_id"])["n_filter_change"]
    assert counts[(str(t3["session_id"]), "T3")] == 2
    assert counts.sum() == 2


def test_an_invalid_duration_reaches_the_tidy_frame_as_absent(tmp_path):
    participant = _participant_for("static", "A")
    run_session(tmp_path, participant, correct_answer, duration_ms=lambda f, t: 5000.0)
    records = study_logging.read_all(tmp_path)
    for record in records:
        if record["event"] == "answer_submit" and record["task_id"] == "T2":
            record["payload"] = {
                **record["payload"],
                "duration_ms": None,
                "duration_invalid": "clock_reset",
            }
    tasks_frame = reshape.tidy_tasks(reshape.events_frame(records))
    t2 = tasks_frame[tasks_frame["task_id"] == "T2"]
    assert t2["duration_ms"].isna().all()
    assert set(t2["duration_invalid"]) == {"clock_reset"}


# --- Exclusions ---------------------------------------------------------------------------------


def _frames(rows: list[dict], sessions: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = {
        "form": "A",
        "kind": "rank",
        "chart": "bar",
        "answer": "x",
        "justification": "y",
        "duration_invalid": None,
        "correct": True,
    }
    tasks_frame = pd.DataFrame([{**base, **row} for row in rows])
    tasks_frame["duration_ms"] = pd.to_numeric(tasks_frame["duration_ms"])
    conditions = pd.DataFrame(
        [{"ended": True, "degraded": False, "paas": 5, **session} for session in sessions]
    )
    return tasks_frame, conditions


def _complete(participant: str, durations=None, condition_pair=("static", "interactive")):
    rows, sessions = [], []
    for index, condition in enumerate(condition_pair):
        session = f"{participant}-s{index}"
        sessions.append(
            {"participant_id": participant, "session_id": session, "condition": condition}
        )
        for n in range(6):
            duration = durations[index][n] if durations else 5000.0
            rows.append(
                {
                    "participant_id": participant,
                    "session_id": session,
                    "condition": condition,
                    "task_id": f"T{n + 1}",
                    "duration_ms": duration,
                }
            )
    return rows, sessions


def _by_rule(report):
    return {e.rule: e for e in report}


def test_a_complete_participant_is_not_excluded():
    tasks_frame, conditions = _frames(*_complete("P1"))
    scored, report = exclusions.apply(tasks_frame, conditions)
    assert scored["use_accuracy"].all() and scored["use_timing"].all()
    assert all(e.n_rows == 0 for e in report if e.kind != "report")


def test_a_participant_with_one_session_is_excluded_entirely():
    rows, sessions = _complete("P1")
    tasks_frame, conditions = _frames(rows[:6], sessions[:1])
    scored, report = exclusions.apply(tasks_frame, conditions)
    assert not scored["use_accuracy"].any()
    assert _by_rule(report)["incomplete_session"].ids == ("P1",)


def test_a_participant_who_restarted_is_excluded_for_inspection():
    """Three sessions under one ID is the signature of a closed tab and a restart."""
    rows, sessions = _complete("P1")
    extra_rows, extra_sessions = _complete("P1", condition_pair=("static",))
    extra_sessions[0]["session_id"] = "P1-restart"
    for row in extra_rows:
        row["session_id"] = "P1-restart"
    tasks_frame, conditions = _frames(rows + extra_rows, sessions + extra_sessions)
    scored, _report = exclusions.apply(tasks_frame, conditions)
    assert not scored["use_accuracy"].any()


def test_a_session_that_never_ended_is_incomplete():
    rows, sessions = _complete("P1")
    sessions[1]["ended"] = False
    tasks_frame, conditions = _frames(rows, sessions)
    scored, _report = exclusions.apply(tasks_frame, conditions)
    assert not scored["use_accuracy"].any()


def test_too_fast_is_a_strict_threshold():
    durations = [[2999.0, 3000.0, 5000.0, 5000.0, 5000.0, 5000.0], [5000.0] * 6]
    tasks_frame, conditions = _frames(*_complete("P1", durations))
    scored, report = exclusions.apply(tasks_frame, conditions)
    assert list(scored.loc[scored["duration_ms"] == 2999.0, "use_accuracy"]) == [False]
    assert list(scored.loc[scored["duration_ms"] == 3000.0, "use_accuracy"]) == [True]
    assert _by_rule(report)["too_fast"].n_rows == 1


def test_a_missing_duration_is_not_counted_as_too_fast():
    """Unknown is not fast. Sweeping nulls into too_fast would throw away answers that are fine."""
    durations = [[None, 5000.0, 5000.0, 5000.0, 5000.0, 5000.0], [5000.0] * 6]
    tasks_frame, conditions = _frames(*_complete("P1", durations))
    scored, report = exclusions.apply(tasks_frame, conditions)
    missing = scored[scored["duration_ms"].isna()]
    assert missing["use_accuracy"].all(), "its answer still counts"
    assert not missing["use_timing"].any(), "its duration does not"
    assert _by_rule(report)["too_fast"].n_rows == 0
    assert _by_rule(report)["invalid_timing"].n_rows == 1


def test_a_flagged_duration_keeps_its_accuracy_but_not_its_timing():
    rows, sessions = _complete("P1")
    rows[0]["duration_invalid"] = "clock_reset"
    tasks_frame, conditions = _frames(rows, sessions)
    scored, _report = exclusions.apply(tasks_frame, conditions)
    flagged = scored[scored["duration_invalid"].notna()]
    assert flagged["use_accuracy"].all()
    assert not flagged["use_timing"].any()


def test_the_duration_trim_is_pooled_across_conditions():
    """A per-condition trim removes a different number of rows from each condition and can create a
    difference by itself. Here every long duration is in the interactive condition."""
    participants = [f"P{n}" for n in range(10)]
    rows, sessions = [], []
    for index, participant in enumerate(participants):
        static = [4000.0 + index * 10 + n for n in range(6)]
        interactive = [9000.0 + index * 100 + n for n in range(6)]
        more_rows, more_sessions = _complete(participant, [static, interactive])
        rows += more_rows
        sessions += more_sessions
    tasks_frame, conditions = _frames(rows, sessions)
    scored, _report = exclusions.apply(tasks_frame, conditions)

    cutoff = tasks_frame["duration_ms"].quantile(exclusions.TOP_TRIM_QUANTILE)
    trimmed = scored[~scored["use_timing"]]
    assert (trimmed["duration_ms"] > cutoff).all()
    assert set(trimmed["condition"]) == {"interactive"}
    static_cutoff = tasks_frame.loc[tasks_frame["condition"] == "static", "duration_ms"].quantile(
        0.99
    )
    static_above_own = scored[
        (scored["condition"] == "static") & (scored["duration_ms"] > static_cutoff)
    ]
    assert static_above_own["use_timing"].all(), "a per-condition trim would have removed these"


def test_each_row_is_counted_by_one_rule_only():
    durations = [[1000.0, 5000.0, 5000.0, 5000.0, 5000.0, 5000.0], [None] + [5000.0] * 5]
    tasks_frame, conditions = _frames(*_complete("P1", durations))
    _scored, report = exclusions.apply(tasks_frame, conditions)
    rows_named = [row for e in report if e.kind != "report" for row in e.ids if ":" in row]
    assert len(rows_named) == len(set(rows_named))


def test_a_degraded_session_is_reported_not_excluded():
    rows, sessions = _complete("P1")
    sessions[0]["degraded"] = True
    tasks_frame, conditions = _frames(rows, sessions)
    scored, report = exclusions.apply(tasks_frame, conditions)
    assert scored["use_accuracy"].all() and scored["use_timing"].all()
    assert _by_rule(report)["degraded_session"].ids == ("P1-s0",)


def test_the_rules_run_in_the_pre_registered_order():
    assert [e.rule for e in exclusions.apply(*_frames(*_complete("P1")))[1]] == [
        "incomplete_session",
        "too_fast",
        "invalid_timing",
        "top_one_percent",
        "degraded_session",
    ]


# --- RQ2 coding harness -------------------------------------------------------------------------


def _units(n_per_condition=10):
    rows = []
    for condition in ("static", "interactive"):
        for n in range(n_per_condition):
            rows.append(
                {
                    "participant_id": f"P{n}",
                    "session_id": f"{condition}-{n}",
                    "condition": condition,
                    "form": "A",
                    "task_id": "T1",
                    "justification": f"reason {condition} {n}",
                }
            )
    return coding.build_units(rows)


def test_the_coding_sheet_leaks_nothing_that_identifies_the_condition(tmp_path):
    units = _units()
    path = tmp_path / "sheet.csv"
    coding.write_sheet(units, path)
    sheet = pd.read_csv(path, dtype=str)
    assert list(sheet.columns) == list(coding.SHEET_COLUMNS)
    raw = path.read_text(encoding="utf-8")
    for unit in units:
        assert unit.session_id not in raw.replace(unit.justification, "")
        assert unit.participant_id not in raw.replace(unit.justification, "")


def test_unit_ids_are_stable_and_opaque():
    assert coding.unit_id("session-1", "T1") == coding.unit_id("session-1", "T1")
    assert coding.unit_id("session-1", "T1") != coding.unit_id("session-1", "T2")
    uid = coding.unit_id("11111111-2222", "T1")
    assert len(uid) == 16 and "1111" not in uid


def test_the_shuffle_is_seeded_and_independent_of_input_order():
    units = _units()
    first = [u.unit_id for u in coding.shuffled(units)]
    assert first == [u.unit_id for u in coding.shuffled(list(reversed(units)))]
    assert first != [u.unit_id for u in coding.shuffled(units, seed=1)]


def test_the_shuffle_breaks_the_condition_blocks():
    """Units arrive condition-blocked. A sheet in that order lets a coder infer condition."""
    conditions = [u.condition for u in coding.shuffled(_units(20))]
    switches = sum(a != b for a, b in zip(conditions, conditions[1:], strict=False))
    assert switches > 5


def test_the_double_coded_sample_is_stratified_by_condition():
    units = _units(n_per_condition=12)
    sample = coding.double_coded_sample(units)
    by_condition = {
        c: sum(u.unit_id in sample for u in units if u.condition == c)
        for c in ("static", "interactive")
    }
    assert by_condition == {"static": math.ceil(12 * 0.2), "interactive": math.ceil(12 * 0.2)}
    assert sample == coding.double_coded_sample(list(reversed(units))), "seeded"


def test_a_task_answered_twice_is_refused():
    rows = [
        {
            "participant_id": "P1",
            "session_id": "s",
            "condition": "static",
            "form": "A",
            "task_id": "T1",
            "justification": text,
        }
        for text in ("one", "two")
    ]
    with pytest.raises(coding.CodingError, match="answered twice"):
        coding.build_units(rows)


def _completed(path: Path, rows: list[tuple]):
    path.write_text(
        "unit_id,justification,cites_values,compares_series,notes_uncertainty\n"
        + "".join(",".join(str(v) for v in row) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("rows", "match"),
    [
        ([("u1", "t", 2, 0, 0)], "must be 0 or 1"),
        ([("u1", "t", "", 0, 0)], "must be 0 or 1"),
        ([("u1", "t", 1, 0, 0), ("u1", "t", 1, 0, 0)], "coded twice"),
        ([("u9", "t", 1, 0, 0)], "not in this study"),
        ([], "uncoded"),
    ],
)
def test_an_unusable_coding_sheet_is_refused(tmp_path, rows, match):
    path = tmp_path / "coded.csv"
    _completed(path, rows)
    with pytest.raises(coding.CodingError, match=match):
        coding.read_sheet(path, expected_ids={"u1"})


def test_depth_is_the_sum_of_the_three_codes():
    assert coding.depth({"cites_values": 1, "compares_series": 1, "notes_uncertainty": 0}) == 2


def test_kappa_for_perfect_agreement_is_one():
    assert coding.cohens_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0


def test_kappa_at_chance_is_zero():
    assert coding.cohens_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == 0.0


def test_kappa_matches_a_hand_computed_value():
    # observed 0.7; p1 = 0.6, p2 = 0.5, so expected = 0.6*0.5 + 0.4*0.5 = 0.5; (0.7-0.5)/0.5 = 0.4
    first = [1, 1, 1, 0, 0, 0, 1, 0, 1, 1]
    second = [1, 1, 0, 0, 0, 1, 1, 0, 1, 0]
    assert coding.cohens_kappa(first, second) == pytest.approx(0.4)


def test_kappa_is_undefined_when_neither_rater_varies():
    """Realistic for a rare code on ~60 units. It must read as undefined, not as a number."""
    value = coding.cohens_kappa([0, 0, 0, 0], [0, 0, 0, 0])
    assert math.isnan(value)
    assert coding.format_kappa(value) == "undefined (no variance)"


def test_kappa_is_reported_per_code_with_prevalence():
    primary = {
        "a": {"cites_values": 1, "compares_series": 0, "notes_uncertainty": 0},
        "b": {"cites_values": 0, "compares_series": 1, "notes_uncertainty": 0},
    }
    report = coding.kappa_report(primary, primary)
    assert set(report) == set(coding.CODES)
    assert report["cites_values"]["kappa"] == 1.0
    assert report["cites_values"]["prevalence"] == 0.5
    assert math.isnan(report["notes_uncertainty"]["kappa"])


# --- The scripts, end to end --------------------------------------------------------------------


def test_scoring_and_coding_run_end_to_end_from_an_export(tmp_path, monkeypatch, capsys):
    """export -> score_study -> code_justifications sheets -> (coders) -> kappa -> depth."""
    logs = tmp_path / "logs"
    run_session(logs, _participant_for("static", "A"), correct_answer)
    run_session(logs, _participant_for("interactive", "B"), wrong_answer)
    records = study_logging.read_all(logs)

    export_logs = _script("export_logs")
    monkeypatch.setattr(export_logs.study_logging, "read_all", lambda: records)
    events_csv = tmp_path / "events.csv"
    monkeypatch.setattr("sys.argv", ["export_logs", "--out", str(events_csv)])
    assert export_logs.main() == 0

    derived = tmp_path / "derived"
    score_study = _script("score_study")
    assert score_study.main(["--events", str(events_csv), "--out", str(derived)]) == 0
    printed = capsys.readouterr().out
    assert "Exclusions" in printed and "Accuracy, RQ1" in printed and "Paas" in printed

    scored = pd.read_csv(derived / "tasks.csv", dtype={"participant_id": str})
    assert len(scored) == 24
    by_participant = scored.groupby("participant_id")["correct"].mean().to_dict()
    assert by_participant == {
        _participant_for("static", "A"): 1.0,
        _participant_for("interactive", "B"): 0.0,
    }

    coding_dir = tmp_path / "coding"
    code = _script("code_justifications")
    tasks_arg = ["--tasks", str(derived / "tasks.csv"), "--out", str(coding_dir)]
    assert code.main(["sheets", *tasks_arg]) == 0

    # Stand in for the coders: fill both sheets identically.
    for name in ("coder1.csv", "coder2.csv"):
        sheet = pd.read_csv(coding_dir / name, dtype=str)
        sheet["cites_values"] = "1"
        sheet["compares_series"] = ["0", "1"] * (len(sheet) // 2) + ["0"] * (len(sheet) % 2)
        sheet["notes_uncertainty"] = "0"
        sheet.to_csv(coding_dir / name, index=False)

    assert code.main(["kappa", *tasks_arg]) == 0
    assert "undefined (no variance)" in capsys.readouterr().out
    assert code.main(["depth", *tasks_arg]) == 0
    depth = pd.read_csv(coding_dir / "depth.csv")
    assert len(depth) == 24
    assert set(depth["depth"]) <= {1, 2}


def test_score_study_refuses_a_key_that_does_not_check_out(tmp_path, monkeypatch, capsys):
    score_study = _script("score_study")
    monkeypatch.setattr(score_study.keys, "EXPECTED", {**keys.EXPECTED, ("A", "T1"): "2"})
    assert score_study.main(["--out", str(tmp_path)]) == 1
    assert "answer key does not check out" in capsys.readouterr().err
    assert not list(tmp_path.iterdir()), "nothing may be written against a wrong key"


def test_the_report_renders_every_section(tmp_path):
    run_session(tmp_path, _participant_for("static", "A"), correct_answer)
    _events, tasks_frame, conditions = _score(tmp_path)
    scored, excluded = exclusions.apply(tasks_frame, conditions)
    text = study_report.render(scored, conditions, excluded)
    for title in (
        "Exclusions",
        "Accuracy, RQ1",
        "by item and chart type",
        "Mental effort",
        "Time on task",
    ):
        assert title in text


# --- Skips and the survey (study-design.md sections 6.1 and 7, 2026-09-21) -----------------------


def test_a_skip_is_incorrect_in_the_primary_and_excluded_from_the_secondary(tmp_path):
    """Primary scores a skip as incorrect (out of six, T1-T6); the secondary drops it."""

    def skip_t1(form, task_id):
        return None if task_id == "T1" else correct_answer(form, task_id)

    run_session(tmp_path, _participant_for("static", "A"), skip_t1)
    _events, tasks_frame, conditions = _score(tmp_path)

    skipped = tasks_frame[tasks_frame["task_id"] == "T1"]
    assert skipped["skipped_answer"].all()
    assert not skipped["correct"].any(), "a skip is incorrect under the primary rule"
    assert len(tasks_frame) == 12, "a skip is still an answer record"
    assert set(conditions["prop_correct"]) == {5 / 6}
    assert set(conditions["prop_correct_answered"]) == {1.0}
    assert set(conditions["n_skipped"]) == {1}


def test_every_item_counts_towards_the_rq1_score(tmp_path):
    """Section 7, 2026-09-23: with the gap item gone, all six items are RQ1 items. T6 used to be
    reported on its own; a wrong T6 now lowers accuracy like any other item."""

    def wrong_t6(form, task_id):
        return wrong_answer(form, task_id) if task_id == "T6" else correct_answer(form, task_id)

    run_session(tmp_path, _participant_for("static", "A"), wrong_t6)
    _events, tasks_frame, conditions = _score(tmp_path)

    assert set(conditions["prop_correct"]) == {5 / 6}
    scored, _excluded = exclusions.apply(tasks_frame, conditions)
    assert set(study_report.accuracy(scored)["mean"]) == {5 / 6}


def test_the_item_table_reports_each_item_on_its_chart(tmp_path):
    """Descriptive only (section 7): one row per item, chart type and condition."""
    run_session(tmp_path, _participant_for("interactive", "B"), correct_answer)
    _events, tasks_frame, conditions = _score(tmp_path)
    scored, _excluded = exclusions.apply(tasks_frame, conditions)
    table = study_report.by_item(scored)
    items = {(task_id, chart) for task_id, chart, _kind, _condition in table.index}
    assert items == {(t.task_id, t.chart) for t in tasks.for_form("A")}
    assert (table["correct"] == 1.0).all()
    assert (table["n"] == 1).all()


def test_a_skipped_session_is_not_an_incomplete_one(tmp_path):
    """A skip is a response, not an abandoned session: incomplete_session must not catch it."""
    run_session(tmp_path, _participant_for("static", "A"), lambda form, task_id: None)
    events, tasks_frame, conditions = _score(tmp_path)
    marked, found = exclusions.apply(tasks_frame, conditions)
    rule = next(e for e in found if e.rule == "incomplete_session")
    assert not rule.ids


def test_the_likert_survey_reaches_the_condition_frame(tmp_path):
    run_session(tmp_path, _participant_for("interactive", "A"), correct_answer)
    _events, _tasks, conditions = _score(tmp_path)
    for key in reshape.LIKERT_KEYS:
        assert set(conditions[key]) == {5}


def test_the_report_shows_the_secondary_accuracy_skips_and_survey(tmp_path):
    run_session(tmp_path, _participant_for("static", "B"), correct_answer)
    _events, tasks_frame, conditions = _score(tmp_path)
    marked, found = exclusions.apply(tasks_frame, conditions)
    text = study_report.render(marked, conditions, found)
    assert "skips excluded" in text
    assert "Skipped answers" in text
    assert "clarity" in text
