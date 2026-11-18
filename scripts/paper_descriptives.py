"""The paper's exploratory descriptives: `paper/exploratory.md`, items 1 to 7.

Everything here is post hoc and descriptive. The confirmatory tests ran once, on 2026-11-11, and
their output is `data/study_logs/derived/significance.txt`. This script runs no test, and nothing
it writes may be called significant. For the main analysis (participant 19 reinstated, n = 24) and
as pre-registered (n = 23) it computes the items `paper/exploratory.md` defines:

    1  the section 7 and section 10 descriptives, and the scores the tests ran on
    2  who has no usable time in a condition, and why
    3  T1's rubric part by part, by condition and by form
    4  Paas against a7, and any participant whose pattern looks like a reversed Paas scale
    5  Paas and a7 by order
    6  c1 against each participant's own accuracy difference
    7  how many codes the grading review changed, and the rules the decision log gained

From `notebooks/significance.py` it takes `reinstate()`, `participant_scores()`, `ceiling()`,
`check_reinstated_coded()` and constants, never a test: `tests/test_paper_descriptives.py` runs it
with every test function trapped. Before writing anything it checks itself against the run:
- each outcome's n and the ceiling counts against `significance.txt`;
- the exclusion flags it re-derives against `tasks.csv`;
- T1's verdicts against `tasks.csv`;
- the reviewed coding sheets against the verdicts and `depth.csv` that scoring used.
On any mismatch it writes nothing.

Free text never reaches an output. T1 descriptions, justifications, c3, E2, E3 and the "Other"
boxes are replaced by a marker as the files are read, so only whether something was written
survives. The outputs go to `data/study_logs/derived/paper/` (participant data, gitignored), and
the `README.txt` written beside them says what each file holds.

Usage:
    uv run python scripts/paper_descriptives.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import coding, exclusions  # noqa: E402
from analysis import report as study_report  # noqa: E402
from src import config  # noqa: E402
from src import tasks as study_tasks  # noqa: E402

DERIVED = config.STUDY_LOGS_DIR / "derived"
CODING = config.STUDY_LOGS_DIR / "coding"
NOTEBOOK = ROOT / "notebooks" / "significance.py"
GRADING_RULES = ROOT / "docs" / "grading-rules.md"

MAIN, PREREGISTERED = "main", "preregistered"
CONDITIONS = ("static", "interactive")
FLAGS = ["use_accuracy", "use_timing"]
# Read as booleans from the CSVs; anything else means the file is not the one expected.
BOOL_COLUMNS = {
    "tasks.csv": ("use_accuracy", "use_timing", "skipped_answer"),
    "conditions.csv": ("ended", "degraded"),
}
# Read as strings, as notebooks/significance.py reads them, so the frames are the ones it tested.
ID_COLUMNS = ("participant_id", "session_id", "unit_id")
ZERO = 1e-9  # differences of proportions are multiples of 1/6: anything smaller is zero

# --- Free text (paper/exploratory.md, rules) ----------------------------------------------------
# `answer` is free text on the written item, T1, only. On every other item it is the option
# chosen, which section 10's T6 table reads, so it is kept there.
TEXT_MARKER = "[text]"
TASK_TEXT = ("justification",)
WRITTEN_ANSWER = "answer"
CONDITION_TEXT = (study_tasks.COMPARISON_TEXT_KEY,)
PARTICIPANT_TEXT = tuple(
    column
    for question in study_tasks.ABOUT_QUESTIONS
    for column in (
        *([question.key] if question.kind == "text" else []),
        *([question.other_key] if question.other_key else []),
    )
)
# No output may carry a column of these names, masked or not.
FREE_TEXT_COLUMNS = frozenset(
    {"answer", "justification", "description", "draft_note", *CONDITION_TEXT, *PARTICIPANT_TEXT}
)

# --- Item 4's cut-offs (paper/exploratory.md) ---------------------------------------------------
# Every a7 point is labelled, so 5 or more is agreement and 3 or less disagreement. Paas is worded
# only at its ends, so a rating counts as low or high two points from its middle, 5.
PAAS_POINTS, A7_POINTS = 9, study_tasks.LIKERT_POINTS
PAAS_HIGH, PAAS_LOW = 7, 3
A7_AGREE, A7_DISAGREE = 5, 3
CHANGES = ("lower", "same", "higher")

# --- significance.txt, as notebooks/significance.py's main() prints it --------------------------
BANNERS = {MAIN: "MAIN: with participant", PREREGISTERED: "AS PRE-REGISTERED: without participant"}
LABEL_WIDTH = 44  # render(): f"{label:<44}{n:>3}  ..."
ROW = re.compile(
    r"^\s*(?P<n>\d+)\s+(?P<effect>x?[+-]?\d+\.\d+)\s+"
    r"\[(?P<low>[+-]?\d+\.\d+),\s*(?P<high>[+-]?\d+\.\d+)\]\s+"
    r"(?P<t>-?\d+\.\d+)\s+\((?P<df>\d+)\)\s+(?P<p>\S+)\s+(?P<holm>\S+)\s+"
    r"(?P<wilcoxon>\S+)\s+(?P<dz>-?\d+\.\d+|nan)\s*$"
)
BANNER_N = re.compile(r": n = (\d+)\s*$")
CEILING = re.compile(
    r"All items right \(ceiling\): static (\d+) of (\d+), interactive (\d+) of (\d+)"
)
# The lines printed after the tables, each read as printed (strings), for paper/numbers.tex.
SIGNED = r"[+-]?\d+\.\d+"
LINES = {
    "tost": re.compile(
        rf"^Accuracy equivalence \(TOST, bound \+/-(?P<bound>{SIGNED}) = (?P<items>\d+) item of "
        rf"(?P<of>\d+)\): 90% CI \[(?P<low>{SIGNED}), (?P<high>{SIGNED})\], p = (?P<p>\S+) -> "
        r"(?P<verdict>.+?)\s*$"
    ),
    "items": re.compile(
        rf"^In items out of (?P<of>\d+): (?P<est>{SIGNED}) "
        rf"\[(?P<low>{SIGNED}), (?P<high>{SIGNED})\]"
    ),
    "permutation": re.compile(
        r"^Accuracy permutation check \((?P<reps>[\d,]+) re-deals of order\): p = (?P<p>\S+)"
    ),
    "cells": re.compile(r"^Cells \(interactive half-form\): \{(?P<cells>[^}]*)\}"),
    "effects": re.compile(
        rf"^Half effect \(descriptive\): (?P<half>{SIGNED}); form effect \(descriptive\): "
        rf"(?P<form>{SIGNED});"
    ),
    "rq3": re.compile(
        r"^RQ3 'rather than' .*: Paas falls (?P<falls>yes|no), accuracy equivalent "
        r"(?P<equivalent>yes|no) -> (?P<verdict>supported|not supported)\s*$"
    ),
    "degraded": re.compile(r"^Degraded sessions \(logger spooled\): (?P<n>\d+)"),
}
CELL = re.compile(r"'(?P<cell>[^']+)': (?P<n>\d+)")

# --- Item 6 -----------------------------------------------------------------------------------
SKIPPED = "(skipped)"
DIRECTIONS = ("interactive higher", "equal", "static higher")

# --- Item 7 -----------------------------------------------------------------------------------
RUBRIC, RQ2 = "T1 rubric", "RQ2"
DROPPED_CODE = "notes_uncertainty"  # docs/grading-rules.md section 1, item 5
DECISION_LOG_HEADING = "## 8. Decision log"
DECISION_LOG_HEADER = ("Date", "Sheet", "The case", "Rule added", "Answers re-checked")
WRITTEN_TASKS = frozenset(
    task.task_id
    for form in study_tasks.FORMS
    for task in study_tasks.for_form(form)
    if task.kind == coding.WRITTEN_KIND
)


class PaperError(RuntimeError):
    """The inputs disagree with the run they must describe, so nothing is written."""


# --- The notebook, for its scores and never its tests -------------------------------------------
_NOTEBOOK: ModuleType | None = None


def load_notebook(path: Path = NOTEBOOK) -> ModuleType:
    """`notebooks/significance.py` as a module, loaded once, by path, as
    `tests/test_significance.py` loads it. Only `reinstate()`, `participant_scores()`,
    `ceiling()`, `check_reinstated_coded()` and constants are used here."""
    global _NOTEBOOK
    if _NOTEBOOK is None:
        loaded = sys.modules.get("significance")
        if loaded is not None and Path(getattr(loaded, "__file__", "")).resolve() == path.resolve():
            _NOTEBOOK = loaded
        else:
            spec = importlib.util.spec_from_file_location("significance", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["significance"] = module  # its dataclasses look their module up here
            spec.loader.exec_module(module)
            _NOTEBOOK = module
    return _NOTEBOOK


# --- Reading, with the free text masked ---------------------------------------------------------
def read_csv(path: Path) -> pd.DataFrame:
    """A pipeline CSV. Only an empty cell is missing: by default pandas also reads typed text
    such as "N/A" or "None" as missing, which would count a participant who wrote it as one who
    skipped. pandas writes a missing value as an empty cell, so the numbers read the same."""
    if not path.exists():
        raise PaperError(f"{path} is missing")
    columns = pd.read_csv(path, nrows=0).columns
    return pd.read_csv(
        path,
        dtype={c: str for c in ID_COLUMNS if c in columns},
        keep_default_na=False,
        na_values=[""],
    )


def mask(frame: pd.DataFrame, columns, rows: pd.Series | None = None) -> pd.DataFrame:
    """Every written value in `columns` (on `rows`, if given) replaced by the marker. A blank stays
    blank, so the counts of who wrote something are unchanged."""
    out = frame.copy()
    for column in columns:
        if column not in out:
            continue
        written = out[column].notna()
        if rows is not None:
            written &= rows
        out[column] = out[column].astype(object)
        out.loc[written, column] = TEXT_MARKER
    return out


def _require_bool(frame: pd.DataFrame, name: str) -> None:
    for column in BOOL_COLUMNS[name]:
        if column not in frame or frame[column].dtype != bool:
            raise PaperError(f"{name}: {column} is not a column of booleans")


@dataclass(frozen=True)
class Inputs:
    tasks: pd.DataFrame  # tasks.csv, the pre-registered exclusions marked
    conditions: pd.DataFrame
    participants: pd.DataFrame
    depth: pd.DataFrame  # coding/depth.csv: every coded unit, participant 19's included
    verdicts: pd.DataFrame  # coding/rubric_verdicts.csv
    significance: dict[str, dict]
    rules_text: str  # docs/grading-rules.md
    coding_dir: Path


def load_inputs(
    derived: Path, coding_dir: Path, significance: Path, rules: Path, labels: dict[str, str]
) -> Inputs:
    tasks = read_csv(derived / "tasks.csv")
    tasks = mask(tasks, TASK_TEXT)
    tasks = mask(tasks, (WRITTEN_ANSWER,), rows=tasks["kind"] == coding.WRITTEN_KIND)
    conditions = mask(read_csv(derived / "conditions.csv"), CONDITION_TEXT)
    participants = mask(read_csv(derived / "participants.csv"), PARTICIPANT_TEXT)
    _require_bool(tasks, "tasks.csv")
    _require_bool(conditions, "conditions.csv")
    for path in (significance, rules):
        if not path.exists():
            raise PaperError(f"{path} is missing")
    return Inputs(
        tasks=tasks,
        conditions=conditions,
        participants=participants,
        depth=read_csv(coding_dir / "depth.csv"),
        verdicts=read_csv(coding_dir / "rubric_verdicts.csv"),
        significance=parse_significance(
            significance.read_text(encoding="utf-8", errors="replace"), labels
        ),
        rules_text=rules.read_text(encoding="utf-8"),
        coding_dir=coding_dir,
    )


# --- significance.txt -----------------------------------------------------------------------
def parse_significance(text: str, labels: dict[str, str]) -> dict[str, dict]:
    """Both analyses in `significance.txt`: each one's n, its outcome rows as printed, its ceiling
    counts, and the lines printed after the tables (`LINES`: the equivalence test, accuracy in
    items, the permutation check, the cells, the half and form effects, RQ3's "rather than" and
    the degraded sessions), all as printed. An outcome the run could not compute reads None; a line
    it did not print is absent. Refuses a file without both analyses, since every check needs
    both."""
    by_label = {label: key for key, label in labels.items()}
    blocks: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        started = next((name for name, b in BANNERS.items() if line.startswith(b)), None)
        if started:
            current = started
            blocks[current] = [line]
        elif current:
            blocks[current].append(line)
    if set(blocks) != set(BANNERS):
        raise PaperError("significance.txt does not hold both analyses")
    parsed = {}
    for name, lines in blocks.items():
        banner_n = BANNER_N.search(lines[0])
        outcomes: dict[str, dict[str, str] | None] = {}
        ceiling = None
        printed: dict[str, dict[str, str]] = {}
        for line in lines[1:]:
            label = line[:LABEL_WIDTH].rstrip()
            if label in by_label:
                if "not available" in line:
                    outcomes[by_label[label]] = None
                    continue
                match = ROW.match(line[LABEL_WIDTH:])
                if match is None:
                    raise PaperError(f"significance.txt: cannot read the row {line.strip()!r}")
                outcomes[by_label[label]] = match.groupdict()
            elif found := CEILING.search(line):
                ceiling = {
                    "static": (int(found[1]), int(found[2])),
                    "interactive": (int(found[3]), int(found[4])),
                }
            for key, pattern in LINES.items():
                if found := pattern.search(line):
                    printed[key] = found.groupdict()
        if "cells" in printed:
            cells = CELL.findall(printed["cells"]["cells"])
            printed["cells"] = {cell: n for cell, n in cells}
        parsed[name] = {
            "n": int(banner_n[1]) if banner_n else None,
            "outcomes": outcomes,
            "ceiling": ceiling,
            "lines": printed,
        }
    return parsed


# --- The two analyses ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Analysis:
    name: str
    tasks: pd.DataFrame  # use_accuracy and use_timing as this analysis's rules set them
    conditions: pd.DataFrame
    exclusions: tuple[exclusions.Exclusion, ...]
    scores: pd.DataFrame  # notebooks/significance.py participant_scores()

    @property
    def included(self) -> set[str]:
        return set(self.tasks.loc[self.tasks["use_accuracy"], "participant_id"].astype(str))

    def own_conditions(self) -> pd.DataFrame:
        """This analysis's sessions for its own participants, as analysis/report.py rates them."""
        keep = self.conditions["participant_id"].astype(str).isin(self.included)
        return self.conditions[keep]


def build_analyses(inputs: Inputs, sig: ModuleType) -> dict[str, Analysis]:
    """The main analysis (participant 19 reinstated) and the analysis as pre-registered."""
    bare = inputs.tasks.drop(columns=FLAGS)
    rederived, preregistered_report = exclusions.apply(bare, inputs.conditions)
    for column in FLAGS:
        differ = rederived[column].to_numpy() != inputs.tasks[column].to_numpy()
        if differ.any():
            raise PaperError(
                f"tasks.csv's {column} differs from what the pre-registered rules give on "
                f"{int(differ.sum())} rows: re-run scripts/score_study.py"
            )
    main_tasks, main_conditions = sig.reinstate(inputs.tasks, inputs.conditions)
    sig.check_reinstated_coded(main_tasks, inputs.depth)
    # reinstate() re-runs the rules and keeps only the frame. The same call again gives the
    # exclusion table it discards, and must mark the same rows.
    again, main_report = exclusions.apply(main_tasks.drop(columns=FLAGS), main_conditions)
    for column in FLAGS:
        if (again[column].to_numpy() != main_tasks[column].to_numpy()).any():
            raise PaperError("re-running the rules on the reinstated frame marks other rows")
    analyses = {}
    for name, frame, conditions, report in (
        (MAIN, main_tasks, main_conditions, main_report),
        (PREREGISTERED, inputs.tasks, inputs.conditions, preregistered_report),
    ):
        scores = sig.participant_scores(frame, conditions, inputs.depth, inputs.participants)
        analyses[name] = Analysis(name, frame, conditions, tuple(report), scores)
    return analyses


def paired(scores: pd.DataFrame, column: str) -> pd.DataFrame:
    """Per participant with a score in both conditions: static, interactive and d, interactive
    minus static. The participants notebooks/significance.py's differences() keeps."""
    wide = scores.pivot(index="participant_id", columns="condition", values=column)
    wide = wide.reindex(columns=list(CONDITIONS)).astype(float).dropna()
    return wide.assign(d=wide["interactive"] - wide["static"])


def check_against_run(analyses: dict[str, Analysis], run: dict[str, dict], sig: ModuleType) -> None:
    """Each analysis's n, n per outcome, and ceiling counts, against significance.txt."""
    problems = []
    for name, analysis in analyses.items():
        printed = run[name]
        n = analysis.scores["participant_id"].nunique()
        if printed["n"] != n:
            problems.append(f"{name}: n = {n} here, {printed['n']} in the run")
        for outcome, row in printed["outcomes"].items():
            ours = len(paired(analysis.scores, outcome)) if outcome in analysis.scores else None
            theirs = None if row is None else int(row["n"])
            if ours != theirs:
                problems.append(f"{name}: {outcome} has n = {ours} here, {theirs} in the run")
        ceiling = {c: tuple(v) for c, v in sig.ceiling(analysis.scores).items()}
        if printed["ceiling"] != ceiling:
            problems.append(f"{name}: ceiling {ceiling} here, {printed['ceiling']} in the run")
    if problems:
        raise PaperError("does not match significance.txt: " + "; ".join(problems))


def _first(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return frame[[column, *[c for c in frame.columns if c != column]]]


def _summary(**labels) -> dict[str, object]:
    """n, mean, SD and median of `values`, beside the labels given."""
    values = labels.pop("values")
    return {
        **labels,
        "n": len(values),
        "mean": values.mean(),
        "sd": values.std(),
        "median": values.median(),
    }


# --- Item 1 -------------------------------------------------------------------------------------
SCORE_OUTCOMES = (
    "accuracy",
    "accuracy_answered",
    "accuracy_no_heard",
    "t1_parts",
    "log_time",
    "paas",
    "depth",
    "cites_values",
    "compares_series",
    "depth_with_t1",
)


def _title(analysis: Analysis) -> str:
    who = ", ".join(exclusions.REINSTATED)
    n = analysis.scores["participant_id"].nunique()
    if analysis.name == MAIN:
        return (
            f"Main analysis: participant {who} reinstated (their empty session dropped, every "
            f"exclusion rule re-run in order), n = {n}"
        )
    return f"As pre-registered: the exclusion rules as written, without participant {who}, n = {n}"


def report_text(analysis: Analysis, participants: pd.DataFrame) -> str:
    """analysis/report.py's render(), the tables of report_section10.txt, for one analysis."""
    lines = [
        _title(analysis),
        "Post hoc and descriptive (paper/exploratory.md, item 1): no test, interval or p-value;",
        "nothing here may be called significant. The tables are analysis/report.py's render().",
    ]
    if analysis.name == PREREGISTERED:
        who = ", ".join(exclusions.REINSTATED)
        lines.append(
            f"Its windows table, as in report_section10.txt, counts every participant with a row, "
            f"participant {who} included; windows.csv counts this analysis's own."
        )
    body = study_report.render(
        analysis.tasks, analysis.conditions, list(analysis.exclusions), participants
    )
    return "\n".join([*lines, "", body])


def windows(analyses: dict[str, Analysis]) -> pd.DataFrame:
    """The windows table, over each analysis's own participants."""
    frames = []
    for name, analysis in analyses.items():
        own = analysis.tasks[analysis.tasks["participant_id"].astype(str).isin(analysis.included)]
        frames.append(study_report.windows(own).assign(analysis=name))
    return _first(pd.concat(frames, ignore_index=True), "analysis")


def scores_table(analyses: dict[str, Analysis]) -> pd.DataFrame:
    """Each participant's scores per condition, the frame the tests ran on. time_s is the
    participant's geometric mean time per task, in seconds."""
    frames = [
        a.scores.assign(time_s=np.exp(a.scores["log_time"]), analysis=name)
        for name, a in analyses.items()
    ]
    return _first(pd.concat(frames, ignore_index=True), "analysis")


def scores_summary(analyses: dict[str, Analysis]) -> pd.DataFrame:
    """Per outcome and condition: n, mean, SD and median. time_s is time in seconds: its mean is
    the geometric mean, exp(mean log_time), its median exp(median log_time), and it has no SD
    (log_time's is on the log scale)."""
    rows = []
    for name, analysis in analyses.items():
        for outcome in (o for o in SCORE_OUTCOMES if o in analysis.scores):
            for condition in CONDITIONS:
                mine = analysis.scores["condition"] == condition
                values = analysis.scores.loc[mine, outcome].astype(float).dropna()
                labels = {"analysis": name, "condition": condition}
                rows.append(_summary(**labels, outcome=outcome, values=values))
                if outcome == "log_time":
                    rows.append(
                        {
                            **labels,
                            "outcome": "time_s",
                            "n": len(values),
                            "mean": float(np.exp(values.mean())),
                            "sd": float("nan"),
                            "median": float(np.exp(values.median())),
                        }
                    )
    columns = ["analysis", "outcome", "condition", "n", "mean", "sd", "median"]
    return pd.DataFrame(rows)[columns]


def score_differences(analyses: dict[str, Analysis]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each participant's difference, interactive minus static, per outcome (log_time's is a log
    ratio); and per outcome how many are above, at and below zero, and their SD. The effect
    itself is the run's estimate, in significance.txt."""
    summary, each = [], []
    for name, analysis in analyses.items():
        for outcome in (o for o in SCORE_OUTCOMES if o in analysis.scores):
            wide = paired(analysis.scores, outcome)
            d = wide["d"]
            summary.append(
                {
                    "analysis": name,
                    "outcome": outcome,
                    "n": len(d),
                    "above_zero": int((d > ZERO).sum()),
                    "zero": int((d.abs() <= ZERO).sum()),
                    "below_zero": int((d < -ZERO).sum()),
                    "sd": d.std(),
                }
            )
            each.append(
                wide.reset_index().assign(analysis=name, outcome=outcome)[
                    ["analysis", "outcome", "participant_id", "static", "interactive", "d"]
                ]
            )
    return pd.DataFrame(summary), pd.concat(each, ignore_index=True)


# --- Item 2 -------------------------------------------------------------------------------------
REMOVED_COLUMNS = [
    "analysis",
    "participant_id",
    "condition",
    "condition_order",
    "form",
    "task_id",
    "rule",
    "duration_invalid",
    "duration_ms",
    "cutoff_ms",
]


def _rules_by_row(report) -> dict[tuple[str, str], str]:
    """(session, task) -> the rule that took the row out, for the rules that name rows."""
    rules: dict[tuple[str, str], str] = {}
    for exclusion in report:
        if exclusion.unit != "session:task":
            continue
        for row_id in exclusion.ids:
            session, task = row_id.rsplit(":", 1)
            rules.setdefault((session, task), exclusion.rule)
    return rules


def _cutoff_ms(report) -> float:
    """The pooled 99th percentile that top_one_percent cut at, from the rule's reason."""
    for exclusion in report:
        if exclusion.rule == "top_one_percent":
            found = re.search(r"\((\d+) ms\)", exclusion.reason)
            if found:
                return float(found[1])
    return float("nan")


def timing(analyses: dict[str, Analysis]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per participant and condition: the answers, those kept for accuracy, and those with a usable
    time. And every answer kept for accuracy whose time was removed, with the rule that removed it.
    The participants it finds without a time score must be the ones the run left out of time."""
    by_participant, removed = [], []
    for name, analysis in analyses.items():
        rules = _rules_by_row(analysis.exclusions)
        cutoff = _cutoff_ms(analysis.exclusions)
        own = analysis.tasks[analysis.tasks["participant_id"].astype(str).isin(analysis.included)]
        without_time = set()
        for (participant, condition), rows in own.groupby(["participant_id", "condition"]):
            timed = int(rows["use_timing"].sum())
            by_participant.append(
                {
                    "analysis": name,
                    "participant_id": participant,
                    "condition": condition,
                    "condition_order": int(rows["condition_order"].iloc[0]),
                    "form": rows["form"].iloc[0],
                    "answers": len(rows),
                    "kept_for_accuracy": int(rows["use_accuracy"].sum()),
                    "kept_for_timing": timed,
                    "has_time_score": timed > 0,
                }
            )
            if not timed:
                without_time.add(str(participant))
        kept = own[own["use_accuracy"] & ~own["use_timing"]]
        for row in kept.itertuples(index=False):
            rule = rules.get((str(row.session_id), row.task_id))
            if rule is None:
                raise PaperError(f"{name}: no rule explains a time removed on {row.task_id}")
            trimmed = rule == "top_one_percent"
            removed.append(
                {
                    "analysis": name,
                    "participant_id": row.participant_id,
                    "condition": row.condition,
                    "condition_order": int(row.condition_order),
                    "form": row.form,
                    "task_id": row.task_id,
                    "rule": rule,
                    "duration_invalid": row.duration_invalid,
                    "duration_ms": row.duration_ms if trimmed else float("nan"),
                    "cutoff_ms": cutoff if trimmed else float("nan"),
                }
            )
        with_time = set(paired(analysis.scores, "log_time").index.astype(str))
        if (analysis.included - without_time) != with_time:
            raise PaperError(f"{name}: the participants without a time score do not reproduce")
    return pd.DataFrame(by_participant), pd.DataFrame(removed, columns=REMOVED_COLUMNS)


# --- Item 3 -------------------------------------------------------------------------------------
def _truthy(value) -> bool:
    if isinstance(value, str):
        return value == "True"
    return False if pd.isna(value) else bool(value)


def t1_rubric(analyses: dict[str, Analysis], verdicts: pd.DataFrame) -> pd.DataFrame:
    """T1's rubric part by part: per analysis, form (all, A, B) and condition, the share of the
    kept T1 answers credited with each part, contradicting one, and correct. A skipped description
    is credited with no part and contradicts none, as the parts score counts it."""
    table = verdicts.assign(session_id=verdicts["session_id"].astype(str))
    table = table.set_index(["session_id", "task_id"])
    rows = []
    for name, analysis in analyses.items():
        written = analysis.tasks["kind"] == coding.WRITTEN_KIND
        t1 = analysis.tasks[analysis.tasks["use_accuracy"] & written]
        coded = []
        for row in t1.itertuples(index=False):
            key = (str(row.session_id), row.task_id)
            if bool(row.skipped_answer):
                fields, verdict = dict.fromkeys(coding.RUBRIC_FIELDS, 0), False
            elif key in table.index:
                fields = {f: int(table.loc[key, f]) for f in coding.RUBRIC_FIELDS}
                verdict = bool(int(table.loc[key, "correct"]))
            else:
                raise PaperError(f"{name}: a T1 answer has no rubric verdict (session {key[0]})")
            parts = sum(fields[p] for p in coding.RUBRIC_PARTS)
            if pd.isna(row.t1_parts) or parts != int(row.t1_parts):
                raise PaperError(f"{name}: a + b + c is not t1_parts (session {key[0]})")
            if verdict != _truthy(row.correct):
                raise PaperError(
                    f"{name}: the rubric verdict is not tasks.csv's (session {key[0]})"
                )
            coded.append(
                {
                    "condition": row.condition,
                    "form": row.form,
                    "skipped": bool(row.skipped_answer),
                    **fields,
                    "correct": int(verdict),
                }
            )
        frame = pd.DataFrame(coded)
        accuracy = study_report.overload(analysis.tasks)["correct"]
        for form in ("all", "A", "B"):
            of_form = frame if form == "all" else frame[frame["form"] == form]
            for condition in CONDITIONS:
                group = of_form[of_form["condition"] == condition]
                share_correct = group["correct"].mean()
                if form == "all" and not np.isclose(share_correct, accuracy[condition]):
                    raise PaperError(f"{name}: T1's share correct is not T1's accuracy")
                rows.append(
                    {
                        "analysis": name,
                        "form": form,
                        "condition": condition,
                        "n": len(group),
                        "skipped": int(group["skipped"].sum()),
                        **{f"share_{f}": group[f].mean() for f in coding.RUBRIC_FIELDS},
                        "share_correct": share_correct,
                    }
                )
    return pd.DataFrame(rows)


# --- Items 4 and 5 ------------------------------------------------------------------------------
def ratings(analysis: Analysis) -> pd.DataFrame:
    """Paas and a7 for each of this analysis's sessions."""
    own = analysis.own_conditions()
    keys = ["participant_id", "session_id", "condition", "condition_order", "form"]
    out = own[keys].copy()
    out["participant_id"] = out["participant_id"].astype(str)
    out["condition_order"] = out["condition_order"].astype(int)
    for column in ("paas", "a7"):
        out[column] = pd.to_numeric(own[column], errors="coerce")
    if out.duplicated(["participant_id", "condition"]).any():
        raise PaperError(f"{analysis.name}: a participant has two sessions in one condition")
    return out.reset_index(drop=True)


def is_opposed(paas: float, a7: float) -> bool:
    """High on one item and low on the other (paper/exploratory.md, item 4)."""
    return (paas >= PAAS_HIGH and a7 <= A7_DISAGREE) or (paas <= PAAS_LOW and a7 >= A7_AGREE)


def change(d: float) -> str:
    """Interactive against static: lower, same or higher."""
    return "same" if abs(d) <= ZERO else ("higher" if d > 0 else "lower")


def spearman(x, y) -> float:
    """Spearman's rank correlation, tied values given their average rank. The coefficient only."""
    x, y = pd.Series(list(x), dtype=float), pd.Series(list(y), dtype=float)
    if len(x) != len(y):
        raise ValueError("spearman: the two series differ in length")
    if len(x) < 2 or x.nunique() < 2 or y.nunique() < 2:
        return float("nan")
    return float(np.corrcoef(x.rank(), y.rank())[0, 1])


def _person(name: str, participant: str, rows: pd.DataFrame) -> dict[str, object]:
    """One participant's four ratings, whether each pair is opposed, and how the scales moved."""
    by_condition = rows.set_index("condition")
    row: dict[str, object] = {"analysis": name, "participant_id": participant}
    for measure in ("paas", "a7"):
        for condition in CONDITIONS:
            value = by_condition[measure].get(condition, float("nan"))
            row[f"{measure}_{condition}"] = float(value)
    for condition in CONDITIONS:
        paas, a7 = row[f"paas_{condition}"], row[f"a7_{condition}"]
        row[f"opposed_{condition}"] = not (pd.isna(paas) or pd.isna(a7)) and is_opposed(paas, a7)
    row["n_opposed"] = int(row["opposed_static"]) + int(row["opposed_interactive"])
    row["complete"] = not any(pd.isna(row[f"{m}_{c}"]) for m in ("paas", "a7") for c in CONDITIONS)
    if row["complete"]:
        d_paas = row["paas_interactive"] - row["paas_static"]
        d_a7 = row["a7_interactive"] - row["a7_static"]
        row["paas_change"], row["a7_change"] = change(d_paas), change(d_a7)
        row["opposite_moves"] = d_paas * d_a7 < 0
    else:
        row["paas_change"] = row["a7_change"] = None
        row["opposite_moves"] = False
    row["looks_reversed"] = bool(
        row["complete"]
        and (row["n_opposed"] == 2 or (row["n_opposed"] == 1 and row["opposite_moves"]))
    )
    return row


def _paas_a7_one(name: str, analysis: Analysis):
    rated = ratings(analysis)
    both = rated.dropna(subset=["paas", "a7"]).copy()
    both["paas01"] = (both["paas"] - 1) / (PAAS_POINTS - 1)
    both["a701"] = (both["a7"] - 1) / (A7_POINTS - 1)
    both["gap01"] = (both["paas01"] - both["a701"]).abs()
    both["opposed"] = [is_opposed(p, q) for p, q in zip(both["paas"], both["a7"], strict=True)]

    summary = []

    def add(statistic: str, scope: str, value) -> None:
        summary.append({"analysis": name, "statistic": statistic, "scope": scope, "value": value})

    add("pairs_missing_a_rating", "all", len(rated) - len(both))
    for scope in ("all", *CONDITIONS):
        mine = both if scope == "all" else both[both["condition"] == scope]
        add("pairs", scope, len(mine))
        add("spearman", scope, spearman(mine["paas"], mine["a7"]))
        add("opposed_pairs", scope, int(mine["opposed"].sum()))
    for what in ("mean", "median", "min", "max"):
        add(f"gap01_{what}", "all", float(getattr(both["gap01"], what)()))

    people = [_person(name, p, rows) for p, rows in rated.groupby("participant_id")]
    moves = [(r["paas_change"], r["a7_change"]) for r in people if r["complete"]]
    add("participants_with_both_pairs", "all", len(moves))
    add("same_direction", "all", sum(p == a != "same" for p, a in moves))
    add("both_unchanged", "all", sum(p == a == "same" for p, a in moves))
    add("opposite_direction", "all", sum({p, a} == {"lower", "higher"} for p, a in moves))
    add("one_unchanged", "all", sum((p == "same") != (a == "same") for p, a in moves))
    add("looks_reversed", "all", sum(bool(r["looks_reversed"]) for r in people))
    directions = [
        {"analysis": name, "paas_change": p, "a7_change": a, "n": moves.count((p, a))}
        for p in CHANGES
        for a in CHANGES
    ]
    return both.assign(analysis=name), people, directions, summary


def paas_a7(analyses: dict[str, Analysis]) -> dict[str, pd.DataFrame]:
    """Item 4: each pair, each participant, the direction table and a summary."""
    pairs, people, directions, summary = [], [], [], []
    for name, analysis in analyses.items():
        one = _paas_a7_one(name, analysis)
        pairs.append(one[0])
        people += one[1]
        directions += one[2]
        summary += one[3]
    pair_columns = [
        "analysis",
        "participant_id",
        "condition",
        "condition_order",
        "form",
        "paas",
        "a7",
        "paas01",
        "a701",
        "gap01",
        "opposed",
    ]
    return {
        "paas_a7_pairs.csv": pd.concat(pairs, ignore_index=True)[pair_columns],
        "paas_a7_participants.csv": pd.DataFrame(people),
        "paas_a7_direction.csv": pd.DataFrame(directions),
        "paas_a7_summary.csv": pd.DataFrame(summary),
    }


def interactive_first(rated: pd.DataFrame) -> dict[str, bool]:
    """Per participant: whether their interactive half came first."""
    interactive = rated[rated["condition"] == "interactive"]
    orders = zip(interactive["participant_id"], interactive["condition_order"], strict=True)
    return {str(p): int(order) == 1 for p, order in orders}


def paas_a7_by_order(analyses: dict[str, Analysis]) -> dict[str, pd.DataFrame]:
    """Item 5: Paas and a7 by group (interactive first or second) and condition; the difference by
    group; and both ratings by half, whichever condition it held."""
    by_group, by_difference, by_half = [], [], []
    for name, analysis in analyses.items():
        rated = ratings(analysis)
        first = interactive_first(rated)
        rated["group"] = [
            "interactive first" if first.get(p) else "interactive second"
            for p in rated["participant_id"]
        ]
        for measure in ("paas", "a7"):
            for (group, condition), rows in rated.groupby(["group", "condition"]):
                labels = {"analysis": name, "group": group, "condition": condition}
                by_group.append(_summary(**labels, measure=measure, values=rows[measure].dropna()))
            for group, rows in rated.groupby("group"):
                wide = rows.pivot(index="participant_id", columns="condition", values=measure)
                wide = wide.reindex(columns=list(CONDITIONS)).dropna()
                d = wide["interactive"] - wide["static"]
                by_difference.append(
                    {
                        "analysis": name,
                        "group": group,
                        "measure": measure,
                        "n": len(d),
                        "mean": d.mean(),
                        "sd": d.std(),
                    }
                )
            for half, rows in rated.groupby("condition_order"):
                labels = {"analysis": name, "half": int(half)}
                by_half.append(_summary(**labels, measure=measure, values=rows[measure].dropna()))
    return {
        "paas_a7_by_order.csv": pd.DataFrame(by_group),
        "paas_a7_order_differences.csv": pd.DataFrame(by_difference),
        "paas_a7_by_half.csv": pd.DataFrame(by_half),
    }


# --- Item 6 -------------------------------------------------------------------------------------
def _direction(items: float) -> str:
    if items > ZERO:
        return DIRECTIONS[0]
    return DIRECTIONS[1] if abs(items) <= ZERO else DIRECTIONS[2]


def c1_against_accuracy(analyses: dict[str, Analysis], items: int) -> dict[str, pd.DataFrame]:
    """Item 6: each participant's c1 answer beside their accuracy difference in items, the two
    against each other, and the difference within each answer."""
    each, crosstab, by_answer = [], [], []
    answers = (*study_tasks.COMPARISON_OPTIONS, SKIPPED)
    for name, analysis in analyses.items():
        own = analysis.own_conditions()
        second = own[own["condition_order"].astype(int) == 2]
        c1 = dict(zip(second["participant_id"].astype(str), second["c1"], strict=True))
        rows = []
        for participant, d in paired(analysis.scores, "accuracy")["d"].items():
            given = c1.get(str(participant))
            in_items = round(float(d) * items, 9)
            rows.append(
                {
                    "analysis": name,
                    "participant_id": participant,
                    "c1": given if isinstance(given, str) else SKIPPED,
                    "accuracy_difference_items": in_items,
                    "direction": _direction(in_items),
                }
            )
        frame = pd.DataFrame(rows)
        each.append(frame)
        for answer in answers:
            mine = frame[frame["c1"] == answer]
            for direction in DIRECTIONS:
                count = int((mine["direction"] == direction).sum())
                crosstab.append(
                    {"analysis": name, "c1": answer, "direction": direction, "n": count}
                )
            values = mine["accuracy_difference_items"]
            by_answer.append(
                {
                    "analysis": name,
                    "c1": answer,
                    "n": len(values),
                    "mean": values.mean(),
                    "median": values.median(),
                    "min": values.min(),
                    "max": values.max(),
                }
            )
    return {
        "c1_accuracy.csv": pd.concat(each, ignore_index=True),
        "c1_accuracy_crosstab.csv": pd.DataFrame(crosstab),
        "c1_accuracy_by_answer.csv": pd.DataFrame(by_answer),
    }


# --- Item 7 -------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Sheet:
    family: str  # RUBRIC or RQ2
    name: str
    draft: str
    reviewed: str
    key: str
    fields: tuple[str, ...]
    columns: tuple[str, ...]


def review_sheets(reinstated: tuple[str, ...] = exclusions.REINSTATED) -> list[Sheet]:
    """The draft and reviewed sheets: the main ones, and each reinstated participant's own."""
    sheets = []
    whose = [("", "main sheet"), *((f"_p{p}", f"participant {p}") for p in reinstated)]
    for suffix, who in whose:
        sheets.append(
            Sheet(
                RUBRIC,
                f"{RUBRIC}, {who}",
                f"rubric_coder1{suffix}_draft.csv",
                f"rubric_coder1{suffix}.csv",
                f"rubric_key{suffix}.csv",
                tuple(coding.RUBRIC_FIELDS),
                tuple(coding.RUBRIC_SHEET_COLUMNS),
            )
        )
        sheets.append(
            Sheet(
                RQ2,
                f"{RQ2}, {who}",
                f"coder1{suffix}_draft.csv",
                f"coder1{suffix}.csv",
                f"key{suffix}.csv",
                tuple(coding.CODES),
                tuple(coding.SHEET_COLUMNS),
            )
        )
    return sheets


def _scored(sheet: Sheet, uid: str, unit: pd.Series, verdicts, depth) -> pd.Series:
    """The fields scoring used for this unit: rubric_verdicts.csv's or depth.csv's."""
    if sheet.family == RUBRIC:
        key = (str(unit["session_id"]), unit["task_id"])
        if key not in verdicts.index:
            raise PaperError(f"{sheet.reviewed}: unit {uid} is not in rubric_verdicts.csv")
        return verdicts.loc[key]
    if uid not in depth.index:
        raise PaperError(f"{sheet.reviewed}: unit {uid} is not in depth.csv")
    return depth.loc[uid]


def _sheet_units(coding_dir: Path, sheet: Sheet, verdicts, depth) -> list[dict[str, object]]:
    """Each unit's draft and reviewed codes, once the reviewed sheet is shown to be scoring's."""
    draft = coding.read_sheet(coding_dir / sheet.draft, None, sheet.fields, sheet.columns)
    reviewed = coding.read_sheet(coding_dir / sheet.reviewed, None, sheet.fields, sheet.columns)
    if set(draft) != set(reviewed):
        raise PaperError(f"{sheet.draft} and {sheet.reviewed} hold different units")
    key = read_csv(coding_dir / sheet.key).set_index("unit_id")
    if set(reviewed) - set(key.index):
        raise PaperError(f"{sheet.key} does not cover {sheet.reviewed}")
    units = []
    for uid, fields in reviewed.items():
        unit = key.loc[uid]
        used = _scored(sheet, uid, unit, verdicts, depth)
        if any(int(used[f]) != fields[f] for f in sheet.fields):
            raise PaperError(f"{sheet.reviewed} is not the sheet scoring used (unit {uid})")
        units.append(
            {
                "family": sheet.family,
                "sheet": sheet.name,
                "unit_id": uid,
                "condition": unit["condition"],
                "task_id": unit["task_id"],
                **{f"draft_{f}": draft[uid][f] for f in sheet.fields},
                **{f"reviewed_{f}": fields[f] for f in sheet.fields},
            }
        )
    return units


def _scopes(family: str, rows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if family == RUBRIC:
        return {"T1": rows}
    t1 = rows["task_id"].isin(WRITTEN_TASKS)
    return {"all units": rows, "T1 units": rows[t1], "T2-T6 units": rows[~t1]}


def _t1_moves(rows: pd.DataFrame) -> dict[str, int]:
    """How many T1 verdicts and parts scores the review's changes moved."""

    def parts(prefix: str) -> pd.Series:
        return rows[[f"{prefix}{p}" for p in coding.RUBRIC_PARTS]].sum(axis=1)

    def correct(prefix: str) -> pd.Series:
        return (parts(prefix) == len(coding.RUBRIC_PARTS)) & (rows[f"{prefix}contradicts"] == 0)

    before, after = correct("draft_"), correct("reviewed_")
    return {
        "units": len(rows),
        "verdicts_changed": int((before != after).sum()),
        "to_correct": int((~before & after).sum()),
        "to_incorrect": int((before & ~after).sum()),
        "parts_changed": int((parts("draft_") != parts("reviewed_")).sum()),
    }


def _counts(label: str, family: str, rows: pd.DataFrame, fields) -> tuple[list, list]:
    changes, outcomes = [], []
    for scope, in_scope in _scopes(family, rows).items():
        for condition in ("all", *CONDITIONS):
            part = in_scope if condition == "all" else in_scope[in_scope["condition"] == condition]
            for field in fields:
                before, after = part[f"draft_{field}"], part[f"reviewed_{field}"]
                changes.append(
                    {
                        "sheet": label,
                        "scope": scope,
                        "condition": condition,
                        "code": field,
                        "units": len(part),
                        "changed": int((before != after).sum()),
                        "zero_to_one": int(((before == 0) & (after == 1)).sum()),
                        "one_to_zero": int(((before == 1) & (after == 0)).sum()),
                        "note": "",
                    }
                )
            if family == RUBRIC:
                outcomes.append({"sheet": label, "condition": condition, **_t1_moves(part)})
    return changes, outcomes


def review(
    coding_dir: Path, sheets: list[Sheet], verdicts: pd.DataFrame, depth: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Item 7: every code of each draft against the reviewed sheet, per sheet and for each family's
    sheets together. The reviewed sheets must be the ones scoring used: their fields are
    rubric_verdicts.csv's, their codes depth.csv's."""
    by_key = verdicts.assign(session_id=verdicts["session_id"].astype(str))
    by_key = by_key.set_index(["session_id", "task_id"])
    by_unit = depth.set_index("unit_id")
    frame = pd.DataFrame(
        [u for sheet in sheets for u in _sheet_units(coding_dir, sheet, by_key, by_unit)]
    )
    changes, outcomes = [], []
    for sheet in sheets:
        mine = frame[frame["sheet"] == sheet.name]
        found = _counts(sheet.name, sheet.family, mine, sheet.fields)
        changes += found[0]
        outcomes += found[1]
    for family in dict.fromkeys(s.family for s in sheets):
        fields = next(s.fields for s in sheets if s.family == family)
        found = _counts(f"{family}, all sheets", family, frame[frame["family"] == family], fields)
        changes += found[0]
        outcomes += found[1]
    for sheet in sheets:
        if DROPPED_CODE in pd.read_csv(coding_dir / sheet.reviewed, nrows=0).columns:
            changes.append(
                {
                    "sheet": sheet.name,
                    "scope": "all units",
                    "condition": "all",
                    "code": DROPPED_CODE,
                    "units": int((frame["sheet"] == sheet.name).sum()),
                    "changed": float("nan"),
                    "zero_to_one": float("nan"),
                    "one_to_zero": float("nan"),
                    "note": "not compared: dropped in review and left as drafted "
                    "(docs/grading-rules.md section 1, item 5)",
                }
            )
    return {
        "review_changes.csv": pd.DataFrame(changes),
        "review_t1_outcomes.csv": pd.DataFrame(outcomes),
    }


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def decision_log(text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The decision log of docs/grading-rules.md (section 8), one row per rule, and per sheet how
    many rules were added, amended in review and moot, and how many answers re-checking changed.
    Refuses a table that is not the one expected, rather than miscount it."""
    if DECISION_LOG_HEADING not in text:
        raise PaperError(f"grading rules: no {DECISION_LOG_HEADING!r} section")
    section = text.split(DECISION_LOG_HEADING, 1)[1].split("\n## ", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("|")]
    if len(lines) < 3:
        raise PaperError("grading rules: the decision log has no rows")
    header = _cells(lines[0])
    expected = zip(header, DECISION_LOG_HEADER, strict=False)
    if len(header) != len(DECISION_LOG_HEADER) or not all(h.startswith(e) for h, e in expected):
        raise PaperError(f"grading rules: unexpected decision log columns {header}")
    rows = []
    for number, line in enumerate(lines[2:], start=1):
        cells = _cells(line)
        if len(cells) != len(header):
            raise PaperError(f"grading rules: decision log row {number} has {len(cells)} cells")
        date, sheet, _case, rule, rechecked = cells
        changed = re.search(r"(\d+) changed", rechecked)
        rows.append(
            {
                "row": number,
                "date": date,
                "sheet": sheet,
                "amended_in_review": "amended in review" in rule.lower(),
                "moot": "moot" in rule.lower(),
                "rechecked": rechecked,
                "rechecked_changed": int(changed[1]) if changed else 0,
            }
        )
    log = pd.DataFrame(rows)
    summary = [
        {
            "sheet": sheet,
            "rules": len(group),
            "amended_in_review": int(group["amended_in_review"].sum()),
            "moot": int(group["moot"].sum()),
            "rechecked_changed": int(group["rechecked_changed"].sum()),
        }
        for sheet, group in [*log.groupby("sheet", sort=False), ("all", log)]
    ]
    return log, pd.DataFrame(summary)


# --- Assembling and writing -----------------------------------------------------------------
OUTPUT_NOTES = {
    "report_main.txt": "Item 1. analysis/report.py's tables (report_section10.txt's), main.",
    "report_preregistered.txt": "Item 1. The same tables as pre-registered (report_section10).",
    "windows.csv": "Item 1. The windows table over each analysis's own participants.",
    "scores.csv": "Item 1. Each participant's scores per condition, the frame the tests ran on; "
    "time_s is their geometric mean time per task, in seconds.",
    "scores_summary.csv": "Item 1. Per outcome and condition: n, mean, sd, median. For time_s, "
    "mean is the geometric mean; log_time carries the sd.",
    "differences.csv": "Item 1. Per outcome: participants above, at and below zero (interactive "
    "minus static), and the sd of the differences. The effect is significance.txt's.",
    "differences_by_participant.csv": "Item 1. Each participant's difference per outcome.",
    "timing_by_participant.csv": "Item 2. Per participant and condition: answers, kept for "
    "accuracy, kept for timing, and whether a time score exists.",
    "timing_exclusions.csv": "Item 2. Each answer kept for accuracy whose time was removed, "
    "and the rule.",
    "t1_rubric.csv": "Items 3 and 3b. Shares of T1 answers credited with a, b, c, contradicting "
    "one, and correct, by form (all, A, B) and condition.",
    "paas_a7_pairs.csv": "Item 4. Each Paas and a7 pair, rescaled to 0-1, their gap, and "
    "whether the pair is opposed.",
    "paas_a7_participants.csv": "Item 4. Each participant's four ratings, their changes, and "
    "whether the pattern looks reversed.",
    "paas_a7_direction.csv": "Item 4. Paas's change against a7's, static to interactive.",
    "paas_a7_summary.csv": "Item 4. Pairs, Spearman's rho (coefficient only), opposed pairs, "
    "gaps, directions, and participants who look reversed.",
    "paas_a7_by_order.csv": "Item 5. Paas and a7 by group (interactive first or second) and "
    "condition.",
    "paas_a7_order_differences.csv": "Item 5. The difference, interactive minus static, by group.",
    "paas_a7_by_half.csv": "Item 5. Both ratings by half, whichever condition it held.",
    "c1_accuracy.csv": "Item 6. Each participant's c1 answer and accuracy difference in items.",
    "c1_accuracy_crosstab.csv": "Item 6. c1 against the direction of the accuracy difference.",
    "c1_accuracy_by_answer.csv": "Item 6. The accuracy difference within each c1 answer.",
    "review_changes.csv": "Items 7 and 7b. Codes the review changed, which way, per sheet, "
    "scope, condition and code.",
    "review_t1_outcomes.csv": "Items 7 and 7b. T1 verdicts and parts scores the changes moved.",
    "decision_log.csv": "Item 7. The decision log's rows (docs/grading-rules.md section 8).",
    "decision_log_summary.csv": "Item 7. Rules added, amended in review and moot, by sheet.",
}


def build(inputs: Inputs, sig: ModuleType) -> dict[str, object]:
    """Every output, in memory, once every check has passed."""
    analyses = build_analyses(inputs, sig)
    check_against_run(analyses, inputs.significance, sig)
    outputs: dict[str, object] = {
        "report_main.txt": report_text(analyses[MAIN], inputs.participants),
        "report_preregistered.txt": report_text(analyses[PREREGISTERED], inputs.participants),
        "windows.csv": windows(analyses),
        "scores.csv": scores_table(analyses),
        "scores_summary.csv": scores_summary(analyses),
    }
    outputs["differences.csv"], outputs["differences_by_participant.csv"] = score_differences(
        analyses
    )
    outputs["timing_by_participant.csv"], outputs["timing_exclusions.csv"] = timing(analyses)
    outputs["t1_rubric.csv"] = t1_rubric(analyses, inputs.verdicts)
    outputs.update(paas_a7(analyses))
    outputs.update(paas_a7_by_order(analyses))
    outputs.update(c1_against_accuracy(analyses, sig.ITEMS_PER_CONDITION))
    outputs.update(review(inputs.coding_dir, review_sheets(), inputs.verdicts, inputs.depth))
    outputs["decision_log.csv"], outputs["decision_log_summary.csv"] = decision_log(
        inputs.rules_text
    )
    guard(outputs)
    outputs["README.txt"] = readme(outputs)
    return outputs


def guard(outputs: dict[str, object]) -> None:
    """No output carries a free-text column, or the marker the free text was replaced by, and
    every output has its line in the README."""
    for name, content in outputs.items():
        if isinstance(content, pd.DataFrame):
            text_columns = FREE_TEXT_COLUMNS & set(content.columns)
            if text_columns:
                raise PaperError(f"{name} would carry free text: {sorted(text_columns)}")
            if (content.astype(str) == TEXT_MARKER).any().any():
                raise PaperError(f"{name} would carry masked free text")
        elif TEXT_MARKER in str(content):
            raise PaperError(f"{name} would carry masked free text")
        if name not in OUTPUT_NOTES:
            raise PaperError(f"{name} has no line in the README")


def readme(outputs: dict[str, object]) -> str:
    who = ", ".join(exclusions.REINSTATED)
    lines = [
        "Exploratory descriptives for the paper (paper/exploratory.md), written by",
        f"scripts/paper_descriptives.py on {dt.date.today().isoformat()}.",
        "",
        "Post hoc and descriptive: no file here holds a test, an interval or a p-value, and",
        "nothing here may be called significant. The effects are significance.txt's.",
        "",
        "Every table gives both analyses, named in its `analysis` column:",
        f"  main           participant {who} reinstated (empty session dropped, every rule re-run)",
        f"  preregistered  the exclusion rules as pre-registered, without participant {who}",
        "",
        "Checked before writing: each outcome's n and the ceiling counts match significance.txt;",
        "the exclusion flags re-derived match tasks.csv; T1's verdicts match tasks.csv; the",
        "reviewed sheets are the ones rubric_verdicts.csv and depth.csv were scored from.",
        "",
        "Participant data: gitignored, never committed. No free text: T1 descriptions,",
        "justifications, c3, E2, E3 and the Other boxes were masked as the files were read.",
        "Background counts are printed in full; the paper merges any group under five.",
        "",
    ]
    width = max(len(name) for name in outputs)
    lines += [f"{name:<{width}}  {OUTPUT_NOTES[name]}" for name in outputs]
    return "\n".join(lines) + "\n"


def write(outputs: dict[str, object], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in outputs.items():
        path = out / name
        if isinstance(content, pd.DataFrame):
            content.to_csv(path, index=False)
        else:
            path.write_text(str(content), encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The paper's exploratory descriptives.")
    parser.add_argument("--derived", type=Path, default=DERIVED)
    parser.add_argument("--coding", type=Path, default=CODING)
    parser.add_argument("--significance", type=Path, help="default: DERIVED/significance.txt")
    parser.add_argument("--rules", type=Path, default=GRADING_RULES)
    parser.add_argument("--out", type=Path, help="default: DERIVED/paper")
    args = parser.parse_args(argv)
    significance = args.significance or args.derived / "significance.txt"
    out = args.out or args.derived / "paper"

    sig = load_notebook()
    try:
        inputs = load_inputs(args.derived, args.coding, significance, args.rules, sig.LABELS)
        outputs = build(inputs, sig)
    except (PaperError, sig.PlanError, coding.CodingError) as exc:
        print(f"Refusing to write: {exc}", file=sys.stderr)
        return 1
    written = write(outputs, out)
    print(
        "Checked against the run: n per outcome and ceiling counts match significance.txt; the "
        "re-derived exclusion flags and T1's verdicts match tasks.csv; the reviewed sheets are "
        "the ones scoring used."
    )
    print(f"Wrote {len(written)} files to {out} (README.txt says what each holds).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
