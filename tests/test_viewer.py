"""Tests for the local data viewer (`analysis/viewer_data.py`, `analysis/viewer_app.py`).

Sessions come from `src.app.step`, via the helpers in test_analysis.py, so every check runs against
what the instrument actually logs. The viewer's job is to show collection problems, so most tests
break a real session in one specific way and assert the matching check -- and only that check --
fails.

These call the functions directly. Like the study app's suite, they cannot see Dash-renderer
failures; the viewer was also driven in a real browser.
"""

from __future__ import annotations

import ast
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from test_analysis import _participant_for, _script, correct_answer, run_session, wrong_answer

from analysis import reshape, sources, viewer_app
from analysis import viewer_data as vd
from src import logging as study_logging
from src import runtime_data

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture(scope="module")
def complete_records(tmp_path_factory):
    """Two complete participants: all correct in cell static/A, all wrong in interactive/B."""
    logs = tmp_path_factory.mktemp("logs")
    run_session(logs, _participant_for("static", "A"), correct_answer)
    run_session(logs, _participant_for("interactive", "B"), wrong_answer)
    return study_logging.read_all(logs)


def _fresh(records):
    return vd.normalise(json.loads(json.dumps(records, default=str)))


def _latest(records) -> datetime:
    return max(vd.parse_ts(r["server_ts"]) for r in records)


def _checks(records, participants=None, now=None, key_problems=()):
    records = vd.normalise(records)
    now = now or _latest(records) + timedelta(minutes=1)
    return {
        c.name: c
        for c in vd.health(records, participants, now=now, key_problems=list(key_problems))
    }


def _not_ok(checks, *allowed):
    return {name for name, c in checks.items() if c.status in (vd.WARN, vd.FAIL)} - set(allowed)


def _answer(records, condition, task_id):
    return next(
        r
        for r in records
        if r["event"] == "answer_submit" and r["condition"] == condition and r["task_id"] == task_id
    )


# --- Health -------------------------------------------------------------------------------------


def test_complete_sessions_pass_every_check(complete_records):
    checks = _checks(_fresh(complete_records))
    assert not _not_ok(checks), {n: checks[n].detail for n in _not_ok(checks)}
    assert checks["Manipulation check"].status == vd.OK


def test_no_events_is_reported_not_raised():
    checks = {c.name: c for c in vd.health([], None, key_problems=[])}
    assert checks["Events"].status == vd.INFO


def test_a_wrong_answer_key_fails(complete_records):
    checks = _checks(_fresh(complete_records), key_problems=["A-T1: data says '1'"])
    assert checks["Answer key"].status == vd.FAIL


def test_an_interactive_event_under_static_fails_the_manipulation_check(complete_records):
    records = _fresh(complete_records)
    records.append({**_answer(records, "static", "T1"), "event": "line_isolate", "payload": {}})
    checks = _checks(records)
    assert checks["Manipulation check"].status == vd.FAIL
    assert _not_ok(checks, "Manipulation check") == set()


def test_mixed_schema_versions_fail(complete_records):
    records = _fresh(complete_records)
    records[0]["schema_version"] = 3
    assert _checks(records)["Schema version"].status == vd.FAIL


def test_an_older_single_schema_version_warns(complete_records):
    records = _fresh(complete_records)
    for record in records:
        record["schema_version"] = study_logging.SCHEMA_VERSION - 1
    assert _checks(records)["Schema version"].status == vd.WARN


def test_an_unknown_event_name_fails(complete_records):
    records = _fresh(complete_records)
    records.append({**records[-1], "event": "filter_chnage"})
    checks = _checks(records)
    assert checks["Event names"].status == vd.FAIL
    assert checks["Event names"].ids == ("filter_chnage x1",)


def test_a_duplicate_answer_fails(complete_records):
    records = _fresh(complete_records)
    records.append(dict(_answer(records, "interactive", "T4")))
    assert _checks(records)["One answer per task"].status == vd.FAIL


def test_a_missing_consent_fails(complete_records):
    records = [r for r in _fresh(complete_records) if r["event"] != "consent"]
    checks = _checks(records)
    assert checks["Consent recorded"].status == vd.FAIL
    assert len(checks["Consent recorded"].ids) == 2


def test_the_same_form_twice_fails(complete_records):
    records = _fresh(complete_records)
    participant = records[0]["participant_id"]
    for record in records:
        if record["participant_id"] == participant:
            record["form"] = "A"
    assert _checks(records)["Condition and form pairing"].status == vd.FAIL


def test_an_outage_warns_and_a_dropped_event_fails(complete_records):
    records = _fresh(complete_records)
    template = records[5]
    records.append(study_logging.recovery_record(template, spooled=3, dropped=0))
    assert _checks(records)["Database outages"].status == vd.WARN
    records.append(study_logging.recovery_record(template, spooled=3, dropped=2))
    assert _checks(records)["Database outages"].status == vd.FAIL


def test_an_unended_session_is_in_progress_then_abandoned(complete_records):
    records = [r for r in _fresh(complete_records) if r["event"] != "session_end"]
    records = [
        r for r in records if not (r["condition_order"] == 2 and r["event"] == "load_rating")
    ]
    last = _latest(records)

    soon = _checks(records, now=last + timedelta(minutes=5))
    assert soon["Sessions ended"].status == vd.INFO
    assert soon["Completeness"].status == vd.OK, "a running participant is not yet incomplete"

    later = _checks(records, now=last + timedelta(minutes=vd.IN_PROGRESS_MINUTES + 1))
    assert later["Sessions ended"].status == vd.WARN
    assert "min ago" in later["Sessions ended"].ids[0]


def test_an_ended_session_short_of_answers_is_incomplete(complete_records):
    records = _fresh(complete_records)
    t3 = _answer(records, "static", "T3")
    records = [r for r in records if r is not t3]
    checks = _checks(records)
    assert checks["Completeness"].status == vd.WARN
    assert any("6/7" in item for item in checks["Completeness"].ids)


def test_a_participant_with_one_session_is_incomplete(complete_records):
    records = [r for r in _fresh(complete_records) if r["condition"] != "interactive"]
    checks = _checks(records, now=_latest(records) + timedelta(hours=3))
    assert any("1 session" in item for item in checks["Completeness"].ids)


def test_a_missing_paas_rating_warns(complete_records):
    records = [r for r in _fresh(complete_records) if r["event"] != "load_rating"]
    assert _checks(records)["Mental-effort rating"].status == vd.WARN


def test_an_invalid_duration_warns_with_its_reason(complete_records):
    records = _fresh(complete_records)
    answer = _answer(records, "static", "T2")
    answer["payload"] = {
        **answer["payload"],
        "duration_ms": None,
        "duration_invalid": "clock_reset",
    }
    check = _checks(records)["Durations"]
    assert check.status == vd.WARN
    assert "clock_reset: 1" in check.detail


def test_registered_participants_without_events_are_listed(complete_records):
    records = _fresh(complete_records)
    people = [{"participant_id": p} for p in {r["participant_id"] for r in records}]
    check = _checks(records, participants=[*people, {"participant_id": "P999"}])[
        "Registered without events"
    ]
    assert check.status == vd.INFO
    assert check.ids == ("P999",)


def test_a_malformed_timestamp_and_payload_do_not_break_health(complete_records):
    records = _fresh(complete_records)
    records[3]["server_ts"] = "not a time"
    records[4]["payload"] = "{not json"
    checks = vd.health(vd.normalise(records), None, key_problems=[])
    assert checks, "health must return, whatever the data looks like"


def test_cell_balance_counts_what_participants_were_shown(complete_records):
    balance = vd.cell_balance(_fresh(complete_records))
    assert len(balance) == 4
    counts = {
        (r["first condition"], r["first form"]): r["participants"]
        for r in balance.to_dict("records")
    }
    assert counts[("static", "A")] == 1
    assert counts[("interactive", "B")] == 1
    assert sum(counts.values()) == 2


# --- Scoring and tables -------------------------------------------------------------------------


def test_scoring_matches_the_score_study_pipeline(complete_records):
    records = _fresh(complete_records)
    scoring = vd.score(records, key_problems=[])
    assert scoring.ok
    events = reshape.events_frame(complete_records)
    expected = reshape.tidy_tasks(events)
    pd.testing.assert_series_equal(
        scoring.tasks["correct"].reset_index(drop=True), expected["correct"].reset_index(drop=True)
    )


def test_a_failed_manipulation_check_is_returned_not_raised(complete_records):
    records = _fresh(complete_records)
    records.append({**_answer(records, "static", "T1"), "event": "sort_change", "payload": {}})
    scoring = vd.score(records, key_problems=[])
    assert not scoring.ok
    assert "manipulation check" in scoring.error

    table = vd.answers(records, scoring)
    assert len(table) == 30, "two participants x (14 scored + 1 practice), still visible"
    assert table["correct"].replace("practice", None).isna().all()
    assert vd.report_tables(scoring) == []


def test_a_wrong_key_refuses_scoring(complete_records):
    scoring = vd.score(_fresh(complete_records), key_problems=["A-T1: wrong"])
    assert not scoring.ok and "answer key" in scoring.error


def test_the_overview_shows_progress_accuracy_and_paas(complete_records):
    records = _fresh(complete_records)
    scoring = vd.score(records, key_problems=[])
    overview = vd.participant_overview(records, scoring, now=_latest(records)).set_index("id")
    right, wrong = _participant_for("static", "A"), _participant_for("interactive", "B")

    assert list(overview.columns) == vd.OVERVIEW_COLUMNS
    assert set(overview["status"]) == {"complete"}
    assert overview.loc[right, "cell"] == "static first, form A"
    assert overview.loc[right, "static answers"] == "7/7"
    assert overview.loc[right, "static accuracy"] == 1.0
    assert overview.loc[wrong, "interactive accuracy"] == 0.0
    assert overview.loc[right, "static Paas"] == 5


def test_the_overview_lists_a_registered_participant_with_no_events(complete_records):
    records = _fresh(complete_records)
    overview = vd.participant_overview(
        records,
        vd.score(records, key_problems=[]),
        [{"participant_id": "P999"}],
        now=_latest(records),
    )
    row = overview[overview["id"] == "P999"].iloc[0]
    assert row["status"] == "registered, no events"


def test_the_overview_names_the_exclusions_that_hit_a_participant(complete_records):
    records = [r for r in _fresh(complete_records) if r["condition"] != "interactive"]
    scoring = vd.score(records, key_problems=[])
    overview = vd.participant_overview(records, scoring, now=_latest(records) + timedelta(hours=3))
    assert set(overview["status"]) == {"incomplete"}
    assert all("incomplete_session" in rules for rules in overview["exclusions"])


def test_justifications_are_hidden_unless_asked_for(complete_records):
    records = _fresh(complete_records)
    scoring = vd.score(records, key_problems=[])

    hidden = vd.answers(records, scoring)
    assert set(hidden["justification"]) == {vd.HIDDEN}
    shown = vd.answers(records, scoring, show_justifications=True)
    assert "Because of the T1 lines." in set(shown["justification"])

    events = vd.events_table(records)
    submits = events[events["event"] == "answer_submit"]
    assert all(json.loads(p)["justification"] == vd.HIDDEN for p in submits["payload"])
    assert "Because of" not in "".join(events["payload"])

    participant = records[0]["participant_id"]
    for detail in vd.participant_detail(records, scoring, participant):
        assert "Because of" not in detail.answers.to_json() + detail.events.to_json()


def test_the_participant_detail_has_one_block_per_session_in_order(complete_records):
    records = _fresh(complete_records)
    participant = _participant_for("interactive", "B")
    details = vd.participant_detail(records, vd.score(records, key_problems=[]), participant)
    assert [d.title for d in details] == [
        "Condition 1: interactive, form B",
        "Condition 2: static, form A",
    ]
    assert list(details[0].answers["task_id"]) == [
        "P0",
        "T1",
        "T2",
        "T3",
        "T4",
        "T5",
        "T6",
        "T7",
    ]
    assert details[1].answers["prompt"].str.len().gt(0).all()
    assert "7/7 scored answers" in details[0].summary


def test_the_report_tables_are_the_section_7_ones(complete_records):
    records = _fresh(complete_records)
    titles = [t for t, _ in vd.report_tables(vd.score(records, key_problems=[]))]
    assert titles[0].startswith("Exclusions")
    assert any(t.startswith("Accuracy, RQ1") for t in titles)
    assert any("Paas" in t for t in titles)


def test_the_events_download_rescores_identically(complete_records, tmp_path):
    """The download must be the export_logs.py format, so score_study.py --events reads it back."""
    records = _fresh(complete_records)
    path = tmp_path / "events.csv"
    path.write_text(vd.events_csv(records), encoding="utf-8")
    from_download = reshape.tidy_tasks(reshape.events_frame(reshape.read_export(path)))
    from_records = reshape.tidy_tasks(reshape.events_frame(complete_records))
    pd.testing.assert_frame_equal(from_download, from_records)


def test_database_style_records_normalise(complete_records):
    """Postgres returns UUID and datetime objects; the viewer must treat them like JSONL text."""
    raw = []
    for record in complete_records:
        row = dict(record)
        row["session_id"] = uuid.UUID(row["session_id"])
        row["server_ts"] = datetime.fromisoformat(row["server_ts"])
        raw.append(row)
    records = vd.normalise(raw)
    assert all(isinstance(r["session_id"], str) for r in records)
    json.dumps(records)  # must be JSON-safe
    assert _not_ok(_checks(raw)) == set()


# --- The app and the launcher -------------------------------------------------------------------


def test_the_snapshot_survives_a_loader_that_fails():
    def broken():
        raise RuntimeError("Neon is asleep")

    snapshot = viewer_app.build_snapshot(broken)
    assert snapshot.load_error and "Neon is asleep" in snapshot.load_error
    assert viewer_app.health_panel(snapshot)


def test_the_app_renders_every_panel(complete_records):
    snapshot = viewer_app.build_snapshot(lambda: (complete_records, None, "test"))
    assert snapshot.scoring.ok
    assert viewer_app.health_panel(snapshot)
    assert viewer_app.summary_panel(snapshot)
    participant = snapshot.records[0]["participant_id"]
    detail = viewer_app.detail_panel(snapshot, participant, show=False)
    assert "Because of" not in json.dumps(detail, default=lambda o: o.to_plotly_json())
    layout = viewer_app.create_app(lambda: (complete_records, None, "test")).layout
    json.dumps(layout, default=lambda o: o.to_plotly_json())


def test_table_rows_are_json_safe(complete_records):
    records = _fresh(complete_records)
    scoring = vd.score(records, key_problems=[])
    for frame in (
        vd.participant_overview(records, scoring),
        vd.answers(records, scoring),
        vd.events_table(records),
    ):
        json.dumps(viewer_app._rows(frame), allow_nan=False)


def test_the_viewer_serves_on_localhost_only():
    view_data = _script("view_data")
    assert view_data.HOST == "127.0.0.1"
    tree = ast.parse((ROOT / "scripts" / "view_data.py").read_text(encoding="utf-8"))
    run_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "run"
    ]
    assert run_calls
    for call in run_calls:
        host = next(k for k in call.keywords if k.arg == "host")
        assert isinstance(host.value, ast.Name) and host.value.id == "HOST"


def test_the_viewer_never_writes_to_the_database():
    for path in ("analysis/viewer_data.py", "analysis/viewer_app.py", "analysis/sources.py"):
        source = (ROOT / path).read_text(encoding="utf-8")
        for forbidden in (
            "insert_event",
            "delete_participant",
            "register_participant",
            "init_schema",
        ):
            assert forbidden not in source, f"{path} calls {forbidden}"


def test_sources_read_local_sessions_when_there_is_no_database(complete_records, tmp_path):
    logs = tmp_path / "logs"
    run_session(logs, _participant_for("static", "B"), correct_answer)
    records, label = sources.load_records(log_dir=logs)
    assert records and "JSONL" in label
    assert sources.load_participants() is None
