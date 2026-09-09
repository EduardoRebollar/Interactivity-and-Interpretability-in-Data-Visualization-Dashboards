"""Tests for the study event logger.

This logging is the study's primary data, so these tests focus on the properties that would
silently corrupt an analysis: record shape, task attribution, monotonic timings, and durability.
"""

from __future__ import annotations

import json

import pytest

from src import logging as study_logging
from src.logging import EVENTS, SCHEMA_VERSION, LogError, StudyLogger, read_log

REQUIRED_KEYS = {
    "schema_version",
    "session_id",
    "participant_id",
    "condition",
    "condition_order",
    "task_id",
    "event",
    "timestamp",
    "elapsed_ms",
    "task_elapsed_ms",
    "payload",
}


@pytest.fixture
def logger(tmp_path):
    log = StudyLogger("P07", condition_order=1, interactive=True, log_dir=tmp_path)
    yield log
    if not log._handle.closed:
        log.close()


# --- Construction -----------------------------------------------------------------------------


def test_rejects_empty_participant_id(tmp_path):
    with pytest.raises(LogError, match="participant_id"):
        StudyLogger("   ", condition_order=1, log_dir=tmp_path)


def test_rejects_bad_condition_order(tmp_path):
    with pytest.raises(LogError, match="condition_order"):
        StudyLogger("P07", condition_order=3, log_dir=tmp_path)


def test_condition_derives_from_interactive_flag(tmp_path):
    static = StudyLogger("P07", condition_order=1, interactive=False, log_dir=tmp_path)
    interactive = StudyLogger("P07", condition_order=2, interactive=True, log_dir=tmp_path)
    assert static.condition == "static"
    assert interactive.condition == "interactive"
    static.close()
    interactive.close()


def test_filename_identifies_participant_and_condition(logger):
    assert logger.path.name.startswith("P07_interactive_")
    assert logger.path.suffix == ".jsonl"


def test_two_sessions_do_not_overwrite_each_other(tmp_path):
    """A re-run must never clobber an earlier participant's file."""
    first = StudyLogger("P07", condition_order=1, interactive=True, log_dir=tmp_path)
    first.close()
    second = StudyLogger("P07", condition_order=2, interactive=False, log_dir=tmp_path)
    second.close()
    assert first.path != second.path
    assert len(list(tmp_path.glob("*.jsonl"))) == 2


# --- Record shape -----------------------------------------------------------------------------


def test_session_start_is_written_automatically(logger):
    records = read_log(logger.path)
    assert records[0]["event"] == "session_start"
    assert records[0]["payload"]["interactive"] is True


def test_every_record_has_the_full_key_set(logger):
    logger.start_task("T1")
    logger.event("line_isolate", entity="Nigeria", isolated=True)
    logger.end_task("T1")
    logger.close()
    for record in read_log(logger.path):
        assert set(record) == REQUIRED_KEYS, f"{record['event']} has wrong keys"
        assert record["schema_version"] == SCHEMA_VERSION


def test_unknown_event_is_rejected(logger):
    """A typo must fail loudly, not invent an event type analysis would miss."""
    with pytest.raises(LogError, match="Unknown event"):
        logger.event("filter_chnage", control="country")


def test_all_documented_events_are_accepted(logger):
    for name in EVENTS:
        if name in ("task_start", "task_end", "session_end"):
            continue  # emitted through the lifecycle methods
        logger.event(name)


def test_session_id_is_stable_within_a_session(logger):
    logger.event("view_change", control="vaccine", value="MCV1", previous="DTP3")
    ids = {r["session_id"] for r in read_log(logger.path)}
    assert len(ids) == 1


# --- Task attribution -------------------------------------------------------------------------


def test_events_are_attributed_to_the_open_task(logger):
    logger.start_task("T2")
    logger.event("sort_change", key="coverage_pct", direction="desc")
    records = read_log(logger.path)
    assert records[-1]["task_id"] == "T2"


def test_events_outside_a_task_have_null_task_id(logger):
    logger.event("view_change", control="vaccine", value="MCV1", previous="DTP3")
    records = read_log(logger.path)
    assert records[-1]["task_id"] is None
    assert records[-1]["task_elapsed_ms"] is None


def test_task_id_clears_after_end(logger):
    logger.start_task("T1")
    logger.end_task("T1")
    logger.event("view_change", control="vaccine", value="MCV1", previous="DTP3")
    assert read_log(logger.path)[-1]["task_id"] is None


def test_cannot_nest_tasks(logger):
    logger.start_task("T1")
    with pytest.raises(LogError, match="still open"):
        logger.start_task("T2")


def test_cannot_end_a_task_that_is_not_open(logger):
    with pytest.raises(LogError, match="No task is open"):
        logger.end_task("T1")


def test_cannot_end_the_wrong_task(logger):
    logger.start_task("T1")
    with pytest.raises(LogError, match="not 'T9'"):
        logger.end_task("T9")


# --- Timing -----------------------------------------------------------------------------------


def test_elapsed_is_monotonic_non_negative(logger):
    logger.start_task("T1")
    for _ in range(5):
        logger.event("line_isolate", entity="Brazil", isolated=True)
    elapsed = [r["elapsed_ms"] for r in read_log(logger.path)]
    assert all(e >= 0 for e in elapsed)
    assert elapsed == sorted(elapsed)


def test_task_duration_is_recorded_on_end(logger):
    logger.start_task("T1")
    record = logger.end_task("T1")
    assert record["event"] == "task_end"
    assert isinstance(record["payload"]["duration_ms"], int)
    assert record["payload"]["duration_ms"] >= 0


def test_task_elapsed_resets_between_tasks(logger):
    logger.start_task("T1")
    for _ in range(200):
        logger.event("line_isolate", entity="India", isolated=False)
    logger.end_task("T1")
    logger.start_task("T2")
    second = logger.event("line_isolate", entity="India", isolated=True)
    first_end = [r for r in read_log(logger.path) if r["event"] == "task_end"][0]
    assert second["task_elapsed_ms"] <= first_end["task_elapsed_ms"]


# --- Durability and lifecycle -----------------------------------------------------------------


def test_records_are_flushed_immediately(logger):
    """A crash mid-session must not lose already-logged events."""
    logger.start_task("T1")
    logger.event("line_isolate", entity="Nigeria", isolated=True)
    # Read without closing the handle.
    assert len(read_log(logger.path)) == 3


def test_close_writes_session_end(logger):
    logger.close()
    assert read_log(logger.path)[-1]["event"] == "session_end"


def test_close_ends_an_abandoned_task(logger):
    logger.start_task("T4")
    logger.close()
    events = [r["event"] for r in read_log(logger.path)]
    assert events[-2:] == ["task_end", "session_end"]
    assert read_log(logger.path)[-1]["payload"]["reason"] == "task_abandoned"


def test_close_is_idempotent(logger):
    logger.close()
    logger.close()
    assert sum(r["event"] == "session_end" for r in read_log(logger.path)) == 1


def test_context_manager_records_an_exception(tmp_path):
    with (
        pytest.raises(ValueError),
        StudyLogger("P09", condition_order=2, interactive=True, log_dir=tmp_path) as log,
    ):
        log.start_task("T1")
        raise ValueError("boom")
    records = read_log(log.path)
    assert records[-1]["payload"]["reason"] == "error:ValueError"


def test_truncated_final_line_still_parses(logger):
    """A killed process leaves a partial line; the rest of the session must survive."""
    logger.event("line_isolate", entity="Ukraine", isolated=True)
    logger._handle.write('{"schema_version": 1, "sess')
    logger._handle.flush()
    records = read_log(logger.path)
    assert len(records) == 2
    assert records[-1]["event"] == "line_isolate"


def test_corrupt_middle_line_raises(logger, tmp_path):
    logger.close()
    text = logger.path.read_text(encoding="utf-8").splitlines()
    text.insert(1, "{ not json")
    logger.path.write_text("\n".join(text) + "\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_log(logger.path)


def test_read_all_collects_every_session(tmp_path):
    for order, interactive in ((1, True), (2, False)):
        with StudyLogger("P11", condition_order=order, interactive=interactive, log_dir=tmp_path):
            pass
    records = study_logging.read_all(tmp_path)
    assert {r["condition"] for r in records} == {"static", "interactive"}
    assert {r["condition_order"] for r in records} == {1, 2}
