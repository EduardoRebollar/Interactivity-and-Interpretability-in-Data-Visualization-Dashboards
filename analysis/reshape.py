"""Raw events to tidy frames: one row per task answered, one per participant x condition, and
one per participant for About you.

Events arrive from three places with one important difference between them. `db.fetch_events`
returns `payload` as a dict (psycopg decodes JSONB); `scripts/export_logs.py` writes it as a JSON
*string*; local JSONL sessions give a dict. `_payload` accepts both, and the tests assert the two
routes produce identical frames -- otherwise a CSV-based analysis and a database-based one could
silently disagree.

The unscored practice item (`P0`) is dropped here, per study-design.md section 8. Every scored item,
T1-T6, counts towards the RQ1 accuracy score (section 7). The crossing item, T6, also carries its
pre-registered secondary score, adjacent-band credit (`correct_adjacent`); every other item has None
there.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from analysis import keys as answer_keys
from src import tasks

PRACTICE_ID = tasks.PRACTICE.task_id
INTERACTION_EVENTS = ("filter_change", "line_isolate", "sort_change", "view_change", "view_reset")
# The events only the interactive condition's controls can produce. `view_change` is not among them:
# the schema documents it as possible in both conditions (src/logging.py EVENTS). Reset view is a
# control under the chart, in the interactive condition only.
INTERACTIVE_ONLY_EVENTS = ("filter_change", "line_isolate", "sort_change", "view_reset")

BASE_COLUMNS = [
    "participant_id",
    "session_id",
    "condition",
    "condition_order",
    "form",
    "task_id",
    "kind",
    "chart",
    "answer",
    "justification",
    "duration_ms",
    "duration_invalid",
    "correct",
    "correct_adjacent",
    "skipped_answer",
    "skipped_justification",
]
# The participant's browser window, from `window_size` (schema v10), on every row of theirs. The
# interactive scatter (T3) and map (T5) cards need scrolling on a window 790 px tall or less, and
# the static ones never do (study-design.md section 10): these columns tell who scrolled.
WINDOW_COLUMNS = ["window_width", "window_height"]
TASK_COLUMNS = [
    *BASE_COLUMNS,
    *[f"n_{name}" for name in INTERACTION_EVENTS],
    *WINDOW_COLUMNS,
]

# The survey after each condition (study-design.md section 6.1): a1-a9 always, b1-b3 after the
# interactive condition only, c1-c3 after the second only. A key not asked is missing there.
LIKERT_KEYS = tuple(tasks.LIKERT_ITEMS)
CONTROLS_KEYS = tuple(tasks.CONTROLS_ITEMS)
COMPARISON_KEYS = tuple(tasks.COMPARISON_KEYS)
SURVEY_EVENTS = (
    ("survey_rating", LIKERT_KEYS),
    ("controls_rating", CONTROLS_KEYS),
    ("comparison", COMPARISON_KEYS),
)

# About you, one column per answer: the tools question's rows each get their own.
DEMOGRAPHIC_COLUMNS = [
    column
    for question in tasks.ABOUT_QUESTIONS
    for column in (
        [f"{question.key}: {row}" for row in question.rows]
        if question.kind == "matrix"
        else [question.key, *([question.other_key] if question.other_key else [])]
    )
]


class ReshapeError(ValueError):
    """The events cannot be analysed as they are, e.g. they pool schema versions."""


def _payload(raw: Any) -> dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise ReshapeError(f"Unreadable payload of type {type(raw).__name__}")


def read_export(path: Path) -> list[dict[str, Any]]:
    """Read a CSV written by `scripts/export_logs.py` back into event records."""
    numeric = {"schema_version": int, "condition_order": int}
    with path.open(newline="", encoding="utf-8") as handle:
        records = []
        for row in csv.DictReader(handle):
            record: dict[str, Any] = {k: (v if v != "" else None) for k, v in row.items()}
            for column, cast in numeric.items():
                if record.get(column) is not None:
                    record[column] = cast(record[column])
            records.append(record)
    return records


def events_frame(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Every event as a row, payload decoded. Refuses to pool schema versions."""
    rows = []
    for record in records:
        row = dict(record)
        row["payload"] = _payload(record.get("payload"))
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ReshapeError("No events to analyse")
    versions = set(frame["schema_version"].dropna().astype(int))
    if len(versions) != 1:
        # export_logs.py only warns about this. Analysis must refuse: the record shape differs
        # between versions, so pooled rows are not comparable.
        raise ReshapeError(f"Events mix schema versions {sorted(versions)}; do not pool them")
    return frame


def tidy_tasks(events: pd.DataFrame, key_table: dict | None = None) -> pd.DataFrame:
    """One row per scored answer: participant x condition x task, with correctness attached.

    A skipped answer is `None`, which never equals a key, so `correct` is False for it: the primary
    rule in study-design.md section 7 scores a skip as incorrect. `skipped_answer` marks it, so the
    pre-registered secondary (skips excluded) and the per-condition skip counts can be computed.
    """
    key_table = key_table if key_table is not None else answer_keys.key_table()
    charts = {(t.form, t.task_id): t.chart for form in tasks.FORMS for t in tasks.for_form(form)}

    answers = events[(events["event"] == "answer_submit") & (events["task_id"] != PRACTICE_ID)]
    rows = []
    for record in answers.to_dict("records"):
        payload = record["payload"]
        form, task_id = record["form"], record["task_id"]
        key = key_table.get((form, task_id))
        if key is None:
            raise ReshapeError(f"Answer for unknown item {form}-{task_id}")
        rows.append(
            {
                "participant_id": record["participant_id"],
                "session_id": str(record["session_id"]),
                "condition": record["condition"],
                "condition_order": int(record["condition_order"]),
                "form": form,
                "task_id": task_id,
                "kind": key.kind,
                # The chart type, so a per-affordance summary does not have to re-derive it. Each
                # type carries one item per form, the line chart three: descriptive only, never a
                # powered comparison.
                "chart": charts.get((form, task_id)),
                "answer": payload.get("answer"),
                "justification": payload.get("justification"),
                "duration_ms": payload.get("duration_ms"),
                "duration_invalid": payload.get("duration_invalid"),
                "correct": answer_keys.is_correct(form, task_id, payload.get("answer"), key_table),
                "correct_adjacent": answer_keys.is_correct_adjacent(
                    form, task_id, payload.get("answer"), key_table
                ),
                "skipped_answer": payload.get("answer") is None,
                "skipped_justification": not (payload.get("justification") or "").strip(),
            }
        )
    tasks_frame = pd.DataFrame(rows, columns=BASE_COLUMNS)
    tasks_frame["duration_ms"] = pd.to_numeric(tasks_frame["duration_ms"], errors="coerce")

    counts = _interaction_counts(events)
    for name in INTERACTION_EVENTS:
        column = f"n_{name}"
        tasks_frame[column] = [
            counts.get((session, task, name), 0)
            for session, task in zip(tasks_frame["session_id"], tasks_frame["task_id"], strict=True)
        ]

    windows = _window_sizes(events)
    for column, key in zip(WINDOW_COLUMNS, ("width", "height"), strict=True):
        tasks_frame[column] = pd.array(
            [windows.get(p, {}).get(key) for p in tasks_frame["participant_id"]], dtype="Int64"
        )

    static_interactions = tasks_frame.loc[
        tasks_frame["condition"] == "static", [f"n_{name}" for name in INTERACTIVE_ONLY_EVENTS]
    ]
    if static_interactions.to_numpy().sum() > 0:
        # The static condition renders no controls and a chart with staticPlot: True. An interaction
        # recorded there means the manipulation failed: the condition is not what it claims to be.
        raise ReshapeError(
            "Interactive-only events recorded in the static condition: manipulation check failed"
        )
    return tasks_frame[TASK_COLUMNS]


def _window_sizes(events: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Each participant's window, from their `window_size` event (logged once, at the start)."""
    logged = events[events["event"] == "window_size"].sort_values("server_ts", kind="stable")
    sizes: dict[str, dict[str, Any]] = {}
    for participant, payload in zip(logged["participant_id"], logged["payload"], strict=True):
        sizes.setdefault(participant, payload)
    return sizes


def _interaction_counts(events: pd.DataFrame) -> dict[tuple[str, str, str], int]:
    subset = events[events["event"].isin(INTERACTION_EVENTS)]
    counts: dict[tuple[str, str, str], int] = {}
    for session, task, name in zip(
        subset["session_id"].astype(str), subset["task_id"], subset["event"], strict=True
    ):
        counts[(session, task, name)] = counts.get((session, task, name), 0) + 1
    return counts


def tidy_conditions(events: pd.DataFrame, tasks_frame: pd.DataFrame) -> pd.DataFrame:
    """One row per participant x condition log session: the RQ1 and RQ3 analysis unit."""
    sessions = events.drop_duplicates("session_id")[
        ["participant_id", "session_id", "condition", "condition_order", "form"]
    ].copy()
    sessions["session_id"] = sessions["session_id"].astype(str)

    ratings = events[events["event"] == "load_rating"]
    paas = {
        str(session): payload.get("value")
        for session, payload in zip(ratings["session_id"], ratings["payload"], strict=True)
    }
    answered_by_event = {}
    for name, _keys in SURVEY_EVENTS:
        chosen = events[events["event"] == name]
        answered_by_event[name] = {
            str(session): payload
            for session, payload in zip(chosen["session_id"], chosen["payload"], strict=True)
        }
    ended = set(events.loc[events["event"] == "session_end", "session_id"].astype(str))
    recovered = set(events.loc[events["event"] == "sink_recovered", "session_id"].astype(str))

    by_session = tasks_frame.groupby("session_id")
    sessions["paas"] = sessions["session_id"].map(paas)
    for name, keys in SURVEY_EVENTS:
        given = answered_by_event[name]
        for key in keys:
            sessions[key] = sessions["session_id"].map(
                lambda s, k=key, g=given: (g.get(s) or {}).get(k)
            )
    sessions["n_answers"] = sessions["session_id"].map(by_session["task_id"].nunique()).fillna(0)
    sessions["n_answers"] = sessions["n_answers"].astype(int)
    # Primary: skips count as incorrect, so the denominator is every scored answer (T1-T6).
    sessions["prop_correct"] = sessions["session_id"].map(by_session["correct"].mean())
    # Secondary, pre-registered: among answered items only.
    answered = tasks_frame[~tasks_frame["skipped_answer"].astype(bool)]
    sessions["prop_correct_answered"] = sessions["session_id"].map(
        answered.groupby("session_id")["correct"].mean()
    )
    sessions["n_skipped"] = (
        sessions["session_id"].map(by_session["skipped_answer"].sum()).fillna(0).astype(int)
    )
    sessions["ended"] = sessions["session_id"].isin(ended)
    sessions["degraded"] = sessions["session_id"].isin(recovered)
    return sessions.sort_values(["participant_id", "condition_order"]).reset_index(drop=True)


def tidy_participants(events: pd.DataFrame) -> pd.DataFrame:
    """One row per participant: the About-you answers (study-design.md section 6.2).

    Logged once, after the second session's end, so a participant who stopped earlier has no row.
    The tools question's answer, an object from tool to answer, becomes one column per tool. Should
    a participant somehow have two records, the later one stands.
    """
    about = events[events["event"] == "demographics"].sort_values("server_ts", kind="stable")
    rows = []
    for participant, payload in zip(about["participant_id"], about["payload"], strict=True):
        row: dict[str, Any] = {"participant_id": participant}
        for question in tasks.ABOUT_QUESTIONS:
            if question.kind == "matrix":
                answers = payload.get(question.key) or {}
                for tool in question.rows:
                    row[f"{question.key}: {tool}"] = answers.get(tool)
            else:
                row[question.key] = payload.get(question.key)
                if question.other_key:
                    row[question.other_key] = payload.get(question.other_key)
        rows.append(row)
    frame = pd.DataFrame(rows, columns=["participant_id", *DEMOGRAPHIC_COLUMNS])
    return frame.drop_duplicates("participant_id", keep="last").reset_index(drop=True)
