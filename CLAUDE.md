# CLAUDE.md

Context and constraints for this project. Read this before proposing changes or writing code.

## Project

Senior comprehensive project (Occidental College, CS). Empirically compares static vs. interactive
data visualization dashboards for **interpretability** of time-series data, using WHO/UNICEF
childhood vaccination coverage data (1980–2024). Single platform: a Plotly Dash implementation, this
repo, fully instrumented.

The study measures whether interactivity improves interpretation accuracy and reasoning depth, or
primarily reduces perceived cognitive load. Participants (target n ≥ 25) complete the same tasks on
both a static and an interactive version in a within-subjects design.

**Cross-platform comparison was cut (2026-09-09.)** The project originally planned a second Tableau
Public build so findings could be cross-checked for platform dependence. That was dropped: a
hand-built second platform is a large amount of work whose visual parity with the Dash build could
never be guaranteed, and the considered alternative — using Our World in Data's own published charts
as the second platform — cannot be instrumented, because their charts run cross-origin and
participant interactions inside them are invisible to this code. The study therefore answers the
narrower question, on one platform. **Write-ups must not claim platform independence.**

## Hard constraints

These are methodological requirements, not preferences. Do not relax them without asking.

### Visual design is held constant

- Chart types, color palette, axis scales, fonts, layout, and spacing must be identical between the
  static and interactive versions.
- A visual change applies to both conditions or to neither. There is no version that is allowed to
  look different.
- Any deviation breaks the core methodological claim that observed differences are attributable to
  interactivity, not aesthetics.
- `docs/visual-spec.md` is the source of truth. Change the spec first, then the code.
- `docs/study-redesign.md` — the redesign brief; read before any UI or study-content work.
- `docs/chart-handoff/` — the charts' visual style (2026-10-11), drawn on Form A. It sets the look
  only; which countries and years a chart shows is `docs/study-design.md` §4.


### Static vs. interactive is a single toggle

- Exactly one boolean separates the conditions, and it is consulted in exactly one place:
  `graph_config(interactive: bool)` in `src/figures.py`. Its second argument, the chart type
  (2026-09-27), is not a switch: it only limits scroll zoom to the line chart.
- **`build_figure()` takes no `interactive` argument at all.** The chart is identical in both
  conditions *by construction*, not by discipline — interactivity is a property of how the figure is
  rendered, not of the figure. `tests/test_conditions.py` asserts the two conditions produce
  byte-identical figure JSON.
- Interactive-only features (the design handoff, 2026-09-25): country chips and Reset view on
  every chart; on the line charts the Years slider (which replaced the View reorder, 2026-10-12),
  Show all, focusing a line (the others fade; until 2026-10-12 they were hidden) and the
  year-over-year change in the tooltip (the clickable legend went with the chart handoff,
  2026-10-11); sorting the bar chart and the heatmap's rows; on the scatter, heatmap and map, a
  click on a colour in the key highlights its band (replacing the map's "Below [n] %" box,
  2026-10-12); hover on every chart; and on T1 alone, both forms, four controls it does not need,
  named to participants nowhere (Coverage, Order, Regions, Show: the overload, 2026-10-12). All
  are built and defined in `docs/visual-spec.md` §7. All sit under the chart except the key's
  buttons, an overlay standing over the key in the chart's own box. That overlay is no part of the
  figure, so the chart stands in the same place, and is the same figure, in both conditions.
- **Five chart types, one builder each** (2026-09-23): line, bar, scatter, heatmap, map. The rule
  above holds for every one — `tests/test_conditions.py` checks byte-identical JSON for every task.
- **Year-over-year change lives in the hover tooltip, not on the chart** (`visual-spec.md` §7.1). A
  drawn indicator would have to be present in one condition and absent in the other, which
  `build_figure` makes impossible by construction. The tooltip text is in both figures and
  `staticPlot: True` is what keeps it out of the static condition's reach.
- **Filtering hides or fades; it never rebuilds the chart from a shorter list** (`figures.set_visible`).
  A rebuild would move every name tag, and (until 2026-10-11, when colour went by position) recolour
  the survivors mid-task. Lines and dots
  go `legendonly`; bars, heatmap rows and map countries fade to 0.15. The map fades by
  **selection** (`figures.set_visible`, `set_bands`): plotly.js 4 silently ignores a per-country
  `marker.opacity` list on a choropleth, which only a browser showed.
- **Each figure removes its own modebar buttons** (`layout.modebar.remove`, `visual-spec.md` §7.5):
  box and lasso select everywhere (unlogged, and they would override the map's selection), zoom
  and pan on the fixed-view charts, and (2026-09-27) Download as PNG and Share chart everywhere, and
  the line chart's Zoom and Pan modes and Autoscale. The line chart keeps Zoom in, Zoom out and
  "Reset axes", retitled "Reset axis" by `graph_config`'s locale dictionary, the one thing it
  carries besides the condition switch; the static condition has no modebar to title.
- **The static condition is fully inert:** `staticPlot: True`, so no hover, no zoom, no pan, no
  modebar. Plotly is interactive by default, so a plain `dcc.Graph` would leave the static condition
  hoverable and the manipulation would be invalid. This is deliberate, not an oversight.
- Do not introduce any other divergence between the two conditions.
- `tests/test_conditions.py` enforces this: the two conditions must produce identical figure JSON
  apart from the interactivity configuration.

**Amended 2026-09-15 — `INTERACTIVE` is no longer a module constant at deploy time.** One deployed
URL serves both conditions, so a module-level global would be shared across concurrent participants
and could serve someone the wrong condition. `config.INTERACTIVE` remains the default for **local**
runs; the deployed app carries the condition in per-session state and passes `interactive` explicitly
down through layout and figure building. The intent of the original constraint is unchanged — one
boolean, one decision point — only the mechanism moved.

### Scope is locked

- **Vaccines (4):** DTP3, MCV1, Polio3, HepB3.
- **Countries (61):** US, UK, Brazil, India, Nigeria, Ethiopia, Indonesia, Ukraine, Pakistan, China;
  and, added 2026-09-23 for the redesigned task bank (each used by at least one item): Afghanistan,
  Bangladesh, Burkina Faso, Cambodia, Cameroon, Central African Republic, Chad, Colombia, Democratic
  Republic of Congo, Egypt, Kenya, Madagascar, Mali, Mozambique, Myanmar, Nepal, Niger, Somalia,
  Tanzania, Uganda, Vietnam, Zambia; and, added 2026-10-11 for T3's sixteen dots only: Benin, Libya,
  Sudan, Iraq, Jordan, Kyrgyzstan, Laos, Lebanon, Oman, Philippines, Syria, Thailand, Yemen; and,
  added 2026-10-11 for B-T5's map only (61 in all): Algeria, Botswana, Congo, Côte d'Ivoire, Eritrea,
  Gabon, Ghana, Guinea, Malawi, Mauritania, Morocco, Namibia, Senegal, South Africa, Tunisia,
  Zimbabwe. (Since 2026-10-12 Gabon also draws a line on A-T1, and Ghana and Guinea on B-T6.
  Since 2026-10-13 Algeria, Eritrea, Guinea, Namibia and South Africa are dots on A-T3, and Cote
  d'Ivoire and Gabon on B-T3.)
- **Aggregates (7):** World, Africa, Asia, Europe, North America, South America, Oceania.
- **Years:** 1985–2024 (2000–2024 until 2026-10-12). 68 entities × 40 years × 4 vaccines =
  **10,880 rows**. The line charts draw every year, so the Years slider has years to set aside;
  every line item still asks about 2000 onward (`tasks.ASKED_FROM`), and no other chart shows a
  year before 2000 (`docs/study-design.md` §4).
- Do not expand scope, add vaccines, or add countries without asking.
- Note: the data scope is not the *display* scope. Far fewer entities can be shown on one chart at
  once and still be legible — see `docs/visual-spec.md`.

### Reproducibility

- Anyone with Python 3.11+ and `uv` must be able to clone, run `uv sync`, run the data-fetch script,
  and launch the app.
- No hardcoded absolute paths. No data files in git (use `.gitignore`); the fetch script pulls fresh
  from Our World in Data.
- Public GitHub repo — no secrets, no API keys, nothing that shouldn't be public.

**Named exemption (2026-09-15): `data/deploy/coverage.csv` is committed.** A Vercel deployment only
has what is in git or in the database — a local download does not reach it. This file is a generated
build artifact (~308 KB, 10,880 rows), produced by `scripts/export_deploy_data.py` from the validated
parquet, never hand-edited. Regenerate it whenever the data is refreshed. Raw downloads and the
parquet cache stay gitignored as before.

**Also committed (2026-09-23): `src/assets/geo_africa.js`,** the map's country shapes (36 KB). It is
Plotly's own file, which plotly.js would otherwise download from its CDN in each participant's
browser mid-task, changed in one respect (2026-10-12): its coastline is the land's own outline, so
no land but Africa is drawn. Generated by `scripts/vendor_map_geometry.py`, never hand-edited.

**Also committed (2026-09-26): `src/assets/flags/`,** one 80 px PNG per country in the scope for
the chips (16 KB in all), from flagcdn.com, so no flag is fetched mid-task. Generated by
`scripts/vendor_flags.py`. And `src/assets/zz-bridge.css`, generated from `study.css` by
`scripts/bridge_stylesheet.py` (`visual-spec.md` §10). Neither is hand-edited.

**Also committed (2026-09-27): `src/assets/vendor/`,** jsPDF 4.2.1 and html2canvas 1.4.1 (MIT,
~600 KB), which make the participant's signed consent PDF in the browser
(`src/assets/consent_pdf.js`). Generated by `scripts/vendor_pdf_libs.py`, pinned by SHA-256 and
checked by `tests/test_consent.py`; never hand-edited. Kept out of the page's initial load
(`assets_path_ignore`) and loaded only when the copy is downloaded.

### Deployment

- Hosted on Vercel; participants complete the whole session from one URL.
- **Entrypoint is pinned**: `tool.vercel.entrypoint = "src.app:server"` in `pyproject.toml`. Without
  the pin, Vercel auto-detects `src/app.py` (its patterns include `app.py` inside `src/`) and looks
  there for a **Flask** instance named `app` — but that name holds a `dash.Dash`. `server` is the
  Flask instance. `vercel.json`'s `functions` key must match the *resolved* entrypoint file,
  `src/app.py`, or its settings silently do nothing.
- **pandas and pyarrow live in the `dev` dependency group, not `[project.dependencies]`.** Vercel
  installs from `pyproject.toml`/`uv.lock` with zero configuration, so anything in the runtime
  dependency list ships. `dev` specifically, because it is the group every tool excludes with
  `--no-dev`; a custom group name would only be dropped by a flag we cannot guarantee Vercel passes.
  `uv sync` still installs it, so local work is unaffected.
- Those three libraries are ~146 MB of the 268 MB local environment. pandas 3.0 does not require
  pyarrow (only our parquet cache does) and plotly 7 uses narwhals rather than pandas, so the runtime
  path reads the deploy CSV with the stdlib `csv` module instead. Measured bundle: **109.8 MB** (2026-09-23)
  against a documented 500 MB limit.
- `uv.lock` remains the source of truth for local development. `requirements.txt` is generated from
  the committed `requirements.in` (`uv pip compile requirements.in -o requirements.txt`) and kept as
  an explicit second expression of the same runtime set. Regenerate from that input, never from a
  scratch file outside the tree — doing so once baked an absolute local path, and a local username,
  into a public artefact.
- Vercel's Python versions are 3.12 (default), 3.13, 3.14. `requires-python = ">=3.11"` is not one of
  them, so Vercel falls back to 3.12. The suite is verified on 3.11 and 3.14, which brackets it.
- Everything under `src/` except `data.py` and `contrast.py` ships to production: `app.py`,
  `config.py`, `consent.py`, `db.py`, `figures.py`, `flow.py`, `layout.py`, `logging.py`,
  `runtime_data.py`, `tasks.py`, and `assets/`. **Do not import pandas in those modules** —
  `tests/test_runtime_data.py` fails the build if you do.
- `vercel.json` excludes `data/consent/**` and `irb/**` as well as `analysis/**`: local signed consent
  records and the IRB paperwork carry names. `tests/test_scoring.py` asserts all three.

### Study instrumentation

- The app logs interaction events (filter changes, legend/isolation clicks, sort actions), task
  timings, participant answers (skips recorded as `null` plus `skipped`), the post-condition survey
  (Paas, a1–a9, b1–b3 after the interactive half, c1–c3 after the second), About you
  (`demographics`, at the end), a `consent` event, and the browser window's size once
  (`window_size`). Hovers are **not** logged (decided
  2026-09-21).
- **Names and signatures never enter the event log.** The signed consent record goes to its own
  `consent_records` table (or `data/consent/` locally), which has no participant ID so it cannot be
  joined to answers — IRB form items 15 and 17. `scripts/export_consents.py --purge` moves it to the
  Oxy Drive and out of Neon.
- This logging IS the study data. Do not remove, disable, or "clean up as unused" any logging code.
- Log schema changes are breaking — flag them explicitly. Bump `SCHEMA_VERSION` in `src/logging.py`.

**Schema v21 (2026-10-13).** Each T3 scatter draws twenty-one dots, not sixteen
(`study-design.md` §4).
- A adds Algeria, Eritrea, Guinea, Namibia and South Africa.
- B adds Benin, the Central African Republic, Cote d'Ivoire, Gabon and Sudan. The first three are
  A's own dots, placed exactly as there.
- All are in scope, every one improving at least 20 points less than the key.
- The scatter names the Central African Republic "CAR", on its dot and its chip.
- The chips run at most seven to a row, so twenty-one run 7/7/7. Every other chart's rows are
  unchanged (`visual-spec.md` §7.3).

Question, key, margin and options are unchanged, but a v20 T3 answer was given against a different
chart. No new event, key, table or column, so `init_db.py` needs no re-run. Nothing collected for
the study, so no migration.

**Schema v20 (2026-10-13).** Each T4 heatmap draws twelve rows, not eight (`study-design.md` §4):
A adds Cote d'Ivoire, Iraq, South Africa and Syria; B adds DR Congo, Ethiopia, Nigeria and Yemen,
all in scope and beyond the six option rows. Question, key, margin and options unchanged, but a v19
T4 answer was given against a different chart. The heatmap's chips are smaller, so twelve still
run 6/6 (`visual-spec.md` §7.3). No new event, key, table or column, so `init_db.py` needs no
re-run. Nothing collected for the study, so no migration.

**Schema v19 (2026-10-12).** Line charts drawn from 1985 (`study-design.md` §4).
- A v18 T1, T6 or practice answer was given against a chart drawn from 2000.
- T6 says "after 2000", so a v18 T6 answer was given to different words.
- A-T1 draws Gabon for Nigeria; B-T6 Ghana and Guinea for Cameroon and Madagascar.
- The Years slider's `value`/`previous` run from 1985, and `session_start.year_range` is
  `[1985, 2024]`.

Keys and options unchanged. No new event, key, table or column, so `init_db.py` needs no re-run.
Nothing collected for the study, so no migration.

**Schema v18 (2026-10-12).** The changes after the first pilot session (`study-design.md` §10).
- The practice asks about 2019–2021, not 2015–2021.
- The heatmap's row sort is `default`, `min` or `max` (highest cell first); `mean` can no longer
  occur.
- The line chart's View went, so `sort_change` `listed`/`coverage` can no longer occur.
- The Years slider logs `view_change` with `control` `years` and `[first, last]` values.
- `line_isolate` now focuses (the others fade; the chips no longer follow).
- Show all also releases a focus.
- `view_reset.previous` gains `xrange`: Reset view undoes a zoom.
- The map's box went, so `filter_change` from `threshold` can no longer occur.
- A click on a key colour logs `filter_change` with `control` `key`, `action` `add`/`remove`, and
  the chosen bands' lower bounds.
- `view_reset.previous` has `bands` in place of `threshold`.

- T1's four extra controls (`visual-spec.md` §7.7): `view_change` with `control` `coverage` (a
  `[low, high]` coverage range) or `display` (the parts shown, of `points`, `tags`);
  `sort_change` with `key` `alpha`, `start` or `end` (the chips' order); `filter_change` with
  `control` `region`, `action` `hide`/`show` and the ticked countries. `view_reset.previous`
  gains `order`, `yrange` and `display` on T1.

T7 was specified and dropped the same day, before any code shipped; T1's overload took its place.
No new event, key, table or column, so `init_db.py` needs no re-run.

**Schema v17 (2026-10-12).** T1, T3 and A-T4 reworded, keys unchanged. B-T2 asks for the
sixth-highest bar, in 2017 (key Mozambique); B-T4 for the highest cell, Laos and Cameroon replacing
Myanmar and Uganda (key Nepal); both option lists changed (`study-design.md` §4). The T4 rule takes
`extreme` (`analysis/keys.py`). No new event, key, table or column, so `init_db.py` needs no re-run.
Nothing collected, so no migration.

**Schema v16 (2026-10-11).** T2 and T4 read MCV1, not DTP3, in both forms (`study-design.md`
§4). A-T2 swaps Brazil's bar for Guinea's, B-T2 moves to 2021 and swaps Cambodia's for Algeria's,
A-T4 swaps the CAR's row for Benin's; both T2 option lists and A-T4's changed. Keys unchanged. No
new event, key, table or column, so `init_db.py` needs no re-run. Nothing collected, so no
migration.

**Schema v15 (2026-10-11).** Each T6 chart draws eight lines, not two: A adds Afghanistan, Chad,
Côte d'Ivoire, DR Congo, Nigeria and Somalia; B adds Benin, Cameroon, Gabon, Kenya, Madagascar and
Sudan (`study-design.md` §4). Question, pair, key and options
unchanged, but a v14 T6 answer was given against a different chart. No new event, key, table or
column, so `init_db.py` needs no re-run. Nothing collected, so no migration.

**Schema v14 (2026-10-11).** The chart handoff redraws every chart (`visual-spec.md`). T3's dots
are named and coloured by change, with no legend; T4's cells are banded; T5 colours eighteen
countries per form, Africa-wide, and its prompt says "in Africa"; line charts lose their legend, so
a `filter_change` from `legend` can no longer occur (its logging code stays). Keys and options are
unchanged, but a v13 answer was given against a different chart. Sixteen countries joined the
scope for B-T5 (6800 rows). No new event, key, table or column, so `init_db.py` needs no re-run.
Nothing collected, so no migration.

**Schema v13 (2026-10-11).** Each T3 scatter draws sixteen dots, not six, its colours used twice
and a shape per dot (`study-design.md` §4, `visual-spec.md` §6). Question, key and options
unchanged, but a v12 T3 answer was given against a different chart. Thirteen countries joined the
scope for it (5200 rows). No new event, key, table or column, so `init_db.py` needs no re-run.
Nothing collected, so no migration.

**Schema v12 (2026-10-11).** Each T2 bar chart draws ten bars, not seven (`study-design.md` §4).
Question, key and options unchanged, but a v11 T2 answer was given against a different chart. No
new event, key, table or column, so `init_db.py` needs no re-run. Nothing collected, so no
migration.

**Schema v11 (2026-09-27).** T1 is a written description of two trends, scored by rubric
(`study-design.md` §4, §7).
- Its `answer_submit.answer` is free text, capped at 2000 characters, where a v10 T1 answer was a
  year. Its `justification` is always null, and its `skipped` can hold only `answer`
  (`submit_answer(..., justification_asked=False)`).
- The screen keeps a hidden `justification-input` and adds an `answer-format` store, because the
  submit callbacks name them.
- No new event, key, table or column, so `init_db.py` needs no re-run. Nothing collected, so no
  migration.

**Schema v10 (2026-09-26).** New event `window_size` (`width`, `height`: the window's inner size
in CSS pixels), once per participant, written at the first Begin right after `consent`.
Participants use their own computers, and on a window 790 px tall or less the interactive scatter
and map cards scroll where the static ones do not. Read on every screen and every resize
(`app.WINDOW_SIZE_JS`); a value the browser did not send is null and stops nothing.
`analysis/reshape.tidy_tasks` carries it as `window_width`/`window_height`. No table or column, so
`init_db.py` needs no re-run. Nothing collected, so no migration.

**Schema v9 (2026-09-25).** The redesign (`docs/study-redesign.md`, phase 2). Every item offers six
options, so an answer means something different against a v8 option list. `survey_rating` carries
a1–a9 in place of clarity/ease_of_use/confidence; new events `controls_rating` (b1–b3, interactive
condition only), `comparison` (c1–c3, second condition only) and `view_reset` (Reset view).
`demographics` carries the ten About-you questions (`tasks.DEMOGRAPHIC_KEYS`) and is written into
the **second** session after its `session_end`, so stopping at About you never makes a session
incomplete. `filter_change` comes from the controls `chips`, `legend`, `show-all` and `threshold`;
`sort_change.key` from the View (`listed`, `coverage`), the bar sort (`alpha`, `desc`, `asc`) and
the heatmap's (`default`, `min`, `mean`). The vocabulary is in `src/logging.py`'s `EVENTS`. No table
or column, so `init_db.py` needs no re-run. Nothing collected, so no migration. The survey and About-you fields use pattern-matching ids (`ALL`): their set differs by
condition and half, and a State naming a component that is not on the page kills a callback.

**Schema v8 (2026-09-25).** The largest-rise item (then T2) was dropped and T3–T7 renumbered T2–T6,
so a task id names a different item than in v7. Record shape unchanged: no new event, key or table,
so `init_db.py` needs no re-run. Nothing collected, so no migration.

**Schema v7 (2026-09-23).** The task bank was replaced, so task ids T1–T6 name different items; a
v6 answer scored against a v7 key would be scored against the wrong question, and analysis refuses
to pool versions. `filter_change` also comes from the map's coverage range (`control`
`coverage-band` or `band-reset`, `value`/`previous` a `[low, high]` range, not a list of entities),
and `sort_change` from the bar chart's sort. T7 was added the same day, before any collection;
T1–T6 kept their meaning, so the version stayed at 7. No new event, no new key, no table change, so
`init_db.py` needs no re-run. Nothing collected, so no migration.

**Schema v6 (2026-09-21).** Brought in line with the IRB submission. Any question may be skipped,
so `answer_submit.answer`/`justification` and `load_rating.value` may be null, and `answer_submit`
carries `skipped`. New events `survey_rating` (three 7-point Likert items, per condition) and
`demographics` (once). `consent` gains `signature_method`. New table `consent_records` — **no
participant ID, by design** — and `participants.withdrawn_at`, both added idempotently, so
`scripts/init_db.py` upgrades a v5 database in place (verified against a v5 Postgres). Nothing
collected, so no migration of data.

**Schema v5 (2026-09-16).** No new column; what Postgres stores in `server_ts` changed. It is now the
time the logger created the record (`db.insert_event` writes it, falling back to `now()`). Under v4
the column took the INSERT time, so an event spooled through an outage carried its replay time and
disagreed with the JSONL sink. Nothing collected, so no migration and no `init_db.py` re-run needed.

**Schema v4 (2026-09-15).** Pre-pilot hardening. Nothing has been collected, so no migration — but
`scripts/init_db.py` must be re-run, and note `CREATE TABLE IF NOT EXISTS` is a no-op on an existing
table, so new columns need an explicit `ALTER` or they are silently absent.

- `event_uid` (UUID, unique) on every record, so a spooled event can be replayed without
  double-inserting.
- New event `consent` — §9 promised a timestamped consent record and nothing produced one.
- New event `sink_recovered` — marks a session where the logger could not reach the database and
  spooled locally. Not an exclusion by itself; see `study-design.md` §7.
- `duration_invalid` on `answer_submit` and `task_end` — a page reload resets the browser clock, and
  the resulting duration must be visibly absent rather than plausibly wrong.
- A partial unique index on `(session_id, task_id) WHERE event = 'answer_submit'`, so one task can
  never record two answers.

**Schema v3 (2026-09-15).** Parallel forms added a `form` column, the `load_rating` event (Paas
mental effort, the RQ3 measure), and `justification` on `answer_submit` (the RQ2 material). Additive,
and nothing has been collected, so no migration — but the record shape changed, so the version moved.

**Schema v2 (2026-09-15).** Deployment forced three changes:

- **Sink:** Neon Postgres when `DATABASE_URL` is set; JSONL under `data/study_logs/` otherwise.
  Vercel's filesystem is ephemeral and read-only outside `/tmp`, so file writes there are lost. The
  file sink remains the local path and stays supported.
- **Timings come from the browser** (`performance.now()`), not server `perf_counter()`. Each event is
  a separate HTTP request, so server-side timing would fold network latency and 800 ms–2.5 s cold
  starts into task duration — a dependent variable.
- **Answers are captured**, since the deployed page runs the whole session. Event `answer_submit`.

`DATABASE_URL` is a secret and this is a public repo: Vercel environment variables only, never
committed, `.env*` gitignored.

### Accessibility baseline

- Color palette must meet WCAG 2.1 AA contrast ratios (4.5:1 for text, 3:1 for graphical elements).
  Series colours must also stay at least 12 ΔE2000 apart under simulated protanopia and deuteranopia
  (`src/contrast.py`, 2026-09-23); three documented exemptions, the gridline, the heatmap/map
  blue bands and the scatter's change scale, are bounded by tests (`visual-spec.md` §4). Bar
  colours hold the full floor on each bar chart (2026-10-11).
- The page chrome's colours, the tokens in `src/assets/study.css`, are held to the same floors by
  `tests/test_palette.py`. One exemption: Submit's fill while saving (`#91796E`, white text 4.07:1),
  because the button is disabled then and WCAG 1.4.3 exempts inactive controls.
- All interactive controls keyboard-navigable. The one exception is the consent screen's
  signature pad, which cannot be drawn with a keyboard. Its keyboard alternative is the
  "signed a paper copy" checkbox, and IRB form item 12A already provides a paper form. Keep that
  alternative whenever the consent screen changes.
- Skip confirmations use the browser's own `window.confirm`, which is keyboard-operable. Don't
  replace it with a custom modal unless the modal is keyboard-operable too.
- Do not propose color choices without checking contrast.
- Full screen-reader accessibility is explicitly out of scope; do not spend time on it, but do not
  add anything that makes it worse.

## Tech stack

- Python 3.11+
- `uv` for dependency and environment management
- `dash`, `plotly` — ship to production
- `psycopg[binary]` — Neon Postgres driver, ships to production
- `pandas`, `pyarrow` — **local only**, for cleaning and validation; never imported by runtime modules
- `ruff` for linting/formatting, `pytest` for tests
- Do not add dependencies without asking first. A new runtime dependency also grows the Vercel
  bundle, so say which of the two groups above it belongs in.

## Data conventions

- Long-format DataFrames throughout. Canonical schema:
  - `country: str` (OWID entity name)
  - `iso_code: str` (ISO-3)
  - `year: int`
  - `vaccine: str` (short code: "DTP3", "MCV1", "Polio3", "HepB3")
  - `coverage_pct: float` (0–100, may be NaN)
- Missing data stays missing. Do not interpolate, forward-fill, or drop rows silently — gaps in
  coverage are meaningful to participants.
- Raw data lives in `data/raw/` (gitignored). Cleaned data cached as parquet in `data/processed/`.
- The frame is reindexed to the complete entity × year × vaccine grid, so an unreported value is an
  explicit NaN row rather than an absent one. Nothing is filled; tests assert the observation count
  and every individual value match the source.

### Known gaps (measured, affects task design)

- **UK HepB3 reports only 2019–2024** (34 of 40 years missing; 19 of 25 before the scope began
  at 1985). The UK added HepB to the routine infant schedule in 2017. Any task comparing HepB3
  across countries shows the UK as a near-empty line, and participants may read absence as zero
  coverage rather than "not reported".
- Ethiopia HepB3 missing 1985–2006; Nigeria and India 1985–2003; Pakistan 1985–2002.
- **Before 2000 (in scope since 2026-10-12), HepB3 is mostly unreported**: 850 of its 1020
  country-and-aggregate years from 1985 to 1999, the aggregates included.
- **Ukraine reports nothing before 1992** (it was part of the USSR) for DTP3, MCV1 and Polio3, and
  no HepB3 before 2000. A-T1 draws its DTP3 line from 1992, uncaptioned: a line chart's gap caption
  names only years from 2000 on (Eduardo, `visual-spec.md` §3). Eritrea,
  Kyrgyzstan, Namibia and Senegal also have DTP3 gaps before 2000; no line chart draws them.
- **Every continent aggregate is missing 2024** across all four vaccines, while World and the
  individual countries have it. Charts mixing countries and continents show continent lines stopping
  a year short — a trap for any task about the most recent year.

## Repo layout

Every tracked file. `irb/` holds the IRB paperwork. It is gitignored and never tracked, so it is
not in this list. `src/data.py` and `src/contrast.py` are the only modules under `src/` that do
not ship to Vercel — see the import rule under Deployment above. `analysis/` never ships either: it is
excluded in `vercel.json` and holds the answer key.

```
CLAUDE.md
README.md
LICENSE
pyproject.toml          # deps + ruff/pytest config; [tool.uv] package = false; entrypoint pin
uv.lock                 # committed — this is the reproducibility guarantee
requirements.in         # hand-written runtime set; the committed input to the compile
requirements.txt        # generated from requirements.in — no pandas/pyarrow/numpy
vercel.json             # function config + excludeFiles, keyed by the resolved entrypoint
.env.example            # names DATABASE_URL; the value itself lives only in Vercel / .env.local
.gitignore
data/
  raw/                  # downloaded CSVs (gitignored, .gitkeep only)
  processed/            # cleaned parquet (gitignored, .gitkeep only)
  study_logs/           # JSONL sessions from local runs (gitignored, .gitkeep only)
  consent/              # signed consent records from local runs (gitignored; created on demand)
  deploy/
    coverage.csv        # committed build artifact (named exemption)
docs/
  visual-spec.md        # locked visual decisions (colors, chart types, layout)
  chart-handoff/        # the charts' visual style (2026-10-11): README, screenshots, renderer; Form A only
  study-design.md       # RQs, conditions, the 12 items + acceptance rule, measures, rubric, consent
src/
  config.py             # INTERACTIVE flag (local default only), palette, scope
  data.py               # load + clean — pandas, local only
  consent.py            # the consent form's text, the signed record, stored apart from study data
  contrast.py           # WCAG contrast + CIEDE2000 under simulated colour blindness; palette tests
  runtime_data.py       # stdlib csv loader; NO pandas
  db.py                 # Neon Postgres connection, DDL, and the 2x2 assignment rule
  figures.py            # build_figure (5 chart types) + graph_config(interactive) — the one switch
  layout.py             # shared layout components, study screens, interactive controls
  flow.py               # study flow state machine
  tasks.py              # the 12 items on 5 chart types, forms A and B. NO answer key — ships
  logging.py            # event/timing logger; Postgres or JSONL sink
  app.py                # Dash app factory, callbacks, clientside timing, Submit and skip guards
  assets/
    study.css           # the design handoff's stylesheet, copied unchanged (visual-spec.md §10)
    zz-bridge.css       # study.css's option rules re-aimed at Dash 4's markup (generated; committed)
    zz-overrides.css    # hand-written rules for Dash's markup and the short screens, each explained
    signature.js        # the consent screen's signature pad; Dash serves assets/ automatically
    consent_pdf.js      # the signed consent sheet as a PDF, laid out as on the page
    chart_pan.js        # zoomed line chart: a sideways touchpad swipe moves the x axis
    redraw_guard.js     # while the chart redraws, keys on the controls do nothing (as clicks)
    vendor/             # jsPDF and html2canvas for consent_pdf.js (generated; committed)
    geo_africa.js       # the map's country shapes, Plotly's own file, coast cut to Africa (generated; committed)
    flags/              # a PNG per country for the chips, from flagcdn.com (generated; committed)
analysis/               # offline scoring — NEVER ships; pandas allowed except in keys.py
  keys.py               # answer key derived from the deploy CSV, checked against study-design §4
  reshape.py            # events -> tidy task and participant x condition frames
  exclusions.py         # the §7 rules, marked not dropped, each separately reportable
  coding.py             # RQ2 blind coding sheets, stratified double-coding sample, Cohen's kappa
  report.py             # the descriptive numbers §7 asks for, nothing inferential
  sources.py            # where events are read from: CSV export, Postgres, or JSONL
  viewer_data.py        # the data viewer's checks and tables; never raises on broken data
  viewer_app.py         # the data viewer's Dash layout; localhost only, justifications masked
scripts/
  download_data.py      # fetches from Our World in Data
  export_deploy_data.py # parquet -> data/deploy/coverage.csv
  init_db.py            # create tables
  export_logs.py        # pull study data out for analysis
  recover_spool.py      # replay spooled events into Postgres; dry run by default, idempotent
  export_consents.py    # signed consent records -> printable copies (+PDF) for the Oxy Drive; --purge
  archive_consents.py   # after a session: copies -> AES-256 7-Zip -> Drive for desktop folder; asks to purge
  withdraw_participant.py # IRB item 13: delete one ID's events everywhere; dry run by default
  derive_keys.py        # print the derived answer key; exits 1 if it disagrees with §4
  export_questionnaire.py # every screen as irb/questionnaire.pdf, for IRB request form item 18
  vendor_map_geometry.py # Plotly's Africa geometry, coast cut to Africa -> src/assets/geo_africa.js
  vendor_flags.py       # the chips' flags -> src/assets/flags/; no CDN mid-task
  vendor_pdf_libs.py    # jsPDF + html2canvas -> src/assets/vendor/, pinned by SHA-256
  bridge_stylesheet.py  # study.css -> src/assets/zz-bridge.css, for Dash 4's option-list markup
  score_study.py        # accuracy, Paas, timing, exclusions -> data/study_logs/derived/
  code_justifications.py # blind sheets, kappa, reasoning depth -> data/study_logs/coding/
  view_data.py          # local data viewer on 127.0.0.1:8051; read-only
  check_contrast.py     # WCAG contrast and colour-blind separation report for the palette
  check_bundle.py       # serves the app from requirements.txt alone, in a throwaway venv
  verify_deployment.py  # round-trips a synthetic session through the real database, then deletes it
tests/
  test_data.py          # cleaning, the complete grid, the missing-data guarantees
  test_runtime_data.py  # the csv loader — and fails the build if a runtime module imports pandas
  test_palette.py       # enforces the contrast floors and the colour-blind separation floor
  test_stylesheet.py    # study.css unchanged; bridge current; every class used is defined; compact
  test_conditions.py    # the two conditions must produce identical figure JSON
  test_tasks.py         # item structure, and that no answer key ships
  test_flow.py          # the stage sequence and the counterbalancing
  test_logging.py       # event schema, both sinks, retry/spool/circuit breaker
  test_db.py            # failure classification, timeouts, schema migrations — no live database
  test_recover_spool.py # replay is dry by default, ordered, idempotent, never deletes
  test_scoring.py       # derived keys match §4; each rule refuses an ill-posed or fragile item; no ship
  test_analysis.py      # real app sessions scored end to end; exclusions; coding harness; kappa
  test_viewer.py        # each health check trips on its fault; masking; download re-scores
  test_app.py           # callbacks called directly, a DB outage, clientside JS run under Node
  test_consent.py       # the pinned consent text, the signed record, export and withdrawal scripts
  test_questionnaire.py # the IRB questionnaire: every question and option, the app's styles, no key
```

### Study protocol

- `docs/study-design.md` is the source of truth for the protocol. Change it before `src/tasks.py`.
  **The IRB approval request form (`irb/`, local only) outranks it.** Where they disagree, change the
  doc to match, or list the mismatch in `study-design.md` §10 so the IRB paperwork is amended.
- `docs/study-redesign.md` — the redesign brief; read before any UI or study-content work.
- **The consent text in `src/consent.py` is the HSRRC-approved form, word for word**
  (`irb/Oxy CS Senior Comps Informed Consent Form.docx`, approved 2026-10-12). Its hash is pinned in
  `tests/test_consent.py`. Change the wording only to match an approved form, and re-pin the hash
  when you do. `consent.APPROVED` is True; set False, the screen shows a "pending approval"
  banner.
- **Every question may be skipped** (IRB form item 10), behind a confirmation popup. Only consent and
  the participant ID are required. A skipped answer scores incorrect in the primary analysis and is
  excluded in the pre-registered secondary (`study-design.md` §7).
- **Withdrawal within two weeks** (IRB form item 13) goes through `scripts/withdraw_participant.py`.
  It deletes the events, but marks the registration `withdrawn_at` rather than deleting it, so the
  counterbalancing sequence stays explainable and the ID cannot be reused.
- **Parallel forms A and B**: a participant sees one form per condition and never the same form
  twice. Plain order-counterbalancing cannot fix a memory effect — it only spreads it evenly.
- Counterbalancing is **2×2**, assigned from a database sequence (`db.assignment_for`, `seq % 4`),
  not a random draw, so cells fill evenly and concurrent starts cannot collide.
- **No correct answers in `src/tasks.py`.** It serialises to the browser; an answer key would be
  readable in the page source. Scoring is offline against the rubric.
- **The answer key lives in `analysis/keys.py`, and is derived, not transcribed.** Each key is
  computed from `data/deploy/coverage.csv` by the rule the item states, then cross-checked against
  the table in `docs/study-design.md` §4; a disagreement fails the suite. §4's T1 key was wrong for
  days because a hand-written key has nothing checking it.
- **Every item must pass the acceptance rule in `study-design.md` §4** (2026-09-22, extended
  2026-09-23 to the six item types), and `analysis/keys.py` refuses one that fails.
  - No call on a position axis closer than 5 points; on a colour scale (heatmap, map), 10.
  - No answer that a one-year misreading moves to another option.
  - No scatter dot within 4 points of another, where one hides the other.
  - No bar, dot, cell or country the question depends on left unreported.
  - A crossing (T6) happens once, the lines part by 5 points on each side, they meet at least a
    year inside the key band, and no other line passes within 5 points of where they meet.

  The task bank as specified on 2026-09-23 broke it on purpose (bars 1 point apart, cells 3). Eduardo
  kept the rule and those items were re-tuned; `tests/test_scoring.py` still runs the originals on
  the real data and checks they are refused. A new or changed item must pass it.
- **RQ1 accuracy is T1–T6** (2026-09-25; the old bank's gap item was scored separately). Per-item
  and per-chart-type results are descriptive only: each chart type carries one item per form, the
  line chart two. T6, the crossing item, also gets adjacent-band credit as a pre-registered
  secondary, reported beside the strict score and never in the RQ1 proportion. Options that are
  countries are alphabetical, like the chart's entities; years and year bands run in calendar
  order; every multiple-choice item offers six options (2026-09-25); no answer position holds more
  than a third of the keys. **T1 is written, not chosen** (2026-09-27): a description of two
  trends, scored by rubric by two blind coders, still in RQ1 (`study-design.md` §4, §7). A
  participant's T1–T6 proportion is not computed while their T1 is uncoded.
- **`analysis/` must never ship.** Everything under `src/` is uploaded to Vercel, so the key cannot
  live there. `analysis/**` is in `vercel.json`'s `excludeFiles`, a test asserts that it stays there,
  and another asserts no runtime module imports it. pandas is allowed freely in `analysis/` —
  except in `keys.py`, which reads the deploy CSV through `src.runtime_data` so the key is derived
  from the same bytes and the same loader the participant's chart came from.
- Static participants cannot read exact values, so no item may ask for one — it would measure
  whether hover exists rather than interpretation.

## Environment notes

Verified 2026-09-08 on Windows 11, so future sessions don't re-derive it:

- `uv` 0.12.11 installed at `C:\Users\Eduardo\.local\bin` (on user PATH).
- Machine Python is 3.14.4. The full stack installs from wheels on 3.14 with no source builds, and a
  universal lock across 3.11–3.14 resolves dash/plotly/pandas/pyarrow identically — only numpy forks
  (2.4.6 for ≤3.12, 2.5.3 above). The `>=3.11` floor is therefore safe and tested.
- Locked versions: dash 4.4.1, plotly 7.0.0, pandas 3.0.5, pyarrow 25.0.1, ruff 0.16.6, pytest 9.1.1.
- **pandas 3.0 defaults string columns to `str` dtype, not `object`.** Matches the canonical schema,
  but differs from pandas 2.x examples you may find in older references.
- Verified: NaN and int64 `year` both survive a pyarrow parquet round-trip, so the missing-data
  constraint holds through the processed cache.
- `src/` is not an installable package (`[tool.uv] package = false`); run via `uv run`.

### Location

The working copy is `C:\Users\Eduardo\Interactivity-and-Interpretability-in-Data-Visualization-Dashboards\`.
Until 2026-09-21 it sat one level deeper, in a folder of the same name nested inside a stale clone;
the stale clone was deleted and the working copy moved up. There is only one clone now.

## Working norms

### Ask before doing

- Anything touching visual design, chart type, colors, or layout
- Anything changing the study protocol, tasks, or scoring
- Adding a dependency
- Expanding scope (more vaccines, countries, years)
- Changing the log schema
- Any change to files under `docs/`

### Just do

- Formatting, imports, obvious refactors within a file
- Fixing bugs in code you just wrote
- Adding tests
- Docstrings and comments

### Definition of done

A task is done when the code runs, the behavior is verified (not just "should work"), and there are
no TODOs or stubs left in the production path. If something is blocked, say so — don't stub past it.

### When in doubt

Point to `docs/study-design.md` or `docs/visual-spec.md`. Those are the source of truth for the study
and for the visual decisions. The IRB approval request form in `irb/` outranks both on anything
it covers. If none of them answers the question, ask.

## Anti-goals (things this project is not)

- Not a general-purpose vaccination-tracking tool. It's a study instrument.
- Not trying to be impressive. The two conditions looking identical is the point; a feature that
  makes only one of them nicer is a defect, not an improvement.
- Not optimizing for performance. ~10,900 rows in memory, single user at a time.
- Not building a public-facing site. It is deployed to one Vercel URL, but that URL is shared only
  with recruited participants during in-person sessions (IRB form item 5B).

---

# Eduardo's notes

Everything below this line is yours. Add whatever helps — open questions, decisions made, advisor
feedback, deadlines, findings.

Keep entries short. This file is loaded into context at the start of every session, so full reports
belong in `docs/` or `reports/` as their own files, with a one-line pointer here. That keeps the
context cheap and the reports as long as they need to be.

## Status / current focus

- 2026-09-15 — **The instrument is finished and verified end to end.** A full session runs from one
  URL; both conditions log a complete session; all four interactive controls work and record their
  events. 489 tests green.
- ~~Blocked on IRB.~~ **HSRRC approved the study on 2026-10-12** (the .docx forms in `irb/`);
  `consent.APPROVED = True`, so the "pending approval" banner is gone.
- 2026-09-16 — **Pre-pilot hardening done** (uncommitted at time of writing). A database outage no
  longer breaks a session or loses answers silently; consent is recorded; double-submit and
  reload-corrupted durations are handled; schema is v4. The offline scoring pipeline exists, with
  the answer key derived from the data. Verified over live HTTP against an unreachable Postgres.
- 2026-09-16 — **Verified in a real browser and against a local Postgres 16** (throwaway, not Neon):
  full sessions in both orders, a DB outage mid-session with replay, and `verify_deployment.py`,
  which could never pass before (it miscounted events). The pytest suite calls `step()` directly
  and cannot see Dash-renderer failures — every button was dead in a browser while it was green.
- 2026-09-21 — **Instrument aligned with the IRB submission** (uncommitted at time of writing):
  the consent form verbatim with typed name, date and a drawn signature (or a paper-copy box), a
  decline path, skippable questions behind a confirmation popup, demographics, the Likert survey
  after each condition, and a two-week withdrawal script. Schema v6. 640 tests; a full session
  driven in headless Chrome against both sinks and a throwaway Postgres upgraded from v5.
- 2026-09-22 — **Task set finalized** (uncommitted at time of writing).
  - Audited against the data and the chart as drawn. Seven of the thirteen items failed the new
    acceptance rule and were replaced or repaired; the rule is enforced in `analysis/keys.py`.
  - T6 is scored separately. End labels are spread apart (`visual-spec.md` §6).
  - `irb/questionnaire.pdf` exported for IRB request form item 18.
  - 712 tests. Four full sessions, one per counterbalancing cell, driven in headless Chrome: every
    derived key matched what the app logged.
- 2026-09-22 — **Neon verified.**
  - Neon was still on schema v5, with no `consent_records` table, so the live site could not have
    recorded consent. `init_db.py` upgraded it in place.
  - `verify_deployment.py` passed every check.
  - Deleted the leftover `test` participant and its 7 v5 events; mixed schema versions would block
    scoring.
  - Region us-east-1, pooled, `sslmode=require`.
  - Tables are empty and the sequence is at 8, so the first real participant is seq 9 (static, A).
  - Production at https://interactivity-and-interpretability.vercel.app serves the current commit.
- 2026-09-23 — **Task bank replaced** (uncommitted at time of writing).
  - Six new items on five chart types: line (isolation; year-over-year change), bar (sort),
    scatter and heatmap (hover), map (coverage range). `study-design.md` §4.
  - Kept the acceptance rule; the spec's bar, heatmap and map items and A-T1's options were
    re-tuned to pass it. 22 countries added to the scope for them; 3900 rows.
  - Palette extended to eight colours, measured under simulated colour blindness; the darkened
    Okabe-Ito orange was dropped (1.1 ΔE from vermillion under protanopia). Cividis for heatmap and
    map. `visual-spec.md` §4.
  - Schema v7. Map geometry vendored, so no CDN call mid-task.
  - Four sessions, one per counterbalancing cell, driven in headless Chrome with Plotly's CDN
    blocked. Every derived key matched what was logged, and interaction events were recorded only
    in the interactive condition.
  - The browser run found three bugs the tests could not see, now fixed and tested:
    - the map's fade drew nothing;
    - China's end label on A-T1 was never drawn;
    - an old watchdog threw a page error in every session.
- 2026-09-23 — **T7 (now T6) added** (uncommitted at time of writing): a crossing item, so one question asks
  how two time series relate. A: Ethiopia over the Central African Republic, 2004-2008. B: Pakistan
  over Mozambique, 2017-2020. Two lines each, no World line. `study-design.md` §4.
- 2026-09-25 — **Largest-rise item dropped** (uncommitted at time of writing), so line charts carry
  two items per form. T3–T7 renumbered T2–T6; schema v8. 853 tests. Four sessions, one per
  counterbalancing cell, driven in headless Chrome: every derived key matched what was logged.
- 2026-09-25 — **Redesign, phases 1–8 of `docs/study-redesign.md`** (uncommitted at time of writing).
  - Phase 1: the §4 decisions (below) and the plan.
  - Phase 2: `study-design.md` and `visual-spec.md` amended; six options per item; T1 without World;
    consent text from the handoff's screen 1 (hash re-pinned); practice-complete stage; About you
    moved to the end with the handoff's ten questions; the new survey (Paas kept first); schema v9.
    Screens keep the old look until phases 3–7. 910 tests. Two sessions (both orders) driven in
    headless Chrome: no page errors, and the survey, About you and skip popups logged as specified.
  - Phase 3: `study.css` copied unchanged; the shell (header, seven-step stepper, backgrounds) on
    every screen; compact mode as a media query in `zz-overrides.css`; chrome contrast tested. 997
    tests. Sessions at 1440 × 790 and 1366 × 768 in headless Chrome: right step and background on
    every screen, compact on at 800 px or less, no page errors.
  - Phase 4 (2026-09-26): the task screen on the handoff's card; chips with bundled flags on every
    chart, the line legend, View, Show all, Reset view, the three-way bar sort, the heatmap row
    sort, the map's "Below [n] %"; Submit busy while saving (S1). One `view` callback reads every
    control by pattern. Dash 4 bridge stylesheet. 1083 tests. A full session in headless Chrome, 38
    checks, no console errors; every event logged, none in the static half. The scatter and map
    task cards overflow a 768 px window in the interactive condition only: scrolling accepted.
  - Phase 5 (2026-09-26): the short screens on the handoff's centred card (declined, ID with S2,
    the four instructions, practice complete, break, finished), with the approved wording. 1089
    tests. Both orders in headless Chrome at 1440 × 790 and 1366 × 768: 66 checks each, no console
    errors. The instructions overflow a 790 px window except 9a (4b's button is 260 px below
    it): scrolling accepted.
  - Phase 6 (2026-09-26): consent as the handoff's Letter sheet, signed inside it, and S3. Pad
    600 × 150. 1094 tests. Headless Chrome at 1440 × 790 and 1366 × 768: 30 checks (layout, Tab
    order, focus rings, signing and clearing, a refusal, S3 forced by a blocked store, then
    consent on the second try). Phases 4 and 5 re-run clean.
  - Phase 7 (2026-09-26): the survey and About you, one question per page with the section rail;
    the pages move in the browser (`app.PAGER_JS`). 1111 tests. Both orders in headless Chrome
    (45–49 checks each): skips confirmed per page, the rail, keyboard, the age refused on its
    page, "Other", and every answer logged as given. Phases 4–6 re-run clean.
  - Phase 8 (2026-09-26): S4 (the log cannot be written, or the spool overflows); `analysis/`
    reads v9 (b1–b3, c1–c3, About you as `participants.csv`, a7 beside Paas, Reset view as an
    interactive-only event); `irb/questionnaire.pdf` re-exported in the app's styles. 1119 tests.
    Four sessions, one per counterbalancing cell, in headless Chrome: 62 checks, every answer the
    derived key, every control's event, none in a static half. A keyboard-only session (24
    checks) and S4 in a browser. Every screen compared with the handoff's screenshots.
- 2026-09-27 — **T1 becomes a written two-trend comparison** (uncommitted at time of writing).
  - Docs first (`study-design.md` §2, §4, §5, §7, §10; `visual-spec.md` §10), then code.
  - Schema v11. The `describe` rule in `analysis/keys.py` enforces T1's acceptance rule.
  - Rubric scoring: `scripts/code_justifications.py rubric-sheets` / `rubric`, then
    `score_study.py`.
  - T1's text is masked in the viewer. The practice moved to Myanmar.
  - 1216 tests.
  - Five sessions covering all four cells in headless Chrome, plus one keyboard-only T1, with no
    console errors:
    - T1's box renders in both conditions with no justification box;
    - a blank T1 asks once and logs `skipped: ["answer"]`;
    - T2–T6 logged their derived keys;
    - T1's chips and Reset view were logged only in interactive halves.
  - `irb/questionnaire.pdf` re-exported (36 pages).
- 2026-10-11 — **Three more bars on each T2** (uncommitted at time of writing): A +Kenya, Mali,
  Afghanistan; B +Mali, Cameroon, Mozambique; all below the key, so key, margins and options are
  unchanged. Schema v12. 1217 tests. Headless Chrome, both forms and conditions at 1440 × 790 and
  1366 × 768: labels level, sort and chips logged, no console errors, page height as with seven
  bars. `irb/questionnaire.pdf` re-exported.
- 2026-10-11 — **Ten more dots on each T3** (uncommitted at time of writing): sixteen per form,
  every added dot at least 20 points below the key, so key, margin, closest pair and options are
  unchanged. 13 countries added to the scope (3 African, 10 Asian), 5200 rows; the existing 3900
  rows regenerated byte-identical. Past eight dots the colours repeat and each dot has its own
  shape (`visual-spec.md` §6); dots no longer clip at the plot edge. Schema v13. 1224 tests.
  Headless Chrome, all four cells at 1440 × 790 and 1366 × 768: 16 legend entries inside the
  chart, hover and chips work, chips logged only in interactive halves, no console errors. The
  interactive T3 card now ends 72 px lower (four chip rows, was two), so it scrolls on any window
  under 862 px tall, where before only under 790.
- 2026-10-11 — **Chart handoff, phase 1: the docs** (uncommitted at time of writing).
  `docs/chart-handoff/` restyles every chart; `visual-spec.md` and `study-design.md` §4 record it.
  Nothing built yet. Phases: 2 shared card and line chart; 3 bar and heatmap; 4 scatter and map
  (with B-T5's sixteen countries fetched, flags vendored, schema v14); 5 keys, tests, all four
  cells in headless Chrome at 1440 × 790 and 1366 × 768, compared with the handoff's screenshots,
  and `irb/questionnaire.pdf` re-exported.
- 2026-10-11 — **Chart handoff, phase 2: the card and the line chart** (uncommitted at time of
  writing). Every chart carries the handoff's title and source line, warm axes and gridlines, medium
  weight (a text shadow in the figure) and fixed margins. Line charts: name tags with leaders, the
  ringed end dot, colour by country, no legend (`order_legend` gone; the legend's logging code
  stays). x runs 1999.75-2024.25 so edge dots are not clipped. The line hint and the instructions'
  line bullet no longer name the legend. 1246 tests. Headless Chrome, A-T1 both conditions and the
  practice: 21 checks (tags, hover, a chip hides a whole tag, isolation, Show all, zoom keeps the
  tags and clips the guides, no console errors); plot area measured at 52-846 px as handed off.
- 2026-10-11 — **Chart handoff, phase 3: the bar chart and the heatmap** (uncommitted at time of
  writing). Bars: a colour per country (`config.BAR_COLORS`, searched; every pair on each T2 chart
  clears 12 dE, so no exemption), rounded tops, the order label following the sort. Heatmap: nine
  blue bands, cells drawn as rounded shapes over a transparent trace that keeps the hover, the
  stepped key above, years on top, the "A–Z" label following the row sort; a chip fades a row's
  cells. The blue scale replaces cividis in config. 1254 tests. Headless Chrome, A-T2, A-T4 and B-T4:
  16 checks (sort moves bars and rows and their labels, hover through the transparent trace, chips
  fade, static has no hover, no console errors); the line checks re-run clean.
- 2026-10-11 — **Chart handoff, phase 4: the scatter, the map and B-T5's countries** (uncommitted
  at time of writing).
  - Scope +16 countries for B-T5 (61; 6800 rows): built from the existing raw download, the 5200
    rows before them byte-identical. 16 flags vendored.
  - T5: 18 countries per form, "in Africa"; keys unchanged (3, 2), all 12 derived keys match §4.
  - `analysis/keys.py` enforces the two new clauses: T3's key shares its change colour, T4's key
    cell sits a band below every other row's lowest.
  - Scatter: named dots on knockouts, colour by change, the stepped key in points; no legend or
    shapes (`MARKER_SYMBOLS` gone). Map: the whole continent, seven bands, names inside or on
    leaders (text geo traces, no hover of their own), stepped key without "No data".
  - Schema v14. 1273 tests.
  - Headless Chrome: 15 scatter and map checks (names, hover through a label, chips take names,
    "Below 50" leaves three countries, 18 flags, static has no hover), line and bar/heatmap checks
    re-run clean. Interactive Submit now at 843 px on the map, 898 on the scatter (non-compact).
- 2026-10-11 — **Chart handoff, phase 5: verification** (uncommitted at time of writing). Four
  full sessions, one per counterbalancing cell, at 1440 × 790 and at 1366 × 768 in headless
  Chrome, through the UI: 96 checks each, no console errors; every T2–T6 answer logged as its
  derived key, chips, sorts and the map's threshold logged in interactive halves only, one
  `window_size`, About you once. Every chart compared with the handoff at 2×: fixed the heatmap
  key (46 px right of centre) and Cameroon's map label (crowding Benin's). Bundle 109.9 MB.
  `irb/questionnaire.pdf` re-exported (36 pages). 1273 tests.
- 2026-10-11 — **Six more lines on each T6** (uncommitted at time of writing), eight per form, so
  isolating the two named lines has something to remove. A: +Afghanistan, Chad, Côte d'Ivoire, DR
  Congo, Nigeria, Somalia; B: +Benin, Cameroon, Gabon, Kenya, Madagascar, Sudan; all in scope, every
  series colour used once, keys and band margins unchanged. T6's rule gains T1's clause (no line
  within 5 points of a named one for 5+ years); nearest line to the meeting point 7.4 points (A),
  9.1 (B); the extra lines cross the pair 33 times in each form. DR Congo's line tag reads "DR
  Congo", as on the map. Schema v15. 1275 tests. Headless Chrome, all four cells at 1440 × 790:
  eight lines and tags, hover, isolation and Show all logged in interactive halves only, keys
  logged, no console errors. At 1366 × 768 the interactive T6 Submit ends at 776 px (two chip
  rows, as on T1). `irb/questionnaire.pdf` re-exported.
- 2026-10-11 — **T2 and T4 move to MCV1** (uncommitted at time of writing), so the bank uses two
  of the four vaccines. Keys and their option positions unchanged. T2 gaps 7/6 (A), 6/7 (B), options
  at ranks 1, 2, 3, 4, 8, 10 in both; T4 margins 17 (A) and 10 (B), a pilot check. Guinea and
  Algeria take the colours of the bars they replace. Schema v16. 1276 tests. Headless Chrome, all
  four cells at 1440 × 790: "MCV1 coverage, …" titles, the new bars and options, the heatmap sort,
  no console errors. `irb/questionnaire.pdf` re-exported. Found, not fixed: long one-word options
  overflow their answer tile (B-T2 Mozambique, B-T4 Afghanistan and Madagascar at 1440 × 790; also
  B-T3 at 1366 × 768). The B-T3 and B-T4 cases predate the change.
- 2026-10-12 — **New wording; B-T2 and B-T4 ask new questions** (uncommitted at time of writing).
  T1, T3 (both forms) and A-T4 reworded as Eduardo gave them. B-T2: sixth-highest, 2017, same ten
  bars, key Mozambique 5 / 13 from its neighbours (2021 tied 5th and 6th). B-T4: highest cell; Laos
  and Cameroon replace Myanmar and Uganda (Nepal's 97 was 6 above Myanmar), key Nepal, margin 11.
  The forms now differ in question on T2 and T4, a pilot check (§4, §10). Key positions 0/1/3/3/2/1.
  Schema v17. 1279 tests. Headless Chrome, all four cells at 1440 × 790: every prompt, the new
  options and grid, no console errors. `irb/questionnaire.pdf` re-exported.
- 2026-10-12 — **Answer tiles at 15 px; T1 named in the instructions** (uncommitted at time of
  writing). The tiles' text is 2 px under study.css's 17 (`zz-overrides.css`, `visual-spec.md`
  §10): every option now sits inside its tile at 1440 × 790, 1440 × 900 and 1536 × 864, B-T2's
  Mozambique 2 px into the padding. Practice complete and the second half's closing paragraph no
  longer say every question is chosen and explained (`study-design.md` §8). Headless Chrome, 660
  tiles over every item, form, condition and five window sizes, and the three reworded screens:
  no console errors. `irb/questionnaire.pdf` re-exported. The 2026-09-28 IRB forms checked: the
  request form's §10 fixes are made, and the consent form still matches `src/consent.py` word for
  word.
- 2026-10-12 — **Neon emptied of test data; consent archiving built.** Deleted test IDs `1` (v6)
  and `123123` (v10) and their 175 events. Every table is empty; the sequence is at 10, so the first
  real participant is seq 11 (static first, form B). The four test consent records went to Drive
  by `scripts/archive_consents.py` (an encrypted 7-Zip in `G:\My Drive\Consent Forms`, Oxy account).
- 2026-10-12 — **IRB approved.** Eduardo got HSRRC approval on the forms now in `irb/` as .docx
  (request form submitted 2026-09-30). The request form is the 2026-09-28 PDF's text plus the
  submission date. The consent form is `src/consent.py`'s text, all 961 words, except one curly
  apostrophe ("study’s"), which the app now matches; hash re-pinned to `3bcd2413c9656ae8`.
  `consent.APPROVED = True`. 1288 tests. Headless Chrome at 1440 × 790: no banner, the curly
  apostrophe on screen, a drawn signature recorded under the new version, no console errors.
  `irb/questionnaire.pdf` not re-exported then; it was after the pilot changes, the same day,
  with the new hash.
- 2026-10-12 — **Two full test sessions on production checked, then deleted.** Every answer, timing,
  interaction event, survey and About you landed in Neon (schema v17, no spool, no invalid
  durations; scoring read them). Deleted IDs `98987` and `2310948109832`, their 138 events and the
  two test consent records (not archived). Every table is empty; the sequence is at 12, so the
  first real participant is seq 13 (static first, form A).
- 2026-10-12 — **`/preview`** (uncommitted at time of writing): any item of either form, in either
  condition, on the participant's own task screen, with a bar to switch. Nothing is logged; Submit
  says it saved nothing. Unguarded by Eduardo's choice, so anyone who guesses the path can read both
  forms. 1310 tests. Headless Chrome: chips, bar sort, zoom, static is inert, no new log files.
- 2026-10-12 — **`/preview` is local only** (uncommitted at time of writing): `uv run python -m
  src.app` serves it; the deployed app (`create_app()`, preview off) does not, so trying a change
  needs no commit and production no longer exposes both forms. 1312 tests. Headless Chrome: the
  local /preview draws its chart and logs nothing; the deployed app's /preview is the study.
- 2026-10-12 — **Pilot session 1**, with Eduardo's faculty supervisor (static A, then interactive
  B; 36 min). Findings, the transcript, and the changes it led to are in `study-design.md` §10. The
  plan runs in phases:
  - Phase 0: keep the pilot out of the study data; ask HSRRC about an amendment (none needed,
    HSRRC answered the same day).
  - Phase 1: quick fixes.
  - Phase 2: line chart.
  - Phase 3: clickable keys.
  - Phase 4: T7, replaced the same day by overloading T1 with controls.
- 2026-10-12 — **Pilot data out of Neon (phase 0).**
  - Participant `1`'s 85 v17 events and registration were exported to `data/study_logs/pilot/`,
    then withdrawn with `withdraw_participant.py --apply`: 0 events left, ID `1` marked withdrawn.
  - The sequence is at 13, so the first study participant is **seq 14 (interactive first, form
    A)**.
  - The pilot's consent record is still in Neon (one row). Eduardo archives it with
    `archive_consents.py`, which asks for the password.
- 2026-10-12 — **Pilot changes, phase 1** (committed as 2a5e7f9). Practice window
  2019–2021. Heatmap sort A–Z / Lowest cell first / Highest cell first (B-T4's key row now comes
  to the top too). Chips at most six to a row, five on the map beside the Highlight box, named as
  the chart names them ("DR Congo"). The line hint names hover. A full-screen request on the first
  instructions screen, "explain each one on its own" in the second half, and a researcher script
  (§8). Schema v18. 1333 tests. Headless Chrome, both forms and conditions at 1440 × 790, 1366 ×
  768 and 1440 × 900: no chip row wraps, the sort brings each T4 key row to the top, the new
  wording is on screen, no console errors. Against the committed version, only the interactive
  T3 card moved (36 px up). Found, not caused: the interactive T1 card ends at 802 px on a
  790-tall window.
- 2026-10-12 — **Pilot changes, phase 2: the line chart** (committed as 2042564).
  - A Years range slider replaces View, with Show all under it. It zooms the x axis, follows
    every other zoom, and its handles take the arrow keys, with no number boxes (Dash 4's commit
    only on blur). Reset view now undoes a zoom.
  - A click on a line focuses it: the others and their tags fade to 0.15 and take no hover or
    click, and the chips stay ticked. plotly.js ignores `hoverinfo` on a trace with a
    `hovertemplate`, so the faded lines' templates are dropped; only a browser showed it.
  - The chip group is never rebuilt now (`ControlResult.group` gone).
  - 1365 tests. Headless Chrome: 23 checks (keyboard, drag, plot-drag, wheel and Reset axis all
    move the slider; focus, Show all, Reset view; static has no slider), with the log showing one
    event per action and none spurious, and no console errors.
  - Line-chart cards are 12 px shorter: T1 now fits a 790 px window, not a 768 one.
- 2026-10-12 — **Pilot changes, phase 3: the key's colours** (committed as 12abf80).
  - On the scatter, heatmap and map, a click on a key block highlights its band: other marks fade
    to 0.15 (dots, single cells, countries by selection). Several bands can be chosen; a second
    click releases one, and so does Reset view.
  - The buttons are native, an overlay over the key in `.ui-chart`, placed from
    `figures.key_blocks`, which the key builders now share. All 13 figures are byte-identical to
    before.
  - The map's "Below [n] %" box went. Its chips run 6/6/6 again, and its card is 36 px shorter
    (fits 1440 × 790).
  - Clicks are told from render-time firings by `n_clicks` > 0 (`app._key_press`).
  - 1394 tests. Headless Chrome: 23 checks (each button over its own colour by pixel, clicks and
    Space, the pressed outline and `aria-pressed`, hover through the overlay, each chart's fade,
    the sort with a band, static has no buttons), one logged event per click, none on load, and no
    console errors.
- 2026-10-12 — **Pilot changes, phase 4: T1 overloaded** (committed as 3f71605).
  - T7 was specified, then dropped by Eduardo for this. A-T1 and B-T1, interactive only, carry a
    second strip under the first: Coverage (a 0–100 range slider that zooms the y axis and
    re-places the name tags), Order (the chips A–Z or by coverage in 2000 or 2024; the lines
    never move), Regions (four boxes that hide or show a region's lines; Europe disabled on
    B-T1) and Show (points, name tags). Named in no instruction and no hint.
  - Every figure byte-identical at rest. Each control logs one event; Reset view puts all four
    back.
  - Kept in RQ1, and reported alone as a pre-registered secondary: accuracy, median time and
    each control's users and counts by condition (`analysis/report.overload`, the viewer).
  - 1431 tests. Headless Chrome, both forms at 1440 × 900: 38 checks (keyboard on Coverage,
    the chip reorder without a renderer error, regions and chips agreeing, points and tags off,
    Reset view; T6 and the static T1 carry none of it), one logged event per action, no console
    errors.
  - The interactive T1 card is 106 px taller: Submit ends at 932 px (896 in compact mode), past
    a 1440 × 900 window by 32 px, the only card that is. Recorded as a pilot check.
  - A fast keyboard run can commit a slider twice with the same `previous`; the chart ends where
    the slider does. The Years slider is the same.
- 2026-10-12 — **No amendment; questionnaire re-exported; a redraw race fixed** (uncommitted at
  time of writing).
  - HSRRC: the pilot changes need no amendment (`study-design.md` §10).
  - `irb/questionnaire.pdf` re-exported (37 pages). The Years and Coverage sliders printed as
    empty boxes, since Dash draws them from script; the exporter now draws them at rest. The cover
    names T1's extra controls.
  - Production serves 3f71605, checked over HTTP (stylesheet, callbacks); the Vercel API still
    refuses this team.
  - Found by a full session in headless Chrome: on T4, Reset view right after a sort and a key
    colour did nothing and logged nothing. Dash drops a reply still on its way when a callback
    fires again, and the heatmap took over a second to redraw (each cell added by `add_shape`,
    which re-validates every shape already there). Now the cells are assigned at once, about 0.1 s,
    every figure byte-identical by hash; and while the chart redraws, the controls, key buttons,
    Reset view and chart take no pointer events (`visual-spec.md` §7). Under an 800 ms round
    trip: clicks during a redraw are ignored, the next one works, the log matches the screen.
  - 1434 tests. Eight full sessions through the UI in headless Chrome, all four cells at 1440 ×
    790 and 1366 × 768, every control used in the interactive halves: 504 checks, none failed,
    no console errors. Every T2–T6 answer logged as its derived key, T1's text as typed; each
    control's event logged; none in a static half; every record v18; consent, window size and
    About you once each, both surveys.
- 2026-10-12 — **The map draws no land but Africa** (uncommitted at time of writing). Plotly's
  Africa file filled only Africa, but its coastline also traced Spain, Italy, Greece, Turkey and
  Arabia. `vendor_map_geometry.py` now makes the coastline the land's own rings (Sinai's land
  border gains its line); nothing else in the file changes, and every figure is byte-identical, so
  no schema bump. `visual-spec.md` §1, §4. A test holds the land and coastline to Africa's outline.
- 2026-10-13 — **Line charts drawn from 1985** (docs committed as e494955; code uncommitted at
  time of writing).
  - Scope 1985–2024, 10,880 rows; every row from 2000 on byte-identical. Every line item still
    asks about 2000 onward (`tasks.ASKED_FROM`); T6 now says "after 2000".
  - A-T1 draws Gabon for Nigeria; B-T6 Ghana and Guinea for Cameroon and Madagascar. Keys,
    options and margins unchanged.
  - `analysis/keys.py` judges the answer on 2000–2024 and the close-run clause on 1985–2024; the
    old lines are refused by test.
  - x axis 1984.6–2024.4 (`LINE_X_PAD` 0.4 year, still 8 px); Years slider marked every 13 years.
  - Found and fixed: "Highest in 2000" read each country's first year, which would have become
    1985, where Ukraine has no value.
  - The gap caption names only years from 2000 on, on a line chart (Eduardo), so A-T1 carries
    none for Ukraine's 1985–1991; its card is B-T1's height again.
  - Schema v19. 1450 tests.
  - Headless Chrome, `/preview`, every line chart in both forms and conditions: 102 checks, no
    console errors. "after 2000" wraps A-T6's heading at 1440 wide (+29 px, both conditions).
  - The controls strip stands 14 px below the chart, not 2 (Eduardo): the source line sits 17 px
    above the strip's legend, not 5. Interactive only, since the strip is; every interactive
    Submit 12 px lower (T1's split 944 px), static cards unchanged (`visual-spec.md` §10).
  - `irb/questionnaire.pdf` re-exported (37 pages). No full session was run through the UI.
  - ~~Not to be deployed until HSRRC answers.~~ Deployed with f507160; HSRRC approved it on
    2026-10-13, with the consent form unchanged (`study-design.md` §10).
- 2026-10-13 — **Four more rows on each T4 heatmap** (uncommitted at time of writing), twelve per
  form. A +Cote d'Ivoire, Iraq, South Africa, Syria; B +DR Congo, Ethiopia, Nigeria, Yemen; all in
  scope, beyond the six option rows, none on the other form's grid. Key, margin and options
  unchanged. Rows 31.17 px tall. Schema v20.
  - Six full-size chips did not fit one line beside Sort rows, so the heatmap's chips are smaller
    (15 px text, 21 × 14 flags, tighter padding and gaps; `.ui-chips--tight`) and run 6/6. No
    other chart's chips change.
  - Headless Chrome, `/preview`, both forms and conditions at 1440 × 790, 1366 × 768 and
    1440 × 900: 109 checks, no console errors. Every card ends where it did; T4's interactive
    Submit is at 787 px (751 compact), static 635. The other charts' chips are unchanged.
  - **`/preview` adds its own bar above the task** (104 px, 112 outside compact mode).
    Subtract it before comparing Submit positions with `study-design.md` §10.
  - `irb/questionnaire.pdf` re-exported (37 pages).
- 2026-10-13 — **Chips spread across their rows on every chart** (uncommitted at time of
  writing): `justify-content: space-between`, which the handoff set on the line charts alone; the
  bar, scatter, heatmap and map had packed theirs left (`visual-spec.md` §7.3). T1's Regions and
  Show stay packed left. Interactive only, no figure change, no schema bump. 1453 tests.
  - Headless Chrome, every chart in both forms at 1440 × 900 and 1366 × 768: 73 checks. Every
    row runs edge to edge on one line and takes clicks.
  - Strip heights, Submit and T1's other boxes are where the committed version has them. No
    console errors.
  - `irb/questionnaire.pdf` re-exported.
- 2026-10-13 — **Five more dots on each T3 scatter** (uncommitted at time of writing), twenty-one
  per form, so the interactive chips fill three rows of seven (13–26 px apart; sixteen ran 6/5/5,
  up to 99 px apart). A +Algeria, Eritrea, Guinea, Namibia, South Africa; B +Benin, Central
  African Republic, Cote d'Ivoire, Gabon, Sudan. Key, margin and options unchanged. Schema v21.
  - Eduardo's choices: full-size chips with the scatter naming the CAR "CAR", over the heatmap's
    smaller chips; and B sharing three of A's dots, over expanding the scope.
  - Found by search over the scope. Every added dot is 4+ points from the others and improves 20+
    less than the key, the chips fit seven to a row, and every name places clear of every other
    name and dot. A's closest pair is now 4.1 points (6.1 before), and its pairs within 8 points
    went from 1 to 6, against B's 7.
  - `CHIPS_PER_ROW` 7. No other chart's rows change.
  - New test: no scatter name touches another name or dot. 1459 tests.
  - Headless Chrome, `/preview`, both forms and conditions at 1440 × 790, 1366 × 768 and
    1440 × 900: 95 checks.
    - T3: rows 7/7/7 edge to edge; no name touching a name or dot, as drawn; hover; a chip hides
      a dot with its name; a key colour fades the rest; static inert.
    - Every Submit where the committed version has it, on every item, and no console errors.
  - `irb/questionnaire.pdf` re-exported.
- 2026-10-13 — **HSRRC approved the 1985 start**, with the consent form unchanged.
- 2026-10-13 — **Full sessions on f48d2e0, which production serves** (checked by hashing its
  served assets against each commit).
  - Eight sessions, all four cells at 1440 × 790 and 1366 × 768, in headless Chrome through the
    UI: 1232 checks, no console errors.
  - Every answer logged as its derived key, every record v21, and `year_range` `[1985, 2024]`.
  - On screen: the 1985 axis; T3's 21 dots with chips 7/7/7; T4's 12 rows with chips 6/6; every
    entity named.
  - Two checks failed, both one bug: arrow keys on the Years slider 120 ms apart left the chart a
    year behind the slider. Dash 4 draws the view callback's replies as they arrive, an older one
    after a newer one, and a line chart's reply now takes 0.25–0.5 s.
- 2026-10-13 — **The keyboard is held while the chart redraws** (uncommitted at time of writing;
  `visual-spec.md` §7, §8).
  - `src/assets/redraw_guard.js` drops keys on the elements the CSS pointer guard covers. Tab and
    the modifiers still work, and a held arrow key moves a slider one step per redraw.
  - A test ties its selector list to the CSS guard's. 1470 tests.
  - Headless Chrome: 16 race trials (120 ms presses and a held key) with no mismatch, the requests
    in order. With replies slowed to 1.5 s, 10 of 10 key checks pass: Space, Enter and arrows are
    held, Tab and typing in the answer box are not, a Space let go after the redraw toggles
    nothing, and every key works afterwards.
  - The eight full sessions re-run with it: 1248 checks, none failed. Each Years `view_change`'s
    `previous` is the value logged before it.
- 2026-10-13 — **No further pilot** (Eduardo): the study starts at seq 14. §10's pilot checks
  are read from the study's data (`study-design.md` §10). Answer-tile overflow accepted, since
  participants work full screen. The 22 local test logs from 2026-10-11 were deleted;
  `data/study_logs/pilot/` is kept.
- **Still to do before the study:**
  - Commit and push the keyboard guard, then confirm production serves it. Over HTTP,
    `/assets/redraw_guard.js` must match the committed file. The Vercel CLI is not installed and
    the API refuses this team.
  - Archive the pilot's consent record, still in Neon (one row), with
    `scripts/archive_consents.py`.
  - Optional: `scripts/verify_deployment.py`. It tests the database only, not the site. Its
    three synthetic participants use three sequence numbers, so the first participant becomes
    seq 17 (static first, form A) instead of 14.
- Next: the study (n ≥ 25), and the checks in `study-design.md` §10, read from its data: static
  accuracy on T2, T4 and T5 (margins sit at the floor), T1, B-T3 and T6 form equivalence, T6
  strict against adjacent-band, whether T4 sits at ceiling in the interactive condition, whether
  the chips, the bar and heatmap sorts and the key's colours are found at all, and whether T1's
  four extra controls are found and what they cost in time.

## Decisions made

- 2026-09-08 — Python floor stays at 3.11; `uv.lock` committed for reproducibility.
- 2026-09-15 — Year-over-year change is a hover-tooltip delta, not an on-chart glyph. It is the only
  treatment that is interactive-only *and* leaves the two figures identical. `visual-spec.md` §7.1.
- 2026-09-15 — Sorting reorders the entity control list, never the chart; a time-series line chart
  has no meaningful row order. `visual-spec.md` §7.2.
- 2026-09-15 — Instructions are shown before **both** conditions, practice before only the first.
  Showing instructions once would leave whoever draws interactive second unaware the controls exist.
- 2026-09-15 — T1's answer key in `study-design.md` was wrong (said 2, is 1). The doc listed six
  coloured countries, which `MAX_SERIES = 5` forbids; the task set was always correct.
- 2026-09-16 — Answer keys are derived from the data and cross-checked against §4, never only
  transcribed. They live in `analysis/`, which does not ship.
- 2026-09-16 — T5's keys sit on the last year of their bands: strict scoring is primary, adjacent-band
  credit is a pre-registered secondary. `study-design.md` §4. (Extended to T4 on 2026-09-22.)
- 2026-09-16 — On a DB failure: retry, then spool to browser session storage first and `/tmp` second.
  `/tmp` alone is not recoverable on Vercel. Interaction events never retry, because a retry inside
  the task window would inflate time-on-task in the interactive condition only.
- 2026-09-16 — `event_uid` and the one-answer-per-task index added now, while schema changes are
  free because nothing has been collected.
- 2026-09-16 — A mid-task reload records the duration absent and flagged `clock_reset`; it used to
  restart the timer silently. The task clock stamps each screen once. `study-design.md` §8.
- 2026-09-16 — Registration looks an ID up before inserting. A repeat registration (even a
  double-click on Continue) burned a sequence number and skipped the next participant's cell.
- 2026-09-16 — Schema v5: Postgres `server_ts` is the record's creation time, not the insert time.
- 2026-09-16 — The chart's 520 px is reserved before Plotly loads, in both conditions; the practice
  screen used to jump 520 px under the cursor. `visual-spec.md` §5.
- 2026-09-16 — Collected data is viewed in a **local** Dash viewer (`scripts/view_data.py`), not an
  admin page on Vercel: correctness needs the answer key, which must not ship. Justifications are
  masked by default to protect the §7 coding blind.
- 2026-09-16 — Resume is not built; the ID screen now asks for one sitting in one tab instead of
  promising it. Enter in the ID box submits it. `study-design.md` §8.
- 2026-09-21 — The IRB approval request form outranks `study-design.md`. Signed consent goes to its
  own table with no participant ID, exported to the Oxy Drive and purged. A skip scores incorrect
  (primary), excluded (secondary). Demographics after the ID. Likert 7-point, after each condition
  — the consent form says so, and one rating after both could not be split by condition. Hover
  logging scrapped. Neon stays the collection store; Sheets would lose the sequence and the
  one-answer index.
- 2026-09-22 — Task set finalized under an item acceptance rule (`study-design.md` §4).
  - Four clean crossing items were not possible: DTP3 has only three clean crossing events. Eduardo
    chose to keep two crossings per form, reassigned to the robust ones. A-T4 moved to Polio3; B-T5
    keeps the China/Brazil tie and is flagged for the pilot.
  - The adjacent-band secondary now covers T4 and T5.
  - T6 is scored separately from RQ1.
  - End labels are spread apart in the figure, identically in both conditions.
  - The questions go to the IRB as a separate attachment, not into the consent text. Participants
    read the consent form just before the tasks, so quoting the items there would show them both
    forms' questions in advance.

- 2026-09-23 — Task bank replaced (`study-design.md` §4, `visual-spec.md`). Eduardo's choices:
  - **Keep the acceptance rule** and re-tune the spec's items that break it, rather than adopt
    items only the interactive condition could answer.
  - **Extend the palette to eight colours**, rather than trim the charts to five. Chosen by search;
    every pair at least 12 ΔE2000 apart under simulated protanopia and deuteranopia.
  - **All four new chart types in one pass.**
  - **The map's filter is a range slider** the participant sets, not a "below 50%" button that
    names the question's threshold.
  - Following from those, taken without asking:
    - the bar sort reuses "as listed / by coverage" and moves the bars;
    - hovers stay unlogged, so affordance use on T2, T4 and T5 is unobservable;
    - the practice moved to Brazil, since Ukraine is now A-T1's subject;
    - the gap and crossing items went, and with them T6's separate reporting and the
      adjacent-band secondary.
- 2026-09-23 — **T7 (now T6), a crossing item, added** after the bank was replaced: the six items asked
  about one series or one set of values, none about how two series relate. Eduardo chose the pairs
  and kept T7 after weighing it (it will likely sit near ceiling in both conditions).
  - Adjacent-band credit is back as a pre-registered secondary, for T7 only.
  - Taken without asking: no World line on either T7 chart. In B it runs within 2 points of the
    crossing, and the crossing rule now refuses any line that does. Dropped from A too, so both
    forms draw two lines.
  - The crossing rule is the 2026-09-22 one, tightened: the overtaker must trail before the
    crossing and lead after it, by 5 points somewhere on each side.
- 2026-09-25 — **The largest-rise item (T2) dropped**, so line charts carry two items per form, not
  three. Eduardo's choice, over dropping T1: T1 is the only item that needs the line controls the
  IRB forms describe, and the only line item whose affordance use is logged. The year-over-year
  tooltip stays on every line chart. T3–T7 renumbered T2–T6, so schema v8. `study-design.md` §4.
  Position 4 now holds 4 of the 12 keys, exactly the one-third ceiling.
- 2026-09-25 — **The design handoff is the new study** (`docs/study-redesign.md`). Eduardo's §4
  answers:
  - A-T1's sixth option is **2004**: the handoff's 2012 fails the acceptance rule (2014, read a
    year early, is nearest 2012).
  - A-T5 keeps **its 13 countries**: the handoff's set fails the rule (South Sudan 53, Guinea 56,
    Ethiopia 59 in 2013), so the scope is unchanged.
  - The map's control becomes the handoff's **"Below [n] %" box**; the objection to a preset button
    was that it named the threshold, and the box names none.
  - **Paas is kept** as the survey's first question.
  - **Form B's sixth options** mirror A's: B-T1 +2005 and no World line, B-T2 +Nigeria, B-T3
    +Indonesia, B-T4 +Madagascar.
  - Line charts keep **end labels, with the legend to their right**.
  - Taken on the proposals in the phase-1 plan: chip labels without values, the heatmap's one-click
    row sort, About you logged after the second `session_end`, S4 also when the spool is full, the
    4b instructions carrying 9b's control bullets.
- 2026-09-26 — **Phase 4, taken without asking** (reported for review):
  - Dash 4's option lists cannot carry the handoff's label classes, so a generated bridge
    stylesheet re-aims study.css's own rules at them (`visual-spec.md` §10).
  - A zoom is kept by the app, in the view, and redrawn with every control. Plotly's `uirevision`
    cannot keep it through dcc.Graph, which re-plots after each zoom with a figure Plotly has
    already edited. A zoom itself sends nothing back: the reply used to undo it.
  - A reorder of the chips rebuilds their group; sending the two checklists new options made
    Dash 4's renderer throw when a flag-and-name label moved between rows.
  - Chips toggled from the legend follow it, and an isolated line shows as its chip alone.
- 2026-09-26 — **Phase 5, taken without asking** (reported for review): the handoff's inline sizes
  on the short screens are classes in `zz-overrides.css`; "ID:" is a `<label>`, not hidden; only
  an empty ID marks the field invalid, by a clientside script, since `dcc.Input` has no `aria-*`.
- 2026-09-26 — **Phase 6, taken without asking** (reported for review): the pad keeps its 600 ×
  150 proportions (120 px tall), not screen 1's 74 px, which stretched the signed copy; fixed
  along the way: signature points are kept on the pad, and a text field drew a second focus ring
  inside its box (phases 4 and 5).
- 2026-09-26 — **Phase 7, taken without asking** (reported for review): a skip is confirmed when
  Next leaves the page, and at Continue for the last page only; typing beside "Other" chooses it;
  the "Other" box is laid over its option's cell. Found and fixed: dcc.Input reports a number
  outside its `min`/`max` as null, so an age of 7 was logged as a skip since phase 2; the field
  now has no range and Next refuses it on its page.
- 2026-09-26 — **Scrolling accepted** (Eduardo) for the two layouts left open by phases 4 and 5:
  the instruction screens, and the interactive scatter and map task cards on a window 790 px tall
  or less. The second makes interactive participants scroll to Submit on T3 and T5 where static
  ones do not; it is listed for the pilot in `study-design.md` §10.
- 2026-09-26 — **Phase 8, taken without asking** (reported for review): S4 keeps the stores as
  written and shows the position of the screen it replaced; the questionnaire PDF prints the
  screens in the app's own stylesheets, landscape, with every survey question shown.
- 2026-09-26 — **About you stays as asked; request form item 17 is amended** (Eduardo, option A),
  rather than turning age back into ranges. The revised form promises answers under the participant
  ID only, age out of the linking file, and "Other" text never quoted. `study-design.md` §6.2 also
  reports About you only in aggregate (age as median and range), groups under five combined or
  withheld; the form does not carry that rule. The consent form's Procedures gains a sentence
  naming the background questions (age, field, experience with charts); `src/consent.py` carries
  it, with the revised form's straight apostrophe in "study's", and the hash is re-pinned (§9).
- 2026-09-26 — **Window size logged once, at the start** (Eduardo; schema v10), so the pilot can
  tell who had to scroll on the interactive T3 and T5 cards. Request form 5B's list of what is
  logged does not name it yet (`study-design.md` §10).
- 2026-09-27 — **T1 replaced by a written comparison of two trends** (Eduardo), because no item
  asked for an interpretation of a time series, which the title promises.
  - Kept in RQ1. Correct only if all three rubric parts are stated and none is contradicted.
  - Form A: India and Ukraine (chart unchanged). Form B: Brazil and Uganda; B's chart swaps India
    and Myanmar for Uganda and Nepal.
  - The practice moves from Brazil to Myanmar.
  - Ukraine's collapse has no match in scope, so the forms match in structure, not size; this is a
    pilot check. `study-design.md` §4.
- 2026-09-23 — Box and lasso select removed from every chart's modebar, including the line charts,
  where they had been since the start: they dim marks with no event recorded. `visual-spec.md` §7.5.

- 2026-10-11 — **The chart handoff** (`docs/chart-handoff/`). Eduardo's choices:
  - Line charts lose the legend; the name tags and the chips do its work.
  - The scatter is as handed off: names beside dots, colour by change, a stepped key, no legend
    or shapes. T3's static cost changes (`study-design.md` §4), and the key must share its colour.
  - A colour per bar. The handoff's extra colours fail the colour-blind floor, so the bar colours
    are searched; every pair on a chart clears 12 ΔE, so no exemption was needed after all.
  - T5 stays on Africa (the world map fails the rule in every year), with the handoff's countries
    less Somalia and Ethiopia: 18, keys unchanged. Form B: 18 too, Chad, Somalia and sixteen new
    countries. The prompt says "in Africa".
  - The handoff sets the style only; the content stays §4's.
  - Taken without asking: World stays black and dashed; the scatter key reads "pts"; the map key
    has no "No data" block; the map keeps its chips (18 per form); the bar and heatmap order labels
    follow their sorts; medium weight is drawn as the handoff's 0.45 px stroke.

- 2026-10-11 — **T6 goes from two lines to eight** (Eduardo; five first, then eight), so the
  interactive condition can show a benefit beyond hover. Taken without asking: the six countries
  per form (found by search: each crosses the pair away from where they meet; none shared between
  forms; not Congo beside DR Congo), adding T1's close-run clause to T6's rule, and "DR Congo" on
  the line tag.

- 2026-10-11 — **T2 and T4 move to MCV1** (Eduardo, over keeping DTP3 throughout). Taken without
  asking: which items (T4's B grid passed unchanged; T5 failed in every year; T2 was the next
  cheapest), the swaps (Guinea, Algeria, Benin, each found by search with the key and its option
  position kept), and Benin over Niger in A-T4, which would have matched B's margin but shared a
  third identical row across forms.

- 2026-10-12 — **After pilot session 1** (Eduardo; the supervisor's points are in `study-design.md`
  §10).
  - A Years range slider replaces View on line charts. Zoom is named once in the instructions.
  - A click on a colour in the key highlights it on the scatter, heatmap and map. The map's
    "Below n %" box goes: the supervisor found it mirrored the question ("almost cheating").
  - ~~T7 is added: an at-a-glance item, scored separately~~ T1 is overloaded instead (Eduardo,
    the same day), as the supervisor's counterpoint where interactivity may not help: four
    controls it does not need, interactive only, told to no participant. Kept in RQ1 and also
    reported alone; T1's interactive difference is the overloaded interface's, never
    interactivity's alone (`study-design.md` §7).
  - The main study stays logging only: no think-aloud, no questions at the break, no debrief.
  - Taken on recommendation:
    - practice window 2019–2021;
    - clicking a line fades the others instead of hiding them;
    - heatmap sort by lowest or highest cell;
    - chips at most six to a row.

- 2026-10-12 — **Line charts drawn from 1985** (Eduardo), so the Years slider has years to set
  aside; every line item still asks about 2000 onward (`study-design.md` §4).
  - A start in 1980 and a question about all of 1985–2024 were weighed and not taken (§4, the
    revision).
  - T6 says "at some point after 2000" (Eduardo's wording of two offered), since both its pairs
    cross before 2000.
  - The close-run clause is kept over every drawn year (Eduardo), so A-T1's Nigeria and B-T6's
    Cameroon and Madagascar were replaced.
  - No caption for Ukraine's 1985–1991 on A-T1 (Eduardo): a line chart's gap caption names only
    years from 2000 on.
  - Taken without asking:
    - Gabon, Ghana and Guinea, found by search;
    - 2000 with no mark of its own on the chart or the slider;
    - the axis padding at 0.4 year, the slider marked every 13 years;
    - "Highest in 2000" kept;
    - T1's rubric neither needs nor penalises 1985–1999.

- 2026-10-13 — **Before the study** (Eduardo):
  - **No further pilot**: straight to the study.
  - **Answer-tile overflow accepted as it is**, since every participant works full screen. A
    full screen on a 1366 × 768 display is still that size; `window_size` shows who met it.
  - **The keyboard is held while the chart redraws** (`visual-spec.md` §7), reversing "the
    keyboard is not held" of 2026-10-12.

## Open questions

- ~~Answer tiles overflow on narrow windows (found 2026-10-11).~~ Accepted as it is (Eduardo,
  2026-10-13): participants work full screen. At 1366 × 768 form B's Mozambique (B-T2's key) and
  Bangladesh still run past their tiles; at 1280 × 720, 108 of 132 options do
  (`study-design.md` §10).

- ~~Does HSRRC accept a drawn electronic signature?~~ Settled by the approval (2026-10-12): the
  approved request form's item 12A describes it.
- Does a countersignature printed in advance count? Neither approved form mentions it. Since 2026-09-26 the consent screen shows
  Eduardo's signature image, the day's date and his name on the researcher's line
  (`RESEARCHER_SIGNATURE`, a Vercel env var, never in git; unset, the line is blank). Since
  2026-09-27 the participant's PDF and the Oxy Drive copies (`export_consents.py`, run with
  `--env-file .env.local`) carry it too, so nothing is countersigned by hand. Ask HSRRC alongside
  the drawn-signature question. Still unasked as of the approval (2026-10-12).

## Reports & external material

<!-- e.g. - [Lit review draft](docs/lit-review.md) — 12 sources, interaction & cognitive load -->

- `irb/Oxy CS Senior Comps Approval Request Form.docx` — the IRB approval request form **as
  approved** (2026-10-12; submitted 2026-09-30). The `.pdf` beside it is the 2026-09-28 revision,
  the same text without the submission date. (Revised 2026-09-21 and 2026-09-26; renamed and
  revised 2026-09-28, which made the §10 fixes and re-dated the signatures.) **Gitignored; local
  only, never commit.**
  It **outranks
  `docs/study-design.md`** (Eduardo, 2026-09-21): where they disagree, the form wins and the doc is
  changed to match — or, if following the form would break the method, flag it so the form is
  amended before submission rather than silently diverging. Read it before any decision on consent,
  recruitment, data handling, tasks, or measures; what it requires is written into
  `docs/study-design.md`, not into the form's folder. Extract text from the `.pdf` with `pdftotext`
  (poppler for the Read tool is not installed); from the `.docx`, unzip `word/document.xml` and
  read its `w:t` runs with the stdlib.
- `irb/Oxy CS Senior Comps Informed Consent Form.docx` — the informed consent form **as approved**
  (2026-10-12), the text participants sign. The `.pdf` beside it is the 2026-09-27 copy, with a
  straight apostrophe in "study's" (revised 2026-09-21; revised 2026-09-26 for the redesign and
  the background questions; renamed 2026-09-27). Also gitignored. `src/consent.py` matches the
  `.docx` character for character (checked 2026-10-12, all 961 words), and the hash pinned in
  `tests/test_consent.py` guards that transcription.
