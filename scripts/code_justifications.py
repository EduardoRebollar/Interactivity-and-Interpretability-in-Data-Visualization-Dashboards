"""Blind coding of justifications for RQ2, and of T1's descriptions for RQ1 (study-design.md 7).

RQ2, three steps:

    sheets   Write the blind sheets under data/study_logs/coding/:
               coder1.csv   every justification, shuffled, for the primary coder; T1's
                            description stands in for its justification
               coder2.csv   the stratified 20% sample, for the second coder
               key.csv      the unblinding map -- for the analyst, NEVER for a coder
    kappa    Read both completed sheets and report Cohen's kappa per code, with prevalence.
    depth    Join the primary coder's sheet back to the tasks and write depth.csv (0-3 per answer).

T1's rubric, two steps (both coders code every description):

    rubric-sheets   Write rubric_coder1.csv and rubric_coder2.csv (the same units, each in its own
                    shuffle) and rubric_key.csv, the unblinding map.
    rubric          Read both, report kappa per field, and write rubric_disagreements.csv. Once
                    every disagreement is settled, still blind, in rubric_settled.csv (unit_id, a,
                    b, c, contradicts), run it again: it writes rubric_verdicts.csv, which
                    scripts/score_study.py reads.

Run `scripts/score_study.py` first: this reads its tasks.csv, so exclusions are already marked.
Everything written here is participant free text and is gitignored.

Usage:
    uv run python scripts/code_justifications.py sheets
    uv run python scripts/code_justifications.py kappa
    uv run python scripts/code_justifications.py depth
    uv run python scripts/code_justifications.py rubric-sheets
    uv run python scripts/code_justifications.py rubric
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


def _rubric_units(tasks_csv: Path) -> list[coding.Unit]:
    tasks = pd.read_csv(tasks_csv, dtype={"session_id": str, "participant_id": str})
    return coding.build_rubric_units(tasks[tasks["use_accuracy"]].to_dict("records"))


def rubric_sheets(tasks_csv: Path, out: Path) -> int:
    units = _rubric_units(tasks_csv)
    if not units:
        print("No T1 descriptions to code.", file=sys.stderr)
        return 1
    # Different seeds, so neither coder's order can be matched against the other's.
    coding.write_rubric_sheet(units, out / "rubric_coder1.csv", seed=coding.SEED)
    coding.write_rubric_sheet(units, out / "rubric_coder2.csv", seed=coding.SEED + 1)
    coding.write_key(units, out / "rubric_key.csv")
    print(f"{len(units)} T1 descriptions -> {out / 'rubric_coder1.csv'} and rubric_coder2.csv")
    print(f"Unblinding map -> {out / 'rubric_key.csv'}  (do NOT give this to a coder)")
    return 0


def rubric(tasks_csv: Path, out: Path) -> int:
    units = _rubric_units(tasks_csv)
    ids = {unit.unit_id for unit in units}
    first = coding.read_rubric_sheet(out / "rubric_coder1.csv", ids)
    second = coding.read_rubric_sheet(out / "rubric_coder2.csv", ids)
    report = coding.kappa_report(first, second, coding.RUBRIC_FIELDS)
    print(f"Rubric agreement over {len(ids)} T1 descriptions, before any discussion")
    for field, stats in report.items():
        print(
            f"  {field:12} kappa {coding.format_kappa(stats['kappa']):>24}   "
            f"prevalence {stats['prevalence']:.2f}   raw agreement {stats['agreement']:.2f}"
        )
    n_open = coding.write_disagreements(units, first, second, out / "rubric_disagreements.csv")
    print(f"{n_open} disagreements -> {out / 'rubric_disagreements.csv'}")
    settled = coding.read_settled(out / "rubric_settled.csv", ids)
    verdicts = coding.settle(first, second, settled)
    coding.write_verdicts(units, verdicts, out / "rubric_verdicts.csv")
    print(f"{sum(verdicts.values())} of {len(verdicts)} correct -> {out / 'rubric_verdicts.csv'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind RQ2 coding of justifications.")
    parser.add_argument("step", choices=("sheets", "kappa", "depth", "rubric-sheets", "rubric"))
    parser.add_argument("--tasks", type=Path, default=DERIVED / "tasks.csv")
    parser.add_argument("--out", type=Path, default=CODING)
    args = parser.parse_args(argv)
    try:
        if args.step == "sheets":
            return sheets(args.tasks, args.out)
        if args.step == "kappa":
            return kappa(args.out)
        if args.step == "rubric-sheets":
            return rubric_sheets(args.tasks, args.out)
        if args.step == "rubric":
            return rubric(args.tasks, args.out)
        return depth(args.out)
    except (coding.CodingError, FileNotFoundError) as exc:
        print(f"Cannot {args.step}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
