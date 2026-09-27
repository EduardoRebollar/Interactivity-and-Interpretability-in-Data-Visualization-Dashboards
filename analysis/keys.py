"""The answer key, derived from the data rather than written down.

Each item's correct option is **computed** from `data/deploy/coverage.csv` by the rule its prompt
states, then compared against `EXPECTED`, a table transcribed by hand from `docs/study-design.md`
section 4. The two must agree or `check()` reports it, and `tests/test_scoring.py` fails.

That duplication is the point. `docs/study-design.md` once carried a wrong key (it said 2; the data
said 1) and nothing noticed, because a hand-written key has nothing checking it. A derived key alone
would not catch a rule implemented wrongly; a transcribed key alone would not catch a wrong
transcription or a data refresh. Together, either kind of error fails loudly.

**Stdlib and `src.runtime_data` only -- no pandas here**, unlike the rest of `analysis/`. The key
must come from the same bytes, through the same loader, as the chart each participant actually saw.
A second read path for the CSV would reopen the class of bug the loader-agreement test exists to
close.

The years an item shows come from the task itself (`task.years`), the same field the chart is drawn
from. What the chart does not need -- the country a line item is about, the rank asked for, the
threshold, which line overtakes which -- lives in `PARAMS`, not in parsed prompt text: parsing
English would couple the key to the wording of the question.

**Each rule also enforces the item acceptance rule** (`docs/study-design.md` section 4). A key that
is right only for a reader who can see exact values measures whether hover exists, not how well
someone interprets a chart, so every item must survive the reading errors a participant without
hover makes: a slip of one year along the x axis, a few points along a value axis, and more than a
few points on a colour scale. An item that fails is refused here, the same way a wrong key is, so a
fragile item cannot reach a participant.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from src import config, runtime_data, tasks
from src.flow import Task
from src.runtime_data import Row


class KeyDerivationError(ValueError):
    """An item whose key cannot be derived -- which means the item itself is not well-posed."""


# --- The item acceptance rule (study-design.md section 4) ---------------------------------------
# On the line and bar charts one point is 4 px, so two values 5 points apart are 20 px apart, the
# smallest gap that reads unaided. Every position judgement must clear it.
MIN_SEPARATION_PP = 5.0
# The heatmap and the map carry value as colour. On the sequential scale one point moves lightness
# by 0.73-0.86 L* (measured along config.SEQUENTIAL_SCALE), and colour is judged less precisely than
# position, between patches that are not side by side. Twice the position floor: 10 points is at
# least 7.3 L*.
MIN_COLOUR_SEPARATION_PP = 10.0
# Scatter dots are 12 px across at 4 px a point. Centres closer than 4 points (16 px) overlap enough
# that one dot hides another.
MIN_DOT_DISTANCE_PP = 4.0
# A crossing must be drawn at least this far inside its answer band, so a reading one year off
# still lands in the right band.
MIN_BAND_INSET_YEARS = 1.0
# The written item (T1): every shape the rubric names must be large enough that a static reader
# cannot miss it. A rise of 25 points is 100 px; a dip of 12 points inside it would read as a fall.
MIN_TREND_PP = 25.0
MAX_RISER_DIP_PP = 12.0
MIN_RECOVERY_PP = 15.0
# Another line within 5 points of a named one for this many years in a row runs alongside it long
# enough to be followed by mistake.
MAX_CLOSE_RUN_YEARS = 4

# (form, task_id) -> what the rule needs that the chart does not.
PARAMS: dict[tuple[str, str], dict[str, Any]] = {
    ("A", "T1"): {"riser": "India", "faller": "Ukraine"},
    ("A", "T2"): {"rank": 3},
    ("A", "T3"): {},
    ("A", "T4"): {},
    ("A", "T5"): {"threshold": 50},
    ("A", "T6"): {"overtaker": "Ethiopia", "overtaken": "Central African Republic"},
    ("B", "T1"): {"riser": "Uganda", "faller": "Brazil"},
    ("B", "T2"): {"rank": 3},
    ("B", "T3"): {},
    ("B", "T4"): {},
    ("B", "T5"): {"threshold": 50},
    ("B", "T6"): {"overtaker": "Pakistan", "overtaken": "Mozambique"},
}

# Transcribed BY HAND from docs/study-design.md section 4. Deliberately duplicated: a cross-check
# that reads its own answer is not a check. Never generate this from `derive()`. T1 is written and
# scored by rubric, so its entry says so; `derive()` still checks its acceptance rule.
RUBRIC = "rubric"
EXPECTED: dict[tuple[str, str], str] = {
    ("A", "T1"): RUBRIC,
    ("A", "T2"): "India",
    ("A", "T3"): "Niger",
    ("A", "T4"): "Chad",
    ("A", "T5"): "3",
    ("A", "T6"): "2004-2008",
    ("B", "T1"): RUBRIC,
    ("B", "T2"): "Colombia",
    ("B", "T3"): "India",
    ("B", "T4"): "Afghanistan",
    ("B", "T5"): "2",
    ("B", "T6"): "2017-2020",
}


@dataclass(frozen=True, slots=True)
class DerivedKey:
    task_id: str
    form: str
    kind: str
    correct: str  # the exact option label `answer_submit` logs, or RUBRIC for the written item
    rule: str  # one line of prose stating the rule applied, for the methods appendix
    evidence: dict[str, Any] = field(default_factory=dict)


# --- Data access ------------------------------------------------------------------------------


def _value(entity: str, vaccine: str, year: int, rows: tuple[Row, ...]) -> float | None:
    for row in runtime_data.series(entity, vaccine, rows):
        if row.year == year:
            return row.coverage_pct
    raise KeyDerivationError(f"No row for {entity} {vaccine} {year}")


def _required(task: Task, entity: str, year: int, rows: tuple[Row, ...]) -> float:
    """A value the item cannot do without: a bar, a dot, a cell or a country with nothing to show
    would leave the chart unreadable at exactly the point the question is about."""
    value = _value(entity, task.vaccine, year, rows)
    if value is None:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {entity} {task.vaccine} {year} is not reported; the "
            "chart would have nothing to show there"
        )
    return value


def _reported(entity: str, vaccine: str, rows: tuple[Row, ...]) -> dict[int, float]:
    return {
        r.year: r.coverage_pct
        for r in runtime_data.series(entity, vaccine, rows)
        if r.coverage_pct is not None
    }


# --- Bands -------------------------------------------------------------------------------------


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

    The pre-registered SECONDARY scoring for the crossing item, T6 (study-design.md sections 4 and
    7). A key year on the edge of its band sends a one-year misreading into the next band.
    """
    accepted = {band_for(year, bands)}
    for neighbour in (year - 1, year + 1):
        # Off the end of the bands there is nothing to credit.
        with suppress(KeyDerivationError):
            accepted.add(band_for(neighbour, bands))
    return accepted


# --- Rules --------------------------------------------------------------------------------------


def _longest_close_run(a: dict[int, float], b: dict[int, float], years: list[int]) -> tuple:
    """The longest run of consecutive `years` in which the two lines are within 5 points, as
    (length, first year, last year). A year either line does not report breaks the run."""
    best, run, start = (0, None, None), 0, None
    for year in years:
        if year in a and year in b and abs(a[year] - b[year]) < MIN_SEPARATION_PP:
            run += 1
            start = year if run == 1 else start
            if run > best[0]:
                best = (run, start, year)
        else:
            run = 0
    return best


def _describe(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    """T1: a written description of two lines, scored by rubric (study-design.md sections 4 and 7).

    There is no option to derive. What is checked is that every shape the rubric names is there,
    large, and traceable without hover:
    - the riser gains at least 25 points and never dips more than 12 below a previous peak;
    - the faller drops at least 25 points from a peak and recovers at least 15 from its trough;
    - the two cross once, counting only years they are at least 5 points apart, riser from below;
    - no other line runs within 5 points of a named one for 5 or more consecutive years; for the
      faller, counted from its last peak before the trough, where its story starts.
    Both named lines must be reported in every year: a gap would be read as part of the trend.
    """
    riser, faller = params["riser"], params["faller"]
    item = f"{task.form}-{task.task_id}"
    years = list(range(config.YEAR_MIN, config.YEAR_MAX + 1))
    series: dict[str, dict[int, float]] = {}
    for entity in (riser, faller):
        if entity not in task.entities:
            raise KeyDerivationError(f"{item}: {entity} is not on the chart")
        series[entity] = _reported(entity, task.vaccine, rows)
        missing = [year for year in years if year not in series[entity]]
        if missing:
            raise KeyDerivationError(
                f"{item}: {entity} is not reported in {missing}; a gap would read as part of its "
                "trend"
            )
    up = [series[riser][year] for year in years]
    down = [series[faller][year] for year in years]

    rise = up[-1] - up[0]
    riser_dip = max(max(up[: i + 1]) - value for i, value in enumerate(up))
    if rise < MIN_TREND_PP or riser_dip > MAX_RISER_DIP_PP:
        raise KeyDerivationError(
            f"{item}: {riser} rises {rise:g} pts and dips {riser_dip:g} below a peak; the rubric "
            f"needs a rise of at least {MIN_TREND_PP:g} with no dip over {MAX_RISER_DIP_PP:g}"
        )
    trough = min(down)
    trough_at = down.index(trough)
    peak = max(down[: trough_at + 1])
    # The last year at the peak: the fall starts there.
    peak_at = max(i for i in range(trough_at + 1) if down[i] == peak)
    drop, recovery = peak - trough, down[-1] - trough
    if drop < MIN_TREND_PP or recovery < MIN_RECOVERY_PP:
        raise KeyDerivationError(
            f"{item}: {faller} drops {drop:g} pts and recovers {recovery:g}; the rubric needs a "
            f"drop of at least {MIN_TREND_PP:g} and a recovery of at least {MIN_RECOVERY_PP:g}"
        )

    # Which line is ahead, in every year they are clearly apart.
    sides = [
        (year, 1 if gap > 0 else -1)
        for year in years
        if abs(gap := series[riser][year] - series[faller][year]) >= MIN_SEPARATION_PP
    ]
    changes = [
        now for (_, before), (now, side) in zip(sides, sides[1:], strict=False) if side != before
    ]
    if len(changes) != 1 or sides[0][1] != -1:
        raise KeyDerivationError(
            f"{item}: {riser} and {faller} change places {len(changes)} times, starting with "
            f"{riser} {'below' if sides[0][1] == -1 else 'above'}; the rubric needs {riser} to "
            "pass from below exactly once"
        )

    fall_years = years[peak_at:]
    clearance: dict[str, dict[str, tuple]] = {}
    for other in task.entities:
        if other in (riser, faller):
            continue
        values = _reported(other, task.vaccine, rows)
        runs = {
            riser: _longest_close_run(series[riser], values, years),
            faller: _longest_close_run(series[faller], values, fall_years),
        }
        clearance[other] = runs
        for named, (length, first, last) in runs.items():
            if length > MAX_CLOSE_RUN_YEARS:
                raise KeyDerivationError(
                    f"{item}: {other}'s line runs within {MIN_SEPARATION_PP:g} pts of {named}'s "
                    f"for {length} years ({first}-{last}); it could be followed by mistake"
                )

    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        RUBRIC,
        f"written: {riser} rose, {faller} fell and recovered, {riser} passed {faller}",
        {
            "riser": riser,
            "faller": faller,
            "rise_pp": rise,
            "riser_dip_pp": riser_dip,
            "faller_peak": (years[peak_at], peak),
            "faller_trough": (years[trough_at], trough),
            "drop_pp": drop,
            "recovery_pp": recovery,
            "clearly_ahead_from": changes[0],
            "end_gap_pp": up[-1] - down[-1],
            "longest_close_run_years": max(
                (run[0] for runs in clearance.values() for run in runs.values()), default=0
            ),
            "clearance": clearance,
        },
    )


def rubric_parts(form: str, task_id: str = "T1") -> dict[str, str]:
    """The rubric's three parts for one form's written item, in the words coders are given.

    Built from the same parameters the acceptance rule checks, so the sheet can never name a
    different pair of countries than the chart drew.
    """
    params = PARAMS[(form, task_id)]
    riser, faller = params["riser"], params["faller"]
    return {
        "a": f"{riser}'s coverage rose over the period",
        "b": f"{faller}'s coverage fell and then recovered",
        "c": f"{riser} overtook or passed {faller}, or the two ended close or level",
    }


def _rank(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    """T2: the country ranked `rank` among the bars.

    Acceptance: the key's bar is at least 5 points from the bars ranked just above and below it, so
    the three can be told apart by height without sorting.
    """
    rank = params["rank"]
    (year,) = task.years
    values = {entity: _required(task, entity, year, rows) for entity in task.entities}
    ordered = sorted(values, key=values.get, reverse=True)
    key = ordered[rank - 1]
    neighbours = {}
    if rank > 1:
        neighbours["above"] = ordered[rank - 2]
    if rank < len(ordered):
        neighbours["below"] = ordered[rank]
    gaps = {side: abs(values[other] - values[key]) for side, other in neighbours.items()}
    for side, gap in gaps.items():
        if gap < MIN_SEPARATION_PP:
            raise KeyDerivationError(
                f"{task.form}-{task.task_id}: {key} ({values[key]:g}) is {gap:g} pts from "
                f"{neighbours[side]}, the bar ranked {side} it; bars that close cannot be ranked "
                "by eye"
            )
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        key,
        f"country with the {_ordinal(rank)}-highest coverage in {year}",
        {
            "year": year,
            "values": values,
            "neighbours": neighbours,
            "gaps_pp": gaps,
        },
    )


def _improved(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    """T3: the dot furthest above the no-change diagonal.

    Acceptance: its improvement beats every other dot's by at least 5 points, and no two dots sit
    within 4 points of each other, where one would hide the other.
    """
    first, last = task.years
    points = {
        entity: (_required(task, entity, first, rows), _required(task, entity, last, rows))
        for entity in task.entities
    }
    improvement = {entity: late - early for entity, (early, late) in points.items()}
    ranked = sorted(improvement, key=improvement.get, reverse=True)
    key, runner_up = ranked[0], ranked[1]
    margin = improvement[key] - improvement[runner_up]
    if margin < MIN_SEPARATION_PP:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {key} improved {improvement[key]:+g}, only {margin:g} "
            f"pts more than {runner_up}"
        )
    closest = min(
        (
            ((points[a][0] - points[b][0]) ** 2 + (points[a][1] - points[b][1]) ** 2) ** 0.5,
            a,
            b,
        )
        for a, b in combinations(task.entities, 2)
    )
    if closest[0] < MIN_DOT_DISTANCE_PP:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: the dots for {closest[1]} and {closest[2]} are "
            f"{closest[0]:.1f} pts apart; one hides the other"
        )
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        key,
        f"country whose coverage rose most from {first} to {last}",
        {
            "points": points,
            "improvement": improvement,
            "runner_up": runner_up,
            "margin_pp": margin,
            "closest_dots_pp": round(closest[0], 2),
        },
    )


def _cell(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    """T4: the row holding the heatmap's lowest cell.

    Acceptance: that cell is at least 10 points below the lowest cell of every other row. Colour is
    the only channel here, and the rule for colour is twice the rule for position.
    """
    minima = {}
    for entity in task.entities:
        cells = {year: _required(task, entity, year, rows) for year in task.years}
        year = min(cells, key=cells.get)
        minima[entity] = (cells[year], year)
    ranked = sorted(minima, key=lambda entity: minima[entity][0])
    key, runner_up = ranked[0], ranked[1]
    margin = minima[runner_up][0] - minima[key][0]
    if margin < MIN_COLOUR_SEPARATION_PP:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {key}'s lowest cell ({minima[key][0]:g}) is only "
            f"{margin:g} pts below {runner_up}'s; that close, the two colours cannot be told apart"
        )
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        key,
        "country whose row holds the lowest cell",
        {
            "row_minima": minima,
            "runner_up": runner_up,
            "margin_pp": margin,
        },
    )


def _threshold(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    """T5: how many coloured countries are below a threshold.

    Acceptance: every coloured country is at least 10 points from the threshold, so which side of
    it each one falls is a colour judgement a static reader can make against the key.
    """
    threshold = params["threshold"]
    (year,) = task.years
    values = {entity: _required(task, entity, year, rows) for entity in task.entities}
    closest = min(values, key=lambda entity: abs(values[entity] - threshold))
    distance = abs(values[closest] - threshold)
    if distance < MIN_COLOUR_SEPARATION_PP:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {closest} ({values[closest]:g}) is only {distance:g} "
            f"pts from {threshold}%; which side it falls is too fine a colour judgement"
        )
    below = sorted(entity for entity, value in values.items() if value < threshold)
    count = len(below)
    return DerivedKey(
        task.task_id,
        task.form,
        task.kind,
        # The options are 0-4 and "5 or more" (2026-09-25; "4 or more" before).
        str(count) if count < 5 else "5 or more",
        f"number of coloured countries strictly below {threshold}% in {year}",
        {
            "year": year,
            "threshold": threshold,
            "below": below,
            "closest": (closest, values[closest]),
            "closest_pp": distance,
            "values": values,
        },
    )


def _crossing(task: Task, params: dict[str, Any], rows: tuple[Row, ...]) -> DerivedKey:
    """T6: the band in which one line first rises above another.

    The key is the band containing the first year the overtaker is strictly above, having not been
    above the year before. Acceptance:
    - one crossing only: the overtaker trails in every year before it and leads in every year
      after, so "when did that first happen" has one true answer;
    - the lines part by at least 5 points somewhere on each side, so it reads as a crossing, not a
      touch;
    - "strictly above" and "no longer below" fall in the same band, so a tie before the crossing
      cannot move the key;
    - the point where the lines meet on the chart sits at least a year inside the key band, so a
      reading one year off still lands in it;
    - no other line on the chart passes within 5 points of that point, where it would be taken for
      one of the two.
    """
    overtaker, overtaken = params["overtaker"], params["overtaken"]
    for entity in (overtaker, overtaken):
        if entity not in task.entities:
            raise KeyDerivationError(f"{task.form}-{task.task_id}: {entity} is not on the chart")
    ahead = _reported(overtaker, task.vaccine, rows)
    behind = _reported(overtaken, task.vaccine, rows)
    # Only years both lines report: elsewhere one of them is not drawn, so nothing crosses there.
    differences = {year: ahead[year] - behind[year] for year in sorted(set(ahead) & set(behind))}
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

    led_before = [year for year in ordered if year < strictly_above and differences[year] > 0]
    if led_before:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {overtaker} is already above {overtaken} in "
            f"{led_before}; the item has more than one crossing"
        )
    back_below = [year for year in ordered if year > strictly_above and differences[year] <= 0]
    if back_below:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: {overtaker} falls back to or below {overtaken} in "
            f"{back_below}; the item has more than one crossing"
        )

    trailed_by = max(-differences[year] for year in ordered if year < strictly_above)
    led_by = max(differences[year] for year in ordered if year >= strictly_above)
    for side, gap in (("behind before", trailed_by), ("ahead after", led_by)):
        if gap < MIN_SEPARATION_PP:
            raise KeyDerivationError(
                f"{task.form}-{task.task_id}: {overtaker} is never more than {gap:g} pts {side} "
                "the crossing; the lines touch rather than cross"
            )

    correct = band_for(strictly_above)
    if band_for(not_below) != correct:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: the crossing is {strictly_above} by 'strictly above' "
            f"but {not_below} by 'no longer below', and those fall in different bands"
        )

    # What a participant sees is where the two lines meet, not the first year of a rule. That point
    # must sit far enough inside the key band that a reading one year off still lands in it.
    previous = ordered[ordered.index(strictly_above) - 1]
    before, after = differences[previous], differences[strictly_above]
    fraction = (0 - before) / (after - before)
    intersection = previous + fraction * (strictly_above - previous)
    start, end = _parse_band(correct)
    inset = min(intersection - (start - 0.5), (end + 0.5) - intersection)
    if inset < MIN_BAND_INSET_YEARS:
        raise KeyDerivationError(
            f"{task.form}-{task.task_id}: the lines meet at {intersection:.2f}, only {inset:.2f} "
            f"years inside {correct}; a reading one year off lands in another band"
        )

    meeting = ahead[previous] + fraction * (ahead[strictly_above] - ahead[previous])
    clearance: dict[str, float] = {}
    for other in task.entities:
        if other in (overtaker, overtaken):
            continue
        values = _reported(other, task.vaccine, rows)
        if previous not in values or strictly_above not in values:
            continue  # not drawn through the crossing
        at_meeting = values[previous] + fraction * (values[strictly_above] - values[previous])
        clearance[other] = abs(at_meeting - meeting)
        if clearance[other] < MIN_SEPARATION_PP:
            raise KeyDerivationError(
                f"{task.form}-{task.task_id}: {other}'s line passes {clearance[other]:.1f} pts "
                f"from where {overtaker} and {overtaken} meet; it would be taken for one of them"
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
            "trailed_by_pp": trailed_by,
            "led_by_pp": led_by,
            "meeting_pp": round(meeting, 2),
            "other_lines_clearance_pp": {k: round(v, 2) for k, v in clearance.items()},
            "differences": differences,
            "adjacent_bands": sorted(adjacent_bands(strictly_above)),
        },
    )


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(n, f"{n}th")


_RULES = {
    "describe": _describe,
    "rank": _rank,
    "improved": _improved,
    "cell": _cell,
    "threshold": _threshold,
    "crossing": _crossing,
}


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
    if tasks.is_written(task):
        return key  # scored by rubric; there is no option to check the key against
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


def is_correct(
    form: str,
    task_id: str,
    answer: Any,
    keys: dict | None = None,
    verdict: bool | None = None,
) -> bool | None:
    """Strict scoring, the primary. None for the unscored practice item or an unknown item.

    The written item (T1) is scored by rubric: `verdict` is the coders' settled verdict for this
    answer, and None while it is uncoded, which returns None -- never a guess. A skipped written
    answer is incorrect without coding, like any skip.
    """
    keys = keys if keys is not None else key_table()
    key = keys.get((form, task_id))
    if key is None:
        return None
    if key.correct == RUBRIC:
        if answer is None or not str(answer).strip():
            return False
        return verdict
    return answer == key.correct


def is_correct_adjacent(
    form: str, task_id: str, answer: Any, keys: dict | None = None
) -> bool | None:
    """Secondary scoring: adjacent-band credit for the crossing item (T6). None for any other item.

    Pre-registered in study-design.md section 7, and reported beside the strict score, never in its
    place.
    """
    keys = keys if keys is not None else key_table()
    key = keys.get((form, task_id))
    if key is None or key.kind != "crossing":
        return None
    return answer in set(key.evidence["adjacent_bands"])
