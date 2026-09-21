"""Withdraw one participant's study data, at their request.

IRB form item 13 promises every participant the right to withdraw their data up to two weeks after
their session, without giving a reason. The final screen tells them to email the researcher with
their participant ID; this script is what the researcher then runs. See `docs/study-design.md` §9.

What it removes, with `--apply`:

- every study event for the ID in Postgres (when `DATABASE_URL` is set), and the participant is
  marked `withdrawn_at` rather than deleted -- so the counterbalancing sequence stays explainable
  and the app refuses the ID from now on;
- every local JSONL session file for the ID under `data/study_logs/`;
- every spool file for the ID, so `scripts/recover_spool.py` can never bring the data back.

What it does NOT touch, and says so: the signed consent record (proof consent was given, kept under
IRB form item 15, and not linked to the ID anyway), and copies already made -- derived frames, CSV
exports, coding sheets, the Oxy Drive. Those must be regenerated or deleted by hand.

Dry run by default. Past the two-week window it refuses unless `--late` is given.

Usage:
    uv run python scripts/withdraw_participant.py P07            # show what would be removed
    uv run python scripts/withdraw_participant.py P07 --apply    # remove it
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db  # noqa: E402

WINDOW = timedelta(days=14)


def _participant_of(path: Path) -> set[str]:
    """Participant IDs recorded in a JSONL file: plain records or spool envelopes."""
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        record = record.get("record", record) if isinstance(record, dict) else {}
        if isinstance(record, dict) and record.get("participant_id"):
            found.add(str(record["participant_id"]))
    return found


def local_files(participant_id: str, log_dir: Path, spool_dir: Path) -> list[Path]:
    """Every local file holding this participant's events. Read, not guessed from file names."""
    candidates = [*sorted(log_dir.glob("*.jsonl"))]
    if spool_dir.exists():
        candidates += sorted(spool_dir.glob("*.jsonl"))
    files = []
    for path in candidates:
        ids = _participant_of(path)
        if participant_id in ids:
            if ids != {participant_id}:
                # Session and spool files are per participant. A mixed one is not something this
                # script produced, and deleting it would take someone else's data with it.
                raise SystemExit(f"{path} holds other participants too; resolve it by hand")
            files.append(path)
    return files


def _first_seen(
    participant: dict[str, Any] | None, events: list[dict[str, Any]]
) -> datetime | None:
    """When the session happened: the registration time, else the earliest event."""
    stamps = []
    if participant and participant.get("created_at"):
        stamps.append(participant["created_at"])
    for event in events:
        value = event.get("server_ts")
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                continue
        if isinstance(value, datetime):
            stamps.append(value)
    stamps = [s if s.tzinfo else s.replace(tzinfo=UTC) for s in stamps]
    return min(stamps) if stamps else None


def _local_events(files: list[Path]) -> list[dict[str, Any]]:
    events = []
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                events.append(record.get("record", record))
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("participant_id")
    parser.add_argument("--apply", action="store_true", help="actually remove the data")
    parser.add_argument("--late", action="store_true", help="allow it past the two-week window")
    parser.add_argument("--log-dir", type=Path, default=config.STUDY_LOGS_DIR)
    parser.add_argument("--spool-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    participant_id = args.participant_id.strip()
    spool_dir = args.spool_dir or config.spool_dir()

    participant = None
    db_events: list[dict[str, Any]] = []
    if db.configured():
        participant = next(
            (p for p in db.fetch_participants() if p["participant_id"] == participant_id), None
        )
        db_events = db.fetch_events(participant_id)
    files = local_files(participant_id, args.log_dir, spool_dir)

    print(f"Participant {participant_id}")
    if db.configured():
        if participant is None:
            print("  database: not registered")
        else:
            state = (
                f"withdrawn {participant['withdrawn_at']}"
                if participant.get("withdrawn_at")
                else "active"
            )
            registered = participant["created_at"]
            print(f"  database: registered {registered} ({state}), {len(db_events)} events")
    else:
        print("  database: not configured (DATABASE_URL unset) -- local files only")
    for path in files:
        print(f"  local file: {path}")

    if participant is None and not db_events and not files:
        print("Nothing found for this ID. Check it against the participant lookup file.")
        return 1

    first = _first_seen(participant, db_events or _local_events(files))
    if first is not None:
        age = datetime.now(UTC) - first
        print(f"  session: {first:%Y-%m-%d %H:%M} UTC, {age.days} days ago")
        if age > WINDOW and not args.late:
            print(
                "Past the two-week withdrawal window (IRB form item 13). Re-run with --late to "
                "honour the request anyway."
            )
            return 1

    if not args.apply:
        print("\nDry run: nothing removed. Re-run with --apply to withdraw.")
        return 0

    if db.configured():
        removed = db.withdraw_participant(participant_id)
        print(f"  database: removed {removed or 0} events; ID marked withdrawn")
    for path in files:
        path.unlink()
        print(f"  deleted {path}")

    print(
        "\nDone. Still to do by hand, because this script cannot see them:\n"
        "  - re-run scripts/score_study.py so data/study_logs/derived/ no longer includes them;\n"
        "  - regenerate or prune coding sheets under data/study_logs/coding/;\n"
        "  - delete them from any CSV export and from the Oxy Drive copies;\n"
        "  - note the withdrawal (date, ID) in the participant lookup file.\n"
        "The signed consent record is kept: it is proof of consent, not study data."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
