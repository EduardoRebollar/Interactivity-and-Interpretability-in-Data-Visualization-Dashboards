"""Archive the signed consent forms into the encrypted Oxy Drive folder, in one run after a session.

IRB form item 15: signed consent forms are kept in an encrypted, password-protected folder on the
researcher's Oxy Google Drive, apart from the study data. Google Drive cannot password-protect a
folder, so what goes there is an encrypted 7-Zip archive (AES-256, file names hidden too), and
nothing unencrypted ever reaches it. This script:

1. writes each signed record as its copy of the form, HTML and PDF, as `export_consents.py` does,
   into a staging folder under `data/consent/` (gitignored);
2. packs them into a 7-Zip archive under a password typed twice, then tests the archive with that
   password and checks every copy is inside;
3. copies the archive into the Drive folder that Google Drive for desktop syncs, and checks the
   copy is byte-identical;
4. deletes the staging folder, so no unencrypted copy is left on this laptop;
5. asks before deleting the archived records from the database (or the local file). Answer y once
   the archive shows in the folder at drive.google.com. Answer anything else and nothing is
   deleted; the next run archives those records again.

The Drive folder is `CONSENT_DRIVE_DIR` in `.env.local` (or `--drive`). It is a path on this
laptop, so it is never committed. The password is never stored: use the same one every time and
keep it in a password manager, since a forgotten password loses the forms for good. It reaches
7-Zip as a command-line argument, which other programs running as this user could read while it
runs.

Needs 7-Zip (7z.exe on PATH, in Program Files, or `SEVEN_ZIP`) and Chrome or Edge for the PDFs.

Usage:
    uv run --env-file .env.local python scripts/archive_consents.py
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import export_consents  # noqa: E402
from src import config, consent, db  # noqa: E402

DRIVE_ENV = "CONSENT_DRIVE_DIR"
DEFAULT_STAGING = config.CONSENT_DIR / "staging"
MIN_PASSWORD = 12

_SEVEN_ZIPS = (
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
    "/opt/homebrew/bin/7zz",
    "/usr/local/bin/7zz",
)


def find_7zip() -> str | None:
    """7-Zip's command-line program: $SEVEN_ZIP, then PATH, then the usual places."""
    if os.environ.get("SEVEN_ZIP"):
        return os.environ["SEVEN_ZIP"]
    for name in ("7z", "7zz", "7za"):
        found = shutil.which(name)
        if found:
            return found
    return next((path for path in _SEVEN_ZIPS if Path(path).exists()), None)


def ask_password() -> str | None:
    """The archive password, typed twice without echo. None if the two differ or it is short."""
    first = getpass.getpass("Archive password: ")
    if len(first) < MIN_PASSWORD:
        print(f"The password must be at least {MIN_PASSWORD} characters. Nothing was written.")
        return None
    if getpass.getpass("Type it again: ") != first:
        print("The two passwords differ. Nothing was written.")
        return None
    return first


def seven_zip(program: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run 7-Zip with no console prompt: a missing password fails rather than waits."""
    return subprocess.run(
        [program, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
    )


def make_archive(program: str, archive: Path, forms: Path, password: str, names: set[str]) -> None:
    """Pack `forms` into an encrypted archive, then prove it opens with `password` and holds every
    copy. Raises RuntimeError otherwise, before anything is copied or deleted."""
    packed = seven_zip(
        program, "a", "-t7z", "-mhe=on", f"-p{password}", "-y", str(archive), str(forms / "*")
    )
    if packed.returncode != 0 or not archive.exists():
        raise RuntimeError(f"7-Zip could not write the archive:\n{packed.stdout}{packed.stderr}")
    tested = seven_zip(program, "t", f"-p{password}", str(archive))
    if tested.returncode != 0:
        raise RuntimeError(f"The archive failed 7-Zip's test:\n{tested.stdout}{tested.stderr}")
    listed = seven_zip(program, "l", "-ba", f"-p{password}", str(archive))
    missing = sorted(name for name in names if name not in listed.stdout)
    if listed.returncode != 0 or missing:
        raise RuntimeError(f"The archive is missing {', '.join(missing) or 'its listing'}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def purge(local_dir: Path | None, uids: set[str]) -> int:
    if db.configured() and local_dir is None:
        return db.delete_consents(sorted(uids))
    return export_consents.purge_local(local_dir, uids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--drive", type=Path, default=None, help=f"the synced Drive folder (default ${DRIVE_ENV})"
    )
    parser.add_argument(
        "--local-dir", type=Path, default=None, help="read local records, not the database"
    )
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    drive = args.drive or (Path(os.environ[DRIVE_ENV]) if os.environ.get(DRIVE_ENV) else None)
    if drive is None:
        print(f"Set {DRIVE_ENV} in .env.local to the Drive folder, or pass --drive.")
        return 1
    if not drive.is_dir():
        print(f"{drive} is not there. Is Google Drive for desktop running and signed in?")
        return 1
    program = find_7zip()
    if program is None:
        print("7-Zip not found. Install it (winget install 7zip.7zip) or set SEVEN_ZIP to 7z.exe.")
        return 1
    browser = export_consents.find_browser()
    if browser is None:
        print("No Chrome or Edge found for the PDFs. Set CHROME to its path.")
        return 1

    records = export_consents.load_records(args.local_dir)
    if not records:
        print("No consent records to archive.")
        return 0
    print(f"{len(records)} signed consent record(s) to archive.")
    if consent.researcher_signature() is None:
        print(
            f"{consent.SIGNATURE_ENV} is not set, so the researcher's line is left blank. Run with "
            "`uv run --env-file .env.local` to countersign the copies."
        )

    password = ask_password()
    if password is None:
        return 1

    # A staging folder left by an interrupted run holds copies of records not yet purged, since
    # purging is the last step; they are written again below.
    shutil.rmtree(args.staging, ignore_errors=True)
    forms = args.staging / "forms"
    forms.mkdir(parents=True)
    try:
        archived: set[str] = set()
        names: set[str] = set()
        for record in records:
            html_path = forms / f"{export_consents.filename(record)}.html"
            html_path.write_text(export_consents.document(record), encoding="utf-8")
            try:
                pdf = export_consents.print_pdf(browser, html_path)
            except (subprocess.SubprocessError, RuntimeError, OSError) as exc:
                print(f"  PDF failed for {html_path.name}: {exc} -- record left in its store")
                html_path.unlink()
                continue
            archived.add(str(record["record_uid"]))
            names.update((html_path.name, pdf.name))
        if not archived:
            print("No copy could be written. Nothing was archived.")
            return 1

        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        archive = args.staging / f"consent-forms_{stamp}.7z"
        try:
            make_archive(program, archive, forms, password, names)
        except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
            print(f"{exc}\nNothing was copied to Drive or deleted.")
            return 1

        target = drive / archive.name
        if target.exists():
            print(f"{target} already exists. Nothing was copied or deleted; run again.")
            return 1
        shutil.copy2(archive, target)
        if sha256(target) != sha256(archive):
            print(f"The copy in {drive} differs from the archive. Nothing was deleted.")
            return 1
    finally:
        # Every unencrypted copy goes, whatever happened; the records are still in their store.
        shutil.rmtree(args.staging, ignore_errors=True)

    print(f"Archived {len(archived)} form(s) into {target}")
    print("Google Drive for desktop uploads it in the background.")
    answer = input(
        f"Once {target.name} shows at drive.google.com, delete these {len(archived)} record(s) "
        "from the database? [y/N] "
    )
    if answer.strip().lower() not in ("y", "yes"):
        print("Nothing deleted. The next run archives these records again.")
        return 0
    print(f"Deleted {purge(args.local_dir, archived)} archived record(s) from their store.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
