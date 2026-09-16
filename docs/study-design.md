# Study design

Source of truth for the protocol: research questions, conditions, tasks, measures, and scoring.
`docs/visual-spec.md` is the source of truth for what the charts look like. Change this document
before changing `src/tasks.py` or `src/flow.py`.

Status: **draft, 2026-09-15.** The consent text in §9 is a DRAFT FOR IRB REVIEW and must not be
shown to a participant until approved.

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
task. Expected duration 20–25 minutes.

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
simultaneous participants can never collide (`db.assign_participant`):

| seq % 4 | Condition 1 | Form | Condition 2 | Form |
|---|---|---|---|---|
| 1 | static | A | interactive | B |
| 2 | interactive | A | static | B |
| 3 | static | B | interactive | A |
| 0 | interactive | B | static | A |

Every participant sees both conditions and both forms, never the same form twice.

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

All values verified against `data/deploy/coverage.csv`. All items use DTP3 except the gap items.

### T1 — Reference comparison (warm-up)

*How many of the countries shown were above the World average in {year}?*

| | Form A | Form B |
|---|---|---|
| Year | 2010 (World 83%) | 2020 (World 83%) |
| Entities | Brazil, Nigeria, Ethiopia, India, Indonesia, World | same |
| Above | Brazil 99 | India 85 |
| Correct | **1** | **1** |

Matched: exactly one above the line out of five, in both forms.

> **Corrected 2026-09-15.** This table previously listed the United States among the entities and
> gave the answer as 2 in both forms. It cannot: six coloured countries breach `MAX_SERIES = 5`
> (`docs/visual-spec.md` §6), and `src/tasks.py` had always omitted the US accordingly. Checked
> against `data/deploy/coverage.csv` — Form A 2010: Brazil 99 is the only country above World's 83
> (Nigeria 56, Ethiopia 61, India 79, Indonesia 81); Form B 2020: India 85 is the only one (Brazil
> 77, Nigeria 62, Ethiopia 62, Indonesia 77). The item stays matched across forms and "1" is among
> the options, so the task set is unchanged — only this key was wrong.

### T2 — Trend, decline

*Between {y1} and {y2}, which country's coverage fell the most?*

| | Form A | Form B |
|---|---|---|
| Window | 2015 → 2021 | 2010 → 2014 |
| Correct | **Brazil** (96 → 68, −28pp) | **Ukraine** (52 → 23, −29pp) |
| Nearest distractor | Indonesia (84 → 67, −17pp) | Nigeria (56 → 43, −13pp) |
| Entities | Brazil, Indonesia, India, United States, Nigeria, World | Ukraine, Nigeria, Brazil, Pakistan, India, World |

Matched: −28 vs −17, against −29 vs −13.

### T3 — Trend, growth

*Between {y1} and {y2}, which country improved the most?*

| | Form A | Form B |
|---|---|---|
| Window | 2000 → 2012 | 2012 → 2024 |
| Correct | **Ethiopia** (30 → 61, +31pp) | **Nigeria** (36 → 67, +31pp) |
| Nearest distractor | India (58 → 82, +24pp) | Pakistan (64 → 87, +23pp) |
| Entities | Ethiopia, India, China, Indonesia, Brazil, World | Nigeria, Pakistan, India, Ethiopia, Indonesia, World |

Matched almost exactly: +31 vs +24, against +31 vs +23.

### T4 — Crossing, large

*One country overtook the other. Roughly when?*

| | Form A | Form B |
|---|---|---|
| Pair | Brazil vs India | India vs Ukraine |
| Crossing | **2017** | **2009** |
| Entities | Brazil, India, World | India, Ukraine, World |

Options are 4-year bands (e.g. 2004–2008, 2009–2012, 2013–2016, 2017–2020, 2021–2024), so the answer
does not depend on reading an exact value.

### T5 — Crossing, smaller

Same wording as T4.

| | Form A | Form B |
|---|---|---|
| Pair | Brazil vs China | Ukraine vs China |
| Crossing | **2012** | **2008** |
| Entities | Brazil, China, World | Ukraine, China, World |

Both pairs have the same effect size (+13 → −17 between early and late means).

### T6 — Gap reasoning

*What can you say about hepatitis B coverage in {country} before {year}?*

| | Form A | Form B |
|---|---|---|
| Series | United Kingdom HepB3 | Ethiopia, Nigeria, India HepB3 |
| Missing | 19 years (2000–2018) | 7, 4 and 4 years (all from 2000) |
| Entities | United Kingdom, United States, Brazil, World | Ethiopia, Nigeria, India, Brazil, World |

Options distinguish *not reported* from *zero coverage* from *low coverage*. This is the item most
directly aimed at RQ1: in the static condition there is no tooltip to explain a break in a line.

> **Known weakness — check this in the pilot.** The UK's 19-year gap has no equal in the dataset; the
> next longest is Ethiopia's 7 years. Form B substitutes three shorter gaps to reach a comparable
> *quantity* of missing data, but the visual impression is not the same, so T6 is the least equivalent
> of the six pairs. If the pilot shows a difficulty difference, use form A's item in both forms and
> accept a repeat on this one task, or drop T6 to a single form.

### Practice task (unscored)

Ukraine DTP3, 2000–2024 — a 99% → 19% collapse, unmissable. Shown in the participant's first
condition only, identical across forms, to teach the interface rather than the concept. **It does not
demonstrate missing data**, so it cannot contaminate T6.

## 5. Answer format

Every scored task collects two things:

1. **A multiple-choice answer** — scored objectively, no rater judgement.
2. **A short free-text justification** ("In one sentence, how did you decide?") — the material for
   RQ2.

The justification is required but not length-constrained. Correct answers are **never** stored in
`src/tasks.py`: that module ships to the browser, where an answer key would be readable in the page
source. Scoring happens offline against §7.

## 6. Cognitive load

After each condition, one item (Paas mental-effort scale):

> **In solving the preceding tasks, I invested:**
> 1 — very, very low mental effort … 9 — very, very high mental effort

One item, not NASA-TLX: with only two conditions per participant the extra subscales add
administration time and fatigue without much resolution. Logged as `load_rating` with
`{"scale": "paas", "value": 1-9}`.

## 7. Scoring

**Accuracy (RQ1).** Binary per task from the multiple choice. Primary outcome: proportion correct per
participant per condition.

**Reasoning depth (RQ2).** Each justification coded on three binary features:

| Code | Present when the participant… |
|---|---|
| `cites_values` | refers to specific levels or magnitudes, however approximate |
| `compares_series` | refers to more than one country, not just the answer |
| `notes_uncertainty` | flags missing data, an estimate, or ambiguity |

Depth score 0–3. Code blind to condition. A second coder scores 20% of the justifications;
report Cohen's κ.

**Cognitive load (RQ3).** Paas score per condition, 1–9.

**Time on task.** From the browser clock (`performance.now()`), never the server, so cold starts and
network latency do not enter a dependent variable.

**Exclusions**, decided before analysis: sessions not reaching `complete`; any task under 3 seconds
(not read); the top 1% of task durations (walked away). Report how many were excluded and why.

## 8. Procedure

`consent → participant ID → instructions → practice → 6 tasks → load rating → break → instructions →
6 tasks → load rating → complete`

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
the session; re-entering the same participant ID resumes with the same condition and form assignment,
never re-randomised.

Each condition is one log session, opened at its instructions and closed after its load rating, so
both halves produce a complete `session_start … session_end` record.

## 9. Consent — DRAFT FOR IRB REVIEW

> **This wording is a draft. It has not been reviewed or approved, and must be replaced with
> IRB-approved text before any participant sees it.**

> **Interactivity and interpretability in data dashboards**
>
> You are invited to take part in a study run by a senior Computer Science student at Occidental
> College. It takes about 20–25 minutes.
>
> You will read charts of childhood vaccination coverage and answer questions about them. There are
> no right-or-wrong consequences for you; we are studying the charts, not you.
>
> **What is recorded:** your answers, how long each task takes, and how you interact with the charts
> (clicks, filters, hovers). A participant ID that you enter, which is not linked to your name. No
> personal information is collected.
>
> **Voluntary:** you may stop at any time by closing the tab, with no consequence. Data from an
> incomplete session is discarded.
>
> **Contact:** [name, email]. **IRB:** [protocol number, contact].
>
> Selecting "I agree" records your consent with a timestamp.

## 10. Open items

- IRB approval, and the final consent wording.
- T6 form equivalence — see the warning in §4.
- Whether the justification should be optional; requiring it may increase dropout on a self-served
  web study.
- Continent aggregates have no 2024 data, so no item may turn on a continent's most recent year.
  None currently does.
