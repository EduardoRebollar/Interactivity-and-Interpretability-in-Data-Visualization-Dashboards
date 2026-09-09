"""Event and timing logger. This module produces the study's primary data.

Output is JSON Lines (one JSON object per line) under `data/study_logs/`, one file per session:

    {participant_id}_{condition}_{utc_timestamp}.jsonl

JSONL rather than CSV because event payloads differ by event type, and because an append-and-flush
line format survives a crash mid-session — a partially written file still parses up to the last
complete line, so a participant's session is never lost wholesale.

Every record carries these keys:

    schema_version   int    bump on ANY breaking change to this record shape
    session_id       str    uuid4, groups all records from one sitting
    participant_id   str    stable across BOTH of a participant's conditions
    condition        str    "static" | "interactive"
    condition_order  int    1 if this condition was seen first, 2 if second
    task_id          str    task this event belongs to, or null between tasks
    event            str    one of EVENTS
    timestamp        str    ISO-8601 UTC wall clock, for cross-referencing external records
    elapsed_ms       int    since session start, monotonic
    task_elapsed_ms  int    since current task start, monotonic; null outside a task
    payload          dict   event-specific fields, see EVENTS

`condition_order` is what makes the within-subjects design analysable: without it, a practice effect
is indistinguishable from an effect of interactivity.

Durations come from a monotonic clock, not the wall clock, so an NTP correction or a sleeping
laptop cannot produce a negative or wildly inflated task time.

BOTH conditions are logged. Zero interaction events in the static condition is itself a finding, and
task timings are only comparable if they are collected identically on both sides.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from src import config

# Bump on any breaking change to the record shape. Analysis code should refuse to mix versions.
SCHEMA_VERSION = 1

# event name -> expected payload keys. Documents the contract and guards against typos silently
# inventing a new event type that analysis would then miss.
EVENTS: dict[str, tuple[str, ...]] = {
    # Lifecycle
    "session_start": ("interactive", "entities", "vaccines", "year_range"),
    "session_end": ("reason",),
    "task_start": (),
    "task_end": ("duration_ms",),
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


class StudyLogger:
    """Append-only JSONL logger for one participant's session in one condition.

    Usage:
        with StudyLogger("P07", condition_order=1) as log:
            log.start_task("T1")
            log.event("filter_change", control="country", action="add",
                      value=["Nigeria"], previous=[])
            log.end_task("T1")
    """

    def __init__(
        self,
        participant_id: str,
        condition_order: int,
        *,
        interactive: bool | None = None,
        log_dir: Path | None = None,
    ) -> None:
        if not participant_id or not participant_id.strip():
            raise LogError("participant_id must be a non-empty string")
        if condition_order not in (1, 2):
            raise LogError(f"condition_order must be 1 or 2, got {condition_order!r}")

        self.participant_id = participant_id.strip()
        self.condition_order = condition_order
        self.interactive = config.INTERACTIVE if interactive is None else interactive
        self.condition = "interactive" if self.interactive else "static"
        self.session_id = str(uuid.uuid4())

        self._dir = log_dir or config.STUDY_LOGS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.path = self._dir / f"{self.participant_id}_{self.condition}_{stamp}.jsonl"

        self._origin = time.perf_counter()
        self._task_id: str | None = None
        self._task_origin: float | None = None
        self._handle = self.path.open("a", encoding="utf-8")

        self.event(
            "session_start",
            interactive=self.interactive,
            entities=config.ENTITIES,
            vaccines=list(config.VACCINES),
            year_range=[config.YEAR_MIN, config.YEAR_MAX],
        )

    # --- Core ---------------------------------------------------------------------------------

    def event(self, name: str, *, task_id: str | None = None, **payload: object) -> dict:
        """Write one event record. Returns the record, mainly so tests can assert on it."""
        if name not in EVENTS:
            raise LogError(f"Unknown event {name!r}; known events: {sorted(EVENTS)}")

        now = time.perf_counter()
        record = {
            "schema_version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "condition": self.condition,
            "condition_order": self.condition_order,
            "task_id": task_id if task_id is not None else self._task_id,
            "event": name,
            "timestamp": datetime.now(UTC).isoformat(),
            "elapsed_ms": round((now - self._origin) * 1000),
            "task_elapsed_ms": (
                None if self._task_origin is None else round((now - self._task_origin) * 1000)
            ),
            "payload": payload,
        }
        self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        # Flush per record: a crashed session must not cost a participant's data.
        self._handle.flush()
        return record

    # --- Task timing --------------------------------------------------------------------------

    def start_task(self, task_id: str) -> dict:
        if self._task_id is not None:
            raise LogError(
                f"Task {self._task_id!r} is still open; end it before starting {task_id!r}"
            )
        self._task_id = task_id
        self._task_origin = time.perf_counter()
        return self.event("task_start")

    def end_task(self, task_id: str | None = None) -> dict:
        if self._task_id is None:
            raise LogError("No task is open")
        if task_id is not None and task_id != self._task_id:
            raise LogError(f"Open task is {self._task_id!r}, not {task_id!r}")

        duration = round((time.perf_counter() - self._task_origin) * 1000)
        record = self.event("task_end", duration_ms=duration)
        self._task_id = None
        self._task_origin = None
        return record

    # --- Lifecycle ----------------------------------------------------------------------------

    def close(self, reason: str = "normal") -> None:
        if self._handle.closed:
            return
        if self._task_id is not None:
            # Record the abandonment rather than silently dropping an in-flight task.
            self.end_task()
            reason = "task_abandoned" if reason == "normal" else reason
        self.event("session_end", reason=reason)
        self._handle.close()

    def __enter__(self) -> StudyLogger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close(reason="normal" if exc_type is None else f"error:{exc_type.__name__}")


# --- Reading ----------------------------------------------------------------------------------


def read_log(path: Path) -> list[dict]:
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


def read_all(log_dir: Path | None = None) -> list[dict]:
    """Read every session file in `log_dir`, newest last."""
    directory = log_dir or config.STUDY_LOGS_DIR
    records: list[dict] = []
    for path in sorted(directory.glob("*.jsonl")):
        records.extend(read_log(path))
    return records
