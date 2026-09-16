"""Export the validated parquet to the CSV the deployed app reads.

The deployment cannot import pandas or pyarrow — together with numpy they are 145 MB of the local
environment and would blow the Vercel Python bundle limit. So cleaning and validation stay here,
offline, and production reads a plain CSV with the stdlib.

`data/deploy/coverage.csv` is committed (a named exemption in CLAUDE.md) because a Vercel deployment
only sees what is in git. It is generated, never hand-edited: re-run this after refreshing the data.

Usage:
    uv run python scripts/export_deploy_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, data  # noqa: E402

DEPLOY_DIR = config.DATA_DIR / "deploy"
DEPLOY_CSV = DEPLOY_DIR / "coverage.csv"


def export() -> int:
    """Write the cleaned frame to the deploy CSV. Returns a process exit code."""
    frame = data.load(refresh=True)

    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    # Empty string for NaN, so a gap round-trips as a gap rather than as the text "nan".
    frame.to_csv(DEPLOY_CSV, index=False, na_rep="", lineterminator="\n")

    size_kb = DEPLOY_CSV.stat().st_size / 1024
    observed = int(frame["coverage_pct"].notna().sum())
    print(f"Wrote {DEPLOY_CSV} ({size_kb:.1f} KB)")
    print(f"  {len(frame)} rows, {observed} observed, {len(frame) - observed} missing")

    # Fail loudly rather than shipping a file the runtime loader would read differently.
    from src import runtime_data

    runtime_data.clear_cache()
    rows = runtime_data.load_rows()
    if len(rows) != len(frame):
        print(f"Round-trip mismatch: {len(rows)} rows read back", file=sys.stderr)
        return 1
    read_observed = sum(1 for r in rows if r.coverage_pct is not None)
    if read_observed != observed:
        print(
            f"Round-trip mismatch: {read_observed} observed read back, expected {observed}",
            file=sys.stderr,
        )
        return 1
    print("  round-trip verified against the runtime loader")
    return 0


if __name__ == "__main__":
    raise SystemExit(export())
