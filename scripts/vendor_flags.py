"""Vendor the country chips' flags into `src/assets/flags/`, so no browser has to fetch them.

The interactive condition's country chips carry a small flag beside each name (the design handoff,
`docs/visual-spec.md` section 7.3). The handoff's mockups load them from flagcdn.com; a study page
must not make a third-party request in the middle of a task, so this script downloads each one
once, and the app serves them from its own assets folder, as it does the map's shapes.

One PNG per country in the locked scope, named by its ISO-3 code as the deploy CSV gives it
(`bra.png`). 80 px wide, for a chip that shows 24 px, so it stays sharp on a high-density screen.
Aggregates such as World have no flag and no chip.

The output is generated and committed so the deployment has it. Re-run this only if the scope
changes.

Usage:
    uv run python scripts/vendor_flags.py
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, runtime_data  # noqa: E402

SOURCE_URL = "https://flagcdn.com/w80/{code}.png"
OUT = ROOT / "src" / "assets" / "flags"
USER_AGENT = "vaccine-dashboard/0.1 (Occidental College senior comprehensive; research use)"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# flagcdn names flags by ISO 3166-1 alpha-2; the data names countries by alpha-3.
ALPHA2 = {
    "AFG": "af",
    "BFA": "bf",
    "BGD": "bd",
    "BRA": "br",
    "CAF": "cf",
    "CHN": "cn",
    "CMR": "cm",
    "COD": "cd",
    "COL": "co",
    "EGY": "eg",
    "ETH": "et",
    "GBR": "gb",
    "IDN": "id",
    "IND": "in",
    "KEN": "ke",
    "KHM": "kh",
    "MDG": "mg",
    "MLI": "ml",
    "MMR": "mm",
    "MOZ": "mz",
    "NER": "ne",
    "NGA": "ng",
    "NPL": "np",
    "PAK": "pk",
    "SOM": "so",
    "TCD": "td",
    "TZA": "tz",
    "UGA": "ug",
    "UKR": "ua",
    "USA": "us",
    "VNM": "vn",
    "ZMB": "zm",
}


def countries() -> dict[str, str]:
    """Each country in the scope and its ISO-3 code, as the deploy CSV has them."""
    codes: dict[str, str] = {}
    for row in runtime_data.load_rows():
        if row.country in config.ENTITIES and not row.iso_code.startswith("OWID"):
            codes.setdefault(row.country, row.iso_code)
    return codes


def main() -> int:
    wanted = countries()
    missing = sorted(code for code in wanted.values() if code not in ALPHA2)
    if missing:
        print(f"No alpha-2 code for {missing}; add them to ALPHA2", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for country, code in sorted(wanted.items()):
        url = SOURCE_URL.format(code=ALPHA2[code])
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"Download failed for {country} ({url}): {exc}", file=sys.stderr)
            return 1
        if not payload.startswith(PNG_SIGNATURE):
            print(f"{url} is not a PNG", file=sys.stderr)
            return 1
        (OUT / f"{code.lower()}.png").write_bytes(payload)
    total = sum(path.stat().st_size for path in OUT.glob("*.png"))
    print(f"Wrote {len(wanted)} flags to {OUT} ({total / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
