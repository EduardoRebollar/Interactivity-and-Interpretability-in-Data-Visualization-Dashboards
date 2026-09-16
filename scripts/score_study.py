"""Score the collected study data and apply the pre-registered exclusions.

Reads events from Postgres when `DATABASE_URL` is set, from local JSONL sessions otherwise, or from
a CSV written by `scripts/export_logs.py` with `--events`. Writes tidy frames under
`data/study_logs/derived/` -- participant data, and gitignored -- and prints the descriptive report
`docs/study-design.md` section 7 asks for.

Refuses to run if the derived answer key disagrees with section 4: scoring against a key that is
known to be wrong would produce a confident, wrong result.

Usage:
    uv run python scripts/score_study.py
    uv run python scripts/score_study.py --events data/study_logs/events.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import exclusions, keys, reshape  # noqa: E402
from analysis import report as study_report  # noqa: E402
from src import config, db  # noqa: E402
from src import logging as study_logging  # noqa: E402

DERIVED_DIR = config.STUDY_LOGS_DIR / "derived"


def load_records(events_csv: Path | None) -> tuple[list[dict], str]:
    if events_csv is not None:
        return reshape.read_export(events_csv), str(events_csv)
    if db.configured():
        return db.fetch_events(), "database"
    return study_logging.read_all(), f"JSONL under {config.STUDY_LOGS_DIR}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the study and apply exclusions.")
    parser.add_argument("--events", type=Path, help="a CSV from scripts/export_logs.py")
    parser.add_argument("--out", type=Path, default=DERIVED_DIR)
    args = parser.parse_args(argv)

    problems = keys.check()
    if problems:
        print("Refusing to score: the answer key does not check out.", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    try:
        records, source = load_records(args.events)
        events = reshape.events_frame(records)
        tasks = reshape.tidy_tasks(events)
        conditions = reshape.tidy_conditions(events, tasks)
    except (reshape.ReshapeError, db.DatabaseError) as exc:
        print(f"Cannot score: {exc}", file=sys.stderr)
        return 1

    scored, excluded = exclusions.apply(tasks, conditions)

    args.out.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.out / "tasks.csv", index=False)
    conditions.to_csv(args.out / "conditions.csv", index=False)

    print(f"Read {len(events)} events from {source}\n")
    print(study_report.render(scored, conditions, excluded))
    print(f"Wrote {args.out / 'tasks.csv'} and {args.out / 'conditions.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
