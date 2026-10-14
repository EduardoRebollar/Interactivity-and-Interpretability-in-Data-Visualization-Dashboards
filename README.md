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
uv run python -m src.data                   # clean and cache -> 10,880 rows
uv run python scripts/export_deploy_data.py # write data/deploy/coverage.csv
uv run python -m src.app                    # http://127.0.0.1:8050
```

The local run also serves a preview at http://127.0.0.1:8050/preview: any item of either form, in
either condition, on the participant's own task screen. It logs nothing and Submit saves nothing.
Only a local run has it — the deployed app does not — so a change can be tried without committing.
Set `DASH_DEBUG=1` to have the page reload as you edit.

One URL serves both conditions. Which one a participant gets is assigned per session from the 2×2
counterbalancing, not chosen from the URL — so to review a particular condition, start a session with
a participant ID that draws it (assignment is deterministic without a database, so an ID always lands
in the same cell).

## Checks

```bash
uv run pytest                               # full suite
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_contrast.py     # WCAG ratios and colour-blind separation
uv run python scripts/check_bundle.py       # app runs on the deployment subset alone
uv run python scripts/derive_keys.py        # answer key, derived from the data, checked vs the docs
uv run python scripts/export_questionnaire.py  # every screen -> irb/questionnaire.pdf (IRB item 18)
```

`derive_keys.py` also enforces the item acceptance rule in `docs/study-design.md` §4. An item is
refused if its answer turns on:
- a difference under 5 points on an axis, or under 10 on a colour scale;
- a year read one off landing on another option;
- a scatter dot hidden behind another;
- a crossing that happens more than once, sits near the edge of its answer band, or has a third
  line running through it;
- a missing value.
`export_questionnaire.py` renders the app's own screen functions, so the PDF says exactly what
participants see. It needs Chrome or Edge to print; `--html-only` skips that.

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
It passed against a local Postgres 16 on 2026-09-16, and again for schema v6 on 2026-09-21. On
2026-09-22 it passed against the production Neon database, after `init_db.py` had upgraded that
database from v5 in place. The test suite executes no SQL at all, so re-run the script after any
schema change.

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

uv run python scripts/code_justifications.py rubric-sheets  # T1's descriptions, for both coders
uv run python scripts/code_justifications.py rubric         # kappa per part; verdicts once settled
```

Run the rubric steps before `score_study.py`'s final run: a participant's T1–T6 accuracy is not
computed while their T1 is uncoded.

The answer key is in `analysis/keys.py`, **derived from the data** by each item's stated rule and
checked against §4; `score_study.py` refuses to run if they disagree. `analysis/` is excluded from
the Vercel bundle and never imported by the app, so the key does not ship. The coding sheets carry
only an opaque id and the text, shuffled with a recorded seed; `key.csv`, which unblinds them, is for
the analyst and must not go to a coder.

## Secrets

This repo is public. `DATABASE_URL` belongs in Vercel's environment variables and in `.env.local`
only; `.env` and `.env.*` are gitignored. See [.env.example](.env.example).

## Running the study

Sessions are run in person, with the researcher script in `docs/study-design.md` §8. Each
participant is assigned their counterbalancing cell from the database sequence. The first study
participant is seq 14 (interactive first, form A); seq 13 and below were tests and the pilot.

```bash
# While collecting: cell balance, unfinished sessions, outages, the manipulation check (Health tab)
uv run --env-file .env.local python scripts/view_data.py

# After each session: signed consent forms -> encrypted 7-Zip on the Drive, then out of Neon
uv run --env-file .env.local python scripts/archive_consents.py

# A withdrawal request, within two weeks: dry run first, then --apply
uv run --env-file .env.local python scripts/withdraw_participant.py P07
uv run --env-file .env.local python scripts/withdraw_participant.py P07 --apply
```

Without `--env-file .env.local`, `withdraw_participant.py` touches local files only and leaves the
participant's data in Neon.

A push to `main` redeploys production. From here, a change to an item, chart, control or logged
field lands mid-study and splits the data by schema version, which analysis refuses to pool
(`docs/study-design.md` §10).

## Status

**Data collection is starting (2026-10-13; target n ≥ 25).** The instrument is finished.
Occidental's HSRRC approved the study on 2026-10-12. It said the changes made after the pilot need
no amendment, and approved drawing the line charts from 1985 on 2026-10-13. The consent form in
`src/consent.py` is the approved form, word for word. Production serves commit 29554dc (log
schema v21).

A participant takes the whole session from one URL: a signed consent form (or a decline),
participant ID, instructions, practice, six tasks, a survey, a break, then the second condition on
the other form, a second survey, and a few questions about themselves. Any question may be skipped,
after a confirmation.

One pilot session was run on 2026-10-12. Its data is kept out of the study, and the changes it led
to are listed in `docs/study-design.md` §10. There is no second pilot, so the pilot checks in §10
are read from the study's own data after collection.

Built and tested (1470 tests, and full sessions in all four counterbalancing cells driven through
the UI in headless Chrome):
- the data layer, 1985–2024;
- the event logger (Postgres or JSONL), with retry and spooling through a database outage;
- five chart types (line, bar, scatter, heatmap, map) carrying twelve items over two parallel
  forms, on a palette checked for contrast and for colour-blind separation;
- the session flow state machine and the study screens;
- the interactive controls, with their interaction logging:
  - country chips and Reset view on every chart;
  - on line charts: a Years slider, Show all, focusing a line, and year-over-year change in the
    tooltip;
  - sorting the bar chart and the heatmap's rows;
  - on the scatter, heatmap and map, a click on a colour in the key highlights its band;
  - hover on every chart;
  - on T1 only, four further controls it does not need, named to participants nowhere
    (`docs/study-design.md` §4, §7);
- the signed consent record, kept apart from the study data and archived encrypted to the Drive,
  with a two-week withdrawal script;
- duplicate-submit protection, and flagged rather than wrong durations after a reload;
- the offline scoring pipeline: derived answer key, pre-registered exclusions, T1's rubric, blind
  RQ2 coding and Cohen's kappa.

Known limits:
- Session resume is not implemented; the participant-ID screen asks for one sitting in one tab
  (`docs/study-design.md` §8).
- Hover and focusing a line are mouse-only. Every other control works from the keyboard
  (`docs/visual-spec.md` §8).
