"""Export collected study data to CSV for analysis.

Reads from Postgres when `DATABASE_URL` is set, otherwise from the local JSONL sessions. The export
path exists BEFORE collection starts deliberately: discovering that the data cannot be got back out
is a problem to have now, not after 25 participants.

Usage:
    uv run python scripts/export_logs.py [--participant P07] [--out data/study_logs/events.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db  # noqa: E402
from src import logging as study_logging  # noqa: E402

COLUMNS = [
    "schema_version",
    "session_id",
    "participant_id",
    "condition",
    "condition_order",
    "form",
    "task_id",
    "event",
    "server_ts",
    "client_elapsed_ms",
    "task_elapsed_ms",
    "server_elapsed_ms",
    "payload",
]


def _from_database(participant_id: str | None) -> list[dict[str, Any]]:
    return db.fetch_events(participant_id)


def _from_files(participant_id: str | None) -> list[dict[str, Any]]:
    records = study_logging.read_all()
    if participant_id is not None:
        records = [r for r in records if r.get("participant_id") == participant_id]
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant", help="restrict to one participant id")
    parser.add_argument("--out", type=Path, help="output CSV path")
    args = parser.parse_args()

    source = "database" if db.configured() else "local JSONL files"
    try:
        records = (
            _from_database(args.participant) if db.configured() else _from_files(args.participant)
        )
    except db.DatabaseError as exc:
        print(f"Failed reading from database: {exc}", file=sys.stderr)
        return 1

    if not records:
        print(f"No events found in {source}.", file=sys.stderr)
        return 1

    out = args.out or config.STUDY_LOGS_DIR / "events.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            # Keep the payload as JSON text so nested answers survive the flattening.
            row["payload"] = json.dumps(row.get("payload") or {}, default=str)
            writer.writerow(row)

    participants = {r.get("participant_id") for r in records}
    conditions = {r.get("condition") for r in records}
    answers = sum(1 for r in records if r.get("event") == "answer_submit")

    print(f"Read {len(records)} events from {source}")
    print(f"  participants: {len(participants)}  conditions: {sorted(c for c in conditions if c)}")
    print(f"  answers recorded: {answers}")
    print(f"Wrote {out}")

    versions = {r.get("schema_version") for r in records}
    if len(versions) > 1:
        print(
            f"WARNING: mixed schema versions {sorted(versions)} — do not pool these.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
