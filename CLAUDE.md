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

### Static vs. interactive is a single toggle

- Exactly one boolean separates the conditions, and it is consulted in exactly one place:
  `graph_config(interactive: bool)` in `src/figures.py`.
- **`build_figure()` takes no `interactive` argument at all.** The chart is identical in both
  conditions *by construction*, not by discipline — interactivity is a property of how the figure is
  rendered, not of the figure. `tests/test_conditions.py` asserts the two conditions produce
  byte-identical figure JSON.
- Interactive-only features: filtering, sorting, line isolation, and year-over-year directional
  change. All four are built; all four are defined in `docs/visual-spec.md` §7.
- **Year-over-year change lives in the hover tooltip, not on the chart** (`visual-spec.md` §7.1). A
  drawn indicator would have to be present in one condition and absent in the other, which
  `build_figure` makes impossible by construction. The tooltip text is in both figures and
  `staticPlot: True` is what keeps it out of the static condition's reach.
- **Filtering hides series; it never rebuilds the chart from a shorter list** (`figures.set_visible`).
  Colour is assigned by position, so a rebuild would recolour the survivors mid-task.
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
- **Countries (10):** US, UK, Brazil, India, Nigeria, Ethiopia, Indonesia, Ukraine, Pakistan, China.
- **Aggregates (7):** World, Africa, Asia, Europe, North America, South America, Oceania.
- **Years:** 2000–2024. 17 entities × 25 years × 4 vaccines = **1700 rows**.
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
build artifact (~60 KB, 1700 rows), produced by `scripts/export_deploy_data.py` from the validated
parquet, never hand-edited. Regenerate it whenever the data is refreshed. Raw downloads and the
parquet cache stay gitignored as before.

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
  path reads the deploy CSV with the stdlib `csv` module instead. Measured bundle: **108.9 MB**
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
  (Paas + three Likert items), demographics, and a `consent` event. Hovers are **not** logged
  (decided 2026-09-21).
- **Names and signatures never enter the event log.** The signed consent record goes to its own
  `consent_records` table (or `data/consent/` locally), which has no participant ID so it cannot be
  joined to answers — IRB form items 15 and 17. `scripts/export_consents.py --purge` moves it to the
  Oxy Drive and out of Neon.
- This logging IS the study data. Do not remove, disable, or "clean up as unused" any logging code.
- Log schema changes are breaking — flag them explicitly. Bump `SCHEMA_VERSION` in `src/logging.py`.

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

- **UK HepB3 reports only 2019–2024** (19 of 25 years missing). The UK added HepB to the routine
  infant schedule in 2017. Any task comparing HepB3 across countries shows the UK as a near-empty
  line, and participants may read absence as zero coverage rather than "not reported".
- Ethiopia HepB3 missing 2000–2006; Nigeria and India 2000–2003; Pakistan 2000–2002.
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
  study-design.md       # RQs, conditions, the 12 items, measures, rubric, consent, withdrawal
src/
  config.py             # INTERACTIVE flag (local default only), palette, scope
  data.py               # load + clean — pandas, local only
  consent.py            # the consent form's text, the signed record, stored apart from study data
  contrast.py           # WCAG luminance/ratio maths; drives the palette script and its tests
  runtime_data.py       # stdlib csv loader; NO pandas
  db.py                 # Neon Postgres connection, DDL, and the 2x2 assignment rule
  figures.py            # build_figure + graph_config(interactive) — the one decision point
  layout.py             # shared layout components, study screens, interactive controls
  flow.py               # study flow state machine
  tasks.py              # the 12 items, forms A and B. NO answer key — it ships to the browser
  logging.py            # event/timing logger; Postgres or JSONL sink
  app.py                # Dash app factory, callbacks, clientside timing, Submit and skip guards
  assets/
    signature.js        # the consent screen's signature pad; Dash serves assets/ automatically
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
  withdraw_participant.py # IRB item 13: delete one ID's events everywhere; dry run by default
  derive_keys.py        # print the derived answer key; exits 1 if it disagrees with §4
  score_study.py        # accuracy, Paas, timing, exclusions -> data/study_logs/derived/
  code_justifications.py # blind sheets, kappa, reasoning depth -> data/study_logs/coding/
  view_data.py          # local data viewer on 127.0.0.1:8051; read-only
  check_contrast.py     # WCAG contrast report for the palette
  check_bundle.py       # serves the app from requirements.txt alone, in a throwaway venv
  verify_deployment.py  # round-trips a synthetic session through the real database, then deletes it
tests/
  test_data.py          # cleaning, the complete grid, the missing-data guarantees
  test_runtime_data.py  # the csv loader — and fails the build if a runtime module imports pandas
  test_palette.py       # enforces the contrast floors
  test_conditions.py    # the two conditions must produce identical figure JSON
  test_tasks.py         # item structure, and that no answer key ships
  test_flow.py          # the stage sequence and the counterbalancing
  test_logging.py       # event schema, both sinks, retry/spool/circuit breaker
  test_db.py            # failure classification, timeouts, schema migrations — no live database
  test_recover_spool.py # replay is dry by default, ordered, idempotent, never deletes
  test_scoring.py       # derived keys match §4; each rule refuses an ill-posed item; key never ships
  test_analysis.py      # real app sessions scored end to end; exclusions; coding harness; kappa
  test_viewer.py        # each health check trips on its fault; masking; download re-scores
  test_app.py           # callbacks called directly, a DB outage, clientside JS run under Node
  test_consent.py       # the pinned consent text, the signed record, export and withdrawal scripts
```

### Study protocol

- `docs/study-design.md` is the source of truth for the protocol. Change it before `src/tasks.py`.
  **The IRB approval request form (`irb/`, local only) outranks it.** Where they disagree, change the
  doc to match, or list the mismatch in `study-design.md` §10 so the IRB paperwork is amended.
- **The consent text in `src/consent.py` is the HSRRC-submitted form, word for word.** Its hash is
  pinned in `tests/test_consent.py`. Change the wording only to match an approved form, and re-pin
  the hash when you do. `consent.APPROVED` stays False until HSRRC approves; while False, the screen
  shows a "pending approval" banner.
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
- Not optimizing for performance. ~1,700 rows in memory, single user at a time.
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
- **Blocked on IRB.** No participant runs until HSRRC approves. As of 2026-09-21 the app shows the
  submitted consent form with a "pending approval" banner (`consent.APPROVED = False`).
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
- **Still to do before the pilot:** run `scripts/init_db.py` then `scripts/verify_deployment.py`
  against **Neon**; fix the IRB wording mismatches listed in `study-design.md` §10; set
  `consent.APPROVED = True` only once HSRRC approves, and re-pin the text hash if the wording
  changed.
- Next after IRB: pilot, and check T6's form equivalence and A-T5's plateau (`study-design.md` §4).

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
  credit is a pre-registered secondary. `study-design.md` §4.
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

## Open questions

- Does HSRRC accept a drawn electronic signature? 45 CFR 46.117 allows electronic documentation;
  confirm with hsrrc@oxy.edu. The paper-copy box is the fallback either way.

## Reports & external material

<!-- e.g. - [Lit review draft](docs/lit-review.md) — 12 sources, interaction & cognitive load -->

- `irb/COMP 490 APPROVAL REQUEST FORM FOR STUDIES INVOLVING HUMAN SUBJECTS.pdf` — the IRB
  approval request form. **Gitignored; local only, never commit.** It **outranks
  `docs/study-design.md`** (Eduardo, 2026-09-21): where they disagree, the form wins and the doc is
  changed to match — or, if following the form would break the method, flag it so the form is
  amended before submission rather than silently diverging. Read it before any decision on consent,
  recruitment, data handling, tasks, or measures; what it requires is written into
  `docs/study-design.md`, not into the form's folder. Extract text with `pdftotext` (poppler for the
  Read tool is not installed).
- `irb/COMP 490 Consent Form.pdf` — the informed consent form, pages 1–2, the text participants
  sign. Also gitignored. `src/consent.py` transcribes it word for word, and the hash pinned in
  `tests/test_consent.py` guards that transcription.
