"""Significance tests: the analysis notebook `analysis/report.py` defers inference to.

The plan is "Statistical Significance Plan" (drafted 2026-11-03, updated 2026-11-11). Write its
choices into `docs/study-design.md` section 7 and commit them *before* this is run on study data:
every choice is a named constant below, so that commit is the record of what was decided first.

Run it once, after the T1 descriptions and the justifications are graded (`docs/grading-rules.md`).
It reads the frames the existing pipeline writes and never touches the database:

    data/study_logs/derived/tasks.csv        scripts/score_study.py (exclusions marked; t1_parts)
    data/study_logs/derived/conditions.csv   scripts/score_study.py (Paas; each session's status)
    data/study_logs/derived/participants.csv scripts/score_study.py (E1, for the sensitivity check)
    data/study_logs/coding/depth.csv         scripts/code_justifications.py depth (RQ2)

Every analysis runs twice (`REINSTATED`): with participant 19, the deviation and main analysis
(their empty duplicate session dropped and every exclusion rule re-run, as the poster export does),
and as pre-registered, without them.

What it does, per outcome: one score per participant per condition, the difference interactive
minus static, and that difference regressed on which half and which form the interactive
condition got (the two-period crossover analysis). The intercept is the effect of interactivity.
A Wilcoxon signed-rank test on the raw differences is the check, and accuracy also gets a
permutation test. Holm across the three main tests; a TOST on accuracy for RQ3's "rather than".

Usage:
    uv run python notebooks/significance.py                 # the study data
    uv run python notebooks/significance.py --simulate      # made-up data: see the output safely
    uv run python notebooks/significance.py --sensitivity   # what each n can detect

Needs scipy, which is not yet a dependency: `uv add --dev scipy` (dev group, never shipped).

Cells are marked `# %%`, so the file opens as a notebook in VS Code or Jupyter as well.
"""

# %% Setup
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # the repo's own exclusion rules, as scripts/ import them
    sys.path.insert(0, str(ROOT))
DERIVED = ROOT / "data" / "study_logs" / "derived"
CODING = ROOT / "data" / "study_logs" / "coding"

# --- The plan's open choices (settle with the supervisor, then commit) -------------------------

ALPHA = 0.05
# The stopping rule: participants with data. Collection closed at 24, 6 per counterbalancing cell
# (2026-11-10). Fewer means an interim look, refused unless --interim stamps the output as one.
STOP_N = 24
# The deviation (Eduardo, 2026-11-10; poster_export/codebook.md): participant 19's interactive half
# was opened twice within a second, leaving an empty third session, so the pre-registered
# incomplete_session rule takes out all 12 of their answers. Main analysis: that session dropped and
# every rule re-run. Reported beside it: the rules as pre-registered, without participant 19.
REINSTATED = ("19",)
# RQ3's "rather than": the accuracy effect is negligible if its 90% CI sits inside this bound,
# in proportion correct. 1/6 = one item of six.
EQUIVALENCE_BOUND = 1 / 6
ITEMS_PER_CONDITION = 6
# The Holm family: the three confirmatory tests, one per research question. Fixed by the plan, so
# a missing outcome stops the correction rather than shrinking the family.
CONFIRMATORY = ("accuracy", "depth", "paas")
# RQ2's primary score leaves T1 out (it almost always codes compares_series); with T1 is secondary.
DEPTH_PRIMARY_TASKS = ("T2", "T3", "T4", "T5", "T6")
# The codes depth sums: analysis/coding.py CODES since notes_uncertainty was dropped
# (docs/grading-rules.md section 1 item 5), so depth runs 0-2. A test ties the two together.
DEPTH_CODES = ("cites_values", "compares_series")
# Accuracy's extra check: a randomization test, with a fixed seed so the p-value reproduces.
PERMUTATION_REPS = 10_000
PERMUTATION_SEED = 2026
HEARD_COLUMN, HEARD_YES = "heard_details", "Yes"  # src/tasks.py HEARD_KEY, HEARD_YES

LABELS = {
    "accuracy": "RQ1 accuracy (proportion correct, T1-T6)",
    "depth": "RQ2 reasoning depth (0-2, T2-T6)",
    "paas": "RQ3 mental effort (Paas 1-9)",
    "log_time": "Time on task (geometric mean, T1-T6)",
    "accuracy_answered": "Accuracy, answered items only",
    "accuracy_no_heard": "Accuracy, without E1 'Yes'",
    "t1_parts": "T1 parts score (0-3)",
    "depth_with_t1": "Reasoning depth (0-2) with T1",
    "cites_values": "Cites values (share, T2-T6)",
    "compares_series": "Compares countries (share, T2-T6)",
}


class PlanError(RuntimeError):
    """The data are not ready for the confirmatory run, so it is refused, not approximated."""


# %% Per-participant scores
def _as_correct(column: pd.Series) -> pd.Series:
    """tasks.csv writes a nullable boolean: True, False, or blank for an uncoded T1."""
    mapped = column.map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0})
    return mapped.astype(float)


def _proportion_if_coded(values: pd.Series) -> float:
    return float("nan") if values.isna().any() else float(values.mean())


def participant_scores(
    tasks: pd.DataFrame,
    conditions: pd.DataFrame,
    depth: pd.DataFrame | None = None,
    participants: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per participant x condition: every score a test below runs on.

    Follows `analysis/report.py`: accuracy over the rows `use_accuracy` keeps, NaN while any of
    them is uncoded; Paas and depth for participants with at least one usable row; time over the
    rows `use_timing` keeps.
    """
    tasks = tasks.copy()
    tasks["participant_id"] = tasks["participant_id"].astype(str)
    tasks["session_id"] = tasks["session_id"].astype(str)
    tasks["correct01"] = _as_correct(tasks["correct"])
    usable = tasks[tasks["use_accuracy"].astype(bool)]
    included = set(usable["participant_id"])

    keys = ["participant_id", "session_id", "condition", "condition_order", "form"]
    scores = usable.drop_duplicates("session_id")[keys].copy()
    by_session = usable.groupby("session_id")
    scores["accuracy"] = scores["session_id"].map(by_session["correct01"].agg(_proportion_if_coded))
    answered = usable[~usable["skipped_answer"].astype(bool)]
    scores["accuracy_answered"] = scores["session_id"].map(
        answered.groupby("session_id")["correct01"].agg(_proportion_if_coded)
    )
    scores["n_uncoded"] = scores["session_id"].map(
        by_session["correct01"].agg(lambda c: c.isna().sum())
    )

    if "t1_parts" in usable:
        t1 = usable[(usable["task_id"] == "T1") & usable["t1_parts"].notna()]
        parts = pd.to_numeric(t1["t1_parts"], errors="coerce")
        scores["t1_parts"] = scores["session_id"].map(parts.groupby(t1["session_id"]).mean())

    timed = tasks[tasks["use_timing"].astype(bool) & tasks["duration_ms"].notna()]
    timed = timed[timed["participant_id"].isin(included)]
    log_seconds = np.log(timed["duration_ms"].astype(float) / 1000.0)
    scores["log_time"] = scores["session_id"].map(log_seconds.groupby(timed["session_id"]).mean())

    conds = conditions.copy()
    conds["session_id"] = conds["session_id"].astype(str)
    scores["paas"] = scores["session_id"].map(conds.set_index("session_id")["paas"]).astype(float)

    if depth is not None:
        coded = depth.copy()
        coded["session_id"] = coded["session_id"].astype(str)
        # Only answers the exclusions kept: a too-fast answer leaves every analysis.
        kept = set(zip(usable["session_id"], usable["task_id"], strict=True))
        coded = coded[[k in kept for k in zip(coded["session_id"], coded["task_id"], strict=True)]]
        primary = coded[coded["task_id"].isin(DEPTH_PRIMARY_TASKS)]
        scores["depth"] = scores["session_id"].map(primary.groupby("session_id")["depth"].mean())
        for code in DEPTH_CODES:
            if code in primary:
                share = primary.groupby("session_id")[code].mean()
                scores[code] = scores["session_id"].map(share)
        scores["depth_with_t1"] = scores["session_id"].map(
            coded.groupby("session_id")["depth"].mean()
        )

    heard: set[str] = set()
    if participants is not None and HEARD_COLUMN in participants:
        yes = participants[HEARD_COLUMN] == HEARD_YES
        heard = set(participants.loc[yes, "participant_id"].astype(str))
    scores["accuracy_no_heard"] = scores["accuracy"].where(~scores["participant_id"].isin(heard))
    return scores.sort_values(["participant_id", "condition_order"]).reset_index(drop=True)


def differences(scores: pd.DataFrame, column: str) -> pd.DataFrame:
    """Per participant: d = interactive - static, and the half and form the interactive one got.

    h = +1 if interactive came second, -1 if first; f = +1 if interactive used form B, -1 if A.
    A participant missing either condition's score drops out of this outcome only.
    """
    wide = scores.pivot(
        index="participant_id", columns="condition", values=[column, "condition_order", "form"]
    )
    out = pd.DataFrame(
        {
            "d": wide[(column, "interactive")] - wide[(column, "static")],
            "h": np.where(wide[("condition_order", "interactive")].astype(int) == 2, 1.0, -1.0),
            "f": np.where(wide[("form", "interactive")] == "B", 1.0, -1.0),
        },
        index=wide.index,
    )
    return out.dropna(subset=["d"])


# %% The tests
@dataclass(frozen=True)
class Result:
    outcome: str
    n: int
    estimate: float  # beta_0: interactive - static, adjusted for half and form
    se: float
    df: int
    t: float
    p: float
    ci95: tuple[float, float]
    ci90: tuple[float, float]
    dz: float  # estimate / residual SD
    half: float  # beta_half: second half minus first, the practice effect (descriptive)
    form: float  # beta_form: form B minus form A, the form difference (descriptive)
    wilcoxon_p: float
    rank_biserial: float
    cells: dict[str, int]
    permutation_p: float = float("nan")  # accuracy only: see permutation_p()


def _cells(diffs: pd.DataFrame) -> dict[str, int]:
    names = {
        (-1.0, -1.0): "int1-A",
        (-1.0, 1.0): "int1-B",
        (1.0, -1.0): "int2-A",
        (1.0, 1.0): "int2-B",
    }
    counts = diffs.groupby(["h", "f"]).size()
    return {names[k]: int(counts.get(k, 0)) for k in names}


def crossover(diffs: pd.DataFrame, outcome: str) -> Result:
    """Regress d on half and form; test the intercept. Same estimate as a random-intercept mixed
    model with fixed condition, half and form, since each participant gives one pair."""
    d = diffs["d"].to_numpy(float)
    covariates = [diffs[c].to_numpy(float) for c in ("h", "f")]
    # A covariate with one value (every participant in the same half, say) carries no information
    # and would make the design singular; it is left out and reported as NaN.
    usable = [np.ptp(c) > 0 for c in covariates]
    X = np.column_stack(
        [np.ones_like(d)] + [c for c, u in zip(covariates, usable, strict=True) if u]
    )
    n, k = X.shape
    if n - k < 2:
        raise PlanError(f"{outcome}: {n} participants cannot support {k} parameters")
    beta, *_ = np.linalg.lstsq(X, d, rcond=None)
    resid = d - X @ beta
    df = n - k
    sigma = math.sqrt(float(resid @ resid) / df)
    cov = sigma**2 * np.linalg.inv(X.T @ X)
    se = math.sqrt(cov[0, 0])
    t = beta[0] / se if se > 0 else (math.inf if beta[0] else float("nan"))
    p = float(2 * stats.t.sf(abs(t), df)) if math.isfinite(t) else (0.0 if beta[0] else 1.0)
    q95, q90 = stats.t.ppf(0.975, df), stats.t.ppf(0.95, df)
    extra = iter(beta[1:])
    half = next(extra) if usable[0] else float("nan")
    form = next(extra) if usable[1] else float("nan")
    w_p, r = wilcoxon(d)
    return Result(
        outcome=outcome,
        n=n,
        estimate=float(beta[0]),
        se=se,
        df=df,
        t=float(t),
        p=p,
        ci95=(beta[0] - q95 * se, beta[0] + q95 * se),
        ci90=(beta[0] - q90 * se, beta[0] + q90 * se),
        dz=float(beta[0] / sigma) if sigma > 0 else float("nan"),
        half=float(half),
        form=float(form),
        wilcoxon_p=w_p,
        rank_biserial=r,
        cells=_cells(diffs),
    )


def wilcoxon(d: np.ndarray) -> tuple[float, float]:
    """Signed-rank test (Pratt: zeros ranked, then dropped) and the matched-pairs rank-biserial."""
    if np.all(d == 0):
        return 1.0, 0.0
    p = float(stats.wilcoxon(d, zero_method="pratt").pvalue)
    nonzero = d[d != 0]
    ranks = stats.rankdata(np.abs(nonzero))
    r = float((ranks[nonzero > 0].sum() - ranks[nonzero < 0].sum()) / ranks.sum())
    return p, r


def tost(result: Result, bound: float) -> tuple[bool, float]:
    """Equivalent if the 90% CI lies inside +/- bound; p is the larger one-sided p."""
    lo = stats.t.sf((result.estimate + bound) / result.se, result.df)
    hi = stats.t.sf((bound - result.estimate) / result.se, result.df)
    inside = -bound < result.ci90[0] and result.ci90[1] < bound
    return inside, float(max(lo, hi))


def permutation_p(
    diffs: pd.DataFrame, reps: int = PERMUTATION_REPS, seed: int = PERMUTATION_SEED
) -> float:
    """Randomization test of the adjusted effect, assuming nothing about the shape of d.

    Under no effect of interactivity, each participant's two scores stay what they were whichever
    order they had been dealt within their form sequence (static A then interactive B, or
    interactive A then static B), so re-dealing it flips the sign of d, h and f together. The
    p-value is the share of re-deals whose adjusted effect (as a t statistic) is at least as far
    from zero as the one observed (two-sided, +1 so it is never 0). Suits accuracy, which takes
    only a few values.
    """
    d = diffs["d"].to_numpy(float)
    covariates = [c for c in (diffs["h"].to_numpy(float), diffs["f"].to_numpy(float)) if np.ptp(c)]

    def effect(signs: np.ndarray) -> np.ndarray:
        """The adjusted effect's t statistic for each re-deal (studentised, as the t-test is)."""
        X = np.stack([np.ones_like(signs)] + [signs * c for c in covariates], axis=-1)
        y = signs * d
        inverse = np.linalg.pinv(np.einsum("rnk,rnj->rkj", X, X))
        beta = (inverse @ np.einsum("rnk,rn->rk", X, y)[..., None])[..., 0]
        resid = y - np.einsum("rnk,rk->rn", X, beta)
        sigma2 = (resid**2).sum(axis=1) / (len(d) - X.shape[-1])
        return beta[:, 0] / np.sqrt(sigma2 * inverse[:, 0, 0])

    observed = effect(np.ones((1, len(d))))[0]
    signs = np.random.default_rng(seed).choice([-1.0, 1.0], size=(reps, len(d)))
    extreme = np.abs(effect(signs)) >= abs(observed) - 1e-12
    return float((extreme.sum() + 1) / (reps + 1))


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-adjusted p-values (step-down, monotone, capped at 1)."""
    order = sorted(pvalues, key=pvalues.get)
    m, running, adjusted = len(order), 0.0, {}
    for i, name in enumerate(order):
        running = max(running, (m - i) * pvalues[name])
        adjusted[name] = min(1.0, running)
    return adjusted


# %% Sensitivity: what n can detect
def power(dz: float, n: int, alpha: float = ALPHA, params: int = 3) -> float:
    """Two-sided power of the crossover t-test (df = n - params) for a true standardised dz."""
    df, nc = n - params, dz * math.sqrt(n)
    crit = stats.t.ppf(1 - alpha / 2, df)
    lower = stats.nct.cdf(-crit, df, nc)
    return float(stats.nct.sf(crit, df, nc) + (0.0 if math.isnan(lower) else lower))


def min_detectable(n: int, alpha: float = ALPHA, target: float = 0.8) -> float:
    return float(optimize.brentq(lambda dz: power(dz, n, alpha) - target, 0.01, 1.3))


def sensitivity_table(ns=(18, 24, 25, 28, 32, 35)) -> pd.DataFrame:
    rows = [
        {
            "n": n,
            "dz, single test": min_detectable(n),
            "dz, Holm first step": min_detectable(n, ALPHA / len(CONFIRMATORY)),
        }
        for n in ns
    ]
    return pd.DataFrame(rows).set_index("n").round(2)


# %% Participant 19: the deviation
def reinstate(
    tasks: pd.DataFrame, conditions: pd.DataFrame, ids: tuple[str, ...] = REINSTATED
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The deviation: drop each reinstated participant's empty session (no answer, no end) and
    re-run every exclusion rule in its pre-registered order, with the repo's own rules
    (`analysis/exclusions.py`, unchanged), as `poster_export/_build/build_export.py` does. That
    script also checked the empty session lasted under a second; this one sees no event times.

    Refuses if a reinstated participant is still incomplete without the empty session.
    """
    from analysis import exclusions

    wanted = {str(i) for i in ids}
    conds = conditions.copy()
    conds["participant_id"] = conds["participant_id"].astype(str)
    conds["session_id"] = conds["session_id"].astype(str)
    for flag in ("ended", "degraded"):
        conds[flag] = conds[flag].astype(bool)
    empty = conds["participant_id"].isin(wanted) & (conds["n_answers"] == 0) & ~conds["ended"]
    kept = conds[~empty].reset_index(drop=True)
    frame = tasks.drop(columns=["use_accuracy", "use_timing"], errors="ignore").copy()
    frame["participant_id"] = frame["participant_id"].astype(str)
    frame["session_id"] = frame["session_id"].astype(str)
    frame, report = exclusions.apply(frame, kept)
    still_out = set(next(e.ids for e in report if e.rule == "incomplete_session"))
    if still_out & wanted:
        raise PlanError(f"Still incomplete without the empty session: {sorted(still_out & wanted)}")
    return frame, kept


def check_reinstated_coded(
    tasks: pd.DataFrame, depth: pd.DataFrame | None, ids: tuple[str, ...] = REINSTATED
) -> None:
    """The main analysis counts a reinstated participant in RQ2 as well. Their answers sit off
    the main coding sheets (`scripts/code_justifications.py reinstated-sheets`), so refuse if they
    were never coded, rather than run RQ2 quietly without them."""
    if depth is None:
        return
    coded = set(depth["participant_id"].astype(str))
    usable = tasks[tasks["use_accuracy"].astype(bool)]
    answered = set(usable["participant_id"].astype(str))
    uncoded = sorted(p for p in map(str, ids) if p in answered and p not in coded)
    if uncoded:
        raise PlanError(
            f"Reinstated but not in depth.csv: {uncoded}. Grade their sheets "
            "(code_justifications.py reinstated-sheets), then run depth again."
        )


# %% Running the plan
def check_ready(tasks: pd.DataFrame, scores: pd.DataFrame, interim: bool) -> list[str]:
    """Refuse a run on data the plan says are not ready. Returns warnings."""
    uncoded = int(scores["n_uncoded"].sum())
    if uncoded:
        raise PlanError(
            f"{uncoded} T1 answers are uncoded, so those participants have no RQ1 score. "
            "Grade them (scripts/code_justifications.py rubric) and re-run score_study.py first."
        )
    collected = tasks["participant_id"].astype(str).nunique()
    if collected < STOP_N and not interim:
        raise PlanError(
            f"{collected} participants with data, below the stopping n of {STOP_N}. A test now is "
            "an interim look; pass --interim only if the supervisor has agreed to one."
        )
    if collected < STOP_N:
        return [f"INTERIM LOOK: {collected} of {STOP_N} participants. Not a result."]
    return []


def analyse(
    tasks: pd.DataFrame,
    conditions: pd.DataFrame,
    depth: pd.DataFrame | None,
    participants: pd.DataFrame | None,
    title: str,
    interim: bool = False,
) -> str:
    """One full analysis, rendered: scores, readiness, the tests, Holm and the TOST."""
    scores = participant_scores(tasks, conditions, depth, participants)
    notes = check_ready(tasks, scores, interim)
    results, adjusted = run(scores)
    n = scores["participant_id"].nunique()
    banner = f"{title}: n = {n}"
    return render(results, adjusted, [banner, "=" * len(banner), *notes])


def run(scores: pd.DataFrame) -> tuple[dict[str, Result], dict[str, float]]:
    results = {}
    for column in LABELS:
        if column in scores and scores[column].notna().any():
            results[column] = crossover(differences(scores, column), column)
    if "accuracy" in results:
        perm = permutation_p(differences(scores, "accuracy"))
        results["accuracy"] = replace(results["accuracy"], permutation_p=perm)
    missing = [c for c in CONFIRMATORY if c not in results]
    adjusted = holm({c: results[c].p for c in CONFIRMATORY}) if not missing else {}
    return results, adjusted


def _p(value: float) -> str:
    return "<.001" if value < 0.001 else f"{value:.3f}"


def _fmt(value: float, unit: str) -> str:
    return f"{value:+.3f}" if unit == "prop" else f"{value:+.2f}"


def render(results: dict[str, Result], adjusted: dict[str, float], notes: list[str]) -> str:
    lines = [*notes, ""] if notes else []
    lines.append("Main tests (Holm across RQ1-RQ3; two-sided; adjusted for half and form)")
    lines.append("-" * 76)
    header = (
        f"{'outcome':<44}{'n':>3}  {'effect [95% CI]':<26}"
        f"{'p':>7}{'Holm p':>8}{'Wilcoxon p':>11}{'dz':>6}"
    )
    for group in (CONFIRMATORY, [c for c in results if c not in CONFIRMATORY]):
        if group is not CONFIRMATORY:
            lines += ["", "Secondary (estimates; not main tests)", "-" * 76]
        lines.append(header)
        for name in group:
            if name not in results:
                lines.append(f"{LABELS[name]:<44}  not available (not coded yet?)")
                continue
            r = results[name]
            if name == "log_time":
                lo, hi = math.exp(r.ci95[0]), math.exp(r.ci95[1])
                effect = f"x{math.exp(r.estimate):.2f} [{lo:.2f}, {hi:.2f}]"
            else:
                unit = "prop" if name.startswith("accuracy") or name in DEPTH_CODES else "pts"
                effect = (
                    f"{_fmt(r.estimate, unit)} [{_fmt(r.ci95[0], unit)}, {_fmt(r.ci95[1], unit)}]"
                )
            holm_p = (
                _p(adjusted[name])
                if name in adjusted
                else ("-" if name not in CONFIRMATORY else "n/a")
            )
            lines.append(
                f"{LABELS[name]:<44}{r.n:>3}  {effect:<26}"
                f"{_p(r.p):>7}{holm_p:>8}{_p(r.wilcoxon_p):>11}{r.dz:>6.2f}"
            )
    if CONFIRMATORY and any(c not in results for c in CONFIRMATORY):
        lines.append(
            "Holm not applied: the family is all three tests, and at least one is missing."
        )

    if "accuracy" in results:
        acc = results["accuracy"]
        inside, p_tost = tost(acc, EQUIVALENCE_BOUND)
        significant = acc.p < ALPHA
        verdict = {
            (True, True): "a real difference, smaller than the bound",
            (True, False): "a difference that may reach the bound or more",
            (False, True): "equivalent: no difference as large as the bound",
            (False, False): "inconclusive",
        }[(significant, inside)]
        bound_items = EQUIVALENCE_BOUND * ITEMS_PER_CONDITION
        lines += [
            "",
            f"Accuracy equivalence (TOST, bound +/-{EQUIVALENCE_BOUND:.3f} = "
            f"{bound_items:.0f} item of {ITEMS_PER_CONDITION}): "
            f"90% CI [{acc.ci90[0]:+.3f}, {acc.ci90[1]:+.3f}], p = {p_tost:.3f} -> {verdict}",
            f"In items out of {ITEMS_PER_CONDITION}: {acc.estimate * ITEMS_PER_CONDITION:+.2f} "
            f"[{acc.ci95[0] * ITEMS_PER_CONDITION:+.2f}, {acc.ci95[1] * ITEMS_PER_CONDITION:+.2f}]",
        ]
        lines.append(
            f"Accuracy permutation check ({PERMUTATION_REPS:,} re-deals of order): "
            f"p = {_p(acc.permutation_p)}"
        )
        lines.append(f"Cells (interactive half-form): {acc.cells}")
        lines.append(
            f"Half effect (descriptive): {acc.half:+.3f}; "
            f"form effect (descriptive): {acc.form:+.3f}; "
            "+ means higher in the second half / on form B."
        )
    return "\n".join(lines)


# %% Made-up data, shaped like the pipeline's frames
def simulate(
    per_cell: int = 6,
    seed: int = 2026,
    accuracy_logit: float = 0.15,
    paas_shift: float = -1.3,
    depth_shift: float = 0.1,
    time_ratio: float = 1.15,
    empty_session_for: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """tasks.csv, conditions.csv and depth.csv as the pipeline writes them, before exclusions, for
    a study of 4 x per_cell participants. The effects are invented (a small accuracy gain, a Paas
    drop of about 1.3 points): the output shows what the analysis prints, never what the study
    found. `empty_session_for` gives that participant an extra empty session, as participant 19
    has; the frames come back with the pre-registered exclusions marked."""
    rng = np.random.default_rng(seed)
    item_logit = {
        (f, f"T{i}"): b
        for f in "AB"
        for i, b in zip(range(1, 7), rng.normal(1.3, 0.7, 6), strict=True)
    }
    sequences = [("static", "A"), ("interactive", "A"), ("static", "B"), ("interactive", "B")]
    task_rows, cond_rows, depth_rows = [], [], []
    pid = 0
    for first_condition, first_form in sequences:
        for _ in range(per_cell):
            pid += 1
            ability, effort, depth_trait, speed = (
                rng.normal(0, 0.9),
                rng.normal(0, 1.2),
                rng.normal(0, 0.5),
                rng.normal(0, 0.3),
            )
            second_condition = "interactive" if first_condition == "static" else "static"
            second_form = "B" if first_form == "A" else "A"
            for half, (condition, form) in enumerate(
                [(first_condition, first_form), (second_condition, second_form)], 1
            ):
                session = f"s{pid}-{half}"
                interactive = condition == "interactive"
                form_ease = 0.3 if form == "A" else 0.0
                for i in range(1, 7):
                    task = f"T{i}"
                    logit = (
                        item_logit[(form, task)]
                        + ability
                        + form_ease
                        + 0.1 * (half == 2)
                        + accuracy_logit * interactive
                    )
                    skipped = rng.random() < 0.02
                    correct = (not skipped) and rng.random() < 1 / (1 + math.exp(-logit))
                    duration = math.exp(
                        rng.normal(math.log(45_000), 0.45)
                        + speed
                        + math.log(time_ratio) * interactive
                    )
                    task_rows.append(
                        {
                            "participant_id": str(pid),
                            "session_id": session,
                            "condition": condition,
                            "condition_order": half,
                            "form": form,
                            "task_id": task,
                            "correct": correct,
                            "t1_parts": (
                                int(rng.binomial(3, 0.85 if correct else 0.4))
                                if task == "T1"
                                else None
                            ),
                            "skipped_answer": skipped,
                            "duration_ms": round(duration),
                            "duration_invalid": None,
                        }
                    )
                    if not skipped:
                        p_feature = 1 / (
                            1
                            + math.exp(
                                -(
                                    -0.2
                                    + depth_trait
                                    + depth_shift * interactive
                                    + (1.5 if task == "T1" else 0)
                                )
                            )
                        )
                        codes = {c: int(rng.random() < p_feature) for c in DEPTH_CODES}
                        depth_rows.append(
                            {
                                "participant_id": str(pid),
                                "session_id": session,
                                "condition": condition,
                                "form": form,
                                "task_id": task,
                                **codes,
                                "depth": sum(codes.values()),
                            }
                        )
                paas = (
                    5.2 + effort + paas_shift * interactive - 0.2 * (half == 2) + rng.normal(0, 1.1)
                )
                cond_rows.append(
                    {
                        "participant_id": str(pid),
                        "session_id": session,
                        "condition": condition,
                        "condition_order": half,
                        "form": form,
                        "paas": int(np.clip(round(paas), 1, 9)),
                        "n_answers": 6,
                        "ended": True,
                        "degraded": False,
                    }
                )
                if str(pid) == empty_session_for and half == 1:
                    cond_rows.append(
                        {
                            "participant_id": str(pid),
                            "session_id": f"s{pid}-empty",
                            "condition": condition,
                            "condition_order": half,
                            "form": form,
                            "paas": None,
                            "n_answers": 0,
                            "ended": False,
                            "degraded": False,
                        }
                    )
    tasks = pd.DataFrame(task_rows)
    tasks["correct"] = tasks["correct"].astype("boolean")  # as analysis/reshape.py stores it
    tasks["t1_parts"] = pd.array(tasks["t1_parts"].tolist(), dtype="Int64")
    conditions = pd.DataFrame(cond_rows)
    from analysis import exclusions

    tasks, _ = exclusions.apply(tasks, conditions)
    return tasks, conditions, pd.DataFrame(depth_rows)


# %% Command line
def _read(path: Path) -> pd.DataFrame | None:
    return (
        pd.read_csv(path, dtype={"participant_id": str, "session_id": str})
        if path.exists()
        else None
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--derived", type=Path, default=DERIVED)
    parser.add_argument("--depth", type=Path, default=CODING / "depth.csv")
    parser.add_argument("--simulate", action="store_true", help="run on made-up data")
    parser.add_argument("--sensitivity", action="store_true", help="print what each n can detect")
    parser.add_argument("--interim", action="store_true", help="allow a run below the stopping n")
    args = parser.parse_args(argv)

    if args.sensitivity:
        print(
            f"Smallest dz detectable with 80% power "
            f"(two-sided, alpha {ALPHA}, crossover t, df = n - 3)"
        )
        print(sensitivity_table().to_string())
        return 0

    if args.simulate:
        tasks, conditions, depth = simulate(empty_session_for=REINSTATED[0])
        participants = None
        print(
            "MADE-UP DATA (--simulate). These numbers are invented and say nothing about the study."
        )
        print()
    else:
        tasks, conditions = (
            _read(args.derived / "tasks.csv"),
            _read(args.derived / "conditions.csv"),
        )
        if tasks is None or conditions is None:
            print(
                f"No tasks.csv/conditions.csv in {args.derived}: run scripts/score_study.py first.",
                file=sys.stderr,
            )
            return 1
        depth, participants = _read(args.depth), _read(args.derived / "participants.csv")

    who = ", ".join(REINSTATED)
    try:
        with_them, kept = reinstate(tasks, conditions)
        check_reinstated_coded(with_them, depth)
        reports = [
            analyse(
                with_them,
                kept,
                depth,
                participants,
                f"MAIN: with participant {who} (deviation)",
                args.interim,
            ),
            analyse(
                tasks,
                conditions,
                depth,
                participants,
                f"AS PRE-REGISTERED: without participant {who}",
                args.interim,
            ),
        ]
    except PlanError as exc:
        print(f"Refusing to run: {exc}", file=sys.stderr)
        return 1
    print("\n\n".join(reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
