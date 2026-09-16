"""Blind coding of justifications for RQ2 (docs/study-design.md section 7).

Three steps:

    sheets   Write the blind sheets under data/study_logs/coding/:
               coder1.csv   every justification, shuffled, for the primary coder
               coder2.csv   the stratified 20% sample, for the second coder
               key.csv      the unblinding map -- for the analyst, NEVER for a coder
    kappa    Read both completed sheets and report Cohen's kappa per code, with prevalence.
    depth    Join the primary coder's sheet back to the tasks and write depth.csv (0-3 per answer).

Run `scripts/score_study.py` first: this reads its tasks.csv, so exclusions are already marked.
Everything written here is participant free text and is gitignored.

Usage:
    uv run python scripts/code_justifications.py sheets
    uv run python scripts/code_justifications.py kappa
    uv run python scripts/code_justifications.py depth
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from analysis import coding  # noqa: E402
from src import config  # noqa: E402

DERIVED = config.STUDY_LOGS_DIR / "derived"
CODING = config.STUDY_LOGS_DIR / "coding"


def _units(tasks_csv: Path) -> list[coding.Unit]:
    tasks = pd.read_csv(tasks_csv, dtype={"session_id": str, "participant_id": str})
    usable = tasks[tasks["use_accuracy"]]
    return coding.build_units(usable.to_dict("records"))


def sheets(tasks_csv: Path, out: Path) -> int:
    units = _units(tasks_csv)
    if not units:
        print("No justifications to code.", file=sys.stderr)
        return 1
    sample = coding.double_coded_sample(units)
    coding.write_sheet(units, out / "coder1.csv")
    coding.write_sheet([u for u in units if u.unit_id in sample], out / "coder2.csv")
    coding.write_key(units, out / "key.csv")
    print(f"{len(units)} units -> {out / 'coder1.csv'}")
    print(f"{len(sample)} double-coded units -> {out / 'coder2.csv'}")
    print(f"seed {coding.SEED}, fraction {coding.DOUBLE_CODED_FRACTION}, stratified by condition")
    print(f"Unblinding map -> {out / 'key.csv'}  (do NOT give this to a coder)")
    return 0


def kappa(out: Path) -> int:
    key = pd.read_csv(out / "key.csv", dtype=str)
    everyone = set(key["unit_id"])
    primary = coding.read_sheet(out / "coder1.csv", expected_ids=everyone)
    secondary_ids = set(pd.read_csv(out / "coder2.csv", dtype=str)["unit_id"])
    secondary = coding.read_sheet(out / "coder2.csv", expected_ids=secondary_ids)
    report = coding.kappa_report(primary, secondary)
    print(f"Inter-rater reliability over {len(secondary)} double-coded units")
    for code, stats in report.items():
        print(
            f"  {code:18} kappa {coding.format_kappa(stats['kappa']):>24}   "
            f"prevalence {stats['prevalence']:.2f}   raw agreement {stats['agreement']:.2f}"
        )
    return 0


def depth(out: Path) -> int:
    key = pd.read_csv(out / "key.csv", dtype=str)
    primary = coding.read_sheet(out / "coder1.csv", expected_ids=set(key["unit_id"]))
    rows = [
        {"unit_id": uid, **codes, "depth": coding.depth(codes)} for uid, codes in primary.items()
    ]
    coded = key.merge(pd.DataFrame(rows), on="unit_id", validate="one_to_one")
    coded.to_csv(out / "depth.csv", index=False)
    print(f"Wrote {out / 'depth.csv'} ({len(coded)} coded answers)")
    print(coded.groupby("condition")["depth"].agg(["count", "mean", "std"]).to_string())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind RQ2 coding of justifications.")
    parser.add_argument("step", choices=("sheets", "kappa", "depth"))
    parser.add_argument("--tasks", type=Path, default=DERIVED / "tasks.csv")
    parser.add_argument("--out", type=Path, default=CODING)
    args = parser.parse_args(argv)
    try:
        if args.step == "sheets":
            return sheets(args.tasks, args.out)
        if args.step == "kappa":
            return kappa(args.out)
        return depth(args.out)
    except (coding.CodingError, FileNotFoundError) as exc:
        print(f"Cannot {args.step}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
