"""Tests for the paper's scripts: scripts/paper_descriptives.py, the exploratory descriptives
(paper/exploratory.md, items 1 to 7); scripts/paper_numbers.py, which writes paper/numbers.tex; and
scripts/paper_figures.py, which writes paper/tables/ and paper/figures/.

All three run on study data, so everything they compute is checked here first, on made-up files
shaped like the pipeline's, with significance.txt printed by the notebook's own main(): each item on
planted cases; the checks that make them refuse to write when their inputs disagree with
significance.txt, tasks.csv, the coding sheets or numbers.tex; that none calls one of the notebook's
tests; that no free text or participant ID reaches an output; that a table types no number; and
that every number the paper uses is defined in the committed paper/numbers.tex.
"""

from __future__ import annotations

import contextlib
import html
import importlib.util
import io
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis import coding, exclusions, reshape
from src import tasks as study_tasks

pytest.importorskip("scipy")

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "paper_descriptives.py"
_spec = importlib.util.spec_from_file_location("paper_descriptives", SCRIPT)
paper = importlib.util.module_from_spec(_spec)
sys.modules["paper_descriptives"] = paper  # its dataclasses look their module up here
_spec.loader.exec_module(paper)
sig = paper.load_notebook()
NUMBERS = ROOT / "scripts" / "paper_numbers.py"
_numbers_spec = importlib.util.spec_from_file_location("paper_numbers", NUMBERS)
numbers_script = importlib.util.module_from_spec(_numbers_spec)
sys.modules["paper_numbers"] = numbers_script
_numbers_spec.loader.exec_module(numbers_script)
assert numbers_script.load_descriptives() is paper, "one module, so a trap set on it holds"
FIGURES = ROOT / "scripts" / "paper_figures.py"
_figures_spec = importlib.util.spec_from_file_location("paper_figures", FIGURES)
figures_script = importlib.util.module_from_spec(_figures_spec)
sys.modules["paper_figures"] = figures_script
_figures_spec.loader.exec_module(figures_script)
assert figures_script._load("paper_numbers", NUMBERS) is numbers_script, "one module, as above"
PAPER = ROOT / "paper"
# Neither paper script may import the library the notebook's tests use.
IMPORTS_SCIPY = re.compile(r"^\s*(import|from)\s+scipy\b", flags=re.MULTILINE)

# Planted in every free-text field of the made-up files. No output may contain it.
SECRET = "SECRET-PARTICIPANT-TEXT"
TASK = {(t.form, t.task_id): t for form in study_tasks.FORMS for t in study_tasks.for_form(form)}
RELOADED = "5"  # a participant whose interactive half lost its clock to a reload
NOTEBOOK_TESTS = (
    "crossover",
    "run",
    "permutation_p",
    "tost",
    "wilcoxon",
    "holm",
    "analyse",
    "main",
    "power",
    "min_detectable",
    "sensitivity_table",
)


# --- Made-up study files ------------------------------------------------------------------------
def _rubric_fields(rng: np.random.Generator, correct: bool) -> dict[str, int]:
    """A rubric coding that agrees with the verdict, as the grading rules require (G4)."""
    if correct:
        return {"a": 1, "b": 1, "c": 1, "contradicts": 0}
    fields = dict.fromkeys(coding.RUBRIC_PARTS, 1)
    while all(fields.values()):
        fields = {part: int(rng.random() < 0.6) for part in coding.RUBRIC_PARTS}
    return {**fields, "contradicts": int(rng.random() < 0.3)}


def _ids(rows: pd.DataFrame) -> list[str]:
    return [coding.unit_id(s, t) for s, t in zip(rows["session_id"], rows["task_id"], strict=True)]


def _tasks(rng: np.random.Generator):
    """tasks.csv's rows as score_study.py writes them, with T1's verdicts beside them."""
    tasks, conditions, depth = sig.simulate(per_cell=6, seed=2026, empty_session_for="19")
    reload = (tasks["participant_id"] == RELOADED) & (tasks["condition"] == "interactive")
    tasks["duration_invalid"] = tasks["duration_invalid"].astype(object)
    tasks.loc[reload, "duration_ms"] = np.nan
    tasks.loc[reload, "duration_invalid"] = "clock_reset"
    tasks, _ = exclusions.apply(tasks.drop(columns=["use_accuracy", "use_timing"]), conditions)

    info = [TASK[(f, t)] for f, t in zip(tasks["form"], tasks["task_id"], strict=True)]
    tasks["kind"] = [task.kind for task in info]
    tasks["chart"] = [task.chart for task in info]
    verdicts = []
    for i in tasks.index[tasks["kind"] == coding.WRITTEN_KIND]:
        if tasks.at[i, "skipped_answer"]:
            tasks.at[i, "correct"], tasks.at[i, "t1_parts"] = False, 0
            continue
        fields = _rubric_fields(rng, bool(tasks.at[i, "correct"]))
        tasks.at[i, "correct"] = coding.rubric_correct(fields)
        tasks.at[i, "t1_parts"] = coding.parts_score(fields)
        verdicts.append(
            {
                "session_id": tasks.at[i, "session_id"],
                "task_id": tasks.at[i, "task_id"],
                "correct": int(coding.rubric_correct(fields)),
                **fields,
                "parts": coding.parts_score(fields),
            }
        )
    skipped = tasks["skipped_answer"]
    tasks["answer"] = [
        None if skip else (f"{SECRET} T1" if task.kind == coding.WRITTEN_KIND else task.options[0])
        for task, skip in zip(info, skipped, strict=True)
    ]
    tasks["justification"] = [
        None if task.kind == coding.WRITTEN_KIND else f"{SECRET} why" for task in info
    ]
    tasks["correct_adjacent"] = [
        c if task.kind == "crossing" else None
        for c, task in zip(tasks["correct"], info, strict=True)
    ]
    tasks["skipped_justification"] = False
    interactive = (tasks["condition"] == "interactive").to_numpy()
    for column in reshape.TASK_COLUMNS:
        if column.startswith("n_"):
            tasks[column] = np.where(interactive, rng.integers(0, 3, len(tasks)), 0)
    tasks["years_from_2000"] = interactive & (rng.random(len(tasks)) < 0.3)
    tasks["zoom_from_2000"] = False
    heights = {p: int(rng.integers(560, 1040)) for p in tasks["participant_id"].unique()}
    tasks["window_width"] = 1440
    tasks["window_height"] = tasks["participant_id"].map(heights)
    return tasks[[*reshape.TASK_COLUMNS, "use_accuracy", "use_timing"]], conditions, depth, verdicts


def _conditions(conditions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """conditions.csv: the survey after each half, nothing after participant 19's empty one."""
    asked = conditions["n_answers"] > 0
    second = asked & (conditions["condition_order"] == 2)
    for key in reshape.LIKERT_KEYS:
        conditions[key] = np.where(asked, rng.integers(1, 8, len(conditions)), np.nan)
    interactive = asked & (conditions["condition"] == "interactive")
    for key in reshape.CONTROLS_KEYS:
        conditions[key] = np.where(interactive, rng.integers(1, 8, len(conditions)), np.nan)
    options = study_tasks.COMPARISON_OPTIONS
    for key in study_tasks.COMPARISON_CHOICES:
        conditions[key] = [options[int(rng.integers(0, 3))] if s else None for s in second]
    conditions[study_tasks.COMPARISON_TEXT_KEY] = [f"{SECRET} c3" if s else None for s in second]
    return conditions


def _participants(people: list[str]) -> pd.DataFrame:
    """participants.csv: About you, with every free-text box written in."""
    frame = pd.DataFrame({"participant_id": people})
    for column in reshape.DEMOGRAPHIC_COLUMNS:
        frame[column] = study_tasks.PREFER_NOT
    frame["age"] = 20
    frame["pointer"], frame["pointer_other"] = study_tasks.OTHER, f"{SECRET} pointer"
    frame["field"], frame["field_other"] = study_tasks.OTHER, f"{SECRET} field"
    frame["confusing"], frame["feedback"] = f"{SECRET} E2", f"{SECRET} E3"
    # Typed text pandas reads as missing by default, and one real skip.
    frame.loc[1, "confusing"] = "N/A"
    frame.loc[2, "feedback"] = "None"
    frame.loc[3, "feedback"] = None
    frame[study_tasks.HEARD_KEY] = ["Yes" if p == "1" else "No" for p in people]
    return frame


def _sheets(coded: Path, depth: pd.DataFrame, t1: pd.DataFrame, verdicts: pd.DataFrame) -> dict:
    """The coding files: depth.csv and rubric_verdicts.csv, the reviewed sheets they were scored
    from, the keys, and Claude's drafts, which the review changed in a few planted places."""
    planted = {}
    depth.to_csv(coded / "depth.csv", index=False)
    verdicts.to_csv(coded / "rubric_verdicts.csv", index=False)
    for suffix, rows in (
        ("", depth[depth["participant_id"] != "19"]),
        ("_p19", depth[depth["participant_id"] == "19"]),
    ):
        rows[list(coding.KEY_COLUMNS)].to_csv(coded / f"key{suffix}.csv", index=False)
        sheet = rows[["unit_id", *coding.CODES]].assign(justification=f"{SECRET} sheet")
        sheet = sheet.assign(draft_note="")
        draft = sheet.copy()
        if not suffix:
            sheet["notes_uncertainty"] = 0
            draft["notes_uncertainty"] = 1  # differs, and must never be compared
            flipped = draft.index[:3]
            draft.loc[flipped, "cites_values"] = 1 - draft.loc[flipped, "cites_values"]
            planted["rq2"] = rows.loc[flipped, ["task_id", "cites_values"]]
        sheet.to_csv(coded / f"coder1{suffix}.csv", index=False)
        draft.to_csv(coded / f"coder1{suffix}_draft.csv", index=False)

    by_session = verdicts.set_index("session_id")
    for suffix, rows in (
        ("", t1[t1["participant_id"] != "19"]),
        ("_p19", t1[t1["participant_id"] == "19"]),
    ):
        rows = rows.assign(unit_id=_ids(rows)).reset_index(drop=True)
        rows[list(coding.KEY_COLUMNS)].to_csv(coded / f"rubric_key{suffix}.csv", index=False)
        fields = by_session.loc[rows["session_id"], list(coding.RUBRIC_FIELDS)]
        sheet = rows[["unit_id"]].assign(
            description=f"{SECRET} T1", part_a="(a)", part_b="(b)", part_c="(c)"
        )
        sheet = pd.concat([sheet, fields.reset_index(drop=True)], axis=1).assign(draft_note="")
        draft = sheet.copy()
        if not suffix:
            # The review credited (c) on two answers the draft had not.
            credited = sheet.index[sheet["c"] == 1][:2]
            draft.loc[credited, "c"] = 0
            planted["rubric"] = sheet.loc[credited]
        sheet.to_csv(coded / f"rubric_coder1{suffix}.csv", index=False)
        draft.to_csv(coded / f"rubric_coder1{suffix}_draft.csv", index=False)
    return planted


def _study(root: Path, seed: int = 2026) -> dict:
    """Every file the script reads, made up, and significance.txt from the notebook's main()."""
    rng = np.random.default_rng(seed)
    tasks, conditions, depth, verdicts = _tasks(rng)
    conditions = _conditions(conditions, rng)
    people = sorted(tasks["participant_id"].unique(), key=int)
    derived, coded = root / "derived", root / "coding"
    derived.mkdir()
    coded.mkdir()
    tasks.to_csv(derived / "tasks.csv", index=False)
    conditions.to_csv(derived / "conditions.csv", index=False)
    _participants(people).to_csv(derived / "participants.csv", index=False)
    t1 = tasks[(tasks["kind"] == coding.WRITTEN_KIND) & ~tasks["skipped_answer"]]
    depth = depth.assign(unit_id=_ids(depth))
    planted = _sheets(coded, depth, t1, pd.DataFrame(verdicts))
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        assert sig.main(["--derived", str(derived), "--depth", str(coded / "depth.csv")]) == 0
    (derived / "significance.txt").write_text(printed.getvalue(), encoding="utf-8")
    return {"derived": derived, "coding": coded, "out": root / "out", "planted": planted}


def _run(study: dict) -> int:
    return paper.main(
        [
            "--derived",
            str(study["derived"]),
            "--coding",
            str(study["coding"]),
            "--out",
            str(study["out"]),
        ]
    )


def _copy(study: dict, root: Path) -> dict:
    """The study's files in a fresh directory, to be changed by one test only."""
    for name in ("derived", "coding"):
        shutil.copytree(study[name], root / name)
    return {**study, "derived": root / "derived", "coding": root / "coding", "out": root / "out"}


def _output(study: dict, name: str) -> pd.DataFrame:
    return pd.read_csv(study["out"] / name, dtype={"participant_id": str})


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> dict:
    """The made-up study, with the script run on it once."""
    study = _study(tmp_path_factory.mktemp("study"))
    assert _run(study) == 0
    return study


# --- The run, end to end ------------------------------------------------------------------------
def test_writes_every_output_for_both_analyses(built):
    written = {path.name for path in built["out"].iterdir()}
    assert written == {*paper.OUTPUT_NOTES, "README.txt"}
    readme = (built["out"] / "README.txt").read_text(encoding="utf-8")
    assert all(name in readme for name in paper.OUTPUT_NOTES)
    for name in paper.OUTPUT_NOTES:
        if name.endswith(".csv"):
            frame = _output(built, name)
            if "analysis" in frame:
                assert set(frame["analysis"]) == {paper.MAIN, paper.PREREGISTERED}, name
    scores = _output(built, "scores.csv")
    people = scores.groupby("analysis")["participant_id"].nunique()
    assert people.to_dict() == {paper.MAIN: 24, paper.PREREGISTERED: 23}
    assert "19" in set(scores.loc[scores["analysis"] == paper.MAIN, "participant_id"])
    assert "19" not in set(scores.loc[scores["analysis"] == paper.PREREGISTERED, "participant_id"])
    windows = _output(built, "windows.csv").set_index("analysis")["participants"]
    assert windows.to_dict() == {paper.MAIN: 24, paper.PREREGISTERED: 23}
    main_report = (built["out"] / "report_main.txt").read_text(encoding="utf-8")
    pre_report = (built["out"] / "report_preregistered.txt").read_text(encoding="utf-8")
    assert "n = 24" in main_report and "Accuracy, RQ1 primary" in main_report
    assert "n = 23" in pre_report and "windows.csv counts this analysis's own" in pre_report


def test_no_free_text_reaches_any_output(built):
    for path in built["out"].iterdir():
        text = path.read_text(encoding="utf-8")
        assert SECRET not in text, path.name
        assert paper.TEXT_MARKER not in text, path.name


def test_the_script_never_calls_one_of_the_notebooks_tests(built, tmp_path, monkeypatch):
    def trap(name):
        def called(*args, **kwargs):
            raise AssertionError(f"paper_descriptives called the notebook's {name}()")

        return called

    for name in NOTEBOOK_TESTS:
        monkeypatch.setattr(sig, name, trap(name))
    assert _run({**built, "out": tmp_path / "out"}) == 0
    assert not IMPORTS_SCIPY.search(SCRIPT.read_text(encoding="utf-8")), "no test library"


def test_the_scores_are_the_ones_the_run_counted(built):
    """Each outcome's n here is the n the notebook printed, analysis by analysis."""
    text = (built["derived"] / "significance.txt").read_text(encoding="utf-8")
    run = paper.parse_significance(text, sig.LABELS)
    assert run[paper.MAIN]["n"] == 24 and run[paper.PREREGISTERED]["n"] == 23
    differences = _output(built, "differences.csv")
    for name in (paper.MAIN, paper.PREREGISTERED):
        assert set(sig.CONFIRMATORY) <= set(run[name]["outcomes"])
        ours = differences[differences["analysis"] == name].set_index("outcome")["n"]
        for outcome, row in run[name]["outcomes"].items():
            assert ours[outcome] == int(row["n"]), (name, outcome)
        assert ours["log_time"] == ours["accuracy"] - 1  # the reloaded half has no time
        total = differences[differences["analysis"] == name].set_index("outcome")
        assert (total["above_zero"] + total["zero"] + total["below_zero"] == total["n"]).all()


# --- Refusals: nothing written -------------------------------------------------------------------
def _refused(study: dict, capsys, message: str) -> None:
    assert _run(study) == 1
    assert message in capsys.readouterr().err
    assert not study["out"].exists(), "a refusal writes nothing"


def test_refuses_when_an_n_differs_from_significance_txt(built, tmp_path, capsys):
    study = _copy(built, tmp_path)
    path = study["derived"] / "significance.txt"
    path.write_text(path.read_text(encoding="utf-8").replace(": n = 24", ": n = 25", 1))
    _refused(study, capsys, "does not match significance.txt")


def test_refuses_when_the_exclusion_flags_are_not_the_rules(built, tmp_path, capsys):
    study = _copy(built, tmp_path)
    path = study["derived"] / "tasks.csv"
    tasks = pd.read_csv(path, dtype={"participant_id": str, "session_id": str})
    tasks.loc[tasks.index[tasks["use_timing"]][0], "use_timing"] = False
    tasks.to_csv(path, index=False)
    _refused(study, capsys, "differs from what the pre-registered rules give")


def test_refuses_when_t1s_parts_are_not_its_rubric(built, tmp_path, capsys):
    study = _copy(built, tmp_path)
    path = study["derived"] / "tasks.csv"
    tasks = pd.read_csv(path, dtype={"participant_id": str, "session_id": str})
    full = tasks.index[(tasks["task_id"] == "T1") & (tasks["t1_parts"] == 3)][0]
    tasks.loc[full, "t1_parts"] = 2
    tasks.to_csv(path, index=False)
    _refused(study, capsys, "a + b + c is not t1_parts")


def test_refuses_a_reviewed_sheet_that_scoring_did_not_use(built, tmp_path, capsys):
    study = _copy(built, tmp_path)
    path = study["coding"] / "coder1.csv"
    sheet = pd.read_csv(path, dtype={"unit_id": str})
    sheet.loc[0, "compares_series"] = 1 - sheet.loc[0, "compares_series"]
    sheet.to_csv(path, index=False)
    _refused(study, capsys, "is not the sheet scoring used")


def test_parse_refuses_a_file_without_both_analyses():
    with pytest.raises(paper.PaperError, match="both analyses"):
        paper.parse_significance("MAIN: with participant 19 (deviation): n = 24\n", sig.LABELS)


# --- Items ----------------------------------------------------------------------------------------
def test_item_2_finds_the_reload_and_names_its_rule(built):
    by_participant = _output(built, "timing_by_participant.csv")
    for name in (paper.MAIN, paper.PREREGISTERED):
        mine = by_participant[by_participant["analysis"] == name]
        without = mine[~mine["has_time_score"]]
        assert list(zip(without["participant_id"], without["condition"], strict=True)) == [
            (RELOADED, "interactive")
        ]
    removed = _output(built, "timing_exclusions.csv")
    reload = removed[
        (removed["participant_id"] == RELOADED) & (removed["condition"] == "interactive")
    ]
    assert len(reload) == 12  # six answers, in each analysis
    assert set(reload["rule"]) == {"invalid_timing"}
    assert set(reload["duration_invalid"]) == {"clock_reset"}
    trimmed = removed[removed["rule"] == "top_one_percent"]
    assert len(trimmed) > 0
    assert (trimmed["duration_ms"] > trimmed["cutoff_ms"]).all()


def test_item_3_t1_shares_match_t1_accuracy_and_forms_add_up(built):
    rubric = _output(built, "t1_rubric.csv")
    tasks = pd.read_csv(built["derived"] / "tasks.csv", dtype={"participant_id": str})
    kept = tasks[tasks["use_accuracy"] & (tasks["task_id"] == "T1")]
    pre = rubric[(rubric["analysis"] == paper.PREREGISTERED) & (rubric["form"] == "all")]
    for condition, share in zip(pre["condition"], pre["share_correct"], strict=True):
        mine = kept[kept["condition"] == condition]
        assert share == pytest.approx(mine["correct"].astype(float).mean())
    for name in (paper.MAIN, paper.PREREGISTERED):
        mine = rubric[rubric["analysis"] == name].set_index(["form", "condition"])["n"]
        for condition in paper.CONDITIONS:
            assert mine[("A", condition)] + mine[("B", condition)] == mine[("all", condition)]
        assert mine.xs("all").sum() == {paper.MAIN: 48, paper.PREREGISTERED: 46}[name]


def _rated(rows: list[tuple]) -> paper.Analysis:
    """An analysis holding only sessions' ratings: (participant, condition, half, paas, a7)."""
    conditions = pd.DataFrame(
        rows, columns=["participant_id", "condition", "condition_order", "paas", "a7"]
    )
    conditions["session_id"] = conditions["participant_id"] + "-" + conditions["condition"]
    conditions["form"] = "A"
    people = conditions["participant_id"].unique()
    tasks = pd.DataFrame({"participant_id": people, "use_accuracy": True})
    return paper.Analysis(paper.MAIN, tasks, conditions, (), pd.DataFrame())


def test_item_4_opposed_pairs_at_the_cut_offs():
    assert paper.is_opposed(7, 3) and paper.is_opposed(8, 2) and paper.is_opposed(9, 1)
    assert paper.is_opposed(3, 5) and paper.is_opposed(2, 6) and paper.is_opposed(1, 7)
    assert not paper.is_opposed(6, 3) and not paper.is_opposed(7, 4)
    assert not paper.is_opposed(3, 4) and not paper.is_opposed(4, 5)
    assert not paper.is_opposed(8, 7) and not paper.is_opposed(2, 1)


def test_item_4_who_looks_reversed():
    analysis = _rated(
        [
            ("1", "static", 1, 8, 2),  # opposed both times
            ("1", "interactive", 2, 2, 6),
            ("2", "static", 1, 7, 3),  # opposed once, the scales moving apart
            ("2", "interactive", 2, 4, 4),
            ("3", "static", 1, 7, 3),  # opposed once, the scales moving together
            ("3", "interactive", 2, 5, 2),
            ("4", "static", 1, 6, 3),  # never opposed: each at the edge of a cut-off
            ("4", "interactive", 2, 3, 4),
            ("5", "static", 1, 3, 5),  # opposed once, but a7 skipped in the other half
            ("5", "interactive", 2, 5, np.nan),
        ]
    )
    found = paper.paas_a7({paper.MAIN: analysis})
    people = found["paas_a7_participants.csv"].set_index("participant_id")
    assert people["looks_reversed"].to_dict() == {
        "1": True,
        "2": True,
        "3": False,
        "4": False,
        "5": False,
    }
    assert not people.loc["5", "complete"]
    summary = found["paas_a7_summary.csv"].set_index(["statistic", "scope"])["value"]
    assert summary[("pairs_missing_a_rating", "all")] == 1
    assert summary[("pairs", "all")] == 9
    assert summary[("opposed_pairs", "static")] == 4
    assert summary[("opposed_pairs", "interactive")] == 1
    assert summary[("looks_reversed", "all")] == 2
    assert summary[("participants_with_both_pairs", "all")] == 4
    assert summary[("opposite_direction", "all")] == 3
    assert summary[("same_direction", "all")] == 1
    direction = found["paas_a7_direction.csv"].set_index(["paas_change", "a7_change"])["n"]
    assert direction[("lower", "higher")] == 3 and direction.sum() == 4


def test_item_4_spearman_is_scipys_coefficient():
    stats = pytest.importorskip("scipy.stats")
    rng = np.random.default_rng(3)
    x = rng.integers(1, 10, 40)
    y = x + rng.integers(-3, 4, 40)
    assert paper.spearman(x, y) == pytest.approx(stats.spearmanr(x, y).statistic)
    assert math.isnan(paper.spearman([4, 4, 4], [1, 2, 3]))


def test_item_5_groups_follow_the_interactive_half():
    analysis = _rated(
        [
            ("1", "interactive", 1, 3, 2),
            ("1", "static", 2, 6, 5),
            ("2", "static", 1, 7, 6),
            ("2", "interactive", 2, 5, 3),
        ]
    )
    found = paper.paas_a7_by_order({paper.MAIN: analysis})
    by_order = found["paas_a7_by_order.csv"].set_index(["group", "condition", "measure"])["mean"]
    assert by_order[("interactive first", "interactive", "paas")] == 3
    assert by_order[("interactive second", "static", "a7")] == 6
    differences = found["paas_a7_order_differences.csv"].set_index(["group", "measure"])["mean"]
    assert differences[("interactive first", "paas")] == -3
    assert differences[("interactive second", "a7")] == -3
    by_half = found["paas_a7_by_half.csv"].set_index(["half", "measure"])["mean"]
    assert by_half[(1, "paas")] == 5 and by_half[(2, "paas")] == 5.5


def test_item_6_c1_beside_each_accuracy_difference():
    scores = pd.DataFrame(
        {
            "participant_id": ["1", "1", "2", "2", "3", "3"],
            "condition": ["static", "interactive"] * 3,
            "accuracy": [3 / 6, 5 / 6, 4 / 6, 4 / 6, 5 / 6, 4 / 6],
        }
    )
    conditions = pd.DataFrame(
        {
            "participant_id": ["1", "1", "2", "2", "3", "3"],
            "condition_order": [1, 2] * 3,
            "c1": [None, "The charts with controls", None, "No difference", None, None],
        }
    )
    tasks = pd.DataFrame({"participant_id": ["1", "2", "3"], "use_accuracy": True})
    analysis = paper.Analysis(paper.MAIN, tasks, conditions, (), scores)
    found = paper.c1_against_accuracy({paper.MAIN: analysis}, items=6)
    each = found["c1_accuracy.csv"].set_index("participant_id")
    assert each["accuracy_difference_items"].to_dict() == {"1": 2.0, "2": 0.0, "3": -1.0}
    assert each["direction"].to_dict() == {
        "1": "interactive higher",
        "2": "equal",
        "3": "static higher",
    }
    assert each.loc["3", "c1"] == paper.SKIPPED
    crosstab = found["c1_accuracy_crosstab.csv"].set_index(["c1", "direction"])["n"]
    assert crosstab[("The charts with controls", "interactive higher")] == 1
    assert crosstab[("No difference", "equal")] == 1
    assert crosstab.sum() == 3 and len(crosstab) == 4 * 3  # every answer, every direction


def test_item_7_counts_each_planted_change_once_and_its_way(built):
    changes = _output(built, "review_changes.csv")
    at = changes.set_index(["sheet", "scope", "condition", "code"])
    flipped = built["planted"]["rq2"]
    cites = at.loc[("RQ2, main sheet", "all units", "all", "cites_values")]
    assert cites["changed"] == len(flipped) == 3
    assert cites["zero_to_one"] == int((flipped["cites_values"] == 1).sum())
    assert at.loc[("RQ2, main sheet", "all units", "all", "compares_series"), "changed"] == 0
    in_t1 = int(flipped["task_id"].isin(paper.WRITTEN_TASKS).sum())
    assert at.loc[("RQ2, main sheet", "T1 units", "all", "cites_values"), "changed"] == in_t1
    assert at.loc[("RQ2, main sheet", "T2-T6 units", "all", "cites_values"), "changed"] == 3 - in_t1
    by_condition = changes[
        (changes["sheet"] == "RQ2, main sheet")
        & (changes["scope"] == "all units")
        & (changes["code"] == "cites_values")
        & changes["condition"].isin(paper.CONDITIONS)
    ]
    assert by_condition["changed"].sum() == 3
    assert at.loc[("RQ2, all sheets", "all units", "all", "cites_values"), "changed"] == 3
    p19 = changes[changes["sheet"].str.contains("participant 19")]
    assert p19["changed"].dropna().eq(0).all() and len(p19) > 0
    dropped = changes[changes["code"] == "notes_uncertainty"]
    assert len(dropped) == 1 and dropped["changed"].isna().all()
    assert "not compared" in dropped["note"].iloc[0]

    credited = built["planted"]["rubric"]
    c = at.loc[("T1 rubric, main sheet", "T1", "all", "c")]
    assert c["changed"] == c["zero_to_one"] == len(credited) == 2
    moved = _output(built, "review_t1_outcomes.csv").set_index(["sheet", "condition"])
    expected = int(
        ((credited["a"] == 1) & (credited["b"] == 1) & (credited["contradicts"] == 0)).sum()
    )
    main_sheet = moved.loc[("T1 rubric, main sheet", "all")]
    assert main_sheet["verdicts_changed"] == main_sheet["to_correct"] == expected
    assert main_sheet["parts_changed"] == 2


DECISION_LOG = """\
# Rules

## 8. Decision log

| Date | Sheet | The case (described, not quoted) | Rule added | Answers re-checked |
|---|---|---|---|---|
| 2026-11-11 | rubric | one | *Amended in review:* a rule | all 46, re-checked: 3 changed |
| 2026-11-11 | rubric | two | another rule | all 46, drafted with it |
| 2026-11-11 | RQ2 | three | a rule. *Moot: the code was dropped.* | all 276, drafted with it |

## 9. Next

| not | the | log | at | all |
|---|---|---|---|---|
| x | x | x | x | x |
"""


def test_item_7_the_decision_log_from_a_fixture_and_the_real_file():
    log, summary = paper.decision_log(DECISION_LOG)
    assert len(log) == 3 and list(log["sheet"]) == ["rubric", "rubric", "RQ2"]
    by_sheet = summary.set_index("sheet")
    assert by_sheet.loc["rubric", "rules"] == 2 and by_sheet.loc["rubric", "amended_in_review"] == 1
    assert by_sheet.loc["rubric", "rechecked_changed"] == 3
    assert by_sheet.loc["RQ2", "moot"] == 1 and by_sheet.loc["all", "rules"] == 3

    real, real_summary = paper.decision_log(paper.GRADING_RULES.read_text(encoding="utf-8"))
    assert len(real) >= 1 and set(real["sheet"]) <= {"rubric", "RQ2"}
    assert real_summary.set_index("sheet").loc["all", "rules"] == len(real)

    broken = DECISION_LOG.replace("| Date | Sheet |", "| When | Sheet |")
    with pytest.raises(paper.PaperError, match="columns"):
        paper.decision_log(broken)


def test_typed_text_that_looks_missing_still_counts_as_written(built, tmp_path):
    """A participant who typed "N/A" or "None" wrote something; only an empty cell is a skip.
    Found on the first run on study data, where the default reading counted four such answers
    as skipped in E2 and E3."""
    path = tmp_path / "frame.csv"
    path.write_text("participant_id,note,value\n1,N/A,1.5\n2,None,\n3,,2\n", encoding="utf-8")
    frame = paper.read_csv(path)
    assert frame["note"].tolist()[:2] == ["N/A", "None"] and pd.isna(frame["note"].iloc[2])
    assert frame["value"].dtype == float and pd.isna(frame["value"].iloc[1])
    report = (built["out"] / "report_main.txt").read_text(encoding="utf-8")
    written = {
        found[1]: int(found[2])
        for found in re.finditer(
            r"^(confusing|feedback)\s+\(written; read the text in participants\.csv\)\s+(\d+)$",
            report,
            flags=re.MULTILINE,
        )
    }
    assert written == {"confusing": 24, "feedback": 23}


def test_masking_keeps_whether_something_was_written_and_nothing_else():
    frame = pd.DataFrame({"kind": ["describe", "rank", "describe"], "answer": ["text", "B", None]})
    masked = paper.mask(frame, ["answer"], rows=frame["kind"] == "describe")
    assert masked["answer"].tolist()[:2] == [paper.TEXT_MARKER, "B"]
    assert pd.isna(masked["answer"].iloc[2])


def test_parse_reads_every_line_printed_after_the_tables(built):
    text = (built["derived"] / "significance.txt").read_text(encoding="utf-8")
    run = paper.parse_significance(text, sig.LABELS)
    for name in (paper.MAIN, paper.PREREGISTERED):
        lines = run[name]["lines"]
        assert set(lines) == set(paper.LINES)
        assert sum(int(n) for n in lines["cells"].values()) == run[name]["n"]
        assert lines["tost"]["items"] == "1" and lines["tost"]["of"] == "6"
        assert lines["rq3"]["verdict"] in ("supported", "not supported")


# --- paper/numbers.tex ----------------------------------------------------------------------------
DEFSTAT = re.compile(r"^\\defstat\{(?P<key>[^{}]+)\}\{(?P<value>.*)\}$")
STAT = re.compile(r"\\stat\{([^{}]+)\}")


def _numbers(study: dict, out: Path) -> int:
    return numbers_script.main(
        [
            "--derived",
            str(study["derived"]),
            "--coding",
            str(study["coding"]),
            "--out",
            str(out),
        ]
    )


def _defined(text: str) -> dict[str, str]:
    """numbers.tex's keys and values. Every line is a comment, the header, or one \\defstat."""
    return {m["key"]: m["value"] for line in text.splitlines() if (m := DEFSTAT.match(line))}


@pytest.fixture(scope="module")
def numbered(built) -> str:
    """numbers.tex written from the made-up study."""
    path = built["out"].parent / "numbers.tex"
    assert _numbers(built, path) == 0
    return path.read_text(encoding="utf-8")


def test_numbers_carry_the_run_as_printed(built, numbered):
    defined = _defined(numbered)
    text = (built["derived"] / "significance.txt").read_text(encoding="utf-8")
    run = paper.parse_significance(text, sig.LABELS)
    for name, p in numbers_script.PREFIX.items():
        assert defined[f"{p}/n"] == str(run[name]["n"])
        for outcome, row in run[name]["outcomes"].items():
            base = f"{p}/{outcome}"
            assert defined[f"{base}/est"] == numbers_script.tex(row["effect"].lstrip("x"))
            ci = numbers_script.tex(f"[{row['low']}, {row['high']}]")
            assert defined[f"{base}/ci"] == ci
            assert defined[f"{base}/p"] == numbers_script.tex(row["p"])
            # Holm's p only for the three main tests: no secondary can cite one.
            assert (f"{base}/holm" in defined) == (outcome in sig.CONFIRMATORY)
        tost = run[name]["lines"]["tost"]
        assert defined[f"{p}/tost/verdict"] == tost["verdict"]
        ceiling = run[name]["ceiling"]
        assert defined[f"{p}/ceiling/interactive"] == str(ceiling["interactive"][0])


def test_numbers_print_a_true_minus_sign():
    assert numbers_script.tex("-0.035") == r"\textminus{}0.035"
    assert numbers_script.tex("[-0.21, +0.88]") == r"[\textminus{}0.21, +0.88]"
    assert numbers_script.tex("<.001") == r"\textless{}.001"
    assert numbers_script.tex("not supported") == "not supported"


def test_numbers_give_the_plans_sensitivity(numbered):
    """docs/study-design.md section 7: dz 0.60 and 0.71 at n = 24, 0.61 and 0.73 at n = 23."""
    defined = _defined(numbered)
    assert defined["main/sensitivity/single"] == "0.60"
    assert defined["main/sensitivity/holm"] == "0.71"
    assert defined["pre/sensitivity/single"] == "0.61"
    assert defined["pre/sensitivity/holm"] == "0.73"
    assert defined["design/power"] == "80", "the power those smallest effects assume"


def test_numbers_carry_the_mini_project_as_the_proposal_reports_it(numbered):
    """The proposal's section 6: six participants (two static, four interactive), drops of 2.75
    and 2.50 points and a rise of 1.50 on a 7-point scale, 6:37 against 8:40."""
    defined = _defined(numbered)
    mini = {k: v for k, v in defined.items() if k.startswith("mini/")}
    assert mini == numbers_script.MINI_PROJECT
    assert int(mini["mini/static/n"]) + int(mini["mini/interactive/n"]) == int(mini["mini/n"])
    assert mini["mini/time/static"] == "6 min 37 s"
    assert mini["mini/time/interactive"] == "8 min 40 s"


def test_numbers_hold_no_free_text_and_no_background_group_under_five(numbered):
    assert SECRET not in numbered and paper.TEXT_MARKER not in numbered
    defined = _defined(numbered)
    summary = ("/sample/n", "/sample/age/n", "/sample/age/median", "/sample/age/min")
    background = [k for k in defined if "/sample/" in k and not k.endswith((*summary, "age/max"))]
    assert background, "the made-up sample has groups of five or more"
    for key in background:
        assert int(defined[key]) >= numbers_script.MIN_GROUP, key
    # Every made-up participant gave "Prefer not to say" for their role: no group, no key.
    assert "main/sample/undergrad" not in defined
    # Described once: the background of both analyses would give participant 19's by subtraction.
    assert [k for k in defined if k.startswith("pre/sample/")] == ["pre/sample/n"]
    fields = [int(v) for k, v in defined.items() if k.startswith("main/sample/field/")]
    assert sum(fields) == int(defined["main/sample/n"]), "no field group hidden in a remainder"


def test_a_background_group_is_written_only_with_five_on_each_side():
    numbers = numbers_script.Numbers()
    numbers.group("main/sample/a", 22, 24)  # leaves a group of two by subtraction
    numbers.group("main/sample/b", 19, 24)
    numbers.group("main/sample/c", 24, 24)  # everyone: nothing left to subtract
    numbers.group("main/sample/d", 4, 24)
    assert numbers.values == {"main/sample/b": "19", "main/sample/c": "24"}


def test_numbers_tex_is_one_defstat_per_line(numbered):
    body = numbered.split(r"\newcommand{\defstat}", 1)[1].splitlines()[1:]
    keys = []
    for line in body:
        if not line.strip() or line.startswith("%"):
            continue
        found = DEFSTAT.match(line)
        assert found, line
        keys.append(found["key"])
        value = found["value"]
        assert value.count("{") == value.count("}"), line
        assert not set(value) & set("%&#$^_~"), line
    assert len(keys) == len(set(keys)) == len(_defined(numbered))


def test_numbers_never_call_one_of_the_notebooks_tests(built, tmp_path, monkeypatch):
    """The sensitivity (min_detectable, power) reads no data; every test function is trapped."""

    def trap(name):
        def called(*args, **kwargs):
            raise AssertionError(f"paper_numbers called the notebook's {name}()")

        return called

    for name in (
        "crossover",
        "run",
        "permutation_p",
        "tost",
        "wilcoxon",
        "holm",
        "analyse",
        "main",
    ):
        monkeypatch.setattr(sig, name, trap(name))
    assert _numbers(built, tmp_path / "numbers.tex") == 0
    assert not IMPORTS_SCIPY.search(NUMBERS.read_text(encoding="utf-8")), "no test library"


def test_numbers_refuse_what_the_descriptives_refuse(built, tmp_path, capsys):
    study = _copy(built, tmp_path)
    path = study["derived"] / "significance.txt"
    path.write_text(path.read_text(encoding="utf-8").replace(": n = 24", ": n = 25", 1))
    out = tmp_path / "numbers.tex"
    assert _numbers(study, out) == 1
    assert "does not match significance.txt" in capsys.readouterr().err
    assert not out.exists()


# --- scripts/paper_figures.py: paper/tables/ and paper/figures/ --------------------------------
TABLES = ("tests", "secondary", "exclusions", "items", "items-pre", "survey", "survey-pre")
DRAWN = ("style", "accuracy", "effort", "items", "time")
COORDINATES = re.compile(r"coordinates \{([^}]*)\}")
POINT = re.compile(r"\((-?[\d.]+),(-?[\d.]+)\)")


def _figures(study: dict, numbers: Path, out: Path) -> int:
    return figures_script.main(
        [
            "--derived",
            str(study["derived"]),
            "--coding",
            str(study["coding"]),
            "--numbers",
            str(numbers),
            "--out",
            str(out),
            "--no-browser",
        ]
    )


@pytest.fixture(scope="module")
def figured(built, numbered, tmp_path_factory) -> Path:
    """paper/tables/ and paper/figures/ written from the made-up study, Figure 1 left out."""
    out = tmp_path_factory.mktemp("paper")
    assert _figures(built, built["out"].parent / "numbers.tex", out) == 0
    return out


def _generated(out: Path) -> dict[str, str]:
    files = [f"tables/{name}.tex" for name in TABLES] + [f"figures/{name}.tex" for name in DRAWN]
    return {name: (out / name).read_text(encoding="utf-8") for name in files}


def test_figures_write_every_table_and_figure_and_mark_each_generated(figured):
    for name, text in _generated(figured).items():
        assert text.startswith("% GENERATED by scripts/paper_figures.py"), name
    assert not (figured / "figures" / "versions.tex").exists(), "--no-browser leaves Figure 1"


def test_tables_cite_only_numbers_numbers_tex_defines_and_type_none(figured, numbered):
    """Every number in a table is a \\stat; what is left is layout, item names and the two
    interval levels."""
    defined = _defined(numbered)
    layout = (
        r"\\stat\{[^{}]+\}",
        r"\\multicolumn\{\d+\}",
        r"\\cmidrule\([a-z]*\)\{\d+-\d+\}",
        r"p\{0\.\d+\\(?:line|text)width\}",
        r"\b(?:T[1-6]|a[1-9]|b[1-4]|c[1-3]|RQ[1-3])\b",
        r"\b9[05]\\%",
        r"participant 19",
    )
    for name in TABLES:
        text = (figured / "tables" / f"{name}.tex").read_text(encoding="utf-8")
        used = set(STAT.findall(text))
        assert used and not used - set(defined), f"{name}: {sorted(used - set(defined))}"
        body = "\n".join(line for line in text.splitlines() if not line.startswith("%"))
        for pattern in layout:
            body = re.sub(pattern, "", body)
        typed = re.findall(r".{0,20}\d", body)
        assert not typed, f"{name} types a number: {typed}"
    # Each analysis's table cites its own keys only.
    for name in ("items", "survey"):
        main = (figured / "tables" / f"{name}.tex").read_text(encoding="utf-8")
        pre = (figured / "tables" / f"{name}-pre.tex").read_text(encoding="utf-8")
        assert not re.search(r"\\stat\{pre/", main) and not re.search(r"\\stat\{main/", pre)


def test_figures_carry_no_text_no_id_and_count_people_per_value(figured, built):
    generated = _generated(figured)
    for name, text in generated.items():
        assert SECRET not in text and paper.TEXT_MARKER not in text, name
    run = paper.parse_significance(
        (built["derived"] / "significance.txt").read_text(encoding="utf-8"), sig.LABELS
    )
    # The accuracy dots: a stack per value, 1, 2, ... high, one dot per participant, no names.
    dots = POINT.findall(COORDINATES.search(generated["figures/accuracy.tex"])[1])
    stacks: dict[float, list[int]] = {}
    for x, y in dots:
        stacks.setdefault(float(x), []).append(int(y))
    assert all(ys == list(range(1, len(ys) + 1)) for ys in stacks.values())
    assert len(dots) == run["main"]["n"]
    # The time ratios: one per participant with a time, sorted by value, so no row is a person's.
    drawn = COORDINATES.search(generated["figures/time.tex"])[1]
    ratios = [float(x) for x, _ in POINT.findall(drawn)]
    assert ratios == sorted(ratios)
    assert len(ratios) == int(run["main"]["outcomes"]["log_time"]["n"])
    # The estimates drawn are the run's, as printed.
    items = run["main"]["lines"]["items"]
    assert f"coordinates {{({float(items['est']):g}," in generated["figures/accuracy.tex"]


def test_figures_refuse_a_numbers_tex_that_is_not_current(built, numbered, tmp_path, capsys):
    items = r"\defstat{design/items}{6}"
    assert items in numbered
    stale = tmp_path / "numbers.tex"
    stale.write_text(numbered.replace(items, items.replace("6", "7")), encoding="utf-8")
    out = tmp_path / "paper"
    assert _figures(built, stale, out) == 1
    assert "run it first" in capsys.readouterr().err
    assert not out.exists(), "nothing written"


def test_figures_never_call_one_of_the_notebooks_tests(built, numbered, tmp_path, monkeypatch):
    def trap(name):
        def called(*args, **kwargs):
            raise AssertionError(f"paper_figures called the notebook's {name}()")

        return called

    for name in NOTEBOOK_TESTS[:8]:  # the eight that read data; the sensitivity's two do not
        monkeypatch.setattr(sig, name, trap(name))
    assert _figures(built, built["out"].parent / "numbers.tex", tmp_path) == 0
    assert not IMPORTS_SCIPY.search(FIGURES.read_text(encoding="utf-8")), "no test library"


def test_figure_colours_hold_the_apps_floors(monkeypatch):
    figures_script.check_palette()
    monkeypatch.setitem(figures_script.COLOURS, "staticcolour", "#F0B0A0")  # 1.9:1 on white
    with pytest.raises(figures_script.FiguresError, match="staticcolour"):
        figures_script.check_palette()


def test_figure_1_draws_both_versions_with_the_apps_screen_code():
    questionnaire = figures_script._load(
        "export_questionnaire", ROOT / "scripts" / "export_questionnaire.py"
    )
    page = figures_script.versions_html(questionnaire)
    sections = re.findall(r'<section data-version="(\w+)">(.*?)</section>', page, flags=re.DOTALL)
    assert [version for version, _ in sections] == ["static", "interactive"]
    static, interactive = (body for _, body in sections)
    # The same chart in both; the controls under it in the interactive version only.
    assert static.count('class="chart"') == interactive.count('class="chart"') == 1
    assert "ui-controls" in interactive and "ui-controls" not in static
    assert 'setAttribute("data-crops"' in page


def test_figure_1_crops_to_the_card_it_measured():
    crop = {"version": "static", "x": 24, "y": 90, "w": 1080, "h": 540, "section": 700}
    # 1440 x 1100 CSS px is 1080 x 825 points: keep x 18-828 and y 67.5-472.5 from the top.
    assert figures_script.trims(crop, (1080.0, 825.0)) == (18.0, 352.5, 252.0, 67.5)
    with pytest.raises(figures_script.FiguresError, match="runs off"):
        figures_script.trims({**crop, "w": 1500}, (1080.0, 825.0))
    crops = [crop, {**crop, "version": "interactive"}]
    dom = f'<body data-crops="{html.escape(json.dumps(crops))}">'
    assert figures_script.read_crops(dom) == crops
    with pytest.raises(figures_script.FiguresError, match="one page"):
        figures_script.read_crops(dom.replace("700", "1200"))
    with pytest.raises(figures_script.FiguresError, match="did Plotly draw"):
        figures_script.read_crops("<body>")
    pdf = b"<< /Type /Page /MediaBox [0 0 1080 824.88] >> << /MediaBox [ 0 0 1080 825 ] >>"
    assert figures_script.page_boxes(pdf) == [(1080.0, 824.88), (1080.0, 825.0)]


def test_every_number_the_paper_uses_is_in_numbers_tex():
    """The committed paper: each \\stat{key} in main.tex, outline.md, deviations.md and the
    generated tables is defined in numbers.tex, so nothing can print a number the generator did not
    write."""
    numbers = PAPER / "numbers.tex"
    if not numbers.exists():
        pytest.skip("paper/numbers.tex not generated yet")
    defined = _defined(numbers.read_text(encoding="utf-8"))
    for name in ("main.tex", "outline.md", "deviations.md", *(f"tables/{t}.tex" for t in TABLES)):
        path = PAPER / name
        if not path.exists():
            continue
        used = set(STAT.findall(path.read_text(encoding="utf-8")))
        assert used, f"{name} cites no number"
        assert not used - set(defined), f"{name}: {sorted(used - set(defined))}"


def test_every_file_main_tex_reads_is_in_the_repository():
    """Each \\input and \\includegraphics in main.tex and in the generated files names a file that
    exists, so the committed paper builds without the study data."""
    reads = re.compile(r"\\(input|includegraphics)(?:\[[^\]]*\])?\{([^}]+)\}")
    sources = [PAPER / "main.tex", *sorted((PAPER / "figures").glob("*.tex"))]
    for source in sources:
        if not source.exists():
            continue
        body = _tex_body(source.read_text(encoding="utf-8"))
        for command, name in reads.findall(body):
            path = PAPER / name
            if command == "input" and not path.suffix:
                path = path.with_suffix(".tex")
            assert path.exists(), f"{source.name} reads {name}, which is missing"


# --- paper/main.tex and paper/references.bib, checked without a TeX installation ---------------
BIB_ENTRY = re.compile(r"^@(\w+)\{([^,\s]+),", flags=re.MULTILINE)
PROPOSAL_GROUP = "% ===== 1."
OTHER_GROUPS = "% ===== 2."


def _tex_body(text: str) -> str:
    """main.tex without its comments and code listings, whose characters LaTeX does not parse."""
    text = re.sub(r"\\begin\{lstlisting\}.*?\\end\{lstlisting\}", "", text, flags=re.DOTALL)
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def _paper_file(name: str) -> str:
    path = PAPER / name
    if not path.exists():
        pytest.skip(f"paper/{name} not written yet")
    return path.read_text(encoding="utf-8")


def test_main_tex_cites_only_references_that_exist_and_every_ref_has_its_label():
    body = _tex_body(_paper_file("main.tex"))
    keys = {key for _kind, key in BIB_ENTRY.findall(_paper_file("references.bib"))}
    cited = {
        k.strip() for group in re.findall(r"\\cite\{([^}]*)\}", body) for k in group.split(",")
    }
    assert cited and not cited - keys, sorted(cited - keys)
    labels = set(re.findall(r"\\label\{([^}]*)\}", body))
    refs = set(re.findall(r"\\ref\{([^}]*)\}", body))
    assert refs and not refs - labels, sorted(refs - labels)


def test_main_tex_balances_its_braces_and_environments():
    body = _tex_body(_paper_file("main.tex"))
    depth = 0
    for char in body.replace(r"\{", "").replace(r"\}", ""):
        depth += {"{": 1, "}": -1}.get(char, 0)
        assert depth >= 0, "a } closes nothing"
    assert depth == 0, "a { is never closed"
    opened = re.findall(r"\\begin\{([^}]*)\}", body)
    closed = re.findall(r"\\end\{([^}]*)\}", body)
    assert sorted(opened) == sorted(closed)


def test_main_tex_marks_every_claude_draft_from_beginning_to_end():
    text = _paper_file("main.tex")
    marks = re.findall(r"^% (BEGIN|END) CLAUDE DRAFT", text, flags=re.MULTILINE)
    assert marks and marks == ["BEGIN", "END"] * (len(marks) // 2), (
        "drafts must not nest or overlap"
    )


def test_references_are_unique_balanced_and_verify_is_on_every_one_outside_the_proposal():
    text = _paper_file("references.bib")
    entries = BIB_ENTRY.findall(text)
    keys = [key for _kind, key in entries]
    assert len(keys) == len(set(keys))
    assert text.count("{") == text.count("}")
    proposal = text.split(PROPOSAL_GROUP, 1)[1].split(OTHER_GROUPS, 1)[0]
    assert len(BIB_ENTRY.findall(proposal)) == 37, "the proposal cites 37 references"
    others = text.split(OTHER_GROUPS, 1)[1]
    for block in re.split(r"\n(?=@)", others)[1:]:
        before = others[: others.index(block)].rstrip().splitlines()[-1]
        assert before.startswith("% VERIFY"), f"no % VERIFY above {block.splitlines()[0]}"
