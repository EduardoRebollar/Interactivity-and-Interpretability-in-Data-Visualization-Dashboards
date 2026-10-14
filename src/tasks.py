"""The task set. Implements `docs/study-design.md` section 4. No pandas — this ships to production.

Two isomorphic forms, A and B: the same six item types in the same order, on the same chart
types, with matched margins, over different data. A participant sees one form per condition and
never the same form twice, so nobody answers a question they have already answered.

Each item pairs one chart type with the interactive affordance that makes it quicker to read
(section 4): isolating a line in a tangle, sorting bars, hovering a dot or a cell, filtering a
map by coverage, and isolating two lines among others, then hovering where they cross.
Every item can still be answered from the static chart, because every key clears the acceptance
rule in section 4.

**No correct answers live in this module.** It is serialised to the browser, where an answer key
would be readable in the page source. Scoring happens offline, in `analysis/keys.py`.

Every value an item turns on was verified against `data/deploy/coverage.csv`. Change the design
document first, then this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.flow import Task

# Six options, like every other item (2026-09-25): "4 or more" became "4" and "5 or more".
COUNT_OPTIONS = ("0", "1", "2", "3", "4", "5 or more")

# The first year every line item asks about. The line charts draw from config.YEAR_MIN, 1985 since
# 2026-10-12, so the Years slider has years to set aside; T1 asks about 2000 to 2024, and T6 about
# "after 2000", since both its pairs cross before then. docs/study-design.md section 4.
ASKED_FROM = 2000

# The crossing item's options. Bands rather than years, because the static condition has no hover
# and an exact crossing year cannot be read from the chart. Inclusive at both ends, contiguous.
# 2000-2003 added 2026-09-25, so the crossing item offers six options like every other.
CROSSING_BANDS = ("2000-2003", "2004-2008", "2009-2012", "2013-2016", "2017-2020", "2021-2024")

# The heatmap's columns: every fifth year, and the last.
HEATMAP_YEARS = (2000, 2005, 2010, 2015, 2020, 2024)

# The scatter plots compare the first and last years of the range.
SCATTER_YEARS = (2000, 2024)

# The practice item is identical in both forms and is not scored. It teaches the interface, so it is
# a line chart, the one chart type with every control, and its change is unmissable. Myanmar,
# because no scored item asks about it and neither T1 chart draws it. Brazil's fall, the practice
# until 2026-09-27, is B-T1's story, as Ukraine's collapse was A-T1's before that. The window was
# 2015-2021 until the first pilot session (2026-10-12): Myanmar holds near 90% until 2019, so most
# of it read as level; 2019-2021 is the fall alone, 90% to 37%.
PRACTICE = Task(
    task_id="P0",
    form="both",
    kind="practice",
    prompt=(
        "Practice (not scored). Look at Myanmar's line. Did coverage rise, fall, or stay level "
        "between 2019 and 2021?"
    ),
    vaccine="DTP3",
    entities=("Myanmar", "World"),
    options=("It rose", "It fell", "It stayed about level"),
)

# T1 is written, not chosen (2026-09-27): the one item that asks for an interpretation of a time
# series. Same wording in both forms, with the two countries alphabetical. Reworded 2026-10-12.
DESCRIBE_PROMPT = (
    "Look at {first} and {second}'s coverage. Describe how their coverage changed between 2000 and "
    "2024, and how their trends were similar or different."
)

# T3's wording, the same in both forms since 2026-10-12, when it stopped naming the continent.
IMPROVED_PROMPT = (
    "Each country is placed by its coverage in 2000 (across) and in 2024 (up). The dashed diagonal "
    "means no change. Which country improved the most?"
)

# Entities are listed alphabetically, World last, and country options follow the same order. The
# order also assigns each line and dot its colour, so neither where the answer sits in the list nor
# which colour it gets depends on the answer (docs/study-design.md section 5). Year options run in
# calendar order. Which options are offered is the one free choice, and it is used to spread the key
# across positions: no position holds more than a third of the ten keys (T1 has none).

FORM_A: tuple[Task, ...] = (
    Task(
        task_id="T1",
        form="A",
        kind="describe",
        prompt=DESCRIBE_PROMPT.format(first="India", second="Ukraine"),
        vaccine="DTP3",
        # Eight countries, no World line (2026-09-25): the tangle the isolation control cuts
        # through. India rises steadily; Ukraine collapses and recovers; India passes it in 2009.
        # Gabon in place of Nigeria since 2026-10-12: drawn from 1985, Nigeria ran within 5 points
        # of India for five years (1985-1989). Gabon crosses the pair as often as Nigeria did, and
        # is African, as Nigeria is, for the Regions control. docs/study-design.md section 4.
        entities=(
            "Brazil",
            "China",
            "Ethiopia",
            "Gabon",
            "India",
            "Indonesia",
            "Pakistan",
            "Ukraine",
        ),
    ),
    Task(
        task_id="T2",
        form="A",
        kind="rank",
        chart="bar",
        years=(2017,),
        prompt="The bars show coverage in 2017. Which country had the third-highest coverage?",
        # MCV1 since 2026-10-11, with Guinea's bar in place of Brazil's: India's 90 is 7 points
        # below Vietnam and 6 above Kenya. The options are ranks 1, 2, 3, 4, 8 and 10, as in B.
        # docs/study-design.md section 4.
        vaccine="MCV1",
        entities=(
            "Afghanistan",
            "China",
            "Ethiopia",
            "Guinea",
            "India",
            "Kenya",
            "Mali",
            "Nigeria",
            "Pakistan",
            "Vietnam",
        ),
        options=("China", "Ethiopia", "Guinea", "India", "Kenya", "Vietnam"),
    ),
    Task(
        task_id="T3",
        form="A",
        kind="improved",
        chart="scatter",
        years=SCATTER_YEARS,
        prompt=IMPROVED_PROMPT,
        vaccine="DTP3",
        # Not Angola or DR Congo: their dots sit within 2 points of Nigeria's and would hide it.
        # Sixteen dots (2026-10-11): the ten added each improved at least 20 points less than
        # Niger, so none rivals the key. Twenty-one since 2026-10-13, so the chips fill three rows
        # of seven: Algeria, Eritrea, Guinea, Namibia and South Africa, found by search, each
        # named clear of every other name and dot. docs/study-design.md section 4.
        entities=(
            "Algeria",
            "Benin",
            "Burkina Faso",
            "Cameroon",
            "Central African Republic",
            "Chad",
            "Egypt",
            "Eritrea",
            "Ethiopia",
            "Guinea",
            "Kenya",
            "Libya",
            "Madagascar",
            "Mali",
            "Mozambique",
            "Namibia",
            "Niger",
            "Nigeria",
            "South Africa",
            "Sudan",
            "Tanzania",
        ),
        options=("Burkina Faso", "Chad", "Ethiopia", "Mali", "Niger", "Nigeria"),
    ),
    Task(
        task_id="T4",
        form="A",
        kind="cell",
        chart="heatmap",
        years=HEATMAP_YEARS,
        prompt=(
            "Rows are countries and columns are years. Which country contains the single lowest "
            "coverage?"
        ),
        # MCV1 since 2026-10-11, with Benin's row in place of the Central African Republic's,
        # whose lowest cell (36) sits 9 points above Chad's 27. Twelve rows since 2026-10-13: the
        # four added each bottom out at 63 or above, beyond Pakistan's 57, the sixth option row, so
        # key, margin and options are unchanged. docs/study-design.md section 4.
        vaccine="MCV1",
        entities=(
            "Benin",
            "Burkina Faso",
            "Cambodia",
            "Chad",
            "Cote d'Ivoire",
            "India",
            "Indonesia",
            "Iraq",
            "Mali",
            "Pakistan",
            "South Africa",
            "Syria",
        ),
        options=("Benin", "Burkina Faso", "Chad", "India", "Mali", "Pakistan"),
    ),
    Task(
        task_id="T5",
        form="A",
        kind="threshold",
        chart="map",
        years=(2013,),
        prompt=(
            "The map colours 18 countries in Africa by their coverage in 2013. "
            "How many of those countries had coverage below 50%?"
        ),
        vaccine="DTP3",
        # The chart handoff's 20 African countries, less Somalia (44) and Ethiopia (59): within 10
        # points of 50% in 2013, their side of the line is a colour judgement too fine to make
        # without hover. Egypt, Libya and Sudan are not sub-Saharan, so the prompt says "Africa"
        # (2026-10-11). docs/study-design.md section 4.
        entities=(
            "Benin",
            "Burkina Faso",
            "Cameroon",
            "Central African Republic",
            "Chad",
            "Democratic Republic of Congo",
            "Egypt",
            "Kenya",
            "Libya",
            "Madagascar",
            "Mali",
            "Mozambique",
            "Niger",
            "Nigeria",
            "Sudan",
            "Tanzania",
            "Uganda",
            "Zambia",
        ),
        options=COUNT_OPTIONS,
    ),
    Task(
        task_id="T6",
        form="A",
        kind="crossing",
        # "after 2000" since 2026-10-12, when the chart began at 1985: Ethiopia is also above the
        # Central African Republic in 1994-1997.
        prompt=(
            "Ethiopia's coverage became higher than the Central African Republic's at some point "
            "after 2000. Roughly when did that first happen?"
        ),
        vaccine="DTP3",
        # Six more lines that cross the pair away from where they meet, so isolating the two has
        # something to remove (2026-10-11). Nigeria comes nearest, 7.4 points from the meeting
        # point. Not Congo, whose tag would sit beside DR Congo's. No World line, to match B-T6,
        # where World runs through the crossing. docs/study-design.md section 4.
        entities=(
            "Afghanistan",
            "Central African Republic",
            "Chad",
            "Cote d'Ivoire",
            "Democratic Republic of Congo",
            "Ethiopia",
            "Nigeria",
            "Somalia",
        ),
        options=CROSSING_BANDS,
    ),
)

FORM_B: tuple[Task, ...] = (
    Task(
        task_id="T1",
        form="B",
        kind="describe",
        prompt=DESCRIBE_PROMPT.format(first="Brazil", second="Uganda"),
        vaccine="DTP3",
        # A's story: Uganda rises steadily; Brazil falls and recovers; Uganda passes it in 2016.
        # Not India, which runs within 5 points of Uganda for 19 of 25 years; Nepal gives the
        # tangle nearest A's. No World line, as in A.
        entities=(
            "Brazil",
            "China",
            "Ethiopia",
            "Indonesia",
            "Nepal",
            "Nigeria",
            "Pakistan",
            "Uganda",
        ),
    ),
    Task(
        task_id="T2",
        form="B",
        kind="rank",
        chart="bar",
        years=(2017,),
        prompt="The bars show coverage in 2017. Which country had the sixth-highest coverage?",
        # The sixth-highest, in 2017, since 2026-10-12: in 2021 the fifth and sixth bars tied.
        # Mozambique's 83 is 5 points below Algeria and 13 above Mali, and the options offer both.
        # docs/study-design.md section 4.
        vaccine="MCV1",
        entities=(
            "Algeria",
            "Cameroon",
            "Colombia",
            "Egypt",
            "Ethiopia",
            "Indonesia",
            "Mali",
            "Mozambique",
            "Nigeria",
            "United States",
        ),
        options=("Algeria", "Cameroon", "Egypt", "Indonesia", "Mali", "Mozambique"),
    ),
    Task(
        task_id="T3",
        form="B",
        kind="improved",
        chart="scatter",
        years=SCATTER_YEARS,
        prompt=IMPROVED_PROMPT,
        vaccine="DTP3",
        # Not Afghanistan: its +35 all but ties India's +36. Sixteen dots, as in A: the ten added
        # each improved at least 20 points less than India. Twenty-one since 2026-10-13, as in A.
        # Asia's eligible countries were used up, so Benin, the Central African Republic and Sudan
        # are A's own dots, placed as there; Cote d'Ivoire and Gabon are B's alone.
        entities=(
            "Bangladesh",
            "Benin",
            "Cambodia",
            "Central African Republic",
            "Cote d'Ivoire",
            "Gabon",
            "India",
            "Indonesia",
            "Iraq",
            "Jordan",
            "Kyrgyzstan",
            "Laos",
            "Lebanon",
            "Nepal",
            "Oman",
            "Pakistan",
            "Philippines",
            "Sudan",
            "Syria",
            "Thailand",
            "Yemen",
        ),
        options=("Bangladesh", "Cambodia", "India", "Indonesia", "Nepal", "Pakistan"),
    ),
    Task(
        task_id="T4",
        form="B",
        kind="cell",
        chart="heatmap",
        years=HEATMAP_YEARS,
        prompt=(
            "Rows are countries and columns are years. Which country contains the single highest "
            "coverage?"
        ),
        # The highest cell since 2026-10-12: Nepal's 97 against Pakistan's 86, the only cell in the
        # lightest band. Laos and Cameroon replace Myanmar (91) and Uganda (90), which sat in that
        # band too. The options are the six highest rows. Twelve rows since 2026-10-13, as in A: the
        # four added each top out at 73 or below, under Mali's 78, the sixth option row.
        # docs/study-design.md section 4.
        vaccine="MCV1",
        entities=(
            "Afghanistan",
            "Cameroon",
            "Democratic Republic of Congo",
            "Ethiopia",
            "Laos",
            "Madagascar",
            "Mali",
            "Nepal",
            "Niger",
            "Nigeria",
            "Pakistan",
            "Yemen",
        ),
        options=("Cameroon", "Laos", "Mali", "Nepal", "Niger", "Pakistan"),
    ),
    Task(
        task_id="T5",
        form="B",
        kind="threshold",
        chart="map",
        years=(2007,),
        prompt=(
            "The map colours 18 countries in Africa by their coverage in 2007. "
            "How many of those countries had coverage below 50%?"
        ),
        vaccine="DTP3",
        # As many as form A's, as far as possible different ones (2026-10-11): Chad (29) and Somalia
        # (40), the only countries in the older scope clear below 50% in 2007, and sixteen added for
        # this map, each at least 13 points above the line. Every African country within 10 points
        # of 50% in 2007 is left out: Nigeria (42), Angola (43), the Central African Republic and
        # Equatorial Guinea (48), Ethiopia (50), Niger (58). docs/study-design.md section 4.
        entities=(
            "Algeria",
            "Botswana",
            "Chad",
            "Congo",
            "Cote d'Ivoire",
            "Eritrea",
            "Gabon",
            "Ghana",
            "Guinea",
            "Malawi",
            "Mauritania",
            "Morocco",
            "Namibia",
            "Senegal",
            "Somalia",
            "South Africa",
            "Tunisia",
            "Zimbabwe",
        ),
        options=COUNT_OPTIONS,
    ),
    Task(
        task_id="T6",
        form="B",
        kind="crossing",
        # "after 2000" since 2026-10-12, when the chart began at 1985: the two change places five
        # times between 1987 and 1996.
        prompt=(
            "Pakistan's coverage became higher than Mozambique's at some point after 2000. Roughly "
            "when did that first happen?"
        ),
        vaccine="DTP3",
        # Six more lines, as in A (2026-10-11); Sudan comes nearest, 9.1 points from the meeting
        # point. No World line: it runs within 2 points of both lines at the 2019 crossing, and
        # Pakistan crosses it too, in 2021. Ghana and Guinea in place of Cameroon and Madagascar
        # since 2026-10-12: drawn from 1985, Madagascar ran within 5 points of Pakistan for nine
        # years (1995-2003) and Cameroon for seven (1996-2002). docs/study-design.md section 4.
        entities=(
            "Benin",
            "Gabon",
            "Ghana",
            "Guinea",
            "Kenya",
            "Mozambique",
            "Pakistan",
            "Sudan",
        ),
        options=CROSSING_BANDS,
    ),
)

FORMS: dict[str, tuple[Task, ...]] = {"A": FORM_A, "B": FORM_B}


def is_written(task: Task) -> bool:
    """True for an item answered in a text box, with no options and no justification (T1)."""
    return task.kind == "describe"


# The items overloaded with controls they do not need (2026-10-12, docs/study-design.md section 4,
# T1): in the interactive condition they carry four more, unannounced (visual-spec.md section 7.7).
EXTRA_CONTROL_ITEMS = ("T1",)


def has_extra_controls(task: Task) -> bool:
    """True for a scored item overloaded with extra controls: T1, in both forms."""
    return task.form in FORMS and task.task_id in EXTRA_CONTROL_ITEMS


JUSTIFICATION_PROMPT = "In one sentence, describe why you chose your answer."

# The first step's heading on a task screen, by item kind. The design handoff's wording.
CHOOSE_PROMPTS: dict[str, str] = {
    "practice": "Choose an answer:",
    "describe": "Write your description:",
    "rank": "Choose one country:",
    "improved": "Choose one country:",
    "cell": "Choose one country:",
    "threshold": "Choose one number:",
    "crossing": "Choose a range:",
}

SKIP_NOTE = "You may skip any question. If you leave one unanswered, you will be asked to confirm."

# --- The post-condition survey: docs/study-design.md section 6.1 ---------------------------------
#
# Asked after EACH condition, one question per page. Paas first, then the design handoff's items,
# verbatim. The statements say "in this part" or "the charts", never which version it was.

# Paas single-item mental effort, the RQ3 measure. Kept 2026-09-25 as the survey's first question.
LOAD_PROMPT = "In solving the preceding tasks, I invested:"
LOAD_ANCHORS = {1: "very, very low mental effort", 9: "very, very high mental effort"}

SURVEY_INTRO = {
    "first": "A few questions about the charts you just used.",
    "second": "A few questions about the charts you just used, then a comparison of both versions.",
}

# 7-point agreement, every point labelled.
LIKERT_POINTS = 7
LIKERT_ANCHORS = {
    1: "Strongly disagree",
    2: "Disagree",
    3: "Somewhat disagree",
    4: "Neither agree nor disagree",
    5: "Somewhat agree",
    6: "Agree",
    7: "Strongly agree",
}

# Section title -> (key -> statement). Asked after every condition; Paas opens the first section.
EXPERIENCE_SECTION = "Your experience"
LIKERT_ITEMS: dict[str, str] = {
    "a1": "I am confident that my answers in this part were correct.",
    "a2": "The charts were easy to understand.",
    "a3": "I could quickly find the information I needed.",
    "a4": "I could read values from the charts as precisely as the questions required.",
    "a5": "It was easy to see where coverage increased or decreased.",
    "a6": "It was easy to compare countries with each other.",
    "a7": "Answering the questions took a lot of mental effort.",
    "a8": "I felt frustrated while answering the questions.",
    "a9": "I felt rushed while answering the questions.",
}

# Asked after the INTERACTIVE condition only: the static condition has no controls to rate. b4
# (2026-10-13) is the only record of hover, which is not logged.
CONTROLS_SECTION = "Chart controls"
CONTROLS_HELP = "About the controls on the charts."
CONTROLS_ITEMS: dict[str, str] = {
    "b1": "I could figure out how to use the chart controls without instructions.",
    "b2": "The chart controls helped me answer the questions.",
    "b3": "The chart controls were easy to use.",
    "b4": "I hovered over the charts to see exact values.",
}

# Asked after the SECOND condition only, once both versions have been used.
COMPARISON_SECTION = "Comparing the two versions"
COMPARISON_OPTIONS = ("The charts with controls", "The charts without controls", "No difference")
COMPARISON_CHOICES: dict[str, str] = {
    "c1": "Which charts helped you answer more accurately?",
    "c2": "Which charts did you prefer using?",
}
# Free text. The handoff labels it "Optional", though every question may be skipped.
COMPARISON_TEXT_KEY = "c3"
COMPARISON_TEXT = "What made one set of charts easier or harder to use than the other?"
COMPARISON_TEXT_HELP = "Optional"
COMPARISON_KEYS = (*COMPARISON_CHOICES, COMPARISON_TEXT_KEY)
# A free-text answer longer than this is cut: long enough for any reply, short enough that a stuck
# key cannot fill the log.
MAX_TEXT = 2000

# --- About you: docs/study-design.md section 6.2 ------------------------------------------------
#
# Asked once, at the END, one question per page. A1-D2 in the handoff's wording (`auBuild()`),
# verbatim; E1-E3 Eduardo's (2026-10-13), checks on the session rather than background. Not all
# broad categories: age in years and the two "Other" text boxes are on the IRB list in
# study-design.md section 10.

PREFER_NOT = "Prefer not to say"
OTHER = "Other"
AGE_RANGE = (18, 99)


@dataclass(frozen=True, slots=True)
class Question:
    """One About-you question.

    `kind` is "choice" (one of `options`), "age" (a whole number in `AGE_RANGE`, or `PREFER_NOT`),
    "matrix" (one of `options` for each of `rows`) or "text" (free text up to `MAX_TEXT`, no
    options). A choice whose options include `OTHER` has a text box beside it, logged under
    `other_key`. `prefer_not_inline` marks the one question whose "Prefer not to say" is an
    ordinary option rather than set apart beneath the others.
    """

    key: str
    code: str
    text: str
    options: tuple[str, ...] = ()
    kind: str = "choice"
    help: str = ""
    ordinal: bool = False
    rows: tuple[str, ...] = ()
    prefer_not_inline: bool = False

    @property
    def other_key(self) -> str | None:
        return f"{self.key}_other" if OTHER in self.options else None


TOOL_LEVELS = ("Never heard of it", "Heard of it, never used", "Used a few times", "Use regularly")

ABOUT_INTRO = "A few questions about your setup and background."

# (section title, questions), in the order they are asked.
ABOUT_SECTIONS: tuple[tuple[str, tuple[Question, ...]], ...] = (
    (
        "Session setup",
        (
            Question(
                "pointer",
                "A1",
                "What are you using to control the pointer right now?",
                ("Mouse", "Trackpad / touchpad", "Touchscreen", OTHER),
            ),
        ),
    ),
    (
        "Background",
        (
            Question("age", "B1", "What is your age (in years)?", kind="age"),
            Question(
                "role",
                "B2",
                "Which best describes your current role?",
                (
                    "Undergraduate student",
                    "Graduate student",
                    "Faculty or staff",
                    "Not affiliated with a college or university",
                    PREFER_NOT,
                ),
            ),
            Question(
                "field",
                "B3",
                "What is your primary field of study or work?",
                (
                    "Computer science, math, or statistics",
                    "Natural or physical sciences (e.g., biology, chemistry, physics)",
                    "Health or life sciences (e.g., kinesiology, public health, pre-med)",
                    "Social sciences (e.g., economics, psychology, politics)",
                    "Humanities or arts",
                    OTHER,
                    PREFER_NOT,
                ),
                help=(
                    "(If you have more than one, choose the one closest to how you spend most of "
                    "your time.)"
                ),
            ),
        ),
    ),
    (
        "Experience with data visualization",
        (
            Question(
                "read_charts",
                "C1",
                "How often do you read or use charts, graphs, or dashboards (for school, work, or "
                "personal interest)?",
                (
                    "Rarely or never",
                    "A few times a year",
                    "About monthly",
                    "About weekly",
                    "Daily or almost daily",
                    PREFER_NOT,
                ),
                ordinal=True,
            ),
            Question(
                "make_charts",
                "C2",
                "How often do you create charts, graphs, or dashboards?",
                (
                    "Never",
                    "A few times ever",
                    "A few times a year",
                    "About monthly",
                    "About weekly or more",
                    PREFER_NOT,
                ),
                ordinal=True,
            ),
            Question(
                "stats_course",
                "C3",
                "Have you taken a course where data visualization or statistics was a major part?",
                ("Yes", "No", "Not sure", PREFER_NOT),
            ),
            Question(
                "tools",
                "C4",
                "How familiar are you with each of these tools?",
                (*TOOL_LEVELS, PREFER_NOT),
                kind="matrix",
                rows=(
                    "Tableau",
                    "Plotly or Plotly Dash",
                    "Microsoft Excel or Google Sheets charts",
                    "Power BI",
                    "Our World in Data charts",
                ),
            ),
        ),
    ),
    (
        "Topic familiarity",
        (
            Question(
                "topic_familiarity",
                "D1",
                "Before today, how familiar were you with data on childhood vaccination rates "
                "around the world?",
                (
                    "1 — Not at all familiar",
                    "2 — Slightly familiar",
                    "3 — Somewhat familiar",
                    "4 — Very familiar",
                    "5 — Extremely familiar",
                    PREFER_NOT,
                ),
                ordinal=True,
            ),
            Question(
                "health_background",
                "D2",
                "Have you studied or worked in public health, medicine, nursing, or epidemiology?",
                ("Yes", "No", PREFER_NOT),
                prefer_not_inline=True,
            ),
        ),
    ),
    (
        # 2026-10-13, study-design.md section 6.2. E1 sets up section 7's word-of-mouth sensitivity
        # analysis; E2 and E3 enter no analysis. No "Prefer not to say": E1 identifies no one, and
        # every question may be skipped.
        "Before you finish",
        (
            Question(
                "heard_details",
                "E1",
                "Before today, had you heard any details about this study from someone who took "
                "part in it?",
                ("Yes", "No", "Not sure"),
            ),
            Question(
                "confusing",
                "E2",
                "Was anything in the questions or instructions confusing? If so, what?",
                kind="text",
                help="Optional",
            ),
            Question(
                "feedback",
                "E3",
                "Anything else you'd like to tell the researcher or give feedback on?",
                kind="text",
                help="Optional",
            ),
        ),
    ),
)

# The E1 answer section 7's sensitivity analysis leaves out.
HEARD_KEY = "heard_details"
HEARD_YES = "Yes"

ABOUT_QUESTIONS: tuple[Question, ...] = tuple(q for _, qs in ABOUT_SECTIONS for q in qs)

# Every key the `demographics` event carries: one per question, plus each "Other" text box.
DEMOGRAPHIC_KEYS: tuple[str, ...] = tuple(
    key for q in ABOUT_QUESTIONS for key in (q.key, q.other_key) if key is not None
)


def for_form(form: str) -> tuple[Task, ...]:
    """The six scored tasks for one form, in presentation order."""
    if form not in FORMS:
        raise KeyError(f"Unknown form {form!r}; expected one of {sorted(FORMS)}")
    return FORMS[form]
