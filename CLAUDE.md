# CLAUDE.md

Context and constraints for this project. Read this before proposing changes or writing code.

## Project

Senior comprehensive project (Occidental College, CS). Empirically compares static vs. interactive
data visualization dashboards for **interpretability** of time-series data, using WHO/UNICEF
childhood vaccination coverage data (1980–2024). Both a Plotly Dash implementation (this repo) and a
Tableau Public implementation exist; findings are cross-checked across platforms to test whether
interactivity effects are platform-dependent.

The study measures whether interactivity improves interpretation accuracy and reasoning depth, or
primarily reduces perceived cognitive load. Participants (target n ≥ 25) complete the same tasks on
both a static and an interactive version in a within-subjects design.

## Hard constraints

These are methodological requirements, not preferences. Do not relax them without asking.

### Visual design is held constant

- Chart types, color palette, axis scales, fonts, layout, and spacing must be identical between the
  static and interactive versions.
- The Dash build must mirror the Tableau build on all of the above.
- If you propose a visual change for one version, apply it to both, and flag that the Tableau version
  also needs updating.
- Any deviation breaks the core methodological claim that observed differences are attributable to
  interactivity, not aesthetics.

### Static vs. interactive is a single toggle

- The two conditions differ only via an `INTERACTIVE: bool` flag in `src/config.py`.
- Interactive-only features: filtering, sorting, line isolation, year-over-year directional change
  indicators.
- Do not introduce any other divergence between the two conditions.

### Scope is locked

- **Vaccines (4):** DTP3, MCV1, Polio3, HepB3.
- **Entities (~10):** US, UK, Brazil, India, Nigeria, Ethiopia, Indonesia, Ukraine, plus 1–2 more,
  plus "World" & continents as aggregate reference.
- **Years:** 2000–2024.
- Do not expand scope, add vaccines, or add countries without asking.

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
```

Planned, not yet written:

```
docs/
  study-design.md       # RQs, conditions, tasks, rubric
  visual-spec.md        # locked visual decisions (colors, chart types, layout)
src/
  config.py             # INTERACTIVE flag, palette, country/vaccine lists
  data.py               # load + clean
  layout.py             # shared layout components
  callbacks.py          # Dash callbacks (interactive version only)
  logging.py            # event/timing logger
  app.py                # Dash entry point
scripts/
  download_data.py      # fetches from OWID
tests/
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
- Not trying to be prettier or more featureful than the Tableau version — matching it is the point.
- Not optimizing for performance. ~1,000 rows in memory, single user at a time.
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
