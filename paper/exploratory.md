# Exploratory descriptives for the paper

**Listed:** 2026-11-17, before any item below was computed.
**Status:** every item is post hoc and descriptive. Nothing here is a test, and nothing here can be
called significant. Only the three Holm-family tests in `significance.txt` can
(`docs/study-design.md` §7, Inference).
**Computed by:** `scripts/paper_descriptives.py`, written after this list. Its outputs go to
`data/study_logs/derived/paper/`, which is gitignored.
**Decided 2026-11-17, before any item was computed:** item 8 computes nothing (Eduardo). Eduardo
left 3b, 7b and item 4's thresholds to Claude, which kept all three as first proposed.

Commit this file before the script runs. The commit date is the record that these definitions,
thresholds included, came before their numbers, as `docs/grading-rules.md`'s did for grading.
This file is meant for the public repository, so it names no participant.

## Seen before this list was written

- `significance.txt`, both analyses (the confirmatory run, 2026-11-11).
- The reports `scripts/score_study.py` printed, n = 23, `report_section10.txt` among them. These
  include Paas and a7 by condition, the c1 and c2 counts, T1's parts score and which controls
  were found.
- The poster's averages (2026-11-10 to 11).
- The qualitative first pass in `data/study_logs/qual/` (2026-11-16), not yet spot-checked.

No participant-level table in items 2 to 7 has been computed yet.

## Rules for every item

- **Two analyses, side by side.**
  - *Main:* participant 19 reinstated, n = 24. It is built by `reinstate()` in
    `notebooks/significance.py`, which drops their empty session and re-runs every rule in
    `analysis/exclusions.py`, unchanged and in order.
  - *As pre-registered:* `tasks.csv` and `conditions.csv` as `scripts/score_study.py` wrote them,
    n = 23.
  - Every table is given for both, and each is labelled.
- **Descriptive statistics only.** That means counts, proportions, means, SDs, medians, ranges,
  cross-tabulations and, in item 4 only, a rank-correlation coefficient. No p-values, confidence
  intervals, standard errors, bootstraps or tests of any kind.
- **The notebook supplies only** `reinstate()`, `participant_scores()` (the scores the tests ran
  on), `ceiling()`, the guard `check_reinstated_coded()` and its constants. The script never calls
  `crossover`, `run`, `permutation_p`, `tost`, `wilcoxon`, `holm`, `analyse` or `main`, and a test
  checks it for those names.
- **Checked against the run.** For each analysis, the script's n for each outcome and its ceiling
  counts must equal those in `significance.txt`, and the exclusion flags it re-derives must equal
  those in `tasks.csv`. If any differs, it writes nothing.
- **Nobody is excluded and no confirmatory estimate is redone.** The effect estimates the paper
  quotes come from `significance.txt`, never from a mean computed here.
- **No free text.** As the files are read, T1 descriptions, justifications, c3, E2, E3 and
  "Other" text are each replaced by a marker. Only whether something was written survives, which
  the report needs for its "how many wrote something" counts. Participant IDs appear only in the
  gitignored outputs, and nothing joins a setting (workplace, outdoors, home) to an ID. Background
  tables are printed in full there, and the paper merges any group smaller than five (§6.2).
- **An accuracy difference in items** is the interactive proportion correct minus the static one,
  times 6.

## 1. The section 7 and section 10 descriptives, with participant 19

- **Computes:** every table in `report_section10.txt`, by `render()` in `analysis/report.py`, on
  the main analysis. That means the reinstated tasks, the conditions without the empty session,
  the exclusion table from the re-run rules, and `participants.csv`. Run on the pre-registered
  frames, the same call reproduces `report_section10.txt`'s tables.
- **Also:** each participant's scores per condition, from `participant_scores()`: accuracy,
  accuracy on answered items, accuracy without E1 "Yes", T1's parts score, time, Paas, depth
  (T2–T6), each code's share and depth with T1. For each condition: n, mean, SD and median (time
  as the geometric mean in seconds). For each participant's difference, interactive minus static:
  how many are above, at and below zero, and their SD.
- **One table differs from `report_section10.txt`.** That file's windows table counts participant
  19, because `windows()` reads every row, while every other table in it is n = 23. Here, each
  analysis counts only its own participants' windows.
- **Post hoc in timing only.** The tables were pre-registered for the analysis as registered. Only
  their n = 24 versions are new.

## 2. The participant with no usable time in one condition

Time has n = 23 in the main analysis and n = 22 as pre-registered. In each, one participant has no
answer with a usable time in one condition, so they leave the time outcome only.

- **Computes:** for each participant and condition, the answers kept for accuracy and those kept
  for timing, and each participant-condition where no answer was kept for timing. For each of its
  answers, the rule that removed the time: `invalid_timing`, with the `duration_invalid` flag the
  browser logged, or `top_one_percent`, with the pooled cutoff. Also every timing exclusion, by
  participant and condition. Both analyses.
- The paper says "one participant", not the ID, unless the ID is needed.

## 3. T1's rubric, part by part

- **Computes:** over the T1 answers each analysis keeps, for each condition: n, the share credited
  with (a), (b) and (c), the share with `contradicts` = 1, and the share correct, which must equal
  T1's accuracy in item 1. The parts come from `coding/rubric_verdicts.csv`, joined on session and
  task. A skipped description counts as credited with no part and contradicting none, as the
  parts score counts it.
- **Check:** for every answer, a + b + c must equal `t1_parts` in `tasks.csv`, or the script stops.
- **3b, by form (kept):** the same table by form. Section 10 asks whether a part fails for nearly
  everyone, and T1's forms differ in size (Ukraine's collapse in A, Brazil's smaller fall in B).

## 4. Paas against a7

- **The two items** (`src/tasks.py`):
  - Paas: "In solving the preceding tasks, I invested:", nine points numbered 1 to 9, with words
    only at the ends ("very, very low mental effort", "very, very high mental effort").
  - a7: "Answering the questions took a lot of mental effort.", seven points, each labelled, from
    Strongly disagree to Strongly agree.
  - Both rise with effort, so they should move together.
- **Computes, for each analysis:**
  - the pairs: each participant-condition with both ratings (a pair missing one rating is counted,
    never filled in);
  - Spearman's rank correlation of Paas with a7, over all pairs and within each condition, as a
    coefficient only;
  - each participant's change from static to interactive on each scale (lower, same or higher), as
    a three-by-three table, and how many move the same way on both;
  - both scales rescaled to run from 0 to 1 (Paas: (x − 1)/8; a7: (x − 1)/6), and the spread of
    the gap between them.
- **A reversed-looking pattern, defined now:**
  - A pair is *opposed* when Paas is 7 or more and a7 is 3 or less, or when Paas is 3 or less and
    a7 is 5 or more.
  - A participant *looks reversed* when both of their pairs are opposed, or when one is and their
    two scales move in opposite directions between conditions.
  - Each such participant is listed with their four ratings in the gitignored output. The paper
    gives only counts.
  - Why these cut-offs: every a7 point is labelled, so 5 or more is agreement and 3 or less is
    disagreement. Paas has words only at its ends, so a rating must sit at least two points from
    its middle (5) to count as low or high.
- **Report only.** Nobody is excluded on this, and RQ3 is not re-estimated without anyone.

## 5. Paas and a7 by order

- **Groups:** interactive first (cells int1-A and int1-B) and interactive second (int2-A and
  int2-B).
- **Computes, for each analysis:**
  - for each group and condition, the n, mean, SD and median of Paas and of a7;
  - for each group, the mean and SD of the difference, interactive minus static;
  - both ratings by half (first or second), whichever condition the half held.

## 6. c1 against each participant's accuracy difference

- **The item:** c1, "Which charts helped you answer more accurately?", asked after the second
  half, with the options "The charts with controls", "The charts without controls" and "No
  difference".
- **Computes, for each analysis:**
  - each participant's c1 answer (or skip) beside their accuracy difference in items;
  - a cross-tabulation of c1 against the direction of that difference (interactive higher, equal,
    static higher);
  - for each c1 answer, the mean, median and range of the difference.
- c1 is a self-report set beside the scores, never used to check them.

## 7. The grading review

- **Computes:** each of Claude's draft sheets against its reviewed sheet, unit by unit, read with
  `analysis/coding.read_sheet`, which keeps only the codes and none of the text:
  - T1: `rubric_coder1_draft.csv` against `rubric_coder1.csv`, and participant 19's pair of sheets
    (`*_p19`), on a, b, c and `contradicts`;
  - RQ2: `coder1_draft.csv` against `coder1.csv`, and participant 19's pair, on `cites_values` and
    `compares_series`.
- **For each sheet and code:** the number of units, how many codes the review changed, and in which
  direction (0 to 1 or 1 to 0). For T1, it also counts how many verdicts and parts scores those
  changes moved. For RQ2, it splits the counts into T1 units and T2–T6 units (`key.csv`), since
  depth is reported both with and without T1.
- **`notes_uncertainty` is not compared.** It was dropped in review and left as drafted
  (`docs/grading-rules.md` §1, item 5), and the output says so.
- **The decision log:** the rows of `docs/grading-rules.md` §8, counted by sheet, with how many were
  amended in review and how many are moot. The file is read, never edited.
- **Not an agreement statistic.** The review started from the draft (§1, item 4).
- **7b, by condition (kept):** the changes by condition, from the key files. The grader knew the
  hypotheses, so this shows whether the review moved one condition's codes more than the other's.

## 8. Sensitivity re-estimates from the qualitative report

**None (Eduardo, 2026-11-17).** No re-estimate is computed, and the paper reports none.

The report (`data/study_logs/qual/qualitative_report.md`) proposed four, considered and not
taken. They are named here by section, not by participant:

- §1.2: the main results without the two participants in the joint session;
- §1.3: T3 without the participants who were run after an answer was first disclosed, on the items
  whose answers were given out;
- §1.4: RQ2 depth without the participant whose static justifications were shortened by
  instruction;
- §1.5: time without the task answers the recordings show were interrupted.

The report's §4.6 suggestion, a view by order, is item 5.
