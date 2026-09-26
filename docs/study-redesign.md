# Study redesign brief

The design handoff in `docs/design-handoff/` is the **new version of the study**. It sets the look,
the content, the behaviour and the flow. This is a study change, not a restyle: the items,
controls, surveys, demographics, consent text and logging all change. Nothing has been collected
yet, and HSRRC has not approved the old version, so the change lands before the pilot.

Read this whole file before each phase.

## 1. Precedence

1. **The handoff wins.** When its files disagree with each other, use this order:
   - `assets/study.css`
   - `Study UI Screens.dc.html` (screen 5 first; the markup and the data in `renderVals()`,
     `taskVals()`, `auBuild()`, `auVals()` and `surveys`)
   - the behaviour notes in the handoff `README.md`
   - `Study UI Spec.dc.html`
   - `Study UI Style Spec.md`
   - `Study UI Components.dc.html`

   §3 settles the contradictions found so far.
2. **The repo fills gaps only**, where the handoff says nothing:
   - Form B (but see §4)
   - each item's vaccine, years and drawn data
   - chart styling inside the plot (`config.py`, `figures.py`, `visual-spec.md` §1–6)
   - the log record format and its sinks, spooling and recovery
   - counterbalancing and ID registration
   - how answer keys are derived
3. **CLAUDE.md's hard constraints still hold** unless this brief changes them:
   - one condition boolean, consulted only in `graph_config`
   - byte-identical figure JSON across conditions
   - missing data stays missing
   - no pandas in runtime modules, and no answer key under `src/`
   - `analysis/` never ships
   - the consent record stays apart from study data
   - the signature pad keeps its keyboard alternative
   - no new dependencies without asking

   If the handoff seems to require breaking one of these, stop and ask.

## 2. What changes

| Area | New (from the handoff) | Today |
|---|---|---|
| Flow | Consent → ID → instructions → practice → **practice complete** → Part 1 → survey → break → instructions → Part 2 → survey → **About you** → finished | About you comes right after the ID; there is no practice-complete screen |
| Stepper | 7 steps: Consent, Practice, Part 1, Break, Part 2, About you, Finished (display only, `aria-current="step"`) | None |
| Form A items | A sixth option per item: T1 adds 2012; T2 Nigeria; T3 Nigeria; T4 India; T5 splits "4 or more" into "4" and "5 or more"; T6 adds 2000-2003. T1 drops the World line | Five options per item |
| Map item (T5) | The 13 countries in `taskVals()`'s `MAP13`, which adds Guinea, Senegal and South Sudan (outside the locked scope) | Another set of 13 |
| Task copy | Justification label, instructions (4a/4b, 9a/9b), finished screen, all from the Screens file (typos per §5) | `tasks.py` and `layout.py` copy |
| Controls, interactive only | Country chips with flags on every chart type; line: View (as listed / by coverage) + Show all; bar: Sort (A–Z / High → low / Low → high); heatmap: Sort rows (Default / Lowest value / Average); map: Highlight "Below [n] %"; Reset view in the hint row on every chart; hint text from `HINT` | Line: chips, sort, Show all. Bar: two-way sort. Map: range slider. Scatter and heatmap: hover hint only |
| Line charts | A legend: click hides or shows a country, double-click shows only that one. Clicking a line isolates it; clicking again or Show all restores | End labels, no legend |
| Chart size | 1050 × 520, fixed | 520 tall |
| Survey | a1–a9 (7-point) after each condition; b1–b3 after the interactive condition only; c1–c3 comparison after the second half; one question per page with a section rail | Paas (9-point) + three Likert items, one page |
| About you | The 10 items in `auBuild()`: pointer device, age in years, role, field, chart use, chart making, stats course, tools matrix, topic familiarity, health background. One per page with a section rail, at the end | Four broad-category items after the ID |
| Consent | The screen 1 text: 40 minutes, the new sentence on vaccination as a sensitive topic, "Neon (a managed PostgreSQL service)" | `consent.py` as submitted |
| Blocking error | S4 replaces the screen when responses can't be saved | Spools and continues |
| Logging | Every `data-log` control is logged (`filter`, `sort`, `legend-isolate`, `threshold`, `reset`) | Schema v8 |
| Look | Everything in `study.css` | Inline styles |

## 3. Contradictions inside the handoff

These are settled as follows.

1. **Instructions vs screen 5.** The 9b instructions say only line, bar and map charts have
   controls and that the map has a "coverage range". Screen 5 puts controls on every chart and a
   "Below [n] %" box on the map. Screen 5 wins, and the instruction sentences get rewritten to
   describe screen 5's controls. Show Eduardo the new wording before it ships.
2. **README "Submit requires an answer and a sentence" vs 9a/9b "You may skip any question".**
   Skipping stays, behind the existing `window.confirm` (IRB item 10).
3. **Stepper.** Use the Screens order; the Components sheet is older.
4. **About you.** Use screen 10 (rail, one question per page). The Spec's `qgrid` hook is for the
   old four-question version. The caption says "five steps" but the data has four sections; go by
   the data.
5. **Controls on scatter and heatmap.** Style Spec.md omits them and screen 5 shows them. Screen 5
   wins.
6. **Consent.** Screen 1's text is final; S3 has a placeholder. The typeface and size come from the
   `.sheet` rule in `study.css`.
7. **Chip list.** The mockup builds non-line chips from the answer options, but the bar and heatmap
   draw more countries than that. Default to one chip per entity drawn on the chart, and flag it in
   the plan.
8. **S4 vs spooling.** The handoff doesn't mention spooling. Keep the retry-and-spool path and show
   S4 only when a response can't be saved anywhere (the database and the spool both fail).
9. **`TEMP`, the grey chart boxes and the flagcdn URLs** are placeholders. Use the real
   participant ID, the Plotly figures, and flags bundled under `src/assets/` by a script, as
   `geo_africa.js` is, so nothing loads from a CDN mid-task.

## 4. Open decisions: ask Eduardo in phase 1, don't guess

1. **Form B.** The handoff has Form A only. Parallel forms need B to get a sixth option per item
   too. Propose one per item (each passing the acceptance rule) for Eduardo to approve, or wait
   for his.
2. **Paas.** The new survey drops the 9-point Paas item, which is RQ3's measure in
   `study-design.md` §6 and in `score_study.py`; a7 is a single 7-point item. Ask whether to drop
   Paas or keep it as the first survey question.
3. **Map item.** Confirm (a) the "Below [n] %" control, which Eduardo rejected on 2026-09-23
   because a participant can type the item's own threshold, and (b) the new country set, which
   means adding three countries to the scope and the data.
4. **Acceptance rule.** If a handoff item fails the rule in `analysis/keys.py`, report it and stop.
   Don't re-tune it.

## 5. Copy fixes to apply (Eduardo can strike any)

- 4a/4b: "Answer the question; then in one sentence, how you decided." → "Answer the question,
  then explain in one sentence how you decided."
- Justification label: "In one sentence, describe why you chose your answer?" → end with a period.
- A-T3: "improved the most; the dot furthest above the diagonal?" → keep today's em dash:
  "improved the most — the dot furthest above the diagonal?"

## 6. Integrity requirements

- **Docs first.** CLAUDE.md requires `study-design.md` (§4 items and keys, §6 measures, the flow)
  and `visual-spec.md` (a page-chrome section, §5 size, §6 legend, §7 controls) to change before
  the code. Show the diffs and wait.
- **IRB.** Add every change the IRB paperwork must reflect to `study-design.md` §10:
  - the consent form (40 minutes, the risk sentence, the Neon wording)
  - the questionnaire for item 18 (instructions, survey, demographics)
  - item 17, because age in years is not a broad category
  - the measures, if Paas goes

  Tell Eduardo whether `irb/questionnaire.pdf` must be re-exported.
- **Consent.** Update `consent.py` `SECTIONS` from screen 1 and re-pin the hash in
  `tests/test_consent.py`. `APPROVED` stays False.
- **Keys.** Re-derive a key for every changed item. Re-check the position rule (no answer position
  holds more than a third of the keys) with six options. Options keep the ordering conventions
  (countries alphabetical, years calendar).
- **Conditions.** Charts and page chrome are identical in both conditions. Only the controls strip
  and hint row are interactive-only, and they sit under the chart, so the chart is at the same
  position in both. The legend exists in both figures; `staticPlot` keeps it inert in static.
  `tests/test_conditions.py` passes unedited.
- **Missing data.** The missing-data caption (`gap_note`) appears in both conditions, directly
  under the chart.
- **Logging.** Bump `SCHEMA_VERSION` to 9 and write a CLAUDE.md entry. Reuse existing event names
  where the meaning matches and add new ones for the new controls and survey. Update
  `init_db.py`, `analysis/` (reshape, report, scoring, viewer) and `scripts/export_questionnaire.py`.
- **Scope.** If the map's new countries are confirmed, update the scope in CLAUDE.md and
  `config.py`, re-download, regenerate `data/deploy/coverage.csv`, and update the row count.
- **Tests.** Update tests that encode the old study (`test_tasks`, `test_flow`, `test_consent`,
  `test_questionnaire`, `test_scoring`, `test_analysis`, `test_logging`). Don't weaken anything
  unrelated. The whole suite stays green.

## 7. Styling rules

- Copy `docs/design-handoff/assets/study.css` to `src/assets/study.css` unchanged. If Dash's DOM
  can't match a selector through `className`, `labelClassName` or `inputClassName`, put the
  smallest possible rule in `src/assets/zz-overrides.css`, comment why, and report each one.
- Replace the inline style dicts in `layout.py` with the handoff's classes.
- Don't ship `.is-hover`, `.is-focus` or `.is-selected`, or `data-checked` / `data-value`. Real
  states come from `:hover`, `:focus-visible`, `:checked` and `disabled`.
- Reading the `.dc.html` files: `<x-dc>`, `<helmet>`, `<sc-for>`, `<sc-if>` and `{{ }}` are
  template syntax, filled from the script block at the bottom. The following are not part of the
  app: the grey canvas, the numbered badges and captions, the violet "790 · fold" lines, the
  Practice/Q1/Static/Interactive buttons, and `support.js`. Unused data (`demo`, `instr`, `bgQs`,
  `vizQs`, `topicQs`, `toolCols`, `formNav`, `countriesF*`, `ticks`, `marks`) isn't a source.
- Run new colour pairs through `src/contrast.py`. The Submit-while-saving fill `#91796E` stays: the
  button is disabled at that moment, and WCAG 1.4.3 exempts inactive controls.

## 8. Done means

- Each screen is captured in headless Chrome at a 1440 × 790 viewport and compared with its
  `screenshots/*.png`, which are 1440 × 900 artboards with the fold at 790. List every difference
  other than chart content and Form B.
- On the task screen, Submit is above the fold with a one-line question. `.is-compact` switches on
  at a window height of 800 or less, and the card fits at 1366 × 768.
- Every control is keyboard-operable, and focus rings appear only for keyboard focus.
- Run four full sessions in headless Chrome, one per counterbalancing cell:
  - every derived key matches what was logged
  - every new control logs its event
  - interaction events appear only in the interactive condition
  - the new survey and demographics are recorded
- The full suite is green.

## 9. Phases

Stop after each phase, report, and wait.

1. **Plan.**
   - Ask the §4 questions.
   - Map every mockup screen and state to the code that will render it.
   - List any contradictions not in §3.
   - Draft the `study-design.md` and `visual-spec.md` diffs and the §10 IRB list.
   - List the tests that will change.
2. **Instrument, no UI.** `tasks.py` (Form A from the handoff, Form B per §4), keys and the
   acceptance rule, scope and data if confirmed, `flow.py`, `consent.py` and its hash, the survey
   and demographics definitions, and logging v9. Tests green.
3. **Foundation.** `study.css` and the overrides, header and stepper, backgrounds, compact mode.
4. **Task screen.** Line (chips, flags, legend, View, Show all, Reset), then bar, heatmap, scatter
   and map, then static, S1, S5 and compact.
5. **Short screens.** Declined, ID (with S2), instructions, practice complete, break, finished.
6. **Consent** and S3.
7. **Survey and About you.**
8. **Final pass.** S4, the analysis pipeline, the screenshot comparison, keyboard, four sessions
   and the full suite.
