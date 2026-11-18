"""`paper/numbers.tex`: every quantity the paper prints, as a LaTeX macro, generated.

The paper never types a number (paper/outline.md). It writes `\\stat{key}`, and a key that
numbers.tex does not define stops the build. This script writes every key, from five sources, none
of them re-run:

- `data/study_logs/derived/significance.txt`, the confirmatory run of 2026-11-11, read as printed
  (`parse_significance()` in scripts/paper_descriptives.py);
- the descriptives scripts/paper_descriptives.py computes (paper/exploratory.md), built in memory
  from the derived CSVs, with every one of its checks against that run;
- the study's own code: the task bank, the scope, the analysis's constants;
- the design's sensitivity, from the notebook's `min_detectable()`, which reads no data: the numbers
  `notebooks/significance.py --sensitivity` prints;
- the mini-project's figures, which the paper compares this study with, as the proposal reports
  them (`MINI_PROJECT`, keys `mini/`): typed once here, since no file in this repository holds
  that earlier study's data.

It runs no test. Keys name the analysis first: `main` (participant 19 reinstated) or `pre` (as
pre-registered). The sample's background is written only in groups of five or more
(docs/study-design.md section 6.2): a smaller group gets no key, so a sentence that needs one fails
to build until the group is merged.

Usage:
    uv run python scripts/paper_numbers.py        # writes paper/numbers.tex
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import math
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from analysis import coding, exclusions, reshape  # noqa: E402
from analysis import keys as answer_keys  # noqa: E402
from analysis import report as study_report  # noqa: E402
from src import config, contrast  # noqa: E402
from src import tasks as study_tasks  # noqa: E402

DESCRIPTIVES = ROOT / "scripts" / "paper_descriptives.py"
STUDY_DESIGN = ROOT / "docs" / "study-design.md"
OUT = ROOT / "paper" / "numbers.tex"

PREFIX = {"main": "main", "preregistered": "pre"}  # paper_descriptives' analyses -> key prefix
CONDITIONS = ("static", "interactive")
# Outcomes read as proportions: printed to 3 places, and as a percentage.
PROPORTIONS = (
    "accuracy",
    "accuracy_answered",
    "accuracy_no_heard",
    "cites_values",
    "compares_series",
)
ACCURACY = ("accuracy", "accuracy_answered", "accuracy_no_heard")
KEY = re.compile(r"^[a-z0-9]+(/[A-Za-z0-9_+-]+)+$")
# A value is a number or a short verdict, never text a participant wrote.
VALUE = re.compile(r"^[A-Za-z0-9 .,:;\[\]()+<-]*$")
MIN_GROUP = 5  # study-design.md section 6.2: a background group under five is merged or withheld

C1_ANSWERS = dict(
    zip(
        (*study_tasks.COMPARISON_OPTIONS, "(skipped)"),
        ("controls", "nocontrols", "nodifference", "skipped"),
        strict=True,
    )
)
C1_DIRECTIONS = {"interactive higher": "higher", "equal": "equal", "static higher": "lower"}
FIELDS = {
    "Computer science, math, or statistics": "cs",
    "Natural or physical sciences (e.g., biology, chemistry, physics)": "natural",
    "Health or life sciences (e.g., kinesiology, public health, pre-med)": "health",
    "Social sciences (e.g., economics, psychology, politics)": "social",
    "Humanities or arts": "humanities",
    study_tasks.OTHER: "other",
    study_tasks.PREFER_NOT: "prefernot",
}


class NumbersError(RuntimeError):
    """A number cannot be written as it stands."""


_DESCRIPTIVES: ModuleType | None = None


def load_descriptives(path: Path = DESCRIPTIVES) -> ModuleType:
    """scripts/paper_descriptives.py as a module, loaded once, as its tests load it."""
    global _DESCRIPTIVES
    if _DESCRIPTIVES is None:
        loaded = sys.modules.get("paper_descriptives")
        if loaded is not None and Path(getattr(loaded, "__file__", "")).resolve() == path.resolve():
            _DESCRIPTIVES = loaded
        else:
            spec = importlib.util.spec_from_file_location("paper_descriptives", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["paper_descriptives"] = module  # its dataclasses look their module up here
            spec.loader.exec_module(module)
            _DESCRIPTIVES = module
    return _DESCRIPTIVES


# --- Formatting -----------------------------------------------------------------------------------
def tex(value: str) -> str:
    """A printed value as LaTeX text: a true minus sign, and < as a text symbol."""
    text = value.replace("<", r"\textless{}")
    return re.sub(r"-(?=[\d.])", r"\\textminus{}", text)


def fixed(x: float, places: int) -> str:
    return f"{x:.{places}f}"


def signed(x: float, places: int) -> str:
    return f"{x:+.{places}f}"


def whole(x: float) -> str:
    """A count, or a measured value that is a whole number (a floor of 5 points prints as 5)."""
    if float(x) != int(x):
        raise NumbersError(f"{x} is not a whole number")
    return str(int(x))


def number(x: float) -> str:
    """A median of whole numbers: whole when it is, else to one place (754.5)."""
    return whole(x) if float(x) == int(x) else fixed(x, 1)


class Numbers:
    """Keys in the order they were written, each once."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def put(self, key: str, value) -> None:
        if not KEY.match(key):
            raise NumbersError(f"not a key: {key!r}")
        if key in self.values:
            raise NumbersError(f"{key} written twice")
        text = value if isinstance(value, str) else str(value)
        if isinstance(value, float) and math.isnan(value) or text.lower() == "nan":
            raise NumbersError(f"{key} has no value")
        if not VALUE.match(text):
            raise NumbersError(f"{key}: {text!r} is not a number or a verdict")
        self.values[key] = tex(text)

    def group(self, key: str, count: int, of: int) -> None:
        """A background count, written only when the group and the rest of those who answered
        (`of` minus it) are each five or more, or the rest is empty: "22 of 24" would report a
        group of two by subtraction (study-design.md section 6.2)."""
        rest = of - count
        if count >= MIN_GROUP and (rest >= MIN_GROUP or rest == 0):
            self.put(key, whole(count))


# --- The design, from the code that ran the study ---------------------------------------------
def design(numbers: Numbers, sig: ModuleType) -> None:
    put = numbers.put
    forms = {form: study_tasks.for_form(form) for form in study_tasks.FORMS}
    first = forms["A"]
    put("design/items", whole(len(first)))
    put("design/totalitems", whole(sum(len(items) for items in forms.values())))
    put("design/forms", whole(len(forms)))
    put("design/charttypes", whole(len({task.chart for task in first})))
    choices = {len(t.options) for items in forms.values() for t in items if t.options}
    if len(choices) != 1:
        raise NumbersError(f"items offer different numbers of options: {sorted(choices)}")
    put("design/options", whole(choices.pop()))
    used = {task.vaccine for items in forms.values() for task in items}
    put("design/vaccinesused", whole(len(used)))
    put("design/vaccines", whole(len(config.VACCINES)))
    put("design/countries", whole(len(config.COUNTRIES)))
    put("design/aggregates", whole(len(config.AGGREGATES)))
    put("design/yearfirst", whole(config.YEAR_MIN))
    put("design/yearlast", whole(config.YEAR_MAX))
    put("design/askedfrom", whole(study_tasks.ASKED_FROM))
    for task in first:
        other = next(t for t in forms["B"] if t.task_id == task.task_id)
        if len(other.entities) == len(task.entities):
            put(f"design/entities/{task.task_id}", whole(len(task.entities)))
    put("design/chart/width", whole(config.CHART_WIDTH))
    put("design/chart/height", whole(config.CHART_HEIGHT))
    put("design/palette", whole(len(config.SERIES_COLORS)))
    put("design/cvdfloor", whole(config.MIN_CVD_DISTANCE))
    put("design/contrast/text", number(contrast.TEXT_MIN))
    put("design/contrast/graphic", number(contrast.GRAPHIC_MIN))
    put("design/bands/heatmap", whole(len(config.HEATMAP_BANDS)))
    put("design/bands/map", whole(len(config.MAP_BANDS)))
    put("design/extracontrols", whole(len(reshape.EXTRA_CONTROLS)))
    put("design/likertpoints", whole(study_tasks.LIKERT_POINTS))
    put("design/likertmin", whole(min(study_tasks.LIKERT_ANCHORS)))
    put("design/paaspoints", whole(max(study_tasks.LOAD_ANCHORS)))
    put("design/paasmin", whole(min(study_tasks.LOAD_ANCHORS)))
    put("design/surveyitems", whole(len(study_tasks.LIKERT_ITEMS)))
    put("design/controlsitems", whole(len(study_tasks.CONTROLS_ITEMS)))
    put("design/t1parts", whole(len(coding.RUBRIC_PARTS)))
    put("design/depthmax", whole(len(coding.CODES)))
    put("design/maxtext", f"{study_tasks.MAX_TEXT:,}")
    put("design/fastseconds", whole(exclusions.MIN_TASK_MS / 1000))
    put("design/trimpercentile", whole(round(exclusions.TOP_TRIM_QUANTILE * 100)))
    put("design/alpha", fixed(sig.ALPHA, 2).lstrip("0"))
    put("design/holmfirst", fixed(sig.ALPHA / len(sig.CONFIRMATORY), 3).lstrip("0"))
    put("design/family", whole(len(sig.CONFIRMATORY)))
    put("design/bounditems", whole(round(sig.EQUIVALENCE_BOUND * sig.ITEMS_PER_CONDITION)))
    put("design/boundprop", fixed(sig.EQUIVALENCE_BOUND, 3))
    put("design/permutations", f"{sig.PERMUTATION_REPS:,}")
    # The power the sensitivity keys assume: min_detectable()'s own default, in percent.
    power = inspect.signature(sig.min_detectable).parameters["target"].default
    put("design/power", whole(round(power * 100)))
    put("design/stopn", whole(sig.STOP_N))
    target = re.search(r"Target n ≥ (\d+)", STUDY_DESIGN.read_text(encoding="utf-8"))
    if target is None:
        raise NumbersError("docs/study-design.md no longer states its target n")
    put("design/targetn", target[1])
    # The parameters the questions themselves state (analysis/keys.py PARAMS, src/tasks.py).
    ordinals = {3: "third", 6: "sixth"}
    for form in forms:
        put(f"design/T2/rank/{form}", ordinals[answer_keys.PARAMS[(form, "T2")]["rank"]])
    thresholds = {answer_keys.PARAMS[(form, "T5")]["threshold"] for form in forms}
    if len(thresholds) != 1:
        raise NumbersError(f"T5's threshold differs between forms: {sorted(thresholds)}")
    put("design/T5/threshold", whole(thresholds.pop()))
    put("design/heatmapyears", whole(len(study_tasks.HEATMAP_YEARS)))
    put("design/compactheight", whole(study_report.COMPACT_MAX_HEIGHT))
    put("design/crossingbands", whole(len(study_tasks.CROSSING_BANDS)))
    put("design/floor/position", whole(answer_keys.MIN_SEPARATION_PP))
    put("design/floor/colour", whole(answer_keys.MIN_COLOUR_SEPARATION_PP))
    put("design/floor/dots", whole(answer_keys.MIN_DOT_DISTANCE_PP))
    put("design/floor/bandyears", whole(answer_keys.MIN_BAND_INSET_YEARS))
    put("design/floor/trend", whole(answer_keys.MIN_TREND_PP))


# The packages Appendix A names. A package uv.lock pins to one version gets a key; one it locks per
# Python version (numpy, scipy) does not, and the appendix says so.
LOCKED = ("dash", "plotly", "psycopg", "pandas", "pyarrow", "scipy", "numpy", "pytest", "ruff")


def software(numbers: Numbers) -> None:
    """The software versions Appendix A gives, from uv.lock and pyproject.toml."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions: dict[str, set[str]] = {}
    for package in lock["package"]:
        if package["name"] in LOCKED:
            versions.setdefault(package["name"], set()).add(package["version"])
    for name in LOCKED:
        found = versions.get(name, set())
        if len(found) == 1:
            numbers.put(f"software/{name}", found.pop())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    floor = re.fullmatch(r">=\s*(\d+\.\d+)", project["requires-python"])
    if floor is None:
        raise NumbersError(f"cannot read the Python floor {project['requires-python']!r}")
    numbers.put("software/python", floor[1])


# --- The mini-project, as the proposal reports it ----------------------------------------------
# The author's earlier, between-subjects study of static and interactive Tableau dashboards
# (references.bib: rebollar2026mini). Its data are not in this repository, so its figures are typed
# here, once, from the proposal's section 6 (paper/sources/Senior_Comps_Proposal (1).pdf), and the
# paper still types none. The point drops and rise are on its 7-point agreement scale.
MINI_PROJECT = {
    "mini/n": "6",  # participants
    "mini/static/n": "2",  # who used only the static dashboard
    "mini/interactive/n": "4",  # who used only the interactive one
    "mini/likertpoints": "7",
    "mini/overwhelming": "2.75",  # how far "the visualization felt overwhelming" dropped
    "mini/tracking": "2.50",  # how far "it was difficult to track multiple countries" dropped
    "mini/ease": "1.50",  # how far ease of use rose
    "mini/confidence/static": "6.50",
    "mini/confidence/interactive": "5.75",
    "mini/rank/pct": "50",  # rank comparison correct, in both conditions
    "mini/time/static": "6 min 37 s",  # mean completion time
    "mini/time/interactive": "8 min 40 s",
}


def mini_project(numbers: Numbers) -> None:
    """The mini-project's figures (`MINI_PROJECT`), for the paper's comparison with it."""
    for key, value in MINI_PROJECT.items():
        numbers.put(key, value)


# --- significance.txt, as printed ---------------------------------------------------------------
def significance(numbers: Numbers, run: dict[str, dict], sig: ModuleType) -> None:
    put = numbers.put
    for name, block in run.items():
        p = PREFIX[name]
        put(f"{p}/n", whole(block["n"]))
        for outcome, row in block["outcomes"].items():
            if row is None:
                continue
            base = f"{p}/{outcome}"
            est = row["effect"].lstrip("x")
            for field, value in (
                ("n", row["n"]),
                ("est", est),
                ("low", row["low"]),
                ("high", row["high"]),
                ("ci", f"[{row['low']}, {row['high']}]"),
                ("t", row["t"]),
                ("df", row["df"]),
                ("p", row["p"]),
                ("wilcoxon", row["wilcoxon"]),
                ("dz", row["dz"]),
            ):
                put(f"{base}/{field}", value)
            # Holm's p exists for the three main tests only, so no other outcome can cite one.
            if outcome in sig.CONFIRMATORY:
                put(f"{base}/holm", row["holm"])
            if row["effect"].startswith("x"):  # a ratio: time on task
                for field, value in (
                    ("pct", est),
                    ("lowpct", row["low"]),
                    ("highpct", row["high"]),
                ):
                    put(f"{base}/{field}", whole(round((float(value) - 1) * 100)))
        lines = block["lines"]
        missing = {"tost", "items", "permutation", "cells", "effects", "rq3", "degraded"} - set(
            lines
        )
        if missing:
            raise NumbersError(f"significance.txt ({name}) does not print {sorted(missing)}")
        tost = lines["tost"]
        for field in ("low", "high", "p", "verdict"):
            put(f"{p}/tost/{field}", tost[field])
        put(f"{p}/tost/ci", f"[{tost['low']}, {tost['high']}]")
        # The verdict up to its explanation ("equivalent"), short enough for a table cell.
        put(f"{p}/tost/short", tost["verdict"].split(":", 1)[0])
        items = lines["items"]
        for field in ("est", "low", "high"):
            put(f"{p}/accuracy/items/{field}", items[field])
        put(f"{p}/accuracy/items/ci", f"[{items['low']}, {items['high']}]")
        put(f"{p}/accuracy/permutation", lines["permutation"]["p"])
        for cell, count in lines["cells"].items():
            put(f"{p}/cells/{cell}", count)
        put(f"{p}/accuracy/half", lines["effects"]["half"])
        put(f"{p}/accuracy/form", lines["effects"]["form"])
        for field in ("falls", "equivalent", "verdict"):
            put(f"{p}/rq3/{field}", lines["rq3"][field])
        put(f"{p}/degraded", lines["degraded"]["n"])
        for condition, (right, _of) in block["ceiling"].items():
            put(f"{p}/ceiling/{condition}", whole(right))
        put(f"{p}/ceiling/of", whole(block["ceiling"]["static"][1]))
        put(f"{p}/sensitivity/single", fixed(sig.min_detectable(block["n"]), 2))
        holm_first = sig.ALPHA / len(sig.CONFIRMATORY)
        put(f"{p}/sensitivity/holm", fixed(sig.min_detectable(block["n"], holm_first), 2))


# --- The descriptives (paper/exploratory.md) ------------------------------------------------------
def _places(outcome: str) -> int:
    return 3 if outcome in PROPORTIONS else 2


# paas_a7_summary.csv's statistics -> keys. Those given per scope (all, static, interactive) take
# the scope as their last part; the others are over all pairs or participants.
PAAS_A7_KEYS = {
    "pairs": "pairs",
    "spearman": "rho",
    "opposed_pairs": "opposed",
    "pairs_missing_a_rating": "missing",
    "participants_with_both_pairs": "participants",
    "same_direction": "samedirection",
    "both_unchanged": "bothunchanged",
    "opposite_direction": "opposite",
    "one_unchanged": "oneunchanged",
    "looks_reversed": "reversed",
}
PAAS_A7_SCOPED = ("pairs", "rho", "opposed")


def exploratory(numbers: Numbers, outputs: dict[str, object], items: int) -> None:
    put = numbers.put
    for row in outputs["scores_summary.csv"].itertuples(index=False):
        p = PREFIX[row.analysis]
        if row.outcome == "time_s":
            put(f"{p}/time/{row.condition}/seconds", fixed(row.mean, 1))
            put(f"{p}/time/{row.condition}/median", fixed(row.median, 1))
            put(f"{p}/time/{row.condition}/n", whole(row.n))
            continue
        base, places = f"{p}/{row.outcome}/{row.condition}", _places(row.outcome)
        put(f"{base}/n", whole(row.n))
        for field in ("mean", "sd", "median"):
            put(f"{base}/{field}", fixed(getattr(row, field), places))
        if row.outcome in PROPORTIONS:
            put(f"{base}/pct", fixed(100 * row.mean, 0))
        if row.outcome in ACCURACY:
            put(f"{base}/items", fixed(items * row.mean, 2))

    for row in outputs["differences.csv"].itertuples(index=False):
        base = f"{PREFIX[row.analysis]}/{row.outcome}/diff"
        for field in ("n", "above_zero", "zero", "below_zero"):
            put(f"{base}/{field.replace('_zero', '')}", whole(getattr(row, field)))
        put(f"{base}/sd", fixed(row.sd, _places(row.outcome)))

    for row in outputs["windows.csv"].itertuples(index=False):
        base = f"{PREFIX[row.analysis]}/windows"
        put(f"{base}/participants", whole(row.participants))
        put(f"{base}/compact", whole(row.compact))
        for field in ("height_min", "height_median", "height_max", "width_median"):
            put(f"{base}/{field.replace('_', '/')}", number(getattr(row, field)))

    timing = outputs["timing_by_participant.csv"]
    removed = outputs["timing_exclusions.csv"]
    for name, p in PREFIX.items():
        mine = timing[timing["analysis"] == name]
        put(f"{p}/timing/notime", whole((~mine["has_time_score"]).sum()))
        out = removed[removed["analysis"] == name]
        invalid = out[out["rule"] == "invalid_timing"]
        put(f"{p}/timing/invalid", whole(len(invalid)))
        put(f"{p}/timing/clockreset", whole((invalid["duration_invalid"] == "clock_reset").sum()))
        put(f"{p}/timing/invalidparticipants", whole(invalid["participant_id"].nunique()))
        trimmed = out[out["rule"] == "top_one_percent"]
        put(f"{p}/timing/trimmed", whole(len(trimmed)))
        if len(trimmed):
            put(f"{p}/timing/cutoff", fixed(trimmed["cutoff_ms"].iloc[0] / 1000, 0))

    for row in outputs["t1_rubric.csv"].itertuples(index=False):
        base = f"{PREFIX[row.analysis]}/t1rubric/{row.form}/{row.condition}"
        put(f"{base}/n", whole(row.n))
        for part in (*coding.RUBRIC_FIELDS, "correct"):
            share = getattr(row, f"share_{part}")
            put(f"{base}/{part}", fixed(100 * share, 0))
            put(f"{base}/{part}/count", whole(round(share * row.n)))

    for row in outputs["paas_a7_summary.csv"].itertuples(index=False):
        base = f"{PREFIX[row.analysis]}/paasa7"
        if row.statistic.startswith("gap01_"):
            put(f"{base}/gap/{row.statistic.removeprefix('gap01_')}", fixed(row.value, 2))
            continue
        name = PAAS_A7_KEYS[row.statistic]
        key = f"{base}/{name}/{row.scope}" if name in PAAS_A7_SCOPED else f"{base}/{name}"
        put(key, fixed(row.value, 2) if name == "rho" else whole(row.value))
    direction = outputs["paas_a7_direction.csv"]
    for name, p in PREFIX.items():
        mine = direction[direction["analysis"] == name]
        for row in mine.itertuples(index=False):
            put(f"{p}/paasa7/change/{row.paas_change}/{row.a7_change}", whole(row.n))
        for measure, column in (("paas", "paas_change"), ("a7", "a7_change")):
            for change in ("lower", "same", "higher"):
                count = mine.loc[mine[column] == change, "n"].sum()
                put(f"{p}/paasa7/{measure}{change}", whole(count))

    for row in outputs["paas_a7_order_differences.csv"].itertuples(index=False):
        group = "first" if row.group == "interactive first" else "second"
        base = f"{PREFIX[row.analysis]}/order/{group}/{row.measure}"
        put(f"{base}/diff", signed(row.mean, 2))
        put(f"{base}/sd", fixed(row.sd, 2))
        put(f"{base}/n", whole(row.n))
    for row in outputs["paas_a7_by_order.csv"].itertuples(index=False):
        group = "first" if row.group == "interactive first" else "second"
        put(
            f"{PREFIX[row.analysis]}/order/{group}/{row.condition}/{row.measure}",
            fixed(row.mean, 2),
        )
    for row in outputs["paas_a7_by_half.csv"].itertuples(index=False):
        put(f"{PREFIX[row.analysis]}/half/{row.half}/{row.measure}", fixed(row.mean, 2))

    for row in outputs["c1_accuracy_crosstab.csv"].itertuples(index=False):
        base = f"{PREFIX[row.analysis]}/c1acc/{C1_ANSWERS[row.c1]}"
        put(f"{base}/{C1_DIRECTIONS[row.direction]}", whole(row.n))
    for row in outputs["c1_accuracy_by_answer.csv"].itertuples(index=False):
        base = f"{PREFIX[row.analysis]}/c1acc/{C1_ANSWERS[row.c1]}"
        put(f"{base}/n", whole(row.n))
        if row.n:
            put(f"{base}/mean", signed(row.mean, 2))

    review(numbers, outputs)
    for row in outputs["decision_log_summary.csv"].itertuples(index=False):
        sheet = row.sheet.lower()
        put(f"rules/{sheet}", whole(row.rules))
        if sheet == "all":
            put("rules/amended", whole(row.amended_in_review))
            put("rules/moot", whole(row.moot))
            put("rules/rechecked", whole(row.rechecked_changed))


def review(numbers: Numbers, outputs: dict[str, object]) -> None:
    """How many codes the grading review changed: all sheets (the main analysis's), and the main
    sheets alone (the pre-registered analysis's)."""
    put = numbers.put
    changes = outputs["review_changes.csv"]
    changes = changes[changes["note"].fillna("") == ""]
    moved = outputs["review_t1_outcomes.csv"]
    for family, scope, key in (("T1 rubric", "T1", "t1"), ("RQ2", "all units", "rq2")):
        for sheets, prefix in (("all sheets", "review"), ("main sheet", "review/mainsheet")):
            mine = changes[
                (changes["sheet"] == f"{family}, {sheets}") & (changes["scope"] == scope)
            ]
            every = mine[mine["condition"] == "all"]
            put(f"{prefix}/{key}/units", whole(every["units"].iloc[0]))
            put(f"{prefix}/{key}/codes", whole(every["units"].sum()))
            put(f"{prefix}/{key}/changed", whole(every["changed"].sum()))
            put(f"{prefix}/{key}/zerotoone", whole(every["zero_to_one"].sum()))
            put(f"{prefix}/{key}/onetozero", whole(every["one_to_zero"].sum()))
            for condition in CONDITIONS:
                part = mine[mine["condition"] == condition]
                put(f"{prefix}/{key}/changed/{condition}", whole(part["changed"].sum()))
            if family == "T1 rubric":
                for row in moved[moved["sheet"] == f"{family}, {sheets}"].itertuples(index=False):
                    suffix = "" if row.condition == "all" else f"/{row.condition}"
                    put(f"{prefix}/t1/verdicts{suffix}", whole(row.verdicts_changed))
                    put(f"{prefix}/t1/tocorrect{suffix}", whole(row.to_correct))
                    put(f"{prefix}/t1/toincorrect{suffix}", whole(row.to_incorrect))
                    put(f"{prefix}/t1/parts{suffix}", whole(row.parts_changed))


# --- The report's tables (analysis/report.py), per analysis --------------------------------------
def report_tables(numbers: Numbers, analyses: dict, participants: pd.DataFrame) -> None:
    put = numbers.put
    for name, analysis in analyses.items():
        p, tasks = PREFIX[name], analysis.tasks
        for exclusion in analysis.exclusions:
            put(f"{p}/excl/{exclusion.rule}/rows", whole(exclusion.n_rows))
            if exclusion.unit in ("participant", "session"):
                put(f"{p}/excl/{exclusion.rule}/{exclusion.unit}s", whole(len(exclusion.ids)))

        for (task, _chart, _kind, condition), row in study_report.by_item(tasks).iterrows():
            base = f"{p}/item/{task}/{condition}"
            put(f"{base}/n", whole(row["n"]))
            put(f"{base}/pct", fixed(100 * float(row["correct"]), 0))
            put(f"{base}/correct", whole(round(float(row["correct"]) * row["n"])))
            put(f"{base}/seconds", fixed(row["median_ms"] / 1000, 0))
        for (task, form, condition), row in study_report.by_item_form(tasks).iterrows():
            base = f"{p}/item/{task}/{form}/{condition}"
            put(f"{base}/n", whole(row["n"]))
            put(f"{base}/pct", fixed(100 * float(row["correct"]), 0))
            put(f"{base}/correct", whole(round(float(row["correct"]) * row["n"])))
        adjacent = study_report.crossing_adjacent(tasks)
        for (condition, _task), row in adjacent.iterrows():
            put(
                f"{p}/item/T6/{condition}/adjacentpct",
                fixed(100 * row[("correct_adjacent", "mean")], 0),
            )

        overload = study_report.overload(tasks)
        if "interactive" in overload.index:
            row = overload.loc["interactive"]
            put(f"{p}/t1extra/n", whole(row["n"]))
            put(f"{p}/t1extra/users", whole(row["used_any"]))
            for control in ("coverage", "order", "regions", "display"):
                put(f"{p}/t1extra/{control}/users", whole(row[f"n_extra_{control}_users"]))
                put(f"{p}/t1extra/{control}/uses", whole(row[f"n_extra_{control}_total"]))
        for condition, row in overload.iterrows():
            put(f"{p}/t1/{condition}/seconds", fixed(row["median_ms"] / 1000, 0))

        used = study_report.controls_used(tasks)
        controls = [c for c in used.columns if c not in ("chart", "n")]
        for (task, form), row in used.iterrows():
            put(f"{p}/controls/{task}/{form}/n", whole(row["n"]))
            for control in controls:
                if row[control] != "-":
                    put(f"{p}/controls/{task}/{form}/{control}", whole(row[control]))
        for task, rows in used.groupby(level=0):
            put(f"{p}/controls/{task}/n", whole(rows["n"].sum()))
            for control in controls:
                if (rows[control] != "-").all():
                    put(f"{p}/controls/{task}/{control}", whole(rows[control].astype(int).sum()))

        for task, row in study_report.from_2000(tasks).iterrows():
            for field in ("n", "by_years", "by_zoom", "either"):
                put(f"{p}/from2000/{task}/{field.replace('by_', '')}", whole(row[field]))
        early = study_report.crossing_early_band(tasks)
        for condition in CONDITIONS:
            put(f"{p}/t6early/{condition}", whole(early.loc[condition, "early"].sum()))
        skipped = study_report.skips(tasks)
        for condition, row in skipped.iterrows():
            put(f"{p}/skips/{condition}/answers", whole(row["skipped_answer"]))
            put(f"{p}/skips/{condition}/justifications", whole(row["skipped_justification"]))

        survey(numbers, p, analysis)
        people = participants[participants["participant_id"].isin(analysis.included)]
        put(f"{p}/sample/n", whole(len(people)))
        put(f"{p}/heard/yes", whole((people[study_tasks.HEARD_KEY] == study_tasks.HEARD_YES).sum()))
        # The sample is described once, for the main analysis. Its background printed for both
        # analyses would give participant 19's by subtraction.
        if name == "main":
            sample(numbers, p, people)


def survey(numbers: Numbers, p: str, analysis) -> None:
    put = numbers.put
    included = analysis.included
    table = study_report.survey(analysis.conditions, included)
    for (item, statistic), row in table.iterrows():
        for condition in CONDITIONS:
            value = row[condition]
            if statistic in ("mean", "std"):
                put(
                    f"{p}/survey/{item}/{condition}/{statistic.replace('std', 'sd')}",
                    fixed(value, 2),
                )
            elif statistic == "count":
                put(f"{p}/survey/{item}/{condition}/n", whole(value))
    controls = study_report.controls(analysis.conditions, included)
    for item in controls.columns:
        put(f"{p}/survey/{item}/interactive/mean", fixed(controls.loc["mean", item], 2))
        put(f"{p}/survey/{item}/interactive/sd", fixed(controls.loc["std", item], 2))
        put(f"{p}/survey/{item}/interactive/n", whole(controls.loc["count", item]))
    comparison = study_report.comparison(analysis.conditions, included)
    for (item, answer), row in comparison.iterrows():
        if item in study_tasks.COMPARISON_CHOICES:
            put(f"{p}/{item}/{C1_ANSWERS[answer]}", whole(row["n"]))
        else:
            put(f"{p}/{item}/written", whole(row["n"]))


def sample(numbers: Numbers, p: str, people: pd.DataFrame) -> None:
    """The sample's background (study-design.md section 6.2): age as a median and range, and only
    groups that leave five or more on each side. Fields under five are folded into "other"."""
    put = numbers.put
    ages = pd.to_numeric(people["age"], errors="coerce").dropna()
    put(f"{p}/sample/age/n", whole(len(ages)))
    put(f"{p}/sample/age/median", number(ages.median()))
    put(f"{p}/sample/age/min", whole(ages.min()))
    put(f"{p}/sample/age/max", whole(ages.max()))

    def group(key: str, column: str, *answers: str) -> None:
        given = people[column].dropna()
        numbers.group(f"{p}/sample/{key}", int(given.isin(answers).sum()), len(given))

    group("undergrad", "role", "Undergraduate student")
    group("trackpad", "pointer", "Trackpad / touchpad")
    group("statscourse", "stats_course", "Yes")
    group("health/yes", "health_background", "Yes")
    group("readcharts/weekly", "read_charts", "About weekly", "Daily or almost daily")
    group("makecharts/monthly", "make_charts", "About monthly", "About weekly or more")
    little = [a for a in people["topic_familiarity"].dropna().unique() if str(a)[:1] in "12"]
    group("topic/little", "topic_familiarity", *little)
    fields = people["field"].dropna().map(FIELDS).value_counts().to_dict()
    small = [field for field, n in fields.items() if n < MIN_GROUP and field != "other"]
    fields["other"] = fields.get("other", 0) + sum(fields.pop(field) for field in small)
    if all(n >= MIN_GROUP for n in fields.values() if n):
        for field, n in fields.items():
            if n:
                put(f"{p}/sample/field/{field}", whole(n))


# --- Assembling and writing -----------------------------------------------------------------------
def build_numbers(
    inputs,
    sig: ModuleType,
    pdesc: ModuleType,
    outputs: dict[str, object] | None = None,
    analyses: dict | None = None,
) -> Numbers:
    """Every key, after every check scripts/paper_descriptives.py makes against the run.

    `outputs` and `analyses` are `pdesc.build()` and `pdesc.build_analyses()` on these inputs, for
    a caller that has them already (scripts/paper_figures.py); otherwise they are built here."""
    numbers = Numbers()
    design(numbers, sig)
    software(numbers)
    mini_project(numbers)
    significance(numbers, inputs.significance, sig)
    if outputs is None:
        outputs = pdesc.build(inputs, sig)
    exploratory(numbers, outputs, sig.ITEMS_PER_CONDITION)
    if analyses is None:
        analyses = pdesc.build_analyses(inputs, sig)
    report_tables(numbers, analyses, inputs.participants)
    return numbers


HEADER = r"""% paper/numbers.tex -- GENERATED by scripts/paper_numbers.py. Do not edit by hand.
%
% Every quantity in the paper is \stat{key}; a key not defined here stops the build. The numbers
% come from data/study_logs/derived/significance.txt (the confirmatory run of 2026-11-11, read as
% printed), the descriptives of scripts/paper_descriptives.py (paper/exploratory.md), the study's
% own code, the notebook's min_detectable() (no data), and the mini-project's figures as the
% proposal reports them (mini/, typed once in the script). Keys start with the analysis: main
% (participant 19 reinstated) or pre (as pre-registered). Background counts exist only for groups
% of five or more (docs/study-design.md section 6.2).
\providecommand{\textminus}{\ensuremath{-}}
\newcommand{\stat}[1]{\ifcsname stat@#1\endcsname\csname stat@#1\endcsname\else
  \PackageError{numbers}{No number named `#1'}{Every number comes from paper/numbers.tex:
  regenerate it with scripts/paper_numbers.py, or fix the key.}\fi}
\newcommand{\defstat}[2]{\expandafter\def\csname stat@#1\endcsname{#2}}
"""


def render(numbers: Numbers) -> str:
    """numbers.tex: the header, then every key in sorted order, grouped by its first part."""
    lines = [HEADER]
    section = None
    for key in sorted(numbers.values):
        head = key.split("/", 1)[0]
        if head != section:
            lines.append(f"\n% --- {head}")
            section = head
        lines.append(f"\\defstat{{{key}}}{{{numbers.values[key]}}}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    pdesc = load_descriptives()
    parser = argparse.ArgumentParser(description="Write paper/numbers.tex.")
    parser.add_argument("--derived", type=Path, default=pdesc.DERIVED)
    parser.add_argument("--coding", type=Path, default=pdesc.CODING)
    parser.add_argument("--significance", type=Path, help="default: DERIVED/significance.txt")
    parser.add_argument("--rules", type=Path, default=pdesc.GRADING_RULES)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    significance_path = args.significance or args.derived / "significance.txt"

    sig = pdesc.load_notebook()
    try:
        inputs = pdesc.load_inputs(
            args.derived, args.coding, significance_path, args.rules, sig.LABELS
        )
        numbers = build_numbers(inputs, sig, pdesc)
    except (pdesc.PaperError, sig.PlanError, coding.CodingError, NumbersError) as exc:
        print(f"Refusing to write: {exc}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(numbers), encoding="utf-8", newline="\n")
    print(f"Wrote {len(numbers.values)} numbers to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
