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

CREATE INDEX IF NOT EXISTS study_events_participant_idx
    ON study_events (participant_id, condition, id);
CREATE INDEX IF NOT EXISTS study_events_session_idx
    ON study_events (session_id, id);
"""

EVENT_COLUMNS = (
    "schema_version",
    "session_id",
    "participant_id",
    "condition",
    "condition_order",
    "form",
    "task_id",
    "event",
    "client_elapsed_ms",
    "task_elapsed_ms",
    "server_elapsed_ms",
    "payload",
)


class DatabaseError(RuntimeError):
    """Raised when the database is unreachable or not configured."""


def database_url() -> str | None:
    """The configured connection string, or None when running without a database."""
    return os.environ.get("DATABASE_URL") or None


def configured() -> bool:
    """True when a database is available. Drives sink selection in src/logging.py."""
    return database_url() is not None


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """Open a connection for one operation, committing on success."""
    dsn = database_url()
    if dsn is None:
        raise DatabaseError("DATABASE_URL is not set")
    try:
        with psycopg.connect(dsn, connect_timeout=10) as connection:
            yield connection
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


def register_participant(participant_id: str) -> tuple[int, str, str]:
    """Return (seq, first_condition, first_form), assigning on first sight.

    Idempotent: calling again for a known participant returns the same assignment, so someone who
    reloads or returns for their second condition is never re-randomised.
    """
    with connect() as connection:
        row = connection.execute(
            "INSERT INTO participants (participant_id) VALUES (%s) "
            "ON CONFLICT (participant_id) DO NOTHING RETURNING seq",
            (participant_id,),
        ).fetchone()

        if row is None:
            # Already registered: read the assignment made the first time.
            row = connection.execute(
                "SELECT seq FROM participants WHERE participant_id = %s",
                (participant_id,),
            ).fetchone()
            if row is None:
                raise DatabaseError(f"Could not register or find participant {participant_id!r}")

        seq = int(row[0])
        condition, form = assignment_for(seq)
        return seq, condition, form


def insert_event(record: dict[str, Any]) -> None:
    """Write one event row. `record` uses the keys in EVENT_COLUMNS."""
    values = [record.get(column) for column in EVENT_COLUMNS]
    values[-1] = Json(record.get("payload") or {})
    placeholders = ", ".join(["%s"] * len(EVENT_COLUMNS))
    with connect() as connection:
        connection.execute(
            f"INSERT INTO study_events ({', '.join(EVENT_COLUMNS)}) VALUES ({placeholders})",
            values,
        )


def fetch_events(participant_id: str | None = None) -> list[dict[str, Any]]:
    """Read events back, oldest first. For `scripts/export_logs.py` and for verification."""
    query = (
        "SELECT id, schema_version, session_id, participant_id, condition, condition_order, form, "
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
