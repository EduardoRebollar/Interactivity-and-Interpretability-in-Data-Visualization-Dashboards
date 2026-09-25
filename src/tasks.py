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

from src.flow import Task

COUNT_OPTIONS = ("0", "1", "2", "3", "4 or more")

# The crossing item's options. Bands rather than years, because the static condition has no hover
# and an exact crossing year cannot be read from the chart. Inclusive at both ends, contiguous.
CROSSING_BANDS = ("2004-2008", "2009-2012", "2013-2016", "2017-2020", "2021-2024")

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
        # Eight countries and World: the tangle the isolation control cuts through.
        entities=(
            "Brazil",
            "China",
            "Ethiopia",
            "India",
            "Indonesia",
            "Nigeria",
            "Pakistan",
            "Ukraine",
            "World",
        ),
        # Not 2010 or 2013: Ukraine is 23 in 2014 and 2015, too close to its low of 19 in 2016 to
        # tell apart, and both years sit nearer 2013 than 2016. docs/study-design.md section 4.
        options=("2008", "2016", "2019", "2022", "2024"),
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
        options=("Brazil", "China", "Ethiopia", "India", "Vietnam"),
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
        options=("Burkina Faso", "Chad", "Ethiopia", "Mali", "Niger"),
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
        options=("Burkina Faso", "Central African Republic", "Chad", "Mali", "Pakistan"),
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
            "World",
        ),
        options=("2009", "2013", "2017", "2021", "2024"),
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
        options=("Cambodia", "Colombia", "Egypt", "Ethiopia", "United States"),
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
        options=("Bangladesh", "Cambodia", "India", "Nepal", "Pakistan"),
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
        options=("Afghanistan", "Mali", "Niger", "Pakistan", "Uganda"),
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
