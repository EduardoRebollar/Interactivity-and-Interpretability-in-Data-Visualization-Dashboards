"""Score the collected study data and apply the pre-registered exclusions.

Reads events from Postgres when `DATABASE_URL` is set, from local JSONL sessions otherwise, or from
a CSV written by `scripts/export_logs.py` with `--events`. Writes tidy frames under
`data/study_logs/derived/` -- tasks, conditions (with the survey) and participants (About you);
participant data, and gitignored -- and prints the descriptive report
`docs/study-design.md` section 7 asks for.

Refuses to run if the derived answer key disagrees with section 4: scoring against a key that is
known to be wrong would produce a confident, wrong result.

T1 is written and scored by rubric. Its verdicts come from `scripts/code_justifications.py rubric`,
which reads the tasks.csv this writes: run this, code T1, then run this again. Until then T1 is
uncoded, the RQ1 proportions leave those participants out, and the report says how many.

Usage:
    uv run python scripts/score_study.py
    uv run python scripts/score_study.py --events data/study_logs/events.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import coding, exclusions, keys, reshape, sources  # noqa: E402
from analysis import report as study_report  # noqa: E402
from src import config, db  # noqa: E402

DERIVED_DIR = config.STUDY_LOGS_DIR / "derived"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the study and apply exclusions.")
    parser.add_argument("--events", type=Path, help="a CSV from scripts/export_logs.py")
    parser.add_argument("--out", type=Path, default=DERIVED_DIR)
    parser.add_argument(
        "--rubric", type=Path, default=coding.VERDICTS_PATH, help="T1's settled rubric verdicts"
    )
    args = parser.parse_args(argv)

    problems = keys.check()
    if problems:
        print("Refusing to score: the answer key does not check out.", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    try:
        records, source = sources.load_records(args.events)
        events = reshape.events_frame(records)
        rubric = coding.read_verdicts(args.rubric)
        tasks = reshape.tidy_tasks(events, rubric=rubric)
        conditions = reshape.tidy_conditions(events, tasks)
        participants = reshape.tidy_participants(events)
    except (reshape.ReshapeError, db.DatabaseError, coding.CodingError) as exc:
        print(f"Cannot score: {exc}", file=sys.stderr)
        return 1

    scored, excluded = exclusions.apply(tasks, conditions)

    args.out.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.out / "tasks.csv", index=False)
    conditions.to_csv(args.out / "conditions.csv", index=False)
    participants.to_csv(args.out / "participants.csv", index=False)

    print(f"Read {len(events)} events from {source}\n")
    print(study_report.render(scored, conditions, excluded, participants))
    waiting = int(scored.loc[scored["kind"] == "describe", "correct"].isna().sum())
    if waiting:
        print(
            f"{waiting} T1 answers are not coded yet: run scripts/code_justifications.py "
            "rubric-sheets, then rubric, then this again.\n"
        )
    written = ", ".join(str(args.out / name) for name in ("tasks.csv", "conditions.csv"))
    print(f"Wrote {written} and {args.out / 'participants.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
