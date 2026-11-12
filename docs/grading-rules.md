# Grading rules: T1 rubric and RQ2 codes

**Written:** 2026-11-11, before any participant answer was read.
**Grader:** Eduardo Rebollar, sole grader. *Amended the same day, before any code was entered:*
Claude drafts every code and Eduardo reviews each one (§1, item 4).
**Status:** clarifies how `docs/study-design.md` sections 4 and 7 are applied. It does not replace
them. G2 and G3 restate rules §4 already gives for T1; the rest settles cases §4 and §7 leave open.
Commit this file before opening any grading sheet. The commit date is the record that these rules
came first.

All examples below are invented to illustrate the rules. None is a participant's answer.

---

## 1. Changes from the pre-registration

Report these in the write-up as deviations, alongside participant 19.

1. **One grader instead of two.** Section 7 has two coders grade every T1 description and a second
   coder grade 20% of the justifications. Here one person grades everything, so no kappa is reported
   for T1 or for the RQ2 codes. This is reported as a limitation. The grader also knows the
   hypotheses, which is why the rules below are written to be as mechanical as possible.
2. **New secondary: T1 parts score (0-3).** The number of rubric parts (a, b, c) credited. The
   primary T1 score is unchanged: correct only when all three parts are credited and nothing
   contradicts one.
3. **New secondary: RQ2 codes by version.** `cites_values` and `compares_series` are each
   reported by version, next to the depth sum (0-2 since item 5).
4. **An AI draft, reviewed code by code** (amended 2026-11-11, before any code was entered).
   - Claude (Anthropic's Claude Opus 5.5, in Claude Code) drafts every code on both sheets, by
     these rules, from the blind sheets alone. It does not open `key.csv`, `rubric_key.csv` or
     `tasks.csv`. Like the grader, it knows the hypotheses.
   - A `draft_note` column explains each call the rules leave close. The scripts ignore it.
   - Eduardo then reviews every code against the text and these rules, and changes any he
     disagrees with. His code is final.
   - The draft is kept unchanged beside each sheet (`rubric_coder1_draft.csv`,
     `coder1_draft.csv`), so the write-up can report how many codes the review changed. That count
     is not an agreement statistic: the review starts from the draft and is anchored by it.
   - Report the scores as AI-drafted and human-reviewed.
5. **`notes_uncertainty` dropped from RQ2** (decided 2026-11-11, in review, before the key was
   opened).
   - Depth is now `cites_values` + `compares_series`, from 0 to 2, not the pre-registered 0-3.
   - Why: the 20 units the draft coded 1 all flag that the chart was hard to read (colours alike,
     too many lines, torn between two answers, no exact value). None flags a limit of the data.
     That is the cognitive-load side of RQ1, not interpretation depth, and static users, who
     cannot hover for values, have more reason to report it, so the code would tilt depth by
     version.
   - The decision followed a look at the code's blind distribution (which units were coded 1, with
     no version attached), not at any result by version.
   - The draft's `notes_uncertainty` column stays in both RQ2 sheets, unreviewed; the analysis
     ignores it.

Everything else in this file explains how the existing codes are applied. It does not change what
they measure.

## 2. Procedure

- Grade only from the blind sheets: opaque unit id and text, shuffled.
- Do not open `key.csv` or `rubric_key.csv` until every unit on every sheet is graded.
- **Decision log.** When an answer is not covered by these rules:
  1. write the new rule in the log at the end of this file, with the date;
  2. re-check every answer already graded against it;
  3. carry on.

  The write-up reports how many rules were added during grading. Claude adds a row when its draft
  meets a case the rules do not cover; Eduardo confirms or changes the rule in review.

The scripts run in single-grader mode (`SINGLE_GRADER` in `analysis/coding.py`). The order:

```
uv run python scripts/score_study.py                      # marks exclusions; T1 uncoded
uv run python scripts/code_justifications.py rubric-sheets  # rubric_coder1.csv, the one T1 sheet
uv run python scripts/code_justifications.py sheets         # coder1.csv, the one RQ2 sheet
#   grade rubric_coder1.csv (a, b, c, contradicts) and coder1.csv (cites_values, compares_series), 0 or 1 each:
#   Claude drafts both, keeping *_draft.csv copies; Eduardo reviews and corrects every code
uv run python scripts/code_justifications.py rubric       # verdicts and parts scores
uv run python scripts/code_justifications.py depth        # depth and each code, with and without T1
uv run python scripts/score_study.py                      # again: RQ1 and the parts score
```

All files land in `data/study_logs/coding/` (gitignored). `rubric` refuses a sheet with a blank
or non-0/1 field, and a unit with `contradicts` = 1 and a, b and c all 1, which G4 rules out.
`kappa` refuses: with one grader there is nothing to compare.

## 3. What the T1 charts show (2000-2024)

The chart runs from 1985 to 2024. It has a dot for every year, horizontal gridlines every 10
points, vertical gridlines every 5 years, and a name tag at the end of each line. Form A's
screenshot was checked; Form B uses the same chart design.

| | Form A | Form B |
|---|---|---|
| Riser | India: 58 → 94. Steady rise; small dip from 91 (2019) to 85 (2020-21) | Uganda: 52 → 91. Peaks at 94 in 2017, then 89-93 |
| Faller | Ukraine: about 99 until 2007; 50 by 2011; 76 in 2012-13; 19 in 2016; 88 by 2024 | Brazil: 98-99 until 2011; jagged fall to 68 in 2021; 91 by 2024 |
| Crossing | India first above Ukraine in 2009 and stays above | Uganda first above Brazil in 2016 |
| End (2024) | India 94, Ukraine 88 (6 apart) | Uganda 91, Brazil 91 (level) |

## 4. T1: general rules (apply to every part)

**G1. Meaning, not keywords.** Any wording that conveys the part earns it. Hedges such as "seems",
"I think" or "probably" do not lose credit.

**G2. Only 2000-2024 counts.** (Restates §4.)
- Ignore statements only about years before 2000, unless one is plainly offered as the 2000-2024
  trend and contradicts a part.
- A statement covering a longer span ("from under 20% in 1985 to 94%") is graded on what it says
  about 2000-2024.

**G3. Judge the pattern, not the precision.** *(Decided 2026-11-11; §4 already says years and
values are neither required nor penalised unless they contradict a part.)*
- A wrong number or year matters only if it changes the pattern: the direction, which country is
  higher, or whether a fall or recovery happened.
- Otherwise precision errors are ignored. For example, "India passed Ukraine around 2015" still
  earns (c), although the crossing was in 2009.
- Rationale: T1 measures trend interpretation, and T2-T5 measure value reading. Static users must
  estimate values, so a precision rule would penalise the static version for something T1 does not
  measure.

**G4. Errors and omissions are coded differently.**
- A part that is stated wrongly scores 0, and `contradicts` = 1.
- A part that is simply missing scores 0, and `contradicts` = 0.
- If a description states a part and also contradicts it, the part scores 0 and `contradicts` = 1.
- So `contradicts` = 1 always comes with at least one part at 0. `rubric` refuses a sheet that
  breaks this, since one of that unit's fields must be a slip.

**G5. Grade what is written.**
- If the two countries are swapped (India's pattern given to Ukraine and vice versa), (a) and (b)
  are both stated wrongly.
- Statements about other countries on the chart are ignored.

## 5. T1: the three parts

### (a) The riser rose. Form A: India. Form B: Uganda.

- **Earns (a):** any statement of an overall increase across the period. Mentioning dips, a plateau
  or a levelling-off is fine. A rise described over most of the period also counts.
- **Does not earn (a):** only "fluctuated" or "changed"; a rise over only a short stretch.
- **Contradiction:** India stayed flat, fell overall, or ended lower than it started.

| Invented example (Form A) | a | contradicts |
|---|---|---|
| "India went from about 60% to over 90%." | 1 | 0 |
| "India improved steadily apart from a dip around 2020." | 1 | 0 |
| "India changed a lot over time." | 0 | 0 |
| "India stayed about the same." | 0 | 1 |

### (b) The faller fell, then recovered. Form A: Ukraine. Form B: Brazil.

- **Earns (b):** a fall *and* a later rise, in any words.
  - A partial recovery counts (Ukraine ends at 88, not 99; Brazil at 91, not 99).
  - Describing one of Ukraine's two dips, or both, is fine.
- **Does not earn (b):** *(Decided 2026-11-11.)*
  - only the fall ("declined", "dropped");
  - only "volatile", "unstable" or "fluctuated", with no sign that it came back up.
- **Not a contradiction:** "Ukraine declined" or "Brazil declined overall". Both are true end to end
  (99 → 88; 98 → 91). They score 0 for (b) as omissions.
- **Contradiction:** rose overall, stayed steady or high throughout, never recovered, or ended at
  its low.

| Invented example (Form A) | b | contradicts |
|---|---|---|
| "Ukraine started near 100%, crashed to about 20% in the mid-2010s, then climbed back to the high 80s." | 1 | 0 |
| "Ukraine dipped twice but recovered by the end." | 1 | 0 |
| "Ukraine fluctuated wildly." | 0 | 0 |
| "Ukraine's coverage declined." | 0 | 0 |
| "Ukraine dropped and never recovered." | 0 | 1 |

### (c) The riser passed the faller, or they ended close. Form A: India and Ukraine. Form B: Uganda and Brazil.

- **Earns (c):**
  - The riser passed or overtook the faller, or the same said the other way ("Ukraine fell below
    India").
  - The riser ended higher than the faller, even without saying "passed". *(Decided 2026-11-11.)*
  - They ended close, similar, level, or caught up with each other. "Close" means within one
    gridline (10 points), so both forms qualify: A ends 6 apart, B ends level.
  - On Form B, "Uganda ended slightly higher" and "Brazil ended slightly higher" both count as
    ending close.
- **Timing is not required.** A wrong crossing year does not cost (c) (G3).
- **Does not earn (c):** two separate descriptions with nothing that relates one country to the
  other.
- **Contradiction:** the faller stayed above the riser the whole time, the riser never caught up,
  or they ended far apart.

| Invented example (Form A) | c | contradicts |
|---|---|---|
| "Ukraine fell below India around 2010." | 1 | 0 |
| "India passed Ukraine around 2015." | 1 | 0 |
| "India ended higher than Ukraine." | 1 | 0 |
| "By 2024 they were at about the same level." | 1 | 0 |
| "Ukraine was higher than India the whole time." | 0 | 1 |

### Worked examples (invented)

| Description | a | b | c | contradicts | Primary | Parts |
|---|---|---|---|---|---|---|
| "India rose steadily from about 60% to 94%. Ukraine was near 100%, dropped a lot in the 2010s, then came back up. India ended above Ukraine." | 1 | 1 | 1 | 0 | correct | 3 |
| "India went up over time. Ukraine was really unstable." | 1 | 0 | 0 | 0 | incorrect | 1 |
| "India dropped sharply around 2015 and recovered, while Ukraine rose steadily." (countries swapped) | 0 | 0 | 0 | 1 | incorrect | 0 |

## 6. T1 scores

- **Primary (pre-registered):** correct = a = 1, b = 1, c = 1 and `contradicts` = 0. A skipped
  description is incorrect and is not graded.
- **Secondary (new):** parts score = a + b + c, from 0 to 3. Under G4 a wrongly stated part is
  already 0, so this counts parts stated correctly.

## 7. RQ2 codes (every justification, plus each T1 description)

Each code is 0 or 1. Depth = `cites_values` + `compares_series` (0-2). `notes_uncertainty` was
dropped (§1, item 5); its definition is kept below as the draft applied it. The two codes are
also reported separately by version.

### `cites_values`: refers to specific levels or magnitudes, however approximate

- **Counts:**
  - a number read from the chart: a value, a change ("rose about 50 points"), a ratio ("doubled"),
    or a year ("crossed around 2007");
  - a value band read from a colour key ("in the 40-50% shade").
- **Approximation is fine.** "About 90%" counts.
- **Does not count:**
  - numbers copied from the question or the answer options ("below 50%" on T5, "2004-2008" on T6,
    "third-highest" on T2);
  - vague amounts ("a lot", "much higher", "huge jump").

### `compares_series`: refers to more than one country, not just the answer

- **Counts:** naming or pointing to another specific country besides the answer.
  - "after China and Vietnam"
  - "the two bars above it"
  - "Burkina Faso was close behind"
- **Does not count:** a bare superlative or a reference to the rest in general. *(Decided
  2026-11-11.)*
  - "the highest of all"
  - "improved the most"
  - "higher than all the others"
- **Questions that already name two countries.** On T1 and T6 the question names two countries, so
  this code will be present in nearly every answer. Section 7 already reports depth with and
  without T1.

### `notes_uncertainty` (dropped, §1 item 5): flags missing data, an estimate, or ambiguity

- **Counts:** saying the answer or the reading was uncertain, or why.
  - "hard to tell between Niger and Burkina Faso"
  - "the lines were really close"
  - "the colours looked alike"
  - "I had to estimate from the gridlines"
  - "these are estimates", or "some years are missing"
  - "I guessed", "I wasn't sure"
- **Does not count:** *(Decided 2026-11-11.)*
  - a bare "I think", "I believe", "probably" or "seems";
  - approximation words attached to a number ("about 90%", "around 2007", "~60"). These earn
    `cites_values` only, so one phrase cannot score twice.

### Invented examples

| Justification | cites_values | compares_series | depth |
|---|---|---|---|
| T2: "India's bar was third, after China and Vietnam." | 0 | 1 | 1 |
| T2: "India was around 90%, just below Vietnam at 97%." | 1 | 1 | 2 |
| T3: "Niger moved the furthest above the diagonal." | 0 | 0 | 0 |
| T3: "Niger went from about 34 to 86, a bit more than Burkina Faso, but it was hard to tell." | 1 | 1 | 2 |
| T4: "I think Chad had the lowest cell." | 0 | 0 | 0 |
| T5: "Chad, Nigeria and the Central African Republic were the only ones shaded below 50%." | 0 | 1 | 1 |

## 8. Decision log

Add a row whenever an answer is not covered above. After each new rule, re-check the answers already
graded against it.

| Date | Sheet | The case (described, not quoted) | Rule added | Answers re-checked |
|---|---|---|---|---|
| 2026-11-11 | rubric | Each country's end value given separately, never compared | *Amended in review, 2026-11-11, before the key was opened:* separate end values earn (c) when both are stated and fall within one gridline (10 points), since that conveys "ended close" by §5 (c)'s own definition (G1). One end value alone does not, nor does anything else that never relates the two (§5 (c), two separate descriptions). *Drafted as:* separate end values, equal or not, never earn (c) | all 46, re-checked in review: 3 changed |
| 2026-11-11 | rubric | Form B: Brazil said to end higher, with nothing on the size of the gap | Earns no (c) and contradicts nothing; "slightly higher" still counts as ending close | all 46, drafted with it |
| 2026-11-11 | rubric | A claim about every country, or the rest of them, where the faller is never named | Not read as a claim about the faller (G5) | all 46, drafted with it |
| 2026-11-11 | rubric | The faller said to decrease over the whole period | An overall decline, an omission like "declined" (§5 (b)), unless it says the fall never stopped or ended at the low | all 46, drafted with it |
| 2026-11-11 | rubric | The riser given a large fall it did not have, but not called flat, falling overall or ending lower | An omission for (a), not a contradiction: (a)'s contradictions are the three listed | all 46, drafted with it |
| 2026-11-11 | rubric | The two said to converge at the end | A later rise for (b) only if the faller had first dropped below the riser; after a fall alone, converging is no sign of a rise | all 46, drafted with it |
| 2026-11-11 | RQ2 | `compares_series` on T2: the bars above or below the answer referred to as a group, by count, rank or value, without names | Counts when it picks out specific bars (how many are taller, the lowest few, the top two, their values), like "the two bars above it"; describing a count-down alone does not | all 276, drafted with it |
| 2026-11-11 | RQ2 | `compares_series` on T5, T1 and T6: countries referred to without names | On T5 only named countries count, not a pointer to the counted ones or a count. On T1 and T6, a pronoun, "the two countries" or the two lines by colour counts: they can only mean the question's pair | all 276, drafted with it |
| 2026-11-11 | RQ2 | `notes_uncertainty`: the chart called hard to read, being torn between two options, checking by hovering | The first two count; checking an answer, with no doubt stated, does not. *Moot: the code was dropped in review (§1, item 5).* | all 276, drafted with it |
| 2026-11-11 | RQ2 | `cites_values` on T4 and T5: years and key bands | A year read off the heatmap counts, its full span included, since T4's question names none; a key band counts unless it only restates the question's threshold | all 276, drafted with it |

Rows of 2026-11-11 were added by Claude while drafting (§1, item 4); Eduardo confirms or changes each in
review.
