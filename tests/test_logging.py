"""Tests for the study event logger (schema v4).

This logging is the study's primary data, so these focus on what would silently corrupt an analysis:
record shape, task attribution, sink selection, durability, and the separation between the browser
clock (the measurement) and the server clock (a cross-check only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import logging as study_logging
from src.logging import (
    EVENTS,
    SCHEMA_VERSION,
    JsonlSink,
    LogError,
    PostgresSink,
    ResilientSink,
    StudyLogger,
    read_log,
)

REQUIRED_KEYS = {
    "schema_version",
    "event_uid",
    "session_id",
    "participant_id",
    "condition",
    "condition_order",
    "form",
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
    # Wrapped, so a database failure spools instead of breaking the participant's session.
    assert isinstance(log._sink, ResilientSink)
    assert isinstance(log._sink.inner, PostgresSink)
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


def test_schema_version_is_six():
    """v6: skips are recorded as null, plus the survey, demographics and signature method."""
    assert SCHEMA_VERSION == 6


def test_form_is_recorded_on_every_event():
    """Analysis pairs matched items across forms; an unlabelled event cannot be paired."""
    with StudyLogger(
        "P20", condition_order=1, interactive=True, form="B", log_dir=Path(__file__).parent
    ) as log:
        record = log.event("view_change")
        assert record["form"] == "B"
        path = log._sink.path
    assert all(r["form"] == "B" for r in read_log(path))
    path.unlink()


def test_form_is_validated(tmp_path):
    with pytest.raises(LogError, match="form must be one of"):
        StudyLogger("P07", condition_order=1, interactive=True, form="C", log_dir=tmp_path)


def test_load_rating_records_the_paas_scale(logger):
    record = logger.rate_load(7)
    assert record["event"] == "load_rating"
    assert record["payload"] == {"scale": "paas", "value": 7}


@pytest.mark.parametrize("bad", [0, 10, -1, 4.5, "7", True])
def test_load_rating_rejects_out_of_scale_values(logger, bad):
    """A rating outside 1-9 is not a Paas score and would corrupt the RQ3 measure."""
    with pytest.raises(LogError, match="1-9"):
        logger.rate_load(bad)


def test_a_skipped_load_rating_is_recorded_as_null(logger):
    """IRB form item 10: any question may be skipped. Missing, never zero."""
    assert logger.rate_load(None)["payload"] == {"scale": "paas", "value": None}


def test_the_survey_records_all_three_likert_items(logger):
    record = logger.rate_survey({"clarity": 6, "ease_of_use": None, "confidence": 2})
    assert record["event"] == "survey_rating"
    assert record["payload"] == {
        "scale": "likert7",
        "clarity": 6,
        "ease_of_use": None,
        "confidence": 2,
    }


@pytest.mark.parametrize(
    "ratings",
    [
        {"clarity": 8, "ease_of_use": 1, "confidence": 1},
        {"clarity": 0, "ease_of_use": 1, "confidence": 1},
        {"clarity": 1, "ease_of_use": 1},
        {"clarity": 1, "ease_of_use": 1, "confidence": 1, "fun": 3},
    ],
)
def test_the_survey_rejects_off_scale_or_misnamed_items(logger, ratings):
    with pytest.raises(LogError):
        logger.rate_survey(ratings)


def test_demographics_must_name_exactly_the_documented_items(logger):
    answers = dict.fromkeys(EVENTS["demographics"])
    assert logger.record_demographics(answers)["payload"] == answers
    with pytest.raises(LogError):
        logger.record_demographics({"age_range": "18–24"})


def test_a_skipped_answer_is_null_and_named_in_skipped(logger):
    """A blank is recorded as absent, and the record says which part was skipped."""
    logger.start_task("T2")
    record = logger.submit_answer("T2", answer="", justification="   ")
    assert record["payload"]["answer"] is None
    assert record["payload"]["justification"] is None
    assert record["payload"]["skipped"] == ["answer", "justification"]
    logger.end_task()
    logger.start_task("T3")
    answered = logger.submit_answer("T3", answer="Brazil", justification=" steepest ")
    assert answered["payload"]["justification"] == "steepest"
    assert answered["payload"]["skipped"] == []


def test_answer_carries_its_justification(logger):
    """The justification is the raw material for the reasoning-depth coding."""
    logger.start_task("T3")
    record = logger.submit_answer(
        "T3", answer="Brazil", justification="It dropped furthest after 2015.", duration_ms=5000.0
    )
    assert record["payload"]["justification"] == "It dropped furthest after 2015."
    assert record["payload"]["answer"] == "Brazil"


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


# --- v4 record additions ----------------------------------------------------------------------


def test_event_uid_is_unique_per_record(logger):
    """Replay is idempotent only because each record carries its own, fixed uid."""
    logger.event("line_isolate", entity="Ukraine", isolated=True)
    logger.event("line_isolate", entity="Ukraine", isolated=False)
    uids = [r["event_uid"] for r in read_log(logger._sink.path)]
    assert len(uids) == len(set(uids)) == 3


def test_consent_is_recorded_with_the_browser_timestamp(logger):
    record = logger.record_consent("2026-09-16T10:00:00.000Z", "abc123")
    assert record["event"] == "consent"
    assert record["payload"] == {
        "consented_at": "2026-09-16T10:00:00.000Z",
        "consent_version": "abc123",
        "signature_method": None,
    }


def test_consent_records_the_method_and_never_the_signature(logger):
    """The name and signature live in the separate consent record (IRB form items 15 and 17)."""
    record = logger.record_consent("2026-09-16T10:00:00.000Z", "abc123", "drawn")
    assert record["payload"]["signature_method"] == "drawn"
    assert set(record["payload"]) == {"consented_at", "consent_version", "signature_method"}


def test_consent_without_a_timestamp_is_refused(logger):
    with pytest.raises(LogError, match="consented_at"):
        logger.record_consent("", "abc123")


def test_an_invalid_duration_is_recorded_absent_with_its_reason(logger):
    logger.start_task("T1")
    answer = logger.submit_answer("T1", "1", duration_ms=None, duration_invalid="clock_reset")
    end = logger.end_task(duration_ms=None, duration_invalid="clock_reset")
    for record in (answer, end):
        assert record["payload"]["duration_ms"] is None
        assert record["payload"]["duration_invalid"] == "clock_reset"


def test_new_events_are_documented():
    assert EVENTS["consent"] == ("consented_at", "consent_version", "signature_method")
    assert EVENTS["sink_recovered"] == ("spooled", "dropped")
    assert "duration_invalid" in EVENTS["answer_submit"]
    assert "duration_invalid" in EVENTS["task_end"]


# --- ResilientSink ----------------------------------------------------------------------------
#
# The deployed sink. A database failure here must never surface as an exception to the app -- that
# is what used to leave a participant pressing a Submit button that did nothing -- and it must never
# quietly lose an event either.

TRANSIENT = study_logging.db.TransientDatabaseError
PERMANENT = study_logging.db.DatabaseError


class FakeDatabase:
    """A sink whose failures are scripted: each call pops the next outcome, None meaning success."""

    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.written: list[dict] = []
        self.replayed: list[dict] = []
        self.calls = 0

    def _next(self):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome("scripted failure")

    def write(self, record):
        self._next()
        self.written.append(record)

    def replay(self, record):
        self._next()
        self.replayed.append(record)

    def close(self):
        pass


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _record(event="line_isolate", n=0):
    return {
        "schema_version": SCHEMA_VERSION,
        "event_uid": f"uid-{event}-{n}",
        "session_id": "11111111-1111-1111-1111-111111111111",
        "participant_id": "P07",
        "condition": "interactive",
        "condition_order": 1,
        "form": "A",
        "task_id": "T1",
        "event": event,
        "payload": {},
    }


def _sink(database, tmp_path=None, clock=None, **kwargs):
    clock = clock or FakeClock()
    kwargs.setdefault("breaker", study_logging.CircuitBreaker(clock=clock))
    return ResilientSink(
        database,
        spool_path=(tmp_path / "s.spool.jsonl") if tmp_path else None,
        sleep=clock.sleep,
        clock=clock,
        **kwargs,
    )


def _uids(records):
    return [r["event_uid"] for r in records]


def test_resilient_sink_retries_a_transient_failure_then_succeeds():
    database = FakeDatabase([TRANSIENT, TRANSIENT])
    sink = _sink(database)
    sink.write(_record())
    assert database.calls == 3
    assert len(database.written) == 1
    assert sink.pending == []


def test_resilient_sink_backoff_increases_and_is_capped():
    clock = FakeClock()
    policy = study_logging.RetryPolicy(attempts=6, base_delay_s=0.5, max_delay_s=1.0, budget_s=100)
    sink = _sink(FakeDatabase([TRANSIENT] * 5), clock=clock, policy=policy)
    sink.write(_record())
    assert clock.sleeps == [0.5, 1.0, 1.0, 1.0, 1.0]


def test_resilient_sink_respects_the_wall_clock_budget():
    """The budget, not the attempt count, is what keeps a retry inside Vercel's maxDuration."""
    clock = FakeClock()
    policy = study_logging.RetryPolicy(attempts=100, base_delay_s=2.0, max_delay_s=2.0, budget_s=5)
    sink = _sink(FakeDatabase([TRANSIENT] * 100), clock=clock, policy=policy)
    sink.write(_record())
    assert clock.now <= 5
    assert len(sink.pending) == 1


def test_resilient_sink_spools_after_exhausting_retries_and_does_not_raise(tmp_path):
    """The headline guarantee: a dead database costs the event its trip, never the session."""
    record = _record()
    sink = _sink(FakeDatabase([TRANSIENT] * 10), tmp_path)
    sink.write(record)

    assert sink.pending == [record], "the browser copy is the one that survives on Vercel"
    envelopes = read_log(tmp_path / "s.spool.jsonl")
    assert len(envelopes) == 1
    assert envelopes[0]["record"] == record, "spooled in an envelope, never as a bare record"
    assert "scripted failure" in envelopes[0]["error"]
    assert envelopes[0]["spooled_at"]


def test_resilient_sink_does_not_retry_a_non_transient_error():
    """Retrying a constraint violation only spends the retry budget before the same failure."""
    clock = FakeClock()
    database = FakeDatabase([PERMANENT])
    sink = _sink(database, clock=clock)
    sink.write(_record())
    assert database.calls == 1
    assert clock.sleeps == []
    assert len(sink.pending) == 1


def test_immediate_spool_policy_never_sleeps():
    """Interaction events are logged inside the measured task window, in the interactive condition
    only. A retry sleep there would inflate time-on-task in one condition: a manufactured result."""
    clock = FakeClock()
    database = FakeDatabase([TRANSIENT] * 10)
    sink = _sink(database, clock=clock, policy=study_logging.NO_RETRY)
    sink.write(_record())
    assert clock.sleeps == []
    assert database.calls == 1


def test_circuit_breaker_skips_the_database_during_cooldown():
    clock = FakeClock()
    breaker = study_logging.CircuitBreaker(cooldown_s=20, clock=clock)
    database = FakeDatabase([TRANSIENT] * 10)

    first = _sink(database, clock=clock, breaker=breaker, policy=study_logging.NO_RETRY)
    first.write(_record())
    assert database.calls == 1

    # The next callback builds a fresh sink; the breaker is the only thing it shares.
    second = _sink(
        database, clock=clock, breaker=breaker, policy=study_logging.NO_RETRY, pending=first.pending
    )
    second.write(_record(n=1))
    assert database.calls == 1, "during cooldown the database must not be touched at all"

    clock.now += 21
    database.outcomes = []
    third = _sink(database, clock=clock, breaker=breaker, pending=second.pending)
    third.write(_record(n=2))
    assert database.calls > 1, "after cooldown the database is tried again"
    assert third.pending == []


def test_pending_events_replay_in_order_before_new_ones():
    database = FakeDatabase()
    sink = _sink(database, pending=[_record(n=0), _record(n=1)])
    sink.write(_record(n=2))

    assert _uids(database.replayed) == ["uid-line_isolate-0", "uid-line_isolate-1"]
    assert database.written[-1]["event_uid"] == "uid-line_isolate-2"
    assert sink.pending == []


def test_sink_recovered_is_written_once_the_backlog_clears():
    database = FakeDatabase()
    _sink(database, pending=[_record(n=0), _record(n=1)]).write(_record(n=2))

    markers = [r for r in database.written if r["event"] == "sink_recovered"]
    assert len(markers) == 1
    assert markers[0]["payload"] == {"spooled": 2, "dropped": 0}


def test_sink_recovered_is_attributed_to_the_backlogs_own_session():
    """A warm container serves many participants. The marker must name the participant whose events
    were spooled, never whoever happens to be the current request's subject."""
    backlog = [_record(n=0)]
    database = FakeDatabase()
    someone_else = {**_record(n=9), "participant_id": "P99", "session_id": "other"}
    _sink(database, pending=backlog).write(someone_else)

    marker = next(r for r in database.written if r["event"] == "sink_recovered")
    assert marker["participant_id"] == "P07"
    assert marker["session_id"] == backlog[0]["session_id"]
    assert marker["event_uid"] and marker["event_uid"] != backlog[0]["event_uid"]


def test_no_recovery_marker_without_a_backlog():
    database = FakeDatabase()
    _sink(database).write(_record())
    assert [r["event"] for r in database.written] == ["line_isolate"]


def test_a_failed_replay_keeps_the_backlog_and_spools_the_new_event():
    database = FakeDatabase([TRANSIENT] * 10)
    sink = _sink(database, pending=[_record(n=0)], policy=study_logging.NO_RETRY)
    sink.write(_record(n=1))
    assert _uids(sink.pending) == ["uid-line_isolate-0", "uid-line_isolate-1"]
    assert database.written == []


def test_the_browser_spool_is_bounded_and_counts_what_it_drops(monkeypatch):
    monkeypatch.setattr(study_logging, "MAX_PENDING", 3)
    sink = _sink(FakeDatabase([PERMANENT] * 10))
    for n in range(5):
        sink.write(_record(n=n))
    assert _uids(sink.pending) == [f"uid-line_isolate-{n}" for n in (2, 3, 4)]
    assert sink.dropped == 2
    assert sink.degraded


def test_dropped_events_are_reported_in_the_recovery_marker():
    database = FakeDatabase()
    _sink(database, pending=[_record(n=0)], dropped=4).write(_record(n=1))
    marker = next(r for r in database.written if r["event"] == "sink_recovered")
    assert marker["payload"] == {"spooled": 1, "dropped": 4}


def test_an_unwritable_spool_file_does_not_break_the_session(tmp_path):
    """Vercel's filesystem is read-only outside /tmp. Failing to write the file copy is survivable
    because the browser copy is still held."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    clock = FakeClock()
    sink = ResilientSink(
        FakeDatabase([PERMANENT]),
        spool_path=blocker / "s.spool.jsonl",
        breaker=study_logging.CircuitBreaker(clock=clock),
        sleep=clock.sleep,
        clock=clock,
    )
    sink.write(_record())
    assert len(sink.pending) == 1


def test_spool_files_round_trip_through_read_spool(tmp_path):
    for n in range(3):
        _sink(FakeDatabase([PERMANENT]), tmp_path).write(_record(n=n))
    envelopes = study_logging.read_spool(tmp_path)
    assert [e["record"]["event_uid"] for e in envelopes] == [
        f"uid-line_isolate-{n}" for n in range(3)
    ]


def test_postgres_replay_ignores_duplicates(monkeypatch):
    """A spooled event may already have landed before the response was lost."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    calls = []
    monkeypatch.setattr(study_logging.db, "insert_event", lambda record, **kw: calls.append(kw))
    sink = PostgresSink()
    sink.write(_record())
    sink.replay(_record())
    assert calls == [{}, {"ignore_duplicates": True}]


def test_the_default_postgres_sink_spools_to_the_configured_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    monkeypatch.setenv("STUDY_SPOOL_DIR", str(tmp_path))
    monkeypatch.setattr(study_logging.db, "insert_event", lambda record, **kw: None)
    log = StudyLogger("P07", condition_order=1, interactive=True)
    assert log.resilient
    assert log._sink.spool_path.parent == tmp_path
    assert log.pending == []


def test_the_file_sink_has_no_spool_to_carry(logger):
    assert not logger.resilient
    assert logger.pending == []
    assert logger.dropped == 0
