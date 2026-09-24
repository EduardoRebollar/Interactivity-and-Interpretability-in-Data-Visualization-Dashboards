"""Event and timing logger. This module produces the study's primary data.

**Schema v4 (2026-09-15).** Pre-pilot hardening:

- `event_uid` on every record, generated once when the record is built, so a spooled event replays
  without double-inserting.
- `consent` -- the timestamped consent record `docs/study-design.md` section 9 promises.
- `sink_recovered` -- written when events that could not reach the database are finally flushed,
  so the outage is visible in the data rather than only in its gaps.
- `duration_invalid` on `answer_submit` and `task_end` -- a reload resets the browser clock, and
  the duration it would produce is plausible and wrong. It is recorded absent, with the reason.

**A database failure never breaks a session.** `ResilientSink` retries connection-level failures
within a wall-clock budget, then spools: into a `pending` list the app keeps in browser session
storage and replays on the next callback, and into a JSONL file under `config.spool_dir()`. The
browser copy is the one that matters on Vercel, where `/tmp` is per-instance and cannot be read back
out of a running function -- the file copy is only genuinely recoverable on a local or self-hosted
run. Be accurate about this in any write-up: the session continues and the loss is recorded; it is
not true that no data can be lost.

**Schema v3 (2026-09-15).** Parallel forms added the `form` column, the `load_rating` event (Paas
mental effort, the RQ3 measure) and `justification` on `answer_submit` (the RQ2 material). Additive,
and nothing had been collected, so there was no migration — but the record shape changed.

v2 before it, where deployment forced three changes from v1:

1. **Timings come from the browser.** Each event is its own HTTP request, so a server clock would
   fold network latency and 800 ms-2.5 s cold starts into task duration — and task duration is a
   dependent variable. The browser measures with `performance.now()` and sends the number.
   `server_elapsed_ms` is still recorded, but only as a cross-check for a missing or implausible
   client value. It is NOT the measurement.
2. **The sink is swappable.** Postgres when `DATABASE_URL` is set, JSONL otherwise. Vercel's
   filesystem is ephemeral and read-only outside `/tmp`, so a deployed session cannot use files.
3. **Answers are captured** (`answer_submit`), because the deployed page runs the whole session.

`condition_order` is what makes the within-subjects design analysable: without it a practice effect
is indistinguishable from an effect of interactivity.

BOTH conditions are logged. Zero interaction events under static is itself a finding, and task
timings only compare if they are collected identically on both sides.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from src import config, db

# Bump on any breaking change to the record shape. Analysis must refuse to mix versions.
#
# v7 (2026-09-23): the task bank was replaced (docs/study-design.md section 4). Task ids T1-T6 now
# name different items on five chart types, so a v6 answer scored against a v7 key would be scored
# against the wrong question -- the version is what stops that. `filter_change` also comes from the
# map's coverage range (`control` "coverage-band" or "band-reset"), whose `value` and `previous`
# are a [low, high] range rather than a list of entities; `sort_change` also comes from the bar
# chart's sort. No new event and no new key. Nothing has been collected, so no migration.
# T7, a crossing item, was added the same day, still before any collection: T1-T6 kept their
# meaning, so no v7 record can be scored against the wrong question, and the version stayed.
#
# v6 (2026-09-21): brought in line with the IRB submission. Any question may be skipped, so
# `answer_submit.answer`, `justification` and `load_rating.value` may be null, and `answer_submit`
# carries `skipped`, the parts left empty. New events `survey_rating` (the three Likert items) and
# `demographics`. `consent` gains `signature_method`. The signature and name never enter this log;
# they go to the separate consent record (src/consent.py).
#
# v5 (2026-09-16): the record shape is unchanged, but what Postgres stores in `server_ts` is not.
# It is now the record's own creation time; under v4 it was the INSERT time, so an event spooled
# through an outage carried its replay time. See `db.insert_event`.
#
# v4 (2026-09-15): event_uid, the consent and sink_recovered events, duration_invalid. See the
# module docstring.
#
# v3 (2026-09-15): parallel forms. Adds the `form` column, the `load_rating` event (Paas mental
# effort, for RQ3), and `justification` on answers (the material for RQ2). Additive, and nothing has
# been collected, so no migration — but the record shape changed, so the version moves.
SCHEMA_VERSION = 7

# event name -> documented payload keys. Guards against a typo silently inventing an event type
# that analysis would then miss.
EVENTS: dict[str, tuple[str, ...]] = {
    # Consent. Emitted once per participant, when condition 1's logger opens -- the logger cannot
    # exist earlier, because a record needs a participant ID and a condition. So `server_ts` is the
    # instructions-screen time; the true consent time is `consented_at`, from the browser clock.
    # `consent_version` is a hash of the wording shown, so a mid-study text change is detectable.
    # `signature_method` is "drawn" or "paper". The signature and the printed name are NOT here:
    # they go to the consent record, which is kept apart from study data (IRB form items 15, 17).
    "consent": ("consented_at", "consent_version", "signature_method"),
    # Once per participant, right after `consent`. Any value may be null (skipped).
    "demographics": ("age_range", "field", "chart_frequency", "dashboard_familiarity"),
    # Session lifecycle
    "session_start": ("interactive", "entities", "vaccines", "year_range"),
    "session_end": ("reason",),
    # Condition lifecycle (a participant does both, in counterbalanced order)
    "condition_start": ("interactive", "condition_order"),
    "condition_end": ("interactive", "condition_order"),
    # Task lifecycle
    "task_start": (),
    # duration_invalid is None when duration_ms is trustworthy, else why it is absent:
    # "missing", "clock_reset" (a reload restarted the browser clock) or "negative".
    "task_end": ("duration_ms", "duration_invalid"),
    # task_id lives in the record column, not the payload, like every other event.
    # `answer` and `justification` are null when skipped; `skipped` lists which ("answer",
    # "justification"), so a skip is explicit rather than inferred from a blank.
    "answer_submit": ("answer", "justification", "skipped", "duration_ms", "duration_invalid"),
    # Paas single-item mental effort, once per condition. The RQ3 measure. `value` null if skipped.
    "load_rating": ("scale", "value"),
    # The three 7-point Likert items, once per condition, alongside load_rating. Null if skipped.
    "survey_rating": ("scale", "clarity", "ease_of_use", "confidence"),
    # Interactive-only affordances. On the map, `filter_change.value` is a [low, high] coverage
    # range, not a list of entities; `control` says which (see v7 above).
    "filter_change": ("control", "action", "value", "previous"),
    "line_isolate": ("entity", "isolated"),
    "sort_change": ("key", "direction"),
    # Present in both conditions
    "view_change": ("control", "value", "previous"),
    # Written by ResilientSink, not by a caller: `spooled` events that could not reach the database
    # were flushed once it came back, and `dropped` overflowed the bounded browser spool.
    "sink_recovered": ("spooled", "dropped"),
}

CONDITIONS = ("static", "interactive")
FORMS = ("A", "B")


class LogError(RuntimeError):
    """Raised on invalid logger construction or an unknown event name."""


def _check_scale(label: str, value: Any, top: int) -> None:
    """A rating is None (skipped) or an integer 1..top. bool is refused: it is an int subclass."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= top:
        raise LogError(f"{label} must be an integer 1-{top} or None, got {value!r}")


class Sink(Protocol):
    """Somewhere a record can be durably written."""

    def write(self, record: dict[str, Any]) -> None: ...

    def close(self) -> None: ...


class JsonlSink:
    """Append-and-flush JSONL, one file per session. The local path.

    Flushes per record and tolerates a truncated final line on read, so a crash mid-session costs at
    most the event in flight.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._handle = path.open("a", encoding="utf-8")

    def write(self, record: dict[str, Any]) -> None:
        self._handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    @property
    def closed(self) -> bool:
        return self._handle.closed


class PostgresSink:
    """Neon Postgres. The deployed path."""

    def __init__(self) -> None:
        if not db.configured():
            raise LogError("PostgresSink requires DATABASE_URL")

    def write(self, record: dict[str, Any]) -> None:
        db.insert_event(record)

    def replay(self, record: dict[str, Any]) -> None:
        """Write a spooled record. A conflict means it already landed, so it is not an error."""
        db.insert_event(record, ignore_duplicates=True)

    def close(self) -> None:
        """No-op: connections are per-operation, so there is nothing to hold open."""


# --- Resilience --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How hard to try before spooling. `budget_s` is wall-clock, and is the primary limit."""

    attempts: int
    base_delay_s: float
    max_delay_s: float
    budget_s: float


# For callbacks outside the measured window. The Submit timestamp is taken in the browser before the
# request leaves, so retry latency on that path lands after the duration is already fixed.
FULL = RetryPolicy(attempts=3, base_delay_s=0.25, max_delay_s=2.0, budget_s=8.0)

# For interaction events. These are logged inside a task's measured window and only in the
# interactive condition, so retrying them would inflate a dependent variable in one condition only.
NO_RETRY = RetryPolicy(attempts=1, base_delay_s=0.0, max_delay_s=0.0, budget_s=0.0)

# The browser spool lives in sessionStorage. Bounded so an outage cannot grow the store without
# limit; overflow drops the oldest and is counted in `sink_recovered.dropped`.
MAX_PENDING = 200


def call_with_retry(
    operation: Callable[[], Any],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None] | None = None,
    clock: Callable[[], float] | None = None,
) -> Any:
    """Run `operation`, retrying `TransientDatabaseError` with capped exponential backoff.

    Stops at `policy.attempts` or when `policy.budget_s` of wall clock is spent, whichever is first,
    and re-raises the last error. Any other error is raised at once: retrying a constraint violation
    only delays the same failure.

    `sleep` and `clock` default to `time.sleep` and `time.monotonic`, looked up at call time so
    tests can replace them.
    """
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    started = clock()
    attempt = 0
    while True:
        attempt += 1
        try:
            return operation()
        except db.TransientDatabaseError:
            elapsed = clock() - started
            if attempt >= policy.attempts or elapsed >= policy.budget_s:
                raise
            delay = min(policy.base_delay_s * 2 ** (attempt - 1), policy.max_delay_s)
            sleep(min(delay, policy.budget_s - elapsed))


class CircuitBreaker:
    """Skip the database for `cooldown_s` after a failure.

    Module-level on purpose: a sink is rebuilt on every callback, but a warm serverless container
    serves the participant's next click too. Once the database has just failed, the next interaction
    event goes straight to the spool instead of spending another connect timeout inside the task
    window. It holds only a timestamp, never participant data, so sharing it is safe.
    """

    def __init__(self, cooldown_s: float = 20.0, clock: Callable[[], float] | None = None):
        self.cooldown_s = cooldown_s
        self._clock = clock or (lambda: time.monotonic())
        self._failed_at: float | None = None

    @property
    def open(self) -> bool:
        return self._failed_at is not None and self._clock() - self._failed_at < self.cooldown_s

    def trip(self) -> None:
        self._failed_at = self._clock()

    def reset(self) -> None:
        self._failed_at = None


BREAKER = CircuitBreaker()


class ResilientSink:
    """Retry transient failures, then spool. `write` never raises a DatabaseError.

    On every write, anything pending from earlier callbacks is replayed first, so events reach the
    database in the order they happened. A backlog that clears is followed by one `sink_recovered`
    record, so the outage appears in the data.

    `pending` belongs to one browser session, and so to one participant -- which is why the recovery
    marker takes its identity from the backlog and never from shared module state.
    """

    def __init__(
        self,
        inner: Sink,
        *,
        pending: list[dict[str, Any]] | None = None,
        dropped: int = 0,
        spool_path: Path | None = None,
        policy: RetryPolicy = FULL,
        breaker: CircuitBreaker | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.inner = inner
        self.pending: list[dict[str, Any]] = list(pending or [])
        self.dropped = dropped
        self.spool_path = spool_path
        self.policy = policy
        self.breaker = breaker if breaker is not None else BREAKER
        self._sleep = sleep
        self._clock = clock

    @property
    def degraded(self) -> bool:
        return bool(self.pending) or self.dropped > 0

    def write(self, record: dict[str, Any]) -> None:
        if (self.pending or self.dropped) and not self._flush(record):
            self._spool(record, "database unavailable; earlier events still pending")
            return
        try:
            self._attempt(self.inner.write, record)
        except db.DatabaseError as exc:
            self._spool(record, str(exc))

    def close(self) -> None:
        # Last chance to flush before the caller discards this sink. On failure the backlog stays in
        # `pending`, which the caller still holds.
        if self.pending:
            self._flush(self.pending[-1])
        self.inner.close()

    def _attempt(self, operation: Callable[[dict[str, Any]], None], record: dict[str, Any]) -> None:
        """Run `operation`, retrying transient failures within the policy. Raises on exhaustion."""
        if self.breaker.open:
            raise db.TransientDatabaseError("circuit open: the database failed moments ago")
        try:
            call_with_retry(
                lambda: operation(record), self.policy, sleep=self._sleep, clock=self._clock
            )
        except db.TransientDatabaseError:
            self.breaker.trip()
            raise
        self.breaker.reset()

    def _flush(self, identity: dict[str, Any]) -> bool:
        """Replay pending records in order. True when the backlog is fully cleared."""
        replay = getattr(self.inner, "replay", self.inner.write)
        template = self.pending[0] if self.pending else identity
        flushed = 0
        while self.pending:
            try:
                self._attempt(replay, self.pending[0])
            except db.DatabaseError:
                return False
            self.pending.pop(0)
            flushed += 1
        # The events made it; if only the marker fails, it is not worth re-spooling a marker.
        with contextlib.suppress(db.DatabaseError):
            self._attempt(self.inner.write, recovery_record(template, flushed, self.dropped))
        self.dropped = 0
        return True

    def _spool(self, record: dict[str, Any], reason: str) -> None:
        print(f"[study-log] spooling {record.get('event')}: {reason}", file=sys.stderr)
        self.pending.append(record)
        if len(self.pending) > MAX_PENDING:
            overflow = len(self.pending) - MAX_PENDING
            del self.pending[:overflow]
            self.dropped += overflow
        if self.spool_path is None:
            return
        envelope = {"record": record, "spooled_at": datetime.now(UTC).isoformat(), "error": reason}
        try:
            self.spool_path.parent.mkdir(parents=True, exist_ok=True)
            with self.spool_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(envelope, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            # The browser copy is still held; a read-only filesystem must not break the session.
            print(f"[study-log] spool file unavailable: {exc}", file=sys.stderr)


IDENTITY_KEYS = (
    "schema_version",
    "session_id",
    "participant_id",
    "condition",
    "condition_order",
    "form",
)


def recovery_record(template: dict[str, Any], spooled: int, dropped: int) -> dict[str, Any]:
    """The `sink_recovered` marker, attributed to the session the backlog came from."""
    return {
        **{key: template.get(key) for key in IDENTITY_KEYS},
        "event_uid": str(uuid.uuid4()),
        "task_id": None,
        "event": "sink_recovered",
        "server_ts": datetime.now(UTC).isoformat(),
        "client_elapsed_ms": None,
        "task_elapsed_ms": None,
        "server_elapsed_ms": None,
        "payload": {"spooled": spooled, "dropped": dropped},
    }


def spool_file(participant_id: str, condition: str, session_id: str) -> Path:
    """Where a session's spooled events are also written, besides the browser store.

    The pid disambiguates two containers serving one session.
    """
    short = session_id.replace("-", "")[:12]
    return config.spool_dir() / f"{participant_id}_{condition}_{short}_{os.getpid()}.spool.jsonl"


def read_spool(directory: Path | None = None) -> list[dict[str, Any]]:
    """Every spooled envelope under `directory`, oldest first. For scripts/recover_spool.py.

    Exact within a session: each session spools to its own file and the sort is stable. Across
    sessions, records stamped in the same clock tick (Windows timestamps are ~1 ms coarse) fall back
    to file-name order. Harmless: analysis groups by session, never by insert order across them.
    """
    directory = directory or config.spool_dir()
    envelopes: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.spool.jsonl")):
        envelopes.extend(read_log(path))
    return sorted(envelopes, key=lambda envelope: envelope.get("spooled_at") or "")


class StudyLogger:
    """Records one participant's session in one condition.

    Timings are supplied by the caller from the browser clock. Passing none is allowed — the record
    then carries only `server_elapsed_ms`, and analysis can see the client value is absent rather
    than being handed a silently wrong number.
    """

    def __init__(
        self,
        participant_id: str,
        condition_order: int,
        *,
        interactive: bool,
        form: str | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
        sink: Sink | None = None,
        log_dir: Path | None = None,
        policy: RetryPolicy = FULL,
        pending: list[dict[str, Any]] | None = None,
        dropped: int = 0,
    ) -> None:
        if not participant_id or not participant_id.strip():
            raise LogError("participant_id must be a non-empty string")
        if condition_order not in (1, 2):
            raise LogError(f"condition_order must be 1 or 2, got {condition_order!r}")
        if form is not None and form not in FORMS:
            raise LogError(f"form must be one of {FORMS}, got {form!r}")

        self.participant_id = participant_id.strip()
        self.condition_order = condition_order
        self.interactive = interactive
        self.form = form
        self.condition = "interactive" if interactive else "static"

        # Resuming: on a serverless host every callback is a separate request, so a logger cannot
        # be held in memory between events. The caller keeps `session_id` (and any open task) in
        # browser session state and hands them back, so one sitting stays one session_id rather
        # than fragmenting into dozens, each with a spurious session_start.
        self._resumed = session_id is not None
        self.session_id = session_id or str(uuid.uuid4())

        self._origin = time.perf_counter()
        self._task_id = task_id
        self._closed = False
        self._sink = (
            sink if sink is not None else self._default_sink(log_dir, policy, pending, dropped)
        )

        if not self._resumed:
            self.event(
                "session_start",
                interactive=self.interactive,
                entities=config.ENTITIES,
                vaccines=list(config.VACCINES),
                year_range=[config.YEAR_MIN, config.YEAR_MAX],
            )

    def _default_sink(
        self,
        log_dir: Path | None,
        policy: RetryPolicy,
        pending: list[dict[str, Any]] | None,
        dropped: int,
    ) -> Sink:
        """Postgres (made resilient) when configured, otherwise a per-session JSONL file.

        The filename is keyed on `session_id`, not a timestamp, so a resumed logger appends to the
        same file instead of scattering one sitting across a file per callback.
        """
        if db.configured():
            return ResilientSink(
                PostgresSink(),
                pending=pending,
                dropped=dropped,
                spool_path=spool_file(self.participant_id, self.condition, self.session_id),
                policy=policy,
            )
        if os.environ.get("VERCEL") and log_dir is None:
            # Vercel's filesystem is read-only outside /tmp, and /tmp is per-instance and lost. A
            # JSONL file there would either crash the request or silently discard the study data, so
            # a deployment without DATABASE_URL is refused outright.
            raise LogError("DATABASE_URL is not set on this deployment; no event could be saved")
        directory = log_dir or config.STUDY_LOGS_DIR
        short = self.session_id.replace("-", "")[:12]
        return JsonlSink(directory / f"{self.participant_id}_{self.condition}_{short}.jsonl")

    # --- Core ---------------------------------------------------------------------------------

    def event(
        self,
        name: str,
        *,
        task_id: str | None = None,
        client_elapsed_ms: float | None = None,
        task_elapsed_ms: float | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        """Write one event record. Returns it, mainly so callers and tests can assert on it."""
        if name not in EVENTS:
            raise LogError(f"Unknown event {name!r}; known events: {sorted(EVENTS)}")
        if self._closed:
            raise LogError("Logger is closed")

        record = {
            "schema_version": SCHEMA_VERSION,
            # Generated here, once. A retry or a replay of this record carries the same uid, which
            # is what makes replay idempotent.
            "event_uid": str(uuid.uuid4()),
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "condition": self.condition,
            "condition_order": self.condition_order,
            "form": self.form,
            "task_id": task_id if task_id is not None else self._task_id,
            "event": name,
            "server_ts": datetime.now(UTC).isoformat(),
            "client_elapsed_ms": client_elapsed_ms,
            "task_elapsed_ms": task_elapsed_ms,
            # Cross-check only. Includes network and cold-start time; never the measurement.
            "server_elapsed_ms": round((time.perf_counter() - self._origin) * 1000, 3),
            "payload": payload,
        }
        self._sink.write(record)
        return record

    # --- Task lifecycle -----------------------------------------------------------------------

    def start_task(self, task_id: str, *, client_elapsed_ms: float | None = None) -> dict[str, Any]:
        if self._task_id is not None:
            raise LogError(
                f"Task {self._task_id!r} is still open; end it before starting {task_id!r}"
            )
        self._task_id = task_id
        return self.event("task_start", client_elapsed_ms=client_elapsed_ms)

    def end_task(
        self,
        task_id: str | None = None,
        *,
        duration_ms: float | None = None,
        duration_invalid: str | None = None,
        client_elapsed_ms: float | None = None,
    ) -> dict[str, Any]:
        """Close the open task. `duration_ms` is the browser-measured time on task.

        `duration_invalid` says why `duration_ms` is absent when it is, so an unusable duration is
        visibly absent in the data rather than silently wrong.
        """
        if self._task_id is None:
            raise LogError("No task is open")
        if task_id is not None and task_id != self._task_id:
            raise LogError(f"Open task is {self._task_id!r}, not {task_id!r}")

        record = self.event(
            "task_end",
            duration_ms=duration_ms,
            duration_invalid=duration_invalid,
            client_elapsed_ms=client_elapsed_ms,
            task_elapsed_ms=duration_ms,
        )
        self._task_id = None
        return record

    def submit_answer(
        self,
        task_id: str,
        answer: Any,
        *,
        justification: str | None = None,
        duration_ms: float | None = None,
        duration_invalid: str | None = None,
        client_elapsed_ms: float | None = None,
    ) -> dict[str, Any]:
        """Record a participant's answer and their reasoning.

        Accuracy is scored offline against the rubric in docs/study-design.md; no answer key exists
        in the running app, where a participant could read it out of the page source.

        Either part may be skipped (IRB form item 10). A blank is recorded as None, and `skipped`
        names what was left empty, so analysis never has to guess whether "" meant a skip.
        """
        if answer == "":
            answer = None
        justification = (justification or "").strip() or None
        skipped = [
            part
            for part, value in (("answer", answer), ("justification", justification))
            if value is None
        ]
        return self.event(
            "answer_submit",
            task_id=task_id,
            answer=answer,
            justification=justification,
            skipped=skipped,
            duration_ms=duration_ms,
            duration_invalid=duration_invalid,
            client_elapsed_ms=client_elapsed_ms,
        )

    def rate_load(
        self, value: int | None, *, client_elapsed_ms: float | None = None
    ) -> dict[str, Any]:
        """Record the Paas mental-effort rating for the condition just finished (RQ3).

        None is a skipped rating; anything else must be on the scale.
        """
        _check_scale("Paas rating", value, 9)
        return self.event(
            "load_rating", scale="paas", value=value, client_elapsed_ms=client_elapsed_ms
        )

    def rate_survey(self, ratings: dict[str, int | None]) -> dict[str, Any]:
        """Record the three 7-point Likert items for the condition just finished.

        Exactly the keys of `tasks.LIKERT_ITEMS`; each value 1-7, or None when skipped.
        """
        expected = set(EVENTS["survey_rating"]) - {"scale"}
        if set(ratings) != expected:
            raise LogError(f"Survey ratings must be {sorted(expected)}, got {sorted(ratings)}")
        for key, value in ratings.items():
            _check_scale(f"Likert rating {key!r}", value, 7)
        return self.event("survey_rating", scale="likert7", **ratings)

    def record_demographics(self, answers: dict[str, str | None]) -> dict[str, Any]:
        """Record the demographic answers. Call once, on condition 1's logger, after consent."""
        expected = set(EVENTS["demographics"])
        if set(answers) != expected:
            raise LogError(f"Demographics must be {sorted(expected)}, got {sorted(answers)}")
        return self.event("demographics", **answers)

    def record_consent(
        self, consented_at: str, consent_version: str, signature_method: str | None = None
    ) -> dict[str, Any]:
        """Record consent. Call once, on condition 1's logger, before anything else.

        `consented_at` is the browser's ISO timestamp from the moment "I agree" was pressed.
        """
        if not consented_at:
            raise LogError("consented_at is required; a consent record without a time is not one")
        return self.event(
            "consent",
            consented_at=consented_at,
            consent_version=consent_version,
            signature_method=signature_method,
        )

    # --- Spool state, for the caller to carry between requests --------------------------------

    @property
    def resilient(self) -> bool:
        """True when writes go through a ResilientSink, i.e. there is a spool to carry."""
        return isinstance(self._sink, ResilientSink)

    @property
    def pending(self) -> list[dict[str, Any]]:
        """Events not yet in the database. The caller stores these in browser session state."""
        return list(getattr(self._sink, "pending", []))

    @property
    def dropped(self) -> int:
        return int(getattr(self._sink, "dropped", 0))

    # --- Session lifecycle --------------------------------------------------------------------

    def close(self, reason: str = "normal") -> None:
        if self._closed:
            return
        if self._task_id is not None:
            # Record the abandonment rather than silently dropping an in-flight task.
            self.end_task()
            reason = "task_abandoned" if reason == "normal" else reason
        self.event("session_end", reason=reason)
        self._closed = True
        self._sink.close()

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> StudyLogger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close(reason="normal" if exc_type is None else f"error:{exc_type.__name__}")


# --- Reading (JSONL sink only; use db.fetch_events for Postgres) --------------------------------


def read_log(path: Path) -> list[dict[str, Any]]:
    """Read one JSONL session file, tolerating a truncated final line from a crashed session."""
    lines = path.read_text(encoding="utf-8").splitlines()
    records = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            # Only the last line can be legitimately truncated; anything earlier is corruption.
            if number != len(lines):
                raise
    return records


def read_all(log_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read every JSONL session file in `log_dir`."""
    directory = log_dir or config.STUDY_LOGS_DIR
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl")):
        records.extend(read_log(path))
    return records
