"""Tests for the database layer, without a database.

No SQL in `src/db.py` has been executed against a real Neon instance by this suite, and these tests
do not pretend otherwise -- `scripts/verify_deployment.py` is what does that. What they guard is the
logic around the SQL that would silently corrupt the study data if it drifted:

- a connection failure classified as permanent (spooled after one try, where a retry would have
  saved it), or a constraint violation classified as transient (retried inside a task window);
- a column written by the logger but absent from the table definition;
- a column added to the table definition but never migrated onto an existing table, where
  `CREATE TABLE IF NOT EXISTS` quietly does nothing and every write of that column is lost.
"""

from __future__ import annotations

import re

import psycopg
import pytest

from src import db
from src.logging import StudyLogger


@pytest.fixture
def url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")


class FakeConnection:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.statements: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.error is not None:
            raise self.error
        self.statements.append((sql, params))
        return self

    rowcount = 1


def _patch_connect(monkeypatch, connection=None, error=None):
    captured: dict = {}

    def fake_connect(dsn, **kwargs):
        captured.update(kwargs)
        if error is not None:
            raise error
        return connection

    monkeypatch.setattr(db.psycopg, "connect", fake_connect)
    return captured


# --- Failure classification --------------------------------------------------------------------


def test_a_transient_error_is_still_a_database_error():
    """Every existing `except DatabaseError` must keep catching connection failures."""
    assert issubclass(db.TransientDatabaseError, db.DatabaseError)


@pytest.mark.parametrize(
    "error",
    [psycopg.OperationalError("could not connect"), psycopg.InterfaceError("connection closed")],
)
def test_connection_failures_are_transient(url, monkeypatch, error):
    _patch_connect(monkeypatch, error=error)
    with pytest.raises(db.TransientDatabaseError), db.connect():
        pass


def test_a_connect_timeout_is_transient(url, monkeypatch):
    """A suspended Neon compute shows up as exactly this. It is the case retrying exists for."""
    _patch_connect(monkeypatch, error=psycopg.errors.ConnectionTimeout("timeout expired"))
    with pytest.raises(db.TransientDatabaseError), db.connect():
        pass


def test_a_constraint_violation_is_not_transient(url, monkeypatch):
    """Retrying a duplicate answer only spends the retry budget before the same failure."""
    _patch_connect(monkeypatch, FakeConnection(psycopg.IntegrityError("duplicate key")))
    with pytest.raises(db.DatabaseError) as raised:
        db.insert_event({"payload": {}})
    assert not isinstance(raised.value, db.TransientDatabaseError)


def test_no_url_is_a_permanent_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(db.DatabaseError) as raised, db.connect():
        pass
    assert not isinstance(raised.value, db.TransientDatabaseError)


# --- Timeouts ----------------------------------------------------------------------------------


def test_event_writes_use_the_short_connect_timeout(url, monkeypatch):
    """Three attempts at the 10 s default would exceed vercel.json's 30 s maxDuration."""
    captured = _patch_connect(monkeypatch, FakeConnection())
    db.insert_event({"payload": {}})
    assert captured["connect_timeout"] == db.EVENT_CONNECT_TIMEOUT


def test_the_event_timeout_fits_the_function_budget():
    from src.logging import FULL

    worst_case = FULL.attempts * db.EVENT_CONNECT_TIMEOUT + FULL.max_delay_s * (FULL.attempts - 1)
    assert worst_case < 30, "a full retry must finish inside vercel.json's maxDuration"


def test_assignment_uses_the_short_connect_timeout(url, monkeypatch):
    """A participant waits on the ID screen while this runs, and it is retried."""

    class Returning(FakeConnection):
        def fetchone(self):
            return (1,)

    captured = _patch_connect(monkeypatch, Returning())
    db.register_participant("P01")
    assert captured["connect_timeout"] == db.EVENT_CONNECT_TIMEOUT


class Registry(FakeConnection):
    """Answers the participant lookup and insert like Postgres would, counting sequence draws."""

    def __init__(self, known: dict[str, int] | None = None, race: bool = False):
        super().__init__()
        self.known = dict(known or {})
        self.next_seq = max(self.known.values(), default=0) + 1
        self.race = race
        self._row = None

    def execute(self, sql, params=None):
        super().execute(sql, params)
        (participant_id,) = params
        if sql.startswith("SELECT"):
            self._row = (self.known[participant_id],) if participant_id in self.known else None
        else:
            # Postgres draws nextval before it checks the conflict: a conflicting insert burns one.
            seq, self.next_seq = self.next_seq, self.next_seq + 1
            if self.race:
                self.known[participant_id] = 99  # a concurrent request got there first
                self._row = None
            elif participant_id in self.known:
                self._row = None
            else:
                self.known[participant_id] = seq
                self._row = (seq,)
        return self

    def fetchone(self):
        return self._row


def test_a_known_participant_is_looked_up_not_inserted(url, monkeypatch):
    """Inserting a known ID burned a sequence number and skipped the next participant's cell."""
    registry = Registry(known={"P01": 5})
    _patch_connect(monkeypatch, registry)
    assert db.register_participant("P01") == (5, *db.assignment_for(5))
    assert not [sql for sql, _ in registry.statements if sql.startswith("INSERT")]
    assert registry.next_seq == 6, "a repeat registration must not draw from the sequence"


def test_repeat_registrations_leave_the_next_participant_consecutive(url, monkeypatch):
    registry = Registry()
    _patch_connect(monkeypatch, registry)
    first = db.register_participant("P01")
    db.register_participant("P01")
    db.register_participant("P01")
    second = db.register_participant("P02")
    assert (first[0], second[0]) == (1, 2)


def test_a_concurrent_registration_of_the_same_id_is_read_back(url, monkeypatch):
    registry = Registry(race=True)
    _patch_connect(monkeypatch, registry)
    assert db.register_participant("P01") == (99, *db.assignment_for(99))


def test_timeouts_are_whole_seconds():
    """libpq parses connect_timeout as an integer."""
    assert isinstance(db.EVENT_CONNECT_TIMEOUT, int)


# --- Inserts -----------------------------------------------------------------------------------


def test_insert_event_writes_every_declared_column(url, monkeypatch):
    connection = FakeConnection()
    _patch_connect(monkeypatch, connection)
    record = {column: f"value-{column}" for column in db.EVENT_COLUMNS}
    record["payload"] = {"answer": "1"}
    db.insert_event(record)

    ((sql, params),) = connection.statements
    for column in db.EVENT_COLUMNS:
        assert column in sql
    assert params[db.EVENT_COLUMNS.index("event_uid")] == "value-event_uid"
    assert params[-1].obj == {"answer": "1"}, "payload must be wrapped as JSONB"


def test_server_ts_is_the_records_own_time_with_now_as_the_fallback(url, monkeypatch):
    """A spooled event replayed later must keep the time it happened, not take the replay time."""
    connection = FakeConnection()
    _patch_connect(monkeypatch, connection)
    db.insert_event({"server_ts": "2026-09-16T10:00:00+00:00", "payload": {}})

    ((sql, params),) = connection.statements
    assert "server_ts" in db.EVENT_COLUMNS
    assert params[db.EVENT_COLUMNS.index("server_ts")] == "2026-09-16T10:00:00+00:00"
    # A record without a time must not violate NOT NULL; it falls back to the insert time.
    assert "COALESCE(%s::timestamptz, now())" in sql
    assert sql.count("%s") == len(db.EVENT_COLUMNS)


def test_live_inserts_do_not_swallow_conflicts(url, monkeypatch):
    """During a session a conflict is a fault to see, not to hide."""
    connection = FakeConnection()
    _patch_connect(monkeypatch, connection)
    db.insert_event({"payload": {}})
    assert "ON CONFLICT" not in connection.statements[0][0]


def test_replayed_inserts_ignore_conflicts(url, monkeypatch):
    connection = FakeConnection()
    _patch_connect(monkeypatch, connection)
    db.insert_event({"payload": {}}, ignore_duplicates=True)
    assert connection.statements[0][0].endswith("ON CONFLICT DO NOTHING")


# --- The schema --------------------------------------------------------------------------------

# The columns study_events had when schema v3 was the latest. Any column added since must be
# migrated onto an existing table explicitly -- see test_every_new_column_has_an_explicit_migration.
V3_COLUMNS = {
    "id",
    "schema_version",
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
}


def _table_columns(table: str) -> set[str]:
    body = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);", db.SCHEMA_SQL, flags=re.DOTALL
    )
    assert body, f"no CREATE TABLE for {table}"
    return {line.split()[0] for line in body.group(1).splitlines() if line.strip()}


def test_event_columns_match_the_declared_table():
    assert set(db.EVENT_COLUMNS) <= _table_columns("study_events")


def test_every_new_column_has_an_explicit_migration():
    """CREATE TABLE IF NOT EXISTS is a no-op on a table that already exists. A column that is only
    in the definition is silently absent from any database created before it was added."""
    for column in _table_columns("study_events") - V3_COLUMNS:
        assert f"ADD COLUMN IF NOT EXISTS {column} " in db.SCHEMA_SQL, (
            f"{column} is not migrated onto existing tables"
        )


def test_the_answer_uniqueness_index_is_declared():
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON study_events \(session_id, task_id\)\s+"
        r"WHERE event = 'answer_submit'",
        db.SCHEMA_SQL,
    )


def test_event_uids_are_unique():
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON study_events \(event_uid\)", db.SCHEMA_SQL
    )


def test_the_migration_runs_before_the_index_that_needs_it():
    assert db.SCHEMA_SQL.index("ADD COLUMN IF NOT EXISTS event_uid") < db.SCHEMA_SQL.index(
        "ON study_events (event_uid)"
    )


def test_the_logger_produces_every_column_the_table_stores(tmp_path, monkeypatch):
    """A column in EVENT_COLUMNS the logger never sets would be written as NULL on every row."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with StudyLogger("P07", condition_order=1, interactive=True, log_dir=tmp_path) as log:
        record = log.event("line_isolate", entity="Brazil", isolated=True)
    assert set(db.EVENT_COLUMNS) <= set(record)
    assert record["event_uid"]
