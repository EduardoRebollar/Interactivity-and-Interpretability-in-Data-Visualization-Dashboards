"""The consent form, the signed record, and the two scripts that handle it afterwards.

The consent text is the form submitted to HSRRC (`irb/COMP 490 Consent Form.pdf`, local only). Its
hash is pinned here: a change to the wording must be deliberate, and must be matched by the form
HSRRC approves. Update the pinned hash only together with the approved document.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts import export_consents, withdraw_participant
from src import consent
from src import logging as study_logging

SIGNATURE = [[[10 + 3 * i, 50 + (i % 4)] for i in range(15)]]


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)


def _record(**overrides):
    fields = {"name": "Ada Example", "date": "2026-09-21", "signature": SIGNATURE, "paper": False}
    fields.update(overrides)
    return consent.build_record(
        "2026-09-21T17:00:00.000Z",
        fields["name"],
        fields["date"],
        fields["signature"],
        fields["paper"],
    )


# --- The text ------------------------------------------------------------------------------------


def test_the_consent_text_is_pinned():
    """Changing the wording changes CONSENT_VERSION. It must match the HSRRC-approved form."""
    assert consent.CONSENT_VERSION == "dc272a0a5568629c"


@pytest.mark.parametrize(
    "phrase",
    [
        "You must be at least 18 years of age",
        "You may skip any question you do not wish to answer.",
        "You will not be paid for participating in this study.",
        "rebollar@oxy.edu",
        "camarilloabad@oxy.edu",
        "hsrrc@oxy.edu",
        "I hereby agree to participate in this research project.",
        "The order in which you see the two versions will be counterbalanced.",
        "up to two weeks after your session by emailing me at rebollar@oxy.edu",
        "encrypted Neon (managed by PostgreSQL) database hosted in the U.S.",
    ],
)
def test_the_form_says_what_the_irb_submission_says(phrase):
    assert phrase in consent.CONSENT_TEXT


def test_the_approval_flag_is_not_part_of_the_hash():
    """Approving the form must not change CONSENT_VERSION, or pre- and post-approval data split."""
    assert "PENDING" not in consent.CONSENT_TEXT


# --- The signed record ---------------------------------------------------------------------------


def test_a_complete_record_has_no_problem():
    assert consent.problem(_record()) is None


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"name": ""}, "full name"),
        ({"name": "x" * 300}, "too long"),
        ({"date": ""}, "date"),
        ({"signature": None}, "sign in the box"),
        ({"signature": [[[1, 2]]]}, "sign in the box"),
        ({"signature": "a picture"}, "could not be read"),
        ({"signature": [[[1, 2, 3]] * 20]}, "could not be read"),
        ({"signature": [[[float("nan"), 1]] * 20]}, "could not be read"),
        ({"signature": [[[1, 1]] * (consent.MAX_POINTS + 1)]}, "could not be read"),
    ],
)
def test_an_incomplete_record_names_what_is_missing(overrides, expected):
    assert expected in consent.problem(_record(**overrides))


def test_a_paper_signature_needs_no_drawing_and_keeps_none():
    record = _record(signature=SIGNATURE, paper=True)
    assert consent.problem(record) is None
    assert record["signature_method"] == "paper"
    assert record["signature"] is None, "a drawing does not belong beside a paper signature"


def test_a_record_carries_no_participant_id():
    """IRB form items 15 and 17: it must not be joinable to the study data."""
    assert "participant_id" not in _record()


def test_saving_locally_keeps_consent_apart_from_the_study_logs(tmp_path):
    consent.save(_record(), tmp_path / "consent")
    assert [r["printed_name"] for r in consent.read_local(tmp_path / "consent")] == ["Ada Example"]
    assert not list(tmp_path.glob("*.jsonl")), "nothing beside the study log files"


def test_an_incomplete_record_is_never_stored(tmp_path):
    with pytest.raises(consent.ConsentError):
        consent.save(_record(name=""), tmp_path)
    assert consent.read_local(tmp_path) == []


def test_a_deployment_without_a_database_refuses_to_store_consent(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(consent.ConsentError, match="DATABASE_URL"):
        consent.save(_record())


def test_the_signed_copy_carries_the_text_the_name_and_the_signature():
    copy = consent.copy_html(_record())
    assert "Ada Example" in copy
    assert "<svg" in copy and "<polyline" in copy
    assert "Researcher or research assistant signature" in copy
    assert "I hereby agree to participate" in copy


def test_the_signed_copy_escapes_what_the_participant_typed():
    copy = consent.copy_html(_record(name="<script>alert(1)</script>"))
    assert "<script>alert" not in copy
    assert "&lt;script&gt;" in copy


def test_a_paper_copy_says_it_was_signed_on_paper():
    assert "paper copy" in consent.copy_html(_record(paper=True))


# --- scripts/export_consents.py ------------------------------------------------------------------


def test_export_writes_a_copy_per_record_and_purges_only_what_it_wrote(tmp_path):
    store = tmp_path / "consent"
    first, second = _record(name="First Person"), _record(name="Second Person")
    consent.save(first, store)
    consent.save(second, store)

    out = tmp_path / "export"
    assert export_consents.main(["--local-dir", str(store), "--out", str(out), "--purge"]) == 0

    copies = sorted(out.glob("*.html"))
    assert len(copies) == 2
    assert all("Person" not in path.name for path in copies), "no name in a file name"
    text = "".join(path.read_text(encoding="utf-8") for path in copies)
    assert "First Person" in text and "Second Person" in text
    assert consent.read_local(store) == [], "exported records are purged"


def test_export_without_purge_keeps_the_records(tmp_path):
    store = tmp_path / "consent"
    consent.save(_record(), store)
    export_consents.main(["--local-dir", str(store), "--out", str(tmp_path / "export")])
    assert len(consent.read_local(store)) == 1


# --- scripts/withdraw_participant.py -------------------------------------------------------------


def _session(log_dir, participant_id, days_ago=0):
    """A minimal logged session for one participant, stamped `days_ago`."""
    logger = study_logging.StudyLogger(
        participant_id, condition_order=1, interactive=False, form="A", log_dir=log_dir
    )
    logger.event("condition_start", interactive=False, condition_order=1)
    logger.close()
    if days_ago:
        stamp = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
        for path in log_dir.glob(f"{participant_id}_*.jsonl"):
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            for record in records:
                record["server_ts"] = stamp
            path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def _withdraw(tmp_path, *args):
    logs, spool = tmp_path / "logs", tmp_path / "spool"
    return withdraw_participant.main([*args, "--log-dir", str(logs), "--spool-dir", str(spool)])


def test_withdrawal_is_a_dry_run_by_default(tmp_path):
    _session(tmp_path / "logs", "P07")
    assert _withdraw(tmp_path, "P07") == 0
    assert list((tmp_path / "logs").glob("P07_*.jsonl")), "a dry run removes nothing"


def test_withdrawal_removes_that_participant_and_nobody_else(tmp_path):
    _session(tmp_path / "logs", "P07")
    _session(tmp_path / "logs", "P08")
    spool = tmp_path / "spool"
    spool.mkdir()
    envelope = {"spooled_at": "t", "record": {"participant_id": "P07", "event": "task_start"}}
    (spool / "P07_static_abc.spool.jsonl").write_text(json.dumps(envelope) + "\n")

    assert _withdraw(tmp_path, "P07", "--apply") == 0
    assert not list((tmp_path / "logs").glob("P07_*.jsonl"))
    assert not list(spool.glob("P07_*")), "a spool copy could otherwise be replayed back"
    assert list((tmp_path / "logs").glob("P08_*.jsonl")), "another participant is untouched"


def test_withdrawal_past_two_weeks_needs_late(tmp_path):
    _session(tmp_path / "logs", "P07", days_ago=20)
    assert _withdraw(tmp_path, "P07", "--apply") == 1
    assert list((tmp_path / "logs").glob("P07_*.jsonl")), "refused, so nothing removed"
    assert _withdraw(tmp_path, "P07", "--apply", "--late") == 0
    assert not list((tmp_path / "logs").glob("P07_*.jsonl"))


def test_withdrawing_an_unknown_id_says_so(tmp_path):
    (tmp_path / "logs").mkdir()
    assert _withdraw(tmp_path, "P99") == 1


def test_a_file_mixing_participants_is_never_deleted(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    mixed = [{"participant_id": "P07"}, {"participant_id": "P08"}]
    (logs / "odd.jsonl").write_text("".join(json.dumps(r) + "\n" for r in mixed))
    with pytest.raises(SystemExit, match="other participants"):
        _withdraw(tmp_path, "P07", "--apply")
    assert (logs / "odd.jsonl").exists()
