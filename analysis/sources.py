"""Where collected events are read from. Shared by `scripts/score_study.py` and the data viewer.

One place decides the source, so the scorer and the viewer can never be looking at different data:
a CSV from `scripts/export_logs.py` when one is given, Postgres when `DATABASE_URL` is set, and the
local JSONL sessions otherwise. Read-only throughout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from analysis import reshape
from src import config, db
from src import logging as study_logging


def load_records(
    events_csv: Path | None = None, log_dir: Path | None = None
) -> tuple[list[dict[str, Any]], str]:
    """Every event, oldest first, and a label naming where they came from."""
    if events_csv is not None:
        return reshape.read_export(events_csv), str(events_csv)
    if db.configured():
        return db.fetch_events(), "database"
    directory = log_dir or config.STUDY_LOGS_DIR
    return study_logging.read_all(directory), f"JSONL under {directory}"


def load_participants(events_csv: Path | None = None) -> list[dict[str, Any]] | None:
    """Registered participants, or None where there is no registration table to read.

    Only the database has one. A CSV export and the local JSONL sessions carry events alone.
    """
    if events_csv is not None or not db.configured():
        return None
    return db.fetch_participants()
