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
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db  # noqa: E402
from src.logging import SCHEMA_VERSION, PostgresSink, StudyLogger  # noqa: E402

EXPECTED_TABLES = {"participants", "study_events", "consent_records"}


class VerificationError(RuntimeError):
    pass


def other(form: str) -> str:
    """The form a participant sees in their second condition."""
    return "B" if form == "A" else "A"


def _check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        raise VerificationError(f"{label}{': ' + detail if detail else ''}")


def verify() -> None:
    # A unique id so a failed earlier run cannot collide, and so cleanup is unambiguous.
    participant = f"__verify_{uuid.uuid4().hex[:8]}"
    partner = f"__verify_{uuid.uuid4().hex[:8]}"
    third = f"__verify_{uuid.uuid4().hex[:8]}"
    try:
        _verify(participant, partner, third)
    finally:
        # Always, pass or fail. A failed check used to return before cleanup and leave synthetic
        # participants and events in the database that holds the real data.
        try:
            for synthetic in (participant, partner, third):
                db.delete_participant(synthetic)
            print("  cleanup: synthetic participants removed")
        except db.DatabaseError as exc:
            print(f"  cleanup FAILED, remove {participant}, {partner}, {third} by hand: {exc}")


def _verify(participant: str, partner: str, third: str) -> None:

    print("1. Schema")
    db.init_schema()
    tables = db.table_names()
    _check("tables created", tables >= EXPECTED_TABLES, f"found {sorted(tables)}")
    db.init_schema()
    _check("init_schema is idempotent", True)
    columns = db.column_names("study_events")
    _check(
        "every logged column exists on the table",
        set(db.EVENT_COLUMNS) <= columns,
        f"missing {sorted(set(db.EVENT_COLUMNS) - columns)} -- a pre-v4 table was not migrated",
    )
    _check(
        "participants can be marked withdrawn",
        "withdrawn_at" in db.column_names("participants"),
        "a pre-v6 participants table was not migrated",
    )
    consent_columns = db.column_names("consent_records")
    _check(
        "the consent table has every column and no participant ID",
        set(db.CONSENT_COLUMNS) <= consent_columns and "participant_id" not in consent_columns,
        f"found {sorted(consent_columns)}",
    )

    print("2. Counterbalancing")
    seq_a, cond_a, form_a = db.register_participant(participant)
    seq_b, cond_b, form_b = db.register_participant(partner)
    _check(
        "two participants get consecutive sequence numbers",
        seq_b == seq_a + 1,
        f"{seq_a} then {seq_b}",
    )
    _check(
        "consecutive participants differ in condition or form",
        (cond_a, form_a) != (cond_b, form_b),
        f"{cond_a}/{form_a} and {cond_b}/{form_b}",
    )
    repeat = db.register_participant(participant)
    _check(
        "re-registering is idempotent",
        repeat == (seq_a, cond_a, form_a),
        "a returning participant must not be re-randomised",
    )
    db.register_participant(participant)
    seq_c, _cond_c, _form_c = db.register_participant(third)
    _check(
        "re-registering does not consume a sequence number",
        seq_c == seq_b + 1,
        f"{seq_b} then {seq_c}: a repeat registration skipped the next participant's cell",
    )

    print("2b. Consent records and withdrawal")
    record_uid = str(uuid.uuid4())
    signature = [[[10, 20], [30, 40], [50, 45]], [[60, 60]]]
    db.insert_consent(
        {
            "record_uid": record_uid,
            "consent_version": "verify",
            "consented_at": "2026-09-16T10:00:00.000Z",
            "printed_name": "Verify Deployment",
            "signed_date": "2026-09-16",
            "signature_method": "drawn",
            "signature": signature,
            "received_at": None,
        }
    )
    try:
        stored = [r for r in db.fetch_consents() if str(r["record_uid"]) == record_uid]
        _check("a consent record round-trips", len(stored) == 1, f"found {len(stored)}")
        _check("the signature survived as JSONB", stored[0]["signature"] == signature)
    finally:
        removed = db.delete_consents([record_uid])
    _check("the synthetic consent record is deleted", removed == 1, f"removed {removed}")

    _check("withdrawing marks a registered participant", db.withdraw_participant(third) == 0)
    try:
        db.register_participant(third)
        refused = False
    except db.WithdrawnParticipantError:
        refused = True
    _check("a withdrawn ID cannot register again", refused)

    print("3. A full synthetic session")
    written = 0
    orders = ((1, cond_a == "interactive", form_a), (2, cond_a != "interactive", other(form_a)))
    for order, interactive, form in orders:
        log = StudyLogger(
            participant,
            condition_order=order,
            interactive=interactive,
            form=form,
            sink=PostgresSink(),
        )
        if order == 1:
            log.record_consent("2026-09-16T10:00:00.000Z", "verify")
            written += 1
        log.event("condition_start", interactive=interactive, condition_order=order)
        log.start_task("T1", client_elapsed_ms=1500.0)
        log.event("line_isolate", entity="Nigeria", isolated=True, client_elapsed_ms=2000.0)
        log.submit_answer(
            "T1",
            answer={"choice": "Nigeria", "confidence": 4},
            justification="Its line fell furthest over the window.",
            duration_ms=8200.5,
            client_elapsed_ms=9700.5,
        )
        log.end_task("T1", duration_ms=8200.5, client_elapsed_ms=9700.5)
        # Deliberately omit client timings here: nulls must survive too.
        log.event("view_change", control="vaccine", value="MCV1", previous="DTP3")
        log.rate_load(7, client_elapsed_ms=12000.0)
        log.event("condition_end", interactive=interactive, condition_order=order)
        log.close()
        # session_start (written when the logger opens), the seven above, and session_end.
        written += 10
    print(f"  wrote {written} events across both conditions")

    print("4. Reading it back")
    events = db.fetch_events(participant)
    _check("every event returned", len(events) == written, f"{len(events)} of {written}")
    _check("schema version recorded", {e["schema_version"] for e in events} == {SCHEMA_VERSION})
    _check("both conditions present", {e["condition"] for e in events} == {"static", "interactive"})
    _check("both condition orders present", {e["condition_order"] for e in events} == {1, 2})
    _check("events are ordered", [e["id"] for e in events] == sorted(e["id"] for e in events))

    _check("both forms present", {e["form"] for e in events} == {"A", "B"})

    answers = [e for e in events if e["event"] == "answer_submit"]
    _check("answers recorded", len(answers) == 2, f"found {len(answers)}")
    _check(
        "nested JSONB answer survived",
        all(a["payload"]["answer"] == {"choice": "Nigeria", "confidence": 4} for a in answers),
    )
    _check("answers attributed to their task", all(a["task_id"] == "T1" for a in answers))
    _check(
        "justification survived",
        all(a["payload"]["justification"].startswith("Its line fell") for a in answers),
    )

    ratings = [e for e in events if e["event"] == "load_rating"]
    _check("one load rating per condition", len(ratings) == 2, f"found {len(ratings)}")
    _check(
        "Paas rating survived",
        all(r["payload"] == {"scale": "paas", "value": 7} for r in ratings),
    )

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

    consents = [e for e in events if e["event"] == "consent"]
    _check("one consent record", len(consents) == 1, f"found {len(consents)}")
    _check(
        "consent keeps the browser timestamp",
        consents[0]["payload"]["consented_at"] == "2026-09-16T10:00:00.000Z",
    )
    uids = [e["event_uid"] for e in events]
    _check("every event has a uid", all(uids))
    _check("event uids are unique", len(set(uids)) == len(uids))

    print("5. Duplicate protection")
    duplicate = dict(next(e for e in events if e["event"] == "answer_submit"))
    duplicate["event_uid"] = str(uuid.uuid4())
    try:
        db.insert_event(duplicate)
    except db.TransientDatabaseError as exc:
        raise VerificationError(f"duplicate answer read as a connection failure: {exc}") from exc
    except db.DatabaseError:
        _check("a second answer for the same task is refused", True)
    else:
        raise VerificationError("the database accepted two answers for one task")
    replayed = db.insert_event(dict(events[0]), ignore_duplicates=True)
    _check("replaying an event that already landed writes nothing", replayed == 0)
    _check("still exactly the events written", len(db.fetch_events(participant)) == written)

    print("6. Cleanup")
    removed_events, removed_participants = db.delete_participant(participant)
    _check("events removed", removed_events == written, f"removed {removed_events}")
    _check("participant removed", removed_participants == 1)
    _check("nothing left behind", db.fetch_events(participant) == [])

    print("7. Timestamps")
    stamped = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
    record = {**dict(events[0]), "event_uid": str(uuid.uuid4()), "server_ts": stamped.isoformat()}
    record["event"] = "view_change"
    db.insert_event(record)
    (stored,) = db.fetch_events(participant)
    _check(
        "server_ts is the record's own time, not the insert time",
        stored["server_ts"] == stamped,
        f"stored {stored['server_ts'].isoformat()} -- a replayed event would carry its replay time",
    )


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
