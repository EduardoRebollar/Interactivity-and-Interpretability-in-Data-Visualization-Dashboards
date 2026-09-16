"""Open the local data viewer: health checks, participants and answers, raw events, the §7 report.

Reads from the same place `scripts/score_study.py` does (`analysis/sources.py`): a CSV export when
`--events` is given, Postgres when `DATABASE_URL` is set, local JSONL sessions otherwise. Read-only.

Serves on 127.0.0.1 only. The page shows participant data, and correctness from the answer key, so
it must never be reachable from another machine -- and it is never deployed.

Usage:
    uv run python scripts/view_data.py                              # local JSONL sessions
    uv run --env-file .env.local python scripts/view_data.py        # Neon
    uv run python scripts/view_data.py --events data/study_logs/events.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import sources, viewer_app  # noqa: E402
from src import db  # noqa: E402

HOST = "127.0.0.1"
DEFAULT_PORT = 8051  # the study app itself uses 8050


def make_loader(events_csv: Path | None) -> viewer_app.Loader:
    def loader():
        records, source = sources.load_records(events_csv)
        return records, sources.load_participants(events_csv), source

    return loader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open the local study-data viewer.")
    parser.add_argument("--events", type=Path, help="a CSV from scripts/export_logs.py")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    if args.events is not None:
        source = str(args.events)
    elif db.configured():
        source = "the database (DATABASE_URL)"
    else:
        source = "local JSONL sessions"
    print(f"Reading from {source}. Open http://{HOST}:{args.port}")

    app = viewer_app.create_app(make_loader(args.events))
    app.run(host=HOST, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
