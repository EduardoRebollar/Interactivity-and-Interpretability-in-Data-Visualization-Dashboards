"""End-to-end check that the study database actually works. Run before any participant does.

`src/db.py`'s SQL cannot be exercised without a real Postgres, so until this passes the DDL, the
inserts and the JSONB round-trip are all unverified. A column mismatch or a DDL typo would otherwise
surface in the middle of a participant's session, when the data is unrecoverable.

Writes a complete synthetic session — both conditions, tasks, answers, null and non-null browser
timings — reads it back, checks every field survived, then deletes exactly what it wrote and
confirms it is gone. Safe to run against the instance that will hold real data.

Usage:
    uv run python scripts/verify_deployment.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db  # noqa: E402
from src.logging import SCHEMA_VERSION, PostgresSink, StudyLogger  # noqa: E402

EXPECTED_TABLES = {"participants", "study_events"}


class VerificationError(RuntimeError):
    pass


def _check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        raise VerificationError(f"{label}{': ' + detail if detail else ''}")


def verify() -> None:
    # A unique id so a failed earlier run cannot collide, and so cleanup is unambiguous.
    participant = f"__verify_{uuid.uuid4().hex[:8]}"
    partner = f"__verify_{uuid.uuid4().hex[:8]}"

    print("1. Schema")
    db.init_schema()
    tables = db.table_names()
    _check("tables created", tables >= EXPECTED_TABLES, f"found {sorted(tables)}")
    db.init_schema()
    _check("init_schema is idempotent", True)

    print("2. Counterbalancing")
    seq_a, cond_a = db.register_participant(participant)
    seq_b, cond_b = db.register_participant(partner)
    _check(
        "two participants get consecutive sequence numbers",
        seq_b == seq_a + 1,
        f"{seq_a} then {seq_b}",
    )
    _check("their first conditions differ", cond_a != cond_b, f"{cond_a} and {cond_b}")
    repeat_seq, repeat_cond = db.register_participant(participant)
    _check(
        "re-registering is idempotent",
        (repeat_seq, repeat_cond) == (seq_a, cond_a),
        "a returning participant must not be re-randomised",
    )

    print("3. A full synthetic session")
    written = 0
    for order, interactive in ((1, cond_a == "interactive"), (2, cond_a != "interactive")):
        log = StudyLogger(
            participant, condition_order=order, interactive=interactive, sink=PostgresSink()
        )
        log.event("condition_start", interactive=interactive, condition_order=order)
        log.start_task("T1", client_elapsed_ms=1500.0)
        log.event("line_isolate", entity="Nigeria", isolated=True, client_elapsed_ms=2000.0)
        log.submit_answer(
            "T1",
            answer={"choice": "Nigeria", "confidence": 4},
            duration_ms=8200.5,
            client_elapsed_ms=9700.5,
        )
        log.end_task("T1", duration_ms=8200.5, client_elapsed_ms=9700.5)
        # Deliberately omit client timings here: nulls must survive too.
        log.event("view_change", control="vaccine", value="MCV1", previous="DTP3")
        log.event("condition_end", interactive=interactive, condition_order=order)
        log.close()
        written += 8
    print(f"  wrote {written} events across both conditions")

    print("4. Reading it back")
    events = db.fetch_events(participant)
    _check("every event returned", len(events) == written, f"{len(events)} of {written}")
    _check("schema version recorded", {e["schema_version"] for e in events} == {SCHEMA_VERSION})
    _check("both conditions present", {e["condition"] for e in events} == {"static", "interactive"})
    _check("both condition orders present", {e["condition_order"] for e in events} == {1, 2})
    _check("events are ordered", [e["id"] for e in events] == sorted(e["id"] for e in events))

    answers = [e for e in events if e["event"] == "answer_submit"]
    _check("answers recorded", len(answers) == 2, f"found {len(answers)}")
    _check(
        "nested JSONB answer survived",
        all(a["payload"]["answer"] == {"choice": "Nigeria", "confidence": 4} for a in answers),
    )
    _check("answers attributed to their task", all(a["task_id"] == "T1" for a in answers))

    timed = [e for e in events if e["event"] == "task_end"]
    _check(
        "browser duration survived as a float",
        all(abs(e["task_elapsed_ms"] - 8200.5) < 1e-6 for e in timed),
    )
    untimed = [e for e in events if e["event"] == "view_change"]
    _check(
        "absent browser timings stay NULL, not zero",
        all(e["client_elapsed_ms"] is None for e in untimed),
    )
    _check(
        "server cross-check always present", all(e["server_elapsed_ms"] is not None for e in events)
    )
    _check("server timestamps set", all(e["server_ts"] is not None for e in events))

    print("5. Cleanup")
    removed_events, removed_participants = db.delete_participant(participant)
    db.delete_participant(partner)
    _check("events removed", removed_events == written, f"removed {removed_events}")
    _check("participant removed", removed_participants == 1)
    _check("nothing left behind", db.fetch_events(participant) == [])


def main() -> int:
    if not db.configured():
        print(
            "DATABASE_URL is not set.\n"
            "Provision Neon through the Vercel Marketplace, then `vercel env pull .env.local` "
            "and export DATABASE_URL (use the POOLED connection string).",
            file=sys.stderr,
        )
        return 1

    try:
        verify()
    except VerificationError as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1
    except db.DatabaseError as exc:
        print(f"\nDatabase error: {exc}", file=sys.stderr)
        return 1

    print("\nDEPLOYMENT VERIFIED - the database is ready for participants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
