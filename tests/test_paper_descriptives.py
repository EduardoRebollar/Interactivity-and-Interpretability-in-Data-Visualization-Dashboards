"""Tests for scripts/paper_descriptives.py: the paper's exploratory descriptives
(paper/exploratory.md, items 1 to 7).

The script runs on study data once, so everything it computes is checked here first, on made-up
files shaped like the pipeline's, with significance.txt printed by the notebook's own main(): each
item on planted cases; the checks that make it refuse to write when its inputs disagree with
significance.txt, tasks.csv or the coding sheets; that it never calls one of the notebook's tests;
and that no free text reaches an output.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import math
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
    assert "scipy" not in SCRIPT.read_text(encoding="utf-8")


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


def test_masking_keeps_whether_something_was_written_and_nothing_else():
    frame = pd.DataFrame({"kind": ["describe", "rank", "describe"], "answer": ["text", "B", None]})
    masked = paper.mask(frame, ["answer"], rows=frame["kind"] == "describe")
    assert masked["answer"].tolist()[:2] == [paper.TEXT_MARKER, "B"]
    assert pd.isna(masked["answer"].iloc[2])
