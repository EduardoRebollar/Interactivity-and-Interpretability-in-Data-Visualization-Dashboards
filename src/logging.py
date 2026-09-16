"""Event and timing logger. This module produces the study's primary data.

**Schema v2 (2026-09-15).** Deployment forced three changes from v1:

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

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from src import config, db

# Bump on any breaking change to the record shape. Analysis must refuse to mix versions.
SCHEMA_VERSION = 2

# event name -> documented payload keys. Guards against a typo silently inventing an event type
# that analysis would then miss.
EVENTS: dict[str, tuple[str, ...]] = {
    # Session lifecycle
    "session_start": ("interactive", "entities", "vaccines", "year_range"),
    "session_end": ("reason",),
    # Condition lifecycle (a participant does both, in counterbalanced order)
    "condition_start": ("interactive", "condition_order"),
    "condition_end": ("interactive", "condition_order"),
    # Task lifecycle
    "task_start": (),
    "task_end": ("duration_ms",),
    # task_id lives in the record column, not the payload, like every other event.
    "answer_submit": ("answer", "duration_ms"),
    # Interactive-only affordances
    "filter_change": ("control", "action", "value", "previous"),
    "line_isolate": ("entity", "isolated"),
    "sort_change": ("key", "direction"),
    # Present in both conditions
    "view_change": ("control", "value", "previous"),
}

CONDITIONS = ("static", "interactive")


class LogError(RuntimeError):
    """Raised on invalid logger construction or an unknown event name."""


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

    def close(self) -> None:
        """No-op: connections are per-operation, so there is nothing to hold open."""


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
        sink: Sink | None = None,
        log_dir: Path | None = None,
    ) -> None:
        if not participant_id or not participant_id.strip():
            raise LogError("participant_id must be a non-empty string")
        if condition_order not in (1, 2):
            raise LogError(f"condition_order must be 1 or 2, got {condition_order!r}")

        self.participant_id = participant_id.strip()
        self.condition_order = condition_order
        self.interactive = interactive
        self.condition = "interactive" if interactive else "static"
        self.session_id = str(uuid.uuid4())

        self._origin = time.perf_counter()
        self._task_id: str | None = None
        self._closed = False
        self._sink = sink if sink is not None else self._default_sink(log_dir)

        self.event(
            "session_start",
            interactive=self.interactive,
            entities=config.ENTITIES,
            vaccines=list(config.VACCINES),
            year_range=[config.YEAR_MIN, config.YEAR_MAX],
        )

    def _default_sink(self, log_dir: Path | None) -> Sink:
        """Postgres when configured, otherwise a per-session JSONL file."""
        if db.configured():
            return PostgresSink()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        directory = log_dir or config.STUDY_LOGS_DIR
        return JsonlSink(directory / f"{self.participant_id}_{self.condition}_{stamp}.jsonl")

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
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "condition": self.condition,
            "condition_order": self.condition_order,
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
        client_elapsed_ms: float | None = None,
    ) -> dict[str, Any]:
        """Close the open task. `duration_ms` is the browser-measured time on task."""
        if self._task_id is None:
            raise LogError("No task is open")
        if task_id is not None and task_id != self._task_id:
            raise LogError(f"Open task is {self._task_id!r}, not {task_id!r}")

        record = self.event(
            "task_end",
            duration_ms=duration_ms,
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
        duration_ms: float | None = None,
        client_elapsed_ms: float | None = None,
    ) -> dict[str, Any]:
        """Record a participant's answer. Accuracy is scored later, not here."""
        return self.event(
            "answer_submit",
            task_id=task_id,
            answer=answer,
            duration_ms=duration_ms,
            client_elapsed_ms=client_elapsed_ms,
        )

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
