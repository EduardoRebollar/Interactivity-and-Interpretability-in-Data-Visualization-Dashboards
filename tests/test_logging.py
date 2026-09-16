"""Tests for the study event logger (schema v2).

This logging is the study's primary data, so these focus on what would silently corrupt an analysis:
record shape, task attribution, sink selection, durability, and the separation between the browser
clock (the measurement) and the server clock (a cross-check only).
"""

from __future__ import annotations

import json

import pytest

from src import logging as study_logging
from src.logging import (
    EVENTS,
    SCHEMA_VERSION,
    JsonlSink,
    LogError,
    PostgresSink,
    StudyLogger,
    read_log,
)

REQUIRED_KEYS = {
    "schema_version",
    "session_id",
    "participant_id",
    "condition",
    "condition_order",
    "task_id",
    "event",
    "server_ts",
    "client_elapsed_ms",
    "task_elapsed_ms",
    "server_elapsed_ms",
    "payload",
}


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    """Default every test to the file sink; the Postgres path is selected explicitly."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture
def logger(tmp_path):
    log = StudyLogger("P07", condition_order=1, interactive=True, log_dir=tmp_path)
    yield log
    if not log.closed:
        log.close()


# --- Construction and sink selection ------------------------------------------------------------


def test_rejects_empty_participant_id(tmp_path):
    with pytest.raises(LogError, match="participant_id"):
        StudyLogger("   ", condition_order=1, interactive=True, log_dir=tmp_path)


def test_rejects_bad_condition_order(tmp_path):
    with pytest.raises(LogError, match="condition_order"):
        StudyLogger("P07", condition_order=3, interactive=True, log_dir=tmp_path)


def test_condition_derives_from_interactive_argument(tmp_path):
    """Condition comes from the argument, not a module global — one deployment serves both."""
    static = StudyLogger("P07", condition_order=1, interactive=False, log_dir=tmp_path)
    interactive = StudyLogger("P08", condition_order=2, interactive=True, log_dir=tmp_path)
    assert static.condition == "static"
    assert interactive.condition == "interactive"
    static.close()
    interactive.close()


def test_uses_file_sink_without_a_database(logger):
    assert isinstance(logger._sink, JsonlSink)


def test_uses_postgres_sink_when_database_url_is_set(monkeypatch, tmp_path):
    """The deployed path: a database wins over the filesystem, which Vercel cannot persist."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    written: list[dict] = []
    monkeypatch.setattr(study_logging.db, "insert_event", written.append)

    log = StudyLogger("P07", condition_order=1, interactive=True, log_dir=tmp_path)
    assert isinstance(log._sink, PostgresSink)
    assert written and written[0]["event"] == "session_start"
    assert not list(tmp_path.glob("*.jsonl")), "should not have written a file"


def test_postgres_sink_requires_a_url():
    with pytest.raises(LogError, match="DATABASE_URL"):
        PostgresSink()


def test_two_sessions_do_not_overwrite_each_other(tmp_path):
    first = StudyLogger("P07", condition_order=1, interactive=True, log_dir=tmp_path)
    first.close()
    second = StudyLogger("P07", condition_order=2, interactive=False, log_dir=tmp_path)
    second.close()
    assert first._sink.path != second._sink.path
    assert len(list(tmp_path.glob("*.jsonl"))) == 2


# --- Record shape -----------------------------------------------------------------------------


def test_session_start_is_written_automatically(logger):
    records = read_log(logger._sink.path)
    assert records[0]["event"] == "session_start"
    assert records[0]["payload"]["interactive"] is True


def test_every_record_has_the_full_key_set(logger):
    logger.start_task("T1")
    logger.event("line_isolate", entity="Nigeria", isolated=True)
    logger.end_task("T1", duration_ms=1234.5)
    logger.close()
    for record in read_log(logger._sink.path):
        assert set(record) == REQUIRED_KEYS, f"{record['event']} has wrong keys"
        assert record["schema_version"] == SCHEMA_VERSION


def test_schema_version_is_two():
    assert SCHEMA_VERSION == 2


def test_unknown_event_is_rejected(logger):
    with pytest.raises(LogError, match="Unknown event"):
        logger.event("filter_chnage", control="country")


def test_all_documented_events_are_accepted(logger):
    lifecycle = {"task_start", "task_end", "session_end", "answer_submit"}
    for name in EVENTS:
        if name not in lifecycle:
            logger.event(name)


def test_cannot_log_after_close(logger):
    logger.close()
    with pytest.raises(LogError, match="closed"):
        logger.event("view_change")


# --- Timing separation --------------------------------------------------------------------------


def test_browser_timings_pass_through_untouched(logger):
    """The browser clock is the measurement; the server must not overwrite or recompute it."""
    record = logger.event("view_change", client_elapsed_ms=4321.25, task_elapsed_ms=120.5)
    assert record["client_elapsed_ms"] == 4321.25
    assert record["task_elapsed_ms"] == 120.5


def test_client_timings_are_none_when_not_supplied(logger):
    """Absent is better than wrong: analysis can see the client value is missing."""
    record = logger.event("view_change")
    assert record["client_elapsed_ms"] is None
    assert record["task_elapsed_ms"] is None


def test_server_elapsed_is_always_recorded_as_a_cross_check(logger):
    records = [logger.event("view_change") for _ in range(4)]
    elapsed = [r["server_elapsed_ms"] for r in records]
    assert all(e >= 0 for e in elapsed)
    assert elapsed == sorted(elapsed)


def test_task_end_carries_the_browser_duration(logger):
    logger.start_task("T1", client_elapsed_ms=1000.0)
    record = logger.end_task("T1", duration_ms=8500.0, client_elapsed_ms=9500.0)
    assert record["payload"]["duration_ms"] == 8500.0
    assert record["task_elapsed_ms"] == 8500.0


# --- Task attribution ---------------------------------------------------------------------------


def test_events_are_attributed_to_the_open_task(logger):
    logger.start_task("T2")
    record = logger.event("sort_change", key="coverage_pct", direction="desc")
    assert record["task_id"] == "T2"


def test_events_outside_a_task_have_null_task_id(logger):
    record = logger.event("view_change", control="vaccine", value="MCV1", previous="DTP3")
    assert record["task_id"] is None


def test_task_id_clears_after_end(logger):
    logger.start_task("T1")
    logger.end_task("T1", duration_ms=10.0)
    assert logger.event("view_change")["task_id"] is None


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


# --- Answers ------------------------------------------------------------------------------------


def test_answer_is_recorded_with_its_task(logger):
    logger.start_task("T3")
    record = logger.submit_answer("T3", answer="Nigeria", duration_ms=4200.0)
    assert record["event"] == "answer_submit"
    assert record["payload"]["answer"] == "Nigeria"
    # Attribution lives in the record column, so answers join to tasks the same way events do.
    assert record["task_id"] == "T3"
    assert record["payload"]["duration_ms"] == 4200.0


def test_answer_accepts_structured_values(logger):
    """Answers are not always strings; a multi-select or a rating must survive the round trip."""
    logger.start_task("T4")
    logger.submit_answer("T4", answer={"choice": ["Nigeria", "India"], "confidence": 4})
    logger.close()
    record = [r for r in read_log(logger._sink.path) if r["event"] == "answer_submit"][0]
    assert record["payload"]["answer"] == {"choice": ["Nigeria", "India"], "confidence": 4}


# --- Durability and lifecycle -------------------------------------------------------------------


def test_records_are_flushed_immediately(logger):
    """A crash mid-session must not lose already-logged events."""
    logger.start_task("T1")
    logger.event("line_isolate", entity="Nigeria", isolated=True)
    assert len(read_log(logger._sink.path)) == 3


def test_close_writes_session_end(logger):
    logger.close()
    assert read_log(logger._sink.path)[-1]["event"] == "session_end"


def test_close_ends_an_abandoned_task(logger):
    logger.start_task("T4")
    logger.close()
    records = read_log(logger._sink.path)
    assert [r["event"] for r in records[-2:]] == ["task_end", "session_end"]
    assert records[-1]["payload"]["reason"] == "task_abandoned"


def test_close_is_idempotent(logger):
    logger.close()
    logger.close()
    assert sum(r["event"] == "session_end" for r in read_log(logger._sink.path)) == 1


def test_context_manager_records_an_exception(tmp_path):
    with (
        pytest.raises(ValueError),
        StudyLogger("P09", condition_order=2, interactive=True, log_dir=tmp_path) as log,
    ):
        log.start_task("T1")
        raise ValueError("boom")
    assert read_log(log._sink.path)[-1]["payload"]["reason"] == "error:ValueError"


def test_truncated_final_line_still_parses(logger):
    """A killed process leaves a partial line; the rest of the session must survive."""
    logger.event("line_isolate", entity="Ukraine", isolated=True)
    logger._sink._handle.write('{"schema_version": 2, "sess')
    logger._sink._handle.flush()
    records = read_log(logger._sink.path)
    assert len(records) == 2
    assert records[-1]["event"] == "line_isolate"


def test_corrupt_middle_line_raises(logger):
    logger.close()
    path = logger._sink.path
    lines = path.read_text(encoding="utf-8").splitlines()
    lines.insert(1, "{ not json")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_log(path)


def test_read_all_collects_every_session(tmp_path):
    for order, interactive in ((1, True), (2, False)):
        with StudyLogger("P11", condition_order=order, interactive=interactive, log_dir=tmp_path):
            pass
    records = study_logging.read_all(tmp_path)
    assert {r["condition"] for r in records} == {"static", "interactive"}
    assert {r["condition_order"] for r in records} == {1, 2}
