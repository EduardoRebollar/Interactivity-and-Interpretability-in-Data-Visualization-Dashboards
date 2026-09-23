"""Derive the answer key from the data and check it against docs/study-design.md section 4.

Prints every item's key with the evidence it was derived from, for the methods appendix. Exits 1 if
any derived key disagrees with the transcribed table, or any item's key cannot be derived at all.
The same check runs in the test suite; this is the readable version.

Usage:
    uv run python scripts/derive_keys.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import keys  # noqa: E402


def main() -> int:
    problems = keys.check()
    try:
        table = keys.key_table()
    except keys.KeyDerivationError:
        table = {}

    for (form, task_id), key in sorted(table.items()):
        print(f"{form}-{task_id}  {key.kind:9}  {key.correct!r}")
        print(f"          rule: {key.rule}")
        # Every rule records the margins its acceptance check measured, under its own names.
        for name, value in key.evidence.items():
            print(f"          {name}: {value}")

    if problems:
        print("\nKEY CHECK FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"\nAll {len(table)} derived keys match docs/study-design.md section 4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
