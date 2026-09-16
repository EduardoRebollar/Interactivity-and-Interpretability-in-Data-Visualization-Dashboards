"""Create the study tables in Neon Postgres. Safe to run repeatedly.

Usage:
    # DATABASE_URL must be set. Use Neon's POOLED connection string.
    uv run python scripts/init_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db  # noqa: E402


def main() -> int:
    if not db.configured():
        print(
            "DATABASE_URL is not set.\n"
            "Provision Neon through the Vercel Marketplace, then either export the pooled "
            "connection string locally or run `vercel env pull .env.local`.",
            file=sys.stderr,
        )
        return 1

    try:
        db.init_schema()
        count = db.participant_count()
        # Post-condition, not a formality: CREATE TABLE IF NOT EXISTS succeeds on a pre-v4 table
        # without adding new columns, and a column that is absent silently drops every write of it.
        missing = set(db.EVENT_COLUMNS) - db.column_names("study_events")
    except db.DatabaseError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    if missing:
        print(
            f"Schema is incomplete: study_events lacks {sorted(missing)}. "
            "The table predates the current schema and was not migrated.",
            file=sys.stderr,
        )
        return 1

    print("Schema ready.")
    print(f"Participants registered so far: {count}")
    if count:
        print("  (a non-zero count on a fresh database means you are pointed at a used one)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
