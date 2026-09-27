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
    """Changing the wording changes CONSENT_VERSION. It must match the HSRRC-approved form.

    Re-pinned 2026-09-25 for the design handoff's screen 1 (docs/study-design.md section 9), and
    2026-09-26 for the sentence naming the background questions (section 10) and the revised
    form's straight apostrophe in "study's"."""
    assert consent.CONSENT_VERSION == "c56a88875374666a"


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
        "encrypted Neon (a managed PostgreSQL service) database hosted in the U.S.",
        # The 2026-09-25 revision (screen 1 of the design handoff).
        "willing to spend approximately 40 minutes viewing dashboards",
        "a single session lasting approximately 40 minutes.",
        "a topic that may be personally sensitive or evoke strong opinions for some participants",
        "Only the researcher and the faculty supervisor will have access to identifying data.",
        "The study's web application",
        # 2026-09-26: About you asks age, role and field, so the form says so (request item 17).
        "At the end of the session, you will be asked a few questions about your background, such "
        "as your age, your field of study or work, and your experience with charts.",
    ],
)
def test_the_form_says_what_the_irb_submission_says(phrase):
    assert phrase in consent.CONSENT_TEXT


@pytest.mark.parametrize(
    "phrase",
    ["20 to 35 minutes", "Neon (managed by PostgreSQL)", "will have access to the data."],
)
def test_the_superseded_wording_is_gone(phrase):
    """The 2026-09-21 transcription's words, replaced by screen 1 of the design handoff."""
    assert phrase not in consent.CONSENT_TEXT


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


def test_the_paper_box_alone_lets_the_participant_on():
    """The paper copy carries the name, the date and the signature (IRB form item 12A)."""
    record = _record(name="", date="", signature=None, paper=True)
    assert consent.problem(record) is None
    assert record["printed_name"] == "" and record["signed_date"] == ""
    typed = _record(name="Ada Example", date="2026-09-21", signature=None, paper=True)
    assert typed["printed_name"] == "Ada Example", "what was typed as well is kept"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"name": "x" * 300}, "too long"),
        ({"name": ""}, None),
    ],
)
def test_a_paper_record_still_needs_a_time_and_a_sane_name(overrides, expected):
    record = _record(signature=None, paper=True, **overrides)
    found = consent.problem(record)
    assert found is None if expected is None else expected in found
    record["consented_at"] = None
    assert "press the button again" in consent.problem(record)


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


def test_the_exported_copy_is_the_participant_s_sheet_in_the_app_s_styles(monkeypatch):
    """The Oxy Drive copy is the sheet the participant's PDF is made from, with the same
    countersignature, dated the day they agreed, in this computer's time zone."""
    from src import layout

    image = "data:image/png;base64,iVBORw0KGgo="
    monkeypatch.setenv(consent.SIGNATURE_ENV, image)
    record = _record()
    copy = export_consents.document(record)
    date = export_consents.countersign_date(record)
    assert layout.signed_sheet_html(record, date) in copy
    assert f'<span id="countersign-date" class="sheet-counter-line">{date}</span>' in copy
    assert f'<img src="{image}"' in copy
    for sheet in export_consents.STYLESHEETS:
        assert sheet.read_text(encoding="utf-8") in copy
    assert "@page { size: letter;" in copy


def test_the_exported_copy_escapes_what_the_participant_typed(monkeypatch):
    monkeypatch.delenv(consent.SIGNATURE_ENV, raising=False)
    copy = export_consents.document(_record(name="<script>alert(1)</script>"))
    assert "<script>alert" not in copy and "&lt;script&gt;" in copy


def test_the_countersignature_is_dated_the_day_the_participant_agreed():
    from datetime import datetime

    record = _record()
    agreed = datetime.fromisoformat("2026-09-21T17:00:00+00:00").astimezone()
    assert export_consents.countersign_date(record) == agreed.strftime("%m/%d/%Y")
    record["consented_at"] = "not a time"
    assert export_consents.countersign_date(record) == "09/21/2026"


def test_export_says_when_the_researcher_s_line_will_be_blank(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(consent.SIGNATURE_ENV, raising=False)
    store = tmp_path / "consent"
    consent.save(_record(), store)
    export_consents.main(["--local-dir", str(store), "--out", str(tmp_path / "export")])
    assert f"{consent.SIGNATURE_ENV} is not set" in capsys.readouterr().out


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


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "iVBORw0KGgo=",
        "data:image/png;base64,",
        "data:image/png;base64,not base64!",
        "data:image/svg+xml;base64,PHN2Zz4=",
        "data:image/png;base64," + "A" * consent.MAX_SIGNATURE,
    ],
)
def test_the_countersignature_refuses_anything_but_a_png_uri(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(consent.SIGNATURE_ENV, raising=False)
    else:
        monkeypatch.setenv(consent.SIGNATURE_ENV, value)
    assert consent.researcher_signature() is None


def test_the_countersignature_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv(consent.SIGNATURE_ENV, " data:image/png;base64,iVBORw0KGgo= ")
    assert consent.researcher_signature() == "data:image/png;base64,iVBORw0KGgo="


# --- The participant's PDF copy ----------------------------------------------------------------


def _sheet(monkeypatch, signature=None, **overrides):
    from src import layout

    if signature is None:
        monkeypatch.delenv(consent.SIGNATURE_ENV, raising=False)
    else:
        monkeypatch.setenv(consent.SIGNATURE_ENV, signature)
    return layout.signed_sheet_html(_record(**overrides))


def test_the_pdf_copy_is_the_screen_s_sheet_filled_in(monkeypatch):
    """The form's text is the screen's own components, so the copy cannot word or order it
    differently; then the participant's fields as stored, and the researcher's line."""
    from src import layout

    sheet = _sheet(monkeypatch)
    assert sheet.startswith('<article class="sheet sheet--form">')
    assert layout._markup(layout.consent_sheet_text()) in sheet
    assert "<svg" in sheet and "09/21/2026" in sheet and "Ada Example" in sheet
    order = [
        consent.SECTIONS[-1][1],
        "09/21/2026",
        "Ada Example",
        layout.SIGNOFF_LABEL,
        layout.COUNTERSIGN_LABEL,
        "Agreed electronically at 2026-09-21T17:00:00.000Z (UTC)",
    ]
    positions = [sheet.index(text) for text in order]
    assert positions == sorted(positions)


def test_the_pdf_copy_escapes_what_the_participant_typed(monkeypatch):
    sheet = _sheet(monkeypatch, name="<script>alert(1)</script>", date="<b>")
    assert "<script>" not in sheet and "&lt;script&gt;" in sheet
    assert "<b></div>" not in sheet


def test_the_pdf_copy_of_a_paper_signature_says_so(monkeypatch):
    from src import layout

    sheet = _sheet(monkeypatch, paper=True)
    assert layout.PAPER_SIGNED in sheet and "<svg" not in sheet


def test_the_pdf_copy_carries_the_countersignature_the_screen_shows(monkeypatch):
    from src import layout

    image = "data:image/png;base64,iVBORw0KGgo="
    signed = _sheet(monkeypatch, signature=image)
    assert f'<img src="{image}"' in signed and 'id="countersign-date"' in signed
    assert f">{consent.INVESTIGATOR}</span>" in signed
    blank = _sheet(monkeypatch)
    assert layout.COUNTERSIGN_RULE in blank and "<img" not in blank


def test_markup_writes_void_elements_and_escapes_attributes():
    from dash import html

    from src import layout

    assert layout._markup(html.P([html.Br(), "a & b"], className='x"y')) == (
        '<p class="x&quot;y"><br>a &amp; b</p>'
    )
    assert layout._markup(html.Img(src="s", alt="<a>")) == '<img src="s" alt="&lt;a&gt;">'


def test_the_vendored_pdf_libraries_are_the_pinned_files():
    import hashlib

    from scripts import vendor_pdf_libs

    for name, (_, digest) in vendor_pdf_libs.LIBRARIES.items():
        payload = (vendor_pdf_libs.OUT / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest, name
