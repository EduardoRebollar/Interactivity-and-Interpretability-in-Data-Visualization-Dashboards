"""Tests for the deployment runtime data path.

Two jobs:

1. The lightweight loader must agree with the validated pandas one, row for row, including where the
   gaps fall. If it drifts, the deployed app charts different numbers than the ones we validated.
2. The runtime modules must not import pandas, numpy, or pyarrow. Those are 145 MB of the local
   environment; importing one would silently push the Vercel bundle over its limit, and the failure
   would appear at deploy time rather than here.
"""

from __future__ import annotations

import ast
import math
import subprocess
import sys
import tomllib

import pytest

from src import config, data, runtime_data

# Every module that ships to production. Anything they import lands in the Vercel bundle, and
# pandas + numpy + pyarrow are 146 MB of the 268 MB local environment.
RUNTIME_MODULES = [
    "src/app.py",
    "src/config.py",
    "src/contrast.py",
    "src/db.py",
    "src/figures.py",
    "src/flow.py",
    "src/layout.py",
    "src/logging.py",
    "src/runtime_data.py",
    # Ships too: imported by src/app.py and src/layout.py. Its absence here was an unguarded hole.
    "src/tasks.py",
]

FORBIDDEN = {"pandas", "numpy", "pyarrow"}

requires_deploy_csv = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)
requires_raw = pytest.mark.skipif(
    not config.RAW_CSV.exists(),
    reason="raw export absent; run scripts/download_data.py",
)


# --- Bundle constraint ------------------------------------------------------------------------


@pytest.mark.parametrize("module_path", RUNTIME_MODULES)
def test_runtime_modules_do_not_import_heavy_libraries(module_path):
    """Static check: no direct import of pandas, numpy, or pyarrow in a shipped module."""
    tree = ast.parse((config.PROJECT_ROOT / module_path).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    offenders = imported & FORBIDDEN
    assert not offenders, f"{module_path} imports {sorted(offenders)}; it ships to production"


@pytest.mark.parametrize("module", ["src.runtime_data", "src.app"])
def test_importing_a_shipped_module_pulls_in_no_heavy_libraries(module):
    """Stronger than the static check: import in a fresh interpreter and inspect the real graph.

    Catches a transitive import the AST scan would miss. `src.app` is the Vercel entrypoint
    (pinned by `tool.vercel.entrypoint`), so this covers the whole production import tree.

    This runs in the dev environment where pandas IS installed — the question is whether the app
    *loads* it, not whether it exists. For the full clean-room check with the heavy libraries
    genuinely uninstalled, run `uv run python scripts/check_bundle.py`.
    """
    code = f"import sys; import {module}; print(sorted({FORBIDDEN!r} & set(sys.modules)))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=config.PROJECT_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", (
        f"importing {module} loaded {result.stdout.strip()} into the bundle"
    )


def test_project_dependencies_exclude_the_heavy_libraries():
    """Vercel installs from [project.dependencies]; anything listed there ships.

    pandas and pyarrow belong in the dev group. `dev` specifically, because it is the group every
    tool excludes with --no-dev — a custom group name would only be dropped by a flag we cannot
    guarantee Vercel passes.
    """
    manifest = tomllib.loads((config.PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = manifest["project"]["dependencies"]
    offenders = [d for d in runtime if any(d.startswith(name) for name in FORBIDDEN)]
    assert not offenders, f"{offenders} are in [project.dependencies] and would ship to production"

    dev = manifest["dependency-groups"]["dev"]
    assert any(d.startswith("pandas") for d in dev), "pandas must stay available for local work"


def test_vercel_entrypoint_is_pinned_to_a_flask_instance():
    """Unpinned, Vercel auto-detects src/app.py and looks there for a *Flask* instance named `app`.

    That name is bound to a dash.Dash object, so the entrypoint must be pinned to `server`.
    """
    manifest = tomllib.loads((config.PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    entrypoint = manifest["tool"]["vercel"]["entrypoint"]
    assert entrypoint == "src.app:server", f"entrypoint is {entrypoint!r}"

    from flask import Flask

    from src.app import app as dash_app
    from src.app import server

    assert isinstance(server, Flask), "the pinned entrypoint must be a Flask instance"
    assert not isinstance(dash_app, Flask), (
        "src.app.app is a Dash object; if this ever becomes a Flask instance, revisit the pin"
    )


# --- Agreement with the validated loader --------------------------------------------------------


@pytest.fixture(scope="module")
def rows():
    return runtime_data.load_rows()


@requires_deploy_csv
def test_row_count_matches_locked_scope(rows):
    years = config.YEAR_MAX - config.YEAR_MIN + 1
    assert len(rows) == len(config.ENTITIES) * years * len(config.VACCINES)


@requires_deploy_csv
@requires_raw
def test_matches_the_pandas_loader_exactly(rows):
    """Every cell must agree, including which cells are missing."""
    frame = data.load()
    assert len(rows) == len(frame)

    from_csv = {(r.country, r.year, r.vaccine): r.coverage_pct for r in rows}
    assert len(from_csv) == len(rows), "duplicate keys in deploy CSV"

    mismatches = []
    for record in frame.itertuples(index=False):
        key = (record.country, int(record.year), record.vaccine)
        assert key in from_csv, f"{key} missing from deploy CSV"
        csv_value = from_csv[key]
        frame_value = None if math.isnan(record.coverage_pct) else float(record.coverage_pct)

        if csv_value is None or frame_value is None:
            if csv_value is not frame_value:
                mismatches.append((key, frame_value, csv_value))
        elif abs(csv_value - frame_value) > 1e-9:
            mismatches.append((key, frame_value, csv_value))

    assert not mismatches, f"{len(mismatches)} cells differ, first: {mismatches[:3]}"


@requires_deploy_csv
def test_gaps_are_none_not_zero(rows):
    """A missing value must never arrive as 0.0 — that would read as zero coverage."""
    uk_hepb = runtime_data.series("United Kingdom", "HepB3", rows)
    missing = [r for r in uk_hepb if r.coverage_pct is None]
    assert len(missing) == 19, f"expected 19 UK HepB3 gaps, got {len(missing)}"
    assert all(r.coverage_pct != 0.0 for r in uk_hepb if r.coverage_pct is not None)


@requires_deploy_csv
def test_series_is_year_ordered_and_complete(rows):
    series = runtime_data.series("Nigeria", "DTP3", rows)
    years = [r.year for r in series]
    assert years == sorted(years)
    assert years == list(range(config.YEAR_MIN, config.YEAR_MAX + 1))


@requires_deploy_csv
def test_entities_and_vaccines_follow_config_order(rows):
    assert runtime_data.entities(rows) == config.ENTITIES
    assert runtime_data.vaccines(rows) == list(config.VACCINES)


# --- Failure modes ----------------------------------------------------------------------------


def test_missing_file_raises_with_instructions(tmp_path):
    with pytest.raises(runtime_data.RuntimeDataError, match="export_deploy_data"):
        runtime_data.load_rows(tmp_path / "absent.csv")


def test_wrong_columns_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("country,year\nNigeria,2000\n", encoding="utf-8")
    with pytest.raises(runtime_data.RuntimeDataError, match="Unexpected columns"):
        runtime_data.load_rows(path)


def test_out_of_range_coverage_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "country,iso_code,year,vaccine,coverage_pct\nNigeria,NGA,2000,DTP3,140\n",
        encoding="utf-8",
    )
    with pytest.raises(runtime_data.RuntimeDataError, match="outside 0-100"):
        runtime_data.load_rows(path)


def test_malformed_year_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "country,iso_code,year,vaccine,coverage_pct\nNigeria,NGA,two-thousand,DTP3,50\n",
        encoding="utf-8",
    )
    with pytest.raises(runtime_data.RuntimeDataError, match="Malformed value on line 2"):
        runtime_data.load_rows(path)
