"""Shared layout components and the study flow screens. No pandas — this ships to production.

Every screen is used by BOTH conditions. Only two things branch on `interactive`:

1. The Plotly config passed to `chart()` — `figures.graph_config`, the single decision point.
2. `instructions_screen`, which must describe the affordances that actually exist. Telling static
   participants about hover, or failing to tell interactive participants, would handicap one
   condition procedurally. That is a difference in instructions, not in the visual design.

Nothing else may differ. `tests/test_conditions.py` enforces the figure half of that.
"""

from __future__ import annotations

from dash import dcc, html

from src import config, figures
from src.tasks import JUSTIFICATION_PROMPT

# Shared page chrome, so both conditions are laid out identically.
PAGE_STYLE = {
    "fontFamily": config.FONT_FAMILY,
    "fontSize": f"{config.FONT_SIZE_BASE}px",
    "color": config.TEXT_PRIMARY,
    "backgroundColor": config.BACKGROUND,
    "maxWidth": "1100px",
    "margin": "0 auto",
    "padding": "24px",
}

PROMPT_STYLE = {
    "fontSize": f"{config.FONT_SIZE_BASE + 2}px",
    "lineHeight": "1.5",
    "margin": "0 0 16px 0",
}

MUTED_STYLE = {"color": config.TEXT_MUTED, "fontSize": f"{config.FONT_SIZE_AXIS}px"}


def chart(entities: list[str], vaccine: str, interactive: bool, element_id: str = "chart"):
    """The coverage chart. The figure is condition-independent; only the config differs."""
    return dcc.Graph(
        id=element_id,
        figure=figures.build_figure(entities, vaccine),
        config=figures.graph_config(interactive),
        # Keeps the rendered size identical across conditions rather than letting the
        # modebar's presence shift the layout.
        style={"height": f"{config.CHART_HEIGHT}px"},
    )


def gap_note(entities: list[str], vaccine: str) -> html.P | None:
    """Name any series with unreported years, so absence is not read as zero coverage.

    The static condition has no tooltip to explain a gap, so this caption is the only channel
    available — and it must therefore appear in BOTH conditions to keep them identical.
    """
    from src import runtime_data

    rows = runtime_data.load_rows()
    incomplete = []
    for entity in entities:
        series = runtime_data.series(entity, vaccine, rows)
        missing = [r.year for r in series if r.coverage_pct is None]
        if missing:
            incomplete.append(f"{entity} ({_year_ranges(missing)})")

    if not incomplete:
        return None
    return html.P(
        f"No data reported for: {'; '.join(incomplete)}. A break in a line means the value was "
        "not reported, which is not the same as zero coverage.",
        style=MUTED_STYLE,
    )


def _year_ranges(years: list[int]) -> str:
    """Compress [2000, 2001, 2002, 2005] to '2000-2002, 2005'."""
    if not years:
        return ""
    ordered = sorted(years)
    spans: list[tuple[int, int]] = [(ordered[0], ordered[0])]
    for year in ordered[1:]:
        start, end = spans[-1]
        if year == end + 1:
            spans[-1] = (start, year)
        else:
            spans.append((year, year))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def page(*children) -> html.Div:
    return html.Div(children, style=PAGE_STYLE)


def heading(text: str) -> html.H1:
    return html.H1(
        text,
        style={
            "fontSize": f"{config.FONT_SIZE_TITLE + 4}px",
            "fontWeight": "600",
            "margin": "0 0 16px 0",
        },
    )


def primary_button(label: str, element_id: str, disabled: bool = False) -> html.Button:
    """Keyboard-navigable by default; do not replace with a div."""
    return html.Button(
        label,
        id=element_id,
        n_clicks=0,
        disabled=disabled,
        style={
            "fontFamily": config.FONT_FAMILY,
            "fontSize": f"{config.FONT_SIZE_BASE}px",
            "padding": "10px 20px",
            "color": config.BACKGROUND,
            "backgroundColor": config.TEXT_MUTED if disabled else config.SERIES_COLORS[0],
            "border": "none",
            "borderRadius": "4px",
            "cursor": "not-allowed" if disabled else "pointer",
            "marginTop": "16px",
        },
    )


# --- Study flow screens --------------------------------------------------------------------------
#
# Every screen is identical across conditions. The only permitted divergence is the Plotly config
# passed to `chart()`, plus the interactive-only controls, which render only when `interactive`.


def consent_screen(text: str) -> html.Div:
    """Consent. `text` comes from docs/study-design.md and is a DRAFT until IRB approves it."""
    paragraphs = [
        html.P(line.strip(), style=PROMPT_STYLE) for line in text.split("\n\n") if line.strip()
    ]
    return page(
        heading("Before you begin"),
        *paragraphs,
        primary_button("I agree — begin", "consent-button"),
    )


def participant_screen() -> html.Div:
    return page(
        heading("Participant ID"),
        html.P(
            "Enter the ID you were given. If you are returning to finish a session, enter the same "
            "ID and you will continue where the study left off.",
            style=PROMPT_STYLE,
        ),
        dcc.Input(
            id="participant-input",
            type="text",
            debounce=True,
            placeholder="e.g. P07",
            style={
                "fontFamily": config.FONT_FAMILY,
                "fontSize": f"{config.FONT_SIZE_BASE}px",
                "padding": "10px",
                "width": "220px",
            },
        ),
        html.Div(id="participant-error", style={**MUTED_STYLE, "color": config.SERIES_COLORS[2]}),
        primary_button("Continue", "participant-button"),
    )


def instructions_screen(interactive: bool, practice: bool = False) -> html.Div:
    """Instructions. The wording differs by condition ONLY in describing what the chart can do.

    Describing controls that are not present, or failing to describe controls that are, would be a
    procedural difference rather than a visual one — but it has to be accurate or the interactive
    condition is handicapped by not knowing its affordances exist.
    """
    shared = (
        "You will see line charts of childhood vaccination coverage and answer a question about "
        "each. After each question you will be asked, in one sentence, how you decided."
    )
    specific = (
        "You can hover a line to read its exact value, and use the controls above the chart to "
        "filter and isolate countries."
        if interactive
        else "The charts are images: read the values against the gridlines."
    )
    return page(
        heading("Instructions"),
        html.P(shared, style=PROMPT_STYLE),
        html.P(specific, style=PROMPT_STYLE),
        html.P(
            "A break in a line means no value was reported for those years.",
            style=PROMPT_STYLE,
        ),
        primary_button("Start the practice question" if practice else "Continue", "begin-button"),
    )


def task_screen(task, interactive: bool, index: int, total: int) -> html.Div:
    """One task: prompt, chart, answer options, justification."""
    children = [
        html.P(f"Question {index} of {total}", style=MUTED_STYLE),
        html.P(task.prompt, style={**PROMPT_STYLE, "fontWeight": "600"}),
        chart(list(task.entities), task.vaccine, interactive),
    ]

    note = gap_note(list(task.entities), task.vaccine)
    if note is not None:
        children.append(note)

    children += [
        dcc.RadioItems(
            id="answer-input",
            options=[{"label": o, "value": o} for o in task.options],
            value=None,
            labelStyle={"display": "block", "margin": "6px 0"},
            inputStyle={"marginRight": "8px"},
        ),
        html.P(JUSTIFICATION_PROMPT, style={**PROMPT_STYLE, "marginTop": "16px"}),
        dcc.Textarea(
            id="justification-input",
            style={
                "fontFamily": config.FONT_FAMILY,
                "fontSize": f"{config.FONT_SIZE_BASE}px",
                "width": "100%",
                "height": "70px",
                "padding": "8px",
            },
        ),
        html.Div(id="task-error", style={**MUTED_STYLE, "color": config.SERIES_COLORS[2]}),
        primary_button("Submit", "submit-button"),
    ]
    return page(*children)


def load_screen(prompt: str, anchors: dict[int, str]) -> html.Div:
    """Paas single-item mental effort, asked once per condition."""
    return page(
        heading("One quick question"),
        html.P(prompt, style={**PROMPT_STYLE, "fontWeight": "600"}),
        dcc.RadioItems(
            id="load-input",
            options=[
                {"label": f"{n} — {anchors[n]}" if n in anchors else str(n), "value": n}
                for n in range(1, 10)
            ],
            value=None,
            labelStyle={"display": "block", "margin": "6px 0"},
            inputStyle={"marginRight": "8px"},
        ),
        html.Div(id="load-error", style={**MUTED_STYLE, "color": config.SERIES_COLORS[2]}),
        primary_button("Continue", "load-button"),
    )


def break_screen() -> html.Div:
    return page(
        heading("Halfway"),
        html.P(
            "That is the first half finished. The next set uses a different version of the chart "
            "and different questions. Take a moment, then continue when you are ready.",
            style=PROMPT_STYLE,
        ),
        primary_button("Continue", "begin-button"),
    )


def complete_screen() -> html.Div:
    return page(
        heading("Finished — thank you"),
        html.P(
            "Your responses have been recorded. You can close this tab.",
            style=PROMPT_STYLE,
        ),
    )
