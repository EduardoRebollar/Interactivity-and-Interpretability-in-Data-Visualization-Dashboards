"""The RQ2 coding harness: blind sheets, a double-coded sample, and Cohen's kappa.

`docs/study-design.md` section 7 requires justifications to be coded blind to condition, 20% of them
by a second coder, with kappa reported. Blinding here is enforced by what the sheet contains, not by
asking coders not to look:

- The sheet has an opaque `unit_id` and the justification text. No condition, form, participant --
  and no task id, since the codes are properties of the text and the task id is the easiest route
  back to the condition.
- Units are **shuffled with a recorded seed**. Justifications are produced in condition-blocked
  order, so an unshuffled sheet would let a coder infer condition from position.
- The double-coded sample is **stratified by condition**, using labels the harness knows and the
  sheet does not, so reliability is never estimated on one condition's material alone.

There is deliberately no automatic coding. A rule that marks `cites_values` whenever a digit appears
would quietly become the coder.

**T1's rubric (2026-09-27).** T1 is a written description of two trends, and its RQ1 score comes
from coders, not a key (section 7). Both coders code **every** T1 description, blind, on the
rubric's three parts and a `contradicts` flag. Kappa is computed from the two independent sheets;
disagreements are then settled by discussion into a third file, and scoring refuses to go on while
one is open. The same sheet machinery serves both: opaque ids, a seeded shuffle, and a key file
coders never see. T1's description is also its RQ2 unit, in place of a justification.

Stdlib only; kappa for binary codes is a few lines and does not justify a dependency.
"""

from __future__ import annotations

import csv
import hashlib
import math
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analysis import keys as answer_keys
from src import config

CODES = ("cites_values", "compares_series", "notes_uncertainty")
WRITTEN_KIND = "describe"
# T1's rubric: the three parts of study-design.md section 4, and whether anything contradicts one.
RUBRIC_FIELDS = ("a", "b", "c", "contradicts")
RUBRIC_SHEET_COLUMNS = ("unit_id", "description", "part_a", "part_b", "part_c", *RUBRIC_FIELDS)
SETTLED_COLUMNS = ("unit_id", *RUBRIC_FIELDS)
VERDICT_COLUMNS = ("session_id", "task_id", "correct")
# Where `scripts/code_justifications.py rubric` writes the settled verdicts, and where scoring
# and the viewer read them. Participant data: gitignored under data/study_logs/.
VERDICTS_PATH = config.STUDY_LOGS_DIR / "coding" / "rubric_verdicts.csv"
SEED = 20260915
DOUBLE_CODED_FRACTION = 0.20
SHEET_COLUMNS = ("unit_id", "justification", *CODES)
KEY_COLUMNS = ("unit_id", "participant_id", "session_id", "condition", "form", "task_id")


class CodingError(ValueError):
    """A completed sheet cannot be used as it stands."""


@dataclass(frozen=True)
class Unit:
    unit_id: str
    justification: str
    participant_id: str
    session_id: str
    condition: str
    form: str
    task_id: str


def unit_id(session_id: str, task_id: str) -> str:
    """Stable and opaque: the same answer always gets the same id, and the id reveals nothing."""
    return hashlib.blake2b(f"{session_id}|{task_id}".encode(), digest_size=8).hexdigest()


def build_units(rows: Iterable[dict[str, Any]]) -> list[Unit]:
    """Units from tidy task rows (dicts of the tidy_tasks columns). Blank justifications skipped.

    A written item's (T1's) unit is its description: it asks for no justification, and the
    description is the reasoning.
    """
    units = []
    for row in rows:
        text = row.get("answer" if row.get("kind") == WRITTEN_KIND else "justification")
        # A CSV round trip turns an empty cell into NaN.
        if not isinstance(text, str):
            text = ""
        text = text.strip()
        if not text:
            continue
        units.append(
            Unit(
                unit_id(str(row["session_id"]), str(row["task_id"])),
                text,
                str(row["participant_id"]),
                str(row["session_id"]),
                str(row["condition"]),
                str(row["form"]),
                str(row["task_id"]),
            )
        )
    ids = [u.unit_id for u in units]
    if len(set(ids)) != len(ids):
        raise CodingError("Two answers share a unit id: a task was answered twice in one session")
    return units


def shuffled(units: Sequence[Unit], seed: int = SEED) -> list[Unit]:
    ordered = sorted(units, key=lambda u: u.unit_id)  # independent of input order
    random.Random(seed).shuffle(ordered)
    return ordered


def double_coded_sample(
    units: Sequence[Unit], fraction: float = DOUBLE_CODED_FRACTION, seed: int = SEED
) -> set[str]:
    """Unit ids for the second coder: `fraction` of each condition, rounded up, seeded."""
    rng = random.Random(seed)
    chosen: set[str] = set()
    for condition in sorted({u.condition for u in units}):
        pool = sorted(u.unit_id for u in units if u.condition == condition)
        chosen.update(rng.sample(pool, math.ceil(len(pool) * fraction)))
    return chosen


def write_sheet(units: Sequence[Unit], path: Path, seed: int = SEED) -> None:
    """A blind coding sheet: unit id, text, and empty columns for the three codes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SHEET_COLUMNS)
        for unit in shuffled(units, seed):
            writer.writerow([unit.unit_id, unit.justification, *[""] * len(CODES)])


def write_key(units: Sequence[Unit], path: Path) -> None:
    """The unblinding map. For the analyst only -- never give this file to a coder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(KEY_COLUMNS)
        for unit in sorted(units, key=lambda u: u.unit_id):
            writer.writerow([getattr(unit, column) for column in KEY_COLUMNS])


def read_sheet(
    path: Path,
    expected_ids: set[str] | None = None,
    codes_read: Sequence[str] = CODES,
    columns: Sequence[str] = SHEET_COLUMNS,
) -> dict[str, dict[str, int]]:
    """A completed sheet as {unit_id: {code: 0 or 1}}. Refuses anything incomplete or unexpected.

    `codes_read` and `columns` default to the RQ2 sheet; the rubric sheets pass their own.
    """
    codes: dict[str, dict[str, int]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_columns = set(columns) - set(reader.fieldnames or ())
        if missing_columns:
            raise CodingError(f"{path.name} is missing columns {sorted(missing_columns)}")
        for line, row in enumerate(reader, start=2):
            uid = row["unit_id"]
            if uid in codes:
                raise CodingError(f"{path.name} line {line}: unit {uid} coded twice")
            values = {}
            for code in codes_read:
                raw = (row[code] or "").strip()
                if raw not in ("0", "1"):
                    raise CodingError(
                        f"{path.name} line {line}: {code} must be 0 or 1, got {raw!r}"
                    )
                values[code] = int(raw)
            codes[uid] = values
    if expected_ids is not None:
        unknown = set(codes) - expected_ids
        uncoded = expected_ids - set(codes)
        if unknown:
            raise CodingError(f"{path.name} has units not in this study: {sorted(unknown)[:5]}")
        if uncoded:
            raise CodingError(f"{path.name} leaves {len(uncoded)} units uncoded")
    return codes


def depth(codes: dict[str, int]) -> int:
    """Reasoning depth, 0-3: the number of the three features present."""
    return sum(codes[code] for code in CODES)


def cohens_kappa(first: Sequence[int], second: Sequence[int]) -> float:
    """Cohen's kappa for two raters' binary codes on the same units.

    Returns NaN when agreement by chance is total (p_e == 1) -- both raters used a single category
    throughout -- because kappa is undefined there, not 0 and not 1. With a rare code and around 60
    double-coded units that is a realistic outcome, so callers must report it rather than print NaN.
    """
    if len(first) != len(second):
        raise CodingError("Raters coded different numbers of units")
    n = len(first)
    if n == 0:
        return math.nan
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / n
    p1, p2 = sum(first) / n, sum(second) / n
    expected = p1 * p2 + (1 - p1) * (1 - p2)
    if math.isclose(expected, 1.0):
        return math.nan
    return (observed - expected) / (1 - expected)


def kappa_report(
    primary: dict[str, dict[str, int]],
    secondary: dict[str, dict[str, int]],
    codes: Sequence[str] = CODES,
) -> dict[str, dict[str, float]]:
    """Kappa per code with prevalence, over the units both coders coded.

    Per code rather than one pooled value: kappa depends on prevalence, and a low value on a rare
    code reflects rarity, not unreliable coding. Section 7 asks for exactly this.
    """
    shared = sorted(set(primary) & set(secondary))
    if len(shared) != len(secondary):
        raise CodingError("The second coder coded units the first coder did not")
    report = {}
    for code in codes:
        a = [primary[u][code] for u in shared]
        b = [secondary[u][code] for u in shared]
        report[code] = {
            "kappa": cohens_kappa(a, b),
            "prevalence": (sum(a) + sum(b)) / (2 * len(shared)) if shared else math.nan,
            "agreement": sum(x == y for x, y in zip(a, b, strict=True)) / len(shared)
            if shared
            else math.nan,
            "n": len(shared),
        }
    return report


def format_kappa(value: float) -> str:
    return "undefined (no variance)" if math.isnan(value) else f"{value:.3f}"


# --- T1's rubric ---------------------------------------------------------------------------------


def build_rubric_units(rows: Iterable[dict[str, Any]]) -> list[Unit]:
    """T1 descriptions to score, from tidy task rows. A skipped description is not coded: it
    scores incorrect without a coder (study-design.md section 7)."""
    return build_units(row for row in rows if row.get("kind") == WRITTEN_KIND)


def write_rubric_sheet(units: Sequence[Unit], path: Path, seed: int = SEED) -> None:
    """A blind rubric sheet: unit id, the description, its form's three parts, empty fields.

    The parts name the form's countries, which the description names anyway; condition,
    participant and session stay in the key file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(RUBRIC_SHEET_COLUMNS)
        for unit in shuffled(units, seed):
            parts = answer_keys.rubric_parts(unit.form, unit.task_id)
            writer.writerow(
                [unit.unit_id, unit.justification, parts["a"], parts["b"], parts["c"]]
                + [""] * len(RUBRIC_FIELDS)
            )


def read_rubric_sheet(path: Path, expected_ids: set[str]) -> dict[str, dict[str, int]]:
    """A completed rubric sheet. Every unit must be coded: both coders code all of them."""
    return read_sheet(path, expected_ids, RUBRIC_FIELDS, RUBRIC_SHEET_COLUMNS)


def rubric_correct(fields: dict[str, int]) -> bool:
    """Correct when all three parts are stated and none is contradicted (section 4)."""
    return bool(fields["a"] and fields["b"] and fields["c"] and not fields["contradicts"])


def disagreements(first: dict[str, dict[str, int]], second: dict[str, dict[str, int]]) -> list[str]:
    """Unit ids on which the two coders differ in any field, sorted."""
    if set(first) != set(second):
        raise CodingError("The two rubric sheets do not cover the same units")
    return sorted(uid for uid in first if first[uid] != second[uid])


def write_disagreements(
    units: Sequence[Unit],
    first: dict[str, dict[str, int]],
    second: dict[str, dict[str, int]],
    path: Path,
) -> int:
    """The units to settle, still blind: both codings, and empty fields for the settled one."""
    by_id = {unit.unit_id: unit for unit in units}
    open_ids = disagreements(first, second)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "unit_id",
                "description",
                *[f"coder1_{f}" for f in RUBRIC_FIELDS],
                *[f"coder2_{f}" for f in RUBRIC_FIELDS],
                *RUBRIC_FIELDS,
            ]
        )
        for uid in open_ids:
            writer.writerow(
                [uid, by_id[uid].justification]
                + [first[uid][f] for f in RUBRIC_FIELDS]
                + [second[uid][f] for f in RUBRIC_FIELDS]
                + [""] * len(RUBRIC_FIELDS)
            )
    return len(open_ids)


def read_settled(path: Path, expected_ids: set[str]) -> dict[str, dict[str, int]]:
    """The settled codings for the disagreements, keyed by unit. No file: nothing settled yet."""
    if not path.exists():
        return {}
    # Only the disputed units are settled, so the file covers some of `expected_ids`, not all.
    settled = read_sheet(path, None, RUBRIC_FIELDS, SETTLED_COLUMNS)
    unknown = set(settled) - expected_ids
    if unknown:
        raise CodingError(f"{path.name} has units not in this study: {sorted(unknown)[:5]}")
    return settled


def settle(
    first: dict[str, dict[str, int]],
    second: dict[str, dict[str, int]],
    settled: dict[str, dict[str, int]],
) -> dict[str, bool]:
    """Each unit's verdict: the coders' shared coding, or the settled one where they differed.

    Refuses while any disagreement is unsettled, and refuses a settled coding for a unit the
    coders agreed on, which would overrule an agreement nobody disputed.
    """
    open_ids = disagreements(first, second)
    unsettled = [uid for uid in open_ids if uid not in settled]
    if unsettled:
        raise CodingError(f"{len(unsettled)} rubric disagreements are not settled yet")
    extra = sorted(set(settled) - set(open_ids))
    if extra:
        raise CodingError(f"Settled codings for units the coders agreed on: {extra[:5]}")
    return {uid: rubric_correct(settled.get(uid, first[uid])) for uid in first}


def write_verdicts(units: Sequence[Unit], verdicts: dict[str, bool], path: Path) -> None:
    """Unblinded verdicts, (session_id, task_id) -> correct, for `scripts/score_study.py`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(VERDICT_COLUMNS)
        for unit in sorted(units, key=lambda u: (u.session_id, u.task_id)):
            writer.writerow([unit.session_id, unit.task_id, int(verdicts[unit.unit_id])])


def read_verdicts(path: Path) -> dict[tuple[str, str], bool]:
    """The verdicts file as `reshape.tidy_tasks` takes it. No file: nothing coded yet."""
    if not path.exists():
        return {}
    verdicts: dict[tuple[str, str], bool] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            if row["correct"] not in ("0", "1"):
                raise CodingError(f"{path.name} line {line}: correct must be 0 or 1")
            verdicts[(row["session_id"], row["task_id"])] = row["correct"] == "1"
    return verdicts
