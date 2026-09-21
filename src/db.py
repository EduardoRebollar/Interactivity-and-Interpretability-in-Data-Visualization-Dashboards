"""Neon Postgres access for study data. Stdlib + psycopg only, no pandas.

Vercel's filesystem is ephemeral and read-only outside `/tmp`, so the JSONL sink cannot persist a
deployed session. This module is where the study data actually survives.

Connection policy: connect per operation rather than holding a module-level connection. Serverless
containers are frozen and resumed unpredictably, so a cached socket is likely to be dead when it is
next used. Point `DATABASE_URL` at Neon's **pooled** endpoint so the churn is absorbed by pgbouncer.

`DATABASE_URL` is a secret and this repo is public: Vercel environment variables only.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.types.json import Json

# Participants are assigned an order from a sequence rather than from count(*): a count read is
# racy under concurrent starts and could give two participants the same first condition.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS participants (
    participant_id  TEXT PRIMARY KEY,
    seq             BIGSERIAL NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS study_events (
    id                 BIGSERIAL PRIMARY KEY,
    schema_version     INTEGER NOT NULL,
    event_uid          UUID,
    session_id         UUID NOT NULL,
    participant_id     TEXT NOT NULL,
    condition          TEXT NOT NULL CHECK (condition IN ('static', 'interactive')),
    condition_order    INTEGER NOT NULL CHECK (condition_order IN (1, 2)),
    form               TEXT CHECK (form IN ('A', 'B')),
    task_id            TEXT,
    event              TEXT NOT NULL,
    server_ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_elapsed_ms  DOUBLE PRECISION,
    task_elapsed_ms    DOUBLE PRECISION,
    server_elapsed_ms  DOUBLE PRECISION,
    payload            JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- v4 columns, added explicitly. CREATE TABLE IF NOT EXISTS is a no-op on a table that already
-- exists, so a column added to the definition above would be SILENTLY ABSENT on any database
-- created before v4 -- and every write of it would be quietly dropped.
ALTER TABLE study_events ADD COLUMN IF NOT EXISTS event_uid UUID;

CREATE INDEX IF NOT EXISTS study_events_participant_idx
    ON study_events (participant_id, condition, id);
CREATE INDEX IF NOT EXISTS study_events_session_idx
    ON study_events (session_id, id);

-- Replaying a spooled event must not double-insert it. The uid is generated once, when the record
-- is built, so a retry and a replay of the same event carry the same uid.
CREATE UNIQUE INDEX IF NOT EXISTS study_events_event_uid_idx
    ON study_events (event_uid) WHERE event_uid IS NOT NULL;

-- One task, one answer -- enforced here and not only in the app, because the app's guard lives in
-- browser session state and a second tab has its own. A duplicate would also skip the next task.
CREATE UNIQUE INDEX IF NOT EXISTS study_events_one_answer_per_task
    ON study_events (session_id, task_id) WHERE event = 'answer_submit';

-- v6: a withdrawn participant keeps their registration row -- so the counterbalancing cell counts
-- stay explainable and the ID cannot be reused -- but loses every event. See withdraw_participant.
ALTER TABLE participants ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMPTZ;

-- v6: signed consent. NO participant_id, deliberately: IRB form items 15 and 17 require signed
-- consent and identifying information to be kept apart from the study data, so this table cannot
-- be joined to study_events through any key. Exported and purged by scripts/export_consents.py.
CREATE TABLE IF NOT EXISTS consent_records (
    id                BIGSERIAL PRIMARY KEY,
    record_uid        UUID NOT NULL UNIQUE,
    consent_version   TEXT NOT NULL,
    consented_at      TEXT NOT NULL,
    printed_name      TEXT NOT NULL,
    signed_date       TEXT NOT NULL,
    signature_method  TEXT NOT NULL CHECK (signature_method IN ('drawn', 'paper')),
    signature         JSONB,
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CONSENT_COLUMNS = (
    "record_uid",
    "consent_version",
    "consented_at",
    "printed_name",
    "signed_date",
    "signature_method",
    "signature",
    "received_at",
)

EVENT_COLUMNS = (
    "schema_version",
    "event_uid",
    "session_id",
    "participant_id",
    "condition",
    "condition_order",
    "form",
    "task_id",
    "event",
    "server_ts",
    "client_elapsed_ms",
    "task_elapsed_ms",
    "server_elapsed_ms",
    "payload",
)

# Calls made inside a participant's request -- event writes and assignment -- get a shorter connect
# timeout than the default. A retry budget is wall-clock, and
# vercel.json pins maxDuration to 30s: three attempts at a 10s connect timeout would blow it and the
# function would be killed before the retry helped. A pooled Neon endpoint that has not answered in
# 5s will not answer in 10.
EVENT_CONNECT_TIMEOUT = 5


class DatabaseError(RuntimeError):
    """Raised when the database is unreachable or not configured."""


class TransientDatabaseError(DatabaseError):
    """A connection-level failure a retry may fix: a suspended Neon compute, a dropped socket.

    Subclasses DatabaseError, so existing `except DatabaseError` handlers keep catching both. The
    distinction exists for the retry loop in src/logging.py: retrying a constraint violation three
    times before spooling it would turn a code bug into silent data loss, and would spend the retry
    budget inside a participant's measured task window to do it.
    """


class WithdrawnParticipantError(DatabaseError):
    """The ID belongs to a participant who withdrew. It must not start a new session.

    A DatabaseError so existing handlers still catch it, but never transient: retrying cannot help.
    """


def database_url() -> str | None:
    """The configured connection string, or None when running without a database."""
    return os.environ.get("DATABASE_URL") or None


def configured() -> bool:
    """True when a database is available. Drives sink selection in src/logging.py."""
    return database_url() is not None


@contextmanager
def connect(timeout: int = 10) -> Iterator[psycopg.Connection]:
    """Open a connection for one operation, committing on success.

    `timeout` is the connect timeout in whole seconds (libpq parses the option as an integer). It
    is the real bound on any retry loop -- see EVENT_CONNECT_TIMEOUT -- so it is a parameter.

    Connection-level failures are raised as TransientDatabaseError so a caller can tell "Neon is
    asleep" from "that INSERT violates a constraint"; everything else is a plain DatabaseError.
    """
    dsn = database_url()
    if dsn is None:
        raise DatabaseError("DATABASE_URL is not set")
    try:
        with psycopg.connect(dsn, connect_timeout=timeout) as connection:
            yield connection
    except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
        raise TransientDatabaseError(f"Database unreachable: {exc}") from exc
    except psycopg.Error as exc:
        raise DatabaseError(f"Database operation failed: {exc}") from exc


def init_schema() -> None:
    """Create tables and indexes if absent. Safe to run repeatedly."""
    with connect() as connection:
        connection.execute(SCHEMA_SQL)


# 2x2 counterbalancing: condition order crossed with form order. Indexed by seq % 4, so the four
# cells fill evenly as participants arrive. See docs/study-design.md section 2.
ASSIGNMENTS: dict[int, tuple[str, str]] = {
    1: ("static", "A"),
    2: ("interactive", "A"),
    3: ("static", "B"),
    0: ("interactive", "B"),
}


def assignment_for(seq: int) -> tuple[str, str]:
    """Return (first_condition, first_form) for a sequence number.

    Pure, so the rule is testable without a database. The second condition and second form are
    always the opposites — every participant sees both conditions and both forms, never a form
    twice, which is what stops them answering the same question with the answer already known.
    """
    return ASSIGNMENTS[seq % 4]


_FIND_PARTICIPANT = "SELECT seq, withdrawn_at FROM participants WHERE participant_id = %s"


def register_participant(participant_id: str) -> tuple[int, str, str]:
    """Return (seq, first_condition, first_form), assigning on first sight.

    Idempotent: calling again for a known participant returns the same assignment, so someone who
    reloads or returns for their second condition is never re-randomised.

    **Looks the ID up before inserting.** An `INSERT ... ON CONFLICT DO NOTHING` on its own draws
    the next sequence value before it detects the conflict, so every repeat registration -- a
    double-click on Continue, a returning participant -- burned a number and pushed the next new
    participant into the wrong counterbalancing cell. The insert remains the race-safe path for a
    genuinely new ID; only two people entering the same new ID at the same instant can still leave a
    gap, and they get one assignment between them.

    Uses the short connect timeout: a participant is waiting on the ID screen while this runs.
    """
    with connect(timeout=EVENT_CONNECT_TIMEOUT) as connection:
        row = connection.execute(_FIND_PARTICIPANT, (participant_id,)).fetchone()

        if row is not None and row[1] is not None:
            raise WithdrawnParticipantError(f"Participant {participant_id!r} has withdrawn")

        if row is None:
            row = connection.execute(
                "INSERT INTO participants (participant_id) VALUES (%s) "
                "ON CONFLICT (participant_id) DO NOTHING RETURNING seq, NULL",
                (participant_id,),
            ).fetchone()

        if row is None:
            # Registered by a concurrent request between the lookup and the insert.
            row = connection.execute(_FIND_PARTICIPANT, (participant_id,)).fetchone()
            if row is None:
                raise DatabaseError(f"Could not register or find participant {participant_id!r}")

        seq = int(row[0])
        condition, form = assignment_for(seq)
        return seq, condition, form


def insert_event(record: dict[str, Any], *, ignore_duplicates: bool = False) -> int:
    """Write one event row. `record` uses the keys in EVENT_COLUMNS.

    `ignore_duplicates` adds ON CONFLICT DO NOTHING, for replaying a spool where an event may
    already have landed before the response was lost. Off by default: during a live session a
    conflict is a real fault and should be seen, not swallowed.

    `server_ts` is the time the logger created the record, not the time of this INSERT. Schema v5:
    before it, the column took the insert time, so an event spooled through an outage and replayed
    later carried the replay time -- and disagreed with the JSONL sink, which always kept the
    record's own. A record without one still gets `now()`.

    Returns the number of rows written: 0 means a replayed event was already present.
    """
    values = [record.get(column) for column in EVENT_COLUMNS]
    values[-1] = Json(record.get("payload") or {})
    placeholders = ", ".join(
        "COALESCE(%s::timestamptz, now())" if column == "server_ts" else "%s"
        for column in EVENT_COLUMNS
    )
    statement = f"INSERT INTO study_events ({', '.join(EVENT_COLUMNS)}) VALUES ({placeholders})"
    if ignore_duplicates:
        statement += " ON CONFLICT DO NOTHING"
    with connect(timeout=EVENT_CONNECT_TIMEOUT) as connection:
        return connection.execute(statement, values).rowcount


def fetch_events(participant_id: str | None = None) -> list[dict[str, Any]]:
    """Read events back, oldest first. For `scripts/export_logs.py` and for verification."""
    query = (
        "SELECT id, schema_version, event_uid, session_id, participant_id, condition, "
        "condition_order, form, "
        "task_id, event, server_ts, client_elapsed_ms, task_elapsed_ms, server_elapsed_ms, payload "
        "FROM study_events"
    )
    params: tuple[Any, ...] = ()
    if participant_id is not None:
        query += " WHERE participant_id = %s"
        params = (participant_id,)
    query += " ORDER BY id"

    with connect() as connection:
        cursor = connection.execute(query, params)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def fetch_participants() -> list[dict[str, Any]]:
    """Registered participants in assignment order. Read-only; for the local data viewer.

    A participant registered here with no events dropped out between the ID screen and the
    instructions, which the events table alone cannot show.
    """
    with connect() as connection:
        cursor = connection.execute(
            "SELECT participant_id, seq, created_at, withdrawn_at FROM participants ORDER BY seq"
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def participant_count() -> int:
    with connect() as connection:
        row = connection.execute("SELECT count(*) FROM participants").fetchone()
        return int(row[0]) if row else 0


def table_names() -> set[str]:
    """Tables present in the public schema. Used to verify `init_schema` actually ran."""
    with connect() as connection:
        rows = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        return {row[0] for row in rows}


def column_names(table: str) -> set[str]:
    """Columns present on a public table. Verifies a schema bump actually reached the database.

    `table_names` alone cannot catch a half-migrated database: CREATE TABLE IF NOT EXISTS succeeds
    on an old table without adding the new columns, so the table exists and the column does not.
    """
    with connect() as connection:
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        ).fetchall()
        return {row[0] for row in rows}


def insert_consent(record: dict[str, Any]) -> int:
    """Write one signed consent record (src/consent.py). Idempotent on `record_uid`.

    A retry after a lost response must not store the same signature twice, hence ON CONFLICT.
    """
    values = [record.get(column) for column in CONSENT_COLUMNS]
    values[CONSENT_COLUMNS.index("signature")] = Json(record.get("signature"))
    placeholders = ", ".join(
        "COALESCE(%s::timestamptz, now())" if column == "received_at" else "%s"
        for column in CONSENT_COLUMNS
    )
    statement = (
        f"INSERT INTO consent_records ({', '.join(CONSENT_COLUMNS)}) VALUES ({placeholders}) "
        "ON CONFLICT (record_uid) DO NOTHING"
    )
    with connect(timeout=EVENT_CONNECT_TIMEOUT) as connection:
        return connection.execute(statement, values).rowcount


def fetch_consents() -> list[dict[str, Any]]:
    """Every signed consent record, oldest first. For `scripts/export_consents.py` only."""
    with connect() as connection:
        cursor = connection.execute(
            f"SELECT {', '.join(CONSENT_COLUMNS)} FROM consent_records ORDER BY id"
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def delete_consents(record_uids: list[str]) -> int:
    """Delete consent records that have been exported. Returns the number removed.

    Called by `scripts/export_consents.py --purge` only after each record's copy is on disk, so the
    database copy is never the last one destroyed.
    """
    if not record_uids:
        return 0
    with connect() as connection:
        return connection.execute(
            "DELETE FROM consent_records WHERE record_uid = ANY(%s::uuid[])", (record_uids,)
        ).rowcount


def withdraw_participant(participant_id: str) -> int | None:
    """Delete a participant's events and mark them withdrawn. Returns events removed, or None.

    None means the ID was never registered. **This destroys study data**, and exists only for a
    participant exercising the two-week withdrawal right (IRB form item 13); see
    `scripts/withdraw_participant.py`. Unlike `delete_participant`, the registration row stays,
    stamped `withdrawn_at`, so the counterbalancing sequence stays explainable and
    `register_participant` refuses the ID from now on. One transaction: both happen or neither.
    """
    with connect() as connection:
        marked = connection.execute(
            "UPDATE participants SET withdrawn_at = COALESCE(withdrawn_at, now()) "
            "WHERE participant_id = %s",
            (participant_id,),
        ).rowcount
        if not marked:
            return None
        return connection.execute(
            "DELETE FROM study_events WHERE participant_id = %s", (participant_id,)
        ).rowcount


def delete_participant(participant_id: str) -> tuple[int, int]:
    """Delete one participant and all their events. Returns (events, participants) removed.

    **This destroys study data.** It exists so `scripts/verify_deployment.py` can clean up the
    synthetic session it writes, and so a participant who withdraws consent can be removed. It is
    never called by the app. Do not use it to tidy up data you merely find inconvenient.
    """
    with connect() as connection:
        events = connection.execute(
            "DELETE FROM study_events WHERE participant_id = %s", (participant_id,)
        ).rowcount
        participants = connection.execute(
            "DELETE FROM participants WHERE participant_id = %s", (participant_id,)
        ).rowcount
        return events, participants
