"""Clean-room check: does the app actually run on the deployment subset alone?

`tests/test_runtime_data.py` proves the app never *loads* pandas, numpy or pyarrow. This goes
further and proves it runs with them genuinely **uninstalled**, which is the real deployment
condition, and measures the resulting bundle.

Builds a throwaway virtualenv from `requirements.txt` only — no dev group, no `uv sync` — installs
nothing else, and serves the Vercel entry point through it.

Usage:
    uv run python scripts/check_bundle.py [--keep]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402

FORBIDDEN = ("pandas", "numpy", "pyarrow")

# Vercel's Python bundle ceiling. Warn well before it rather than at deploy time.
LIMIT_MB = 250.0
WARN_MB = 200.0

CHECK_SCRIPT = """
import sys

forbidden = ("pandas", "numpy", "pyarrow")
for name in forbidden:
    try:
        __import__(name)
    except ImportError:
        pass
    else:
        raise SystemExit(f"FAIL: {name} is installed; the venv is not clean")

from api.index import app as wsgi

client = wsgi.test_client()
for path in ("/", "/_dash-layout", "/_dash-dependencies"):
    response = client.get(path)
    if response.status_code != 200:
        raise SystemExit(f"FAIL: {path} returned {response.status_code}")
    print(f"  {path:22s} -> 200  {len(response.data):>7,} bytes")

leaked = [n for n in forbidden if n in sys.modules]
if leaked:
    raise SystemExit(f"FAIL: {leaked} loaded at runtime")

from src import figures

entities = ["Nigeria", "India", "World"]
first = figures.build_figure(entities, "DTP3").to_json()
second = figures.build_figure(entities, "DTP3").to_json()
if first != second:
    raise SystemExit("FAIL: figures are not deterministic")
if figures.graph_config(False)["staticPlot"] is not True:
    raise SystemExit("FAIL: static condition is not static")
print("  figures deterministic, static condition inert")
print(f"  python {sys.version.split()[0]}, {len(sys.modules)} modules loaded")
"""


def _directory_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="do not delete the throwaway venv")
    args = parser.parse_args()

    requirements = config.PROJECT_ROOT / "requirements.txt"
    if not requirements.exists():
        print(f"{requirements} not found", file=sys.stderr)
        return 1

    # A short path on purpose: a deep one overruns Windows' path limit and the venv's python.exe
    # then fails to launch with an opaque error.
    venv = Path(tempfile.gettempdir()) / "vdbundle"
    if venv.exists():
        shutil.rmtree(venv, ignore_errors=True)

    try:
        print(f"Building clean venv at {venv}")
        subprocess.run(
            ["uv", "venv", "--python", "3.11", str(venv)],
            check=True,
            capture_output=True,
            text=True,
        )
        python = venv / "Scripts" / "python.exe"
        if not python.exists():
            python = venv / "bin" / "python"

        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), "-r", str(requirements)],
            check=True,
            capture_output=True,
            text=True,
        )

        print("Running the app on the deployment subset alone:")
        # Inherit the environment and only add PYTHONPATH. Clearing PATH on Windows stops the
        # interpreter loading system socket DLLs, which asyncio needs at import time.
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(config.PROJECT_ROOT)
        result = subprocess.run(
            [str(python), "-c", CHECK_SCRIPT],
            cwd=config.PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        print(result.stdout, end="")
        if result.returncode != 0:
            print(result.stdout or "", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1

        site_packages = next(venv.rglob("site-packages"), None)
        size = _directory_mb(site_packages) if site_packages else 0.0
        print(f"\nBundle: {size:.1f} MB installed (limit {LIMIT_MB:.0f} MB)")
        if size > LIMIT_MB:
            print(f"OVER THE LIMIT by {size - LIMIT_MB:.1f} MB", file=sys.stderr)
            return 1
        if size > WARN_MB:
            print(f"Within {LIMIT_MB - size:.1f} MB of the limit — watch new dependencies")
        print("BUNDLE OK")
        return 0

    except subprocess.CalledProcessError as exc:
        print(f"Setup failed: {exc.stderr or exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep:
            shutil.rmtree(venv, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
