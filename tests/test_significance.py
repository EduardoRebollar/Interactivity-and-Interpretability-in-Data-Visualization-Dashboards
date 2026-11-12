"""Tests for notebooks/significance.py: error rates hold, and so do the plan's guards.

The confirmatory run happens once, on real data, so everything it relies on is checked here on
made-up data first: a false-positive rate near alpha when practice and form effects are present
and the cells are unequal; power near what the sensitivity table promises; the same estimate as a
random-intercept mixed model; and refusals for uncoded T1 answers and a run below the stopping n.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("scipy")

_PATH = Path(__file__).resolve().parent.parent / "notebooks" / "significance.py"
_spec = importlib.util.spec_from_file_location("significance", _PATH)
sig = importlib.util.module_from_spec(_spec)
sys.modules["significance"] = sig  # dataclasses look their module up here
_spec.loader.exec_module(sig)


def _diffs(
    cells: dict[tuple[float, float], int], effect: float, half: float, form: float, rng
) -> pd.DataFrame:
    rows = []
    for (h, f), count in cells.items():
        for _ in range(count):
            rows.append({"d": effect + half * h + form * f + rng.normal(0, 1), "h": h, "f": f})
    return pd.DataFrame(rows)


UNEQUAL = {(-1.0, -1.0): 7, (-1.0, 1.0): 6, (1.0, -1.0): 6, (1.0, 1.0): 5}
EQUAL = {(-1.0, -1.0): 6, (-1.0, 1.0): 6, (1.0, -1.0): 6, (1.0, 1.0): 6}


def test_false_positive_rate_is_alpha_with_practice_form_and_unequal_cells():
    rng = np.random.default_rng(1)
    reps = 4000
    hits = sum(
        sig.crossover(_diffs(UNEQUAL, 0.0, 0.5, 0.7, rng), "x").p < 0.05 for _ in range(reps)
    )
    # 95% Monte Carlo band around 0.05 for 4000 reps is about +/- 0.007.
    assert abs(hits / reps - 0.05) < 0.01


def test_the_unadjusted_mean_difference_is_biased_when_cells_are_unequal():
    """Why the adjustment: with form A easier and unequal cells, the plain mean leaks the form
    difference into the condition effect; the intercept does not."""
    rng = np.random.default_rng(2)
    cells = {(-1.0, -1.0): 10, (-1.0, 1.0): 2, (1.0, -1.0): 10, (1.0, 1.0): 2}
    plain, adjusted = [], []
    for _ in range(2000):
        diffs = _diffs(cells, 0.0, 0.0, 1.0, rng)
        plain.append(diffs["d"].mean())
        adjusted.append(sig.crossover(diffs, "x").estimate)
    assert abs(np.mean(adjusted)) < 0.03
    assert np.mean(plain) < -0.5


def test_power_matches_the_sensitivity_table():
    dz = sig.min_detectable(24)
    assert dz == pytest.approx(0.60, abs=0.01)
    rng = np.random.default_rng(3)
    reps = 3000
    hits = sum(sig.crossover(_diffs(EQUAL, dz, 0.3, 0.3, rng), "x").p < 0.05 for _ in range(reps))
    assert abs(hits / reps - 0.80) < 0.03


def test_same_estimate_as_a_random_intercept_mixed_model():
    smf = pytest.importorskip("statsmodels.formula.api")
    tasks, conditions, depth = sig.simulate(per_cell=6, seed=11)
    scores = sig.participant_scores(tasks, conditions, depth)
    ours = sig.crossover(sig.differences(scores, "paas"), "paas")
    long = scores.assign(
        interactive=(scores["condition"] == "interactive").astype(float),
        second=(scores["condition_order"] == 2).astype(float),
        formB=(scores["form"] == "B").astype(float),
    )
    fit = smf.mixedlm(
        "paas ~ interactive + second + formB", long, groups=long["participant_id"]
    ).fit(reml=True)
    assert ours.estimate == pytest.approx(fit.params["interactive"], abs=1e-6)
    assert ours.se == pytest.approx(fit.bse["interactive"], rel=0.02)


def test_simulated_effects_are_recovered():
    tasks, conditions, depth = sig.simulate(per_cell=200, seed=5, paas_shift=-1.3)
    scores = sig.participant_scores(tasks, conditions, depth)
    paas = sig.crossover(sig.differences(scores, "paas"), "paas")
    assert paas.ci95[0] < -1.0 < paas.ci95[1] or abs(paas.estimate + 1.25) < 0.2
    assert paas.estimate < -1.0


def test_holm_by_hand():
    adjusted = sig.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})


def test_wilcoxon_rank_biserial_and_all_zero_differences():
    p, r = sig.wilcoxon(np.array([1.0, 2.0, 0.5, 3.0, 1.5, 2.5]))
    assert r == 1.0 and p < 0.05
    assert sig.wilcoxon(np.zeros(10)) == (1.0, 0.0)


def test_tost_inside_and_outside_the_bound():
    tasks, conditions, depth = sig.simulate(per_cell=6, seed=7, accuracy_logit=0.0)
    scores = sig.participant_scores(tasks, conditions, depth)
    acc = sig.crossover(sig.differences(scores, "accuracy"), "accuracy")
    inside, _ = sig.tost(acc, 10.0)
    outside, _ = sig.tost(acc, 1e-4)
    assert inside and not outside


def test_refuses_uncoded_t1():
    tasks, conditions, depth = sig.simulate(per_cell=6)
    tasks.loc[(tasks["task_id"] == "T1") & (tasks["participant_id"] == "3"), "correct"] = pd.NA
    scores = sig.participant_scores(tasks, conditions, depth)
    with pytest.raises(sig.PlanError, match="uncoded"):
        sig.check_ready(tasks, scores, interim=False)


def test_refuses_a_run_below_the_stopping_n_unless_interim():
    tasks, conditions, depth = sig.simulate(per_cell=5)
    scores = sig.participant_scores(tasks, conditions, depth)
    with pytest.raises(sig.PlanError, match="stopping n"):
        sig.check_ready(tasks, scores, interim=False)
    assert "INTERIM" in sig.check_ready(tasks, scores, interim=True)[0]


def test_the_stopping_n_counts_participants_with_data_not_usable_ones():
    """Collection closed at 24. As pre-registered 23 are usable, which is no interim look."""
    tasks, conditions, depth = sig.simulate(per_cell=6, empty_session_for="19")
    scores = sig.participant_scores(tasks, conditions, depth)
    assert scores["participant_id"].nunique() == 23
    assert sig.check_ready(tasks, scores, interim=False) == []


def test_excluded_rows_leave_accuracy_and_depth_and_missing_paas_drops_one_outcome_only():
    tasks, conditions, depth = sig.simulate(per_cell=6, seed=9)
    one = tasks.index[(tasks["participant_id"] == "1") & (tasks["task_id"] == "T2")]
    tasks.loc[one, ["use_accuracy", "use_timing"]] = False  # as too_fast marks a row
    conditions.loc[conditions["participant_id"] == "2", "paas"] = np.nan  # a skipped Paas
    scores = sig.participant_scores(tasks, conditions, depth)
    session = tasks.loc[one, "session_id"].iloc[0]
    kept = tasks[(tasks["session_id"] == session) & tasks["use_accuracy"]]
    row = scores[scores["session_id"] == session].iloc[0]
    assert row["accuracy"] == pytest.approx(kept["correct"].astype(float).mean())
    coded = depth[
        (depth["session_id"] == session)
        & depth["task_id"].isin(sig.DEPTH_PRIMARY_TASKS)
        & (depth["task_id"] != "T2")
    ]
    assert row["depth"] == pytest.approx(coded["depth"].mean())
    assert len(sig.differences(scores, "paas")) == 23
    assert len(sig.differences(scores, "accuracy")) == 24


def test_holm_is_withheld_when_a_confirmatory_outcome_is_missing():
    tasks, conditions, _ = sig.simulate(per_cell=6)
    results, adjusted = sig.run(sig.participant_scores(tasks, conditions, None))
    assert "depth" not in results and adjusted == {}
    assert "Holm not applied" in sig.render(results, adjusted, [])


def test_permutation_check_holds_alpha_on_accuracy_like_data():
    """Few possible values and many zero differences, no real effect: about 5% significant."""
    rng = np.random.default_rng(21)
    sims, hits = 400, 0
    for _ in range(sims):
        rows = []
        for h, f in EQUAL:
            for _ in range(EQUAL[(h, f)]):
                ability = rng.normal(1.3, 0.9)
                p_first = 1 / (1 + np.exp(-(ability + 0.1 * 0)))
                p_second = 1 / (1 + np.exp(-(ability + 0.1)))
                first, second = rng.binomial(5, p_first) / 5, rng.binomial(5, p_second) / 5
                d = second - first if h == 1 else first - second
                rows.append({"d": d, "h": h, "f": f})
        hits += sig.permutation_p(pd.DataFrame(rows), reps=999, seed=int(rng.integers(1e9))) < 0.05
    assert abs(hits / sims - 0.05) < 0.03


def test_permutation_check_agrees_with_the_t_test_on_normal_data():
    """Exact and approximate p-values differ dataset by dataset, but not on average."""
    rng = np.random.default_rng(22)
    gaps = []
    for _ in range(30):
        diffs = _diffs(EQUAL, 0.4, 0.3, 0.3, rng)
        perm = sig.permutation_p(diffs, reps=4000, seed=int(rng.integers(1_000_000)))
        gaps.append(perm - sig.crossover(diffs, "x").p)
    assert abs(np.mean(gaps)) < 0.01
    assert np.max(np.abs(gaps)) < 0.05


def test_permutation_check_is_reported_for_accuracy():
    tasks, conditions, depth = sig.simulate(per_cell=6)
    results, adjusted = sig.run(sig.participant_scores(tasks, conditions, depth))
    assert 0 < results["accuracy"].permutation_p <= 1
    assert "permutation check" in sig.render(results, adjusted, [])


def test_depth_codes_match_the_repo():
    coding = pytest.importorskip("analysis.coding")
    assert sig.DEPTH_CODES == coding.CODES


def test_reinstating_participant_19_restores_their_answers_and_only_theirs():
    tasks, conditions, depth = sig.simulate(per_cell=6, empty_session_for="19")
    pre = tasks[tasks["participant_id"] == "19"]
    assert not pre["use_accuracy"].any()  # incomplete_session, as pre-registered
    reinstated, kept = sig.reinstate(tasks, conditions)
    assert reinstated.loc[reinstated["participant_id"] == "19", "use_accuracy"].all()
    assert "s19-empty" not in set(kept["session_id"])
    others = reinstated["participant_id"] != "19"
    assert (reinstated.loc[others, "use_accuracy"] == tasks.loc[others, "use_accuracy"]).all()
    with_them = sig.participant_scores(reinstated, kept, depth)
    without = sig.participant_scores(tasks, conditions, depth)
    assert with_them["participant_id"].nunique() == 24
    assert without["participant_id"].nunique() == 23


def test_the_reinstated_list_is_the_one_the_coding_scripts_use():
    exclusions = pytest.importorskip("analysis.exclusions")
    assert sig.REINSTATED == exclusions.REINSTATED


def test_main_refuses_when_a_reinstated_participant_has_no_codes(tmp_path, capsys):
    """Without the guard, RQ2 would run quietly on one participant fewer than RQ1 and RQ3."""
    tasks, conditions, depth = sig.simulate(per_cell=6, empty_session_for="19")
    tasks.to_csv(tmp_path / "tasks.csv", index=False)
    conditions.to_csv(tmp_path / "conditions.csv", index=False)
    depth[depth["participant_id"] != "19"].to_csv(tmp_path / "depth.csv", index=False)
    assert sig.main(["--derived", str(tmp_path), "--depth", str(tmp_path / "depth.csv")]) == 1
    captured = capsys.readouterr()
    assert "Reinstated but not in depth.csv: ['19']" in captured.err
    assert captured.out == "", "nothing computed, nothing printed"


def test_reinstating_refuses_a_participant_still_incomplete_without_the_empty_session():
    tasks, conditions, _ = sig.simulate(per_cell=6, empty_session_for="19")
    missing = tasks[~((tasks["participant_id"] == "19") & (tasks["task_id"] == "T6"))]
    with pytest.raises(sig.PlanError, match="Still incomplete"):
        sig.reinstate(missing.reset_index(drop=True), conditions)


def test_new_secondaries_are_scored_per_participant():
    tasks, conditions, depth = sig.simulate(per_cell=6)
    scores = sig.participant_scores(tasks, conditions, depth)
    t1 = tasks[tasks["task_id"] == "T1"].set_index("session_id")["t1_parts"]
    by_session = scores.set_index("session_id")["t1_parts"]
    assert by_session.to_dict() == pytest.approx(t1.astype(float).to_dict())
    primary = depth[depth["task_id"] != "T1"]
    share = primary.groupby("session_id")["cites_values"].mean()
    assert scores.set_index("session_id")["cites_values"].to_dict() == pytest.approx(
        share.to_dict()
    )
    assert depth["depth"].max() <= 2


def test_ceiling_counts_participants_with_every_item_right():
    tasks, conditions, depth = sig.simulate(per_cell=6, seed=13)
    scores = sig.participant_scores(tasks, conditions, depth)
    top = sig.ceiling(scores)
    assert list(top) == ["static", "interactive"]
    for condition, (k, n) in top.items():
        own = scores[scores["condition"] == condition]
        assert n == own["accuracy"].notna().sum() == 24
        assert k == (own["accuracy"] == 1).sum()
    assert "All items right (ceiling): static" in "\n".join(sig.describe(scores))


def test_a_degraded_session_re_runs_timing_without_it_and_none_adds_nothing():
    """Section 7: a degraded session is reported, not excluded; timing is re-run without it."""
    tasks, conditions, depth = sig.simulate(per_cell=6)
    clean = sig.participant_scores(tasks, conditions, depth)
    assert "log_time_not_degraded" not in clean
    assert "Degraded sessions (logger spooled): 0" in "\n".join(sig.describe(clean))

    conditions.loc[conditions["session_id"] == "s5-2", "degraded"] = True
    scores = sig.participant_scores(tasks, conditions, depth)
    rerun = scores.set_index("session_id")["log_time_not_degraded"]
    assert np.isnan(rerun["s5-2"])
    assert rerun.drop("s5-2").to_dict() == pytest.approx(
        scores.set_index("session_id")["log_time"].drop("s5-2").to_dict()
    )
    results, _ = sig.run(scores)
    assert results["log_time_not_degraded"].n == 23  # participant 5 leaves this outcome only
    assert results["log_time"].n == 24
    assert "Degraded sessions (logger spooled): 1" in "\n".join(sig.describe(scores))


def test_the_equivalence_verdict_uses_the_holm_p_not_the_raw_one():
    tasks, conditions, depth = sig.simulate(per_cell=6)
    results, adjusted = sig.run(sig.participant_scores(tasks, conditions, depth))
    results["accuracy"] = replace(results["accuracy"], p=0.01)
    held = sig.render(results, {**adjusted, "accuracy": 0.2}, [])
    assert "a real difference" not in held and "may reach the bound" not in held
    passed = sig.render(results, {**adjusted, "accuracy": 0.01}, [])
    assert "a real difference" in passed or "may reach the bound" in passed
    withheld = sig.render(results, {}, [])
    assert "Holm withheld: judged on the unadjusted p" in withheld


def test_rq3_rather_than_needs_paas_to_fall_and_accuracy_to_be_equivalent():
    big = {"per_cell": 60, "seed": 4, "accuracy_logit": 0.0}
    results, adjusted = sig.run(sig.participant_scores(*sig.simulate(paas_shift=-2.0, **big)))
    assert "accuracy equivalent yes -> supported" in sig.render(results, adjusted, [])
    results, adjusted = sig.run(sig.participant_scores(*sig.simulate(paas_shift=0.0, **big)))
    assert "Paas falls no" in sig.render(results, adjusted, [])
    assert "-> not supported" in sig.render(results, adjusted, [])


def test_main_reads_the_pipeline_csvs_and_prints_both_analyses(tmp_path, capsys):
    tasks, conditions, depth = sig.simulate(per_cell=6, empty_session_for="19")
    tasks.to_csv(tmp_path / "tasks.csv", index=False)
    conditions.to_csv(tmp_path / "conditions.csv", index=False)
    depth.to_csv(tmp_path / "depth.csv", index=False)
    assert sig.main(["--derived", str(tmp_path), "--depth", str(tmp_path / "depth.csv")]) == 0
    out = capsys.readouterr().out
    assert "MAIN: with participant 19 (deviation): n = 24" in out
    assert "AS PRE-REGISTERED: without participant 19: n = 23" in out
    assert "T1 parts score" in out and "Cites values" in out
    assert out.count("All items right (ceiling)") == 2 and "RQ3 'rather than'" in out
