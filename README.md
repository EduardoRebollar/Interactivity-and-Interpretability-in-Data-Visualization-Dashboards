# Interactivity and Interpretability in Data Visualization Dashboards

This project investigates whether interactive features improve users' ability to interpret
time-series data compared with static visualizations. The aim is to produce findings about
interaction and interpretability that are more credible, more generalizable, and more relevant to
the kinds of decisions dashboards are increasingly used to support.

Senior comprehensive project, Occidental College, CS. The study instrument is a Plotly Dash app
comparing a static and an interactive dashboard of WHO/UNICEF childhood vaccination coverage data,
in a within-subjects design. See [CLAUDE.md](CLAUDE.md) for the project constraints and
[docs/visual-spec.md](docs/visual-spec.md) for the locked visual decisions.

## Local setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python scripts/download_data.py      # fetch from Our World in Data
uv run python -m src.data                   # clean and cache -> 1700 rows
uv run python scripts/export_deploy_data.py # write data/deploy/coverage.csv
uv run python -m src.app                    # http://127.0.0.1:8050
```

One URL serves both conditions. Which one a participant gets is assigned per session from the 2×2
counterbalancing, not chosen from the URL — so to review a particular condition, start a session with
a participant ID that draws it (assignment is deterministic without a database, so an ID always lands
in the same cell).

## Checks

```bash
uv run pytest                               # full suite
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_contrast.py     # WCAG ratios for the palette
uv run python scripts/check_bundle.py       # app runs on the deployment subset alone
```

`check_bundle.py` builds a throwaway virtualenv from `requirements.txt` only and serves the app
through it, proving the deployment works with pandas, numpy and pyarrow uninstalled. Those three are
146 MB of the 268 MB development environment; excluding them puts the bundle at ~109 MB.

## Deployment

Hosted on Vercel, with participant data in Neon Postgres. The app's filesystem on Vercel is
ephemeral, so event logs **must** go to the database — a file sink there silently loses the study
data.

```bash
vercel login
vercel link

# Provision Neon. This injects DATABASE_URL into the Vercel project automatically.
vercel integration add neon

# Bring the connection string down locally (gitignored).
vercel env pull .env.local

# Create the tables, then prove the whole path works before any participant uses it.
uv run python scripts/init_db.py
uv run python scripts/verify_deployment.py

vercel deploy            # preview URL
vercel deploy --prod     # once the preview checks out
```

`verify_deployment.py` writes a complete synthetic session, reads it back, checks every field
survived including nested JSONB answers and null browser timings, then deletes exactly what it
wrote. Run it against the real instance before collecting data — `src/db.py`'s SQL is otherwise
unexercised.

Use Neon's **pooled** connection string. Serverless functions churn connections; the direct endpoint
runs out.

### Getting the data back out

```bash
uv run python scripts/export_logs.py                 # everything, to CSV
uv run python scripts/export_logs.py --participant P07
```

Reads from Postgres when `DATABASE_URL` is set and from local JSONL sessions otherwise.

## Secrets

This repo is public. `DATABASE_URL` belongs in Vercel's environment variables and in `.env.local`
only; `.env` and `.env.*` are gitignored. See [.env.example](.env.example).

## Status

**The instrument is complete and runs end to end.** A participant can take the whole session from one
URL: consent, participant ID, instructions, practice, six tasks, a mental-effort rating, a break, then
the second condition in the other version and the other form.

Built and tested: data layer; event logger (schema v3, Postgres or JSONL); chart rendering on a
verified-contrast palette; the session flow state machine; the study screens; the interactive
controls (filter, sort, line isolation, and year-over-year change in the hover tooltip) with their
interaction logging; the Vercel entry point.

**Not yet run with participants, and it must not be.** The consent wording in `src/app.py` is a
draft, marked as such on screen, and `docs/study-design.md` §9 carries unfilled contact and protocol
placeholders. Nothing runs until IRB approves the final text.

Also open before piloting: T6's form equivalence, flagged in `docs/study-design.md` §4 — the UK's
19-year HepB3 gap has no equal in the dataset, and form B substitutes three shorter ones.
