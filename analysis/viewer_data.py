"""What the local data viewer shows, as plain functions and frames. No Dash here, so it is testable.

**It must keep working when the data is broken**, because that is when it is most needed. The
scoring pipeline refuses loudly on mixed schema versions and on a failed manipulation check, as it
should. So the viewer has two layers:

- `health` works from the raw records and never raises. It is the collection check.
- `score` runs exactly the `scripts/score_study.py` pipeline, and on a refusal returns the reason
  instead of raising. Whatever depends on scoring degrades to unscored, with the reason shown.

**Justifications are masked unless asked for.** `docs/study-design.md` section 7 codes them blind to
condition, and `analysis/coding.py` builds its sheets to guarantee it. A table that puts a
justification beside its condition would quietly break that blind for whoever codes, so every
function that can emit one takes `show_justifications` and defaults to hiding it. Downloads are the
exception: they are the analysis input, and a masked copy would be silently wrong.

Read-only. Nothing here writes to any sink.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from analysis import exclusions, keys, reshape
from analysis import report as study_report
from src import db, tasks
from src import logging as study_logging

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"

# A session with no session_end whose last event is more recent than this is taken to be running
# now, not abandoned. A display heuristic only: it excludes nothing.
IN_PROGRESS_MINUTES = 60

HIDDEN = "(hidden)"
PRACTICE_ID = reshape.PRACTICE_ID
SCORED_TASKS = exclusions.SCORED_TASKS
INTERACTION_COUNT_COLUMNS = [f"n_{name}" for name in reshape.INTERACTION_EVENTS]


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # ok | warn | fail | info
    detail: str
    ids: tuple[str, ...] = ()


@dataclass
class Scoring:
    """The score_study.py pipeline's output, or why it refused."""

    tasks: pd.DataFrame | None = None
    conditions: pd.DataFrame | None = None
    exclusions: list[exclusions.Exclusion] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class Session:
    session_id: str
    participant_id: str
    condition: str
    condition_order: int | None
    form: str | None
    records: list[dict[str, Any]] = field(default_factory=list)

    @property
    def end(self) -> dict[str, Any] | None:
        return next((r for r in self.records if r["event"] == "session_end"), None)

    @property
    def scored_answers(self) -> set[str]:
        return {
            r["task_id"]
            for r in self.records
            if r["event"] == "answer_submit" and r["task_id"] != PRACTICE_ID
        }

    @property
    def last_ts(self) -> datetime | None:
        stamps = [t for t in (parse_ts(r["server_ts"]) for r in self.records) if t is not None]
        return max(stamps) if stamps else None

    @property
    def label(self) -> str:
        return f"{self.participant_id} {self.condition} ({self.session_id[:8]})"


# --- Normalising ---------------------------------------------------------------------------------


def parse_ts(value: Any) -> datetime | None:
    """A server timestamp as an aware datetime. Database rows give datetimes, JSONL and CSV text."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        stamp = value
    else:
        try:
            stamp = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)


def _decode_payload(raw: Any) -> dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else None
    except json.JSONDecodeError:
        decoded = None
    return decoded if isinstance(decoded, dict) else {"_unreadable": str(raw)}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalise(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The three sources' records in one JSON-safe shape.

    Postgres gives UUIDs, datetimes and a decoded payload; a CSV export gives text throughout; JSONL
    gives strings and a dict. Values are converted, never changed: a timestamp stays one instant.
    """
    out = []
    for record in records:
        row = dict(record)
        for column in ("session_id", "event_uid"):
            if row.get(column) is not None:
                row[column] = str(row[column])
        if isinstance(row.get("server_ts"), datetime):
            row["server_ts"] = row["server_ts"].isoformat()
        row["schema_version"] = _int_or_none(row.get("schema_version"))
        row["condition_order"] = _int_or_none(row.get("condition_order"))
        row["payload"] = _decode_payload(row.get("payload"))
        for column in ("participant_id", "condition", "form", "task_id", "event"):
            row.setdefault(column, None)
        out.append(row)
    return out


def sessions(records: list[dict[str, Any]]) -> dict[str, Session]:
    """Records grouped by session, in first-seen order. Expects normalised records."""
    grouped: dict[str, Session] = {}
    for record in records:
        session_id = str(record.get("session_id"))
        if session_id not in grouped:
            grouped[session_id] = Session(
                session_id=session_id,
                participant_id=str(record.get("participant_id")),
                condition=str(record.get("condition")),
                condition_order=record.get("condition_order"),
                form=record.get("form"),
            )
        grouped[session_id].records.append(record)
    return grouped


def _by_participant(grouped: dict[str, Session]) -> dict[str, list[Session]]:
    people: dict[str, list[Session]] = defaultdict(list)
    for session in grouped.values():
        people[session.participant_id].append(session)
    for items in people.values():
        items.sort(key=lambda s: (s.condition_order or 0, s.session_id))
    return people


def _minutes_since(stamp: datetime | None, now: datetime) -> float | None:
    return None if stamp is None else (now - stamp).total_seconds() / 60


def _running(stamp: datetime | None, now: datetime) -> bool:
    minutes = _minutes_since(stamp, now)
    return minutes is not None and minutes < IN_PROGRESS_MINUTES


def mask(value: Any, show: bool) -> Any:
    return value if show or not value else HIDDEN


# --- Health --------------------------------------------------------------------------------------


def health(
    records: list[dict[str, Any]],
    participants: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
    key_problems: list[str] | None = None,
) -> list[Check]:
    """Every collection check, from the raw records. Never raises on bad data."""
    now = now or datetime.now(UTC)
    key_problems = keys.check() if key_problems is None else key_problems
    grouped = sessions(records)
    people = _by_participant(grouped)
    checks: list[Check] = []

    checks.append(
        Check(
            "Answer key",
            FAIL,
            "The derived key disagrees with study-design.md §4.",
            tuple(key_problems),
        )
        if key_problems
        else Check("Answer key", OK, "Derived keys agree with study-design.md §4.")
    )

    if not records:
        checks.append(Check("Events", INFO, "No events recorded yet."))
        return checks

    versions = sorted({r["schema_version"] for r in records if r["schema_version"] is not None})
    if len(versions) != 1:
        checks.append(
            Check(
                "Schema version", FAIL, f"Events mix schema versions {versions}; do not pool them."
            )
        )
    elif versions[0] != study_logging.SCHEMA_VERSION:
        checks.append(
            Check(
                "Schema version",
                WARN,
                f"Events are v{versions[0]}; this code writes v{study_logging.SCHEMA_VERSION}.",
            )
        )
    else:
        checks.append(Check("Schema version", OK, f"Every event is v{versions[0]}."))

    unknown = Counter(r["event"] for r in records if r["event"] not in study_logging.EVENTS)
    checks.append(
        Check(
            "Event names",
            FAIL,
            "Events the logger does not define; analysis would miss them.",
            tuple(f"{name} x{n}" for name, n in sorted(unknown.items(), key=str)),
        )
        if unknown
        else Check("Event names", OK, "Every event is one the logger defines.")
    )

    leaked = [
        f"{grouped[str(r['session_id'])].label} {r['task_id']}: {r['event']}"
        for r in records
        if r["condition"] == "static" and r["event"] in reshape.INTERACTIVE_ONLY_EVENTS
    ]
    checks.append(
        Check(
            "Manipulation check",
            FAIL,
            "Interactive-only events were logged in the static condition.",
            tuple(leaked),
        )
        if leaked
        else Check("Manipulation check", OK, "No interactive-only events under static.")
    )

    answer_counts = Counter(
        (str(r["session_id"]), r["task_id"]) for r in records if r["event"] == "answer_submit"
    )
    duplicates = [f"{grouped[s].label} {t} x{n}" for (s, t), n in answer_counts.items() if n > 1]
    checks.append(
        Check(
            "One answer per task", FAIL, "A task recorded more than one answer.", tuple(duplicates)
        )
        if duplicates
        else Check("One answer per task", OK, "No task has more than one answer.")
    )

    consented = {r["participant_id"] for r in records if r["event"] == "consent"}
    unconsented = sorted(p for p in people if p not in consented)
    checks.append(
        Check(
            "Consent recorded",
            FAIL,
            "Participants with data but no consent event.",
            tuple(unconsented),
        )
        if unconsented
        else Check("Consent recorded", OK, "Every participant with data has a consent record.")
    )

    mispaired = []
    for participant, items in people.items():
        if len(items) == 2:
            if items[0].condition == items[1].condition:
                mispaired.append(f"{participant}: {items[0].condition} twice")
            if items[0].form is not None and items[0].form == items[1].form:
                mispaired.append(f"{participant}: form {items[0].form} twice")
    checks.append(
        Check(
            "Condition and form pairing",
            FAIL,
            "A participant saw the same condition or form twice.",
            tuple(mispaired),
        )
        if mispaired
        else Check(
            "Condition and form pairing", OK, "Everyone saw each condition and form at most once."
        )
    )

    recovered = [r for r in records if r["event"] == "sink_recovered"]
    dropped = sum(_int_or_none(r["payload"].get("dropped")) or 0 for r in recovered)
    outage_ids = tuple(
        f"{grouped[str(r['session_id'])].label}: spooled {r['payload'].get('spooled')}, "
        f"dropped {r['payload'].get('dropped')}"
        for r in recovered
    )
    if dropped:
        checks.append(
            Check(
                "Database outages",
                FAIL,
                f"{dropped} events overflowed the browser spool and were lost.",
                outage_ids,
            )
        )
    elif recovered:
        checks.append(
            Check(
                "Database outages",
                WARN,
                "Sessions logged through an outage. Nothing lost; §7 re-runs timing without them.",
                outage_ids,
            )
        )
    else:
        checks.append(Check("Database outages", OK, "No session went through a database outage."))

    unended = [s for s in grouped.values() if s.end is None]
    abandoned = [s for s in unended if not _running(s.last_ts, now)]
    running = [s for s in unended if _running(s.last_ts, now)]

    def _age(session: Session) -> str:
        minutes = _minutes_since(session.last_ts, now)
        return (
            f"{session.label}: last event {minutes:.0f} min ago"
            if minutes is not None
            else session.label
        )

    if abandoned:
        checks.append(
            Check(
                "Sessions ended",
                WARN,
                f"{len(abandoned)} session(s) stopped without a session_end "
                f"(silent for {IN_PROGRESS_MINUTES}+ min).",
                tuple(_age(s) for s in [*abandoned, *running]),
            )
        )
    elif running:
        checks.append(
            Check(
                "Sessions ended",
                INFO,
                f"{len(running)} session(s) in progress.",
                tuple(_age(s) for s in running),
            )
        )
    else:
        checks.append(Check("Sessions ended", OK, "Every session has a session_end."))

    odd_reasons = [
        f"{s.label}: {s.end['payload'].get('reason')}"
        for s in grouped.values()
        if s.end is not None and s.end["payload"].get("reason") != "normal"
    ]
    checks.append(
        Check(
            "Session end reasons",
            WARN,
            "Sessions that ended other than normally.",
            tuple(odd_reasons),
        )
        if odd_reasons
        else Check("Session end reasons", OK, "Every ended session ended normally.")
    )

    short = []
    for participant, items in people.items():
        if len(items) != 2 and not _running(
            max((s.last_ts for s in items if s.last_ts), default=None), now
        ):
            short.append(f"{participant}: {len(items)} session(s)")
    for session in grouped.values():
        n = len(session.scored_answers)
        if session.end is not None and n != SCORED_TASKS:
            short.append(f"{session.label}: {n}/{SCORED_TASKS} answers")
    checks.append(
        Check(
            "Completeness",
            WARN,
            "Not two sessions of six answers each. §7 excludes these participants.",
            tuple(short),
        )
        if short
        else Check("Completeness", OK, "Every finished participant has two full sessions.")
    )

    unrated = [
        s.label
        for s in grouped.values()
        if s.end is not None
        and s.end["payload"].get("reason") == "normal"
        and not any(r["event"] == "load_rating" for r in s.records)
    ]
    checks.append(
        Check("Mental-effort rating", WARN, "Ended sessions with no Paas rating.", tuple(unrated))
        if unrated
        else Check("Mental-effort rating", OK, "Every ended session has a Paas rating.")
    )

    invalid = Counter()
    invalid_ids = []
    for r in records:
        if r["event"] != "answer_submit":
            continue
        reason = r["payload"].get("duration_invalid") or (
            "missing" if r["payload"].get("duration_ms") is None else None
        )
        if reason:
            invalid[reason] += 1
            invalid_ids.append(f"{grouped[str(r['session_id'])].label} {r['task_id']}: {reason}")
    checks.append(
        Check(
            "Durations",
            WARN,
            "Answers with no usable duration ("
            + ", ".join(f"{k}: {v}" for k, v in sorted(invalid.items()))
            + "). Accuracy stands; timing drops them.",
            tuple(invalid_ids),
        )
        if invalid
        else Check("Durations", OK, "Every answer has a browser-measured duration.")
    )

    if participants is None:
        checks.append(
            Check("Registered without events", INFO, "Only the database records registrations.")
        )
    else:
        silent = sorted(
            str(p["participant_id"]) for p in participants if str(p["participant_id"]) not in people
        )
        checks.append(
            Check(
                "Registered without events",
                INFO,
                f"{len(silent)} registered but left before the instructions screen.",
                tuple(silent),
            )
            if silent
            else Check("Registered without events", OK, "Everyone who registered logged events.")
        )

    idle = [
        s.label
        for s in grouped.values()
        if s.condition == "interactive"
        and s.end is not None
        and not any(r["event"] in reshape.INTERACTIVE_ONLY_EVENTS for r in s.records)
    ]
    checks.append(
        Check(
            "Interactive use",
            INFO,
            "Finished interactive sessions with no filter, sort or isolation. Not an error.",
            tuple(idle),
        )
        if idle
        else Check("Interactive use", OK, "Every finished interactive session used a control.")
    )
    return checks


def cell_balance(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Participants per counterbalancing cell, by what they were actually shown first."""
    first: dict[str, tuple[str, str]] = {}
    for record in records:
        if record["condition_order"] == 1 and record["participant_id"] not in first:
            first[record["participant_id"]] = (record["condition"], record["form"])
    counts = Counter(first.values())
    cells = [db.assignment_for(seq) for seq in range(4)]
    return pd.DataFrame(
        [
            {"first condition": c, "first form": f, "participants": counts.get((c, f), 0)}
            for c, f in cells
        ]
    )


# --- Scoring -------------------------------------------------------------------------------------


def score(records: list[dict[str, Any]], *, key_problems: list[str] | None = None) -> Scoring:
    """The score_study.py pipeline. Returns the refusal as `error` rather than raising."""
    key_problems = keys.check() if key_problems is None else key_problems
    if key_problems:
        return Scoring(error="The answer key does not check out: " + "; ".join(key_problems))
    if not records:
        return Scoring(error="No events recorded yet.")
    try:
        events = reshape.events_frame(records)
        tasks_frame = reshape.tidy_tasks(events)
        conditions = reshape.tidy_conditions(events, tasks_frame)
        scored, excluded = exclusions.apply(tasks_frame, conditions)
    except reshape.ReshapeError as exc:
        return Scoring(error=f"Scoring refused: {exc}")
    except Exception as exc:  # the viewer must stay up to show what is wrong
        return Scoring(error=f"Scoring failed: {type(exc).__name__}: {exc}")
    return Scoring(tasks=scored, conditions=conditions, exclusions=excluded)


UNIT_NAMES = {"session:task": "answer"}


def report_tables(scoring: Scoring) -> list[tuple[str, pd.DataFrame]]:
    """The section 7 descriptive tables, as score_study.py prints them."""
    if not scoring.ok:
        return []
    tasks_frame, conditions = scoring.tasks, scoring.conditions
    included = set(tasks_frame.loc[tasks_frame["use_accuracy"], "participant_id"].astype(str))
    by_condition = [
        (
            "Accuracy, RQ1 primary: proportion correct per participant, T1-T5",
            study_report.accuracy(tasks_frame),
        ),
        (
            "Crossing items secondary: strict vs adjacent-band credit",
            study_report.crossing_adjacent(tasks_frame),
        ),
        (
            "T6 gap check, reported separately: proportion correct",
            study_report.gap_check(tasks_frame),
        ),
        ("Mental effort, RQ3: Paas 1-9", study_report.mental_effort(conditions, included)),
        ("Time on task (ms), timing-usable rows only", study_report.time_on_task(tasks_frame)),
    ]
    # report.exclusion_table puts each rule's unit in its own column, which leaves a sparse, float-
    # cast grid on screen. Same numbers, one "affected" column.
    exclusion_table = pd.DataFrame(
        [
            {
                "rule": e.rule,
                "kind": e.kind,
                "rows affected": e.n_rows,
                "affected": f"{len(e.ids)} {UNIT_NAMES.get(e.unit, e.unit)}"
                + ("" if len(e.ids) == 1 else "s"),
                "reason": e.reason,
            }
            for e in scoring.exclusions
        ]
    )
    return [
        ("Exclusions (study-design.md §7)", exclusion_table),
        *[(title, frame.reset_index().round(3)) for title, frame in by_condition],
    ]


def _excluded_by_participant(scoring: Scoring, grouped: dict[str, Session]) -> dict[str, list[str]]:
    rules: dict[str, list[str]] = defaultdict(list)
    for exclusion in scoring.exclusions:
        for item in exclusion.ids:
            if exclusion.unit == "participant":
                participant = item
            else:
                session = grouped.get(item.split(":")[0])
                participant = session.participant_id if session else None
            if participant and exclusion.rule not in rules[participant]:
                rules[participant].append(exclusion.rule)
    return rules


# --- Tables --------------------------------------------------------------------------------------

OVERVIEW_COLUMNS = [
    "participant_id",
    "status",
    "cell",
    "sessions",
    *[f"{c} {m}" for c in study_logging.CONDITIONS for m in ("answers", "Paas", "accuracy")],
    "consented_at",
    "first event",
    "last event",
    "exclusions",
]


def participant_overview(
    records: list[dict[str, Any]],
    scoring: Scoring,
    participants: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """One row per participant: cell, progress, Paas and accuracy per condition, exclusions.

    Accuracy is the RQ1 score, over T1-T5; T6 is reported separately (study-design.md section 7).
    """
    now = now or datetime.now(UTC)
    grouped = sessions(records)
    people = _by_participant(grouped)
    excluded = _excluded_by_participant(scoring, grouped) if scoring.ok else {}
    accuracy = {}
    if scoring.ok and not scoring.tasks.empty:
        rq1 = scoring.tasks[~scoring.tasks["task_id"].isin(reshape.SEPARATELY_REPORTED)]
        accuracy = rq1.groupby(["participant_id", "condition"])["correct"].mean().to_dict()

    rows = []
    for participant, items in people.items():
        mine = [r for s in items for r in s.records]
        stamps = [t for t in (parse_ts(r["server_ts"]) for r in mine) if t is not None]
        first = next((s for s in items if s.condition_order == 1), items[0])
        complete = len(items) == 2 and all(
            s.end is not None and len(s.scored_answers) == SCORED_TASKS for s in items
        )
        if complete:
            status = "complete"
        elif _running(max(stamps, default=None), now):
            status = "in progress"
        else:
            status = "incomplete"
        consent = next((r for r in mine if r["event"] == "consent"), None)
        row: dict[str, Any] = {
            "id": participant,
            "participant_id": participant,
            "status": status,
            "cell": f"{first.condition} first, form {first.form}",
            "sessions": len(items),
        }
        for condition in study_logging.CONDITIONS:
            of_condition = [s for s in items if s.condition == condition]
            answered = (
                set().union(*(s.scored_answers for s in of_condition)) if of_condition else set()
            )
            ratings = [
                r["payload"].get("value")
                for s in of_condition
                for r in s.records
                if r["event"] == "load_rating"
            ]
            share = accuracy.get((participant, condition))
            row[f"{condition} answers"] = f"{len(answered)}/{SCORED_TASKS}"
            row[f"{condition} Paas"] = ratings[-1] if ratings else None
            row[f"{condition} accuracy"] = (
                None if share is None or pd.isna(share) else round(float(share), 3)
            )
        row["consented_at"] = consent["payload"].get("consented_at") if consent else None
        row["first event"] = min(stamps).isoformat(timespec="seconds") if stamps else None
        row["last event"] = max(stamps).isoformat(timespec="seconds") if stamps else None
        row["exclusions"] = ", ".join(excluded.get(participant, []))
        rows.append(row)

    for registered in participants or []:
        participant = str(registered["participant_id"])
        if participant in people:
            continue
        created = parse_ts(registered.get("created_at"))
        rows.append(
            {
                "id": participant,
                "participant_id": participant,
                "status": "registered, no events",
                "first event": created.isoformat(timespec="seconds") if created else None,
            }
        )

    frame = pd.DataFrame(rows, columns=["id", *OVERVIEW_COLUMNS])
    return frame.sort_values("first event", na_position="last").reset_index(drop=True)


def _prompt(form: str | None, task_id: str | None) -> str:
    if task_id == PRACTICE_ID:
        return tasks.PRACTICE.prompt
    if form not in tasks.FORMS:
        return ""
    return next((t.prompt for t in tasks.for_form(form) if t.task_id == task_id), "")


ANSWER_COLUMNS = [
    "participant_id",
    "session_id",
    "condition",
    "condition_order",
    "form",
    "task_id",
    "prompt",
    "answer",
    "justification",
    "correct",
    "correct_adjacent",
    "duration_ms",
    "duration_invalid",
    *INTERACTION_COUNT_COLUMNS,
]


def answers(
    records: list[dict[str, Any]], scoring: Scoring, *, show_justifications: bool = False
) -> pd.DataFrame:
    """Every answer as recorded, practice included, with correctness when scoring succeeded.

    Built from the raw records rather than the tidy frame, so it still works when scoring refuses.
    """
    interactions = Counter(
        (str(r["session_id"]), r["task_id"], r["event"])
        for r in records
        if r["event"] in reshape.INTERACTION_EVENTS
    )
    correctness: dict[tuple[str, str], tuple[Any, Any]] = {}
    if scoring.ok:
        for row in scoring.tasks.to_dict("records"):
            correctness.setdefault(
                (str(row["session_id"]), row["task_id"]), (row["correct"], row["correct_adjacent"])
            )

    rows = []
    for record in records:
        if record["event"] != "answer_submit":
            continue
        payload = record["payload"]
        session_id, task_id = str(record["session_id"]), record["task_id"]
        correct, adjacent = correctness.get((session_id, task_id), (None, None))
        rows.append(
            {
                "participant_id": record["participant_id"],
                "session_id": session_id,
                "condition": record["condition"],
                "condition_order": record["condition_order"],
                "form": record["form"],
                "task_id": task_id,
                "prompt": _prompt(record["form"], task_id),
                "answer": payload.get("answer"),
                "justification": mask(payload.get("justification"), show_justifications),
                "correct": "practice" if task_id == PRACTICE_ID else correct,
                "correct_adjacent": adjacent,
                "duration_ms": payload.get("duration_ms"),
                "duration_invalid": payload.get("duration_invalid"),
                **{
                    f"n_{name}": interactions.get((session_id, task_id, name), 0)
                    for name in reshape.INTERACTION_EVENTS
                },
            }
        )
    return pd.DataFrame(rows, columns=ANSWER_COLUMNS)


EVENT_TABLE_COLUMNS = [
    "server_ts",
    "participant_id",
    "condition",
    "condition_order",
    "form",
    "session_id",
    "task_id",
    "event",
    "client_elapsed_ms",
    "task_elapsed_ms",
    "server_elapsed_ms",
    "schema_version",
    "payload",
]


def events_table(
    records: list[dict[str, Any]], *, show_justifications: bool = False
) -> pd.DataFrame:
    """Every event, payload as JSON text, justification masked unless asked for."""
    rows = []
    for record in records:
        payload = dict(record["payload"])
        if "justification" in payload:
            payload["justification"] = mask(payload["justification"], show_justifications)
        row = {column: record.get(column) for column in EVENT_TABLE_COLUMNS}
        row["payload"] = json.dumps(payload, ensure_ascii=False, default=str)
        rows.append(row)
    return pd.DataFrame(rows, columns=EVENT_TABLE_COLUMNS)


@dataclass
class SessionDetail:
    title: str
    summary: str
    answers: pd.DataFrame
    events: pd.DataFrame


def participant_detail(
    records: list[dict[str, Any]],
    scoring: Scoring,
    participant_id: str,
    *,
    show_justifications: bool = False,
) -> list[SessionDetail]:
    """One block per session of one participant, in the order they took them."""
    grouped = sessions(records)
    items = _by_participant(grouped).get(participant_id, [])
    all_answers = answers(records, scoring, show_justifications=show_justifications)
    details = []
    for session in items:
        end = session.end
        rating = next((r for r in session.records if r["event"] == "load_rating"), None)
        summary = " · ".join(
            [
                f"session {session.session_id}",
                f"ended ({end['payload'].get('reason')})" if end else "not ended",
                f"{len(session.scored_answers)}/{SCORED_TASKS} scored answers",
                f"Paas {rating['payload'].get('value')}" if rating else "no Paas rating",
                f"{len(session.records)} events",
            ]
        )
        details.append(
            SessionDetail(
                title=(
                    f"Condition {session.condition_order}: {session.condition}, form {session.form}"
                ),
                summary=summary,
                answers=all_answers[all_answers["session_id"] == session.session_id]
                .drop(
                    columns=["participant_id", "session_id", "condition", "condition_order", "form"]
                )
                .reset_index(drop=True),
                events=events_table(session.records, show_justifications=show_justifications).drop(
                    columns=["participant_id", "condition", "condition_order", "form", "session_id"]
                ),
            )
        )
    return details


# --- Downloads -----------------------------------------------------------------------------------


def events_csv(records: list[dict[str, Any]]) -> str:
    """The same file `scripts/export_logs.py` writes, so `score_study.py --events` reads it back."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(db.EVENT_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    for record in records:
        row = dict(record)
        row["payload"] = json.dumps(row.get("payload") or {}, default=str)
        writer.writerow(row)
    return buffer.getvalue()
