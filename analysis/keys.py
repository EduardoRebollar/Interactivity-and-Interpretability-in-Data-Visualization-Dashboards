"""The answer key, derived from the data rather than written down.

Each item's correct option is **computed** from `data/deploy/coverage.csv` by the rule its prompt
states, then compared against `EXPECTED`, a table transcribed by hand from `docs/study-design.md`
section 4. The two must agree or `check()` reports it, and `tests/test_scoring.py` fails.

That duplication is the point. `docs/study-design.md` carried a wrong key for T1 (it said 2; the
data says 1) and nothing noticed, because a hand-written key has nothing checking it. A derived key
alone would not catch a rule implemented wrongly; a transcribed key alone would not catch a wrong
transcription or a data refresh. Together, either kind of error fails loudly.

**Stdlib and `src.runtime_data` only -- no pandas here**, unlike the rest of `analysis/`. The key
must come from the same bytes, through the same loader, as the chart each participant actually saw.
A second read path for the CSV would reopen the class of bug the loader-agreement test exists to
close.

Item parameters live in `PARAMS`, not in parsed prompt text: parsing English would couple the key
to the wording of the question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src import runtime_data, tasks
from src.flow import Task
from src.runtime_data import Row


class KeyDerivationError(ValueError):
    """An item whose key cannot be derived -- which means the item itself is not well-posed."""


# Trend items need a clear winner. A data refresh that brings the runner-up within this many
# percentage points would make two options defensible; that must fail, not quietly score.
MIN_TREND_MARGIN_PP = 5.0

REFERENCE = "World"

# (form, task_id) -> the parameters each rule runs on.
PARAMS: dict[tuple[str, str], dict[str, Any]] = {
    ("A", "T1"): {"year": 2010},
    ("A", "T2"): {"window": (2015, 2021), "direction": "fall"},
    ("A", "T3"): {"window": (2000, 2012), "direction": "rise"},
    ("A", "T4"): {"overtaker": "India", "overtaken": "Brazil"},
    ("A", "T5"): {"overtaker": "China", "overtaken": "Brazil"},
    ("A", "T6"): {"series": ("United Kingdom",), "before": 2019},
    ("B", "T1"): {"year": 2020},
    ("B", "T2"): {"window": (2010, 2014), "direction": "fall"},
    ("B", "T3"): {"window": (2012, 2024), "direction": "rise"},
    ("B", "T4"): {"overtaker": "India", "overtaken": "Ukraine"},
    ("B", "T5"): {"overtaker": "China", "overtaken": "Ukraine"},
    # "before each line begins": the gap is each series' own leading run of unreported years.
    ("B", "T6"): {"series": ("Ethiopia", "Nigeria", "India"), "before": None},
}

# Transcribed BY HAND from docs/study-design.md section 4. Deliberately duplicated: a cross-check
# that reads its own answer is not a check. Never generate this from `derive()`.
EXPECTED: dict[tuple[str, str], str] = {
    ("A", "T1"): "1",
    ("A", "T2"): "Brazil",
    ("A", "T3"): "Ethiopia",
    ("A", "T4"): "2017-2020",
    ("A", "T5"): "2009-2012",
    ("A", "T6"): "Coverage was not reported for those years",
    ("B", "T1"): "1",
    ("B", "T2"): "Ukraine",
    ("B", "T3"): "Nigeria",
    ("B", "T4"): "2009-2012",
    ("B", "T5"): "2004-2008",
    ("B", "T6"): "Coverage was not reported for those years",
}

# The option asserting the gap is "not reported". `derive` proves it rather than assuming it.
NOT_REPORTED = tasks.GAP_OPTIONS[0]


@dataclass(frozen=True, slots=True)
class DerivedKey:
    task_id: str
    form: str
    kind: str
    correct: str  # the exact option label, which is exactly what `answer_submit` logs
    rule: str  # one line of prose stating the rule applied, for the methods appendix
    evidence: dict[str, Any] = field(default_factory=dict)


# --- Data access ------------------------------------------------------------------------------


def _value(entity: str, vaccine: str, year: int, rows: tuple[Row, ...]) -> float | None:
    for row in runtime_data.series(entity, vaccine, rows):
        if row.year == year:
            return row.coverage_pct
    raise KeyDerivationError(f"No row for {entity} {vaccine} {year}")


def _required(entity: str, vaccine: str, year: int, rows: tuple[Row, ...]) -> float:
    value = _value(entity, vaccine, year, rows)
    if value is None:
        raise KeyDerivationError(
            f"{entity} {vaccine} {year} is not reported; the item has no answer"
        )
    return value


# --- Bands --------------------------------------------------------------------------------------


def _parse_band(band: str) -> tuple[int, int]:
    start, end = band.split("-")
    return int(start), int(end)


def band_for(year: int, bands: tuple[str, ...] = tasks.CROSSING_BANDS) -> str:
    """The option band containing `year`. Bands are inclusive at both ends.

    Raises for a year no band covers, rather than picking the nearest: an item whose crossing falls
    outside every option cannot be answered correctly by anyone.
    """
    for band in bands:
        start, end = _parse_band(band)
        if start <= year <= end:
            return band
    raise KeyDerivationError(f"No answer band contains {year}; bands are {bands}")


def adjacent_bands(year: int, bands: tuple[str, ...] = tasks.CROSSING_BANDS) -> set[str]:
    """The key band plus the bands containing year - 1 and year + 1.

    The pre-registered SECONDARY scoring for T5 (study-design.md section 4), whose keys both sit on
    the last year of their band, so a one-year-late reading lands in the next band.
    """
    accepted = {band_for(year, bands)}
    for neighbour in (year - 1, year + 1):
        try:
            accepted.add(band_for(neighbour, bands))
        except KeyDerivationError:
            continue
    return accepted


# --- Rules --------------------------------------------------------------------------------------


def _reference(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    year = params["year"]
    world = _required(REFERENCE, task.vaccine, year, rows)
    countries = [e for e in task.entities if e != REFERENCE]
    values = {c: _required(c, task.vaccine, year, rows) for c in countries}
    above = sorted(c for c, v in values.items() if v > world)
    count = len(above)
    correct = str(count) if count < 4 else "4 or more"
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        correct,
        f"countries shown strictly above {REFERENCE} in {year}; a tie is not above",
        {"year": year, "world": world, "values": values, "above": above},
    )


def _trend(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    start, end = params["window"]
    direction = params["direction"]
    deltas = {
        c: _required(c, task.vaccine, end, rows) - _required(c, task.vaccine, start, rows)
        for c in task.options
    }
    # Largest fall is the most negative change; largest rise the most positive.
    ranked = sorted(deltas, key=deltas.get, reverse=direction == "rise")
    winner, runner_up = ranked[0], ranked[1]
    margin = abs(deltas[winner] - deltas[runner_up])
    if margin < MIN_TREND_MARGIN_PP:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {winner} leads {runner_up} by only {margin:g} pp; "
            f"two options are defensible"
        )
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        winner,
        f"largest {direction} in coverage from {start} to {end}, in percentage points",
        {"window": (start, end), "deltas": deltas, "runner_up": runner_up, "margin_pp": margin},
    )


def _crossing(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    overtaker, overtaken = params["overtaker"], params["overtaken"]
    years = sorted({r.year for r in runtime_data.series(overtaker, task.vaccine, rows)})
    differences = {}
    for year in years:
        a = _value(overtaker, task.vaccine, year, rows)
        b = _value(overtaken, task.vaccine, year, rows)
        if a is not None and b is not None:
            differences[year] = a - b
    ordered = sorted(differences)

    def first(predicate) -> int:
        for previous, year in zip(ordered, ordered[1:], strict=False):
            if predicate(differences[previous], differences[year]):
                return year
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {overtaker} never overtakes {overtaken}"
        )

    strictly_above = first(lambda before, now: before <= 0 < now)
    not_below = first(lambda before, now: before < 0 <= now)

    # Well-posed only if it is ONE overtaking: once above, the overtaker must stay above. Otherwise
    # "when did it overtake" has more than one true answer.
    back_below = [y for y in ordered if y > strictly_above and differences[y] <= 0]
    if back_below:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {overtaker} falls back to or below {overtaken} in "
            f"{back_below}; the item has more than one crossing"
        )

    correct = band_for(strictly_above)
    # A plateau of exact ties before the crossing (A-T5: 99.0 == 99.0 for 2009-2011) means two
    # reasonable definitions of the crossing year disagree. The key is safe only while they agree
    # at the level participants answer at: the band.
    if band_for(not_below) != correct:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: the crossing is {strictly_above} by 'strictly above' "
            f"but {not_below} by 'no longer below', and those fall in different bands"
        )
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        correct,
        f"band containing the first year {overtaker} is strictly above {overtaken}",
        {
            "cross_year": strictly_above,
            "not_below_year": not_below,
            "differences": differences,
            "adjacent_bands": sorted(adjacent_bands(strictly_above)),
        },
    )


def _gap(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    missing: dict[str, list[int]] = {}
    for entity in params["series"]:
        observations = runtime_data.series(entity, task.vaccine, rows)
        if params["before"] is not None:
            window = [r for r in observations if r.year < params["before"]]
        else:
            # The leading run of unreported years, up to where the line begins.
            first_reported = next(
                (r.year for r in observations if r.coverage_pct is not None), None
            )
            if first_reported is None:
                raise KeyDerivationError(f"{entity} {task.vaccine} is never reported")
            window = [r for r in observations if r.year < first_reported]
        if not window:
            raise KeyDerivationError(
                f"{task.form}-{task.task_id}: {entity} has no gap to ask about"
            )
        # The distinction the item exists to test: absent is not zero. A recorded 0.0 would make
        # "coverage was zero" the true answer instead.
        reported = [(r.year, r.coverage_pct) for r in window if r.coverage_pct is not None]
        if reported:
            raise KeyDerivationError(
                f"{task.form}-{task.task_id}: {entity} has reported values inside the gap window: "
                f"{reported}"
            )
        missing[entity] = [r.year for r in window]
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        NOT_REPORTED,
        "every year in the window is unreported (None), not recorded as zero",
        {"missing_years": missing},
    )


_RULES = {"reference": _reference, "trend": _trend, "crossing": _crossing, "gap": _gap}


# --- Public API -----------------------------------------------------------------------------


def derive(task: Task, rows: tuple[Row, ...] | None = None) -> DerivedKey:
    """Compute one item's key from the data. Raises `KeyDerivationError` if it is not well-posed."""
    rows = rows if rows is not None else runtime_data.load_rows()
    params = PARAMS.get((task.form, task.task_id))
    if params is None:
        raise KeyDerivationError(f"No parameters for {task.form}-{task.task_id}")
    rule = _RULES.get(task.kind)
    if rule is None:
        raise KeyDerivationError(f"No scoring rule for kind {task.kind!r}")
    key = rule(task, params, rows)
    if key.correct not in task.options:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: derived key {key.correct!r} is not one of the options "
            f"{task.options}; no participant could choose it"
        )
    return key


def key_table(rows: tuple[Row, ...] | None = None) -> dict[tuple[str, str], DerivedKey]:
    """Every scored item's key, by (form, task_id)."""
    rows = rows if rows is not None else runtime_data.load_rows()
    return {
        (task.form, task.task_id): derive(task, rows)
        for form in sorted(tasks.FORMS)
        for task in tasks.for_form(form)
    }


def check(
    expected: dict[tuple[str, str], str] | None = None, rows: tuple[Row, ...] | None = None
) -> list[str]:
    """Compare derived keys with the transcribed table. Returns problems; empty means agreement."""
    expected = EXPECTED if expected is None else expected
    problems: list[str] = []
    derived: dict[tuple[str, str], DerivedKey] = {}
    rows = rows if rows is not None else runtime_data.load_rows()
    for form in sorted(tasks.FORMS):
        for task in tasks.for_form(form):
            try:
                derived[(form, task.task_id)] = derive(task, rows)
            except KeyDerivationError as exc:
                problems.append(f"{form}-{task.task_id}: cannot derive a key: {exc}")
    for item in sorted(set(expected) | set(derived)):
        if item not in expected:
            problems.append(f"{item[0]}-{item[1]}: derived but missing from EXPECTED")
        elif item not in derived:
            continue  # already reported above
        elif derived[item].correct != expected[item]:
            problems.append(
                f"{item[0]}-{item[1]}: data says {derived[item].correct!r}, "
                f"study-design.md says {expected[item]!r}"
            )
    return problems


def is_correct(form: str, task_id: str, answer: Any, keys: dict | None = None) -> bool | None:
    """Primary (strict) scoring. None for the unscored practice item or an unknown item."""
    keys = keys if keys is not None else key_table()
    key = keys.get((form, task_id))
    if key is None:
        return None
    return answer == key.correct


def is_correct_adjacent(
    form: str, task_id: str, answer: Any, keys: dict | None = None
) -> bool | None:
    """Secondary scoring: adjacent-band credit, T5 only. None for every other item."""
    if task_id != "T5":
        return None
    keys = keys if keys is not None else key_table()
    key = keys.get((form, task_id))
    if key is None:
        return None
    return answer in set(key.evidence["adjacent_bands"])
