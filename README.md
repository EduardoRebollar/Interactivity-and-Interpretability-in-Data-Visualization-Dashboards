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
uv run python scripts/derive_keys.py        # answer key, derived from the data, checked vs the docs
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
survived including nested JSONB answers and null browser timings, confirms the database refuses a
second answer for the same task and ignores a replayed event, then deletes exactly what it wrote.
Run it against the real instance before collecting data — **no SQL in `src/db.py` has yet been
executed against a real Postgres**, and the test suite does not do it either.

`init_db.py` also checks that every column the logger writes exists on the table. `CREATE TABLE IF
NOT EXISTS` does nothing to a table created under an older schema, so a missed migration would
otherwise drop a column's worth of data silently.

Use Neon's **pooled** connection string. Serverless functions churn connections; the direct endpoint
runs out.

### When the database is unreachable

A participant's session does not stop. Event writes retry connection failures within an 8-second
budget, then spool: into the participant's browser session storage, replayed automatically on their
next click once the database answers, and into a JSONL file. After one failure the app skips the
database for 20 seconds, so an outage costs one wait, not one per click. A `sink_recovered` event
marks every session that went through this.

Measured against a genuinely unreachable Postgres: the first write of an outage took ~10 s (two 5 s
connect timeouts), later ones ~0 s. Once the 20-second pause lapses, the next interaction waits one
5 s connect timeout **inside the task's measured time**, in the interactive condition only. That is
why `docs/study-design.md` §7 reports degraded sessions and re-runs timing analyses without them.

Participant assignment cannot be spooled — inventing one would break the counterbalancing — so if
the database is down when someone enters their ID, they see "We could not start your session" and
can press Continue again.

The file copy of the spool is recoverable only where the filesystem persists:

```bash
uv run python scripts/recover_spool.py           # dry run: what is spooled
uv run python scripts/recover_spool.py --apply   # replay into Postgres, idempotent
```

On Vercel it lives in `/tmp`, which is per-instance and cannot be read back out of a running
function; there, the browser copy is the one that counts. Write-ups should say *the session
continues and the loss is recorded*, not that no data can be lost.

### Getting the data back out

```bash
uv run python scripts/export_logs.py                 # everything, to CSV
uv run python scripts/export_logs.py --participant P07
```

Reads from Postgres when `DATABASE_URL` is set and from local JSONL sessions otherwise.

### Viewing collected data

```bash
uv run python scripts/view_data.py                          # local JSONL sessions
uv run --env-file .env.local python scripts/view_data.py    # Neon
uv run python scripts/view_data.py --events data/study_logs/events.csv
```

Opens a local dashboard at http://127.0.0.1:8051. It has four tabs:

- **Health:** collection checks (manipulation check, consent, duplicate answers, unfinished
  sessions, outages, schema version, answer key) and the 2×2 cell balance.
- **Participants:** progress, Paas and accuracy per condition. Select a row to see each answer and
  the session's event timeline.
- **Events:** every raw event, with filtering.
- **Summary:** the §7 report, plus CSV downloads in the `export_logs.py` / `score_study.py`
  formats.

It is read-only and serves on localhost only. It never deploys, because it lives in `analysis/`
with the answer key. Justifications are hidden unless you tick the box, since reading them beside
their condition breaks the blind coding in §7. The downloads always include them. Data loads when
the page opens and again when you press Reload; the page doesn't poll, so it won't keep Neon
awake.

### Scoring

Offline, against the pre-registration in `docs/study-design.md` §7. Everything below writes under
`data/study_logs/`, which is gitignored: it is participant data, including free text.

```bash
uv run python scripts/score_study.py                        # accuracy, Paas, timing, exclusions
uv run python scripts/score_study.py --events data/study_logs/events.csv

uv run python scripts/code_justifications.py sheets         # blind sheets for two coders
uv run python scripts/code_justifications.py kappa          # after both are coded
uv run python scripts/code_justifications.py depth          # reasoning depth per answer
```

The answer key is in `analysis/keys.py`, **derived from the data** by each item's stated rule and
checked against §4; `score_study.py` refuses to run if they disagree. `analysis/` is excluded from
the Vercel bundle and never imported by the app, so the key does not ship. The coding sheets carry
only an opaque id and the text, shuffled with a recorded seed; `key.csv`, which unblinds them, is for
the analyst and must not go to a coder.

## Secrets

This repo is public. `DATABASE_URL` belongs in Vercel's environment variables and in `.env.local`
only; `.env` and `.env.*` are gitignored. See [.env.example](.env.example).

## Status

**The instrument is complete and runs end to end.** A participant can take the whole session from one
URL: a signed consent form (or a decline), participant ID, a few demographic questions, instructions,
practice, six tasks, a short survey, a break, then the second condition in the other version and the
other form. Any question may be skipped, after a confirmation.

Built and tested: data layer; event logger (schema v6, Postgres or JSONL) with retry and spooling
through a database outage; chart rendering on a verified-contrast palette; the session flow state
machine; the study screens; the interactive controls (filter, sort, line isolation, and
year-over-year change in the hover tooltip) with their interaction logging; the signed consent
record, kept apart from the study data, with export and a two-week withdrawal script;
duplicate-submit protection; flagged rather than wrong durations after a reload; the Vercel entry
point; and the offline scoring pipeline — derived answer key, pre-registered exclusions, blind RQ2
coding and Cohen's kappa.

**Not yet run with participants, and it must not be.** The consent form in `src/consent.py` is the
one submitted to Occidental's HSRRC and is marked "pending approval" on screen until it is approved.
`docs/study-design.md` §10 lists wording in the IRB paperwork still to fix before submission.

Also open before piloting:

- **Run `verify_deployment.py` against the real Neon database.** Nothing has exercised the SQL yet.
- T6's form equivalence, flagged in `docs/study-design.md` §4 — the UK's 19-year HepB3 gap has no
  equal in the dataset, and form B substitutes three shorter ones.
- A-T5 may not read as a crossing: China and Brazil sit at exactly 99.0 for three years. §4.
- Session resume is promised on the participant-ID screen but not implemented. §8.
- Hover and line isolation are mouse-only, so a keyboard-only participant in the interactive
  condition gets a chart that behaves like the static one.
