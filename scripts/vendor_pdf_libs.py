"""Vendor the two libraries that make the signed consent PDF into `src/assets/vendor/`.

The ID screen's "Download your signed consent form" saves a PDF laid out exactly as the consent
sheet looks on the page (`src/assets/consent_pdf.js`): html2canvas draws the sheet, and jsPDF puts
the drawing on Letter pages. The page must not fetch a script from a third party, so this script
downloads each one once and the app serves them from its own assets folder, as it does the map's
shapes and the flags. `app.create_app` keeps them out of the page's initial load
(`assets_path_ignore`); consent_pdf.js loads them when the button is pressed.

Each file is pinned by version and by SHA-256, and a download that does not match is refused.
Both are MIT-licensed, and each keeps its licence header.

The output is generated and committed so the deployment has it. Re-run this only to change a
version, and update the pins with it.

Usage:
    uv run python scripts/vendor_pdf_libs.py
"""

from __future__ import annotations

import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "assets" / "vendor"
USER_AGENT = "vaccine-dashboard/0.1 (Occidental College senior comprehensive; research use)"

# file name -> (source URL, SHA-256 of the file as published)
LIBRARIES = {
    "jspdf.umd.min.js": (
        "https://cdn.jsdelivr.net/npm/jspdf@4.2.1/dist/jspdf.umd.min.js",
        "e6551fcdc32f09d6853b2c5126d18d01d9447e0da618a41a11ebeee0f6c20d54",
    ),
    "html2canvas.min.js": (
        "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js",
        "e87e550794322e574a1fda0c1549a3c70dae5a93d9113417a429016838eab8cb",
    ),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in LIBRARIES.items():
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"Download failed for {name} ({url}): {exc}", file=sys.stderr)
            return 1
        found = hashlib.sha256(payload).hexdigest()
        if found != digest:
            print(f"{url} has SHA-256 {found}, not the pinned {digest}", file=sys.stderr)
            return 1
        (OUT / name).write_bytes(payload)
        print(f"Wrote {name} ({len(payload) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
