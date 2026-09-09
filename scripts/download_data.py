"""Fetch the raw WHO/UNICEF vaccination coverage export from Our World in Data.

Writes the unmodified CSV to `data/raw/`. Cleaning happens in `src/data.py`; nothing here filters,
reshapes, or fills anything, so the raw file stays a faithful copy of the source.

Usage:
    uv run python scripts/download_data.py [--force]
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request

# Allow running as a plain script (`python scripts/download_data.py`) without installing the
# project, since it is configured as an application rather than a package.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402

# OWID returns 403 to the default urllib agent.
USER_AGENT = "vaccine-dashboard/0.1 (Occidental College senior comprehensive; research use)"
TIMEOUT_SECONDS = 120


def download(force: bool = False) -> int:
    """Download the OWID CSV to `data/raw/`. Returns a process exit code."""
    if config.RAW_CSV.exists() and not force:
        size = config.RAW_CSV.stat().st_size
        print(f"Already present: {config.RAW_CSV} ({size:,} bytes)")
        print("Re-download with --force")
        return 0

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {config.OWID_CSV_URL}")

    request = urllib.request.Request(config.OWID_CSV_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    text = payload.decode("utf-8")
    header = text.split("\n", 1)[0]
    missing = [c for c in config.VACCINES.values() if c not in header]
    if missing:
        # The upstream schema changed; fail loudly rather than caching a file that cleaning
        # would silently reduce to empty columns.
        print(f"Unexpected OWID schema, missing columns: {missing}", file=sys.stderr)
        print(f"Header was: {header}", file=sys.stderr)
        return 1

    # Write only after validating, so a bad response never replaces a good cached file.
    config.RAW_CSV.write_bytes(payload)
    rows = text.count("\n")
    print(f"Wrote {config.RAW_CSV} ({len(payload):,} bytes, ~{rows:,} rows)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    args = parser.parse_args()
    return download(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
