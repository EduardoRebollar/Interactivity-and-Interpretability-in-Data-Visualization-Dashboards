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

from src import config, consent, figures
from src.tasks import (
    DEMOGRAPHIC_ITEMS,
    JUSTIFICATION_PROMPT,
    LIKERT_ANCHORS,
    LIKERT_ITEMS,
    LIKERT_POINTS,
)

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


def chart(
    entities: list[str],
    vaccine: str,
    interactive: bool,
    element_id: str = "chart",
    *,
    chart_type: str = "line",
    years: tuple[int, ...] = (),
):
    """The coverage chart. The figure is condition-independent; only the config differs.

    Wrapped in a container that holds the chart's height before Plotly has loaded. `dcc.Graph`
    loads Plotly on demand and renders at zero height until it arrives, so without the wrapper the
    answers and Submit jumped 520 px down the page while a participant might be clicking them.
    `docs/visual-spec.md` section 5.
    """
    height = f"{config.CHART_HEIGHT}px"
    return html.Div(
        dcc.Graph(
            id=element_id,
            figure=figures.build_figure(entities, vaccine, chart_type=chart_type, years=years),
            config=figures.graph_config(interactive),
            # Keeps the rendered size identical across conditions rather than letting the
            # modebar's presence shift the layout.
            style={"height": height},
        ),
        style={"height": height},
    )


SORT_KEYS = ("listed", "coverage")


def filterable(entities: list[str]) -> list[str]:
    """The entities a participant may hide.

    World is excluded: it is the dashed reference every task is read against, and several items ask
    directly about it. Letting it be switched off would let a participant remove the thing the
    question is about.
    """
    return [entity for entity in entities if entity != "World"]


def latest_values(entities: list[str], vaccine: str) -> dict[str, float | None]:
    """Each entity's most recently REPORTED value, which is not always the last year.

    Every continent aggregate is missing 2024, so keying off the final year alone would sort those
    series as if they had no data.
    """
    from src import runtime_data

    rows = runtime_data.load_rows()
    values: dict[str, float | None] = {}
    for entity in entities:
        observed = [
            row.coverage_pct
            for row in runtime_data.series(entity, vaccine, rows)
            if row.coverage_pct is not None
        ]
        values[entity] = observed[-1] if observed else None
    return values


def sorted_entities(entities: list[str], vaccine: str, sort_key: str) -> list[str]:
    """Control-list order. `listed` is the task's own order; `coverage` is highest-latest first."""
    if sort_key not in SORT_KEYS:
        raise ValueError(f"Unknown sort key {sort_key!r}; expected one of {SORT_KEYS}")
    if sort_key == "listed":
        return list(entities)
    values = latest_values(entities, vaccine)
    # An entity with nothing reported sorts last rather than crashing the comparison.
    return sorted(entities, key=lambda e: (values[e] is None, -(values[e] or 0), e))


def control_label(entity: str, value: float | None, sort_key: str) -> str:
    """Checkbox text. The latest value is shown only when the list is ordered BY that value.

    Sorting by coverage is meaningless without showing what it sorted on, but the default view has
    no reason to carry numbers — and leaving them out of it keeps the resting state of the two
    conditions closer.
    """
    if sort_key != "coverage":
        return entity
    return f"{entity} — {value:.0f}%" if value is not None else f"{entity} — not reported"


def entity_controls(task, sort_key: str, selected: list[str]) -> html.Div:
    """Filter, sort and reset. Rendered ONLY in the interactive condition.

    These are the study's independent variable. The chart they act on is the same chart the static
    condition sees; what differs is that it can be worked with rather than only looked at.

    Every control here is a native form element, so keyboard navigation comes for free — required by
    the accessibility baseline in CLAUDE.md. Do not reimplement any of them as styled divs.
    """
    options = filterable(list(task.entities))
    ordered = sorted_entities(options, task.vaccine, sort_key)
    values = latest_values(ordered, task.vaccine) if sort_key == "coverage" else {}

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Show:", style={**MUTED_STYLE, "marginRight": "8px"}),
                    dcc.Checklist(
                        id="entity-filter",
                        options=[
                            {"label": control_label(e, values.get(e), sort_key), "value": e}
                            for e in ordered
                        ],
                        value=[e for e in ordered if e in selected],
                        labelStyle={"display": "inline-block", "marginRight": "16px"},
                        inputStyle={"marginRight": "6px"},
                        style={"display": "inline-block"},
                    ),
                ],
                style={"marginBottom": "6px"},
            ),
            html.Div(
                [
                    html.Span("Order:", style={**MUTED_STYLE, "marginRight": "8px"}),
                    dcc.RadioItems(
                        id="entity-sort",
                        options=[
                            {"label": "as listed", "value": "listed"},
                            {"label": "by coverage", "value": "coverage"},
                        ],
                        value=sort_key,
                        labelStyle={"display": "inline-block", "marginRight": "16px"},
                        inputStyle={"marginRight": "6px"},
                        style={"display": "inline-block"},
                    ),
                    html.Button(
                        "Show all",
                        id="reset-view",
                        n_clicks=0,
                        style={
                            "fontFamily": config.FONT_FAMILY,
                            "fontSize": f"{config.FONT_SIZE_AXIS}px",
                            "padding": "4px 10px",
                            "marginLeft": "12px",
                            "color": config.TEXT_PRIMARY,
                            "backgroundColor": config.BACKGROUND,
                            "border": f"1px solid {config.AXIS_COLOR}",
                            "borderRadius": "4px",
                            "cursor": "pointer",
                        },
                    ),
                ]
            ),
            html.P(
                "Click a line to show it on its own; click it again, or Show all, to bring the "
                "others back.",
                style={**MUTED_STYLE, "margin": "6px 0 0 0"},
            ),
        ],
        style={"marginBottom": "12px"},
    )


def _small_button(label: str, element_id: str) -> html.Button:
    """The quiet button beside a control, like Show all. Native, so keyboard-navigable."""
    return html.Button(
        label,
        id=element_id,
        n_clicks=0,
        style={
            "fontFamily": config.FONT_FAMILY,
            "fontSize": f"{config.FONT_SIZE_AXIS}px",
            "padding": "4px 10px",
            "marginLeft": "12px",
            "color": config.TEXT_PRIMARY,
            "backgroundColor": config.BACKGROUND,
            "border": f"1px solid {config.AXIS_COLOR}",
            "borderRadius": "4px",
            "cursor": "pointer",
        },
    )


def _hint(text: str) -> html.P:
    return html.P(text, style={**MUTED_STYLE, "margin": "6px 0 0 0"})


def bar_controls(sort_key: str) -> html.Div:
    """Sort the bars. Rendered ONLY in the interactive condition, above a bar chart.

    Its own id, not `entity-sort`: a Dash callback whose Inputs are only partly on the page is dead
    in the browser, so the bar chart's control cannot share a callback with the line chart's three.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Order:", style={**MUTED_STYLE, "marginRight": "8px"}),
                    dcc.RadioItems(
                        id="bar-sort",
                        options=[
                            {"label": "as listed", "value": "listed"},
                            {"label": "by coverage", "value": "coverage"},
                        ],
                        value=sort_key,
                        labelStyle={"display": "inline-block", "marginRight": "16px"},
                        inputStyle={"marginRight": "6px"},
                        style={"display": "inline-block"},
                    ),
                ]
            ),
            _hint(
                "Order by coverage to sort the bars, highest first. Hover a bar to read its value."
            ),
        ],
        style={"marginBottom": "12px"},
    )


BAND_FULL = [0, 100]


def band_controls(band: list[int]) -> html.Div:
    """Show only the countries within a coverage range. Rendered ONLY in the interactive condition.

    The participant sets the range. A preset "below 50%" button was rejected (2026-09-23): it names
    the question's own threshold and would answer the item in one click. The slider's number boxes
    make it usable from the keyboard as well.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "Show countries with coverage between:",
                        style={**MUTED_STYLE, "marginRight": "8px"},
                    ),
                    _small_button("Show all", "band-reset"),
                ]
            ),
            html.Div(
                dcc.RangeSlider(
                    id="coverage-band",
                    min=BAND_FULL[0],
                    max=BAND_FULL[1],
                    step=1,
                    value=list(band),
                    marks={value: f"{value}%" for value in range(0, 101, 10)},
                    allowCross=False,
                ),
                style={"maxWidth": "640px", "marginTop": "6px"},
            ),
            _hint("Countries outside the range fade. Hover a country to read its name and value."),
        ],
        style={"marginBottom": "12px"},
    )


HOVER_HINTS = {
    "scatter": "Hover a dot to see which country it is and its values.",
    "heatmap": "Hover a cell to read its value.",
}


def task_controls(task) -> html.Div | None:
    """The interactive condition's controls for this task's chart, or None if it has none.

    One control set per chart type (visual-spec.md section 7). The scatter and the heatmap have no
    controls; their affordance is hover, which only a one-line hint announces.
    """
    if task.chart == "line":
        # Rendered fresh with every task. The view they act on lives in the app's `control-state`
        # store, which `app.control_step` keys to the task, so no task inherits the previous one's
        # filtering, sorting or isolation.
        return entity_controls(task, sort_key="listed", selected=filterable(list(task.entities)))
    if task.chart == "bar":
        return bar_controls("listed")
    if task.chart == "map":
        return band_controls(BAND_FULL)
    if task.chart in HOVER_HINTS:
        return html.Div(_hint(HOVER_HINTS[task.chart]), style={"marginBottom": "12px"})
    return None


def gap_note(
    entities: list[str], vaccine: str, years: tuple[int, ...] = (), chart_type: str = "line"
) -> html.P | None:
    """Name any series with unreported years, so absence is not read as zero coverage.

    The static condition has no tooltip to explain a gap, so this caption is the only channel
    available — and it must therefore appear in BOTH conditions to keep them identical.

    `years` limits the check to the years the chart shows; empty means all of them, as on a line.
    """
    from src import runtime_data

    rows = runtime_data.load_rows()
    incomplete = []
    for entity in entities:
        series = runtime_data.series(entity, vaccine, rows)
        missing = [
            r.year for r in series if r.coverage_pct is None and (not years or r.year in years)
        ]
        if missing:
            incomplete.append(f"{entity} ({_year_ranges(missing)})")

    if not incomplete:
        return None
    absence = {
        "line": "A break in a line",
        "bar": "A missing bar",
        "scatter": "A missing dot",
        "heatmap": "An empty cell",
        "map": "An uncoloured country",
    }[chart_type]
    return html.P(
        f"No data reported for: {'; '.join(incomplete)}. {absence} means the value was not "
        "reported, which is not the same as zero coverage.",
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


ERROR_STYLE = {
    "fontSize": f"{config.FONT_SIZE_BASE}px",
    "color": config.ERROR_COLOR,
    "marginTop": "12px",
    "minHeight": "1.4em",
}


def page(*children) -> html.Div:
    """Page chrome plus the one validation-error slot.

    `flow-error` is emitted on EVERY screen, not only the ones that can produce an error. A Dash
    callback resolves its outputs against whatever is in the DOM, so an error output present on some
    screens and not others is a latent failure on exactly the screens that need it most. One id,
    always present, is the version that cannot misfire.
    """
    return html.Div(
        [*children, html.Div(id="flow-error", style=ERROR_STYLE)],
        style=PAGE_STYLE,
    )


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


def secondary_button(label: str, element_id: str) -> html.Button:
    """The quieter action beside a primary one. A native button, so keyboard-navigable."""
    return html.Button(
        label,
        id=element_id,
        n_clicks=0,
        style={
            "fontFamily": config.FONT_FAMILY,
            "fontSize": f"{config.FONT_SIZE_BASE}px",
            "padding": "9px 18px",
            "color": config.TEXT_PRIMARY,
            "backgroundColor": config.BACKGROUND,
            "border": f"1px solid {config.AXIS_COLOR}",
            "borderRadius": "4px",
            "cursor": "pointer",
            "marginTop": "16px",
            "marginLeft": "12px",
        },
    )


FIELD_STYLE = {
    "fontFamily": config.FONT_FAMILY,
    "fontSize": f"{config.FONT_SIZE_BASE}px",
    "padding": "10px",
    "width": "320px",
    "maxWidth": "100%",
    "boxSizing": "border-box",
}

LABEL_STYLE = {"display": "block", "fontWeight": "600", "margin": "16px 0 6px 0"}

SUBHEADING_STYLE = {
    "fontSize": f"{config.FONT_SIZE_BASE + 2}px",
    "fontWeight": "600",
    "margin": "20px 0 6px 0",
}

SKIP_NOTE = "You may skip any question. If you leave one unanswered, you will be asked to confirm."


def choice_question(element_id: str, question: str, options) -> html.Div:
    """A question and its radio options. Native radios: keyboard-navigable (CLAUDE.md baseline)."""
    return html.Div(
        [
            html.P(question, style={**PROMPT_STYLE, "fontWeight": "600", "margin": "20px 0 8px"}),
            dcc.RadioItems(
                id=element_id,
                options=options,
                value=None,
                labelStyle={"display": "block", "margin": "6px 0"},
                inputStyle={"marginRight": "8px"},
            ),
        ]
    )


# --- Study flow screens --------------------------------------------------------------------------
#
# Every screen is identical across conditions. The only permitted divergence is the Plotly config
# passed to `chart()`, plus the interactive-only controls, which render only when `interactive`.


def consent_screen() -> html.Div:
    """The Occidental informed consent form, then name, date, signature, agree or decline.

    IRB form item 12A: typed name and date, a signature, and an explicit "I agree to participate".
    Item 12B: declining must be possible and must lead somewhere that says no data was collected.

    The signature pad (`src/assets/signature.js`) cannot be used from a keyboard. The paper-copy box
    is the alternative, and it is a native checkbox: a participant who cannot draw signs the paper
    form the researcher brings, which item 12A already provides for.
    """
    banner = (
        []
        if consent.APPROVED
        else [
            html.P(
                "PENDING HSRRC APPROVAL — this consent form has not been approved. Do not run "
                "participants.",
                style={
                    **PROMPT_STYLE,
                    "fontWeight": "600",
                    "color": config.ERROR_COLOR,
                    "border": f"2px solid {config.ERROR_COLOR}",
                    "padding": "10px",
                },
            )
        ]
    )
    body = []
    for section_heading, text in consent.SECTIONS:
        if section_heading:
            body.append(html.H2(section_heading, style=SUBHEADING_STYLE))
        body.append(html.P(text, style=PROMPT_STYLE))

    return page(
        heading("Informed consent"),
        *banner,
        html.P("Occidental College — Informed Consent Form", style=MUTED_STYLE),
        *body,
        html.Label("Printed name", htmlFor="consent-name", style=LABEL_STYLE),
        dcc.Input(id="consent-name", type="text", autoComplete="name", style=FIELD_STYLE),
        html.Label("Date", htmlFor="consent-date", style=LABEL_STYLE),
        dcc.Input(id="consent-date", type="date", style=FIELD_STYLE),
        html.Label("Signature", htmlFor="signature-pad", style=LABEL_STYLE),
        html.P(
            "Sign in the box with your mouse, trackpad or finger.",
            style={**MUTED_STYLE, "margin": "0 0 6px 0"},
        ),
        html.Canvas(
            id="signature-pad",
            width=consent.PAD_WIDTH,
            height=consent.PAD_HEIGHT,
            style={
                "display": "block",
                "width": "100%",
                "maxWidth": f"{consent.PAD_WIDTH}px",
                "aspectRatio": f"{consent.PAD_WIDTH} / {consent.PAD_HEIGHT}",
                "border": f"1px solid {config.AXIS_COLOR}",
                "borderRadius": "4px",
                "backgroundColor": config.BACKGROUND,
                # The pen colour: the pad's script draws in the canvas's computed `color`.
                "color": config.TEXT_PRIMARY,
                # Without this a finger on a touchscreen scrolls the page instead of signing.
                "touchAction": "none",
                "cursor": "crosshair",
            },
        ),
        html.Button(
            "Clear signature",
            id="signature-clear",
            n_clicks=0,
            style={
                "fontFamily": config.FONT_FAMILY,
                "fontSize": f"{config.FONT_SIZE_AXIS}px",
                "padding": "4px 10px",
                "marginTop": "6px",
                "color": config.TEXT_PRIMARY,
                "backgroundColor": config.BACKGROUND,
                "border": f"1px solid {config.AXIS_COLOR}",
                "borderRadius": "4px",
                "cursor": "pointer",
            },
        ),
        dcc.Checklist(
            id="consent-paper",
            options=[
                {
                    "label": "I have signed a paper copy of this form with the researcher instead",
                    "value": "paper",
                }
            ],
            value=[],
            inputStyle={"marginRight": "8px"},
            style={"marginTop": "12px"},
        ),
        html.Div(
            [
                primary_button("I agree to participate", "consent-button"),
                secondary_button("I do not agree", "decline-button"),
            ]
        ),
    )


def declined_screen() -> html.Div:
    """IRB form item 12B. Nothing is written before consent, so the second sentence is true."""
    return page(
        heading("Thank you for your time"),
        html.P(
            "You chose not to take part in this study. No data has been collected. You can close "
            "this tab.",
            style=PROMPT_STYLE,
        ),
        html.P(
            "If you chose this by mistake, you can go back to the consent form.",
            style=MUTED_STYLE,
        ),
        secondary_button("Go back to the consent form", "reconsider-button"),
    )


def participant_screen() -> html.Div:
    return page(
        heading("Participant ID"),
        # The copy is held in a memory store and lost on reload; the researcher can send one then.
        html.P(
            "Thank you for signing. You can keep a copy of the consent form you signed.",
            style=PROMPT_STYLE,
        ),
        html.Button(
            "Download your signed consent form",
            id="consent-copy-button",
            n_clicks=0,
            style={
                "fontFamily": config.FONT_FAMILY,
                "fontSize": f"{config.FONT_SIZE_AXIS}px",
                "padding": "6px 12px",
                "marginBottom": "20px",
                "color": config.TEXT_PRIMARY,
                "backgroundColor": config.BACKGROUND,
                "border": f"1px solid {config.AXIS_COLOR}",
                "borderRadius": "4px",
                "cursor": "pointer",
            },
        ),
        # Resume is not implemented, so this must not promise it. docs/study-design.md section 8.
        html.P(
            "Enter the ID you were given. Please complete the study in one sitting, in this tab "
            "— closing it ends your session.",
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
        primary_button("Continue", "participant-button"),
    )


def demographics_screen() -> html.Div:
    """Broad-category background questions, once per participant. study-design.md section 6.2."""
    questions = [
        choice_question(f"demo-{key}", question, [{"label": o, "value": o} for o in options])
        for key, (question, options) in DEMOGRAPHIC_ITEMS.items()
    ]
    return page(
        heading("About you"),
        html.P(
            "A few questions about your background. The answers are broad categories and cannot "
            "identify you.",
            style=PROMPT_STYLE,
        ),
        html.P(SKIP_NOTE, style=MUTED_STYLE),
        *questions,
        primary_button("Continue", "demographics-button"),
    )


def instructions_screen(interactive: bool, practice: bool = False) -> html.Div:
    """Instructions. The wording differs by condition ONLY in describing what the chart can do.

    Describing controls that are not present, or failing to describe controls that are, would be a
    procedural difference rather than a visual one — but it has to be accurate or the interactive
    condition is handicapped by not knowing its affordances exist.

    **Shown before BOTH conditions.** `practice=True` marks the first, which is the only one leading
    into the practice item. The second condition reaches this screen from the break, and needs it
    precisely because its affordances differ from the first's — a participant who gets the
    interactive version second would otherwise never learn the controls exist.
    """
    shared = (
        "You will see charts of childhood vaccination coverage — line charts, a bar chart, a "
        "scatter plot, a grid of coloured cells and a map — and answer a question about each. "
        "After each question you will be asked, in one sentence, how you decided."
    )
    specific = (
        "You can hover over any line, bar, dot, cell or country to read its exact value; on a "
        "line chart you also see its change from the year before. Some charts have controls "
        "above them: on line charts you can filter, sort and isolate countries, on the bar chart "
        "you can sort the bars, and on the map you can show only the countries within a coverage "
        "range."
        if interactive
        else "The charts are images: read values against the gridlines, or against the colour "
        "key where there is one."
    )
    intro = (
        []
        if practice
        else [
            html.P(
                "This half uses a different version of the chart from the one you have just used. "
                "Please read on — what the chart can do has changed.",
                style={**PROMPT_STYLE, "fontWeight": "600"},
            )
        ]
    )
    return page(
        heading("Instructions"),
        *intro,
        html.P(shared, style=PROMPT_STYLE),
        html.P(specific, style=PROMPT_STYLE),
        html.P(
            "A break in a line means no value was reported for those years.",
            style=PROMPT_STYLE,
        ),
        html.P(SKIP_NOTE, style=PROMPT_STYLE),
        primary_button(
            "Start the practice question" if practice else "Start the questions", "begin-button"
        ),
    )


def task_screen(
    task, interactive: bool, index: int, total: int, practice: bool = False
) -> html.Div:
    """One task: prompt, chart, answer options, justification.

    The practice item uses this same screen, so what it teaches is the interface the scored tasks
    actually use.
    """
    position = "Practice — not scored" if practice else f"Question {index} of {total}"
    children = [
        html.P(position, style=MUTED_STYLE),
        html.P(task.prompt, style={**PROMPT_STYLE, "fontWeight": "600"}),
    ]

    # The controls are the interactive condition's whole point, and the static condition renders
    # nothing in their place. The CHART is identical either way: at first render every series is
    # shown, in the listed order, unfiltered, so both conditions open on the same picture.
    if interactive:
        controls = task_controls(task)
        if controls is not None:
            children.append(controls)

    children.append(
        chart(
            list(task.entities),
            task.vaccine,
            interactive,
            chart_type=task.chart,
            years=task.years,
        )
    )

    note = gap_note(list(task.entities), task.vaccine, task.years, task.chart)
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
        primary_button("Submit", "submit-button"),
    ]
    return page(*children)


def load_screen(prompt: str, anchors: dict[int, str]) -> html.Div:
    """The post-condition survey, asked after EACH condition. study-design.md section 6.1.

    Paas mental effort (the RQ3 measure) first, then the three 7-point Likert items. The screen is
    identical in both conditions; the statements say "in this part", never which version it was.
    """
    likert = [
        choice_question(
            f"likert-{key}",
            statement,
            [
                {
                    "label": f"{n} — {LIKERT_ANCHORS[n]}" if n in LIKERT_ANCHORS else str(n),
                    "value": n,
                }
                for n in range(1, LIKERT_POINTS + 1)
            ],
        )
        for key, statement in LIKERT_ITEMS.items()
    ]
    return page(
        heading("A few quick questions about this part"),
        html.P(SKIP_NOTE, style=MUTED_STYLE),
        choice_question(
            "load-input",
            prompt,
            [
                {"label": f"{n} — {anchors[n]}" if n in anchors else str(n), "value": n}
                for n in range(1, 10)
            ],
        ),
        html.P(
            "How much do you agree with each statement? "
            f"1 = {LIKERT_ANCHORS[1]}, {LIKERT_POINTS} = {LIKERT_ANCHORS[LIKERT_POINTS]}.",
            style={**PROMPT_STYLE, "marginTop": "28px"},
        ),
        *likert,
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
        # Its own id, not `begin-button`: this leads to the second condition's INSTRUCTIONS, whereas
        # `begin-button` starts the tasks. Sharing an id would make the two indistinguishable in the
        # callback and is how the second condition lost its instructions in the first place.
        primary_button("Continue", "resume-button"),
    )


def complete_screen(participant_id: str | None = None) -> html.Div:
    """The end, with the withdrawal right IRB form item 13 promises to remind participants of."""
    who = f" (your participant ID is {participant_id})" if participant_id else ""
    return page(
        heading("Finished — thank you"),
        html.P(
            "Your responses have been recorded. You can close this tab.",
            style=PROMPT_STYLE,
        ),
        html.P(
            "If you change your mind, you can withdraw your responses within two weeks of today, "
            f"without giving a reason. Email {consent.RESEARCHER_EMAIL} and include your "
            f"participant ID{who}.",
            style=PROMPT_STYLE,
        ),
    )
