"""The exclusion rules pre-registered in `docs/study-design.md` section 7.

Nothing is dropped. Each rule marks rows, so the same frame serves every analysis and the report can
say exactly how many rows each rule removed and why -- which section 7 requires.

Two kinds, because they remove different things:

- **Accuracy exclusions** (`incomplete_session`, `too_fast`): the response is unusable, so the row
  leaves every analysis. Clears `use_accuracy` and `use_timing`.
- **Timing exclusions** (`invalid_timing`, `top_one_percent`): the answer stands but its duration
  does not. Clears `use_timing` only.

`degraded_session` is reported and never excludes.

**Order is fixed** and changing it changes the numbers: session-level rules, then `too_fast`, then
`invalid_timing`, then the 1% trim computed on whatever timing rows survive.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src import tasks as task_bank

MIN_TASK_MS = 3_000
TOP_TRIM_QUANTILE = 0.99
# Scored items per session, from the task bank itself, so adding an item cannot leave every
# session looking incomplete. Both forms have the same number (tests/test_tasks.py).
SCORED_TASKS = len(task_bank.for_form("A"))
CONDITIONS_PER_PARTICIPANT = 2


@dataclass(frozen=True)
class Exclusion:
    rule: str
    kind: str  # "accuracy" | "timing" | "report"
    unit: str  # what `ids` identifies
    n_rows: int  # task rows newly affected by this rule
    ids: tuple[str, ...]
    reason: str


def incomplete_participants(tasks: pd.DataFrame, conditions: pd.DataFrame) -> set[str]:
    """Participants without exactly two ended sessions of `SCORED_TASKS` answers each.

    More than two sessions is incomplete too: it is the signature of a participant who closed the
    tab and restarted, which leaves overlapping runs under one ID that need manual inspection.
    """
    incomplete = set()
    for participant, sessions in conditions.groupby("participant_id"):
        answered = tasks[tasks["participant_id"] == participant].groupby("session_id")["task_id"]
        per_session = answered.nunique()
        ok = (
            len(sessions) == CONDITIONS_PER_PARTICIPANT
            and bool(sessions["ended"].all())
            and all(per_session.get(s, 0) == SCORED_TASKS for s in sessions["session_id"])
        )
        if not ok:
            incomplete.add(str(participant))
    return incomplete


def apply(tasks: pd.DataFrame, conditions: pd.DataFrame) -> tuple[pd.DataFrame, list[Exclusion]]:
    """Mark exclusions in order. Returns the frame, with use_accuracy/use_timing, and the report."""
    frame = tasks.copy()
    frame["use_accuracy"] = True
    frame["use_timing"] = True
    report: list[Exclusion] = []

    # 1. Session level.
    incomplete = incomplete_participants(frame, conditions)
    mask = frame["participant_id"].astype(str).isin(incomplete)
    report.append(
        Exclusion(
            "incomplete_session",
            "accuracy",
            "participant",
            int(mask.sum()),
            tuple(sorted(incomplete)),
            f"did not finish two sessions of {SCORED_TASKS} answers each",
        )
    )
    frame.loc[mask, ["use_accuracy", "use_timing"]] = False

    # 2. Too fast to have been read. A null duration is NOT fast -- it is unknown -- and must never
    # be swept in here; nulls are handled by invalid_timing.
    fast = (
        frame["use_accuracy"] & frame["duration_ms"].notna() & (frame["duration_ms"] < MIN_TASK_MS)
    )
    report.append(
        Exclusion(
            "too_fast",
            "accuracy",
            "session:task",
            int(fast.sum()),
            _row_ids(frame, fast),
            f"answered in under {MIN_TASK_MS} ms",
        )
    )
    frame.loc[fast, ["use_accuracy", "use_timing"]] = False

    # 3. No trustworthy duration: absent, or flagged (a reload reset the browser clock).
    invalid = frame["use_timing"] & (
        frame["duration_ms"].isna() | frame["duration_invalid"].notna()
    )
    report.append(
        Exclusion(
            "invalid_timing",
            "timing",
            "session:task",
            int(invalid.sum()),
            _row_ids(frame, invalid),
            "no usable browser duration; accuracy kept",
        )
    )
    frame.loc[invalid, "use_timing"] = False

    # 4. Walked away. POOLED across conditions: a per-condition trim removes a different number of
    # rows from each condition and can manufacture a difference on its own.
    timed = frame.loc[frame["use_timing"], "duration_ms"]
    cutoff = float(timed.quantile(TOP_TRIM_QUANTILE)) if len(timed) else float("inf")
    slow = frame["use_timing"] & (frame["duration_ms"] > cutoff)
    report.append(
        Exclusion(
            "top_one_percent",
            "timing",
            "session:task",
            int(slow.sum()),
            _row_ids(frame, slow),
            f"duration above the pooled 99th percentile ({cutoff:.0f} ms); accuracy kept",
        )
    )
    frame.loc[slow, "use_timing"] = False

    # Reported only.
    degraded = conditions.loc[conditions["degraded"], "session_id"].astype(str)
    report.append(
        Exclusion(
            "degraded_session",
            "report",
            "session",
            int(frame["session_id"].isin(set(degraded)).sum()),
            tuple(sorted(degraded)),
            "logged through a database outage; re-run timing analyses without these",
        )
    )
    return frame, report


def _row_ids(frame: pd.DataFrame, mask: pd.Series) -> tuple[str, ...]:
    selected = frame.loc[mask]
    return tuple(
        f"{s}:{t}" for s, t in zip(selected["session_id"], selected["task_id"], strict=True)
    )
