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

- The two conditions differ only via an `INTERACTIVE: bool` flag in `src/config.py`.
- Interactive-only features: filtering, sorting, line isolation, year-over-year directional change
  indicators.
- **The static condition is fully inert:** `staticPlot: True`, so no hover, no zoom, no pan, no
  modebar. Plotly is interactive by default, so a plain `dcc.Graph` would leave the static condition
  hoverable and the manipulation would be invalid. This is deliberate, not an oversight.
- Do not introduce any other divergence between the two conditions.

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

### Study instrumentation

- The app logs interaction events (filter changes, legend/isolation clicks, sort actions) and task
  timings to a local file (JSON or CSV under `data/study_logs/`).
- This logging IS the study data. Do not remove, disable, or "clean up as unused" any logging code.
- Log schema changes are breaking — flag them explicitly.

### Accessibility baseline

- Color palette must meet WCAG 2.1 AA contrast ratios (4.5:1 for text, 3:1 for graphical elements).
- All interactive controls keyboard-navigable.
- Do not propose color choices without checking contrast.
- Full screen-reader accessibility is explicitly out of scope; do not spend time on it, but do not
  add anything that makes it worse.

## Tech stack

- Python 3.11+
- `uv` for dependency and environment management
- `dash`, `plotly`, `pandas`, `pyarrow`
- `ruff` for linting/formatting, `pytest` for tests
- Do not add dependencies without asking first.

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

Present:

```
CLAUDE.md
README.md
LICENSE
pyproject.toml          # deps + ruff/pytest config; [tool.uv] package = false
uv.lock                 # committed — this is the reproducibility guarantee
.gitignore
data/
  raw/                  # downloaded CSVs (gitignored, .gitkeep only)
  processed/            # cleaned parquet (gitignored, .gitkeep only)
  study_logs/           # participant interaction logs (gitignored, .gitkeep only)
docs/
  visual-spec.md        # locked visual decisions (colors, chart types, layout)
src/
  config.py             # INTERACTIVE flag, palette, country/vaccine lists
  data.py               # load + clean
  logging.py            # event/timing logger
scripts/
  download_data.py      # fetches from Our World in Data
  check_contrast.py     # WCAG contrast report for the palette
tests/
  test_data.py
  test_logging.py
  test_palette.py       # enforces the contrast floors
```

Planned, not yet written:

```
docs/
  study-design.md       # RQs, conditions, tasks, rubric
src/
  layout.py             # shared layout components
  callbacks.py          # Dash callbacks (interactive version only)
  app.py                # Dash entry point
```

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

### Duplicate clone — be careful

This repo is cloned twice on this machine, both pointing at the same GitHub remote:

- `…/Interactivity-and-Interpretability-in-Data-Visualization-Dashboards/` (outer, stale — only the
  initial commit)
- `…/Interactivity-and-Interpretability-in-Data-Visualization-Dashboards/Interactivity-and-Interpretability-in-Data-Visualization-Dashboards/`
  (inner, **this is the working copy**)

Confirm you are in the inner one before committing.

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
and for the visual decisions. If those docs don't answer the question, ask.

## Anti-goals (things this project is not)

- Not a general-purpose vaccination-tracking tool. It's a study instrument.
- Not trying to be impressive. The two conditions looking identical is the point; a feature that
  makes only one of them nicer is a defect, not an improvement.
- Not optimizing for performance. ~1,700 rows in memory, single user at a time.
- Not building a public-facing site. Runs locally during study sessions.

---

# Eduardo's notes

Everything below this line is yours. Add whatever helps — open questions, decisions made, advisor
feedback, deadlines, findings.

Keep entries short. This file is loaded into context at the start of every session, so full reports
belong in `docs/` or `reports/` as their own files, with a one-line pointer here. That keeps the
context cheap and the reports as long as they need to be.

## Status / current focus

-

## Decisions made

- 2026-09-08 — Python floor stays at 3.11; `uv.lock` committed for reproducibility.

## Open questions

- `docs/study-design.md` and `docs/visual-spec.md` are named as the source of truth but don't exist
  yet. They gate most visual and protocol work.

## Reports & external material

<!-- e.g. - [Lit review draft](docs/lit-review.md) — 12 sources, interaction & cognitive load -->

-
