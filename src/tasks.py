"""The task set. Implements `docs/study-design.md` section 4. No pandas — this ships to production.

Two isomorphic forms, A and B: same six task types in the same order, matched effect sizes, over
different data. A participant sees one form per condition and never the same form twice, so nobody
answers a question they have already answered.

**No correct answers live in this module.** It is serialised to the browser, where an answer key
would be readable in the page source. Scoring happens offline against the rubric in
`docs/study-design.md` section 7.

Every value referenced in a prompt was verified against `data/deploy/coverage.csv`. Change the
design document first, then this file.
"""

from __future__ import annotations

from src.flow import Task

# Answer options shared by the two crossing items. Bands rather than years, because the static
# condition has no hover and an exact crossing year is not readable from the chart.
CROSSING_BANDS = ("2004-2008", "2009-2012", "2013-2016", "2017-2020", "2021-2024")

GAP_OPTIONS = (
    "Coverage was not reported for those years",
    "Coverage was zero for those years",
    "Coverage was very low but above zero",
    "Coverage was high and steady",
)

COUNT_OPTIONS = ("0", "1", "2", "3", "4 or more")

# The practice item is identical in both forms and is not scored. Ukraine's collapse is unmissable,
# so it teaches the interface rather than the concept. It deliberately shows NO missing data, so it
# cannot contaminate T6, which is the item that tests gap reasoning.
PRACTICE = Task(
    task_id="P0",
    form="both",
    kind="practice",
    prompt=(
        "Practice (not scored). Look at Ukraine's line. Did coverage rise, fall, or stay level "
        "between 2008 and 2016?"
    ),
    vaccine="DTP3",
    entities=("Ukraine", "World"),
    options=("It rose", "It fell", "It stayed about level"),
)

FORM_A: tuple[Task, ...] = (
    Task(
        task_id="T1",
        form="A",
        kind="reference",
        prompt=(
            "The dashed black line is the world average. In 2010, how many of the countries shown "
            "were above it?"
        ),
        vaccine="DTP3",
        entities=("Brazil", "Nigeria", "Ethiopia", "India", "Indonesia", "World"),
        options=COUNT_OPTIONS,
    ),
    Task(
        task_id="T2",
        form="A",
        kind="trend",
        prompt="Between 2015 and 2021, which country's coverage fell the most?",
        vaccine="DTP3",
        entities=("Brazil", "Indonesia", "India", "United States", "Nigeria", "World"),
        options=("Brazil", "Indonesia", "India", "United States", "Nigeria"),
    ),
    Task(
        task_id="T3",
        form="A",
        kind="trend",
        prompt="Between 2000 and 2012, which country improved the most?",
        vaccine="DTP3",
        entities=("Ethiopia", "India", "China", "Indonesia", "Brazil", "World"),
        options=("Ethiopia", "India", "China", "Indonesia", "Brazil"),
    ),
    Task(
        task_id="T4",
        form="A",
        kind="crossing",
        prompt=("India's coverage overtook Brazil's at some point. Roughly when did that happen?"),
        vaccine="DTP3",
        entities=("Brazil", "India", "World"),
        options=CROSSING_BANDS,
    ),
    Task(
        task_id="T5",
        form="A",
        kind="crossing",
        prompt="China's coverage overtook Brazil's at some point. Roughly when did that happen?",
        vaccine="DTP3",
        entities=("Brazil", "China", "World"),
        options=CROSSING_BANDS,
    ),
    Task(
        task_id="T6",
        form="A",
        kind="gap",
        prompt=(
            "Look at the United Kingdom's hepatitis B line before 2019. What can you say about "
            "coverage in those years?"
        ),
        vaccine="HepB3",
        entities=("United Kingdom", "United States", "Brazil", "World"),
        options=GAP_OPTIONS,
    ),
)

FORM_B: tuple[Task, ...] = (
    Task(
        task_id="T1",
        form="B",
        kind="reference",
        prompt=(
            "The dashed black line is the world average. In 2020, how many of the countries shown "
            "were above it?"
        ),
        vaccine="DTP3",
        entities=("Brazil", "Nigeria", "Ethiopia", "India", "Indonesia", "World"),
        options=COUNT_OPTIONS,
    ),
    Task(
        task_id="T2",
        form="B",
        kind="trend",
        prompt="Between 2010 and 2014, which country's coverage fell the most?",
        vaccine="DTP3",
        entities=("Ukraine", "Nigeria", "Brazil", "Pakistan", "India", "World"),
        options=("Ukraine", "Nigeria", "Brazil", "Pakistan", "India"),
    ),
    Task(
        task_id="T3",
        form="B",
        kind="trend",
        prompt="Between 2012 and 2024, which country improved the most?",
        vaccine="DTP3",
        entities=("Nigeria", "Pakistan", "India", "Ethiopia", "Indonesia", "World"),
        options=("Nigeria", "Pakistan", "India", "Ethiopia", "Indonesia"),
    ),
    Task(
        task_id="T4",
        form="B",
        kind="crossing",
        prompt="India's coverage overtook Ukraine's at some point. Roughly when did that happen?",
        vaccine="DTP3",
        entities=("India", "Ukraine", "World"),
        options=CROSSING_BANDS,
    ),
    Task(
        task_id="T5",
        form="B",
        kind="crossing",
        prompt="China's coverage overtook Ukraine's at some point. Roughly when did that happen?",
        vaccine="DTP3",
        entities=("Ukraine", "China", "World"),
        options=CROSSING_BANDS,
    ),
    Task(
        task_id="T6",
        form="B",
        kind="gap",
        prompt=(
            "Look at the hepatitis B lines for Ethiopia, Nigeria and India in the early years. "
            "What can you say about coverage before each line begins?"
        ),
        vaccine="HepB3",
        entities=("Ethiopia", "Nigeria", "India", "Brazil", "World"),
        options=GAP_OPTIONS,
    ),
)

FORMS: dict[str, tuple[Task, ...]] = {"A": FORM_A, "B": FORM_B}

JUSTIFICATION_PROMPT = "In one sentence, how did you decide?"

# Paas single-item mental effort, asked once per condition. See docs/study-design.md section 6.
LOAD_PROMPT = "In solving the preceding tasks, I invested:"
LOAD_ANCHORS = {1: "very, very low mental effort", 9: "very, very high mental effort"}

# The rest of the post-condition survey: 7-point agreement items, asked after EACH condition, as the
# consent form states. See docs/study-design.md section 6.1. Key -> statement.
LIKERT_ITEMS: dict[str, str] = {
    "clarity": "The charts in this part made the information clear.",
    "ease_of_use": "The charts in this part were easy to use.",
    "confidence": "I am confident in my answers in this part.",
}
LIKERT_ANCHORS = {1: "strongly disagree", 4: "neither agree nor disagree", 7: "strongly agree"}
LIKERT_POINTS = 7

# Asked once, after the participant ID. Broad categories only (IRB form item 17), so no answer can
# re-identify anyone. See docs/study-design.md section 6.2. Key -> (question, options).
PREFER_NOT = "Prefer not to say"
DEMOGRAPHIC_ITEMS: dict[str, tuple[str, tuple[str, ...]]] = {
    "age_range": (
        "What is your age range?",
        ("18–24", "25–34", "35–44", "45–54", "55–64", "65 or older", PREFER_NOT),
    ),
    "field": (
        "What is your main field of study or work?",
        (
            "Arts and humanities",
            "Social sciences",
            "Natural sciences",
            "Mathematics, statistics or computer science",
            "Engineering",
            "Health or medicine",
            "Business or economics",
            "Education",
            "Other",
            PREFER_NOT,
        ),
    ),
    "chart_frequency": (
        "How often do you read charts or graphs, for example in the news, at work, or in class?",
        (
            "Never",
            "Less than once a month",
            "A few times a month",
            "A few times a week",
            "Daily",
            PREFER_NOT,
        ),
    ),
    "dashboard_familiarity": (
        "How familiar are you with interactive data dashboards, such as Tableau, Power BI, or "
        "online COVID-19 trackers?",
        (
            "Not at all familiar",
            "Slightly familiar",
            "Moderately familiar",
            "Very familiar",
            "Extremely familiar",
            PREFER_NOT,
        ),
    ),
}


def for_form(form: str) -> tuple[Task, ...]:
    """The six scored tasks for one form, in presentation order."""
    if form not in FORMS:
        raise KeyError(f"Unknown form {form!r}; expected one of {sorted(FORMS)}")
    return FORMS[form]
