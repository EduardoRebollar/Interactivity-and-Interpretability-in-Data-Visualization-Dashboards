# Paper outline

The plan for `paper/main.tex`: for every paragraph, the one claim it makes, its evidence, and how
strongly the claim can be made. Written 2026-11-17, after the confirmatory run (2026-11-11) and the
exploratory descriptives (`paper/exploratory.md`). Check each paragraph against its row before it
is final.

- **Numbers.** Every count, measurement, parameter and statistic is written as `\stat` with a key
  from `paper/numbers.tex` (for example `\stat{main/n}`), which `scripts/paper_numbers.py`
  generates. An undefined key stops the build, and a test checks every key cited here and in
  `main.tex`. Dates, section numbers and item
  names (T1–T6) are typed. Keys start `main/` (participant 19 reinstated, n = 24: reported first) or
  `pre/` (as pre-registered, n = 23: reported beside it).
- **Strength.** *Shows*: the data establish it, within this design and sample. *Consistent
  with*: the data fit it but do not establish it (any description, secondary, exploratory number,
  or anything qualitative). *Cannot say*: the design or the data cannot answer it, and the paper
  says so.
- **Significance.** Only the three Holm-family tests can be called significant, and none is.
  `numbers.tex` defines a Holm p (`/holm`) for those three alone.
- **Writer.** E: Eduardo. C: drafted by Claude, wrapped in `% BEGIN CLAUDE DRAFT` and
  `% END CLAUDE DRAFT`, for Eduardo to rewrite and disclose.
- **Sources.** `docs/study-design.md` (§ numbers below), `docs/grading-rules.md`,
  `docs/visual-spec.md`, `data/study_logs/derived/significance.txt` and `paper/sources/`.

## Changes from the proposal

| Proposal (`paper/sources/`) | This study | What the paper does with it |
|---|---|---|
| RQ1: does interactivity improve accuracy and reasoning depth, or primarily reduce perceived load? | Split into RQ1 accuracy, RQ2 reasoning depth, RQ3 cognitive load (study-design §1) | Uses the new numbering throughout. |
| RQ2: do directional change indicators change what users notice? | Not a research question. The year-over-year change is in the hover tooltip, in the interactive condition only: a drawn indicator would make the two figures differ (visual-spec §7.1). | Says its effect cannot be separated from interactivity's, and claims nothing about indicators. |
| RQ3: platform (Tableau against Dash) | Cut 2026-09-09: one platform, Plotly Dash | No platform claims. |
| 25+ participants, more diverse than the mini-project | 24, a convenience sample, mostly undergraduates; target `\stat{design/targetn}` | Reports the shortfall; no generalisation beyond the sample. |
| Order randomized | 2×2 counterbalancing by database sequence; `\stat{design/forms}` parallel forms | Describes it as counterbalanced. |
| Think-aloud set aside | Not in the protocol (§8), but asked for informally and audio-recorded | A deviation (`paper/deviations.md`). |
| Pilot with 3–5 participants; rubric pilot-tested by another person | One pilot session (2026-10-12), then none (§10) | Says so in Methods. |
| Rubric crediting accuracy, evidence, comparison and alternative explanations | T1 rubric (a, b, c, contradicts) and two RQ2 codes; `notes_uncertainty` dropped in review | Depth runs 0–2 (a deviation). |
| Likert ratings of clarity, confidence, ease of use and load | Paas mental effort (RQ3), a1–a9, b1–b4, c1–c3 | a7 beside Paas, never in its place. |
| Energy data | WHO/UNICEF childhood vaccination coverage, `\stat{design/yearfirst}`–`\stat{design/yearlast}` | |

## Rubric map and page budget

The comps rubric (`paper/sources/Final Paper Rubric (Fall 2026).pdf`): 6–10 pages, not counting
headings, figures, tables, references or appendices. Methods, Evaluation Metrics and Results and
Discussion together are at least half of it. At most about 200 words on languages and libraries,
and no discussion of code outside Appendix B. No images of text. References in every area except
the two appendices. **[TODO: the due dates.]**

| Rubric area | Section | Writer | Pages |
|---|---|---|---|
| Problem statement | 1 Introduction | E | 0.75 |
| Technical background | 2 | E | 0.75 |
| Prior work | 3 | E | 1 |
| Methods | 4 | C drafts 4.1–4.6 (4.1, 4.2 on 2026-11-18), for E to rewrite | 1.5 |
| Evaluation metrics | 5 | C drafts 5.1, 5.2 (5.2 on 2026-11-18), for E to rewrite | 1 |
| Results and discussion | 6, 7, Limitations | C drafts 6 and Limitations (2026-11-18), 7 to come; for E to rewrite | 2.5 |
| Ethical considerations | 8 | E | 0.75 |
| Conclusion | 9 | E | 0.25 |
| Replication instructions | Appendix A | C | not counted |
| Code architecture overview | Appendix B | C | not counted |
| Use of AI tools | after 9 | C | |

That puts 5 of 8.5 pages in Methods, Evaluation and Results.

## Abstract (E)

| Claim | Evidence | Strength |
|---|---|---|
| The question: does interactivity improve interpretation, or make it feel easier? | §1 | — |
| What was done: `\stat{main/n}` participants, both versions, `\stat{design/totalitems}` items on `\stat{design/charttypes}` chart types, the two versions identical except for interactivity, one platform | §2, §4 | shows |
| Accuracy differed by `\stat{main/accuracy/items/est}` items of `\stat{design/items}` (95% CI `\stat{main/accuracy/items/ci}`), ruling out an advantage of one item or more | `main/accuracy/items`, `main/tost` | shows |
| A difference in mental effort was not detected (`\stat{main/paas/est}`, CI `\stat{main/paas/ci}`) | `main/paas` | cannot say |
| Interactive sessions took longer (×`\stat{main/log_time/est}`; exploratory) | `main/log_time` | consistent with |
| Participants preferred the controls, in a sample that knew the researcher | `main/c2/controls` | consistent with |

## 1. Introduction (E)

| ¶ | Claim | Evidence | Strength |
|---|---|---|---|
| 1 | Dashboards now inform clinical, workplace and public decisions, and design choices change the conclusions people draw. | Proposal refs: Murphy, Xie, Marler, Cai, Alieva, Padilla, Romano | literature |
| 2 | Interactivity is assumed to help reasoning, but it may only make interpretation feel easier, which matters if confidence outruns accuracy. | Yi, Dimara, Lam 2008, Hullman; the mini-project (6 participants) | consistent with |
| 3 | This study compares a static and an interactive version of the same charts, identical in every visual respect, within subjects. | §2, visual-spec | shows (design) |
| 4 | Preview of the findings, in §6's wording, never stronger. | §6 rows below | as in §6 |
| 5 | Scope: one platform, `\stat{main/n}` participants from one campus, one dataset. | §1, §6.2 | — |

## 2. Technical background (E)

Definitions for a CS senior who has not taken HCI or statistics. No study results here.

| ¶ | Content | Sources |
|---|---|---|
| 1 | Interaction techniques: filtering, sorting, focusing a line, details on demand (hover), zooming | Yi, Munzner 2014 |
| 2 | Interpretability against usability; cognitive load; mental effort, and the Paas scale | Ware, Castro-Alonso, Paas 1992 (VERIFY) |
| 3 | Within-subjects designs, order and practice effects, counterbalancing, parallel forms | Greenwald, Charness |
| 4 | The analysis: a two-period crossover analysis, Holm's correction, equivalence by two one-sided tests at a bound (`\stat{design/boundprop}`, one item), dz, a Wilcoxon signed-rank and a permutation check, and what a 95% and a 90% interval mean | Jones and Kenward, Holm, Schuirmann, Lakens, Wilcoxon, Pratt (all VERIFY) |

## 3. Prior work (E)

The proposal's five themes (proposal §3), each ending with what it changed in this study:

| ¶ | Theme | Proposal refs | What it changed here |
|---|---|---|---|
| 1 | Interaction driving reasoning | Yi, Dimara | Reasoning depth as an outcome (RQ2) |
| 2 | Sensemaking, load, visual complexity | Pirolli, Klein, Ware, Hullman, Etemadpour, Yoghourdjian, Lam 2008 | Effort measured (RQ3); line charts drawn as a tangle the controls cut through |
| 3 | User variation in interpretation | Quadri, Choe | A written item (T1) scored by rubric, not one answer |
| 4 | Accessibility | Srinivasan, W3C | WCAG floors and colour-blind separation; no screen-reader support |
| 5 | Evaluating interpretability | Amar, Lam 2012, North, Chang, Saraiya, Carpendale | Low-level task types; objective and subjective measures together |

**[TODO, E: any study that compares static and interactive charts head to head goes here; mark it
`% VERIFY` in `references.bib`.]**

## 4. Methods

| § | ¶ | Claim | Evidence | Strength | Writer |
|---|---|---|---|---|---|
| 4.1 Design | 1 | Within subjects, 2 conditions × 2 forms, counterbalanced by database sequence; each participant saw both conditions and both forms, never a form twice; `\stat{design/items}` scored items per condition plus a practice | §2; cells `\stat{main/cells/int1-A}`, `\stat{main/cells/int1-B}`, `\stat{main/cells/int2-A}`, `\stat{main/cells/int2-B}` | shows | C draft 2026-11-18 |
| 4.2 Participants | 1 | `\stat{main/sample/n}` people, recruited and run in person on campus, many of them friends or co-workers of the researcher; collection closed one short of `\stat{design/targetn}` | §10; qualitative report §1.7 [UNVERIFIED] | shows | C draft 2026-11-18 |
| | 2 | Mostly undergraduates (no count: the rest are fewer than five); age median `\stat{main/sample/age/median}`, range `\stat{main/sample/age/min}`–`\stat{main/sample/age/max}`; fields: CS, math or statistics `\stat{main/sample/field/cs}`, health `\stat{main/sample/field/health}`, natural sciences `\stat{main/sample/field/natural}`, other `\stat{main/sample/field/other}`; read charts weekly or more `\stat{main/sample/readcharts/weekly}` | `numbers.tex` (groups of five or more only, main analysis only) | shows | C draft 2026-11-18 |
| 4.3 Apparatus | 1–4 | The two versions draw the same figure; the only difference is interactivity (an image, or hover and the controls under the chart). Five chart types, one dataset, one palette checked for contrast and colour-blind separation. | visual-spec §1, §4, §7; `\stat{design/charttypes}`, `\stat{design/palette}`, `\stat{design/cvdfloor}` | shows (by construction, tested) | C |
| 4.4 Tasks | 1–3 | Six items per form, each pairing a chart type with an affordance; two parallel forms; every key survives a reader without hover (the acceptance rule) | §4; `\stat{design/floor/position}`, `\stat{design/floor/colour}`, `\stat{design/floor/dots}` | shows (design) | C |
| 4.5 Procedure | 1–3 | The session sequence, instructions before both halves, one practice, the full-screen request, the researcher script, and how it differed in practice | §8; `paper/deviations.md` | shows | C |
| 4.6 Deviations | table | Every deviation from the pre-registration and the protocol, dated, before or after the tests | `paper/deviations.md` | shows | C (table, caption) |

## 5. Evaluation metrics

| § | ¶ | Claim | Evidence | Strength | Writer |
|---|---|---|---|---|---|
| 5.1 Measures | 1 | RQ1: proportion correct over T1–T6 per participant and condition; a skip scores incorrect; T1 by rubric | §7 | shows (definition) | C |
| | 2 | RQ2: depth per justification, `cites_values` + `compares_series` (0–2), T2–T6; T1 descriptions coded as well | §7; grading-rules §1 | shows | C |
| | 3 | RQ3: Paas mental effort (1–`\stat{design/paaspoints}`), after each half; a7 beside it | §6.1 | shows | C |
| | 4 | Secondaries: time (browser clock), the survey, control use from the logs, hover by self-report (b4) | §6.1, §7 | shows | C |
| | 5 | Exclusions, fixed in advance | §7; `\stat{design/fastseconds}` s, top `\stat{design/trimpercentile}`th percentile | shows | C |
| 5.2 Analysis | 1 | Two analyses: participant 19 reinstated (main), and as pre-registered beside it | §7 Inference | shows | C draft 2026-11-18 |
| | 2 | Crossover t (difference regressed on half and form); Wilcoxon; a permutation check on accuracy; Holm across the `\stat{design/family}` tests at α `\stat{design/alpha}`; an equivalence test at one item | §7 Inference | shows | C draft 2026-11-18 |
| | 3 | What 24 can detect: dz `\stat{main/sensitivity/single}` alone, `\stat{main/sensitivity/holm}` at Holm's first step (80% power) | `main/sensitivity` | shows | C draft 2026-11-18 |
| | 4 | The plan was written after looks at the data (2026-11-03, the poster), before any test; the tests ran once | §10 | shows | C draft 2026-11-18 |
| | 5 | Metrics considered and not used: NASA-TLX, eye tracking, insight-based evaluation, a full think-aloud | §6.1; proposal §4.2, §5 | — | C draft 2026-11-18 |

## 6. Results (C draft 2026-11-18, for E to rewrite)

Tables and figures are generated (list at the end). Every row is given for the main analysis and,
beside it, as pre-registered.

| § | Claim | Evidence | Strength |
|---|---|---|---|
| 6.1 Sample, exclusions | `\stat{main/n}` analysed; as pre-registered `\stat{pre/n}`, the empty duplicate session taking out `\stat{pre/excl/incomplete_session/rows}` answers. `\stat{main/excl/invalid_timing/rows}` times lost to page reloads (`\stat{main/timing/invalidparticipants}` participants) and `\stat{main/excl/top_one_percent/rows}` trimmed, so time has n = `\stat{main/log_time/n}`. No degraded sessions (`\stat{main/degraded}`). | `main/excl`, `main/timing` | shows |
| 6.2 RQ1 | Interactivity changed accuracy by `\stat{main/accuracy/items/est}` items of `\stat{design/items}` (95% CI `\stat{main/accuracy/items/ci}`; proportion `\stat{main/accuracy/est}`, CI `\stat{main/accuracy/ci}`, Holm p `\stat{main/accuracy/holm}`). | `main/accuracy` | cannot say (a difference smaller than one item) |
| | Its 90% CI, `\stat{main/tost/ci}`, lies inside ±`\stat{design/boundprop}`: the data rule out an advantage of one item or more (`\stat{main/tost/verdict}`). Never "accuracy did not change". | `main/tost` | shows |
| | Checks agree: Wilcoxon p `\stat{main/accuracy/wilcoxon}`, permutation p `\stat{main/accuracy/permutation}`. Every item right: static `\stat{main/ceiling/static}`, interactive `\stat{main/ceiling/interactive}` of `\stat{main/ceiling/of}`. | `main/accuracy`, `main/ceiling` | shows |
| | As pre-registered: `\stat{pre/accuracy/items/est}` items (CI `\stat{pre/accuracy/items/ci}`), Holm p `\stat{pre/accuracy/holm}`, also equivalent (`\stat{pre/tost/ci}`). The conclusion does not differ. | `pre/...` | shows |
| | §7's fallback sentence ("the effect on accuracy is unclear") does not fit: accuracy is the settled part, effort the unclear one. Say what happened. | — | — |
| 6.3 By item | T5 at ceiling in both conditions (`\stat{main/item/T5/static/pct}`%, `\stat{main/item/T5/interactive/pct}`%); T2 and T4 near it (`\stat{main/item/T2/static/pct}`%, `\stat{main/item/T4/static/pct}`% static); T1 near the floor (`\stat{main/item/T1/static/pct}`%, `\stat{main/item/T1/interactive/pct}`%). Most of the accuracy contrast rides on T3 and T6 (`\stat{main/item/T3/static/pct}`% against `\stat{main/item/T3/interactive/pct}`%; `\stat{main/item/T6/static/pct}`% against `\stat{main/item/T6/interactive/pct}`%). A limitation on what the test could detect, not on its own an explanation of the result. No test per item. | `main/item` | consistent with |
| 6.4 RQ2 | Depth: `\stat{main/depth/est}` (CI `\stat{main/depth/ci}`, Holm p `\stat{main/depth/holm}`): not detected. Secondaries are estimates: with T1 `\stat{main/depth_with_t1/est}`; `cites_values` `\stat{main/cites_values/est}` (CI `\stat{main/cites_values/ci}`); `compares_series` `\stat{main/compares_series/est}`. As pre-registered, `cites_values`' interval excludes zero; do not highlight it, since it moves with one participant. | `main/depth`, `main/cites_values` | cannot say |
| 6.5 RQ3 | Paas: `\stat{main/paas/est}` (CI `\stat{main/paas/ci}`, Holm p `\stat{main/paas/holm}`, dz `\stat{main/paas/dz}`): not detected, never "no effect". The design could detect dz `\stat{main/sensitivity/holm}` at Holm's first step. a7, beside it and never in its place: static `\stat{main/survey/a7/static/mean}`, interactive `\stat{main/survey/a7/interactive/mean}` (descriptive). RQ3's "rather than": `\stat{main/rq3/verdict}`. | `main/paas`, `main/survey/a7` | cannot say |
| 6.6 Time (exploratory) | Interactive halves took ×`\stat{main/log_time/est}` as long per task (CI `\stat{main/log_time/ci}`), about `\stat{main/log_time/pct}`% longer: the clearest effect in the data, labelled exploratory. Not promoted to a main test: choosing the test by its result. Geometric mean per task: static `\stat{main/time/static/seconds}` s, interactive `\stat{main/time/interactive/seconds}` s. | `main/log_time`, `main/time` | consistent with |
| 6.7 T1, the overload | T1 correct: static `\stat{main/t1rubric/all/static/correct}`%, interactive `\stat{main/t1rubric/all/interactive/correct}`%; the four extra controls used by `\stat{main/t1extra/users}` of `\stat{main/t1extra/n}`. A T1 difference belongs to the overloaded interface, never to interactivity alone. | `main/t1rubric`, `main/t1extra` | cannot say (interactivity on T1) |
| 6.8 Controls, hover | Logged use: T2's sort by `\stat{main/controls/T2/sort}` of `\stat{main/controls/T2/n}`; the key on T3 by `\stat{main/controls/T3/key}`, on T5 by `\stat{main/controls/T5/key}`; T1's chart set to start in 2000 or later by `\stat{main/from2000/T1/either}`. Hover is not logged: b4 (self-report) `\stat{main/survey/b4/interactive/mean}` of `\stat{design/likertpoints}`. No logged control never means no interaction. | `main/controls`, `main/survey/b4` | consistent with |
| 6.9 Survey, preference | a2–a6 ran higher with controls (for example a6 `\stat{main/survey/a6/static/mean}` against `\stat{main/survey/a6/interactive/mean}`); `\stat{main/c1/controls}` of `\stat{main/n}` said the controls helped them answer more accurately, and `\stat{main/c2/controls}` preferred them. Described with their context: many participants were friends or co-workers, the purpose was described aloud in some sessions [UNVERIFIED count], and everyone knew the researcher built the system. | `main/survey`, `main/c1`, `main/c2` | consistent with |
| 6.10 Exploratory | Post hoc (`paper/exploratory.md`). Part (c) of T1's rubric fails most: static `\stat{main/t1rubric/all/static/c}`%, interactive `\stat{main/t1rubric/all/interactive/c}`%. Paas and a7 agree weakly (ρ `\stat{main/paasa7/rho/all}`); a7 fell for `\stat{main/paasa7/a7lower}` of `\stat{main/paasa7/participants}`, Paas for `\stat{main/paasa7/paaslower}`; `\stat{main/paasa7/reversed}` participants' ratings look like a reversed Paas scale (report only, nobody excluded). Of the `\stat{main/c1acc/controls/n}` who said the controls helped their accuracy, `\stat{main/c1acc/controls/higher}` scored higher with them. | `main/t1rubric`, `main/paasa7`, `main/c1acc` | consistent with |
| | The grading review changed `\stat{review/t1/changed}` of `\stat{review/t1/codes}` T1 rubric codes (`\stat{review/t1/changed/interactive}` of them on interactive answers) and `\stat{review/rq2/changed}` of `\stat{review/rq2/codes}` RQ2 codes; the decision log gained `\stat{rules/all}` rules. Not an agreement statistic. | `review`, `rules` | shows (counts) |
| 6.11 Qualitative | Themes, each with an exemplar (`paper/private/quotes.md`), never with prevalence: filtering clutter on the line charts; the key read as a reference, not a control; exact values changing the method on T3; item wording behind errors. Counts of talk, one AI-assisted coder not blind to version: [UNVERIFIED] until the spot-check. | `data/study_logs/qual/` | consistent with |

## 7. Discussion (E)

| ¶ | Claim | Strength |
|---|---|---|
| 1 | Accuracy is settled within one item; effort is unclear; interactive work took longer (exploratory); the controls were preferred, in a sample primed to like them. | as in §6 |
| 2 | Set against the mini-project: comparable accuracy and longer time again; its lower load was not detected with Paas, though a7 moved further (descriptive). | consistent with |
| 3 | Why accuracy might not move: items at ceiling and floor, the key left undiscovered, hover unlogged. Each limits what could be detected; none on its own explains the result. | consistent with |
| 4 | What a designer can take from it, without generalising beyond the sample or the platform. | consistent with |

## Limitations (C draft 2026-11-18, for E to rewrite)

Each with its source:
- a convenience sample of `\stat{main/n}`, mostly undergraduates, many of them friends or
  co-workers, and one short of the target (§10);
- one platform, so no platform claims;
- one grader, with codes drafted by Claude (`paper/deviations.md`);
- the inference plan written after looks at the data (§10);
- T1's overload confounds the item (§4);
- items at ceiling and floor (6.3);
- forms not equivalent: T2 and T4 ask different questions per form, T1's falling lines differ in
  size, T6 runs in opposite directions (§4, Matching the forms);
- hover unlogged, and the change in the tooltip inseparable from interactivity;
- `\stat{main/windows/compact}` of `\stat{main/windows/participants}` windows were 800 px tall or
  less despite the full-screen request, so some interactive cards scrolled;
- the protocol as run differed from §8: informal think-aloud and recording, researcher input,
  disclosures in debriefs, a joint session (`paper/deviations.md`);
- the qualitative material is unverified.

## 8. Ethical considerations (E)

From the ethics paper (`paper/sources/`), updated:
- consent stored apart from the data;
- AI tools used with participant text (the sheets carry no identifying data, and neither approved
  form mentions AI);
- the recordings: **[TODO: HSRRC's approval, its date and how it was given]**;
- unequal data quality behind the WHO/UNICEF estimates, which the source line on every chart
  states;
- accessibility (WCAG floors, colour-blind separation, keyboard operation, no screen reader);
- a sensitive domain;
- the researcher as the builder of what is evaluated.

## 9. Conclusion (E)

The question, what the data settle and what they leave open, and what the next study would change.

## Appendices and statements (C)

- **A. Replication instructions:** software and versions, clone to app, the analysis pipeline,
  what needs the study data, building the paper.
- **B. Code architecture overview:** the components, the single condition switch, the data flow
  from events to `numbers.tex`, and where to extend.
- **Use of AI tools:** where Claude and Whisper were used, factual, for Eduardo to edit.

## Open items (also marked in `main.tex`)

- **The supervisor's answers** to the nine questions in §10. They arrive after the run, so any
  answer that changes the plan is a deviation.
- **HSRRC's approval of the recordings:** its date and how it was given.
- **The comps due dates.** The length and the template are known.
- **The qualitative spot-check** (qualitative report §8). Until it is done, every qualitative count
  is [UNVERIFIED].
- **Where the data can be found.** The rubric asks for the raw data in the repository; rule 5,
  `.gitignore` and the IRB forms keep it out. Eduardo to decide what the paper says.
## Tables and figures (approved and built 2026-11-18)

All generated by `scripts/paper_figures.py` into `paper/tables/` and `paper/figures/`; captions
and labels live in `main.tex` (Claude's drafts). Tables cite every number as `\stat`, and the
script refuses to write if `numbers.tex` is not current. Figures are pgfplots, drawn from
coordinates the script writes, so their text is real text and no Python plotting library is added.
Colours come from `src/config.py` (static `#D55E00`, interactive `#0072B2`, ink `#241C18`, grid
`#BBAEA4`), each checked against white by `src/contrast.py` (3:1 for marks, 4.5:1 for text). Each
gives the main analysis and, where the rules call for it, the pre-registered analysis beside it;
Tables 4 and 5 as pre-registered are in Appendix C. Figure 1 is printed by headless Chrome from the
app's own screen code (`--versions-only` needs no study data). LaTeX numbers floats by position,
so the deviations table is Table 1 in the PDF and the rest follow from there.

| | Shows | From |
|---|---|---|
| Table 1 | The three main tests and the equivalence test, both analyses: n, estimate (95% CI), t (df), p, Holm p, dz; the 90% CI and the verdict | `significance.txt` |
| Table 2 | The secondaries, both analyses: estimate (95% CI), p, no Holm column; headed "exploratory" | `significance.txt` |
| Table 3 | Exclusions by rule, both analyses | `paper_descriptives` report tables |
| Table 4 | Accuracy (% correct) and median time by item and condition, main analysis (as pre-registered in Appendix C) | `report_main.txt` tables |
| Table 5 | The survey: a1–a9 by condition, b1–b4, c1 and c2 counts | report tables |
| Table 6 | The deviations (hand-written from `paper/deviations.md`, not generated) | `deviations.md` |
| Figure 1 | One item in both versions, as participants saw it (a screenshot of A-T6 from `/preview` in headless Chrome) | the app |
| Figure 2 | Each participant's accuracy difference in items, with the estimate, its 95% and 90% CIs, and the ±1-item band | `differences_by_participant.csv`, `significance.txt` |
| Figure 3 | Paas and a7 per participant, static against interactive, with Paas's estimate and CI | `scores.csv`, `paas_a7_pairs.csv` |
| Figure 4 | Accuracy by item and condition, as dots | report tables |
| Figure 5 | Each participant's time ratio on a log scale, with the estimate and CI, marked exploratory | `differences_by_participant.csv` |
