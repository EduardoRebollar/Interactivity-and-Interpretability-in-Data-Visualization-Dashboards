# Study design

Source of truth for the protocol: research questions, conditions, tasks, measures, and scoring.
`docs/visual-spec.md` is the source of truth for what the charts look like. Change this document
before changing `src/tasks.py` or `src/flow.py`.

Status: **draft, 2026-09-15; revised 2026-09-21 to match the IRB submission; task set finalized
2026-09-22, then replaced 2026-09-23 by a redesigned task bank on five chart types, with a
crossing item added the same day; the largest-rise item dropped 2026-09-25 (§4); redesigned
2026-09-25 from the design handoff (`docs/design-handoff/`, `docs/study-redesign.md`): six options
per item, controls on every chart, a new survey, and About you, which moves to the end; built and
verified in headless Chrome 2026-09-26.** The consent text in §9 is the form submitted to
Occidental's HSRRC and must not be shown to a participant until approved.

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
| Line charts | image | View (as listed / by coverage), Show all, click a line to isolate it, legend click to hide or show, double-click to show only one, zoom and pan |
| Bar chart | image | Sort: A–Z, High → low, Low → high |
| Heatmap | image | Sort rows: Default, Lowest value, Average |
| Map | image | Highlight: fade every country not below a typed percentage |
| Every chart | — | Reset view: undo filtering, sorting, isolating and the highlight |

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
the static condition cannot see: the chips and the legend hide entities within the set, the sorts
reorder them, and the map's highlight fades countries within it.

This is deliberate. If interactive participants could pull in entities that static participants could
not, interactivity would be changing *what data is available* as well as *how it is worked with*, and
no observed difference could be attributed to interactivity alone.

At most 8 colour-coded series — lines plus the dashed World reference, or scatter dots — per
`docs/visual-spec.md` §6. The bar chart, the heatmap and the map are not limited by the palette: bars
are named on their axis, and rows and countries take the sequential scale.

## 4. Task set

**Replaced 2026-09-23.** The task bank of 2026-09-22 (a reference count, two trends, two crossings
and a gap item, all on line charts) was replaced by a bank Eduardo specified on 2026-09-23
(`task-bank-spec.md`, supplied with the request and not kept in this repository; every item it
specified is recorded below, as kept or as changed). All items use DTP3. Every value was verified against
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
| T1 | line, 8 countries | isolating lines: a click, a legend double-click, or the chips | tracing two lines through a tangle of crossings |
| T2 | bar | sorting the bars | ranking bars that stand in no order |
| T3 | scatter | hovering a dot; hiding dots with the chips | matching a dot to its legend entry |
| T4 | heatmap | hovering a cell; sorting rows by lowest value | telling dark shades apart |
| T5 | map | the highlight: countries below a typed percentage | sorting every country's colour against the key |
| T6 | line, 2 countries | hovering both lines where they meet | placing, by eye, the year two lines cross |

**Redesign, 2026-09-25.** Every chart now has country chips and Reset view. The heatmap gained a
row sort, and the map's range slider gave way to a typed threshold. The heatmap's Lowest value sort
answers T4 in one click, as the bar sort answers T2. Like the bar sort, it lowers the static cost
rather than making the item answerable, because T4's key already clears the acceptance rule.

Chart type here is **variety** — evidence that an effect holds across formats — not a per-type
claim. Each type carries one item per form, the line chart two, so per-chart-type differences
are reported descriptively and never tested (§7).

T2–T5 each read one set of values: a ranking, an extreme, a count. T6 was added the same day, at
Eduardo's request, as a **relational** item: its answer is a relation between two series, when one
overtakes the other. T1 (2026-09-27) is the one **interpretive** item: the participant describes two
series over the whole period and how they compare, in their own words.

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
so the floor for colour is doubled. On the sequential scale one point moves lightness by 0.73–0.86
L*, so 10 points is at least 7.3 L*.

| Item | The key must survive... |
|---|---|
| T1 two trends | Each shape the rubric names is large: the riser gains at least **25 points** and never drops more than **12** below a previous peak; the other line drops at least **25 points** from a peak and recovers at least **15** from its trough. The two cross **once**, by the T6 rule's 5-point test. No other line runs within **5 points** of a named line for **5 or more consecutive years**; for the falling line, counted from its last peak before the trough. |
| T2 rank | The key bar is at least **5 points** from the bars ranked just above and just below it. |
| T3 most improved | The key's improvement beats every other dot's by at least **5 points**, and no two dots sit within **4 points** of each other (12 px dots at 4 px a point: closer, and one hides the other). |
| T4 lowest cell | The lowest cell is at least **10 points** below the lowest cell of every other row. |
| T5 count | Every coloured country is at least **10 points** from the threshold. |
| T6 crossing | The point where the two lines **meet on the chart** sits at least **1 year inside** its answer band, a band spanning start − 0.5 to end + 0.5. One crossing only: the overtaker trails in every year before it and leads in every year after, by at least **5 points** somewhere on each side. The first year strictly above and the first year no longer below fall in the same band. No other line drawn within **5 points** of where the two meet. |

A bar, dot, cell or country with no reported value is refused outright: the chart would have nothing
to show exactly where the question looks. A crossing is judged only on years both lines report. An
item that fails any part is refused by `analysis/keys.py` with `KeyDerivationError`, so a fragile
item fails the test suite exactly as a wrong key does, including after a data refresh.
`tests/test_scoring.py` also runs each spec item that was changed on the real data and checks that
it is still refused.

### T1 — Two trends (line, isolation)

*Look at the lines for {country} and {country}. Describe how their coverage changed between 2000 and
2024, and how the two countries' trends were similar or different.*

Answered in writing, in one text box, with no separate justification: the description is the
reasoning (§5).

| | Form A | Form B |
|---|---|---|
| Named countries | India and Ukraine | Brazil and Uganda |
| The riser | India: 58% → 94%; never more than 6 below a previous peak | Uganda: 52% → 91%; never more than 5 below |
| The line that falls and recovers | Ukraine: 99% → **19%** (2016) → 88%; drop 80, recovery 69 | Brazil: 99% → **68%** (2021) → 91%; drop 31, recovery 23 |
| Crossing (5-point test) | once: India above from 2009, 5 points clear from 2010 | once: Uganda above from 2016, 5 points clear from 2017 |
| Gap in 2024 | India 6 points above | level |
| Longest run of another line within 5 points of a named one, as the rule counts it | 4 years: Indonesia and India, 2014–2017; Brazil and Ukraine, 2004–2007 | 4 years: Indonesia and Uganda, 2009–2012 |
| Other lines | Brazil, China, Ethiopia, Indonesia, Nigeria, Pakistan (no World line) | China, Ethiopia, Indonesia, Nepal, Nigeria, Pakistan (no World line) |
| Crossings of the two named lines with the other six | 30 | 26 |

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
by two coders, blind to condition (§7).

The difficulty is finding and following two lines through the tangle, then describing them. The
isolation control, the chips and the legend all cut through it.

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

### T2 — Third-highest bar (bar, sort)

*The bars show coverage in {year}. Which country had the third-highest coverage?*

| | Form A | Form B |
|---|---|---|
| Year | 2017 | 2024 |
| Bars | China 99, Vietnam 94, **India 89**, Brazil 83, Pakistan 75, Ethiopia 65, Nigeria 55 | Egypt 97, United States 94, **Colombia 89**, Cambodia 83, Indonesia 78, Ethiopia 73, Nigeria 67 |
| Gap to the bar above / below | 5 / 6 | 5 / 6 |
| Options | Brazil, China, Ethiopia, India, Nigeria, Vietnam | Cambodia, Colombia, Egypt, Ethiopia, Nigeria, United States |
| Key | **India** | **Colombia** |

The bars stand in alphabetical order, so the top three are not side by side. Sorting lines them up.
The forms are matched exactly: the key is 89 in both, 5 points below the bar above and 6 above the
bar below. Each form's options are the ranks 1, 2, 3, 4, 6 and 7 (Nigeria, the seventh, added
2026-09-25).

> **Re-tuned from the spec.** The spec's A-T2 (2015) had China 99, Bangladesh 98, Vietnam 97 and
> Brazil 96, and its B-T2 (2019) Egypt 95 against Colombia 94. Both keys were 1 point from a
> neighbour, which no one can rank by bar height. The new sets were found by search over the bank's
> countries, for the tightest gaps that clear 5 points.

### T3 — Most improved (scatter, hover)

*Each dot is an {African / Asian} country, placed by its coverage in 2000 (across) and in 2024 (up).
The dashed diagonal means no change. Which country improved the most — the dot furthest above the
diagonal?*

| | Form A | Form B |
|---|---|---|
| Dots, 2000 → 2024 | Burkina Faso 45 → 91, Chad 38 → 68, Ethiopia 30 → 73, Mali 43 → 82, **Niger 34 → 86**, Nigeria 29 → 67 | Bangladesh 82 → 97, Cambodia 59 → 83, **India 58 → 94**, Indonesia 75 → 78, Nepal 74 → 97, Pakistan 59 → 87 |
| Improvement, key vs runner-up | +52 vs +46 (Burkina Faso): 6 | +36 vs +28 (Pakistan): 8 |
| Closest two dots | 6.1 points (Ethiopia, Nigeria) | 4.0 points (Cambodia, Pakistan) |
| Options | Burkina Faso, Chad, Ethiopia, Mali, Niger, Nigeria | Bangladesh, Cambodia, India, Indonesia, Nepal, Pakistan |
| Key | **Niger** | **India** |

The dot is easy to find; the static cost is naming it, by matching its colour and shape to the
legend. Hover names it directly.

> **Changed from the spec.** A-T3 drops Angola (31 → 64) and DR Congo (30 → 65): their dots sat
> 1.4 points apart, and within 3 of Nigeria's, so one dot hid another. B-T3 drops Laos, so both forms
> show six dots, and keeps Afghanistan out as the spec warned: its +35 all but ties India's +36.
> Since 2026-09-25 both forms offer all six dots.

### T4 — Lowest cell (heatmap, hover and row sort)

*Rows are countries and columns are years. Darker cells mean lower coverage. Which country's row
contains the single lowest cell?* Columns: 2000, 2005, 2010, 2015, 2020, 2024.

| | Form A | Form B |
|---|---|---|
| Rows | Burkina Faso, Cambodia, Central African Republic, Chad, India, Indonesia, Mali, Pakistan | Afghanistan, Madagascar, Mali, Myanmar, Nepal, Niger, Pakistan, Uganda |
| Lowest cell | **Chad, 2005: 26%** | **Afghanistan, 2000: 24%** |
| Next row's lowest | Central African Republic, 37% | Niger, 34% |
| Margin | 11 | 10 |
| Options | Burkina Faso, Central African Republic, Chad, India, Mali, Pakistan | Afghanistan, Madagascar, Mali, Niger, Pakistan, Uganda |
| Key | **Chad** | **Afghanistan** |

No number is written in a cell. Static participants compare shades against the colour key; hover
gives the exact value, and the Lowest value row sort brings the key's row to the top. The sixth
option, added 2026-09-25, is each grid's sixth-lowest row: India (58) in A, Madagascar (57) in B.

> **Re-tuned from the spec.** The spec's A-T4 lowest cell (Chad, 26) was 3 points from Nigeria's
> (29), and its B-T4 (Afghanistan, 24) 5 points from Nigeria's — enough on a position axis, not in
> colour. Nigeria (29), Ethiopia (30) and Angola (31) bottom out within 10 points of both keys, Niger
> (34) within 10 of Chad's and Somalia (33) within 10 of Afghanistan's, so they left the grids. Form
> B also traded India and Indonesia for rows form A does not show, so the two grids share only Mali
> and Pakistan. The spec's keys, Chad and Afghanistan, stayed.

### T5 — Countries below 50% (map, highlight)

*The map colours {n} countries in sub-Saharan Africa by their coverage in {year}. How many of those
countries had coverage below 50%?*

| | Form A | Form B |
|---|---|---|
| Year | 2013 | 2007 |
| Countries coloured | 13 | 11 |
| Below 50% | Central African Republic 23, Chad 39, Nigeria 39 | Chad 29, Somalia 40 |
| Closest to the line | Chad and Nigeria, 11 points below | Somalia, 10 points below |
| Left uncoloured, within 10 points of 50% | Somalia 44, South Sudan 53, Angola 54, Ethiopia 59 | Nigeria 42, Angola 43, Central African Republic 48, Ethiopia 50, Niger 58; South Sudan has no 2007 value |
| Options | 0, 1, 2, 3, 4, 5 or more | same |
| Key | **3** | **2** |

The coloured countries are the spec's pool of large, easily seen countries, less those within 10
points of the line in that year. Every other country is plain grey land, and the prompt states how
many are coloured.

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

*{Country}'s coverage became higher than {other country}'s at some point. Roughly when did that
first happen?* Options, in calendar order: 2000-2003, 2004-2008, 2009-2012, 2013-2016, 2017-2020,
2021-2024. 2000-2003 was added 2026-09-25 so that every item offers six options. No key, margin or
adjacent band moves.

| | Form A | Form B |
|---|---|---|
| Lines | Central African Republic, Ethiopia | Mozambique, Pakistan |
| Before | Ethiopia trails from 2000, by up to 12 points (2004) | Pakistan trails from 2000, by up to 22 points (2008–2010) |
| The crossing | Ethiopia rises (46, 50) as the Central African Republic falls (51, 48) | Pakistan climbs to 84 against Mozambique's 85; Mozambique then falls to 71 |
| First year strictly above | **2007** | **2020** |
| Lines meet at | 2006.71 | 2019.10 |
| Inside the band by | 1.79 years | 1.40 years |
| After | Ethiopia leads every year to 2024, by up to 36 points | Pakistan leads every year to 2024, by up to 30 points |
| Key | **2004-2008** | **2017-2020** |

Bands, not years, because the static condition has no hover and an exact crossing year cannot be
read from the chart. **The key is the band containing the first year the overtaker is strictly
above** the other, having not been above the year before. The pairs were found by search over the
32 countries, which turned up five clean DTP3 crossings. The other three: China over Ukraine, whose
lines are both on A-T1's chart; Burkina Faso over Mozambique, only 1.17 years inside its band; and
Niger over Madagascar, which ties in 2010 and leads by 2 points the next year.

**Two lines, no World line.** In B-T6, World runs at 85–86 through 2014–2019, within 1 point of
Mozambique, and at 2019 all three lines sit within 2 points of each other, exactly where the question
looks. Pakistan also rises above World in 2021, a second crossing in the next band. The rule's last
clause refuses that chart. A-T6 could keep World, which runs about 29 points above its crossing, but
it is dropped there too, so both forms draw two lines.

**The affordance is hover.** Line charts use the closest-point tooltip, so hovering either line
near the crossing gives its exact value, and the tooltip's change from the year before shows which
line is rising. The line controls and zoom work here as on every line chart.

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
| Margin, form A | drop 80, rise 36 | 5 / 6 | 6 | 11 | 11 | 1.79 years |
| Margin, form B | drop 31, rise 39 | 5 / 6 | 8 | 10 | 10 | 1.40 years |
| Floor | drop 25, rise 25 | 5 | 5 | 10 | 10 | 1 year |

`tests/test_scoring.py` pins these margins, so a data refresh that moves one fails the suite rather
than quietly unbalancing the forms. Four known differences go to the pilot (§10):
- T1's falling line: Ukraine's collapse (80 points, 2008–2016) is far larger and faster than
  Brazil's decline (31 points over a decade). A-T1 is probably the easier form.
- B-T3's closest dots sit on the 4-point floor.
- The two T6 crossings are drawn differently. In A, two lines converge from opposite directions. In
  B, one line climbs to meet a level one, and the lines come within 1 point a year before they
  cross.

### Practice task (unscored)

*Practice (not scored). Look at Myanmar's line. Did coverage rise, fall, or stay level between 2015
and 2021?* Myanmar and World, DTP3, 2000–2024: a fall from 89% to 37%, unmissable. Shown in the
participant's first condition only, identical across forms, to teach the interface rather than the
concept. It is a line chart, the type with the most controls. The other types' controls are
described in the instructions and by the hint row under each chart in the interactive condition.

> **Changed 2026-09-23.** The practice was Ukraine's collapse between 2008 and 2016, and A-T1 now
> asks for Ukraine's lowest year: a first half of form A would have been answered by its own
> practice. No scored prompt names Brazil (`tests/test_tasks.py`).

> **Changed 2026-09-27.** B-T1 now names Brazil, and the practice asked whether Brazil fell between
> 2015 and 2021: exactly B-T1's story. The practice moved to Myanmar, which no scored prompt names
> and which is no longer on either T1 chart. It appears elsewhere only as an unasked heatmap row in
> B-T4, whose columns skip 2021.

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
  which also sets each line's and dot's colour and the order of bars and rows, with World always last.
- Years and year bands run in calendar order; counts in their natural order.
- Which options an item offers is the one free choice. It is used to spread the key: no position
  holds more than a third of the keys. Every multiple-choice item offers six options (2026-09-25).
  Since T1 became a written item (2026-09-27), ten keys are options, and they sit first: 1,
  second: 2, third: 3, fourth: 2, fifth: 2, sixth: 0. T6 has no free choice, since it offers all
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
| T1 | isolating lines (also chips, legend, sort, zoom) | yes — `line_isolate`, `filter_change` (`chips`, `legend`, `show-all`), `sort_change`, `view_change`, `view_reset` |
| T2 | sorting the bars | yes — `sort_change` |
| T3 | hover; hiding dots with the chips | the chips only — `filter_change` (`chips`) |
| T4 | hover; sorting rows by lowest value | the sort only — `sort_change` |
| T5 | the highlight | yes — `filter_change` with `control` `threshold` |
| T6 | hover | no (the line controls are, if used) |

For T3, T4 and T6, an interactive participant who answers correctly may or may not have hovered.
Analyses of affordance use are confined to T1, T2, T4's sort and T5; for T3, T4 and T6 a correct
interactive answer may rest on an unlogged hover, and the write-up says so.

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
interactive condition, a hint row under each chart restates what that chart can do.

First half, both versions. Heading "Instructions", then "Practice Question":

> Before the main set of questions, you'll try one practice question so you know what to expect. It
> won't be scored.
>
> You'll see a line chart of childhood vaccination coverage (the share of children who received a
> vaccine each year). Answer the question, then explain in one sentence how you decided.

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
> - On line charts you can also click a line, or double-click a name in the legend, to see one
>   country on its own; reorder the countries by coverage; and bring every line back with Show all.
> - The bar chart and the coloured grid can sort their bars or rows. The map can highlight only the
>   countries below a coverage you type.
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

and 4b's second, third and fourth bullets. Both end: "As before, you'll answer a question about
each chart and then say in one sentence how you decided. A break in a line means no value was
reported for those years. You may skip any question, and you'll be asked to confirm if you leave one
blank." Button: "Start the questions".

The colour-key sentences in 4a and 9a are additions to the handoff, made so the static wording names
the colour key the heatmap and map are read against, as the 2026-09-23 wording did.

**Practice complete** (first half only), heading "Practice Complete!":

> That was the practice question. It was not scored.
>
> The next six questions are the ones that count. The charts use the same version
> (static/interactive) that you experienced in the practice question.
>
> For each question, choose one answer, then write a short sentence response about your decision.
> After the sixth question, there are a few quick reflecting questions about your experience with
> this version.
>
> You may skip a question at any time. If you leave one unanswered, you will be asked to confirm.

Button: "Start the questions". **The break**, heading "Halfway There!": "Congratulations! The first
half of the study is complete! The next set will ask different questions using the other version
(static/interactive). Take a moment, then continue when you are ready." Button: "Continue".

The practice answer is recorded under `task_id` `P0` so that its timing is available, and **excluded
from scoring** (§7).

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

The consent screen shows the Occidental informed consent form submitted to HSRRC
(`irb/COMP 490 Consent Form.pdf`, local only), word for word. The app's copy lives in
`src/consent.py`; `tests/test_consent.py` pins it. **Until HSRRC approves it, the screen carries a
"pending approval" banner** (`consent.APPROVED = False`), and no participant may be run.

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
- **Pilot checks for the 2026-09-23 bank, as redesigned 2026-09-25:**
  - **Static accuracy on T2, T4 and T5.** Their margins sit at the floor on purpose (5, 10 and 10
    points), so they are the hardest static reads. Near-chance static accuracy (one in six) would
    mean the floor is too tight for that chart type.
  - **Form equivalence.** T1's falling line is Ukraine's 80-point collapse in form A and Brazil's
    31-point decline in form B (§4). B-T3's two closest dots sit exactly on the 4-point floor. The
    T6 crossings are drawn differently (§4).
  - **T1, the written item (2026-09-27).**
    - Its time, since it is the only item written in full.
    - Whether the rubric can be applied: κ per part, and how many descriptions the coders had to
      discuss.
    - Whether a part fails for nearly everyone in both conditions, which would point at the rubric
      rather than the reading.
  - **T6 against its adjacent-band secondary.** If the two scores differ much, static readers are
    placing the crossing a band off, and the band edges are doing the work.
  - **Whether the interactive affordances are found at all.** Especially the chips, the heatmap's
    row sort, the map's highlight and the bar sort, which the practice does not teach. The logs show
    all four (§7).
  - **Whether T4 sits at ceiling in the interactive condition** because the Lowest value row sort
    answers it in one click (§4).
- **Scrolling differs by condition on two items (accepted 2026-09-26).** On a window 790 px tall
  or less, the interactive scatter (T3) and map (T5) cards run past the fold, so interactive
  participants scroll to Submit there and static ones never do (`visual-spec.md` §10). Eduardo
  accepted it over tightening the layout. In the pilot, look at the interactive time on T3 and T5
  for it. Participants use their own computers (request form 5B), so the window height varies by
  participant; `window_size` records it (§8), and `tasks.csv` carries it as `window_height`, so
  the interactive T3 and T5 times can be split at 790 px.
- **Hover is not logged**, so affordance use cannot be observed for T3, T4 and T6 (§7).
- **Keyboard-only participants.** Hover, clicking a line and clicking the legend are mouse-only, so a
  keyboard-only participant in the interactive condition meets T3 and T6 with only the chips, and T4
  with only the row sort. The chips, the sorts, the highlight, Show all and Reset view all work from
  the keyboard (`docs/visual-spec.md` §8); a whole session was run from the keyboard alone on
  2026-09-26, consent (by the paper-copy box) to About you.
- ~~Whether the items can be answered without hover.~~ Resolved 2026-09-22 by the item acceptance
  rule, and kept for the 2026-09-23 bank, which was re-tuned to pass it (§4).
- **Session resume is not implemented.** The participant-ID screen no longer promises it; it asks
  for one sitting in one tab instead. See §8.
- ~~Whether the justification should be optional.~~ Resolved 2026-09-21: every question may be
  skipped (IRB form item 10), behind a confirmation popup. See §5.
- **IRB paperwork revised 2026-09-26** (`irb/COMP 490 Request Form.pdf` and `irb/COMP 490 Consent
  Form.pdf`, local only). The consent form is the app's text word for word (§9). The revision fixed
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
- **To fix in the request form before sending** (as saved 2026-09-26):
  - item 9: "WHO/UNICEG" for WHO/UNICEF;
  - item 15: "the lasting records is the export";
  - item 5B: "The participants answers six-multiple choice interpretation questions". Since
    2026-09-27 it should say five multiple-choice questions and one written description of two
    trends per version, and the one-sentence explanation follows the five multiple-choice questions
    only;
  - item 18: `irb/questionnaire.pdf` was re-exported after the T1 change (2026-09-27, 36 pages);
    attach that copy;
  - item 1: the initial submission date is still the placeholder "(Date sent to hsrrc@oxy.edu)";
  - the investigator signed 9/21/26 and the faculty supervisor 9/23/2026, both before this revision;
  - item 5B lists what the application logs, and since schema v10 (§8) it also logs the browser
    window's size once, which the list does not name. The consent form's Procedures lists what is
    logged too ("your task responses, response times, and interaction events"); adding the window
    size there would change the consent text and its pinned hash.
- **Fixed in the 2026-09-21 revision:** "randomized" is now "counterbalanced" in both forms; "hovers"
  and "so findings aren't platform specific" are gone from the request form; both forms now name
  Neon; the consent form now states the two-week withdrawal window.
- Continent aggregates have no 2024 data, so no item may turn on a continent's most recent year.
  No item uses a continent.
