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

Options are 4-year bands (`2004-2008`, `2009-2012`, `2013-2016`, `2017-2020`, `2021-2024`), so the
answer does not depend on reading an exact value.

**The crossing year → band rule (recorded 2026-09-15).** The tables above state a crossing *year*;
the participant chooses a *band*. The key is the band containing that year. Bands are inclusive at
both ends and contiguous, so the mapping is unambiguous:

| | Form A | Form B |
|---|---|---|
| T4 | 2017 → `2017-2020` | 2009 → `2009-2012` |
| T5 | 2012 → `2009-2012` | 2008 → `2004-2008` |

The crossing year itself is the first year in which the overtaking series is **strictly above** the
other, having not been above in the preceding year. Note `CROSSING_BANDS` does not cover 2000–2003;
no item crosses there. `analysis/keys.py` derives all four from `data/deploy/coverage.csv` by this
rule and fails if any disagrees with the table.

### T5 — Crossing, smaller

Same wording as T4.

| | Form A | Form B |
|---|---|---|
| Pair | Brazil vs China | Ukraine vs China |
| Crossing | **2012** | **2008** |
| Entities | Brazil, China, World | Ukraine, China, World |

Both pairs have the same effect size (+13 → −17 between early and late means).

> **Band-edge asymmetry — ruled on 2026-09-15, pre-registered.** Both T5 keys fall on the **last**
> year of their band (2012 closes `2009-2012`; 2008 closes `2004-2008`), while both T4 keys fall on
> the **first** year of theirs. A participant who reads the crossing one year late still scores
> correctly on T4 but incorrectly on T5 — and a one-year misread is likelier in the static
> condition, which has no hover. That would push RQ1 in the hypothesised direction for a reason that
> is not interactivity.
>
> **Decision: keep the items and pre-register both analyses.** Strict band scoring is the primary
> outcome. Adjacent-band credit on T5 (the key band, or the band containing key year ± 1) is
> pre-registered as a **secondary** analysis, reported alongside. The forms are matched on edge
> position — T4 first-year and T5 last-year in *both* — so neither form is advantaged; the cost is
> error variance on T5, not bias between forms. Recording the rule now, before collection, is what
> keeps this a disclosure rather than a post-hoc choice.

> **Pilot check — A-T5 may be a weak stimulus.** China and Brazil are both *exactly* 99.0 in 2009,
> 2010 and 2011 before China separates in 2012. Scoring is safe (first-strictly-above gives 2012 and
> first-not-below gives 2009, and both land in `2009-2012`), but two lines sitting on top of each
> other at 99 for three years may not read as an "overtaking" at all in the static condition. Check
> it in the pilot alongside T6.

### T6 — Gap reasoning

*What can you say about hepatitis B coverage in {country} before {year}?*

| | Form A | Form B |
|---|---|---|
| Series | United Kingdom HepB3 | Ethiopia, Nigeria, India HepB3 |
| Missing | 19 years (2000–2018) | 7, 4 and 4 years (all from 2000) |
| Entities | United Kingdom, United States, Brazil, World | Ethiopia, Nigeria, India, Brazil, World |
| Correct | **Coverage was not reported for those years** | same |

Options distinguish *not reported* from *zero coverage* from *low coverage*. This is the item most
directly aimed at RQ1: in the static condition there is no tooltip to explain a break in a line.

> **Correct row added 2026-09-15.** This table previously had no `Correct` row at all — the key was
> implied by the surrounding prose and stated nowhere, the same class of omission that left T1's key
> wrong until it was checked against the data. The key is derivable, not assumed: of the four
> options, only "not reported" is a claim the data supports. `analysis/keys.py` proves it by
> asserting every year in the window is missing (`None`) rather than recorded as `0.0` — which is
> exactly the distinction the item asks the participant to make.

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

This section is a **pre-registration**. Every rule here is fixed before collection begins, because
choosing an exclusion rule after seeing the data is a methodological problem however reasonable the
rule is. `analysis/` implements it; nothing is decided at analysis time.

**Accuracy (RQ1).** Binary per task from the multiple choice. Primary outcome: proportion correct per
participant per condition.

Scored by exact string equality against a key **derived from `data/deploy/coverage.csv`** by the
rule each item states, and cross-checked against the tables in §4 (`analysis/keys.py`). A derived key
that disagrees with §4 fails the test suite. This exists because §4's prose key for T1 was wrong —
it said 2, the data says 1 — and nothing would have caught it.

*Secondary, for T5 only:* accuracy recomputed with adjacent-band credit, per the band-edge ruling in
§4. Reported alongside the primary, never in place of it.

**Reasoning depth (RQ2).** Each justification coded on three binary features:

| Code | Present when the participant… |
|---|---|
| `cites_values` | refers to specific levels or magnitudes, however approximate |
| `compares_series` | refers to more than one country, not just the answer |
| `notes_uncertainty` | flags missing data, an estimate, or ambiguity |

Depth score 0–3. Code blind to condition. A second coder scores 20% of the justifications;
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

**Cognitive load (RQ3).** Paas score per condition, 1–9.

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
| `incomplete_session` | The participant did not produce **two** log sessions each carrying a `session_end` and six scored answers. Stated this way because `session_end` is written per *condition*, not once at the end of the study, so "reached `complete`" needed a precise test. |
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

### How consent is recorded

Selecting "I agree" captures a timestamp in the participant's browser. It is written to the log as a
`consent` event when the session's logger opens, a moment later, on the instructions screen — the
logger cannot open before then, because a log record must carry a participant ID and a condition, and
neither exists until the participant has entered an ID and been assigned. The event is emitted once
per participant, not once per condition.

Two consequences, recorded rather than hidden:

- The event's `server_ts` is the instructions-screen time; the true consent time is
  `payload.consented_at`. Analysis must read the latter.
- **A participant who agrees and then leaves before entering an ID produces no consent record.** They
  also produce no data, so nothing unconsented is ever stored — but the record is of consenting
  participants, not of everyone who clicked.

The event also stores a hash of the consent wording shown, so a mid-study change to the text is
detectable in the data rather than being a matter of recollection.

## 10. Open items

- IRB approval, and the final consent wording.
- T6 form equivalence — see the warning in §4.
- **A-T5 may not read as a crossing at all** — China and Brazil sit at exactly 99.0 for three years
  before separating. Check in the pilot, with T6. See §4.
- **Session resume is not implemented.** The participant-ID screen no longer promises it; it asks
  for one sitting in one tab instead. See §8.
- Whether the justification should be optional; requiring it may increase dropout on a self-served
  web study.
- Continent aggregates have no 2024 data, so no item may turn on a continent's most recent year.
  None currently does.
