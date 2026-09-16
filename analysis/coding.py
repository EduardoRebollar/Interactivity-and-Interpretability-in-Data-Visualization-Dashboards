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

CODES = ("cites_values", "compares_series", "notes_uncertainty")
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
    """Units from tidy task rows (dicts of the tidy_tasks columns). Blank justifications skipped."""
    units = []
    for row in rows:
        text = (row.get("justification") or "").strip()
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


def read_sheet(path: Path, expected_ids: set[str] | None = None) -> dict[str, dict[str, int]]:
    """A completed sheet as {unit_id: {code: 0 or 1}}. Refuses anything incomplete or unexpected."""
    codes: dict[str, dict[str, int]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_columns = set(SHEET_COLUMNS) - set(reader.fieldnames or ())
        if missing_columns:
            raise CodingError(f"{path.name} is missing columns {sorted(missing_columns)}")
        for line, row in enumerate(reader, start=2):
            uid = row["unit_id"]
            if uid in codes:
                raise CodingError(f"{path.name} line {line}: unit {uid} coded twice")
            values = {}
            for code in CODES:
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
    primary: dict[str, dict[str, int]], secondary: dict[str, dict[str, int]]
) -> dict[str, dict[str, float]]:
    """Kappa per code with prevalence, over the units both coders coded.

    Per code rather than one pooled value: kappa depends on prevalence, and a low value on a rare
    code reflects rarity, not unreliable coding. Section 7 asks for exactly this.
    """
    shared = sorted(set(primary) & set(secondary))
    if len(shared) != len(secondary):
        raise CodingError("The second coder coded units the first coder did not")
    report = {}
    for code in CODES:
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
