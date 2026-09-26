"""The task set. Implements `docs/study-design.md` section 4. No pandas — this ships to production.

Two isomorphic forms, A and B: the same six item types in the same order, on the same chart
types, with matched margins, over different data. A participant sees one form per condition and
never the same form twice, so nobody answers a question they have already answered.

Each item pairs one chart type with the interactive affordance that makes it quicker to read
(section 4): isolating a line in a tangle, sorting bars, hovering a dot or a cell, filtering a
map by coverage, and hovering two lines where they cross.
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

# The crossing item's options. Bands rather than years, because the static condition has no hover
# and an exact crossing year cannot be read from the chart. Inclusive at both ends, contiguous.
# 2000-2003 added 2026-09-25, so the crossing item offers six options like every other.
CROSSING_BANDS = ("2000-2003", "2004-2008", "2009-2012", "2013-2016", "2017-2020", "2021-2024")

# The heatmap's columns: every fifth year, and the last.
HEATMAP_YEARS = (2000, 2005, 2010, 2015, 2020, 2024)

# The scatter plots compare the first and last years of the range.
SCATTER_YEARS = (2000, 2024)

# The practice item is identical in both forms and is not scored. It teaches the interface, so it is
# a line chart, the one chart type with every control, and its change is unmissable. Brazil, because
# no scored item asks about Brazil: the old practice, Ukraine's collapse, would have primed A-T1.
PRACTICE = Task(
    task_id="P0",
    form="both",
    kind="practice",
    prompt=(
        "Practice (not scored). Look at Brazil's line. Did coverage rise, fall, or stay level "
        "between 2015 and 2021?"
    ),
    vaccine="DTP3",
    entities=("Brazil", "World"),
    options=("It rose", "It fell", "It stayed about level"),
)

# Entities are listed alphabetically, World last, and country options follow the same order. The
# order also assigns each line and dot its colour, so neither where the answer sits in the list nor
# which colour it gets depends on the answer (docs/study-design.md section 5). Year options run in
# calendar order. Which options are offered is the one free choice, and it is used to spread the key
# across positions: no position holds more than a third of the twelve keys.

FORM_A: tuple[Task, ...] = (
    Task(
        task_id="T1",
        form="A",
        kind="lowest",
        prompt="Focus on Ukraine's line. In which year was its coverage at its lowest point?",
        vaccine="DTP3",
        # Eight countries, no World line (2026-09-25): the tangle the isolation control cuts
        # through.
        entities=(
            "Brazil",
            "China",
            "Ethiopia",
            "India",
            "Indonesia",
            "Nigeria",
            "Pakistan",
            "Ukraine",
        ),
        # Not 2010-2015: Ukraine is 23 in 2014 and 2015, too close to its low of 19 in 2016 to tell
        # apart, and a year either side of them must still be nearest 2016. The handoff's 2012
        # failed exactly that way. docs/study-design.md section 4.
        options=("2004", "2008", "2016", "2019", "2022", "2024"),
    ),
    Task(
        task_id="T2",
        form="A",
        kind="rank",
        chart="bar",
        years=(2017,),
        prompt="The bars show coverage in 2017. Which country had the third-highest coverage?",
        vaccine="DTP3",
        entities=("Brazil", "China", "Ethiopia", "India", "Nigeria", "Pakistan", "Vietnam"),
        options=("Brazil", "China", "Ethiopia", "India", "Nigeria", "Vietnam"),
    ),
    Task(
        task_id="T3",
        form="A",
        kind="improved",
        chart="scatter",
        years=SCATTER_YEARS,
        prompt=(
            "Each dot is an African country, placed by its coverage in 2000 (across) and in 2024 "
            "(up). The dashed diagonal means no change. Which country improved the most — the dot "
            "furthest above the diagonal?"
        ),
        vaccine="DTP3",
        # Not Angola or DR Congo: their dots sit within 2 points of Nigeria's and would hide it.
        entities=("Burkina Faso", "Chad", "Ethiopia", "Mali", "Niger", "Nigeria"),
        options=("Burkina Faso", "Chad", "Ethiopia", "Mali", "Niger", "Nigeria"),
    ),
    Task(
        task_id="T4",
        form="A",
        kind="cell",
        chart="heatmap",
        years=HEATMAP_YEARS,
        prompt=(
            "Rows are countries and columns are years. Darker cells mean lower coverage. Which "
            "country's row contains the single lowest cell?"
        ),
        vaccine="DTP3",
        entities=(
            "Burkina Faso",
            "Cambodia",
            "Central African Republic",
            "Chad",
            "India",
            "Indonesia",
            "Mali",
            "Pakistan",
        ),
        options=(
            "Burkina Faso",
            "Central African Republic",
            "Chad",
            "India",
            "Mali",
            "Pakistan",
        ),
    ),
    Task(
        task_id="T5",
        form="A",
        kind="threshold",
        chart="map",
        years=(2013,),
        prompt=(
            "The map colours 13 countries in sub-Saharan Africa by their coverage in 2013. "
            "How many of those countries had coverage below 50%?"
        ),
        vaccine="DTP3",
        # Every country at least 10 points from 50% in 2013. Somalia (44), South Sudan (53), Angola
        # (54) and Ethiopia (59) are left uncoloured: their side of the line is a colour judgement
        # too fine to make without hover. docs/study-design.md section 4.
        entities=(
            "Cameroon",
            "Central African Republic",
            "Chad",
            "Democratic Republic of Congo",
            "Kenya",
            "Madagascar",
            "Mali",
            "Mozambique",
            "Niger",
            "Nigeria",
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
        prompt=(
            "Ethiopia's coverage became higher than the Central African Republic's at some point. "
            "Roughly when did that first happen?"
        ),
        vaccine="DTP3",
        # No World line, to match B-T6, where World runs through the crossing.
        # docs/study-design.md section 4.
        entities=("Central African Republic", "Ethiopia"),
        options=CROSSING_BANDS,
    ),
)

FORM_B: tuple[Task, ...] = (
    Task(
        task_id="T1",
        form="B",
        kind="lowest",
        prompt="Focus on Myanmar's line. In which year was its coverage at its lowest point?",
        vaccine="DTP3",
        entities=(
            "Brazil",
            "China",
            "Ethiopia",
            "India",
            "Indonesia",
            "Myanmar",
            "Nigeria",
            "Pakistan",
        ),
        # 2005 mirrors A-T1's 2004: a year four before the first option. No World line, as in A.
        options=("2005", "2009", "2013", "2017", "2021", "2024"),
    ),
    Task(
        task_id="T2",
        form="B",
        kind="rank",
        chart="bar",
        years=(2024,),
        prompt="The bars show coverage in 2024. Which country had the third-highest coverage?",
        vaccine="DTP3",
        entities=(
            "Cambodia",
            "Colombia",
            "Egypt",
            "Ethiopia",
            "Indonesia",
            "Nigeria",
            "United States",
        ),
        options=("Cambodia", "Colombia", "Egypt", "Ethiopia", "Nigeria", "United States"),
    ),
    Task(
        task_id="T3",
        form="B",
        kind="improved",
        chart="scatter",
        years=SCATTER_YEARS,
        prompt=(
            "Each dot is an Asian country, placed by its coverage in 2000 (across) and in 2024 "
            "(up). The dashed diagonal means no change. Which country improved the most — the dot "
            "furthest above the diagonal?"
        ),
        vaccine="DTP3",
        # Not Afghanistan: its +35 all but ties India's +36.
        entities=("Bangladesh", "Cambodia", "India", "Indonesia", "Nepal", "Pakistan"),
        options=("Bangladesh", "Cambodia", "India", "Indonesia", "Nepal", "Pakistan"),
    ),
    Task(
        task_id="T4",
        form="B",
        kind="cell",
        chart="heatmap",
        years=HEATMAP_YEARS,
        prompt=(
            "Rows are countries and columns are years. Darker cells mean lower coverage. Which "
            "country's row contains the single lowest cell?"
        ),
        vaccine="DTP3",
        entities=(
            "Afghanistan",
            "Madagascar",
            "Mali",
            "Myanmar",
            "Nepal",
            "Niger",
            "Pakistan",
            "Uganda",
        ),
        options=("Afghanistan", "Madagascar", "Mali", "Niger", "Pakistan", "Uganda"),
    ),
    Task(
        task_id="T5",
        form="B",
        kind="threshold",
        chart="map",
        years=(2007,),
        prompt=(
            "The map colours 11 countries in sub-Saharan Africa by their coverage in 2007. "
            "How many of those countries had coverage below 50%?"
        ),
        vaccine="DTP3",
        # Every country at least 10 points from 50% in 2007. Nigeria (42), Angola (43), the Central
        # African Republic (48), Ethiopia (50) and Niger (58) are too close to colour.
        entities=(
            "Cameroon",
            "Chad",
            "Democratic Republic of Congo",
            "Kenya",
            "Madagascar",
            "Mali",
            "Mozambique",
            "Somalia",
            "Tanzania",
            "Uganda",
            "Zambia",
        ),
        options=COUNT_OPTIONS,
    ),
    Task(
        task_id="T6",
        form="B",
        kind="crossing",
        prompt=(
            "Pakistan's coverage became higher than Mozambique's at some point. Roughly when did "
            "that first happen?"
        ),
        vaccine="DTP3",
        # No World line: it runs within 2 points of both lines at the 2019 crossing, and Pakistan
        # crosses it too, in 2021. docs/study-design.md section 4.
        entities=("Mozambique", "Pakistan"),
        options=CROSSING_BANDS,
    ),
)

FORMS: dict[str, tuple[Task, ...]] = {"A": FORM_A, "B": FORM_B}

JUSTIFICATION_PROMPT = "In one sentence, describe why you chose your answer."

# The first step's heading on a task screen, by item kind. The design handoff's wording.
CHOOSE_PROMPTS: dict[str, str] = {
    "practice": "Choose an answer:",
    "lowest": "Choose one year:",
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

# Asked after the INTERACTIVE condition only: the static condition has no controls to rate.
CONTROLS_SECTION = "Chart controls"
CONTROLS_HELP = "About the controls on the charts."
CONTROLS_ITEMS: dict[str, str] = {
    "b1": "I could figure out how to use the chart controls without instructions.",
    "b2": "The chart controls helped me answer the questions.",
    "b3": "The chart controls were easy to use.",
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
# Asked once, at the END, one question per page. The handoff's wording (`auBuild()`), verbatim. Not
# all broad categories: age in years and the two "Other" text boxes are on the IRB list in
# study-design.md section 10.

PREFER_NOT = "Prefer not to say"
OTHER = "Other"
AGE_RANGE = (18, 99)


@dataclass(frozen=True, slots=True)
class Question:
    """One About-you question.

    `kind` is "choice" (one of `options`), "age" (a whole number in `AGE_RANGE`, or `PREFER_NOT`)
    or "matrix" (one of `options` for each of `rows`). A choice whose options include `OTHER` has a
    text box beside it, logged under `other_key`. `prefer_not_inline` marks the one question whose
    "Prefer not to say" is an ordinary option rather than set apart beneath the others.
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
)

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
