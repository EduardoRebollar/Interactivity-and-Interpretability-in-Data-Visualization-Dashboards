# Study design

Source of truth for the protocol: research questions, conditions, tasks, measures, and scoring.
`docs/visual-spec.md` is the source of truth for what the charts look like. Change this document
before changing `src/tasks.py` or `src/flow.py`.

Status: **draft, 2026-09-15; revised 2026-09-21 to match the IRB submission; task set finalized
2026-09-22, then replaced 2026-09-23 by a redesigned task bank on five chart types, with a
crossing item added the same day; the largest-rise item dropped 2026-09-25 (§4); redesigned
2026-09-25 from the design handoff (`docs/design-handoff/`, `docs/study-redesign.md`): six options
per item, controls on every chart, a new survey, and About you, which moves to the end; built and
verified in headless Chrome 2026-09-26; restyled 2026-10-11 from the chart handoff
(`docs/chart-handoff/`), with T5's maps redrawn, T6 given six more lines, and T2 and T4 moved to
MCV1 (§4); line charts drawn from 1985 on 2026-10-12, every line item still asking about 2000
onward (§4).** The consent text in §9 is the form submitted to Occidental's HSRRC and must not be shown to a participant until approved.

**The IRB approval request form outranks this document** (`irb/`, local only — see CLAUDE.md). Where
the two disagree, this document is changed to match, or the disagreement is listed in §10 so the IRB
paperwork can be amended before submission.

---

## 1. Research questions

**RQ1 (accuracy).** Does interactivity improve the accuracy of interpretations of vaccination-coverage
data — a time series, shown on line, bar, scatter, heatmap and map charts — relative to a visually
identical static chart?

**RQ2 (reasoning depth).** Does interactivity change *how* people reason — the evidence they cite and
the number of series they bring to bear — independently of whether they answer correctly?

**RQ3 (cognitive load).** Does interactivity primarily reduce perceived mental effort rather than
improving accuracy?

RQ3 matters because a null result on RQ1 with a reliable effect on RQ3 is still a finding: it would
suggest interactivity makes interpretation feel easier without making it better.

**Out of scope.** Cross-platform generalisation. The second platform was cut (see CLAUDE.md);
write-ups must not claim platform independence. So is any claim about a chart type as such: each type
carries one item per form, the line chart two (§4, §7).

## 2. Design

Within-subjects, 2 (condition: static / interactive) × 2 (form: A / B), fully counterbalanced.
Target n ≥ 25.

Each participant completes **6 scored tasks per condition, 12 in total**, plus one unscored practice
task. Five are multiple choice; one, T1, is a written description (2026-09-27). All six make up the
RQ1 accuracy score (§7). Expected duration about 40 minutes (the consent
form and request form 5B), capped at one hour (IRB form item 10). In person, on campus, on the
participant's own computer (request form 5B).

### Conditions

Identical in every visual respect. The only difference is the Plotly render config
(`figures.graph_config`) and the controls rendered under the chart (`docs/visual-spec.md` §7):

| | Static | Interactive |
|---|---|---|
| Hover tooltips | none | every chart |
| Country chips | none | every chart: show or hide each country drawn |
| Line charts | image | Years (a range slider), Show all, click a line to focus on it, zoom and pan |
| Bar chart | image | Sort: A–Z, High → low, Low → high |
| Heatmap | image | Sort rows: A–Z, Lowest cell first, Highest cell first; the key's colours highlight cells |
| Scatter | image | the key's colours: a click highlights the dots in that band |
| Map | image | the key's colours: a click highlights the countries in that band |
| Every chart | — | Reset view: undo filtering, sorting, focusing, zooming and a highlight |

The controls and a one-line hint sit under the chart, so the chart is in the same place in both
conditions.

**Static participants cannot read exact values.** They estimate against gridlines or a colour key.
No task may therefore ask for a specific number — such an item would measure whether hover exists,
not interpretation. Every item below asks for a year, a country or a count, and every key survives
the reading errors of a participant without hover (§4).

### Counterbalancing

Assignment comes from a database sequence, not a random draw, so the cells fill evenly and two
simultaneous participants can never collide (`db.register_participant`, which applies the rule
in `db.assignment_for`):

| seq % 4 | Condition 1 | Form | Condition 2 | Form |
|---|---|---|---|---|
| 1 | static | A | interactive | B |
| 2 | interactive | A | static | B |
| 3 | static | B | interactive | A |
| 0 | interactive | B | static | A |

Every participant sees both conditions and both forms, never the same form twice.

**A returning ID does not consume a sequence number (fixed 2026-09-16).** Registration looks the ID
up before inserting. It used to insert with `ON CONFLICT DO NOTHING`, and Postgres draws the next
sequence value *before* detecting the conflict — so every repeat registration of a known ID, a
double-click on Continue included, silently skipped the next participant into a different cell. The
sequence can still have gaps (two people entering the *same new* ID at the same instant, a rolled-back
insert, `scripts/verify_deployment.py` runs), so check the realised cell counts before analysis rather
than assuming they are equal.

### Why parallel forms

If both conditions used the same tasks, a participant would answer each question a second time
already knowing the answer. Counterbalancing the *order* spreads that practice effect evenly but does
not remove it: second-condition accuracy would be inflated for everyone, partially masking or
mimicking an effect of interactivity. Forms A and B are isomorphic — same item types, on the same
chart types, in the same order, with matched margins — over different data.

## 3. The entity set

Each task shows **the same fixed set of entities in both conditions.** No control reaches an entity
the static condition cannot see: the chips hide entities within the set, the sorts
reorder them, and a highlight from the key fades marks within it.

This is deliberate. If interactive participants could pull in entities that static participants could
not, interactivity would be changing *what data is available* as well as *how it is worked with*, and
no observed difference could be attributed to interactivity alone.

At most 8 lines plus the dashed World reference, or 21 scatter dots (16 from 2026-10-11, 21 from
2026-10-13), per `docs/visual-spec.md` §6. The bar chart, the scatter, the heatmap and the map are not limited by the
line palette: bars have colours of their own, dots are coloured by their change, and rows and
countries take the blue bands (`docs/visual-spec.md` §4).

## 4. Task set

**Replaced 2026-09-23.** The task bank of 2026-09-22 (a reference count, two trends, two crossings
and a gap item, all on line charts) was replaced by a bank Eduardo specified on 2026-09-23
(`task-bank-spec.md`, supplied with the request and not kept in this repository; every item it
specified is recorded below, as kept or as changed). Every item used DTP3 until 2026-10-11, when T2
and T4 moved to MCV1 (below); the others still do. Every value was verified against
`data/deploy/coverage.csv`. The spec's own values were right: they also match the Our World in Data
export it cites, which agrees with this project's source for DTP3, 2000–2024, value for value.

**Renumbered 2026-09-25.** The largest-rise item, then T2, was dropped, and the items after it moved
up one: the old T3–T7 are T2–T6. Numbers below are the current ones, including where they describe
the spec's own items.

### The design principle

Each item isolates **one interactive affordance** and pairs it with a chart type where the static
read is costly and that affordance lowers the cost:

| Item | Chart | Affordance | The static cost it lowers |
|---|---|---|---|
| T1 | line, 8 countries | setting lines aside: a click on a line fades the rest, the chips hide them; and, since 2026-10-12, four controls it does not need (the overload) | tracing two lines through a tangle of crossings |
| T2 | bar | sorting the bars | ranking bars that stand in no order |
| T3 | scatter | hovering a dot; hiding dots with the chips; highlighting a change band from the key | judging, by eye, which of the dots sharing the darkest change colour sits furthest above the diagonal |
| T4 | heatmap | hovering a cell; sorting rows by lowest (A) or highest (B) cell; highlighting a band from the key | telling dark (A) or light (B) bands apart against the key |
| T5 | map | highlighting bands from the key: a click on a colour | sorting every country's colour against the key |
| T6 | line, 8 countries | hiding the six other lines with the chips; hovering both where they meet | following two lines through six others that cross them, then placing, by eye, the year they cross |

**Redesign, 2026-09-25.** Every chart now has country chips and Reset view. The heatmap gained a
row sort, and the map's range slider gave way to a typed threshold. The heatmap's row sort answers
T4 in one click, as the bar sort answers T2: Lowest cell first in A and, since the first pilot
session (2026-10-12, T4 below), Highest cell first in B. Like the bar sort, it lowers the static
cost rather than making the item answerable, because T4's key already clears the acceptance rule.

Chart type here is **variety** — evidence that an effect holds across formats — not a per-type
claim. Each type carries one item per form, the line chart two, so per-chart-type differences
are reported descriptively and never tested (§7).

T2–T5 each read one set of values: a ranking, an extreme, a count. T6 was added the same day, at
Eduardo's request, as a **relational** item: its answer is a relation between two series, when one
overtakes the other. T1 (2026-09-27) is the one **interpretive** item: the participant describes two
series over 2000–2024 and how they compare, in their own words. (Until 2026-10-12, when the line
charts began drawing from 1985, that was the whole period on the chart.)

### Item acceptance rule (2026-09-22, extended 2026-09-23)

Section 2 forbids items that ask for an exact value, because static participants cannot read one.
An item that asks for no number can still turn on one: an answer that flips when a year is read one
off, or when two values 2 points apart must be told apart, measures whether hover exists just as
surely. So every key must survive the reading errors a participant without hover makes.

**The spec asked for the opposite on three chart types.** Its bars were 99, 98, 97 and 96, its
darkest cells 26 and 29, and several of its map countries sat within 3 points of the 50% line. Only
the interactive condition could have answered those items. Eduardo chose, on 2026-09-23, to keep
this rule and re-tune those items so every call clears it. In the static condition the affordance
then saves time and effort, which RQ3 measures, rather than making the question answerable at all.
Accuracy near chance in one condition would drive the RQ1 comparison for reasons fixed before
anyone took part.

On the line and bar charts one point is 4 px, so 5 points is 20 px, the smallest gap that reads
unaided. Colour is judged less precisely than position, between patches that are not side by side,
so the floor for colour is doubled. On the continuous scale the rule was set on, one point moved
lightness by 0.73–0.86 L*, so 10 points was at least 7.3 L*. **Since 2026-10-11 the heatmap and the
map draw bands** (`docs/visual-spec.md` §4): a value takes one flat colour, and every band boundary
moves lightness by at least 8.3 L*. The 10-point floor stands, and T4 and T5 now also require that
the key be read across a band boundary, which 10 points alone does not guarantee inside the
heatmap's 0–20 band.

| Item | The key must survive... |
|---|---|
| T1 two trends | Each shape the rubric names is large: the riser gains at least **25 points** and never drops more than **12** below a previous peak; the other line drops at least **25 points** from a peak and recovers at least **15** from its trough. The two cross **once**, by the T6 rule's 5-point test. No other line runs within **5 points** of a named line for **5 or more consecutive years**; for the falling line, counted from its last peak before the trough. |
| T2 rank | The key bar is at least **5 points** from the bars ranked just above and just below it. |
| T3 most improved | The key's improvement beats every other dot's by at least **5 points**, and no two dots sit within **4 points** of each other (closer, and one dot hides the other, or their names collide). **The key shares its change colour with at least one other dot** (2026-10-11), so the colour alone never names it. |
| T4 extreme cell | The lowest cell is at least **10 points** below the lowest cell of every other row, and **in a darker band** than any of them (2026-10-11). For the highest cell (B, 2026-10-12), the mirror: at least **10 points** above every other row's highest, and **in a lighter band**. |
| T5 count | Every coloured country is at least **10 points** from the threshold. The threshold, 50, is a band boundary, so the countries below it sit in the two darkest bands and those above in 60–70 or lighter: the 50–60 band stays empty. |
| T6 crossing | The point where the two lines **meet on the chart** sits at least **1 year inside** its answer band, a band spanning start − 0.5 to end + 0.5. One crossing only: the overtaker trails in every year before it and leads in every year after, by at least **5 points** somewhere on each side. The first year strictly above and the first year no longer below fall in the same band. No other line drawn within **5 points** of where the two meet, and none runs within **5 points** of either named line for **5 or more consecutive years** (T1's clause, added 2026-10-11 with T6's extra lines). |

**Drawn from 1985, asked from 2000 (2026-10-12).** Line charts show 1985–2024; T1 and T6 ask
about 2000 onward. The rule splits on that line:
- **What the answer turns on is judged on the years asked, 2000–2024:** T1's three shapes and its
  one crossing, and T6's one crossing and its key band. Both T6 pairs also cross before 2000 (T6
  below); the question's "after 2000" sets those aside, and so does the rule.
- **What keeps a line traceable is judged on every year drawn, 1985–2024:** no other line within
  5 points of a named one for 5 or more consecutive years (for T1's falling line, still from its
  last peak before the trough), and none within 5 points of where T6's pair meet. A line followed
  by mistake in 1995 is still followed by mistake.
- **A named line must report every year asked.** Before 2000 it may start late: Ukraine, A-T1's
  falling line, reports from 1992. The gap caption names only years missing from 2000 on, so it
  does not name that one (`docs/visual-spec.md` §3).

Drawn from 1985, A-T1 failed the second clause (Nigeria within 5 points of India, 1985–1989) and
so did B-T6 (Madagascar beside Pakistan for 9 years, 1995–2003, and beside Mozambique 1986–1990;
Cameroon beside Pakistan for 7, 1996–2002). Eduardo kept the clause over every drawn year, and
those lines were replaced (T1, T6 below).

A bar, dot, cell or country with no reported value is refused outright: the chart would have nothing
to show exactly where the question looks. A crossing is judged only on years both lines report. An
item that fails any part is refused by `analysis/keys.py` with `KeyDerivationError`, so a fragile
item fails the test suite exactly as a wrong key does, including after a data refresh.
`tests/test_scoring.py` also runs each spec item that was changed on the real data and checks that
it is still refused.

### T1 — Two trends (line, isolation)

*Look at {country} and {country}'s coverage. Describe how their coverage changed between 2000 and
2024, and how their trends were similar or different.* (Until 2026-10-12, "Look at the lines for
{country} and {country}. … how the two countries' trends were similar or different.")

Answered in writing, in one text box, with no separate justification: the description is the
reasoning (§5).

| | Form A | Form B |
|---|---|---|
| Named countries | India and Ukraine | Brazil and Uganda |
| The riser | India: 58% → 94%; never more than 6 below a previous peak | Uganda: 52% → 91%; never more than 5 below |
| The line that falls and recovers | Ukraine: 99% → **19%** (2016) → 88%; drop 80, recovery 69 | Brazil: 99% → **68%** (2021) → 91%; drop 31, recovery 23 |
| Crossing (5-point test) | once: India above from 2009, 5 points clear from 2010 | once: Uganda above from 2016, 5 points clear from 2017 |
| Gap in 2024 | India 6 points above | level |
| Longest run of another line within 5 points of a named one, as the rule counts it, 1985–2024 | 4 years: Indonesia and India, 2014–2017; Brazil and Ukraine, 2004–2007; Pakistan and India, 1999–2002 | 4 years: Indonesia and Uganda, 2009–2012; and, beside Uganda before 2000, Nigeria (1985–1988), Nepal (1989–1992) and Ethiopia (1994–1997) |
| Other lines | Brazil, China, Ethiopia, Gabon, Indonesia, Pakistan (no World line). Gabon replaced Nigeria on 2026-10-12 (below) | China, Ethiopia, Indonesia, Nepal, Nigeria, Pakistan (no World line) |
| Crossings of the two named lines with the other six, 2000–2024 | 30 | 26 |
| Crossings the years 1985–2000 add | 10 | 16 |
| Years a line is not reported, 1985–2024 | Ukraine, 1985–1991 | none |

Both forms tell one story: a country rising steadily from far below overtakes one that starts near
the top, as that one falls, and the fallen country recovers to about where the riser ends. The
countries are named alphabetically, so the riser is named first in A and second in B.

**Rubric.** A description is **correct** if it states all three of the following and contradicts
none of them:

| Part | Form A | Form B |
|---|---|---|
| (a) the riser rose | India's coverage rose over the period | Uganda's coverage rose over the period |
| (b) the other fell and recovered | Ukraine's coverage fell and then recovered | Brazil's coverage fell and then recovered |
| (c) how the two relate | India overtook or passed Ukraine, **or** they ended close | Uganda overtook or passed Brazil, **or** they ended close or level |

Years and values are neither required nor penalised unless they contradict a part: a static reader
cannot read them exactly (§2). "Ukraine dropped to about 20% around 2015 and came back" states (b);
"Ukraine's coverage declined" alone does not, and "Ukraine stayed high" contradicts it. Scoring is
by two coders, blind to condition (§7). Since the chart starts in 1985 (2026-10-12), a description
may also cover 1985–1999. The parts are about 2000–2024, so what it says about the earlier years is
neither required nor penalised, unless it is plainly offered as the 2000–2024 trend and contradicts
a part.

The difficulty is finding and following two lines through the tangle, then describing them. A
click on a line fades the rest, and the chips hide them; either cuts through it. Since 2026-10-12
the Years slider can also set aside the fifteen years before the question's.

> **Drawn from 1985, 2026-10-12** (Eduardo). Every line chart now starts in 1985 (`docs/visual-
> spec.md` §1), so the Years slider has years to set aside. The question still asks about 2000 to
> 2024, and the rubric is unchanged. Before 2000:
> - India rises from 18% (1985) to 70% (1990) and falls back to 56% (1992). That dip is 14 points,
>   over the riser's 12, but it falls before the years asked, so the rule does not count it.
> - Ukraine reports from 1992 only, so its line starts there. There is no caption: on a line
>   chart the caption names only years missing from 2000 on (`docs/visual-spec.md` §3; Eduardo
>   had A-T1's removed the same day).
> - **Nigeria left A-T1** for running within 5 points of India for five years, 1985–1989. **Gabon
>   took its place**, found by search. It is African, so A-T1's Regions control keeps two African
>   countries. It crosses the named pair four times between 2000 and 2024, as Nigeria did: it
>   passes India in 2007 and Ukraine in 2009, then India passes it in 2010 and Ukraine in 2019. It
>   ends at 61%, 12 points from the nearest tag. It takes Nigeria's colour, by the rule that gives
>   a country the first colour its chart does not use (`docs/visual-spec.md` §4). Other countries
>   that passed: Guinea, Benin and Madagascar (Madagascar running beside India for exactly 4
>   years).
> - B-T1 passes as it stands.

> **Overloaded with controls, 2026-10-12** (pilot session 1). The supervisor asked for at least one
> case where interactivity might be too much: a chart carrying more controls than it needs.
> Otherwise the study tests only cases chosen for interactivity to help. Eduardo chose to overload T1,
> in both forms, rather than add an item. In the interactive condition T1 carries, besides every line
> chart's controls, four of its own (`docs/visual-spec.md` §7.7):
> - **Coverage**, zooming the y axis;
> - **Order**, reordering the chips by name or by coverage in 2000 or 2024;
> - **Regions**, showing or hiding a region's lines at once;
> - **Show**, turning off the points or the name tags.
>
> None answers the question, and none ranks the countries by change, which would. They are
> **unannounced**: neither the instructions nor the hint row name them (Eduardo), so whether they
> are found is part of what T1 shows. T1 stays in RQ1, and is also reported on its own (§7). On T1
> the design cannot separate "interactivity helps" from "too many controls hurt", since there is no
> T1 with the standard controls alone. The write-up says so.

> **Replaced 2026-09-27.** T1 asked for the year of one line's lowest point (Ukraine in A, Myanmar in
> B). Every other item asked for a value or a relation, and none asked for an interpretation of a
> time series, which the study's title promises. Eduardo chose to replace T1 with a written
> comparison of two lines, kept in RQ1 and scored by rubric, over adding a seventh item or leaving
> the bank as it was. The 2026-09-27 data search:
> - Ukraine's 80-point collapse has no match in scope. Myanmar's 2021 dip lasts one year; Brazil
>   and Mozambique fall about 30 points. The forms match the story's structure, not its size, and
>   the pilot checks whether that is enough (§10).
> - India cannot stay on B's chart: it runs within 5 points of Uganda for 19 of 25 years. B's chart
>   swaps India and Myanmar for Uganda and Nepal, which gives the tangle nearest A's.
> - A's chart is unchanged. Ukraine and Brazil sit together near 99% for eight years, 2000–2007,
>   but only 2004–2007 falls after Ukraine's last peak, and all eight precede anything the rubric
>   turns on. So the rule counts four.

### T2 — Ranked bar (bar, sort)

*The bars show coverage in 2017. Which country had the {third / sixth}-highest coverage?* Form A
asks for the third, form B since 2026-10-12 for the sixth (below). MCV1 since 2026-10-11 (below).

| | Form A | Form B |
|---|---|---|
| Year | 2017 | 2017 |
| Asks for | third-highest | sixth-highest |
| Bars | China 99, Vietnam 97, **India 90**, Kenya 84, Pakistan 76, Mali 70, Afghanistan 64, Ethiopia 59, Nigeria 54, Guinea 48 | Egypt 94, Colombia 93, United States 91, Indonesia 90, Algeria 88, **Mozambique 83**, Mali 70, Cameroon 67, Ethiopia 59, Nigeria 54 |
| Gap to the bar above / below | 7 / 6 | 5 / 13 |
| Options | China, Ethiopia, Guinea, India, Kenya, Vietnam | Algeria, Cameroon, Egypt, Indonesia, Mali, Mozambique |
| Options' ranks | 1, 2, 3, 4, 8, 10 | 1, 4, 5, 6, 7, 8 |
| Key | **India** | **Mozambique** |

The bars stand in alphabetical order, so the ranked bars are not side by side. Sorting lines them
up. Ten bars per form. Form A's options are ranks 1, 2, 3, 4, 8 and 10, every one at least 2
points from its neighbours. Form B's include both of the key's neighbours (ranks 5 and 7).

> **B-T2 asks for the sixth-highest bar, 2026-10-12** (Eduardo), and reads 2017, as A does. Same
> ten bars. In 2021, B's year until then, the fifth and sixth bars tie (Indonesia and Mali, 72),
> so no sixth-highest can be named. In 2017 the key, Mozambique, sits **5 points** below the fifth
> bar (Algeria 88), on the floor, and 13 above the seventh (Mali 70). The options were re-chosen to
> offer both neighbours and to put the key sixth, which keeps every position at or under a third of
> the keys (§5). **The forms no longer ask the same question:** counting to six through bars packed
> within 6 points of each other (94 to 88) is a harder static read than A's third, and B's margin
> above the key is A's less 2. A pilot check (§10).

> **Moved to MCV1, 2026-10-11** (Eduardo), so the bank uses more than one vaccine. On DTP3 the
> bars were A 2017: China 99, Vietnam 94, India 89, Brazil 83, Kenya 81, Mali 77, Pakistan 75,
> Ethiopia 65, Afghanistan 64, Nigeria 55; B 2024: Egypt 97, United States 94, Colombia 89,
> Cambodia 83, Mali 82, Indonesia 78, Cameroon 77, Ethiopia 73, Mozambique 70, Nigeria 67, each key
> 5 / 6 points from its neighbours. Neither chart passes on MCV1 as it stood (A's India is 3 points
> above Brazil; B's Colombia 1 point below the United States in 2024), and B passes in no year
> without a change of bars. Found by search over every year and every one-bar swap, with the options
> re-chosen at the same ranks and the key kept in its place: A keeps 2017 and swaps Brazil for
> Guinea; B moves to 2021 and swaps Cambodia for Algeria. Guinea takes Brazil's colour and Algeria
> Cambodia's, so each chart's set of colours is the one already measured (`docs/visual-spec.md`
> §4). The keys stay India and Colombia. (B-T2 moved again on 2026-10-12, above.)

> **Three bars added to each form, 2026-10-11** (Eduardo), so a reader without the sort has more
> bars to rank. A gains Kenya (81), Mali (77) and Afghanistan (64); B gains Mali (82), Cameroon (77)
> and Mozambique (70). Every new bar sits at least 5 points below the key, so the key, its margins,
> the options and the key's place among them are unchanged; the options moved from ranks 1, 2, 3,
> 4, 6 and 7 to 1, 2, 3, 4, 8 and 10, alike in both forms. In each form the fifth bar is a new one,
> 1–2 points under the fourth. The Democratic Republic of Congo (A 71, B 65) and the Central
> African Republic were left out: ten bars give each name about 94 px of axis, and theirs would
> collide.

> **Re-tuned from the spec.** The spec's A-T2 (2015) had China 99, Bangladesh 98, Vietnam 97 and
> Brazil 96, and its B-T2 (2019) Egypt 95 against Colombia 94. Both keys were 1 point from a
> neighbour, which no one can rank by bar height. The new sets were found by search over the bank's
> countries, for the tightest gaps that clear 5 points.

### T3 — Most improved (scatter, hover)

*Each country is placed by its coverage in 2000 (across) and in 2024 (up). The dashed diagonal means
no change. Which country improved the most?* Same wording in both forms. (Until 2026-10-12, "Each
dot is an {African / Asian} country, placed by … improved the most — the dot furthest above the
diagonal?")

| | Form A | Form B |
|---|---|---|
| Dots, 2000 → 2024 | Burkina Faso 45 → 91, Chad 38 → 68, Ethiopia 30 → 73, Mali 43 → 82, **Niger 34 → 86**, Nigeria 29 → 67 | Bangladesh 82 → 97, Cambodia 59 → 83, **India 58 → 94**, Indonesia 75 → 78, Nepal 74 → 97, Pakistan 59 → 87 |
| Added 2026-10-11 | Benin 78 → 63, Cameroon 62 → 77, Central African Republic 37 → 42, Egypt 98 → 97, Kenya 82 → 91, Libya 94 → 86, Madagascar 57 → 60, Mozambique 70 → 70, Sudan 62 → 39, Tanzania 79 → 83 | Iraq 80 → 90, Jordan 91 → 96, Kyrgyzstan 99 → 85, Laos 51 → 67, Lebanon 83 → 49, Oman 99 → 99, Philippines 78 → 71, Syria 86 → 73, Thailand 97 → 92, Yemen 74 → 42 |
| Added 2026-10-13 | Algeria 86 → 92, Eritrea 81 → 95, Guinea 46 → 63, Namibia 79 → 74, South Africa 73 → 74 | Benin 78 → 63, Central African Republic 37 → 42, Cote d'Ivoire 65 → 77, Gabon 45 → 61, Sudan 62 → 39 |
| Improvement, key vs runner-up | +52 vs +46 (Burkina Faso): 6 | +36 vs +28 (Pakistan): 8 |
| Best added dot | +17 (Guinea, 2026-10-13), 35 below the key | +16 (Laos; Gabon, 2026-10-13), 20 below the key |
| Dots below the diagonal | 5 (4 until 2026-10-13) | 8 (6 until 2026-10-13) |
| Closest two dots | 4.1 points (Algeria and Eritrea, each with Kenya; 6.1, Ethiopia and Nigeria, until 2026-10-13) | 4.0 points (Cambodia, Pakistan) |
| Pairs of dots within 8 points | 6 (1 until 2026-10-13) | 7 |
| Options | Burkina Faso, Chad, Ethiopia, Mali, Niger, Nigeria | Bangladesh, Cambodia, India, Indonesia, Nepal, Pakistan |
| Key's change colour, shared with | more than +40: Burkina Faso (+46), Ethiopia (+43) | +20 to +40: Pakistan (+28), Cambodia (+24), Nepal (+23) |
| Key | **Niger** | **India** |

Every dot is named beside it and coloured by its change (`docs/visual-spec.md` §1, §4). The static
cost is choosing among the dots that share the darkest change colour: judging, by eye, which sits
furthest above the diagonal, 6 points ahead in A and 8 in B. Hover gives each dot's two values
exactly.

> **Five dots added to each form, 2026-10-13** (Eduardo), so that in the interactive condition the
> chips fill three rows of seven (`docs/visual-spec.md` §7.3). Sixteen ran 6/5/5, with up to
> 99 px between chips. Twenty-one dots per form. As on 2026-10-11, every added dot improved at
> least 20 points less than the key. The key, the runner-up, the margin and the options are
> unchanged, and the key shares its colour with the same dots as before. The sets were chosen by
> search, all in scope, under three conditions:
> - the 4-point floor;
> - a name beside every dot that touches no other name or dot (`config.SCATTER_LABEL_SIDES`);
> - the 21 chips running seven to a row, each row on one line.
> - **A** adds five African countries, and no existing name moves. Its closest pair falls from 6.1
>   points to 4.1, and its pairs within 8 points rise from 1 to 6, against B's 7. The forms' density
>   now nearly matches (Matching the forms, below).
> - **B shares three of A's dots:** Benin, the Central African Republic and Sudan, placed exactly
>   as in A (the two T4 grids already share Mali and Pakistan). Asia's eligible countries were all
>   used on 2026-10-11. No in-scope country that appears only on B placed its name clear of B's
>   crowded top-right corner. B's additions sit in the open middle and lower left: no new pair
>   within 8 points, the nearest 8.0 (Benin, Philippines). Expanding the scope instead, with
>   Bolivia, Papua New Guinea, Panama and the like, was offered and not taken (Eduardo).
> - **The scatter names the Central African Republic "CAR"**, on its dot and its chip, as the map
>   does: at full size, "Central African Rep." would not fit a row of seven. It is not an option in
>   either form, and T6's line tag keeps the longer name.

> **Highlighting from the key, 2026-10-12** (pilot session 1). The pilot's participant wanted to
> click the key to filter. A click on the key's band now fades every dot outside it
> (`docs/visual-spec.md` §7.4). On the key's band that leaves 3 dots in A (more than +40) and 4 in
> B (+20 to +40). The acceptance rule makes the key share its colour, so the key narrows the
> choice and never names the answer.

> **Restyled 2026-10-11** (the chart handoff, Eduardo). Until then the dots were named only by a
> legend, matched by colour and shape, and that matching was the static cost hover lowered. The
> names remove it, and the change colours narrow the answer to three dots in A and four in B, never
> to one: the acceptance rule now requires the key to share its colour. T3 is likely easier without
> hover than it was; the pilot checks whether it sits at ceiling in both conditions (§10). The
> question, the dots, the key and the options are unchanged.

> **Ten dots added to each form, 2026-10-11** (Eduardo), so a reader without hover had more legend
> entries to match. The restyle the same day (above) removed the legend; the sixteen dots stay.
> Every added dot improved at least 20 points less than the key, in both forms, so the key, the
> runner-up, the margin, the closest pair and the options are all unchanged; the new dots add
> entries to match, not rivals for the answer. Form B could not reach 20 points
> otherwise: Asia's eligible countries improved by +16 at most. Within that rule the sets were
> chosen by search for the fewest close pairs, then the fewest countries outside the old scope.
> - **A** keeps every in-scope African country that fits (Kenya over Zambia, 3 points apart) and adds
>   Benin, Libya and Sudan. Uganda (+39) and Somalia (+37) fit the 4-point rule but not the 20.
> - **B** adds ten Asian countries, none from the old scope: Myanmar, the practice's country, is left
>   out, and Vietnam and China crowd the top-right corner. Armenia, Azerbaijan and Georgia were left
>   out because participants may not read them as Asian, and Georgia as the US state.
> - **Not matched:** B's chart is denser. It has 7 pairs of dots within 8 points of each other
>   against A's 1, and 6 dots below the diagonal against A's 4, because Asia's high-coverage
>   countries share the top-right corner. Both forms still clear the 4-point floor.

> **Changed from the spec.** A-T3 drops Angola (31 → 64) and DR Congo (30 → 65): their dots sat
> 1.4 points apart, and within 3 of Nigeria's, so one dot hid another. B-T3 drops Laos, so both forms
> show six dots, and keeps Afghanistan out as the spec warned: its +35 all but ties India's +36.
> Since 2026-09-25 both forms offer all six dots.

### T4 — Extreme cell (heatmap, hover and row sort)

*Rows are countries and columns are years. Which country contains the single {lowest / highest}
coverage?* Form A asks for the lowest, form B since 2026-10-12 for the highest (below). Columns:
2000, 2005, 2010, 2015, 2020, 2024. MCV1 since 2026-10-11 (below). (Until 2026-10-12, both forms:
"Rows are countries and columns are years. Darker cells mean lower coverage. Which country's row
contains the single lowest cell?" The stepped key above the grid still shows which colour is
which.)

| | Form A | Form B |
|---|---|---|
| Asks for | the lowest cell | the highest cell |
| Rows (12 since 2026-10-13, below) | Benin, Burkina Faso, Cambodia, Chad, Cote d'Ivoire, India, Indonesia, Iraq, Mali, Pakistan, South Africa, Syria | Afghanistan, Cameroon, Democratic Republic of Congo, Ethiopia, Laos, Madagascar, Mali, Nepal, Niger, Nigeria, Pakistan, Yemen |
| Key cell | **Chad, 2005: 27%** | **Nepal, 2024: 97%** |
| Next row's | Benin, lowest 44% (2024) | Pakistan, highest 86% (2024) |
| Margin | 17 | 11 |
| Bands | Chad's 2000 (28) and 2005 (27) are the only cells in 20–30; nothing lower. Next: Benin 2024 (44), in 40–50, two bands lighter | the key is the only cell in 90 and over. Next: Pakistan 2024 (86) and Niger 2015 (85), in 80–90 |
| Options | Benin, Burkina Faso, Chad, India, Mali, Pakistan | Cameroon, Laos, Mali, Nepal, Niger, Pakistan |
| Key | **Chad** | **Nepal** |

No number is written in a cell. Static participants match each cell's band against the stepped key;
hover gives the exact value. The row sort brings the key's row to the top: Lowest cell first in A,
and Highest cell first in B (since 2026-10-12, below). Since
2026-10-11 the cells are banded (`docs/visual-spec.md` §4): the key cell is the only one of its
colour in either grid, at least one band from the next. A's options are its six lowest rows, B's
its six highest.

> **Four more rows per form, 2026-10-13** (Eduardo), so a static reader has more cells to scan:
> twelve rows, not eight. Every added row sits beyond the six option rows, on the far side of the
> grid from the key, as T2's added bars and T3's added dots did. **The key, its margin, its band,
> the options and the key's place among them are unchanged.** No added row is on the other form's
> grid, so the forms still share only Mali and Pakistan. MCV1, every cell reported:
>
> | Form | Row | 2000 | 2005 | 2010 | 2015 | 2020 | 2024 | Its extreme cell |
> |---|---|---|---|---|---|---|---|---|
> | A | Cote d'Ivoire | 68 | 84 | 64 | 67 | 63 | 75 | lowest 63, 36 above Chad's 27 |
> | A | Iraq | 86 | 69 | 75 | 71 | 93 | 91 | lowest 69 |
> | A | South Africa | 72 | 64 | 72 | 86 | 84 | 76 | lowest 64 |
> | A | Syria | 84 | 81 | 82 | 64 | 70 | 81 | lowest 64 |
> | B | DR Congo | 26 | 61 | 66 | 65 | 62 | 55 | highest 66 |
> | B | Ethiopia | 28 | 40 | 64 | 56 | 57 | 72 | highest 72 |
> | B | Nigeria | 33 | 41 | 56 | 42 | 60 | 57 | highest 60 |
> | B | Yemen | 70 | 73 | 68 | 61 | 53 | 41 | highest 73, 24 below Nepal's 97 |
>
> In A the added rows' lowest cells sit 6 or more above Pakistan's 57, the sixth option row; in B
> their highest sit 5 or more below Mali's 78. Each was picked for a cell that dips (A) or rises (B)
> towards the middle bands, so no added row reads at a glance as all light or all dark. Two African
> and two Asian rows in A; B had one Asian candidate, Yemen, so three of its four are African. Not
> Myanmar, the practice's country. Rows are 31.17 px tall, not 46.75 (`docs/visual-spec.md` §1).
> The heatmap's chips are drawn a little smaller, so the twelve still run in two rows of six beside
> Sort rows (`docs/visual-spec.md` §7.3), and the interactive card keeps its height (§10).

> **Highlighting from the key, 2026-10-12** (pilot session 1). A click on a colour in the key fades
> every cell outside that band (`docs/visual-spec.md` §7.4). No other row has a cell in the key
> cell's band, so a click on it leaves only the key's row lit: Chad's 2000 and 2005 cells in A
> (20–30), Nepal's 2024 in B (90 and over).
> With the row sort, T4 has two one-click routes in each form. Whether it sits at ceiling in the
> interactive condition is a pilot check (§10).

> **B-T4 asks for the highest cell, 2026-10-12** (Eduardo). On B's grid as it stood, Nepal's 97 was
> 6 points above Myanmar's 91 and 7 above Uganda's 90, all three in the 90-and-over band, so the
> rule refused it. Laos (highest 78) and Cameroon (79), found by search, replace Myanmar and
> Uganda; neither is on A's grid, which still shares only Mali and Pakistan with B's. Myanmar,
> the practice's country, no longer appears on any scored chart. **The forms no longer ask the
> same question, and the row sort no longer helps both alike.** The sort orders rows by their
> lowest cell or by their average, lowest first, and has no order by highest cell. Nepal also has
> the grid's highest average (83), so the Average sort happens to put its row last, but a reader
> must know to look at the bottom; A's Lowest value sort puts the key on top. B's key is also one
> band from the next row (A's two), and the light bands may be harder to tell apart than the dark
> ones. Pilot checks (§10).

> **Highest cell first, 2026-10-12** (pilot session 1, Eduardo). In the pilot's interactive half,
> on B-T4, the row sort was unclear and of no help: it had no order by highest cell. Its options
> became A–Z, Lowest cell first and Highest cell first; Average went, since neither form's question
> turns on a row's average (`docs/visual-spec.md` §7.2). Each form's key row now comes to the top in
> one click, so the sort no longer helps A more than B. Whether T4 then sits at ceiling in the
> interactive condition is a pilot check (§10).

> **Moved to MCV1, 2026-10-11** (Eduardo), with T2. On DTP3, A's grid had the Central African
> Republic where Benin is (Chad 26 against the CAR's 37, margin 11), and B's key cell was 24 against
> Niger's 34. B's grid passed on MCV1 unchanged (B's question and grid changed on 2026-10-12,
> above). A's does not: the CAR's lowest cell (36) is 9
> points above Chad's (27). Benin, found by search over one-row swaps, keeps Chad the key and in its
> place among the options. **The forms are less evenly matched than on DTP3:** A's margin is 17
> and B's 10, and A's next row sits two bands lighter than its key where B's sits one. Niger in A
> would match B exactly (margin 10, one band), but it would move the key's place among the options
> and add a third row identical in both forms' grids, beside Mali and Pakistan. A pilot check (§10).

> **Re-tuned from the spec.** The spec's A-T4 lowest cell (Chad, 26) was 3 points from Nigeria's
> (29), and its B-T4 (Afghanistan, 24) 5 points from Nigeria's — enough on a position axis, not in
> colour. Nigeria (29), Ethiopia (30) and Angola (31) bottom out within 10 points of both keys, Niger
> (34) within 10 of Chad's and Somalia (33) within 10 of Afghanistan's, so they left the grids. Form
> B also traded India and Indonesia for rows form A does not show, so the two grids share only Mali
> and Pakistan. The spec's keys, Chad and Afghanistan, stayed.

### T5 — Countries below 50% (map, the key)

*The map colours {n} countries in Africa by their coverage in {year}. How many of those countries
had coverage below 50%?* (Until 2026-10-11, "in sub-Saharan Africa".)

| | Form A | Form B |
|---|---|---|
| Year | 2013 | 2007 |
| Countries coloured | 18: Benin, Burkina Faso, Cameroon, Central African Republic, Chad, Democratic Republic of Congo, Egypt, Kenya, Libya, Madagascar, Mali, Mozambique, Niger, Nigeria, Sudan, Tanzania, Uganda, Zambia | 18: Algeria, Botswana, Chad, Congo, Côte d'Ivoire, Eritrea, Gabon, Ghana, Guinea, Malawi, Mauritania, Morocco, Namibia, Senegal, Somalia, South Africa, Tunisia, Zimbabwe |
| Below 50% | Central African Republic 23, Chad 39, Nigeria 39 | Chad 29, Somalia 40 |
| Closest to the line | Chad and Nigeria, 11 points below; Mali, 14 above | Somalia, 10 points below; Guinea, 13 above |
| Left out | Somalia 44 and Ethiopia 59, within 10 points of 50% | every African country within 10 points of 50% in 2007 (Nigeria 42, Angola 43, CAR 48, Equatorial Guinea 48, Ethiopia 50, Niger 58); Togo, Sierra Leone and Liberia, the smallest of the countries that pass |
| Options | 0, 1, 2, 3, 4, 5 or more | same |
| Key | **3** | **2** |

Every other country is plain land, and the prompt states how many are coloured. Each coloured
country is named on the map (`docs/visual-spec.md` §1). The forms share one country, Chad.

> **The key replaces the highlight box, 2026-10-12** (pilot session 1, Eduardo). Until then the
> interactive map had a "Below [n] %" box; typing 50 left exactly the answer at full strength. The
> pilot's participant found it "almost cheating" and "biased": the control echoed the question's
> own words. In its place, a click on a colour in the key highlights the countries in that band
> (`docs/visual-spec.md` §7.4). The key names no threshold: 50 is one of its six boundaries, and
> the countries below it fill the two darkest bands (the acceptance rule above), so a reader must
> work out which bands to choose. Two clicks then leave the answer at full strength. The pilot
> checks whether T5 still sits at ceiling in the interactive condition (§10).

> **Redrawn 2026-10-11 from the chart handoff** (Eduardo). The handoff's Form A map colours all 20
> African countries then in scope. Somalia (44) and Ethiopia (59) sit within 10 points of 50%, and
> with them the 20 fail the rule in every year from 2000 to 2024, so Eduardo kept the rule and
> dropped those two: 18 countries, the key still 3. Form B has the same number, as far as possible
> different ones. Only Chad and Somalia in scope fall clear below 50% in 2007, B's year, so B is those
> two and 16 countries added to the scope for it, each at least 13 points above the line. A form B
> drawn entirely from new countries works only for 2000–2002, and then counts tiny countries such as
> Equatorial Guinea. Egypt, Libya and Sudan in A, and Algeria, Mauritania, Morocco and Tunisia in B,
> are not sub-Saharan, so the prompt says "in Africa". The handoff's world map was not taken: with
> every country coloured it fails the rule in every year and at every band boundary.

> **Re-tuned from the spec.** The spec's A-T5 (2013, all 17 countries) had South Sudan at 53 and
> Somalia at 44, and its B-T5 (2018) had Chad at 47 and Somalia at 53, all 3 points from the line.
> No single pool kept every country 10 points clear in two years with different counts, so each form
> has its own. B-T5 moved to 2007: 2018 left only one country clear below the line.

> **Redesign, 2026-09-25.** The handoff proposed another 13: Burkina Faso, Cameroon, the Central
> African Republic, Chad, Ethiopia, Guinea, Kenya, Mali, Niger, Nigeria, Senegal, South Sudan and
> Uganda. In 2013 South Sudan (53), Guinea (56) and Ethiopia (59) sit within 10 points of 50%, so
> the rule refuses it. Eduardo kept this set, and the scope is unchanged. "4 or more" became two
> options, "4" and "5 or more", so every item offers six.

### T6 — Crossing (line, hover)

*{Country}'s coverage became higher than {other country}'s at some point after 2000. Roughly when
did that first happen?* (Until 2026-10-12, "… at some point. Roughly when …": the chart then
started in 2000.) Options, in calendar order: 2000-2003, 2004-2008, 2009-2012, 2013-2016,
2017-2020, 2021-2024. 2000-2003 was added 2026-09-25 so that every item offers six options. No
key, margin or adjacent band moves.

| | Form A | Form B |
|---|---|---|
| Lines | Central African Republic, Ethiopia; and Afghanistan, Chad, Côte d'Ivoire, Democratic Republic of Congo, Nigeria, Somalia | Mozambique, Pakistan; and Benin, Gabon, Ghana, Guinea, Kenya, Sudan (Ghana and Guinea since 2026-10-12, for Cameroon and Madagascar) |
| Before 2000 (drawn since 2026-10-12, not asked) | Ethiopia passes the Central African Republic in 1994 and falls back below it in 1998 | the two change places five times: Mozambique passes Pakistan in 1987, Pakistan passes it in 1990, Mozambique in 1992, Pakistan in 1995, Mozambique in 1996 |
| Before | Ethiopia trails from 2000, by up to 12 points (2004) | Pakistan trails from 2000, by up to 22 points (2008–2010) |
| The crossing | Ethiopia rises (46, 50) as the Central African Republic falls (51, 48) | Pakistan climbs to 84 against Mozambique's 85; Mozambique then falls to 71 |
| First year strictly above | **2007** | **2020** |
| Lines meet at | 2006.71 | 2019.10 |
| Inside the band by | 1.79 years | 1.40 years |
| After | Ethiopia leads every year to 2024, by up to 36 points | Pakistan leads every year to 2024, by up to 30 points |
| Key | **2004-2008** | **2017-2020** |
| Nearest other line where they meet | Nigeria, 7.4 points (Afghanistan 12.7, Somalia 12.9, DR Congo 15.3, Chad 16.4, Côte d'Ivoire 27.4) | Sudan, 9.1 points (Kenya 9.4, Benin 11.8, Ghana 13.1, Gabon 14.3, Guinea 30.5) |
| Longest run of another line within 5 points of a named one, 1985–2024 | 4 years (Nigeria and Afghanistan, each beside Ethiopia; before 2000, Chad and DR Congo beside Ethiopia and Côte d'Ivoire beside the Central African Republic) | 4 years (Guinea beside Mozambique, 1992–1995) |

Bands, not years, because the static condition has no hover and an exact crossing year cannot be
read from the chart. **The key is the band containing the first year the overtaker is strictly
above** the other, having not been above the year before. The pairs were found by search over the
32 countries, which turned up five clean DTP3 crossings. The other three: China over Ukraine, whose
lines are both on A-T1's chart; Burkina Faso over Mozambique, only 1.17 years inside its band; and
Niger over Madagascar, which ties in 2010 and leads by 2 points the next year.

**Eight lines, no World line (2026-10-11).** Until then each chart drew its two lines alone: the
static reader had only the crossing to place, and isolating a line had nothing to remove, so T6
could show no benefit of interactivity but hover's. Each chart now draws six more countries,
found by search over the scope for lines that cross the named pair away from where they meet. A
static reader must first find the two named lines by their tags and colours and follow them back
through the others. The extra lines cross the named ones elsewhere: in A, DR Congo passes the
Central African Republic in 2004, Nigeria passes it in 2008 and Ethiopia in 2009, and Chad passes
it in 2013 and again in 2018, Afghanistan passes Ethiopia in 2001 and 2018 and Somalia in 2022,
and Côte d'Ivoire passes Ethiopia in 2012; in B, Pakistan passes Gabon and Benin in 2018, Guinea
passes Pakistan in 2007 and Mozambique in 2022, Ghana passes Mozambique in 2005, Kenya passes it in
2006 and 2018, and Sudan passes Pakistan in 2003. Between 2000 and 2024, A's extra lines cross the
named pair 33 times in all, and B's 29 (33 until 2026-10-12: Madagascar and Cameroon crossed it ten
times, Ghana and Guinea cross it six). Not Congo in A: its tag would sit beside DR Congo's. The rule keeps the item readable without the controls: no extra line comes
within 5 points of where the pair meet, and none runs alongside a named line for 5 years or more,
the clause T1 already used for the same reason. Every extra line reports every year, and no colour
is shared (`docs/visual-spec.md` §4).

World stays off both charts. In B-T6 it runs at 85–86 through 2014–2019, and at 2019 it sits 2.1
points from where the pair meet; Pakistan also rises above it in 2021, a second crossing in the next
band. The rule's meeting-point clause refuses that chart. A-T6 could draw World, which runs about 29
points above its crossing, but it is left off there too, so both forms draw eight countries.

**The affordances are the chips and hover.** The chips leave the two named lines alone on the
chart, which removes the six others the static reader must look past. A click on either line fades
everything but it, since 2026-10-12 (until then it hid them). Line charts use the closest-point
tooltip, so hovering either line near the crossing gives its exact value, and the tooltip's change
from the year before shows which line is rising. Zoom, and since 2026-10-12 the Years slider,
works here as on every line chart.

> **Drawn from 1985, asked from 2000 (2026-10-12, Eduardo).** Every line chart now starts in 1985
> (`docs/visual-spec.md` §1), so the Years slider has years to set aside. Both pairs cross before
> 2000 (the table's "Before 2000" row), so "first" would name 1994 in A and 1990 in B, where no
> option is. The question now says "after 2000"; key, bands and options are unchanged. A reader
> who takes the first crossing on the chart has no option for it. The nearest, 2000-2003, is wrong
> in both forms and is not the adjacent band of either key, so the strict and adjacent-band scores
> both count that reading wrong (§10).
>
> Drawn from 1985, B-T6 failed the rule's close-run clause, which is judged on every drawn year
> (Acceptance rule, above):
> - Madagascar ran within 5 points of Pakistan for 9 years (1995–2003) and of Mozambique for 5
>   (1986–1990);
> - Cameroon ran within 5 points of Pakistan for 7 years (1996–2002).
>
> **Ghana and Guinea replace them**, found by search as the six were. Both report every year from
> 1985 and stay clear of where the pair meet (13.1 and 30.5 points). Both are African, as the
> lines they replace are, and neither is on A-T6. Their 2024 ends (95%, 63%) keep away from
> Pakistan's and Mozambique's name tags (87%, 70%). Of the other African countries that passed,
> Malawi, Libya, Zimbabwe, Tanzania, Burkina Faso and Uganda each end within 4 points of Pakistan's
> tag, and Congo passes 5.2 points from where the pair meet. A-T6 passes as it stands. The pair's own
> lines, keys and margins are unchanged.

> **Adjacent-band credit, pre-registered as a secondary for T6** (§7). A reader who puts the
> crossing a year late or early lands in the key band in both forms, since the lines meet more than
> a year inside it. The credit is for one step further: the key band, or the band containing the
> key year ± 1. B-T6's key year, 2020, closes its band, so a reading of 2021 earns it. A-T6's,
> 2007, is mid-band, so there the secondary is the strict score. It was
> pre-registered for the crossing items of the 2026-09-22 bank, dropped with them, and is restored
> with this one.

### Matching the forms

| | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|
| Margin, form A | drop 80, rise 36 | 7 / 6 | 6 | 17 | 11 | 1.79 years |
| Margin, form B | drop 31, rise 39 | 5 / 13 | 8 | 11 | 10 | 1.40 years |
| Floor | drop 25, rise 25 | 5 | 5 | 10 | 10 | 1 year |

`tests/test_scoring.py` pins these margins, so a data refresh that moves one fails the suite rather
than quietly unbalancing the forms. Eight known differences go to the pilot (§10):
- **T2 and T4 ask different questions in each form (2026-10-12).** A-T2 the third-highest bar, B-T2
  the sixth-highest, its key on the 5-point floor above; A-T4 the lowest cell, B-T4 the highest,
  which no row sort brought to the top until Highest cell first, the same day (T2, T4 above). The pairs are matched in chart and rule, not
  in question, so a form difference on either item is expected rather than a surprise.
- T1's falling line: Ukraine's collapse (80 points, 2008–2016) is far larger and faster than
  Brazil's decline (31 points over a decade). A-T1 is probably the easier form.
- A-T4's key clears the next row by 17 points and two bands, B-T4's by 11 and one (T4 above). A-T4
  is probably the easier form.
- B-T3's closest dots sit on the 4-point floor. Since 2026-10-11 B's dots were also more crowded
  than A's. Since 2026-10-13 the gap is small: A's closest pair is 4.1 points, and A has 6 pairs
  within 8 points against B's 7 (T3 above). Three of B's dots are A's, placed exactly as in A.
- The two T6 crossings are drawn differently. In A, two lines converge from opposite directions. In
  B, one line climbs to meet a level one, and the lines come within 1 point a year before they
  cross. A's nearest extra line passes closer to where the pair meet (Nigeria, 7.4 points) than
  B's (Sudan, 9.1), so A may be the harder form to read without isolation. Since 2026-10-12 A's
  extra lines also cross the pair more often between 2000 and 2024 (33 times against B's 29).
- **The T6 pairs cross differently before 2000 (2026-10-12),** where the question does not ask. In
  A, Ethiopia is above the Central African Republic for four years, 1994–1997. In B, Pakistan and
  Mozambique change places five times, 1987–1996, mostly by a few points. B's earlier crossings are
  more, and A's is plainer. Which one draws more readers who miss "after 2000" is for the pilot.
- **A-T1's falling line starts mid-chart (2026-10-12).** Ukraine reports from 1992, and no
  caption says why (`docs/visual-spec.md` §3); every line on B-T1 starts in 1985. Also, with
  "after 2000", A-T6's question takes two lines on a 1440-wide window where B-T6's takes one
  (§10).

### Practice task (unscored)

*Practice (not scored). Look at Myanmar's line. Did coverage rise, fall, or stay level between 2019
and 2021?* Myanmar and World, DTP3, 1985–2024 (2000–2024 until 2026-10-12): a fall from 90% to
37%, unmissable. Shown in the
participant's first condition only, identical across forms, to teach the interface rather than the
concept. It is a line chart, the type with the most controls. The other types' controls are
described in the instructions and by the hint row under each chart in the interactive condition.

> **Changed 2026-09-23.** The practice was Ukraine's collapse between 2008 and 2016, and A-T1 now
> asks for Ukraine's lowest year: a first half of form A would have been answered by its own
> practice. No scored prompt names Brazil (`tests/test_tasks.py`).

> **Changed 2026-09-27.** B-T1 now names Brazil, and the practice asked whether Brazil fell between
> 2015 and 2021: exactly B-T1's story. The practice moved to Myanmar, which no scored prompt names
> and which is no longer on either T1 chart. It appeared elsewhere only as an unasked heatmap row in
> B-T4, whose columns skip 2021, until that row left B-T4 on 2026-10-12.

> **Changed 2026-10-12** (pilot session 1, Eduardo). The window was 2015–2021. Myanmar holds at
> 89–91% through 2019 and falls only at the end, to 84 in 2020 and 37 in 2021, so most of the
> window reads as level. 2019–2021 is the fall alone, 90% to 37%. (Ending in 2020 instead would
> have asked about 89 → 84, which reads as close to level.)

### Revision 2026-09-23, in brief

- **Six new item types** on five chart types, one affordance each (above), replacing the reference,
  trend, crossing and gap items.
- **T6, a crossing item, added the same day**, so the bank has one item whose answer is a relation
  between two series. It follows the old bank's crossing rule, tightened (above).
- **Kept from the spec as written:** B-T1, and every item's affordance, chart type and question.
- **Changed to pass the acceptance rule:**
  - A-T1's options;
  - both T2 bar sets;
  - both T4 grids;
  - both T5 pools and B-T5's year;
  - A-T3's dots.
- **Changed for balance:** B-T3 drops Laos, so both scatters have six dots; option subsets were chosen
  so no answer position holds more than a third of the keys (§5).
- **Gone with the old bank:** the gap item's separate reporting. No item asks about missing data now; the gap
  caption stays for a data refresh (`docs/visual-spec.md` §3). The adjacent-band secondary went too,
  and came back with T6 (§7).

### Revision 2026-09-25: the largest-rise item dropped

- **Dropped:** *In which single year did its coverage rise the most over the year before?*, on
  Pakistan's line in form A and Bangladesh's in form B. With the crossing item added, line charts
  carried three of seven items. Eduardo chose to keep two, the crossing item among them.
- **Why this one and not T1.** T1 is the only item that needs the line controls — filter, sort and
  isolate, which the IRB forms describe — and the only line item whose affordance use is logged
  (§7). The rise item's affordance, the tooltip's change from the year before, is still on every
  line chart, and T6's tooltip uses it.
- **Renumbered.** The old T3–T7 are now T2–T6. A task id now names a different item than it did, so
  the log schema moved to v8 (`src/logging.py`). Nothing had been collected.

### Revision 2026-09-25: the redesign

The design handoff (`docs/design-handoff/`, `docs/study-redesign.md`) changed the items' options and
the controls, not the questions or the keys.

- **Six options per item.** Form A's sixth options came from the handoff. Two failed the rule and
  were replaced at Eduardo's choice: A-T1's 2012 became 2004, and A-T5 kept its 13 countries
  instead of the handoff's set (T1, T5 above). Form B's sixth options mirror A's.
- **No World line on T1**, in either form.
- **Controls on every chart:** country chips and Reset view everywhere, a row sort on the heatmap,
  and a typed threshold on the map in place of the range slider (§2).
- **Unchanged:** every key, every margin in the table above, and the scope (3900 rows).

### Revision 2026-09-27: T1 becomes a written comparison

- **Replaced:** T1's lowest-point question, with a written description of two named lines and how
  they compare (T1 above). Kept in RQ1 and scored by rubric (§7).
- **Charts:** A's is unchanged. B's swaps India and Myanmar for Uganda and Nepal.
- **Practice:** moved from Brazil to Myanmar (above).
- **Keys:** ten keys are now options, T2–T6 in both forms, spread first: 1, second: 2, third: 3,
  fourth: 2, fifth: 2 (§5).
- **Log schema v11:** T1's `answer` is free text, and a T1 record carries no justification
  (`src/logging.py`). Nothing had been collected.

### Revision 2026-10-11: three more bars on T2

- **Added:** three bars to each T2 chart, all below the key (T2 above). Ten bars per form.
- **Unchanged:** the question, the key, its margins, the options and the key's position among them.
- **Log schema v12:** a v11 T2 answer was given against seven bars, a v12 one against ten
  (`src/logging.py`). Nothing had been collected.

### Revision 2026-10-11: ten more dots on T3

- **Added:** ten dots to each T3 scatter, every one improving at least 20 points less than the key
  (T3 above). Sixteen dots per form.
- **Scope:** thirteen countries added, three African (Benin, Libya, Sudan) and ten Asian (Iraq,
  Jordan, Kyrgyzstan, Laos, Lebanon, Oman, Philippines, Syria, Thailand, Yemen), each used only by
  T3. 52 entities, 5200 rows.
- **Visual:** past eight dots the colours repeat, so every dot has its own marker shape
  (`docs/visual-spec.md` §6). Applies to both conditions.
- **Unchanged:** the question, the key, the margin, the closest pair, the options and the key's
  position among them.
- **Log schema v13:** a v12 T3 answer was given against six dots, a v13 one against sixteen
  (`src/logging.py`). Nothing had been collected.

### Revision 2026-10-11: the chart handoff

- **Restyled:** every chart, both conditions alike, from `docs/chart-handoff/` (`docs/visual-spec.md`).
  The handoff draws Form A's five chart types; Form B, T6 and the practice take the same style.
- **T3:** dots named beside them and coloured by change, with no legend. The question, dots, key and
  options are unchanged, but the static cost changed (T3 above), and the acceptance rule gained a
  clause: the key shares its change colour.
- **T4:** cells drawn in nine bands. Both grids already passed the new clause (T4 above).
- **T5:** 18 countries per form, Africa-wide, named on the map (T5 above). Keys unchanged.
- **Line charts:** no legend; the name tags and the chips do its work.
- **Scope:** sixteen countries added for B-T5 only (Algeria, Botswana, Congo, Côte d'Ivoire, Eritrea,
  Gabon, Ghana, Guinea, Malawi, Mauritania, Morocco, Namibia, Senegal, South Africa, Tunisia,
  Zimbabwe): 68 entities, 6800 rows.
- **Log schema v14** (`src/logging.py`): a v13 T3 or T5 answer was given against a different chart,
  and T5's prompt changed. Nothing had been collected.

### Revision 2026-10-11: six more lines on T6

- **Added:** six countries to each T6 chart, so isolation has lines to remove (T6 above). Form A:
  Afghanistan, Chad, Côte d'Ivoire, Democratic Republic of Congo, Nigeria, Somalia. Form B: Benin,
  Cameroon, Gabon, Kenya, Madagascar, Sudan. Eight lines per form, every series colour used once,
  all already in the scope.
- **Rule:** T6 gains T1's clause, so no other line runs within 5 points of a named one for 5 years
  or more (`analysis/keys.py`).
- **Unchanged:** the question, the pair, the key, the band margin, the options and the key's
  position among them.
- **Log schema v15:** a v14 T6 answer was given against two lines, a v15 one against eight
  (`src/logging.py`). Nothing had been collected.

### Revision 2026-10-11: T2 and T4 move to MCV1

- **Changed:** T2 and T4 read MCV1 in both forms, so the bank uses two of the dataset's four
  vaccines. The other items stay on DTP3. A-T2 swaps Brazil's bar for Guinea's; B-T2 moves to 2021
  and swaps Cambodia's bar for Algeria's; A-T4 swaps the Central African Republic's row for
  Benin's (T2, T4 above). B-T4's grid is unchanged.
- **Options:** A-T2 now offers China, Ethiopia, Guinea, India, Kenya and Vietnam; B-T2 Algeria,
  Colombia, Egypt, Mozambique, Nigeria and the United States; A-T4 Benin in place of the CAR.
- **Unchanged:** every key, and its place among the options, so the spread in §5 holds. The chart
  titles read "MCV1 coverage, …" on these items, from the item's vaccine; nothing else on the
  screen names the vaccine, as before.
- **Log schema v16:** a v15 T2 or T4 answer was given against a different chart, and a v15 B-T2
  prompt named a different year (`src/logging.py`). Nothing had been collected.

### Revision 2026-10-12: new wording, and new questions on B-T2 and B-T4

- **Reworded (Eduardo), same key, chart and options:** T1 in both forms ("Look at {country} and
  {country}'s coverage. … how their trends were similar or different."); T3 in both forms (no
  longer names the continent, or "the dot furthest above the diagonal"); A-T4 ("Which country
  contains the single lowest coverage?", without "Darker cells mean lower coverage").
- **New questions:** B-T2 asks for the sixth-highest bar, in 2017, key Mozambique; B-T4 for the
  highest cell, key Nepal, with Laos and Cameroon in place of Myanmar and Uganda (T2, T4 above).
  Both re-pass the acceptance rule, which gains the highest-cell mirror for T4.
- **Options:** B-T2 Algeria, Cameroon, Egypt, Indonesia, Mali, Mozambique; B-T4 Cameroon, Laos,
  Mali, Nepal, Niger, Pakistan. The keys now sit first: 0, second: 1, third: 3, fourth: 3,
  fifth: 2, sixth: 1 (§5).
- **Not matched:** the two forms now ask different questions on T2 and T4 (Matching the forms,
  above).
- **Log schema v17:** a v16 answer to any of these prompts was given to different words, and a v16
  B-T2 or B-T4 answer to a different question (`src/logging.py`). Nothing had been collected.

### Revision 2026-10-12: line charts drawn from 1985

- **Why (Eduardo):** to give the Years slider years to set aside. Over 2000–2024 alone it could
  only narrow a chart that already showed everything a question asked about.
- **Drawn:** every line chart, 1985–2024: T1 and T6 in both forms, and the practice. The bar,
  scatter, heatmap and map are unchanged. They show only the years they name.
- **Asked:** unchanged. T1 still asks about 2000 to 2024, and the practice about 2019–2021. T6 now
  says "after 2000", since both its pairs cross before then (T6 above).
- **Rule:** the answer is judged on 2000–2024, and traceability on 1985–2024 (Acceptance rule,
  above).
- **Lines replaced:** on A-T1, Gabon for Nigeria. On B-T6, Ghana and Guinea for Cameroon and
  Madagascar. B-T1 and A-T6 unchanged.
- **Keys:** unchanged, with the same options and positions. T6's margins are unchanged. B-T6's
  nearest other line and longest close run are re-measured (T6 above).
- **Scope:** years 1985–2024 for every entity and vaccine, 68 × 40 × 4 = 10,880 rows. Every value
  from 2000 on is unchanged. More values are unreported before 2000, HepB3's most of all. They
  stay explicit gaps. The only one any chart draws is Ukraine's DTP3 before 1992, on A-T1.
- **IRB:** the approved request form describes the data as coverage "from 2000 to 2024". Eduardo
  asks HSRRC before the change goes live (§10).
- **Log schema v19:** a v18 T1 or T6 answer, or a practice answer, was given against a chart drawn
  from 2000, and a v18 T6 answer to different words. The Years slider's logged values now run from
  1985. Nothing collected for the study.
- **Not taken:** a start in 1980. Ukraine, Nigeria, Côte d'Ivoire, Kenya and Benin report only from
  the mid-1980s or later, and each pair's earlier crossings would only grow. Also not taken: asking
  about the whole of 1985–2024. A-T1 fails its rule over that period, India's 1990–1992 dip being
  14 points, and Ukraine is unreported for seven of those years.

### Revision 2026-10-13: four more rows on T4

- **Added:** four rows to each T4 heatmap, every one beyond the six option rows, on the far side
  from the key (T4 above). Twelve rows per form. Form A: Cote d'Ivoire, Iraq, South Africa, Syria.
  Form B: Democratic Republic of Congo, Ethiopia, Nigeria, Yemen. All already in the scope.
- **Unchanged:** the question, the key, its margin and band, the options and the key's position
  among them. No row is shared with the other form's grid beyond Mali and Pakistan.
- **Visual:** rows 31.17 px tall, not 46.75; both conditions alike (`docs/visual-spec.md` §1). The
  heatmap's chips are smaller, so twelve run 6/6 beside Sort rows (§7.3 there), and neither
  card's height changes (§10).
- **Log schema v20:** a v19 T4 answer was given against eight rows, a v20 one against twelve
  (`src/logging.py`). Nothing collected for the study.

### Revision 2026-10-13: five more dots on T3

- **Added:** five dots to each T3 scatter, every one improving at least 20 points less than the key
  (T3 above). Twenty-one dots per form. Form A: Algeria, Eritrea, Guinea, Namibia, South Africa.
  Form B: Benin, Central African Republic, Cote d'Ivoire, Gabon, Sudan, the first three also on A's
  scatter. All already in the scope.
- **Unchanged:** the question, the key, its margin, the options and the key's position among them,
  and which dots share the key's colour. A's closest pair is now 4.1 points (6.1 before).
- **Visual:** both conditions alike. The Central African Republic's dot is named "CAR" (its chip
  too, in the interactive condition). The chips run seven to a row, 7/7/7 (`docs/visual-spec.md`
  §7.3), and no other chart's rows change.
- **Log schema v21:** a v20 T3 answer was given against sixteen dots, a v21 one against
  twenty-one (`src/logging.py`). Nothing collected for the study.

The 2026-09-22 bank, its audit and its acceptance rule for crossings and gaps are in the git history,
and so are the rise item and the lowest-point T1, with their rules and values.

## 5. Answer format

T2–T6 and the practice each collect two things:

1. **A multiple-choice answer** — scored objectively, no rater judgement.
2. **A short free-text justification** ("In one sentence, describe why you chose your answer.") —
   the material for RQ2.

**T1 collects one thing (2026-09-27): a written description**, in a text box headed "Write your
description:", in place of the options. There is no justification box: the description is the
reasoning, and it is the RQ2 material for T1. It is capped at 2,000 characters (`tasks.MAX_TEXT`),
the cap on the survey's free text. It is scored by rubric (§4, §7).

**Both may be skipped (2026-09-21).** The IRB form (item 10) and the consent form promise that a
participant may skip any question. Pressing Submit with either part empty opens a confirmation popup
naming what is unanswered; confirming moves on, cancelling returns to the task. A skipped part is
recorded as `null`, and `answer_submit` carries `skipped` — the list of parts left empty — so a skip
is explicit in the data rather than inferred from a blank. The practice item works the same way. On
T1 the popup names only the description, and `skipped` can hold only `answer`: no justification is
asked, so none can be skipped. The justification is not length-constrained. Correct answers are **never** stored in
`src/tasks.py`: that module ships to the browser, where an answer key would be readable in the page
source. Scoring happens offline against §7.

**Option order (2026-09-22).** The position of an option must carry no information about the answer.
- Where the options are countries, they are listed **alphabetically**. So are the chart's entities,
  which sets the order of bars, rows and chips, with World always last. Colour goes by country
  (`docs/visual-spec.md` §4), and by position only until 2026-10-11.
- Years and year bands run in calendar order; counts in their natural order.
- Which options an item offers is the one free choice. It is used to spread the key: no position
  holds more than a third of the keys. Every multiple-choice item offers six options (2026-09-25).
  Since T1 became a written item (2026-09-27), ten keys are options, and since 2026-10-12 they
  sit first: 0, second: 1, third: 3, fourth: 3, fifth: 2, sixth: 1. T6 has no free choice, since it offers all
  six bands; its keys sit second and fifth. `tests/test_scoring.py` fails if any position holds
  more than a third.

Before this rule, the country options were sorted by how much each changed, which put the correct
answer first in 7 of the then 12 items.

## 6. Surveys

### 6.1 Post-condition survey

After **each** condition — the consent form says so ("For each version … followed by a brief survey
with Likert-scale ratings of clarity, ease of use, confidence, and cognitive load"), and a single
survey after both would give one rating that cannot be split between the conditions it compares.

**Redesigned 2026-09-25** from the design handoff. One question per page, with a rail of sections
beside it. The first half's survey opens with "A few questions about the charts you just used."; the
second half's with "A few questions about the charts you just used, then a comparison of both
versions."

**Paas comes first** (kept 2026-09-25: it is RQ3's measure). Cognitive load is the Paas
mental-effort item:

> **In solving the preceding tasks, I invested:**
> 1 — very, very low mental effort … 9 — very, very high mental effort

One item, not NASA-TLX: with only two conditions per participant the extra subscales add
administration time and fatigue without much resolution. Logged as `load_rating` with
`{"scale": "paas", "value": 1-9}`.

Then the handoff's items, verbatim, on a 7-point agreement scale with every point labelled:
1 Strongly disagree, 2 Disagree, 3 Somewhat disagree, 4 Neither agree nor disagree, 5 Somewhat
agree, 6 Agree, 7 Strongly agree.

| Id | Section | Statement | Asked |
|---|---|---|---|
| a1 | Your experience | I am confident that my answers in this part were correct. | after each condition |
| a2 | | The charts were easy to understand. | |
| a3 | | I could quickly find the information I needed. | |
| a4 | | I could read values from the charts as precisely as the questions required. | |
| a5 | | It was easy to see where coverage increased or decreased. | |
| a6 | | It was easy to compare countries with each other. | |
| a7 | | Answering the questions took a lot of mental effort. | |
| a8 | | I felt frustrated while answering the questions. | |
| a9 | | I felt rushed while answering the questions. | |
| b1 | Chart controls | I could figure out how to use the chart controls without instructions. | after the interactive condition only |
| b2 | | The chart controls helped me answer the questions. | |
| b3 | | The chart controls were easy to use. | |
| c1 | Comparing the two versions | Which charts helped you answer more accurately? | after the second condition only |
| c2 | | Which charts did you prefer using? | |
| c3 | | What made one set of charts easier or harder to use than the other? | |

c1 and c2 offer "The charts with controls", "The charts without controls" and "No difference". c3
is free text, marked "Optional". Paas sits on the first page of "Your experience", before a1.

Logged, once per condition, as `survey_rating` with `{"scale": "likert7", "a1": …, …, "a9": …}`;
after the interactive condition also `controls_rating` with `{"scale": "likert7", "b1": …, "b2": …,
"b3": …}`; and after the second condition `comparison` with `{"c1": …, "c2": …, "c3": …}`. Every item
may be skipped, behind the same confirmation popup as a task (§5); a skipped rating is `null`. The
popup comes when Next leaves a page unanswered, once per page, and at Continue for the last page
only. Nothing is logged until Continue, so a participant can go back and change any answer.

The three items of 2026-09-21 (`clarity`, `ease_of_use`, `confidence`) are gone. a1 and a2 are near
two of them but reworded, so the two are not comparable.

### 6.2 About you

**Redesigned 2026-09-25**, replacing the four broad-category items of 2026-09-21. Asked once, at the
**end**, after the second survey. One question per page, with a rail of four sections: Session
setup, Background, Experience with data visualization, Topic familiarity. Introduced as "A few
questions about your setup and background." Every item may be skipped, behind the confirmation
popup, and most also offer "Prefer not to say". The wording is the handoff's (`auBuild()` in
`Study UI Screens.dc.html`), verbatim. An age that is not a whole number from 18 to 99 is refused on
its own page, when Next is pressed: "Please enter your age as a whole number from 18 to 99, or tick
Prefer not to say." (the server refuses it too). Typing in the box beside "Other" chooses "Other",
so text typed there is never dropped for want of a ticked option.

| Key | Id | Question | Answer |
|---|---|---|---|
| `pointer` | A1 | What are you using to control the pointer right now? | Mouse; Trackpad / touchpad; Touchscreen; Other (with a text box, `pointer_other`) |
| `age` | B1 | What is your age (in years)? | A whole number from 18 to 99, or Prefer not to say |
| `role` | B2 | Which best describes your current role? | Undergraduate student; Graduate student; Faculty or staff; Not affiliated with a college or university; Prefer not to say |
| `field` | B3 | What is your primary field of study or work? *(If you have more than one, choose the one closest to how you spend most of your time.)* | Computer science, math, or statistics; Natural or physical sciences (e.g., biology, chemistry, physics); Health or life sciences (e.g., kinesiology, public health, pre-med); Social sciences (e.g., economics, psychology, politics); Humanities or arts; Other (with a text box, `field_other`); Prefer not to say |
| `read_charts` | C1 | How often do you read or use charts, graphs, or dashboards (for school, work, or personal interest)? | Rarely or never; A few times a year; About monthly; About weekly; Daily or almost daily; Prefer not to say |
| `make_charts` | C2 | How often do you create charts, graphs, or dashboards? | Never; A few times ever; A few times a year; About monthly; About weekly or more; Prefer not to say |
| `stats_course` | C3 | Have you taken a course where data visualization or statistics was a major part? | Yes; No; Not sure; Prefer not to say |
| `tools` | C4 | How familiar are you with each of these tools? | For each of Tableau; Plotly or Plotly Dash; Microsoft Excel or Google Sheets charts; Power BI; Our World in Data charts: Never heard of it; Heard of it, never used; Used a few times; Use regularly; Prefer not to say |
| `topic_familiarity` | D1 | Before today, how familiar were you with data on childhood vaccination rates around the world? | 1 — Not at all familiar; 2 — Slightly familiar; 3 — Somewhat familiar; 4 — Very familiar; 5 — Extremely familiar; Prefer not to say |
| `health_background` | D2 | Have you studied or worked in public health, medicine, nursing, or epidemiology? | Yes; No; Prefer not to say |

**These are not all broad categories.** Request form 17, as revised 2026-09-26, promises that the
answers are kept under the participant ID only, never with a name, and that the text typed beside
"Other" is never quoted; the file that links IDs to people holds email addresses and names, not age.
This document goes further (decided 2026-09-26): age in years, role and field could together single
someone out in a small campus sample, so any write-up gives them only in aggregate, age as a median
and range and the other answers as counts, and a group of fewer than five participants is combined
with a neighbouring group or not reported. The form does not carry this rule (§10).

Logged as a `demographics` event, once per participant, in the **second** condition's log session,
after that session's `session_end`. The session is closed at its survey as before, so a participant
who stops at About you still leaves two complete sessions (§7's `incomplete_session`), and one who
stops earlier leaves no demographics. `tools` is an object from tool name to answer; `age` is an
integer or "Prefer not to say"; any value may be null (skipped).

## 7. Scoring

This section is a **pre-registration**. Every rule here is fixed before collection begins, because
choosing an exclusion rule after seeing the data is a methodological problem however reasonable the
rule is. `analysis/` implements it; nothing is decided at analysis time.

**Accuracy (RQ1).** Binary per task: from the multiple choice for T2–T6, and from the rubric for T1
(below). Primary outcome: proportion correct per participant per condition, **over T1–T6** (revised
2026-09-23: the old bank's gap item was reported separately, since its answer was printed on
screen, and no item's answer is on screen now).

**T1 is scored by rubric (2026-09-27).** Two coders each code **every** T1 description, blind to
condition, on four binary fields:

- parts (a), (b) and (c) of §4's rubric, each present or not;
- `contradicts`, set if the description states anything that contradicts one of them.

A description is correct when (a), (b) and (c) are all present and `contradicts` is not set.

- **Sheets.** They carry an opaque unit id and the text only, in a seeded shuffle, as for RQ2
  (below). The rubric is printed per form, since the text names its countries anyway.
- **Agreement.** Cohen's κ is reported per field, with prevalence, from the two independent codings,
  before any disagreement is discussed.
- **Disagreements** are settled by discussion, still blind, and the settled verdict is the score.
  Scoring refuses a sheet with a disagreement left open.
- **Uncoded answers.** A participant's T1–T6 proportion is not computed while their T1 is uncoded,
  never quietly scored out of five.
- **Skips.** A skipped description scores incorrect, like any skip.

**A skipped answer scores as incorrect** in the primary analysis (ruled 2026-09-21), so every
participant is scored out of six per condition. Dropping skips instead would let a condition that
provokes more skipping look more accurate than it is. *Secondary, pre-registered:* proportion correct
among answered items only, skips excluded. The number of skips per condition is reported alongside
both.

*Secondary, pre-registered for the crossing item (T6):* accuracy on T6 recomputed with adjacent-band
credit — the key band, or the band containing the key year ± 1 (§4). Reported alongside the strict
score, never in place of it, and never folded into the T1–T6 proportion.

*Secondary, pre-registered for the overloaded item (T1, 2026-10-12):* T1 reported on its own,
alongside RQ1, which still counts it:
- per condition, proportion correct and median time on T1;
- in the interactive condition, how many participants used any of T1's four extra controls (§4),
  and how often each.

Descriptive only. On T1 the overload and interactivity cannot be told apart, so a T1 difference
between conditions is reported as the effect of the overloaded interface, never of interactivity
alone. Set beside the other items, it shows how an overloaded chart fared against charts carrying
only the controls their questions use.

T2–T6 are scored by exact string equality against a key **derived from `data/deploy/coverage.csv`**
by the rule each item states. T1 has no key to derive, but its acceptance rule is checked on the same
data in the same place, and cross-checked against the tables in §4 (`analysis/keys.py`). A derived key
that disagrees with §4 fails the test suite. This exists because §4's prose key for an earlier item
was wrong — it said 2, the data said 1 — and nothing would have caught it.

**By item and chart type — descriptive only (added 2026-09-23).** Proportion correct and median time
per item, chart type and condition (`analysis/report.by_item`). Each item pairs one chart type with
one affordance (§4), so this is where a difference can be traced to an affordance. But each type
carries one item per form, the line chart two, so these are **never tested** and never reported
as per-chart-type effects.

**Which affordance a participant used** is known only where it is logged. Hovers are not logged
(decided 2026-09-21), so:

| Item | Affordance | Logged? |
|---|---|---|
| T1 | focusing a line (also chips, the Years slider, zoom); and the four extra controls, which it does not need | yes — `line_isolate`, `filter_change` (`chips`, `show-all`, `region`), `view_change` (`chart`, `years`, `coverage`, `display`), `sort_change` (`alpha`, `start`, `end`: the chip Order), `view_reset`. `filter_change` from `legend` stays in the vocabulary but cannot occur since the legend went (2026-10-11); View's `sort_change` keys cannot since View went (2026-10-12). |
| T2 | sorting the bars | yes — `sort_change` |
| T3 | hover; hiding dots with the chips; highlighting a band from the key | the chips and the key — `filter_change` (`chips`, `key`) |
| T4 | hover; sorting rows by lowest (A) or highest (B) cell; highlighting a band from the key | the sort and the key — `sort_change`, `filter_change` (`key`) |
| T5 | highlighting bands from the key (also chips) | yes — `filter_change` with `control` `key` (`threshold` until 2026-10-12) |
| T6 | hiding lines with the chips, focusing a line; hover | the line controls only — `line_isolate`, `filter_change` (`chips`, `show-all`) |

For T3, T4 and T6, an interactive participant who answers correctly may or may not have hovered.
Analyses of affordance use are confined to T1, T2, T3's and T4's key, T4's sort, T5 and T6's line
controls; for T3, T4 and T6 a correct interactive answer may rest on an unlogged hover, and the
write-up says so.

**Reasoning depth (RQ2).** Each justification coded on three binary features:

| Code | Present when the participant… |
|---|---|
| `cites_values` | refers to specific levels or magnitudes, however approximate |
| `compares_series` | refers to more than one country, not just the answer |
| `notes_uncertainty` | flags missing data, an estimate, or ambiguity |

T1 has no justification. Its description is coded in its place, on the same sheet (2026-09-27).
Since T1 asks about two countries, `compares_series` will be present in nearly every T1 unit, and
the write-up reports depth with and without T1.

Depth score 0–3. Code blind to condition. A skipped justification has no text to code; it is
absent from the coding sheet and missing, not zero, in the depth analysis. A second coder scores 20%
of the justifications; report Cohen's κ.

Blinding is enforced by the harness, not by discipline (`analysis/coding.py`): the coding sheet
carries only an opaque unit id and the justification text — no condition, no form, no participant,
and no task id. Justifications are emitted in a **seeded shuffle**, because they are produced in
condition-blocked order and an unshuffled sheet would let a coder infer condition from position. The
20% double-coded sample is **stratified by condition**, so reliability is not accidentally estimated
on one condition's material.

**κ is reported per code, with each code's prevalence** — three values, not one. κ is
prevalence-sensitive, so a low κ on a rare code (`notes_uncertainty` is the likely one) indicates
rarity, not poor coding. Where a coder used a single category throughout, κ is undefined and is
reported as such rather than as a number. At n ≥ 25 the double-coded sample is roughly 60 units:
conventional, but thin, and the write-up should say so.

**Cognitive load (RQ3).** Paas score per condition, 1–9. A skipped rating is missing for that
participant × condition. The survey (§6.1) is reported descriptively: a1–a9 per condition, b1–b3
for the interactive condition (the only one that asks them), and c1–c2 as a count of each answer
(`analysis/report`). c3's free text is reported descriptively too; it is not part of the RQ2
coding, which covers task justifications only. a7 (mental effort) is reported beside Paas, never in
its place.

**About you (§6.2)** describes the sample, as counts of each answer and the median and range of
age; it is not an outcome and enters no test. `analysis/report` prints every count, however small,
for the researcher; a group of fewer than five is combined or withheld when it is written up (§6.2).

**Time on task.** From the browser clock (`performance.now()`), never the server, so cold starts and
network latency do not enter a dependent variable.

### Exclusions

Decided before analysis. Each rule is a named, separately reportable filter; `analysis/exclusions.py`
returns the count and the affected ids for every one, and the write-up reports **how many were
excluded and why** as a table.

Two kinds, which the earlier flat list did not distinguish:

**Accuracy exclusions** — the response itself is not usable, so the row leaves every analysis.

| Rule | Definition |
|---|---|
| `incomplete_session` | The participant did not produce **two** log sessions each carrying a `session_end` and six scored answers — a skipped item still counts, since a skip is a response rather than an abandoned session. Stated this way because `session_end` is written per *condition*, not once at the end of the study, so "reached `complete`" needed a precise test. |
| `too_fast` | Task duration < 3000 ms — not read. A **null** duration is not "fast"; nulls are their own category and are never swept in here. |

**Timing exclusions** — the answer stands, but the duration is not usable, so the row leaves
time-on-task analysis only and keeps its accuracy.

| Rule | Definition |
|---|---|
| `invalid_timing` | The browser clock reset mid-task (a page reload), so no duration was recorded. Flagged in the data as `duration_invalid`; see §8. |
| `top_one_percent` | The top 1% of task durations — walked away. Computed **pooled across both conditions**, never per condition: a per-condition trim removes a different number of rows from each condition and can manufacture a difference by itself. |

**Reported, not excluded:** `degraded_session` — a session in which the event logger could not reach
the database and spooled locally (`sink_recovered` present). The answers are unaffected, but the
interactive condition pays a database round-trip inside the measured task window, so these sessions
are counted and timing analyses are re-run without them as a robustness check.

**Order is fixed**, because a different order gives different numbers: session-level rules first,
then `too_fast`, then the 1% trim computed on whatever survives.

## 8. Procedure

`consent → participant ID → instructions → practice → practice complete → 6 tasks → survey → break
→ instructions → 6 tasks → survey → about you → finished`

**Revised 2026-09-25** (the design handoff): a practice-complete screen now sits between the
practice and the first scored task, in the first half only, and About you (§6.2) moved from after
the participant ID to the end. A stepper in the header shows where the participant is: Consent,
Practice, Part 1, Break, Part 2, About you, Finished. It is display only; nothing in it can be
clicked.

Declining on the consent screen leads to a thank-you screen that confirms no data was collected (IRB
form item 12B), with a button back to the consent form in case the choice was a mis-click. Nothing is
written anywhere before consent, so the confirmation is true.

Implemented as `flow.Stage`; `tests/test_flow.py` walks the whole sequence.

**Instructions appear twice, practice once.** The conditions differ in what the chart can do, so a
participant entering their second condition is shown the instructions again, describing the version
they are about to use. Showing them only once would leave whoever draws the interactive condition
second unaware that the controls exist — a procedural difference between conditions rather than a
difference in interactivity, and one that would depress the interactive condition's scores for
exactly the wrong reason. Practice is not repeated: it teaches the interface, and by the second
condition the participant has used it.

**What the instructions say (revised 2026-09-25).** The wording is the design handoff's (screens
4a, 4b, 9a, 9b), with the copy fixes in `docs/study-redesign.md` §5. Its interactive bullets were
rewritten to describe the controls the charts actually have, and the first half's interactive
version (4b) now carries the same control bullets as the second half's (9b). Without that, whoever
draws the interactive condition first would meet the bar, heatmap and map controls with only the
hint row to go on, which is the procedural difference this section exists to prevent. In the
interactive condition, a hint row under each chart restates what that chart can do. Since
2026-10-11 the line charts have no legend, so the third bullet no longer mentions double-clicking a
name in it. Since 2026-10-12 the third bullet names the Years slider and zoom in place of View's
reorder, and says "focus on it" for a click on a line, which now fades the others rather than
hiding them (`docs/visual-spec.md` §7.3, §7.6). It is the one place zoom is named (Eduardo,
after the first pilot session). The fourth bullet names the key's colours in place of the map's
"Below [n] %" box, which went the same day (§7.4 of the visual spec).

**The one exception: T1's extra controls (2026-10-12) are named nowhere,** neither here nor in
T1's hint row (Eduardo). This section otherwise names every control, so that no participant meets
one unawares. T1's four are the overload (§4, T1), and whether they are found is part of what it
shows. They appear in both forms' interactive T1 alike, whichever half that falls in.

First half, both versions. Heading "Instructions", then "Practice Question":

> Before you start, please make this browser window full screen.
>
> Before the main set of questions, you'll try one practice question so you know what to expect. It
> won't be scored.
>
> You'll see a line chart of childhood vaccination coverage (the share of children who received a
> vaccine each year). Answer the question, then explain in one sentence how you decided.

The full-screen sentence was added on 2026-10-12, after the first pilot session, at the supervisor's
suggestion. It stands on the screen whose Begin records `window_size` (below), so the logged size
is the window the participant answered in.

Then, **static (4a):**

> - The chart is an image. Read values by comparing the line to the gridlines.
> - A break in a line means no value was reported for those years.
> - You can skip the question. If you leave it blank, you'll be asked to confirm.
>
> In the main task, you'll see other kinds of charts too: bar charts, scatter plots, coloured grids
> and maps. Those are images too: read them against the gridlines, or against the colour key where
> there is one.

Or **interactive (4b):**

> - The charts are interactive. Move your pointer over any line, bar, dot, cell or country to see
>   its value; on a line chart you also see its change from the year before.
> - Under each chart, the country buttons show or hide countries, and Reset view undoes your
>   changes.
> - On line charts you can also click a line to focus on it, choose which years to show (or drag
>   across the chart to zoom), and bring every line back with Show all.
> - The bar chart and the coloured grid can sort their bars or rows. On a chart with a colour key,
>   click a colour in the key to highlight what is drawn in that colour.
> - A break in a line means no value was reported for those years.
> - You can skip the question. If you leave it blank, you'll be asked to confirm.
>
> In the main task, you'll see other kinds of charts too: bar charts, scatter plots, coloured grids
> and maps.

Button: "Start the practice question". Second half, heading "Instructions", then "Second Half":

> This half uses a different version of the charts. The tasks are similar, but the charts work
> differently.

Then, **static (9a):** "The charts in this half are **static** images. They don't respond to your
mouse pointer and have no controls. Read them against the gridlines, or against the colour key where
there is one." Or **interactive (9b):** "The charts in this half are **interactive**:", followed by

> - Pointing at any line, bar, dot, cell or country shows its value. On line charts, it also shows
>   the change from the year before.

and 4b's second, third and fourth bullets. Both end: "As before, the first question asks you to
describe what a chart shows. For each of the others, you'll choose an answer and then say in one
sentence how you decided. Explain each one on its own, even if your reasoning is the same as in the
first half. A break in a line means no value was reported for those years. You may skip any
question, and you'll be asked to confirm if you leave one blank." Button: "Start the questions".

"Explain each one on its own…" was added on 2026-10-12. In the first pilot session the participant
asked, in the second half, whether an explanation given in the first had to be written again. A
participant who writes "same as before" gives the second half's explanations less to code, so
reasoning depth (RQ2) would depend on order.

The colour-key sentences in 4a and 9a are additions to the handoff, made so the static wording names
the colour key the heatmap and map are read against, as the 2026-09-23 wording did.

**Practice complete** (first half only), heading "Practice Complete!":

> That was the practice question. It was not scored.
>
> The next six questions are the ones that count. The charts use the same version
> (static/interactive) that you experienced in the practice question.
>
> For the first question, write a short description of what the chart shows. For each of the
> others, choose one answer, then write a short sentence response about your decision. After the
> sixth question, there are a few quick reflecting questions about your experience with this
> version.
>
> You may skip a question at any time. If you leave one unanswered, you will be asked to confirm.

Button: "Start the questions". **The break**, heading "Halfway There!": "Congratulations! The first
half of the study is complete! The next set will ask different questions using the other version
(static/interactive). Take a moment, then continue when you are ready." Button: "Continue".

**T1's wording (2026-10-12).** Since T1 became a written description (2026-09-27), the
practice-complete screen and the second half's closing paragraph had still said every question was
chosen and then explained. Both now name the first question as a description. The practice's own
instructions are unchanged, since the practice is chosen and explained.

The practice answer is recorded under `task_id` `P0` so that its timing is available, and **excluded
from scoring** (§7).

**Researcher script (2026-10-12, after the first pilot session).** Sessions are run in person
(request form 5B). The researcher says the same few things in each, and nothing else about the
charts:
- before the consent form: who the researcher is, and that the study compares two versions of the
  same charts of childhood vaccination data;
- before the link is opened: please make the browser window full screen (the first instructions
  screen asks again);
- if asked whether an explanation from the first half has to be written again: yes, explain each
  answer on its own (the second half's instructions say so too);
- to any other question about reading a chart or using a control: "Please do whatever you would do
  on your own."

The study's data is what the app logs (request form 5B). The researcher does not record what a
participant says or does. After the pilot, the supervisor proposed thinking aloud during the tasks,
follow-up questions at the break, and a debrief showing the controls left unused. Eduardo kept the
main study to logging only (2026-10-12): thinking aloud slows the timed tasks, a question at the
break can change how the second half is done, and the approved forms describe neither.

Participants self-serve from one URL. Session state lives in `sessionStorage`, so a closed tab ends
the session. Re-entering the same participant ID returns the same condition and form assignment,
never re-randomised — the assignment is held in the database and is idempotent.

> **Known limitation, corrected 2026-09-15.** This paragraph previously said a returning participant
> *resumes*. Only the assignment survives; the progress does not. `sessionStorage` is per-tab, so a
> participant who closes the tab and re-enters their ID restarts at the beginning of condition 1 and
> writes a second, overlapping set of events under the same participant ID with a new `session_id`.
> A reload within the same tab does keep their place.
>
> **The participant-ID screen no longer promises resume (2026-09-16).** It used to say a returning
> participant would "continue where the study left off". Since 2026-09-25 it reads: *"Thank you!
> Please download a copy of your signed consent form below. Afterwards, enter the ID you were given
> by the student investigator in the empty text area below. Please complete the study in one
> sitting, in this tab. Closing it ends your session."*
> Resume itself is still not implemented, so treat a participant with more than two log sessions as
> needing manual inspection before analysis — the `incomplete_session` rule in §7 counts sessions and
> would otherwise be misled.

Each condition is one log session, opened at its instructions and closed after its survey, so
both halves produce a complete `session_start … session_end` record. About you is written into the
second session after its `session_end` (§6.2).

**Timing integrity.** Task duration is the difference between two `performance.now()` stamps taken in
the participant's browser. That clock resets to zero on a page reload, which would otherwise yield a
plausible but wrong duration — an undercount measured from the reload, indistinguishable from a fast
answer. Each stamp therefore carries `performance.timeOrigin`, and a duration whose two stamps come
from different origins is recorded as **absent and flagged** (`duration_ms` null,
`duration_invalid: "clock_reset"`) rather than as a number. This follows the same principle as the
coverage data: a missing value is missing, never silently filled. Those rows keep their accuracy and
leave time-on-task analysis (§7).

**One answer per task.** Submit is disabled in the browser the moment it is pressed, and re-enabled
if the step is refused (an answer that cannot be read, or a database error; a blank answer is not
refused but confirmed in the browser before Submit is sent, §5) or if no response arrives within 15
seconds, so a participant is never left with a dead button. Disabling it is the guard that matters:
two rapid clicks send two requests that both carry the same pre-click session state, so the server
cannot tell them apart.
Behind it, the app refuses an answer for a task already recorded in the session, and the database
refuses a second `answer_submit` for the same session and task through a unique index. Without these
a double-click writes a duplicate answer and a duplicate `task_end`; it does not skip an item, since
both requests advance from the same starting point. The 15-second re-enable does nothing if the
button has left the page (2026-09-23): after the last task the survey is on screen, and
re-enabling a Submit that no longer existed made the page throw an error in every session. While a
Submit is in flight the button also carries `aria-busy="true"` (2026-09-25); its label never
changes.

**When nothing can be saved (2026-09-25).** A database that is only unreachable does not stop a
session: events are retried, then spooled in the browser and replayed later (CLAUDE.md, schema v4).
When a response cannot be saved anywhere, the screen's content is replaced by a blocking message:
*"The study cannot save responses right now, so it cannot continue. Please contact the
researcher."* That happens when the log sink cannot be opened or written at all, and when the
browser spool is full, so the next answer or rating would be dropped rather than kept. Built
2026-09-26: the header stays, with the position label of the screen replaced ("Question 3 of 6"),
and the session's stores keep whatever was written, so reloading the tab shows that stage again.
The researcher, who is present, decides whether to continue.

**Window size (schema v10, 2026-09-26).** Participants use their own computers (request form 5B),
and on a window 790 px tall or less the interactive scatter and map cards need scrolling where the
static ones never do (§10). So the first Begin logs a `window_size` event, once per participant,
right after `consent`: the browser window's inner width and height in CSS pixels, which is what the
layout answers to, with browser zoom and toolbars already taken out. The size is read whenever a
screen appears and again on every resize, so a window resized while the instructions are read is
logged at the size Begin found. A value the browser did not send is logged null and stops nothing.
Analysis carries it onto every task row as `window_width` and `window_height`.

**Finished.** Heading "Finished! Thank you!": "Your responses have been successfully recorded. You
can close this tab." and "If you change your mind, you can withdraw your responses within two weeks
of today, without giving a reason. Email rebollar@oxy.edu and include your participant ID (your
participant ID is {ID})."

## 9. Consent

The consent screen shows the Occidental informed consent form approved by HSRRC on 2026-10-12
(`irb/Oxy CS Senior Comps Informed Consent Form.docx`, local only), word for word. The app's copy
lives in `src/consent.py`; `tests/test_consent.py` pins it. `consent.APPROVED` is True; while it was
False, the screen carried a "pending approval" banner and no participant could be run.

**Approved 2026-10-12.** The approved form is the 2026-09-26 text word for word, all 961 words; its
"study’s" has a curly apostrophe where the 2026-09-27 PDF had a straight one, so the app's copy
changed to match and the hash was re-pinned.

**Revised 2026-09-25** to the design handoff's screen 1, which reproduces the finalized form as a
Letter sheet in Times New Roman, with the signing fields inside the sheet: the signature pad
(600 × 150), the date and the printed name on one line, and a "Clear signature" button that appears
after the first stroke. Its wording differs from
the 2026-09-21 transcription in four places, all listed in §10 for the IRB paperwork: about 40
minutes instead of 20 to 35 (twice), a new sentence in Risks on childhood vaccination as a sensitive
topic, "Neon (a managed PostgreSQL service)" instead of "Neon (managed by PostgreSQL)", and access to
"identifying data" instead of "the data". The hash in `tests/test_consent.py` was re-pinned.

**Revised 2026-09-26** (Eduardo): Procedures names the background questions, since About you
(§6.2) asks age in years, role, field and health background and the form never said so. After
"…short open-ended questions about your reasoning." it now reads: "At the end of the session, you
will be asked a few questions about your background, such as your age, your field of study or work,
and your experience with charts." The same day the text was checked word for word against the
revised form in `irb/`: all 961 words match once "study’s" takes the form's straight apostrophe.
Hash re-pinned (`c56a88875374666a`); listed in §10.

### How consent is given

IRB form item 12A: the participant types their **printed name** and the **date**, **signs**, and
presses **"I agree to participate"**. The signature is drawn with a mouse, trackpad or finger on a
signature pad. A participant who cannot or prefers not to draw one signs the paper copy the
researcher brings instead, and ticks "I have signed a paper copy of this form with the researcher
instead", a checkbox that works from the keyboard, which the pad does not.
"I do not agree" is always available (item 12B). The app refuses to go on without a name, a date and
a drawn signature, unless the paper box is ticked: the paper copy carries all three, so the box
alone lets the participant on (2026-09-27). A name or date typed as well is kept in the record.

Electronic documentation of consent is permitted by 45 CFR 46.117; confirm with HSRRC that Occidental
accepts a drawn signature.

### Where the signed consent goes

Items 15 and 17 require signed consent forms and identifying information to be kept apart from the
study data. So:

- **The signed record goes to its own table, `consent_records`, which has no participant ID.** It
  cannot be joined to answers through any key. (Locally, without a database, it goes to
  `data/consent/`, gitignored and separate from `data/study_logs/`.)
- **The study log gets only a `consent` event**: the browser timestamp, the consent-text hash and
  the signature method (`drawn` or `paper`). No name, no signature.
- `scripts/export_consents.py` writes each record out as a signed copy of the form, for the
  researcher to countersign and store in the encrypted Oxy Drive folder (item 15), and with
  `--purge` then deletes it from the database.
- The participant can download their own signed copy from the next screen. The paper form asks the
  subject to "keep one copy"; this is the digital equivalent.
- Consent must be recorded before the session continues. If the database cannot be reached, the
  participant is asked to try again, and nothing else happens. A consent record is never spooled or
  held back.

### How consent is logged in the study data

Selecting "I agree" captures a timestamp in the participant's browser. It is written to the log as a
`consent` event when the session's logger opens, a moment later, on the instructions screen — the
logger cannot open before then, because a log record must carry a participant ID and a condition, and
neither exists until the participant has entered an ID and been assigned. The event is emitted once
per participant, not once per condition.

Two consequences, recorded rather than hidden:

- The event's `server_ts` is the instructions-screen time; the true consent time is
  `payload.consented_at`. Analysis must read the latter.
- **A participant who agrees and then leaves before entering an ID has a signed consent record but no
  study data.** Nothing unconsented is ever stored.

The event also stores a hash of the consent wording shown, so a mid-study change to the text is
detectable in the data rather than being a matter of recollection.

### Withdrawal

IRB form item 13: a participant may withdraw their data **up to two weeks after the session**,
without giving a reason. The consent form says the same, and adds that after two weeks "your
responses will have been merged into the de-identified dataset and can no longer be pulled out".
The final screen tells them so, shows their participant ID, and gives the researcher's email.

The researcher runs `scripts/withdraw_participant.py <ID>`. It is a dry run by default. `--apply`
deletes every study event for that ID — from the database, from `data/study_logs/`, and from any
spool file, so `recover_spool.py` cannot bring it back — and marks the participant `withdrawn_at`
rather than deleting the registration, so counterbalancing cell counts stay explainable and the ID
cannot be used again. Past two weeks it refuses without `--late`.

The signed consent record is kept: it is proof that consent was given, subject to the retention rules
in item 15, and it is not study data. Copies already exported — `data/study_logs/derived/`, a CSV
export, the Drive — must be regenerated or deleted by hand; the script lists what to check.

## 10. Open items

- IRB approval, and the final consent wording.
- **Changes since HSRRC's approval (2026-10-12): no amendment needed.** Eduardo put them to
  HSRRC, which answered the same day that they need no amendment. The approved request form
  describes the features generically ("filtering, sorting, line isolation") and the logging as
  "clicks, filter and sort selections". Every new control stays inside that, and no item was added
  or removed. These change what the approved questionnaire (item 18) shows:
  - the practice question's wording (2019–2021);
  - the controls: a Years slider in place of View; a click on a line fades the others; the heatmap
    sort's options; the key's colours in place of the map's highlight box; and T1's four extra,
    unannounced controls;
  - the instructions: the full-screen request, "explain each one on its own", and the line and key
    bullets.

  `irb/questionnaire.pdf` was re-exported with all of them on 2026-10-12 (37 pages, consent text
  version `3bcd2413c9656ae8`).
- **Line charts drawn from 1985 (2026-10-12): approved by HSRRC on 2026-10-13, with the consent
  form unchanged.** The approved request form (item 9) describes "WHO/UNICEF childhood vaccination
  coverage from 2000 to 2024". The line charts now draw 1985–2024, and T6's wording changed (§4).
  Every question still asks about 2000 onward, and no item, control or logged field was added.
  `irb/questionnaire.pdf` is re-exported with the new charts and T6's wording.
- **Pilot session 1 (2026-10-12).** One participant, Eduardo's faculty supervisor: the static half
  on form A, the interactive half on form B, 36 minutes in all. It is pilot data, kept out of the
  study: the participant knows the study's hypotheses, and the instrument changed after the
  session. On 2026-10-12 its 85 events (schema v17) and its registration were exported to
  `data/study_logs/pilot/` (local, gitignored), then removed from Neon by
  `scripts/withdraw_participant.py`. ID `1` is marked withdrawn at seq 13 and cannot be used again.
  **The study starts at seq 14 (interactive first, form A).** The signed consent record stays in
  Neon until `scripts/archive_consents.py` moves it to the Drive. Changed because of it:
  - the practice asks about 2019–2021, not 2015–2021 (§4);
  - the heatmap's row sort is A–Z, Lowest cell first, Highest cell first; Average went (§4, T4);
  - the chips run at most six to a row (`docs/visual-spec.md` §7.3; seven since 2026-10-13);
  - a Years slider replaces View on the line charts, and zoom is named once in the instructions
    (`docs/visual-spec.md` §7.6);
  - a click on a line fades the others instead of hiding them (`docs/visual-spec.md` §7.3);
  - a click on a colour in the key highlights its band on the scatter, heatmap and map; the map's
    "Below [n] %" box went (`docs/visual-spec.md` §7.4);
  - the line chart's hint names hover;
  - the first instructions screen asks for a full-screen window;
  - the second half asks for each answer to be explained on its own;
  - a researcher script (§8);
  - T1 overloaded with four unannounced controls it does not need, the counterpoint the supervisor
    asked for (§4, §7).
  
  Not changed:
  - no background music;
  - the heatmap's cells stay colour only: numbers in them would give a static reader exact values
    (§2), and the participant preferred reading the key;
  - the one-sentence explanation stays (the participant found it useful, not repetitive).
- **No further pilot (Eduardo, 2026-10-13).** The study starts directly after pilot session 1, at
  seq 14. Every "pilot check" in this document (§4 and the list below) is therefore read from the
  study's own data, after collection, and can no longer change an item before it. An item changed
  mid-study would split the data by schema version, which analysis refuses to pool
  (`analysis/reshape.py`).
- **Checks for the 2026-09-23 bank, as redesigned 2026-09-25** (read from the study data, above):
  - **Static accuracy on T2, T4 and T5.** Their margins sit at the floor on purpose (5, 10 and 10
    points), so they are the hardest static reads. Near-chance static accuracy (one in six) would
    mean the floor is too tight for that chart type.
  - **Form equivalence.** T1's falling line is Ukraine's 80-point collapse in form A and Brazil's
    31-point decline in form B (§4). B-T3's two closest dots sit exactly on the 4-point floor and
    A-T3's 0.1 above it; since 2026-10-13 the two scatters are about as crowded, and share three
    dots (§4). The T6 crossings are drawn differently (§4).
  - **Whether T3 sits at ceiling in both conditions (2026-10-11).** Its dots are named and coloured
    by change, which removes the legend lookup that was its static cost (§4). If static accuracy
    matches interactive accuracy near ceiling, T3 measures little about hover.
  - **Static accuracy on T5's new maps (2026-10-11).** Eighteen countries per form, Africa-wide, and
    form B's from the countries added to the scope for it.
  - **T1, the written item (2026-09-27).**
    - Its time, since it is the only item written in full.
    - Whether the rubric can be applied: κ per part, and how many descriptions the coders had to
      discuss.
    - Whether a part fails for nearly everyone in both conditions, which would point at the rubric
      rather than the reading.
  - **T6 against its adjacent-band secondary.** If the two scores differ much, static readers are
    placing the crossing a band off, and the band edges are doing the work.
  - **T4's forms on MCV1 (2026-10-11).** A's margin is 17 points against B's 10 (§4). If A-T4's
    static accuracy is clearly higher, one of the two grids needs changing.
  - **T6 with eight lines (2026-10-11).** Static accuracy, and form equivalence, since A's extra
    lines sit nearer the crossing than B's (§4); and how often interactive participants hide the
    other lines, or focus one of the two, before answering, which the logs show.
  - **Line charts drawn from 1985 (2026-10-12).**
    - How many interactive participants set the Years slider to 2000 or later on T1 and T6, and
      whether they score better than those who do not. The logs show it (`view_change`, `years`).
    - How often T6 is answered 2000-2003, the band nearest each pair's crossing before 2000, by
      condition. A cluster there means readers took the first crossing on the chart and missed
      "after 2000".
    - Whether T1 descriptions turn on 1985–1999, and how coders handle them (§4, T1).
    - Whether A-T1 descriptions treat Ukraine's line, which starts in 1992 with no caption to
      say why, as part of its trend (§4, Matching the forms).
  - **Whether the interactive affordances are found at all.** Especially the chips, the heatmap's
    row sort, the key's colours and the bar sort, which the practice does not teach. The logs show
    all four (§7).
  - **T1's overload (2026-10-12).**
    - Do interactive participants find the four extra controls, and use them?
    - Does T1 take longer interactively than statically, by more than T6, the other line chart?
    - The second controls strip pushes T1's Submit past the fold on common windows, a 1440 × 900
      laptop included (measured, below). Split T1's interactive times at 944 px (932 until the
      spacing of 2026-10-13, below).
  - **Whether T4 and T5 sit at ceiling in the interactive condition.** On T4 the row sort answers it
    in one click in both forms: Lowest cell first in A and, since 2026-10-12, Highest cell first in
    B. So does a click on the key cell's band. On T5, two clicks on the key's darkest bands leave the
    answer at full strength, once the reader has worked out that those bands are below 50 (§4).
  - **T2 and T4 asking different questions per form (2026-10-12).** B-T2 counts to the
    sixth-highest bar with 5 points above it; B-T4 asks for the highest cell, among light bands
    (§4). Compare each item's static and interactive accuracy per form; if B is clearly harder on
    either, the pair is not one item measured twice.
- **Scrolling differs by condition on two items (accepted 2026-09-26).** On a window 790 px tall
  or less, the interactive scatter (T3) and map (T5) cards run past the fold, so interactive
  participants scroll to Submit there and static ones never do (`visual-spec.md` §10). Eduardo
  accepted it over tightening the layout. In the data, look at the interactive time on T3 and T5
  for it. Participants use their own computers (request form 5B), so the window height varies by
  participant; `window_size` records it (§8), and `tasks.csv` carries it as `window_height`, so
  the interactive T3 and T5 times can be split at 790 px. **Since 2026-10-11 the splits are 898 px
  for T3 and 843 px for T5** (862 and 807–836 in compact mode, at or under 800 px): T3's sixteen
  chips take two more rows, and T5's map has eighteen chips in each form where it had 13 and 11
  (`visual-spec.md` §10, measured in headless Chrome after the chart handoff). **Since 2026-10-12
  T3's split is 862 px (826 in compact mode)**, its chips in three rows. The same measurement found
  the interactive T1 card past the fold too. With the Years slider in place of View, its split is
  826 px (790 in compact mode, so it scrolls at 1366 × 768 but not at 1440 × 790). Split T1's
  interactive times the same way. **With the map's highlight box gone, T5's split is 807 px** (771
  in compact mode at 1440 wide, 800 at 1366 × 768). **With T1's four extra controls (§4, T1),
  T1's split is 932 px (896 in compact mode)**: its interactive card is the only one that runs
  past a 1440 × 900 window, by 32 px. **Drawn from 1985 (2026-10-12), T1's split stays 932 px in
  both forms**: A-T1 carries no gap caption (§4). T6's wording ("after 2000") wraps A-T6's question
  onto a second line at 1440 and 1536 wide, as it already did at 1366. Its card is 29 px taller
  there in both conditions, and its interactive Submit still ends inside a 1440 × 790 window
  (about 764 px). Measured in headless Chrome against B-T1, which the change left as it was.
  **Since 2026-10-13 every interactive Submit ends 12 px lower**: the controls strip stands
  further from the chart (`visual-spec.md` §10). The splits are now T1 944 px (908 in compact
  mode), T3 874 (838), and T5 819 (783 at 1440 wide, 812 at 1366 × 768). A-T6's interactive
  Submit ends at about 776 px, still inside a 1440 × 790 window. The static cards are unchanged.
  T4's twelve rows (2026-10-13) leave its cards' heights as they were: the interactive Submit
  ends at 787 px (751 in compact mode), inside a 790 px window (`visual-spec.md` §10). So do
  T3's twenty-one dots, the same day. The chips still take three rows, now of seven, so T3's split
  stays 874 px (838 in compact mode).
- **Hover is not logged**, so affordance use cannot be observed for T3, T4 and T6 (§7).
- **Keyboard-only participants.** Hover and clicking a line are mouse-only, so a
  keyboard-only participant in the interactive condition meets T3 and T6 with only the chips, and T4
  with only the row sort. The chips, the sorts, the key's colours, Show all and Reset view all work from
  the keyboard (`docs/visual-spec.md` §8); a whole session was run from the keyboard alone on
  2026-09-26, consent (by the paper-copy box) to About you. Since 2026-10-12 the Years slider also
  zooms the line charts from the keyboard. Since 2026-10-13 a key on a control does nothing while
  the chart redraws, as a click does (`docs/visual-spec.md` §7), so a held arrow key moves a
  slider one step per redraw.
- ~~Whether the items can be answered without hover.~~ Resolved 2026-09-22 by the item acceptance
  rule, and kept for the 2026-09-23 bank, which was re-tuned to pass it (§4).
- **Session resume is not implemented.** The participant-ID screen no longer promises it; it asks
  for one sitting in one tab instead. See §8.
- ~~Whether the justification should be optional.~~ Resolved 2026-09-21: every question may be
  skipped (IRB form item 10), behind a confirmation popup. See §5.
- **IRB paperwork revised 2026-09-26** (then `irb/COMP 490 Request Form.pdf` and `irb/COMP 490
  Consent Form.pdf`, renamed `irb/Oxy CS Senior Comps Approval Request Form.pdf` and `… Informed
  Consent Form.pdf` on 2026-09-27; local only). The consent form is the app's text word for word (§9). The revision fixed
  every mismatch this list carried:
  - *Consent form:* about 40 minutes, not 20 to 35 (twice); the Risks sentence on childhood
    vaccination as a sensitive topic; "Neon (a managed PostgreSQL service)"; access to "identifying
    data"; and the Procedures sentence naming the background questions (About you, §6.2).
  - *Request form 5A:* the interactive features are "filtering, sorting, line isolation", with no
    change indicator; the session's contents are stated.
  - *Request form 5B:* about 40 minutes; six multiple-choice questions per version on five kinds of
    chart; a one-sentence explanation; the survey after each version; ten background questions at
    the end; hover not logged. "Value retrieval" is gone.
  - *Request form 8C:* every recruitment message and posting says the study shows childhood
    vaccination data, as item 9 promises.
  - *Request form 9:* the same charts of one dataset in both versions, with controls under each
    chart by type, not "a time-series chart" with "explicit directional change indicators".
  - *Request form 12A:* the typed name and date, the drawn signature, the paper-copy box, and the
    downloadable copy (§9).
  - *Request form 15:* the signed consent is written to the database, in its own table with no
    participant ID, until it is exported; Neon's backups last days, so the three-year record is the
    Oxy Drive export; "a managed PostgreSQL service", not "PostSQL".
  - *Request form 17:* background answers under the participant ID only; the linking file holds
    email addresses and names, not age; "Other" text never quoted.
  - *Request form 18:* the deployed URL and `irb/questionnaire.pdf`, generated by
    `scripts/export_questionnaire.py` from the app's own screen code and re-exported 2026-09-26.
- **Left as they are in the 2026-09-26 forms** (not errors, but narrower than the app):
  - *Consent form:* the interactive version "displays directional (year-over-year) change
    indicators". The change appears only in the hover tooltip (`visual-spec.md` §7.1).
  - *Request form 5B and the consent form:* both describe the survey as Likert-scale ratings of
    clarity, ease of use, confidence, and cognitive load (the consent form) or mental effort (5B).
    Neither names the controls items (b1–b3) or the comparison questions (c1–c3, one open-ended) of
    §6.1. The questionnaire (item 18) shows every one.
  - *Request form 12A:* signing "with a mouse/trackpad". The pad also takes a finger on a
    touchscreen.
  - *Request form 17* promises less than §6.2: it does not carry the aggregate-only reporting of
    About you or the rule for groups under five.
- **HSRRC approved the study on 2026-10-12** (`irb/Oxy CS Senior Comps Approval Request Form.docx`
  and `… Informed Consent Form.docx`). The request form gives 2026-09-30 as its submission date
  (item 1). The points under "Left as they are" above were approved as written.
- **Fixed in the 2026-09-28 revision:** item 9's "WHO/UNICEG"; item 15's "the lasting records is
  the export"; item 5B now says five multiple-choice questions and one written description per
  version, the explanation after the multiple-choice answers, and names the window size among what
  is logged; both signatures re-dated 9/28. The consent form's Procedures still does not name the
  window size; adding it would change the consent text and its pinned hash.
- **Answer tiles overflow on narrow windows (found 2026-10-11, partly fixed 2026-10-12).** The
  tiles' text went from 17 px to 15 px (`visual-spec.md` §10), which fits every option at 1440 ×
  790 and 1536 × 864. At 1366 × 768 form B's Mozambique (B-T2's key) and Bangladesh still run past
  their tiles, clipping the radio button too; at 1280 × 720, a common laptop window at 150 %
  scaling, 108 of the 132 options do. Participants use their own computers.
  **Accepted as it is (Eduardo, 2026-10-13):** every participant works in a full-screen window
  (§8). A full screen is the display's own size, so a 1366 × 768 display still shows the overflow
  above. `window_size` records each participant's window, so who met it can be read from the data.
- **Fixed in the 2026-09-21 revision:** "randomized" is now "counterbalanced" in both forms; "hovers"
  and "so findings aren't platform specific" are gone from the request form; both forms now name
  Neon; the consent form now states the two-week withdrawal window.
- Continent aggregates have no 2024 data, so no item may turn on a continent's most recent year.
  No item uses a continent.
