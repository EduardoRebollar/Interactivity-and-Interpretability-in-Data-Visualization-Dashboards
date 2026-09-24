# Study design

Source of truth for the protocol: research questions, conditions, tasks, measures, and scoring.
`docs/visual-spec.md` is the source of truth for what the charts look like. Change this document
before changing `src/tasks.py` or `src/flow.py`.

Status: **draft, 2026-09-15; revised 2026-09-21 to match the IRB submission; task set finalized
2026-09-22, then replaced 2026-09-23 by a redesigned task bank on five chart types, with a
crossing item added the same day (§4).** The
consent text in §9 is the form submitted to Occidental's HSRRC and must not be shown to a participant
until approved.

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
carries one item per form, the line chart three (§4, §7).

## 2. Design

Within-subjects, 2 (condition: static / interactive) × 2 (form: A / B), fully counterbalanced.
Target n ≥ 25.

Each participant completes **7 scored tasks per condition, 14 in total**, plus one unscored practice
task. All seven make up the RQ1 accuracy score (§7). Expected duration 20–35 minutes, capped at one
hour (IRB form items 5B and 10).

### Conditions

Identical in every visual respect. The only difference is the Plotly render config
(`figures.graph_config`) and the controls rendered beside the chart (`docs/visual-spec.md` §7):

| | Static | Interactive |
|---|---|---|
| Hover tooltips | none | every chart |
| Line charts | image | filter, sort, line isolation, zoom and pan |
| Bar chart | image | sort the bars |
| Map | image | show only countries within a coverage range |

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
the static condition cannot see: filtering hides lines within the set, and the map's coverage range
fades countries within it.

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

### The design principle

Each item isolates **one interactive affordance** and pairs it with a chart type where the static
read is costly and that affordance lowers the cost:

| Item | Chart | Affordance | The static cost it lowers |
|---|---|---|---|
| T1 | line, 8 countries and World | isolating a line | tracing one line through a tangle of crossings |
| T2 | line, 5 countries and World | the tooltip's year-over-year change | judging one-year slopes by eye |
| T3 | bar | sorting the bars | ranking bars that stand in no order |
| T4 | scatter | hovering a dot | matching a dot to its legend entry |
| T5 | heatmap | hovering a cell | telling dark shades apart |
| T6 | map | the coverage range | sorting every country's colour against the key |
| T7 | line, 2 countries | hovering both lines where they meet | placing, by eye, the year two lines cross |

Chart type here is **variety** — evidence that an effect holds across formats — not a per-type
claim. Each type carries one item per form, the line chart three, so per-chart-type differences
are reported descriptively and never tested (§7).

T1–T6 each read one series or one set of values: a line's own shape, a ranking, an extreme. T7 was
added the same day, at Eduardo's request, as the one **relational** item: its answer is a relation
between two series, when one overtakes the other.

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
| T1 lowest point | Every year within **5 points** of the line's minimum could be taken for it, and any may be read **one year off**; every such reading must be nearer the key option than any other, with no ties. The minimum itself is unique. |
| T2 largest rise | The largest one-year rise beats every other one-year change by at least **5 points**. Either end of that segment may be taken for "the year" and read one year off; all four readings must be nearest the key option. |
| T3 rank | The key bar is at least **5 points** from the bars ranked just above and just below it. |
| T4 most improved | The key's improvement beats every other dot's by at least **5 points**, and no two dots sit within **4 points** of each other (12 px dots at 4 px a point: closer, and one hides the other). |
| T5 lowest cell | The lowest cell is at least **10 points** below the lowest cell of every other row. |
| T6 count | Every coloured country is at least **10 points** from the threshold. |
| T7 crossing | The point where the two lines **meet on the chart** sits at least **1 year inside** its answer band, a band spanning start − 0.5 to end + 0.5. One crossing only: the overtaker trails in every year before it and leads in every year after, by at least **5 points** somewhere on each side. The first year strictly above and the first year no longer below fall in the same band. No other line drawn within **5 points** of where the two meet. |

A bar, dot, cell or country with no reported value is refused outright: the chart would have nothing
to show exactly where the question looks. A crossing is judged only on years both lines report. An item that fails any part is refused by
`analysis/keys.py` with `KeyDerivationError`, so a fragile item fails the test suite exactly as a
wrong key does, including after a data refresh. `tests/test_scoring.py` also runs each spec item
that was changed on the real data and checks that it is still refused.

### T1 — Lowest point (line, isolation)

*Focus on {country}'s line. In which year was its coverage at its lowest point?*

| | Form A | Form B |
|---|---|---|
| Country | Ukraine | Myanmar |
| Lowest point | **2016** (19%) | **2021** (37%) |
| Within 5 points of it | 2014 and 2015 (23%) | none |
| Options | 2008, 2016, 2019, 2022, 2024 | 2009, 2013, 2017, 2021, 2024 |
| Next-lowest option | 2022 at 73%: 54 points above | 2024 at 71%: 34 points above |
| Other lines | Brazil, China, Ethiopia, India, Indonesia, Nigeria, Pakistan, World | same |
| Key | **2016** | **2021** |

The difficulty is finding and following the line, not reading it: both lows are far below every
other option. The other lines are the tangle the isolation control cuts through: Ukraine's line
crosses all eight of them, 25 times in all, and Myanmar's crosses seven of eight, 21 times.

> **A-T1's options changed from the spec.** The spec offered 2010, 2013, 2016, 2019 and 2022.
> Ukraine is at 23% in 2014 and 2015, too close to its 19% in 2016 to tell apart, and 2014 lies
> nearer the 2013 option than the 2016 one. A participant who took 2014 for the low point would
> have been scored wrong for reading the chart correctly. 2010 and 2013 were replaced by 2008 and
> 2024. B-T1 is as specified.

### T2 — Largest one-year rise (line, year-over-year change)

*Focus on {country}'s line. In which single year did its coverage rise the most over the year
before?*

| | Form A | Form B |
|---|---|---|
| Country | Pakistan | Bangladesh |
| Largest rise | **2011**, +11 | **2004**, +12 |
| Next-largest change | 2018, +5 | 2003, +4 |
| Margin | 6 | 8 |
| Options | 2005, 2011, 2015, 2018, 2021 | 2004, 2009, 2013, 2018, 2022 |
| Other lines | Ethiopia, India, Indonesia, Nigeria, World | Ethiopia, India, Nigeria, Vietnam, World |
| Key | **2011** | **2004** |

As specified. The tooltip states each point's change from the year before ("+11 pts vs 2010").
Without it, the steepest one-year segment has to be picked out by eye.

### T3 — Third-highest bar (bar, sort)

*The bars show coverage in {year}. Which country had the third-highest coverage?*

| | Form A | Form B |
|---|---|---|
| Year | 2017 | 2024 |
| Bars | China 99, Vietnam 94, **India 89**, Brazil 83, Pakistan 75, Ethiopia 65, Nigeria 55 | Egypt 97, United States 94, **Colombia 89**, Cambodia 83, Indonesia 78, Ethiopia 73, Nigeria 67 |
| Gap to the bar above / below | 5 / 6 | 5 / 6 |
| Options | Brazil, China, Ethiopia, India, Vietnam | Cambodia, Colombia, Egypt, Ethiopia, United States |
| Key | **India** | **Colombia** |

The bars stand in alphabetical order, so the top three are not side by side. Sorting lines them up.
The forms are matched exactly: the key is 89 in both, 5 points below the bar above and 6 above the
bar below. Each form's options are the ranks 1, 2, 3, 4 and 6.

> **Re-tuned from the spec.** The spec's A-T3 (2015) had China 99, Bangladesh 98, Vietnam 97 and
> Brazil 96, and its B-T3 (2019) Egypt 95 against Colombia 94. Both keys were 1 point from a
> neighbour, which no one can rank by bar height. The new sets were found by search over the bank's
> countries, for the tightest gaps that clear 5 points.

### T4 — Most improved (scatter, hover)

*Each dot is an {African / Asian} country, placed by its coverage in 2000 (across) and in 2024 (up).
The dashed diagonal means no change. Which country improved the most — the dot furthest above the
diagonal?*

| | Form A | Form B |
|---|---|---|
| Dots, 2000 → 2024 | Burkina Faso 45 → 91, Chad 38 → 68, Ethiopia 30 → 73, Mali 43 → 82, **Niger 34 → 86**, Nigeria 29 → 67 | Bangladesh 82 → 97, Cambodia 59 → 83, **India 58 → 94**, Indonesia 75 → 78, Nepal 74 → 97, Pakistan 59 → 87 |
| Improvement, key vs runner-up | +52 vs +46 (Burkina Faso): 6 | +36 vs +28 (Pakistan): 8 |
| Closest two dots | 6.1 points (Ethiopia, Nigeria) | 4.0 points (Cambodia, Pakistan) |
| Options | Burkina Faso, Chad, Ethiopia, Mali, Niger | Bangladesh, Cambodia, India, Nepal, Pakistan |
| Key | **Niger** | **India** |

The dot is easy to find; the static cost is naming it, by matching its colour and shape to the
legend. Hover names it directly.

> **Changed from the spec.** A-T4 drops Angola (31 → 64) and DR Congo (30 → 65): their dots sat
> 1.4 points apart, and within 3 of Nigeria's, so one dot hid another. B-T4 drops Laos, so both forms
> show six dots, and keeps Afghanistan out as the spec warned: its +35 all but ties India's +36. A-T4
> offers Mali in place of Nigeria (+39 and +38), which moves the key off the fourth option.

### T5 — Lowest cell (heatmap, hover)

*Rows are countries and columns are years. Darker cells mean lower coverage. Which country's row
contains the single lowest cell?* Columns: 2000, 2005, 2010, 2015, 2020, 2024.

| | Form A | Form B |
|---|---|---|
| Rows | Burkina Faso, Cambodia, Central African Republic, Chad, India, Indonesia, Mali, Pakistan | Afghanistan, Madagascar, Mali, Myanmar, Nepal, Niger, Pakistan, Uganda |
| Lowest cell | **Chad, 2005: 26%** | **Afghanistan, 2000: 24%** |
| Next row's lowest | Central African Republic, 37% | Niger, 34% |
| Margin | 11 | 10 |
| Options | Burkina Faso, Central African Republic, Chad, Mali, Pakistan | Afghanistan, Mali, Niger, Pakistan, Uganda |
| Key | **Chad** | **Afghanistan** |

No number is written in a cell. Static participants compare shades against the colour key; hover
gives the exact value.

> **Re-tuned from the spec.** The spec's A-T5 lowest cell (Chad, 26) was 3 points from Nigeria's
> (29), and its B-T5 (Afghanistan, 24) 5 points from Nigeria's — enough on a position axis, not in
> colour. Nigeria (29), Ethiopia (30) and Angola (31) bottom out within 10 points of both keys, Niger
> (34) within 10 of Chad's and Somalia (33) within 10 of Afghanistan's, so they left the grids. Form
> B also traded India and Indonesia for rows form A does not show, so the two grids share only Mali
> and Pakistan. The spec's keys, Chad and Afghanistan, stayed.

### T6 — Countries below 50% (map, coverage range)

*The map colours {n} countries in sub-Saharan Africa by their coverage in {year}. How many of those
countries had coverage below 50%?*

| | Form A | Form B |
|---|---|---|
| Year | 2013 | 2007 |
| Countries coloured | 13 | 11 |
| Below 50% | Central African Republic 23, Chad 39, Nigeria 39 | Chad 29, Somalia 40 |
| Closest to the line | Chad and Nigeria, 11 points below | Somalia, 10 points below |
| Left uncoloured, within 10 points of 50% | Somalia 44, South Sudan 53, Angola 54, Ethiopia 59 | Nigeria 42, Angola 43, Central African Republic 48, Ethiopia 50, Niger 58; South Sudan has no 2007 value |
| Options | 0, 1, 2, 3, 4 or more | same |
| Key | **3** | **2** |

The coloured countries are the spec's pool of large, easily seen countries, less those within 10
points of the line in that year. Every other country is plain grey land, and the prompt states how
many are coloured.

> **Re-tuned from the spec.** The spec's A-T6 (2013, all 17 countries) had South Sudan at 53 and
> Somalia at 44, and its B-T6 (2018) had Chad at 47 and Somalia at 53, all 3 points from the line.
> No single pool kept every country 10 points clear in two years with different counts, so each form
> has its own. B-T6 moved to 2007: 2018 left only one country clear below the line.

### T7 — Crossing (line, hover)

*{Country}'s coverage became higher than {other country}'s at some point. Roughly when did that
first happen?* Options, in calendar order: 2004-2008, 2009-2012, 2013-2016, 2017-2020, 2021-2024.

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

**Two lines, no World line.** In B-T7, World runs at 85–86 through 2014–2019, within 1 point of
Mozambique, and at 2019 all three lines sit within 2 points of each other, exactly where the question
looks. Pakistan also rises above World in 2021, a second crossing in the next band. The rule's last
clause refuses that chart. A-T7 could keep World, which runs about 29 points above its crossing, but
it is dropped there too, so both forms draw two lines.

**The affordance is hover.** Line charts use the closest-point tooltip, so hovering either line
near the crossing gives its exact value, and the tooltip's change from the year before shows which
line is rising. The line controls and zoom work here as on every line chart.

> **Adjacent-band credit, pre-registered as a secondary for T7** (§7). A reader who puts the
> crossing a year late or early lands in the key band in both forms, since the lines meet more than
> a year inside it. The credit is for one step further: the key band, or the band containing the
> key year ± 1. B-T7's key year, 2020, closes its band, so a reading of 2021 earns it. A-T7's,
> 2007, is mid-band, so there the secondary is the strict score. It was
> pre-registered for the crossing items of the 2026-09-22 bank, dropped with them, and is restored
> with this one.

### Matching the forms

| | T1 | T2 | T3 | T4 | T5 | T6 | T7 |
|---|---|---|---|---|---|---|---|
| Margin, form A | 54 | 6 | 5 / 6 | 6 | 11 | 11 | 1.79 years |
| Margin, form B | 34 | 8 | 5 / 6 | 8 | 10 | 10 | 1.40 years |
| Floor | 5 | 5 | 5 | 5 | 10 | 10 | 1 year |

`tests/test_scoring.py` pins these margins, so a data refresh that moves one fails the suite rather
than quietly unbalancing the forms. Three known differences go to the pilot (§10):
- T1's low point is a three-year trough in A and a one-year dip in B.
- B-T4's closest dots sit on the 4-point floor.
- The two T7 crossings are drawn differently. In A, two lines converge from opposite directions. In
  B, one line climbs to meet a level one, and the lines come within 1 point a year before they
  cross.

### Practice task (unscored)

*Practice (not scored). Look at Brazil's line. Did coverage rise, fall, or stay level between 2015
and 2021?* Brazil and World, DTP3, 2000–2024: a fall from 96% to 68%, unmissable. Shown in the
participant's first condition only, identical across forms, to teach the interface rather than the
concept. It is a line chart, the one type with every control. The other types' controls are
described in the instructions and by a line of text above each chart in the interactive condition.

> **Changed 2026-09-23.** The practice was Ukraine's collapse between 2008 and 2016, and A-T1 now
> asks for Ukraine's lowest year: a first half of form A would have been answered by its own
> practice. No scored prompt names Brazil (`tests/test_tasks.py`).

### Revision 2026-09-23, in brief

- **Six new item types** on five chart types, one affordance each (above), replacing the reference,
  trend, crossing and gap items.
- **T7, a crossing item, added the same day**, so the bank has one item whose answer is a relation
  between two series. It follows the old bank's crossing rule, tightened (above).
- **Kept from the spec as written:** A-T2, B-T1, B-T2, and every item's affordance, chart type and
  question.
- **Changed to pass the acceptance rule:**
  - A-T1's options;
  - both T3 bar sets;
  - both T5 grids;
  - both T6 pools and B-T6's year;
  - A-T4's dots.
- **Changed for balance:** B-T4 drops Laos, so both scatters have six dots; option subsets were chosen
  so no answer position holds more than three keys (§5).
- **Gone with the old bank:** T6's separate reporting. No item asks about missing data now; the gap
  caption stays for a data refresh (`docs/visual-spec.md` §3). The adjacent-band secondary went too,
  and came back with T7 (§7).

The 2026-09-22 bank, its audit and its acceptance rule for crossings and gaps are in the git history.

## 5. Answer format

Every scored task collects two things:

1. **A multiple-choice answer** — scored objectively, no rater judgement.
2. **A short free-text justification** ("In one sentence, how did you decide?") — the material for
   RQ2.

**Both may be skipped (2026-09-21).** The IRB form (item 10) and the consent form promise that a
participant may skip any question. Pressing Submit with either part empty opens a confirmation popup
naming what is unanswered; confirming moves on, cancelling returns to the task. A skipped part is
recorded as `null`, and `answer_submit` carries `skipped` — the list of parts left empty — so a skip
is explicit in the data rather than inferred from a blank. The practice item works the same way. The
justification is not length-constrained. Correct answers are **never** stored in
`src/tasks.py`: that module ships to the browser, where an answer key would be readable in the page
source. Scoring happens offline against §7.

**Option order (2026-09-22).** The position of an option must carry no information about the answer.
- Where the options are countries, they are listed **alphabetically**. So are the chart's entities,
  which also sets each line's and dot's colour and the order of bars and rows, with World always last.
- Years and year bands run in calendar order; counts in their natural order.
- Which options an item offers is the one free choice. It is used to spread the key: no position
  holds more than four of the fourteen keys (first: 3, second: 3, third: 3, fourth: 4, fifth: 1).
  T7 has no free choice, since it offers all five bands; its keys sit first and fourth.
  `tests/test_scoring.py` fails if any position holds more than a third.

Before this rule, the country options were sorted by how much each changed, which put the correct
answer first in 7 of the then 12 items.

## 6. Surveys

### 6.1 Post-condition survey

After **each** condition — the consent form says so ("For each version … followed by a brief survey
with Likert-scale ratings of clarity, ease of use, confidence, and cognitive load"), and a single
survey after both would give one rating that cannot be split between the conditions it compares.

Cognitive load is the Paas mental-effort item (RQ3):

> **In solving the preceding tasks, I invested:**
> 1 — very, very low mental effort … 9 — very, very high mental effort

One item, not NASA-TLX: with only two conditions per participant the extra subscales add
administration time and fatigue without much resolution. Logged as `load_rating` with
`{"scale": "paas", "value": 1-9}`.

Clarity, ease of use and confidence are three 7-point agreement items (1 = strongly disagree,
4 = neither agree nor disagree, 7 = strongly agree), chosen 2026-09-21 over 5-point for resolution,
since each condition yields only one rating per participant:

| Key | Statement |
|---|---|
| `clarity` | The charts in this part made the information clear. |
| `ease_of_use` | The charts in this part were easy to use. |
| `confidence` | I am confident in my answers in this part. |

Logged as `survey_rating` with `{"scale": "likert7", "clarity": …, "ease_of_use": …,
"confidence": …}`. Every item may be skipped, behind the same confirmation popup as a task (§5); a
skipped rating is `null`.

### 6.2 Demographics

Once, after the participant ID and before the instructions (chosen 2026-09-21: simplest, and nothing
is lost when a participant stops part-way). Broad categories only, per IRB form item 17, so no answer
can re-identify anyone. Every item may be skipped, behind the confirmation popup, and every item also
offers "Prefer not to say".

| Key | Question | Options |
|---|---|---|
| `age_range` | What is your age range? | 18–24; 25–34; 35–44; 45–54; 55–64; 65 or older |
| `field` | What is your main field of study or work? | Arts and humanities; Social sciences; Natural sciences; Mathematics, statistics or computer science; Engineering; Health or medicine; Business or economics; Education; Other |
| `chart_frequency` | How often do you read charts or graphs, for example in the news, at work, or in class? | Never; Less than once a month; A few times a month; A few times a week; Daily |
| `dashboard_familiarity` | How familiar are you with interactive data dashboards, such as Tableau, Power BI, or online COVID-19 trackers? | Not at all familiar; Slightly familiar; Moderately familiar; Very familiar; Extremely familiar |

Logged as a `demographics` event, once per participant, in condition 1's log session right after
`consent` — it is held in session state until then, for the same reason consent is (§9).

## 7. Scoring

This section is a **pre-registration**. Every rule here is fixed before collection begins, because
choosing an exclusion rule after seeing the data is a methodological problem however reasonable the
rule is. `analysis/` implements it; nothing is decided at analysis time.

**Accuracy (RQ1).** Binary per task from the multiple choice. Primary outcome: proportion correct per
participant per condition, **over T1–T7** (revised 2026-09-23: T6 was reported separately while it
was a gap item whose answer was printed on screen; no item's answer is on screen now; T7 was added
the same day).

**A skipped answer scores as incorrect** in the primary analysis (ruled 2026-09-21), so every
participant is scored out of seven per condition. Dropping skips instead would let a condition that
provokes more skipping look more accurate than it is. *Secondary, pre-registered:* proportion correct
among answered items only, skips excluded. The number of skips per condition is reported alongside
both.

*Secondary, pre-registered for the crossing item (T7):* accuracy on T7 recomputed with adjacent-band
credit — the key band, or the band containing the key year ± 1 (§4). Reported alongside the strict
score, never in place of it, and never folded into the T1–T7 proportion.

Scored by exact string equality against a key **derived from `data/deploy/coverage.csv`** by the
rule each item states, and cross-checked against the tables in §4 (`analysis/keys.py`). A derived key
that disagrees with §4 fails the test suite. This exists because §4's prose key for an earlier item
was wrong — it said 2, the data said 1 — and nothing would have caught it.

**By item and chart type — descriptive only (added 2026-09-23).** Proportion correct and median time
per item, chart type and condition (`analysis/report.by_item`). Each item pairs one chart type with
one affordance (§4), so this is where a difference can be traced to an affordance. But each type
carries one item per form, the line chart three, so these are **never tested** and never reported
as per-chart-type effects.

**Which affordance a participant used** is known only where it is logged. Hovers are not logged
(decided 2026-09-21), so:

| Item | Affordance | Logged? |
|---|---|---|
| T1 | isolating a line (also filter, sort, zoom) | yes — `line_isolate`, `filter_change`, `sort_change`, `view_change` |
| T2 | the tooltip's change from the year before | no (the line controls are, if used) |
| T3 | sorting the bars | yes — `sort_change` |
| T4, T5 | hover | no |
| T6 | the coverage range | yes — `filter_change` with `control` `coverage-band` or `band-reset` |
| T7 | hover | no (the line controls are, if used) |

For T2, T4, T5 and T7, an interactive participant who answers correctly may or may not have hovered.
Analyses of affordance use are confined to T1, T3 and T6, and the write-up says so.

**Reasoning depth (RQ2).** Each justification coded on three binary features:

| Code | Present when the participant… |
|---|---|
| `cites_values` | refers to specific levels or magnitudes, however approximate |
| `compares_series` | refers to more than one country, not just the answer |
| `notes_uncertainty` | flags missing data, an estimate, or ambiguity |

Depth score 0–3. Code blind to condition. A skipped justification has no text to code; it is
absent from the coding sheet and missing, not zero, in the depth analysis. A second coder scores 20% of the justifications;
report Cohen's κ.

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
participant × condition. The three Likert items (§6.1) are reported descriptively per condition.

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
| `incomplete_session` | The participant did not produce **two** log sessions each carrying a `session_end` and seven scored answers — a skipped item still counts, since a skip is a response rather than an abandoned session. Stated this way because `session_end` is written per *condition*, not once at the end of the study, so "reached `complete`" needed a precise test. |
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

`consent → participant ID → demographics → instructions → practice → 7 tasks → survey → break →
instructions → 7 tasks → survey → complete`

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

**What the instructions say (revised 2026-09-23).** Both versions name the five kinds of chart. The
interactive version says that hovering over any line, bar, dot, cell or country shows its exact
value, and on a line chart its change from the year before. It also names the controls: filter,
sort and isolate on line charts, sort on the bar chart, a coverage range on the map. The static
version says the charts are images, to be read against the gridlines or the colour key. In the
interactive condition, a line of text above each chart restates what that chart can do.

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
> participant would "continue where the study left off". It now reads: *"Enter the ID you were
> given. Please complete the study in one sitting, in this tab — closing it ends your session."*
> Resume itself is still not implemented, so treat a participant with more than two log sessions as
> needing manual inspection before analysis — the `incomplete_session` rule in §7 counts sessions and
> would otherwise be misled.

Each condition is one log session, opened at its instructions and closed after its load rating, so
both halves produce a complete `session_start … session_end` record.

**Timing integrity.** Task duration is the difference between two `performance.now()` stamps taken in
the participant's browser. That clock resets to zero on a page reload, which would otherwise yield a
plausible but wrong duration — an undercount measured from the reload, indistinguishable from a fast
answer. Each stamp therefore carries `performance.timeOrigin`, and a duration whose two stamps come
from different origins is recorded as **absent and flagged** (`duration_ms` null,
`duration_invalid: "clock_reset"`) rather than as a number. This follows the same principle as the
coverage data: a missing value is missing, never silently filled. Those rows keep their accuracy and
leave time-on-task analysis (§7).

**One answer per task.** Submit is disabled in the browser the moment it is pressed, and re-enabled
if the step is refused (an unanswered question) or if no response arrives within 15 seconds, so a
participant is never left with a dead button. This is the guard that matters: two rapid clicks send
two requests that both carry the same pre-click session state, so the server cannot tell them apart.
Behind it, the app refuses an answer for a task already recorded in the session, and the database
refuses a second `answer_submit` for the same session and task through a unique index. Without these
a double-click writes a duplicate answer and a duplicate `task_end`; it does not skip an item, since
both requests advance from the same starting point. The 15-second re-enable does nothing if the
button has left the page (2026-09-23): after the last task the survey is on screen, and
re-enabling a Submit that no longer existed made the page throw an error in every session.

## 9. Consent

The consent screen shows the Occidental informed consent form submitted to HSRRC
(`irb/COMP 490 Consent Form.pdf`, local only), word for word. The app's copy lives in
`src/consent.py`; `tests/test_consent.py` pins it. **Until HSRRC approves it, the screen carries a
"pending approval" banner** (`consent.APPROVED = False`), and no participant may be run.

### How consent is given

IRB form item 12A: the participant types their **printed name** and the **date**, **signs**, and
presses **"I agree to participate"**. The signature is drawn with a mouse, trackpad or finger on a
signature pad. A participant who cannot or prefers not to draw one signs the paper copy the
researcher brings instead, and ticks "I have signed a paper copy of this form with the researcher".
"I do not agree" is always available (item 12B). The app refuses to go on without a name, a date, and
either a drawn signature or the paper box ticked.

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
responses will have been merged into the de-identified dataset and can no longer be pulled out". The final screen tells them so, shows their participant ID, and gives the
researcher's email.

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
- **Pilot checks for the 2026-09-23 bank:**
  - **Static accuracy on T3, T5 and T6.** Their margins sit at the floor on purpose (5, 10 and 10
    points), so they are the hardest static reads. Near-chance static accuracy (one in five) would
    mean the floor is too tight for that chart type.
  - **Form equivalence.** T1's low point is a three-year trough in form A and a one-year dip in form
    B. B-T4's two closest dots sit exactly on the 4-point floor. The T7 crossings are drawn
    differently (§4).
  - **T7 against its adjacent-band secondary.** If the two scores differ much, static readers are
    placing the crossing a band off, and the band edges are doing the work.
  - **Whether the interactive affordances are found at all.** Especially the map's coverage range
    and the bar sort, which the practice does not teach. The logs show both (§7).
- **Hover is not logged**, so affordance use cannot be observed for T2, T4, T5 and T7 (§7).
- **Keyboard-only participants.** Hover is mouse-only, so a keyboard-only participant in the
  interactive condition meets T4, T5 and T7 with no affordance at all. The bar sort and the map's range
  work from the keyboard (`docs/visual-spec.md` §8).
- ~~Whether the items can be answered without hover.~~ Resolved 2026-09-22 by the item acceptance
  rule, and kept for the 2026-09-23 bank, which was re-tuned to pass it (§4).
- **Session resume is not implemented.** The participant-ID screen no longer promises it; it asks
  for one sitting in one tab instead. See §8.
- ~~Whether the justification should be optional.~~ Resolved 2026-09-21: every question may be
  skipped (IRB form item 10), behind a confirmation popup. See §5.
- **IRB paperwork wording to fix before submission.** The app follows this document; these lines in
  the IRB documents (`irb/COMP 490 Request Form.pdf` and `irb/COMP 490 Consent Form.pdf`, revised
  2026-09-21) still describe it inaccurately:
  - *Request form 9:* "The static version presents a time-series chart of the study dataset". Since
    2026-09-23 each version shows five kinds of chart of the one dataset: line charts, a bar chart,
    a scatter plot, a heatmap and a map. Both versions still share every visual choice. The consent
    form's "two versions of the same time-series data dashboard" remains true.
  - *Request form 9 and the consent form:* the interactive version "allows filtering, sorting, and
    line isolation". Still true; it now also sorts the bar chart and filters the map by a coverage
    range, which the form's "filtering, sorting" covers.
  - *Both forms:* "explicit directional (year-over-year) change indicators". Year-over-year change
    appears only in the hover tooltip (`visual-spec.md` §7.1).
  - *Request form 5B:* "value retrieval" tasks. No item may ask for an exact value (§2).
  - *Request form 18* is blank, and it asks for the survey's URL and a PDF copy of it. The PDF is
    `irb/questionnaire.pdf`, generated by `scripts/export_questionnaire.py` from the app's own screen
    code. Regenerated for the new bank on 2026-09-23; attach that copy. The URL is the deployed
    Vercel address.
  - *Request form 15:* "no personal identifying information is present or ever written into the
    database". **Not true of the signed consent.** The typed name and drawn signature are written to
    Neon's `consent_records` table (§9), kept separate from the study data and deleted from Neon once
    exported to the Oxy Drive. Either the form must say so, or the consent record must change.
  - *Request form 15:* "All records and backups will be available for at least three years". Neon's
    automatic backups are kept for days, not years, so the three-year copy has to be the export on
    the Oxy Drive. Deleted rows also survive in Neon's backups until that window passes.
  - *Request form 15:* "managed by PostSQL" is a typo for PostgreSQL. Both forms also say "Neon
    (managed by PostgreSQL)", but Neon is a managed PostgreSQL service, not managed by it.
- **Fixed in the 2026-09-21 revision:** "randomized" is now "counterbalanced" in both forms; "hovers"
  and "so findings aren't platform specific" are gone from the request form; both forms now name
  Neon; the consent form now states the two-week withdrawal window.
- Continent aggregates have no 2024 data, so no item may turn on a continent's most recent year.
  No item uses a continent.
