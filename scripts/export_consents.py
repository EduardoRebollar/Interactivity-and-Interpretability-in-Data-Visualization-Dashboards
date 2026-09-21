"""Export signed consent records as printable signed copies, for the encrypted Oxy Drive folder.

IRB form item 15: signed consent forms are kept in an encrypted, password-protected folder on the
researcher's Oxy Google Drive, apart from the study data. The app stores each signed record in its
own `consent_records` table (or, locally, `data/consent/`). This script writes each one out as a
standalone copy of the form -- the consent text, the printed name, the date and the drawn signature
-- with a blank line for the researcher's countersignature.

Output goes to `data/consent/export/` (gitignored). Move it to the Drive folder, then delete the
local copy. `--pdf` also prints each copy to PDF through a locally installed Chrome or Edge.

`--purge` then deletes the exported records from the database (or the local file), so the
identifying copy does not linger in Neon. It only ever deletes a record whose copy is already
written -- and, with `--pdf`, whose PDF is.

Usage:
    uv run python scripts/export_consents.py                  # write HTML copies
    uv run python scripts/export_consents.py --pdf            # and PDFs
    uv run python scripts/export_consents.py --pdf --purge    # then remove them from the database
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, consent, db  # noqa: E402

DEFAULT_OUT = config.CONSENT_DIR / "export"

_BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def find_browser() -> str | None:
    """A Chromium browser that can print to PDF: $CHROME, then PATH, then the usual places."""
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return next((path for path in _BROWSERS if Path(path).exists()), None)


def load_records(local_dir: Path | None) -> list[dict[str, Any]]:
    if db.configured() and local_dir is None:
        return db.fetch_consents()
    return consent.read_local(local_dir)


def filename(record: dict[str, Any]) -> str:
    """Date first so the folder sorts chronologically; the uid keeps names unique. No name in it."""
    date = str(record.get("signed_date") or "undated").replace("/", "-")
    return f"{date}_{str(record['record_uid'])[:8]}"


def print_pdf(browser: str, html_path: Path) -> Path:
    pdf = html_path.with_suffix(".pdf")
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf}",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    if not pdf.exists():
        raise RuntimeError(f"{browser} did not produce {pdf}")
    return pdf


def purge_local(local_dir: Path | None, uids: set[str]) -> int:
    path = (local_dir or config.CONSENT_DIR) / "consent_records.jsonl"
    kept = [r for r in consent.read_local(local_dir) if str(r["record_uid"]) not in uids]
    before = len(consent.read_local(local_dir))
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8"
    )
    return before - len(kept)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pdf", action="store_true", help="also print each copy to PDF")
    parser.add_argument("--purge", action="store_true", help="delete exported records afterwards")
    parser.add_argument(
        "--local-dir", type=Path, default=None, help="read local records, not the database"
    )
    args = parser.parse_args(argv)

    records = load_records(args.local_dir)
    if not records:
        print("No consent records to export.")
        return 0

    browser = find_browser() if args.pdf else None
    if args.pdf and browser is None:
        print("No Chrome or Edge found for --pdf. Set CHROME to its path, or drop --pdf.")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    exported: set[str] = set()
    for record in records:
        html_path = args.out / f"{filename(record)}.html"
        html_path.write_text(consent.copy_html(record), encoding="utf-8")
        written = [html_path.name]
        if browser:
            try:
                written.append(print_pdf(browser, html_path).name)
            except (subprocess.SubprocessError, RuntimeError, OSError) as exc:
                print(f"  PDF failed for {html_path.name}: {exc} -- record kept in the database")
                continue
        exported.add(str(record["record_uid"]))
        print(f"  {', '.join(written)}")
    print(f"Exported {len(exported)} of {len(records)} records to {args.out}")

    if args.purge and exported:
        if db.configured() and args.local_dir is None:
            removed = db.delete_consents(sorted(exported))
        else:
            removed = purge_local(args.local_dir, exported)
        print(f"Purged {removed} exported records from their store.")

    print(
        "\nNext: countersign each copy, move the folder into the encrypted Oxy Drive consent "
        "folder (IRB form item 15), then delete the local copy."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
