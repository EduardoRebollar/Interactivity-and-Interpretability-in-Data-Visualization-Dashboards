"""The descriptive numbers `docs/study-design.md` section 7 asks for, and nothing more.

Per condition: accuracy (the RQ1 primary outcome over T1-T6, as the mean of per-participant
proportions, a skip scored incorrect), the pre-registered secondaries (skips excluded; adjacent-band
credit on the crossing item) and sensitivity (without those who had heard about the study), skip
counts, accuracy item by item, Paas mental effort (RQ3) with a7 beside it, the survey (a1-a9; b1-b4
after the interactive condition; the comparison c1-c3 after the second), and time on task. Plus the
exclusion table section 7 requires, and About you, which describes the sample. Inferential tests
are deliberately absent: they belong in the analysis notebook, run once, on the frames this package
produces.

T1 is scored by rubric (section 7). A participant whose T1 is not yet coded has no RQ1 proportion
for that condition, so the accuracy tables count only fully scored participants, and the report says
how many T1 answers still wait for coders.
"""

from __future__ import annotations

import pandas as pd

from analysis.exclusions import Exclusion
from src import tasks as study_tasks


def _per_participant(usable: pd.DataFrame) -> pd.Series:
    """Each participant's proportion correct per condition, left out while their T1 is uncoded."""
    from analysis.reshape import proportion_if_coded

    grouped = usable.groupby(["condition", "participant_id"])["correct"]
    return grouped.agg(proportion_if_coded).dropna().rename("prop_correct")


def accuracy(tasks: pd.DataFrame) -> pd.DataFrame:
    """Proportion correct over T1-T6 per participant per condition, summarised by condition."""
    usable = tasks[tasks["use_accuracy"]]
    return _per_participant(usable).groupby("condition").agg(["count", "mean", "std"])


WORD_OF_MOUTH_TITLE = "Accuracy, sensitivity: RQ1 without participants who had heard (E1 Yes)"
CONTROLS_TITLE = "Chart controls b1-b4 (1-7), interactive condition; b4 is hover"


def word_of_mouth(tasks: pd.DataFrame, participants: pd.DataFrame | None) -> pd.DataFrame:
    """Sensitivity, pre-registered (section 7, 2026-10-13): the RQ1 primary without every
    participant who answered E1 "Yes", beside the primary itself, by condition.

    "Not sure", a skip and no About-you record stay in. The two rows' counts differ by the
    participants the rule took out; how many gave each answer is in the About-you table.
    """
    usable = tasks[tasks["use_accuracy"]]
    heard: set[str] = set()
    if participants is not None and study_tasks.HEARD_KEY in participants:
        said_yes = participants[study_tasks.HEARD_KEY] == study_tasks.HEARD_YES
        heard = set(participants.loc[said_yes, "participant_id"].astype(str))
    kept = usable[~usable["participant_id"].astype(str).isin(heard)]
    analyses = {"primary": usable, "without E1 Yes": kept}
    return pd.concat(
        {
            name: _per_participant(rows).groupby("condition").agg(["count", "mean", "std"])
            for name, rows in analyses.items()
        },
        names=["analysis"],
    )


def accuracy_answered(tasks: pd.DataFrame) -> pd.DataFrame:
    """Secondary: proportion correct among ANSWERED items only, skips excluded (section 7)."""
    usable = tasks[tasks["use_accuracy"] & ~tasks["skipped_answer"].astype(bool)]
    return _per_participant(usable).groupby("condition").agg(["count", "mean", "std"])


def uncoded(tasks: pd.DataFrame) -> pd.DataFrame:
    """T1 answers the rubric coders have not scored yet, by condition. Zero before RQ1 is read."""
    usable = tasks[tasks["use_accuracy"] & (tasks["kind"] == "describe")]
    return usable.groupby("condition").agg(
        answers=("task_id", "count"), uncoded=("correct", lambda c: int(c.isna().sum()))
    )


def by_item(tasks: pd.DataFrame) -> pd.DataFrame:
    """Proportion correct and median time per item, chart type and condition. DESCRIPTIVE ONLY.

    Each item pairs one chart type with one affordance (section 4), so this is where an effect can
    be traced to an affordance. But each chart type carries one item per form, so a per-item
    difference is never a powered result and is not tested (section 7).
    """
    usable = tasks[tasks["use_accuracy"]]
    return usable.groupby(["task_id", "chart", "kind", "condition"]).agg(
        n=("task_id", "count"),
        # Over coded answers: an uncoded T1 is neither right nor wrong yet.
        correct=("correct", "mean"),
        median_ms=("duration_ms", "median"),
    )


def skips(tasks: pd.DataFrame) -> pd.DataFrame:
    """How many answers and justifications were skipped, by condition. Reported with accuracy."""
    usable = tasks[tasks["use_accuracy"]]
    return usable.groupby("condition")[["skipped_answer", "skipped_justification"]].sum()


def _rated(conditions: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    return conditions[conditions["participant_id"].astype(str).isin(included)]


def survey(conditions: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    """a1-a9 (1-7), descriptively, by condition (section 6.1). Never tested."""
    from analysis.reshape import LIKERT_KEYS

    rated = _rated(conditions, included)
    columns = [key for key in LIKERT_KEYS if key in rated]
    table = rated.groupby("condition")[columns].agg(["count", "mean", "std"]).T
    return table.rename_axis(["item", "statistic"])


def controls(conditions: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    """b1-b4 (1-7), asked after the interactive condition only, descriptively. b4 is the only
    record of hover (section 7)."""
    from analysis.reshape import CONTROLS_KEYS

    rated = _rated(conditions, included)
    rated = rated[rated["condition"] == "interactive"]
    columns = [key for key in CONTROLS_KEYS if key in rated]
    table = rated[columns].apply(pd.to_numeric, errors="coerce").agg(["count", "mean", "std"])
    return table.rename_axis("statistic")


def comparison(conditions: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    """c1 and c2 counted by answer, and how many wrote c3, after the second condition only."""
    rated = _rated(conditions, included)
    second = rated[rated["condition_order"].astype(int) == 2]
    rows = []
    for key in study_tasks.COMPARISON_CHOICES:
        given = second[key] if key in second else pd.Series(dtype=object)
        for option in (*study_tasks.COMPARISON_OPTIONS, None):
            n = int(given.isna().sum()) if option is None else int((given == option).sum())
            rows.append({"item": key, "answer": option or "(skipped)", "n": n})
    text = study_tasks.COMPARISON_TEXT_KEY
    written = int(second[text].notna().sum()) if text in second else 0
    rows.append(
        {"item": text, "answer": "(written; read the text in conditions.csv)", "n": written}
    )
    return pd.DataFrame(rows).set_index(["item", "answer"])


def about_you(participants: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    """The sample, from About you (section 6.2): each answer's count, and the age in years as a
    summary. The text beside "Other" is left to participants.csv, and so is E2's and E3's: for
    those only how many wrote something is counted, so no typed text reaches the report."""
    from analysis.reshape import DEMOGRAPHIC_COLUMNS

    answered = participants[participants["participant_id"].astype(str).isin(included)]
    written = {q.key for q in study_tasks.ABOUT_QUESTIONS if q.kind == "text"}
    rows = []
    for column in DEMOGRAPHIC_COLUMNS:
        if column.endswith("_other"):
            continue
        values = answered[column]
        if column in written:
            given = int(values.notna().sum())
            read_it = "(written; read the text in participants.csv)"
            rows.append({"question": column, "answer": read_it, "n": given})
            rows.append({"question": column, "answer": "(skipped)", "n": len(values) - given})
            continue
        if column == "age":
            years = pd.to_numeric(values, errors="coerce").dropna()
            if len(years):
                summary = f"{int(years.median())} (range {int(years.min())}-{int(years.max())})"
                rows.append({"question": column, "answer": f"median {summary}", "n": len(years)})
            values = values[pd.to_numeric(values, errors="coerce").isna()]
        for answer, n in values.fillna("(skipped)").value_counts().sort_index().items():
            rows.append({"question": column, "answer": answer, "n": int(n)})
    frame = pd.DataFrame(rows, columns=["question", "answer", "n"])
    return frame.set_index(["question", "answer"])


def overload(tasks: pd.DataFrame) -> pd.DataFrame:
    """Secondary, pre-registered: T1, the overloaded item, on its own (section 7, 2026-10-12).

    Per condition: proportion correct (over coded answers) and median time on T1; and, from the
    interactive condition's log, how many participants used each of T1's four extra controls and
    how often. Descriptive only: on T1 the overload and interactivity cannot be told apart, so a
    difference between conditions is the overloaded interface's, never interactivity's alone.
    T1 still counts in RQ1.
    """
    from analysis.reshape import EXTRA_COLUMNS

    t1 = tasks[tasks["use_accuracy"] & tasks["task_id"].isin(study_tasks.EXTRA_CONTROL_ITEMS)]
    # Over coded answers only: an uncoded T1 is neither right nor wrong yet.
    t1 = t1.assign(correct=t1["correct"].astype("Float64"))
    table = t1.groupby("condition").agg(n=("task_id", "count"), correct=("correct", "mean"))
    timed = tasks[tasks["use_timing"] & tasks["task_id"].isin(study_tasks.EXTRA_CONTROL_ITEMS)]
    table["median_ms"] = timed.groupby("condition")["duration_ms"].median()
    counts = {"used_any": t1[t1[EXTRA_COLUMNS].sum(axis=1) > 0]}
    counts.update({f"{column}_users": t1[t1[column] > 0] for column in EXTRA_COLUMNS})
    for name, rows in counts.items():
        table[name] = rows.groupby("condition")["participant_id"].nunique()
        table[name] = table[name].fillna(0).astype(int)
    for column in EXTRA_COLUMNS:
        table[f"{column}_total"] = t1.groupby("condition")[column].sum().astype(int)
    return table


def crossing_adjacent(tasks: pd.DataFrame) -> pd.DataFrame:
    """Secondary: the crossing item (T6) under strict and adjacent-band scoring (section 7)."""
    crossings = tasks[tasks["use_accuracy"] & (tasks["kind"] == "crossing")]
    scored = crossings.assign(
        correct=crossings["correct"].astype(float),
        correct_adjacent=crossings["correct_adjacent"].astype(float),
    )
    return scored.groupby(["condition", "task_id"])[["correct", "correct_adjacent"]].agg(
        ["count", "mean"]
    )


def mental_effort(conditions: pd.DataFrame, included: set[str]) -> pd.DataFrame:
    """Paas (1-9), RQ3's measure, by condition, with a7 (1-7, "a lot of mental effort") beside it,
    never in its place (section 7)."""
    rated = _rated(conditions, included)
    columns = ["paas", *(["a7"] if "a7" in rated else [])]
    return rated.groupby("condition")[columns].agg(["count", "mean", "std"])


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


def render(
    tasks: pd.DataFrame,
    conditions: pd.DataFrame,
    exclusions: list[Exclusion],
    participants: pd.DataFrame | None = None,
) -> str:
    included = set(tasks.loc[tasks["use_accuracy"], "participant_id"].astype(str))
    sections = [
        ("Exclusions (study-design.md section 7)", exclusion_table(exclusions)),
        ("T1 written answers awaiting the rubric coders", uncoded(tasks)),
        ("Accuracy, RQ1 primary: proportion correct per participant, T1-T6", accuracy(tasks)),
        ("Accuracy, secondary: answered items only, skips excluded", accuracy_answered(tasks)),
        (WORD_OF_MOUTH_TITLE, word_of_mouth(tasks, participants)),
        ("Crossing item, secondary: strict vs adjacent-band credit", crossing_adjacent(tasks)),
        ("T1, the overloaded item, secondary: accuracy, time, extra controls", overload(tasks)),
        ("Skipped answers and justifications", skips(tasks)),
        ("Accuracy and time by item and chart type (descriptive, not tested)", by_item(tasks)),
        ("Mental effort, RQ3: Paas 1-9, with a7 beside it", mental_effort(conditions, included)),
        ("Survey a1-a9 (1-7), descriptive", survey(conditions, included)),
        (CONTROLS_TITLE, controls(conditions, included)),
        ("Comparing the two versions, c1-c3, second condition", comparison(conditions, included)),
        ("Time on task (ms), timing-usable rows only", time_on_task(tasks)),
    ]
    if participants is not None:
        sections.append(("About you: the sample", about_you(participants, included)))
    parts = []
    with pd.option_context("display.width", 120, "display.max_columns", 20):
        for title, frame in sections:
            parts.append(f"{title}\n{'-' * len(title)}\n{frame.to_string()}\n")
    return "\n".join(parts)
