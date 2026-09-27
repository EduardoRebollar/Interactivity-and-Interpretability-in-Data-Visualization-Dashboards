"""Export signed consent records as printable signed copies, for the encrypted Oxy Drive folder.

IRB form item 15: signed consent forms are kept in an encrypted, password-protected folder on the
researcher's Oxy Google Drive, apart from the study data. The app stores each signed record in its
own `consent_records` table (or, locally, `data/consent/`). This script writes each one out as a
standalone copy of the form, laid out exactly as the participant's own PDF and the consent screen
are (`layout.signed_sheet_html`, in the app's stylesheets): the consent text, the drawn signature,
the date and the printed name, and the researcher's countersignature. The countersignature needs
RESEARCHER_SIGNATURE, as the app does, so run it with `--env-file .env.local`; without it the
researcher's line is left blank, as on the screen, and the script says so. Its date is the day the
participant agreed, in this computer's time zone.

Output goes to `data/consent/export/` (gitignored). Move it to the Drive folder, then delete the
local copy. `--pdf` also prints each copy to PDF through a locally installed Chrome or Edge, on
Letter pages, breaking only between the sheet's paragraphs, with the text kept as text.

`--purge` then deletes the exported records from the database (or the local file), so the
identifying copy does not linger in Neon. It only ever deletes a record whose copy is already
written -- and, with `--pdf`, whose PDF is.

Usage:
    uv run --env-file .env.local python scripts/export_consents.py                # HTML copies
    uv run --env-file .env.local python scripts/export_consents.py --pdf          # and PDFs
    uv run --env-file .env.local python scripts/export_consents.py --pdf --purge  # then purge
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, consent, db, layout  # noqa: E402

DEFAULT_OUT = config.CONSENT_DIR / "export"

# The app's stylesheets, in the order Dash loads them, so the sheet prints as it looks.
STYLESHEETS = tuple(
    ROOT / "src" / "assets" / name for name in ("study.css", "zz-bridge.css", "zz-overrides.css")
)
# The sheet is laid out at its width on the page, 1240 px, and scaled to a Letter page's 8.5 in
# (816 CSS px). Its 80 px top and bottom padding becomes each page's margin, as in the
# participant's PDF (assets/consent_pdf.js).
SHEET_WIDTH = 1240
SCALE = 816 / SHEET_WIDTH
PRINT_CSS = f"""
@page {{ size: letter; margin: {80 * SCALE:.2f}px 0; }}
html, body {{ margin: 0; background: #FFFFFF; }}
* {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.sheet.sheet--form {{ width: {SHEET_WIDTH}px; max-width: none; margin: 0 auto; box-shadow: none; }}
@media print {{
  .sheet.sheet--form {{ zoom: {SCALE:.6f}; padding-top: 0; padding-bottom: 0; }}
  .sheet > * {{ break-inside: avoid; }}
}}
"""

_BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def countersign_date(record: dict[str, Any]) -> str:
    """The day the participant agreed, in this computer's time zone, as the screen shows a date:
    the day their own PDF was dated in their browser. The date they typed if that is unreadable."""
    try:
        agreed = datetime.fromisoformat(str(record.get("consented_at")).replace("Z", "+00:00"))
        return agreed.astimezone().strftime("%m/%d/%Y")
    except ValueError:
        return layout._shown_date(str(record.get("signed_date") or ""))


def document(record: dict[str, Any]) -> str:
    """A standalone copy of the signed sheet: its markup, the app's stylesheets, and the print
    rules that put it on Letter pages."""
    styles = "\n".join(sheet.read_text(encoding="utf-8") for sheet in STYLESHEETS)
    sheet = layout.signed_sheet_html(record, countersign_date(record))
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">\n'
        "<title>Signed consent form</title>\n"
        f"<style>\n{styles}\n{PRINT_CSS}</style></head>\n"
        f"<body>{sheet}</body></html>\n"
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

    if consent.researcher_signature() is None:
        print(
            f"{consent.SIGNATURE_ENV} is not set, so the researcher's line is left blank. Run with "
            "`uv run --env-file .env.local` to countersign the copies."
        )

    args.out.mkdir(parents=True, exist_ok=True)
    exported: set[str] = set()
    for record in records:
        html_path = args.out / f"{filename(record)}.html"
        html_path.write_text(document(record), encoding="utf-8")
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
        "\nNext: move the folder into the encrypted Oxy Drive consent folder (IRB form item 15), "
        "then delete the local copy."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
