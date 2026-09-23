# Study design

Source of truth for the protocol: research questions, conditions, tasks, measures, and scoring.
`docs/visual-spec.md` is the source of truth for what the charts look like. Change this document
before changing `src/tasks.py` or `src/flow.py`.

Status: **draft, 2026-09-15; revised 2026-09-21 to match the IRB submission; task set finalized
2026-09-22 (§4).** The consent text in
§9 is the form submitted to Occidental's HSRRC and must not be shown to a participant until approved.

**The IRB approval request form outranks this document** (`irb/`, local only — see CLAUDE.md). Where
the two disagree, this document is changed to match, or the disagreement is listed in §10 so the IRB
paperwork can be amended before submission.

---

## 1. Research questions

**RQ1 (accuracy).** Does interactivity improve the accuracy of interpretations of time-series
coverage data, relative to a visually identical static chart?

**RQ2 (reasoning depth).** Does interactivity change *how* people reason — the evidence they cite and
the number of series they bring to bear — independently of whether they answer correctly?

**RQ3 (cognitive load).** Does interactivity primarily reduce perceived mental effort rather than
improving accuracy?

RQ3 matters because a null result on RQ1 with a reliable effect on RQ3 is still a finding: it would
suggest interactivity makes interpretation feel easier without making it better.

**Out of scope.** Cross-platform generalisation. The second platform was cut (see CLAUDE.md);
write-ups must not claim platform independence.

## 2. Design

Within-subjects, 2 (condition: static / interactive) × 2 (form: A / B), fully counterbalanced.
Target n ≥ 25.

Each participant completes **6 scored tasks per condition, 12 in total**, plus one unscored practice
task. Five of the six (T1–T5) make up the RQ1 accuracy score; T6, the gap item, is scored and
reported separately (§4, §7). Expected duration 20–35 minutes, capped at one hour (IRB form items 5B
and 10).

### Conditions

Identical in every visual respect. The only difference is the Plotly render config
(`figures.graph_config`):

| | Static | Interactive |
|---|---|---|
| Hover tooltips | none | yes |
| Zoom / pan / modebar | none | yes |
| Filter, sort, line isolation | none | yes |

**Static participants cannot read exact values.** They estimate against gridlines. No task may
therefore ask for a specific number — such an item would measure whether hover exists, not
interpretation. Every item below targets direction, magnitude comparison, ordering, or missingness.

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
mimicking an effect of interactivity. Forms A and B are isomorphic — same task types, same order,
matched effect sizes — over different data.

## 3. The entity set

Each task shows **the same fixed set of entities in both conditions.** Filtering in the interactive
condition hides and reveals within that set only.

This is deliberate. If interactive participants could pull in entities that static participants could
not, interactivity would be changing *what data is available* as well as *how it is worked with*, and
no observed difference could be attributed to interactivity alone.

At most 5 coloured series plus the dashed World reference, per `docs/visual-spec.md` §6.

## 4. Task set

All values verified against `data/deploy/coverage.csv`. All items use DTP3 except the gap items
(HepB3) and A-T4 (Polio3; see T4). Every item passes the acceptance rule below, which
`analysis/keys.py` enforces when it derives the key.

**Finalized 2026-09-22**, after an audit of every item against the data and the chart as drawn. What
changed, and why, is recorded at each item and summarised at the end of this section.

### Item acceptance rule (2026-09-22)

Section 2 forbids items that ask for an exact value, because static participants cannot read one. The
audit found items that asked for no number and still turned on one. An answer that flips when a year
is read one off, or when two lines 2 points apart must be told apart, measures whether hover exists
just as surely. So every key must survive the reading errors a participant without hover makes. On
the chart, 1 point is 4 px, a marker is 10 px across, and x gridlines fall every 5 years.

| Item type | The key must survive... |
|---|---|
| T1 reference count | Every country at least **5 points** from World, and every two countries at least 5 points apart, in the asked year **and the years either side**, with the same count in all three. |
| T2, T3 trends | Either end of the window read **one year off**, in any combination: the same winner. The nominal margin stays at least 5 points. |
| T4, T5 crossings | The point where the two lines **meet on the chart** sits at least **1 year inside** its answer band. A band spans start − 0.5 to end + 0.5. |
| T6 gaps | The gap series is **not hidden**. It may come within 4 points of another shown line in no more than half its reported years. |

A year with an unreported value is skipped, since there is no point there to misread. An item that
fails is refused by `analysis/keys.py` with `KeyDerivationError`. A fragile item therefore fails the
test suite exactly as a wrong key does, including after a data refresh.

### T1 — Reference comparison (warm-up)

*The dashed black line is the world average. In {year}, how many of the countries shown were above
it?*

| | Form A | Form B |
|---|---|---|
| Year | 2005 (World 77%) | 2015 (World 85%) |
| Entities | China, Ethiopia, India, Indonesia, Nigeria, World | Ethiopia, Nigeria, Pakistan, Ukraine, United Kingdom, World |
| Above | China 87 (+10) | United Kingdom 95 (+10) |
| Closest call, year ± 1 | Indonesia, 5 below (72 vs 77) | United Kingdom, 8 above in 2016 |
| Correct | **1** | **1** |

The forms are matched: in each, exactly one country is above the line, by 10 points, and every other
line is well clear. No country is above the line in both forms, and both years sit on an x-axis
gridline.

> **Replaced 2026-09-22.** The previous T1 asked about 2010 (A) and 2020 (B), with one entity set for
> both forms. Its answer turned on 2-point calls: Indonesia 81 vs World 83 in 2010, and India 85 vs 83
> in 2020. Lines that close draw overlapping markers. Both forms also showed the same chart. The
> 2026-09-15 correction to that item's key (transcribed as 2; the data said 1) is in the git
> history.

### T2 — Trend, decline

*Between {y1} and {y2}, which country's coverage fell the most?*

| | Form A | Form B |
|---|---|---|
| Window | 2015 → 2021 | 2010 → 2015 |
| Correct | **Brazil** (96 → 68, −28pp) | **Ukraine** (52 → 23, −29pp) |
| Nearest distractor | Indonesia (84 → 67, −17pp) | Nigeria (56 → 42, −14pp) |
| Entities | Brazil, India, Indonesia, Nigeria, United States, World | Brazil, India, Nigeria, Pakistan, Ukraine, World |

The forms are matched: −28 vs −17 in A, against −29 vs −14 in B. Both keep their winner under every
one-year misreading.

> **B changed 2026-09-22.** B's window ended in 2014. Ukraine was 76 in 2013 and 23 in 2014, so a
> participant who read the end year one early got Nigeria. Ending at 2015 removes that dependence:
> 2015 is a gridline, and Ukraine is still at the bottom of its trough there.

### T3 — Trend, growth

*Between {y1} and {y2}, which country's coverage rose the most?*

| | Form A | Form B |
|---|---|---|
| Window | 2000 → 2012 | 2013 → 2024 |
| Correct | **Ethiopia** (30 → 61, +31pp) | **Nigeria** (39 → 67, +28pp) |
| Nearest distractor | India (58 → 82, +24pp) | Pakistan (65 → 87, +22pp) |
| Entities | Brazil, China, Ethiopia, India, Indonesia, World | Ethiopia, India, Indonesia, Nigeria, Pakistan, World |

The forms are matched: +31 vs +24 (margin 7) against +28 vs +22 (margin 6). Each window begins or
ends at an edge of the chart.

> **B changed 2026-09-22.** B's window began in 2012, which is the year of a one-year dip in
> Nigeria's line (53 in 2011, 36 in 2012). Reading the start one year early made Pakistan the answer.
> The wording also changed, from "improved the most" to "coverage rose the most", to parallel T2.

### T4 — Crossing, large

*{X}'s coverage became higher than {Y}'s at some point. Roughly when did that first happen?*

| | Form A | Form B |
|---|---|---|
| Pair | India over Brazil, **Polio3** | China over Ukraine |
| First year above | **2016** (India 86, Brazil 72) | **2008** (China 97, Ukraine 90) |
| Lines meet | 2015.46 | 2007.42 |
| Key | `2013-2016` | `2004-2008` |
| Entities | Brazil, India, World | China, Ukraine, World |

The forms are matched. In both, the lines meet about a year before the end of their band (1.04 and
1.08 years inside it), and the overtaker stays above for the rest of the chart.

> **Why A-T4 is Polio3 (2026-09-22).** On DTP3, India and Brazil meet at 2016.14: India 88 and
> Brazil 89 in 2016, then India 89 and Brazil 83 in 2017. The chart shows the crossing in 2016
> (`2013-2016`), but the first-year rule keys `2017-2020`. Participants who read the chart correctly
> would be scored wrong, and only hover can separate 88 from 89. On Polio3 the same pair crosses
> cleanly: Brazil falls from 98 to 72 in 2016, and India stays at least 5 points above from then on.
>
> **B-T4 was India over Ukraine.** Those lines meet at 2008.87, only 0.37 years inside `2009-2012`,
> so a slightly early reading lands in `2004-2008`. China over Ukraine was B-T5 and moves here.

Options are 4-year bands (`2004-2008`, `2009-2012`, `2013-2016`, `2017-2020`, `2021-2024`), so the
answer does not depend on reading an exact value.

**The crossing year → band rule (recorded 2026-09-15).** The tables above state a crossing *year*;
the participant chooses a *band*. The key is the band containing that year. Bands are inclusive at
both ends and contiguous, so the mapping is unambiguous:

| | Form A | Form B |
|---|---|---|
| T4 | 2016 → `2013-2016` | 2008 → `2004-2008` |
| T5 | 2006 → `2004-2008` | 2012 → `2009-2012` |

The crossing year itself is the first year in which the overtaking series is **strictly above** the
other, having not been above in the preceding year. `CROSSING_BANDS` does not cover 2000–2003, and
no item crosses there. `analysis/keys.py` derives all four keys from `data/deploy/coverage.csv` by
this rule. It fails if any key disagrees with the table and, since 2026-09-22, if the lines meet less
than a year inside the key band.

### T5 — Crossing, smaller

Same wording as T4.

| | Form A | Form B |
|---|---|---|
| Pair | China over United Kingdom | China over Brazil |
| First year above | **2006** (China 93, United Kingdom 92) | **2012** (China 99, Brazil 95) |
| Lines meet | 2005.80 | tied at 99 in 2009–2011, apart from 2012 |
| Key | `2004-2008` | `2009-2012` |
| Entities | China, United Kingdom, World | Brazil, China, World |

Both are small crossings: in the years around the crossing, the lines are within about 6 points of
each other.

**Why the crossing items could not all be clean.** Among the ten countries, DTP3 has only three
clean single-crossing events: China's rise around 2006, Ukraine's collapse around 2008, and Brazil's
decline around 2016. MCV1, Polio3 and crossings of the World line add no fourth. Four items cannot
each use a distinct clean event. Using one event in both forms would let a participant answer the
second form from memory, which is the practice effect parallel forms exist to remove. So China over
Brazil stays, moved to form B, with the known weakness noted below. Each form's two crossing items
land in different bands.

> **Band-edge positions: revised 2026-09-22, pre-registered.**
> - Both T4 keys fall on the **last** year of their band: 2016 closes `2013-2016` and 2008 closes
>   `2004-2008`. There, a key-year reading one year late scores wrong, and a one-year misread is
>   likelier in the static condition.
> - A-T5's key is mid-band.
> - B-T5's key closes its band, after a three-year tie.
> - Every drawn crossing sits at least a year inside its band, which is what the acceptance rule
>   protects.
>
> **Decision: strict band scoring stays primary.** Adjacent-band credit is pre-registered as a
> **secondary** analysis for **every crossing item (T4 and T5)**, reported alongside the primary.
> Adjacent-band credit means the key band, or the band containing the key year ± 1. It was first
> ruled on 2026-09-15 for T5 alone, when both T5 keys sat on the last year of their band. Applying it
> to all four removes an item-by-item choice. Recording the rule before collection is what keeps
> this a disclosure rather than a post-hoc choice.

> **Pilot check: B-T5 may be a weak stimulus.** China and Brazil are both *exactly* 99.0 in 2009,
> 2010 and 2011 before China separates in 2012. Scoring is safe: first-strictly-above gives 2012 and
> first-not-below gives 2009, and both land in `2009-2012`. But two lines sitting on top of each
> other at 99 for three years may not read as a crossing at all in the static condition. This item
> was A-T5 until 2026-09-22.

### T6 — Gap reasoning

*What does the chart tell you about hepatitis B coverage in {countries} before {2019 / each of their
lines begins}?*

| | Form A | Form B |
|---|---|---|
| Series | United Kingdom HepB3 | Ethiopia, Nigeria, India HepB3 |
| Missing | 19 years (2000–2018) | 7, 4 and 4 years (all from 2000) |
| Entities | China, Ukraine, United Kingdom, World | Brazil, Ethiopia, India, Nigeria, World |
| Correct | **Coverage was not reported for those years** | same |

The options distinguish *not reported* from *zero coverage* from *low coverage*.

> **Scored separately from RQ1 (ruled 2026-09-22).** The answer is on screen in both conditions. The
> caption under every chart with a gap (`layout.gap_note`, `visual-spec.md` §3) says a break in a
> line "means the value was not reported, which is not the same as zero coverage", and so do the
> instructions. The caption is deliberate: without it, static participants could not know what a gap
> means. But it makes T6 the same task in both conditions by construction. T6 cannot show an effect
> of interactivity and will probably sit at ceiling, so counting it in the RQ1 score would only
> dilute the difference. It stays in the task set for two reasons: as a check that gaps are not read
> as zero, and for its justification (RQ2). It is reported on its own (§7).
>
> **A-T6's other lines changed 2026-09-22.** The UK's reported segment (93, 93, 93, 92, 92, 92 in
> 2019–2024) lay within 2 points of the United States line in every one of those years. The UK line
> was hidden, and only a participant who could filter the US away could find it. The UK, US and
> Brazil end labels also collided. China, Ukraine and World are at least 4 points from the UK
> throughout.
>
> **Correct row added 2026-09-15.** Of the four options, only "not reported" is a claim the data
> supports. `analysis/keys.py` proves it by asserting that every year in the window is missing
> (`None`) rather than recorded as `0.0`, which is exactly the distinction the item asks the
> participant to make.

> **Known weakness: check this in the pilot.** The UK's 19-year gap has no equal in the dataset; the
> next longest is Ethiopia's 7 years. Form B substitutes three shorter gaps to reach a comparable
> *quantity* of missing data, but the visual impression is not the same. Now that T6 is scored
> separately, the pilot question is whether either form falls below ceiling.

### Practice task (unscored)

Ukraine DTP3, 2000–2024: a collapse from 99% to 19%, unmissable. It is shown in the participant's
first condition only, identical across forms, to teach the interface rather than the concept. **It
does not demonstrate missing data**, so it cannot contaminate T6.

### Revision 2026-09-22, in brief

The audit measured every item against the acceptance rule above. Seven of the thirteen failed:

- T1 in both forms (2-point calls);
- B-T2 and B-T3 (a one-year slip flips the answer);
- A-T4 (the drawn crossing and the key disagree);
- B-T4 (0.37 years from a band edge);
- A-T6 (the UK line hidden under the US line).

Two further problems were systemic, and §5 and `visual-spec.md` §6 fix them:

- The correct answer was the first option in 7 of the 12 items.
- End labels collided on 9 of the 13 charts.

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
  which also sets each line's colour, with World always last.
- The gap item's options come in a fixed order: zero, very low, high and steady, **not reported**.
- Counts and year bands stay in their natural order.

Before this rule, the country options were sorted by how much each changed. That put the correct
answer first in every trend item, and on the first-coloured line. Counting the gap item too, the key
was option 1 in 7 of the 12 items. `tests/test_tasks.py` now fails if any one position holds more
than a third of the keys.

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
participant per condition, **over T1–T5**.

**T6 is reported separately (ruled 2026-09-22).** It is scored the same way, and reported per
condition as its own line. It never enters the RQ1 score. Its answer is on screen in both
conditions (§4), so it cannot differ by condition, and counting it would only dilute RQ1. Its
justifications are coded for RQ2 like any other.

**A skipped answer scores as incorrect** in the primary analysis (ruled 2026-09-21), so every
participant is scored out of five per condition. Dropping skips instead would let a condition that
provokes more skipping look more accurate than it is. *Secondary, pre-registered:* proportion correct
among answered items only, skips excluded. The number of skips per condition is reported alongside
both.

Scored by exact string equality against a key **derived from `data/deploy/coverage.csv`** by the
rule each item states, and cross-checked against the tables in §4 (`analysis/keys.py`). A derived key
that disagrees with §4 fails the test suite. This exists because §4's prose key for T1 was wrong —
it said 2, the data says 1 — and nothing would have caught it.

*Secondary, for the crossing items (T4 and T5):* accuracy recomputed with adjacent-band credit, per
the band-edge ruling in §4. It applied to T5 alone until 2026-09-22, when both T4 keys came to sit
on the last year of their band. It is reported alongside the primary, never in place of it.

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

`consent → participant ID → demographics → instructions → practice → 6 tasks → survey → break →
instructions → 6 tasks → survey → complete`

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
both requests advance from the same starting point.

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
- T6 form equivalence. T6 is now scored separately, so the pilot question is whether either form
  falls below ceiling. See the warning in §4.
- **B-T5 may not read as a crossing at all.** China and Brazil sit at exactly 99.0 for three years
  before separating. Check it in the pilot, with T6. It was A-T5 until 2026-09-22. See §4.
- ~~Whether the items can be answered without hover.~~ Resolved 2026-09-22: the item acceptance
  rule in §4, enforced by `analysis/keys.py`. Seven of the thirteen items were replaced or repaired.
- **Session resume is not implemented.** The participant-ID screen no longer promises it; it asks
  for one sitting in one tab instead. See §8.
- ~~Whether the justification should be optional.~~ Resolved 2026-09-21: every question may be
  skipped (IRB form item 10), behind a confirmation popup. See §5.
- **IRB paperwork wording to fix before submission.** The app follows this document; these lines in
  the IRB documents (`irb/COMP 490 Request Form.pdf` and `irb/COMP 490 Consent Form.pdf`, revised
  2026-09-21) still describe it inaccurately:
  - *Both forms:* "explicit directional (year-over-year) change indicators". Year-over-year change
    appears only in the hover tooltip (`visual-spec.md` §7.1).
  - *Request form 5B:* "value retrieval" tasks. No item may ask for an exact value (§2).
  - *Request form 18* is blank, and it asks for the survey's URL and a PDF copy of it. The PDF is
    `irb/questionnaire.pdf`, generated by `scripts/export_questionnaire.py` from the app's own screen
    code. Regenerate it after any wording change. The URL is the deployed Vercel address.
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
  None currently does.
