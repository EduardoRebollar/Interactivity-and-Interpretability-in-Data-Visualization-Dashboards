"""Informed consent: the form's text, the signed record, and where it is kept. No pandas: ships.

The text is Occidental's informed consent form as submitted to HSRRC (`irb/COMP 490 Consent
Form.pdf`, local only), word for word. `docs/study-design.md` section 9 describes the procedure.

**The signed record is kept apart from the study data** (IRB form items 15 and 17). It carries the
printed name, the date and the signature, and deliberately NO participant ID: it goes to its own
table, `consent_records`, or locally to `config.CONSENT_DIR`, never to the event log. The study log
receives only a `consent` event with the time, the text hash and the signature method.

A signature is a list of strokes, each a list of `[x, y]` points in the pad's own coordinate space
(`PAD_WIDTH` x `PAD_HEIGHT`), captured by `src/assets/signature.js`. Strokes rather than an image:
small, exact, and drawable as SVG in the signed copy without any image library.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src import config, db

# Flip to True only once HSRRC has approved this exact wording. While False, the consent screen
# carries a banner saying no participant may be run. Deliberately not part of the hashed text, so
# approving the form does not change CONSENT_VERSION.
APPROVED = False

TITLE = "Interactivity and Interpretability in Data Visualization Dashboards"
INVESTIGATOR = "Eduardo Rebollar"
SUPERVISOR = "Hector M. Camarillo Abad"
RESEARCHER_EMAIL = "rebollar@oxy.edu"

# The form's own heading: two centred lines above the body.
FORM_HEADING = ("OCCIDENTAL COLLEGE", "INFORMED CONSENT FORM")

# (heading, paragraph), in the form's order and with its own capitalisation. A heading ending in a
# colon runs in to its paragraph; one without (CONSENT STATEMENT) stands on a line of its own. A
# heading of None is an unheaded paragraph.
#
# Transcribed 2026-09-25 from the design handoff's screen 1, which reproduces the finalized form
# (docs/study-redesign.md section 3.6). Against the 2026-09-21 transcription it says about 40
# minutes instead of 20 to 35 (twice), adds the sentence on vaccination as a sensitive topic to
# Risks, says "Neon (a managed PostgreSQL service)", and gives access to "identifying data" rather
# than "the data". The apostrophe in "study’s" is the form's curly one.
SECTIONS: tuple[tuple[str | None, str], ...] = (
    ("Title of Study:", TITLE),
    ("Student Investigator:", INVESTIGATOR),
    ("Faculty Supervisor:", SUPERVISOR),
    (
        None,
        "You are invited to participate in a research study conducted by Eduardo Rebollar, a "
        "student in the Computer Science department at Occidental College in Los Angeles, CA. You "
        "must be at least 18 years of age to consent to participation in this study. Please read "
        "this form and ask any questions you may have before agreeing to participate in the study.",
    ),
    (
        "PURPOSE OF STUDY:",
        "The purpose of this study is to investigate whether interactive features in data "
        "visualization dashboards (such as filtering, sorting, and line isolation, along with "
        "directional change indicators) improve users' ability to interpret data compared with "
        "static visualizations of the same information, or whether they primarily reduce "
        "perceived cognitive load without changing the accuracy or depth of interpretation. You "
        "were selected to participate because you are an adult (18 or older) who is willing to "
        "spend approximately 40 minutes viewing dashboards and answering interpretation "
        "questions. Data collected from this study will be used for the researcher's senior "
        "comprehensive project (a final written thesis and public presentation at Occidental "
        "College), and de-identified findings will later be shared in a public repository on "
        "GitHub.",
    ),
    (
        "PROCEDURES:",
        "If you agree to take part in this study, you will be asked to complete a single session "
        "lasting approximately 40 minutes. In the session, you will view two versions of the same "
        "time-series data dashboard: one static version with no interactive controls, and one "
        "interactive version that allows filtering, sorting, and line isolation, and that displays "
        "directional (year-over-year) change indicators. The order in which you see the two "
        "versions will be counterbalanced. For each version, you will answer a short set of "
        "interpretation questions (such as identifying trends, comparing categories, or explaining "
        "what you notice in the data), followed by a brief survey with Likert-scale ratings of "
        "clarity, ease of use, confidence, and cognitive load, and short open-ended questions "
        "about your reasoning. The web application that presents the dashboards will "
        "automatically log your task responses, response times, and interaction events (such as "
        "clicks and filter selections) within the dashboard interface. No audio or video "
        "recording will be made, and no sensitive information will be requested. You may skip "
        "any question you do not wish to answer.",
    ),
    (
        "VOLUNTARY PARTICIPATION:",
        "Participation in this study is voluntary. You may skip any questions that you do not want "
        "to answer or stop participating at any time. You are free to withdraw from the study at "
        "any time without penalty, with no loss of benefits to which you were otherwise entitled. "
        "You may also request that your data be withdrawn from the study up to two weeks after "
        "your session by emailing me at rebollar@oxy.edu with your participant id. If two weeks "
        "have surpassed, your responses will have been merged into the de-identified dataset and "
        "can no longer be pulled out.",
    ),
    (
        "RISKS and BENEFITS:",
        "There are no anticipated risks or discomforts to your participation in this study other "
        "than those encountered in daily life. Reading and interpreting data visualizations may "
        "involve mild mental effort, similar to reading a chart in a news article. If you "
        "experience eye strain or fatigue, you may pause or stop at any time. The dashboards "
        "display real data on childhood vaccination coverage, a topic that may be personally "
        "sensitive or evoke strong opinions for some participants; you are not asked to share "
        "your views on vaccination, and you may skip any task or withdraw at any time without "
        "penalty.",
    ),
    (
        None,
        "Although you may not benefit directly from this research, by participating in this study "
        "you will help the researcher better understand how interactive features in dashboards "
        "affect the way people interpret data, which may inform the design of visualization tools "
        "used in journalism, healthcare, public policy, and other domains where dashboards support "
        "real decisions.",
    ),
    (
        "CONFIDENTIALITY:",
        "Your responses will be kept confidential. You will not be identified by name in any "
        "reported data, as each participant will be assigned a random participant id. The "
        "study’s web application writes this data to an encrypted Neon (a managed PostgreSQL "
        "service) database hosted in the U.S. The file linking ids to any identifying information "
        "(such as email addresses used for scheduling) will be stored in an encrypted file "
        "separate from the Neon study database. Only the researcher and the faculty supervisor "
        "will have access to identifying data. All study data and signed consent forms will be "
        "kept on a password-protected computer and, where applicable, in a locked office at "
        "Occidental College. De-identified data will be shared in a public repository on GitHub. "
        "No information that could identify you will be included in any public release.",
    ),
    ("COMPENSATION:", "You will not be paid for participating in this study."),
    (
        "CONTACT INFORMATION:",
        "If you have any questions or concerns about the research, you can contact Eduardo "
        "Rebollar at rebollar@oxy.edu or Hector M. Camarillo Abad at camarilloabad@oxy.edu. If you "
        "have any questions or concerns regarding your rights as a subject in this study, you may "
        "contact the Institutional Review Board Office at Occidental College in Los Angeles, CA, "
        "90041 at hsrrc@oxy.edu.",
    ),
    (
        "CONSENT STATEMENT",
        "I am at least eighteen years of age. I have read this form and the research study has "
        "been explained to me. I am fully aware of the nature and extent of my participation in "
        "this research project and the possible risks as outlined above. I understand that I may "
        "withdraw my participation in this project at any time without prejudice or penalty of any "
        "kind. I hereby agree to participate in this research project.",
    ),
)


def runs_in(heading: str | None) -> bool:
    """Whether a heading runs in to its paragraph ("PROCEDURES: If you agree ...")."""
    return heading is not None and heading.endswith(":")


def _joined(heading: str | None, body: str) -> str:
    if heading is None:
        return body
    return f"{heading} {body}" if runs_in(heading) else f"{heading}\n{body}"


CONSENT_TEXT = "\n\n".join([*FORM_HEADING, *(_joined(heading, body) for heading, body in SECTIONS)])

# Recorded on every consent event and record, so a change to the wording mid-study shows up in the
# data rather than depending on anyone's memory of when the text was edited.
CONSENT_VERSION = hashlib.sha256(CONSENT_TEXT.encode("utf-8")).hexdigest()[:16]

METHODS = ("drawn", "paper")

# The signature pad's coordinate space. The canvas is drawn at this size and scaled by CSS, and the
# JS maps pointer positions back into it, so a signature means the same thing at any screen width.
PAD_WIDTH = 600
PAD_HEIGHT = 180

# A tap or a stray click is not a signature. Real signatures run to hundreds of points.
MIN_POINTS = 10
# Bounds on what a browser may send, so a malformed or hostile payload cannot bloat the table.
MAX_POINTS = 5000
MAX_STROKES = 200
MAX_NAME = 200


class ConsentError(RuntimeError):
    """The consent record could not be stored. The participant must not advance."""


def build_record(
    consented_at: str | None,
    printed_name: str | None,
    signed_date: str | None,
    signature: Any,
    paper: bool = False,
) -> dict[str, Any]:
    """Assemble the record from what the consent screen sent. Pure; `problem` checks it."""
    return {
        "record_uid": str(uuid.uuid4()),
        "consent_version": CONSENT_VERSION,
        "consented_at": consented_at,
        "printed_name": (printed_name or "").strip(),
        "signed_date": (signed_date or "").strip(),
        "signature_method": "paper" if paper else "drawn",
        # A participant who signed on paper sends no drawing; anything the pad holds is dropped
        # rather than stored alongside a paper signature it does not belong to.
        "signature": None if paper else signature,
        "received_at": datetime.now(UTC).isoformat(),
    }


def problem(record: dict[str, Any] | None) -> str | None:
    """What the participant still has to do, or None when the record is complete.

    The messages are shown on screen, so they speak to the participant.
    """
    if not record:
        return "Please fill in your name and the date, and sign, before agreeing."
    if not record.get("consented_at"):
        # The browser failed to stamp the click. Consent without a time is not a record of consent.
        return "Please press the button again."
    if not record.get("printed_name"):
        return "Please type your full name."
    if len(record["printed_name"]) > MAX_NAME:
        return "That name is too long. Please type your name as you would sign it."
    if not record.get("signed_date"):
        return "Please enter today's date."
    if record.get("signature_method") not in METHODS:
        return "Please sign in the box, or tick the paper-copy box."
    if record["signature_method"] == "drawn":
        points = _point_count(record.get("signature"))
        if points is None:
            return "Your signature could not be read. Please clear it and sign again."
        if points < MIN_POINTS:
            return "Please sign in the box, or tick the box if you signed a paper copy."
    return None


def _point_count(signature: Any) -> int | None:
    """Points in a well-formed signature, or None if it is not one."""
    if signature is None:
        return 0
    if not isinstance(signature, list) or len(signature) > MAX_STROKES:
        return None
    total = 0
    for stroke in signature:
        if not isinstance(stroke, list):
            return None
        for point in stroke:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not all(
                    isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
                    for v in point
                )
            ):
                return None
            total += 1
    return total if total <= MAX_POINTS else None


# --- Storage -------------------------------------------------------------------------------------


def save(record: dict[str, Any], directory: Path | None = None) -> None:
    """Store a complete record: Postgres when configured, otherwise a local JSONL file.

    Raises `db.DatabaseError` on a database failure, so the caller's retry policy applies, and
    `ConsentError` when there is nowhere safe to put it. It never spools: the participant waits and
    retries on the consent screen instead, because the session must not continue on a consent that
    was not recorded (IRB form item 12B).
    """
    if problem(record) is not None:
        raise ConsentError(f"Refusing to store an incomplete consent record: {problem(record)}")
    if db.configured():
        db.insert_consent(record)
        return
    if os.environ.get("VERCEL") and directory is None:
        raise ConsentError("DATABASE_URL is not set on this deployment; consent cannot be recorded")
    target = directory or config.CONSENT_DIR
    target.mkdir(parents=True, exist_ok=True)
    with (target / "consent_records.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_local(directory: Path | None = None) -> list[dict[str, Any]]:
    """Records written by local runs, oldest first."""
    path = (directory or config.CONSENT_DIR) / "consent_records.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


# --- The signed copy -----------------------------------------------------------------------------


def signature_svg(signature: Any) -> str:
    """The drawn signature as inline SVG. Empty string when there is nothing to draw."""
    if not signature or _point_count(signature) in (None, 0):
        return ""
    lines = []
    for stroke in signature:
        if len(stroke) == 1:
            x, y = stroke[0]
            lines.append(f'<circle cx="{x}" cy="{y}" r="1.5" fill="#1A1A1A"/>')
        elif stroke:
            points = " ".join(f"{x},{y}" for x, y in stroke)
            lines.append(f'<polyline points="{points}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAD_WIDTH} {PAD_HEIGHT}" '
        f'width="{PAD_WIDTH // 2}" height="{PAD_HEIGHT // 2}" fill="none" stroke="#1A1A1A" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        + "".join(lines)
        + "</svg>"
    )


def copy_html(record: dict[str, Any]) -> str:
    """A standalone, printable copy of the signed form.

    The participant downloads one (the paper form asks them to keep a copy), and
    `scripts/export_consents.py` writes one per record for the researcher to countersign and file.
    The researcher's line is left blank for exactly that.
    """
    esc = html.escape
    paragraphs = "\n".join(
        f"<p><b>{esc(heading)}</b> {esc(body)}</p>"
        if runs_in(heading)
        else (f"<p><b>{esc(heading)}</b></p>" if heading else "") + f"<p>{esc(body)}</p>"
        for heading, body in SECTIONS
    )
    title = "<br>".join(esc(line) for line in FORM_HEADING)
    if record.get("signature_method") == "paper":
        signature = "<p><em>Signed on a paper copy of this form with the researcher.</em></p>"
    else:
        signature = signature_svg(record.get("signature"))
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Signed consent form</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; color: #1A1A1A; max-width: 720px;
       margin: 32px auto; padding: 0 16px; line-height: 1.5; }}
h1 {{ font-size: 20px; text-align: center; }} h2 {{ font-size: 15px; margin: 18px 0 4px; }}
.line {{ border-top: 1px solid #1A1A1A; margin-top: 8px; padding-top: 4px; font-size: 13px; }}
.meta {{ color: #595959; font-size: 12px; }}
</style></head><body>
<h1>{title}</h1>
{paragraphs}
<h2>Participant signature and date / printed name</h2>
{signature}
<p class="line">Signed: {esc(record.get("signed_date") or "")} &nbsp;/&nbsp;
{esc(record.get("printed_name") or "")}</p>
<h2>Researcher or research assistant signature and date / printed name</h2>
<p style="height:48px"></p>
<p class="line">&nbsp;</p>
<p class="meta">Agreed electronically at {esc(str(record.get("consented_at") or ""))} (UTC).
Consent text version {esc(str(record.get("consent_version") or ""))}.
Record {esc(str(record.get("record_uid") or ""))}.</p>
</body></html>
"""


__all__ = [
    "APPROVED",
    "CONSENT_TEXT",
    "CONSENT_VERSION",
    "ConsentError",
    "FORM_HEADING",
    "SECTIONS",
    "build_record",
    "copy_html",
    "problem",
    "save",
]
