"""Tests for `scripts/recover_spool.py`.

Replay writes study data into the database, so the guarantees here are about not corrupting it:
nothing is written on a dry run, every event lands once and in order however often the script runs,
a spool from a different schema version is refused rather than pooled, and nothing is ever deleted.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src import db
from src import logging as study_logging

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "recover_spool.py"
_spec = importlib.util.spec_from_file_location("recover_spool", _SCRIPT)
recover_spool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recover_spool)


def _record(n: int, **overrides) -> dict:
    return {
        "schema_version": study_logging.SCHEMA_VERSION,
        "event_uid": f"uid-{n}",
        "session_id": "11111111-1111-1111-1111-111111111111",
        "participant_id": "P07",
        "condition": "static",
        "condition_order": 1,
        "form": "A",
        "task_id": "T1",
        "event": "answer_submit",
        "payload": {"answer": "1"},
        **overrides,
    }


def _spool(directory: Path, records: list[dict], name: str = "s") -> None:
    sink = study_logging.ResilientSink(
        _Refusing(),
        spool_path=directory / f"{name}.spool.jsonl",
        breaker=study_logging.CircuitBreaker(),
    )
    for record in records:
        sink.write(record)


class _Refusing:
    def write(self, record):
        raise db.DatabaseError("down")

    def close(self):
        pass


@pytest.fixture
def database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    stored: dict[str, dict] = {}
    order: list[str] = []

    def insert(record, *, ignore_duplicates=False):
        assert ignore_duplicates, "replay must never fail on an event that already landed"
        if record["event_uid"] in stored:
            return 0
        stored[record["event_uid"]] = record
        order.append(record["event_uid"])
        return 1

    monkeypatch.setattr(db, "insert_event", insert)
    return order


def test_a_dry_run_writes_nothing(tmp_path, database):
    _spool(tmp_path, [_record(1), _record(2)])
    assert recover_spool.main(["--spool-dir", str(tmp_path)]) == 0
    assert database == []
    assert list(tmp_path.glob("*.spool.jsonl")), "a dry run must not archive"


def test_apply_replays_in_order_and_archives(tmp_path, database):
    _spool(tmp_path, [_record(1), _record(2), _record(3)])
    assert recover_spool.main(["--spool-dir", str(tmp_path), "--apply"]) == 0
    assert database == ["uid-1", "uid-2", "uid-3"]
    assert not list(tmp_path.glob("*.spool.jsonl"))
    assert len(list(tmp_path.glob("*.recovered.jsonl"))) == 1, "renamed, never deleted"


def test_an_event_spooled_twice_is_replayed_once(tmp_path, database):
    _spool(tmp_path, [_record(1)], name="first-container")
    _spool(tmp_path, [_record(1), _record(2)], name="second-container")
    assert recover_spool.main(["--spool-dir", str(tmp_path), "--apply"]) == 0
    assert database == ["uid-1", "uid-2"]


def test_replaying_again_inserts_nothing_new(tmp_path, database):
    records = [_record(1), _record(2)]
    assert recover_spool.recover(records, apply=True) == (2, 0)
    assert recover_spool.recover(records, apply=True) == (0, 2)


def test_a_mixed_schema_spool_is_refused(tmp_path, database):
    _spool(tmp_path, [_record(1), _record(2, schema_version=3)])
    assert recover_spool.main(["--spool-dir", str(tmp_path), "--apply"]) == 1
    assert database == []


def test_a_record_without_a_uid_is_refused(tmp_path, database):
    """Without a uid, replay is not idempotent and a re-run would duplicate data."""
    _spool(tmp_path, [_record(1, event_uid=None)])
    assert recover_spool.main(["--spool-dir", str(tmp_path), "--apply"]) == 1
    assert database == []


def test_apply_without_a_database_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _spool(tmp_path, [_record(1)])
    assert recover_spool.main(["--spool-dir", str(tmp_path), "--apply"]) == 1
    assert list(tmp_path.glob("*.spool.jsonl"))


def test_a_failed_replay_archives_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")

    def unreachable(record, **kwargs):
        raise db.TransientDatabaseError("still down")

    monkeypatch.setattr(db, "insert_event", unreachable)
    _spool(tmp_path, [_record(1)])
    assert recover_spool.main(["--spool-dir", str(tmp_path), "--apply"]) == 1
    assert list(tmp_path.glob("*.spool.jsonl")), "the spool must survive a failed replay"


def test_a_missing_spool_directory_is_not_an_error(tmp_path):
    assert recover_spool.main(["--spool-dir", str(tmp_path / "absent")]) == 0
