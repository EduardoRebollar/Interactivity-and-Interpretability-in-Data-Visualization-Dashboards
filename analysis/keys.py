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

**Each rule also enforces the item acceptance rule** (`docs/study-design.md` section 4). A key that
is right only for a reader who can see exact values measures whether hover exists, not how well
someone interprets a chart, so every item must survive the reading errors a participant without
hover makes: a slip of one year along the x axis, and a few points along y. An item that fails is
refused here, the same way a wrong key is, so a fragile item cannot reach a participant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, product
from typing import Any

from src import config, runtime_data, tasks
from src.flow import Task
from src.runtime_data import Row


class KeyDerivationError(ValueError):
    """An item whose key cannot be derived -- which means the item itself is not well-posed."""


# Trend items need a clear winner. A data refresh that brings the runner-up within this many
# percentage points would make two options defensible; that must fail, not quietly score.
MIN_TREND_MARGIN_PP = 5.0

# --- The item acceptance rule (study-design.md section 4) ---------------------------------------
# One point is 4 px on the chart and a marker is 10 px across, so two values 2 points apart draw
# overlapping markers. 5 points (20 px) is the smallest gap that reads unaided.
MIN_SEPARATION_PP = 5.0
# A crossing must be drawn at least this far inside its answer band, so a reading one year off
# still lands in the right band.
MIN_BAND_INSET_YEARS = 1.0
# A gap series must be distinguishable from every other line: within this many points of another
# line in more than half its reported years, and it is hidden behind that line.
MIN_LINE_SEPARATION_PP = 4.0

REFERENCE = "World"

# (form, task_id) -> the parameters each rule runs on.
PARAMS: dict[tuple[str, str], dict[str, Any]] = {
    ("A", "T1"): {"year": 2005},
    ("A", "T2"): {"window": (2015, 2021), "direction": "fall"},
    ("A", "T3"): {"window": (2000, 2012), "direction": "rise"},
    ("A", "T4"): {"overtaker": "India", "overtaken": "Brazil"},
    ("A", "T5"): {"overtaker": "China", "overtaken": "United Kingdom"},
    ("A", "T6"): {"series": ("United Kingdom",), "before": 2019},
    ("B", "T1"): {"year": 2015},
    ("B", "T2"): {"window": (2010, 2015), "direction": "fall"},
    ("B", "T3"): {"window": (2013, 2024), "direction": "rise"},
    ("B", "T4"): {"overtaker": "China", "overtaken": "Ukraine"},
    ("B", "T5"): {"overtaker": "China", "overtaken": "Brazil"},
    # "before each line begins": the gap is each series' own leading run of unreported years.
    ("B", "T6"): {"series": ("Ethiopia", "Nigeria", "India"), "before": None},
}

# Transcribed BY HAND from docs/study-design.md section 4. Deliberately duplicated: a cross-check
# that reads its own answer is not a check. Never generate this from `derive()`.
EXPECTED: dict[tuple[str, str], str] = {
    ("A", "T1"): "1",
    ("A", "T2"): "Brazil",
    ("A", "T3"): "Ethiopia",
    ("A", "T4"): "2013-2016",
    ("A", "T5"): "2004-2008",
    ("A", "T6"): "Coverage was not reported for those years",
    ("B", "T1"): "1",
    ("B", "T2"): "Ukraine",
    ("B", "T3"): "Nigeria",
    ("B", "T4"): "2004-2008",
    ("B", "T5"): "2009-2012",
    ("B", "T6"): "Coverage was not reported for those years",
}

# The option asserting the gap is "not reported". `derive` proves it rather than assuming it, and
# refuses the key if this text stops being one of the options. Looked up by wording, not position:
# option order is chosen so the key does not sit in the same place every time (section 5).
NOT_REPORTED = "Coverage was not reported for those years"


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

    The pre-registered SECONDARY scoring for the crossing items, T4 and T5 (study-design.md
    sections 4 and 7). A key on the last year of its band -- both T4 keys, and B-T5's -- sends a
    one-year-late reading into the next band.
    """
    accepted = {band_for(year, bands)}
    for neighbour in (year - 1, year + 1):
        try:
            accepted.add(band_for(neighbour, bands))
        except KeyDerivationError:
            continue
    return accepted


# --- Rules --------------------------------------------------------------------------------------


def _misreadings(year: int) -> list[int]:
    """The year itself and the years either side that are on the chart: a one-year slip."""
    return [y for y in (year - 1, year, year + 1) if config.YEAR_MIN <= y <= config.YEAR_MAX]


def _reference(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    year = params["year"]
    world = _required(REFERENCE, task.vaccine, year, rows)
    countries = [e for e in task.entities if e != REFERENCE]
    values = {c: _required(c, task.vaccine, year, rows) for c in countries}
    above = sorted(c for c, v in values.items() if v > world)
    count = len(above)
    correct = str(count) if count < 4 else "4 or more"

    # Acceptance: the count must not depend on a close call, at the year asked or a year either
    # side of it. A year with an unreported value is skipped: there is no point there to misread.
    closest = closest_pair = float("inf")
    for y in _misreadings(year):
        at = {e: _value(e, task.vaccine, y, rows) for e in (*countries, REFERENCE)}
        if any(v is None for v in at.values()):
            continue
        for country in countries:
            margin = at[country] - at[REFERENCE]
            closest = min(closest, abs(margin))
            if abs(margin) < MIN_SEPARATION_PP:
                raise KeyDerivationError(
                    f"{task.form}-{task.task_id}: {country} is {margin:+g} pts from {REFERENCE} "
                    f"in {y}; closer than {MIN_SEPARATION_PP:g} pts, above or below is a close call"
                )
        if sum(at[c] > at[REFERENCE] for c in countries) != count:
            raise KeyDerivationError(
                f"{task.form}-{task.task_id}: the count in {y} differs from {year}'s; reading the "
                f"year one off changes the answer"
            )
        # Counting needs every line to be told apart from the others where it is counted.
        for a, b in combinations(countries, 2):
            closest_pair = min(closest_pair, abs(at[a] - at[b]))
            if abs(at[a] - at[b]) < MIN_SEPARATION_PP:
                raise KeyDerivationError(
                    f"{task.form}-{task.task_id}: {a} and {b} are {abs(at[a] - at[b]):g} pts apart "
                    f"in {y}; their lines cannot be counted separately"
                )
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        correct,
        f"countries shown strictly above {REFERENCE} in {year}; a tie is not above",
        {
            "year": year,
            "world": world,
            "values": values,
            "above": above,
            "closest_to_reference_pp": closest,
            "closest_pair_pp": closest_pair,
        },
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

    # Acceptance: reading either end of the window one year off must not change the winner. The
    # item asks about a trend; an answer that hinges on one year's dip is a precision task.
    worst = margin
    for a, b in product(_misreadings(start), _misreadings(end)):
        if a >= b:
            continue
        at = {
            c: (_value(c, task.vaccine, a, rows), _value(c, task.vaccine, b, rows))
            for c in task.options
        }
        if any(v is None for pair in at.values() for v in pair):
            continue
        shifted = {c: later - earlier for c, (earlier, later) in at.items()}
        order = sorted(shifted, key=shifted.get, reverse=direction == "rise")
        if order[0] != winner:
            raise KeyDerivationError(
                f"{task.form}-{task.task_id}: read as {a} to {b}, {order[0]} "
                f"({shifted[order[0]]:+g}) beats {winner} ({shifted[winner]:+g}); a one-year slip "
                f"changes the answer"
            )
        worst = min(worst, abs(shifted[order[0]] - shifted[order[1]]))
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        winner,
        f"largest {direction} in coverage from {start} to {end}, in percentage points",
        {
            "window": (start, end),
            "deltas": deltas,
            "runner_up": runner_up,
            "margin_pp": margin,
            "worst_misread_margin_pp": worst,
        },
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
    # A plateau of exact ties before the crossing (B-T5: 99.0 == 99.0 for 2009-2011) means two
    # reasonable definitions of the crossing year disagree. The key is safe only while they agree
    # at the level participants answer at: the band.
    if band_for(not_below) != correct:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: the crossing is {strictly_above} by 'strictly above' "
            f"but {not_below} by 'no longer below', and those fall in different bands"
        )

    # Acceptance: what a participant sees is where the two lines meet, not the first year of a
    # rule. That point must sit far enough inside the key band that a reading one year off still
    # lands in it. A drawn crossing at 2016.1 keyed to 2017-2020 is scored wrong for everyone who
    # reads the chart correctly.
    previous = ordered[ordered.index(strictly_above) - 1]
    before, after = differences[previous], differences[strictly_above]
    intersection = previous + (0 - before) / (after - before) * (strictly_above - previous)
    start, end = _parse_band(correct)
    inset = min(intersection - (start - 0.5), (end + 0.5) - intersection)
    if inset < MIN_BAND_INSET_YEARS:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: the lines meet at {intersection:.2f}, only {inset:.2f} "
            f"years inside {correct}; a reading one year off lands in another band"
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
            "intersection": round(intersection, 2),
            "band_inset_years": round(inset, 2),
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

        # Acceptance: the line the question is about must be findable. A gap series drawn on top
        # of another line for most of its reported span is hidden, and only a participant who can
        # filter the other line away can see it -- an item that measures the filter, not reading.
        reported_years = [r.year for r in observations if r.coverage_pct is not None]
        for other in task.entities:
            if other == entity:
                continue
            close = 0
            for year in reported_years:
                theirs = _value(other, task.vaccine, year, rows)
                ours = _value(entity, task.vaccine, year, rows)
                if theirs is not None and abs(theirs - ours) < MIN_LINE_SEPARATION_PP:
                    close += 1
            if close * 2 > len(reported_years):
                raise KeyDerivationError(
                    f"{task.form}-{task.task_id}: {entity}'s line is within "
                    f"{MIN_LINE_SEPARATION_PP:g} pts of {other} in {close} of its "
                    f"{len(reported_years)} reported years; it is hidden behind that line"
                )
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
    """Secondary scoring: adjacent-band credit for the crossing items (T4, T5). None otherwise."""
    keys = keys if keys is not None else key_table()
    key = keys.get((form, task_id))
    if key is None or key.kind != "crossing":
        return None
    return answer in set(key.evidence["adjacent_bands"])
