"""Replay spooled study events into Postgres.

When the database refuses an event, `logging.ResilientSink` spools it twice: into the participant's
browser session storage, which is replayed automatically on their next click, and into a JSONL file
under `config.spool_dir()`. This script recovers the file copy.

**Know what that copy is worth before relying on it.** On Vercel the spool directory is /tmp,
which is per-instance, lost on a cold start or redeploy, and cannot be read back out of a running
function. There, this script has nothing to read, and the browser copy is the only one that counts.
The file copy is genuinely recoverable on a local or self-hosted run.

Dry run by default. Replay is idempotent -- every event carries its own `event_uid` and conflicts
are ignored -- so running it twice, or against events that did land before a lost response, does no
harm. Recovered files are renamed to `*.recovered.jsonl`, never deleted: this is study data.

Usage:
    uv run python scripts/recover_spool.py                     # report what is spooled
    uv run python scripts/recover_spool.py --apply             # replay it (DATABASE_URL required)
    uv run python scripts/recover_spool.py --spool-dir DIR --apply
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, db  # noqa: E402
from src import logging as study_logging  # noqa: E402


def load(spool_dir: Path) -> list[dict[str, Any]]:
    """Spooled records, oldest first, each event once."""
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for envelope in study_logging.read_spool(spool_dir):
        record = envelope.get("record") or {}
        uid = record.get("event_uid")
        if not uid:
            # Nothing written by this schema lacks a uid, and without one replay is not idempotent.
            raise ValueError(f"spooled record has no event_uid: {record.get('event')!r}")
        if uid in seen:
            continue
        seen.add(uid)
        records.append(record)
    return records


def recover(records: list[dict[str, Any]], *, apply: bool) -> tuple[int, int]:
    """Replay `records` in order. Returns (inserted, already present). Nothing is written unless
    `apply` is true."""
    if not apply:
        return 0, 0
    inserted = present = 0
    for record in records:
        if db.insert_event(record, ignore_duplicates=True):
            inserted += 1
        else:
            present += 1
    return inserted, present


def archive(spool_dir: Path) -> list[Path]:
    """Rename replayed spool files so they are not replayed again. Never deletes."""
    renamed = []
    for path in sorted(spool_dir.glob("*.spool.jsonl")):
        target = path.with_name(path.name.replace(".spool.jsonl", ".recovered.jsonl"))
        path.rename(target)
        renamed.append(target)
    return renamed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay spooled study events into Postgres.")
    parser.add_argument("--spool-dir", type=Path, help="default: config.spool_dir()")
    parser.add_argument("--apply", action="store_true", help="write to the database")
    args = parser.parse_args(argv)

    spool_dir = args.spool_dir or config.spool_dir()
    if not spool_dir.is_dir():
        print(f"No spool directory at {spool_dir}. Nothing to recover.")
        return 0

    try:
        records = load(spool_dir)
    except ValueError as exc:
        print(f"Refusing to replay: {exc}", file=sys.stderr)
        return 1
    if not records:
        print(f"No spooled events under {spool_dir}.")
        return 0

    versions = {record.get("schema_version") for record in records}
    if versions != {study_logging.SCHEMA_VERSION}:
        print(
            f"Refusing to replay: spool holds schema versions {sorted(versions, key=str)}, "
            f"this code writes v{study_logging.SCHEMA_VERSION}.",
            file=sys.stderr,
        )
        return 1

    participants = Counter(record.get("participant_id") for record in records)
    events = Counter(record.get("event") for record in records)
    print(f"{len(records)} spooled events under {spool_dir}")
    print(f"  participants: {dict(participants)}")
    print(f"  events: {dict(events)}")

    if not args.apply:
        print("Dry run. Re-run with --apply to replay into the database.")
        return 0
    if not db.configured():
        print("--apply needs DATABASE_URL.", file=sys.stderr)
        return 1

    try:
        inserted, present = recover(records, apply=True)
    except db.DatabaseError as exc:
        # Safe to re-run: whatever landed is skipped next time by its event_uid.
        print(f"Replay stopped: {exc}. Nothing archived; re-run when reachable.", file=sys.stderr)
        return 1

    renamed = archive(spool_dir)
    print(f"Inserted {inserted}; {present} were already in the database.")
    print(f"Archived {len(renamed)} spool file(s) as *.recovered.jsonl.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
