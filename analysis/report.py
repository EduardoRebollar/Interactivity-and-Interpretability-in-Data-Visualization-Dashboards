"""The descriptive numbers `docs/study-design.md` section 7 asks for, and nothing more.

Per condition: accuracy (the RQ1 primary outcome, as the mean of per-participant proportions, a
skip scored incorrect), the pre-registered secondaries (skips excluded; T5 adjacent-band credit),
skip counts, Paas mental effort (RQ3), the Likert survey, and time on task. Plus the
exclusion table section 7 requires. Inferential tests are deliberately absent: they belong in the
analysis notebook, run once, on the frames this package produces.
"""

from __future__ import annotations

import pandas as pd

from analysis.exclusions import Exclusion


def accuracy(tasks: pd.DataFrame) -> pd.DataFrame:
    """Proportion correct per participant per condition, then summarised by condition."""
    usable = tasks[tasks["use_accuracy"]]
    per_participant = (
        usable.groupby(["condition", "participant_id"])["correct"].mean().rename("prop_correct")
    )
    return per_participant.groupby("condition").agg(["count", "mean", "std"])


def accuracy_answered(tasks: pd.DataFrame) -> pd.DataFrame:
    """Secondary: proportion correct among ANSWERED items only, skips excluded (section 7)."""
    usable = tasks[tasks["use_accuracy"] & ~tasks["skipped_answer"].astype(bool)]
    per_participant = (
        usable.groupby(["condition", "participant_id"])["correct"].mean().rename("prop_correct")
    )
    return per_participant.groupby("condition").agg(["count", "mean", "std"])


def skips(tasks: pd.DataFrame) -> pd.DataFrame:
    """How many answers and justifications were skipped, by condition. Reported with accuracy."""
    usable = tasks[tasks["use_accuracy"]]
    return usable.groupby("condition")[["skipped_answer", "skipped_justification"]].sum()


def survey(conditions: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    """The three 7-point Likert items, descriptively, by condition (section 6.1)."""
    from analysis.reshape import LIKERT_KEYS

    rated = conditions[conditions["participant_id"].astype(str).isin(included)]
    columns = [key for key in LIKERT_KEYS if key in rated]
    return rated.groupby("condition")[columns].agg(["count", "mean", "std"])


def t5_adjacent(tasks: pd.DataFrame) -> pd.DataFrame:
    """Secondary: T5 correct under strict and under adjacent-band scoring, by condition."""
    t5 = tasks[tasks["use_accuracy"] & (tasks["task_id"] == "T5")]
    return t5.groupby("condition")[["correct", "correct_adjacent"]].mean()


def mental_effort(conditions: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    rated = conditions[conditions["participant_id"].astype(str).isin(included)]
    return rated.groupby("condition")["paas"].agg(["count", "mean", "std"])


def time_on_task(tasks: pd.DataFrame) -> pd.DataFrame:
    timed = tasks[tasks["use_timing"]]
    return timed.groupby("condition")["duration_ms"].agg(["count", "median", "mean"])


def exclusion_table(exclusions: list[Exclusion]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rule": e.rule,
                "kind": e.kind,
                "rows affected": e.n_rows,
                f"{e.unit}s": len(e.ids),
                "reason": e.reason,
            }
            for e in exclusions
        ]
    )


def render(tasks: pd.DataFrame, conditions: pd.DataFrame, exclusions: list[Exclusion]) -> str:
    included = set(tasks.loc[tasks["use_accuracy"], "participant_id"].astype(str))
    sections = [
        ("Exclusions (study-design.md section 7)", exclusion_table(exclusions)),
        ("Accuracy, RQ1 primary: proportion correct per participant", accuracy(tasks)),
        ("Accuracy, secondary: answered items only, skips excluded", accuracy_answered(tasks)),
        ("Skipped answers and justifications", skips(tasks)),
        ("T5 secondary: strict vs adjacent-band credit", t5_adjacent(tasks)),
        ("Mental effort, RQ3: Paas 1-9", mental_effort(conditions, included)),
        ("Survey: clarity, ease of use, confidence (1-7)", survey(conditions, included)),
        ("Time on task (ms), timing-usable rows only", time_on_task(tasks)),
    ]
    parts = []
    with pd.option_context("display.width", 120, "display.max_columns", 20):
        for title, frame in sections:
            parts.append(f"{title}\n{'-' * len(title)}\n{frame.to_string()}\n")
    return "\n".join(parts)
