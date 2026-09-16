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

Append `?interactive=1` or `?interactive=0` to the URL to review either condition.

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

Built and tested: data layer, event logger (schema v2, Postgres or JSONL), chart rendering with
verified-contrast palette, session flow state machine, Vercel entry point.

Not yet built: the study flow UI (consent, participant ID, task prompts, answer capture). It is
blocked on `docs/study-design.md` — the task list, answer formats and scoring rubric are protocol
decisions, and the app currently shows a clearly labelled preview chart in their place.
