"""Raw events to tidy frames: one row per task answered, and one per participant x condition.

Events arrive from three places with one important difference between them. `db.fetch_events`
returns `payload` as a dict (psycopg decodes JSONB); `scripts/export_logs.py` writes it as a JSON
*string*; local JSONL sessions give a dict. `_payload` accepts both, and the tests assert the two
routes produce identical frames -- otherwise a CSV-based analysis and a database-based one could
silently disagree.

The unscored practice item (`P0`) is dropped here, per study-design.md section 8. Every scored item,
T1-T6, counts towards the RQ1 accuracy score (section 7).
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
INTERACTION_EVENTS = ("filter_change", "line_isolate", "sort_change", "view_change")
# The events only the interactive condition's controls can produce. `view_change` is not among them:
# the schema documents it as possible in both conditions (src/logging.py EVENTS).
INTERACTIVE_ONLY_EVENTS = ("filter_change", "line_isolate", "sort_change")

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
    "skipped_answer",
    "skipped_justification",
]
TASK_COLUMNS = [*BASE_COLUMNS, *[f"n_{name}" for name in INTERACTION_EVENTS]]

# The three 7-point Likert items asked after each condition (study-design.md section 6.1).
LIKERT_KEYS = tuple(tasks.LIKERT_ITEMS)


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
                # type carries one item per form: descriptive only, never a powered comparison.
                "chart": charts.get((form, task_id)),
                "answer": payload.get("answer"),
                "justification": payload.get("justification"),
                "duration_ms": payload.get("duration_ms"),
                "duration_invalid": payload.get("duration_invalid"),
                "correct": answer_keys.is_correct(form, task_id, payload.get("answer"), key_table),
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
    surveys = events[events["event"] == "survey_rating"]
    likert = {
        str(session): payload
        for session, payload in zip(surveys["session_id"], surveys["payload"], strict=True)
    }
    ended = set(events.loc[events["event"] == "session_end", "session_id"].astype(str))
    recovered = set(events.loc[events["event"] == "sink_recovered", "session_id"].astype(str))

    by_session = tasks_frame.groupby("session_id")
    sessions["paas"] = sessions["session_id"].map(paas)
    for key in LIKERT_KEYS:
        sessions[key] = sessions["session_id"].map(lambda s, k=key: (likert.get(s) or {}).get(k))
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
