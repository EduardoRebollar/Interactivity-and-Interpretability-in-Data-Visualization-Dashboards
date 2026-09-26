"""Shared layout components and the study flow screens. No pandas — this ships to production.

Every screen is used by BOTH conditions. Only these branch on `interactive`:

1. The Plotly config passed to `chart()` — `figures.graph_config`, the single decision point.
2. The task screen's controls strip and hint row (`task_controls`, `hint_row`), which exist only in
   the interactive condition and sit under the chart, so the chart is in the same place in both.
3. `instructions_screen`, which must describe the affordances that actually exist. Telling static
   participants about hover, or failing to tell interactive participants, would handicap one
   condition procedurally. That is a difference in instructions, not in the visual design.
4. `load_screen`, which asks about the chart controls only after the condition that had them.

Nothing else may differ. `tests/test_conditions.py` enforces the figure half of that.

The look comes from `src/assets/study.css`, the design handoff's stylesheet, copied unchanged,
with `src/assets/zz-bridge.css` (generated) and `src/assets/zz-overrides.css` for what Dash 4's
markup needs (docs/visual-spec.md section 10). Every screen sits in `shell`: the header band, the
stepper, and the page's background. The short screens are `stage_page`. Screens not yet rebuilt on
the stylesheet's classes (consent, the survey, About you) use `interim_page`, the old look in a
white box, until their phase of docs/study-redesign.md.
"""

from __future__ import annotations

from dash import dcc, html

from src import config, consent, figures, flow, tasks
from src.tasks import (
    ABOUT_INTRO,
    ABOUT_SECTIONS,
    COMPARISON_CHOICES,
    COMPARISON_OPTIONS,
    COMPARISON_SECTION,
    COMPARISON_TEXT,
    COMPARISON_TEXT_HELP,
    COMPARISON_TEXT_KEY,
    CONTROLS_HELP,
    CONTROLS_ITEMS,
    CONTROLS_SECTION,
    EXPERIENCE_SECTION,
    JUSTIFICATION_PROMPT,
    LIKERT_ANCHORS,
    LIKERT_ITEMS,
    LIKERT_POINTS,
    LOAD_ANCHORS,
    LOAD_PROMPT,
    OTHER,
    PREFER_NOT,
    SKIP_NOTE,
    SURVEY_INTRO,
)

TITLE = "Vaccination coverage study"

# The page's background, by the class on the app root (the handoff's Screens file): none behind a
# chart, a slow sand fade on the other screens, and a warmer one at the three milestones.
BACKGROUNDS = {"plain": "app", "deco": "app app--deco", "celebrate": "app app--celebrate"}


def stepper(current: int) -> html.Ol:
    """The header's seven steps, `flow.STEPS`. Orientation only: plain list items, not links, so
    nothing in it can be clicked or tabbed to. Steps before the current one are ticked."""
    if not 0 <= current < len(flow.STEPS):
        raise ValueError(f"Step {current} is not one of the {len(flow.STEPS)} steps")
    items = []
    for index, label in enumerate(flow.STEPS):
        if index < current:
            items.append(html.Li(label, className="is-done"))
        elif index == current:
            items.append(html.Li(label, **{"aria-current": "step"}))
        else:
            items.append(html.Li(label))
    return html.Ol(items, className="steps")


def shell(step: int, background: str, screen) -> html.Div:
    """Every screen's frame: the app root with its background, then the header band with the title
    and the stepper, then the screen itself.

    Identical in both conditions: the step and the background come from the stage and the half,
    never from the condition. Compact mode, for a window 800 px tall or less, is a media query in
    `zz-overrides.css`, so it applies before the screen first paints.
    """
    if background not in BACKGROUNDS:
        raise ValueError(f"Unknown background {background!r}; expected one of {list(BACKGROUNDS)}")
    return html.Div(
        [
            html.Header(
                [
                    html.P(TITLE, className="appbar-title"),
                    html.Div(stepper(step), className="appbar-right"),
                ],
                className="appbar",
            ),
            screen,
        ],
        className=BACKGROUNDS[background],
    )


# Today's look for a screen's content, inside the shell's `.page`, until its phase of
# docs/study-redesign.md rebuilds it on the stylesheet's classes. Both conditions alike.
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


def chart(task, interactive: bool, element_id: str = "chart") -> html.Div:
    """A task's chart, 1050 x 520. The figure is condition-independent; only the config differs.

    Its container, `.ui-chart`, holds the chart's size before Plotly has loaded. `dcc.Graph` loads
    Plotly on demand and renders at zero height until it arrives, so without it the answers and
    Submit jumped 520 px while a participant might be clicking them (visual-spec.md section 5).
    Not responsive: the figure sets its own size, the same on every screen.
    """
    return html.Div(
        dcc.Graph(
            id=element_id,
            figure=figures.task_figure(task),
            config=figures.graph_config(interactive),
            responsive=False,
        ),
        className="ui-chart",
    )


def filterable(entities: list[str]) -> list[str]:
    """The entities a participant may hide: every one but World.

    World is the dashed reference every line is read against, and the practice asks about it. It
    has no chip and no legend entry, and no control can switch it off (visual-spec.md section 6).
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
    """The line chart's chip and legend order. `listed` is the task's own order; `coverage` is
    highest-latest first, an entity with nothing reported last."""
    if sort_key not in ("listed", "coverage"):
        raise ValueError(f"Unknown line sort {sort_key!r}; expected listed or coverage")
    if sort_key == "listed":
        return list(entities)
    values = latest_values(entities, vaccine)
    return sorted(entities, key=lambda e: (values[e] is None, -(values[e] or 0), e))


# The sort control each chart type has (visual-spec.md section 7.2, the handoff's SORT): its
# legend, then (value, label) for each option. The first option is the chart as first drawn.
SORTS = {
    "line": ("View", (("listed", "as listed"), ("coverage", "by coverage"))),
    "bar": ("Sort", (("alpha", "A–Z"), ("desc", "High → low"), ("asc", "Low → high"))),
    "heatmap": (
        "Sort rows",
        (("default", "Default"), ("min", "Lowest value"), ("mean", "Average")),
    ),
}

# The hint under each interactive chart, verbatim from the handoff's HINT.
HINTS = {
    "line": (
        "Click a legend entry to hide or show a country; double-click to show only that country."
    ),
    "bar": "Hover a bar to read its value.",
    "scatter": "Hover a dot to see which country it is and its values.",
    "heatmap": "Hover a cell to read its value.",
    "map": "Countries not below the threshold turn grey. Hover a country to read its value.",
}

RESET_TITLE = "Undo any filtering, sorting or isolating on this chart"
# The handoff's undo arrow, in the button's ink. An image because Dash has no SVG components.
UNDO_ICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' "
    "viewBox='0 0 16 16' fill='none' stroke='%23241C18' stroke-width='1.8' "
    "stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M2.5 8a5.5 5.5 0 1 0 1.7-4'/%3E"
    "%3Cpath d='M2.5 2.5v3.5H6'/%3E%3C/svg%3E"
)
THRESHOLD_START = 100
CHIP_ROWS = 2


def default_sort(chart_type: str) -> str | None:
    """The sort a chart opens with, or None for a chart with no sort."""
    return SORTS[chart_type][1][0][0] if chart_type in SORTS else None


def control_id(name: str, index: int = 0) -> dict[str, object]:
    """A control's pattern id. Every chart type has a different set of controls and the static
    condition has none, so one callback reads them all with `ALL`: a named id absent from the page
    would stop a callback in the browser."""
    return {"control": name, "index": index}


def flag_src(entity: str) -> str | None:
    """The chip's flag, served from `src/assets/flags/` (scripts/vendor_flags.py), or None for an
    aggregate, which has no flag."""
    from src import runtime_data

    for row in runtime_data.load_rows():
        if row.country == entity:
            return (
                None
                if row.iso_code.startswith("OWID")
                else f"assets/flags/{row.iso_code.lower()}.png"
            )
    return None


def chip_rows(order: list[str], shown: list[str]) -> list[dict[str, list]]:
    """The chips in two rows, the first taking the extra one: each row's options and ticked values.

    Two rows as in the handoff, so a long set wraps where the design wraps it, and a reorder by
    coverage moves chips between rows without moving anything else on the page (its state S5).
    """
    half = -(-len(order) // CHIP_ROWS)
    rows = []
    for names in (order[:half], order[half:]):
        options = []
        for name in names:
            flag = flag_src(name)
            label = [html.Span(name)]
            if flag:
                label.insert(
                    0, html.Img(src=flag, alt="", width=24, height=16, className="chip-flag")
                )
            options.append({"label": label, "value": name})
        rows.append({"options": options, "value": [name for name in names if name in shown]})
    return rows


def chip_group(task, order: list[str], shown: list[str]) -> list:
    """The Countries group's contents: its legend, then a checklist for each row of chips.

    Built afresh whenever the chips' order changes (the View control, or Reset view undoing it),
    rather than by sending the checklists new options. A chip's label is a flag and a name, as
    components, and Dash 4 loses track of them when one moves to the other row's checklist: the
    renderer throws and the chips vanish (headless Chrome, 2026-09-26). An empty row, the
    practice's second, is left out.
    """
    justify = "space-between" if task.chart == "line" else "flex-start"
    return [
        html.Span("Countries", className="ui-legend"),
        *[
            dcc.Checklist(
                id=control_id("chips", index),
                options=row["options"],
                value=row["value"],
                className="chips ui-chips",
                labelClassName="chip-name",
                # Data-driven, as in the handoff: line charts spread their chips across the row.
                style={"justifyContent": justify},
            )
            for index, row in enumerate(chip_rows(order, shown))
            if row["options"]
        ],
    ]


def _chips(task, order: list[str], shown: list[str]) -> html.Div:
    return html.Div(
        chip_group(task, order, shown),
        id=control_id("chip-group"),
        className="ui-group ui-group--grow",
        role="group",
        **{"aria-label": "Countries"},
    )


def _sort_group(task) -> html.Div:
    legend, options = SORTS[task.chart]
    stack = [
        dcc.RadioItems(
            id=control_id("sort"),
            options=[{"label": label, "value": value} for value, label in options],
            value=default_sort(task.chart),
            className="seg ui-seg ui-seg--stack",
        )
    ]
    if task.chart == "line":
        stack.append(
            html.Button(
                "Show all", id=control_id("show-all"), n_clicks=0, className="btn btn-quiet btn-xs"
            )
        )
    return html.Div(
        [html.Span(legend, className="ui-legend"), html.Div(stack, className="ui-stack")],
        className="ui-group ui-group--fit",
        role="group",
        **{"aria-label": legend},
    )


def _highlight_group() -> html.Div:
    """The map's "Below [n] %" box (visual-spec.md section 7.4). It commits on Enter or when it
    loses focus (`debounce`), so a number half typed does not fade the map."""
    return html.Div(
        [
            html.Span("Highlight", className="ui-legend"),
            html.Label(
                [
                    "Below",
                    dcc.Input(
                        id=control_id("threshold"),
                        type="number",
                        min=0,
                        max=100,
                        step=1,
                        value=THRESHOLD_START,
                        debounce=True,
                        className="tb-num",
                    ),
                    "%",
                ],
                className="tb-inline",
            ),
        ],
        className="ui-group ui-group--fit",
        role="group",
        **{"aria-label": "Highlight"},
    )


def task_controls(task) -> html.Div:
    """The controls strip under the chart. Rendered ONLY in the interactive condition.

    These are the study's independent variable. The chart they act on is the same chart the static
    condition sees; what differs is that it can be worked with rather than only looked at. Every
    chart has the country chips (visual-spec.md section 7.3); the line, bar and heatmap add a sort,
    the line chart Show all, and the map the highlight. Each opens on the chart as first drawn:
    every country shown, in the listed order, nothing faded. The view they change lives in the
    app's `control-state` store, keyed to the task, so no task inherits another's.

    Every control is a native form element, so keyboard navigation comes for free (the
    accessibility baseline in CLAUDE.md). Do not reimplement any of them as styled divs.
    """
    order = filterable(list(task.entities))
    groups = [_chips(task, order, order)]
    if task.chart in SORTS:
        groups.append(_sort_group(task))
    if task.chart == "map":
        groups.append(_highlight_group())
    return html.Div(groups, className="ui-controls")


def hint_row(task) -> html.Div:
    """What the chart can do, and Reset view. Interactive condition only, under the controls."""
    return html.Div(
        [
            html.P(HINTS[task.chart], className="tb-hint"),
            html.Button(
                [html.Img(src=UNDO_ICON, alt="", width=14, height=14), "Reset view"],
                id=control_id("reset"),
                n_clicks=0,
                title=RESET_TITLE,
                className="btn btn-quiet btn-sm btn-reset",
            ),
        ],
        className="ui-hint-row",
    )


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
        className="ui-hint",
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


def error_slot(class_name: str = "msg msg-error", element=html.Div, **attributes):
    """The one validation-error slot, `flow-error`, which every screen must carry somewhere.

    It is on EVERY screen, not only the ones that can produce an error. A Dash callback resolves its
    outputs against whatever is in the DOM, so an error output present on some screens and not
    others is a latent failure on exactly the screens that need it most. One id, always present, is
    the version that cannot misfire. Where it sits is the screen's business: under Submit on the
    task screen, under the field on the participant-ID screen, as in the handoff.
    """
    return element(id="flow-error", className=class_name, **attributes)


def page(*children, class_name: str = "page") -> html.Main:
    """A screen's content, the `.page` inside the shell. The screen places its own error slot."""
    return html.Main(list(children), className=class_name)


def stage_page(*children) -> html.Main:
    """A short screen: its copy and buttons on one white card, centred on the page (the handoff's
    screens 2, 3, 4, 6, 8, 9 and 11). The screen places its own error slot."""
    return page(
        html.Div(
            html.Div(html.Div(list(children), className="prose"), className="stage-col"),
            className="stage",
        ),
        class_name="page page--fill",
    )


def screen_title(text: str, emoji: str | None = None) -> html.H1:
    """A short screen's heading. Its emoji is hidden from screen readers, which would read out the
    emoji's name in the middle of the heading."""
    if emoji is None:
        return html.H1(text, className="h1")
    return html.H1([f"{text} ", html.Span(emoji, **{"aria-hidden": "true"})], className="h1")


def button(label, element_id: str, kind: str = "primary") -> html.Button:
    """A native button, so keyboard-operable, in the stylesheet's look: `primary` or `secondary`."""
    return html.Button(label, id=element_id, n_clicks=0, className=f"btn btn-{kind}")


def actions(*buttons) -> html.Div:
    return html.Div(list(buttons), className="actions")


def interim_page(*children) -> html.Main:
    """A screen not yet rebuilt on the stylesheet's classes: today's look in a white box, inside the
    shell, with the error slot at the end. docs/study-redesign.md phases 5-7 retire it."""
    return page(
        html.Div([*children, html.Div(id="flow-error", style=ERROR_STYLE)], style=PAGE_STYLE)
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

    return interim_page(
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


def declined_screen() -> html.Main:
    """IRB form item 12B. Nothing is written before consent, so the second sentence is true."""
    return stage_page(
        screen_title("Thank you for your time!"),
        html.P(
            "You chose not to take part in this study. No data has been collected. You can close "
            "this tab."
        ),
        html.P(
            "If you chose this by mistake, you can go back to the consent form.", className="note"
        ),
        actions(button("Go back to the consent form", "reconsider-button", "secondary")),
        error_slot(),
    )


def participant_screen() -> html.Main:
    """The participant ID, and the participant's copy of the consent form they signed (held in a
    memory store and lost on reload; the researcher can send one then).

    A refusal (S2) shows under the field, and `app.PARTICIPANT_ENABLE_JS` marks the field invalid
    and points it at the message: `dcc.Input` has no `aria-*` properties to do it from here.
    """
    return stage_page(
        screen_title("Participant ID", "👤"),
        # Resume is not implemented, so this must not promise it. docs/study-design.md section 8.
        html.P(
            [
                "Thank you! Please download a copy of your signed consent form below.",
                html.Br(),
                html.Br(),
                "Afterwards, enter the ID you were given by the student investigator in the "
                "empty text area below. Please complete the study in one sitting, in this tab. "
                "Closing it ends your session.",
            ]
        ),
        html.Div(
            [
                # A <label>, where the handoff hides "ID:" from screen readers: it names the field.
                html.Label("ID:", htmlFor="participant-input", className="id-label"),
                dcc.Input(
                    id="participant-input",
                    type="text",
                    debounce=True,
                    placeholder="e.g. 19",
                    className="field",
                ),
            ],
            className="id-row",
        ),
        error_slot("field-error", html.P, role="alert"),
        actions(
            html.Button(
                [html.Span("↓", **{"aria-hidden": "true"}), "Download your signed consent form"],
                id="consent-copy-button",
                n_clicks=0,
                className="btn btn-secondary",
            ),
            button("Continue", "participant-button"),
        ),
    )


def about_id(item: str) -> dict[str, str]:
    """An About-you field's pattern id. The callback reads every one with `ALL`."""
    return {"type": "about", "item": item}


def survey_id(item: str) -> dict[str, str]:
    """A survey field's pattern id. The fields differ by condition and half, so the callback reads
    whichever are on the page with `ALL` rather than naming them."""
    return {"type": "survey", "item": item}


def _about_question(question) -> list:
    """One About-you question and its fields. The ids are what `app._demographic_answers` reads."""
    text = [
        html.P(question.text, style={**PROMPT_STYLE, "fontWeight": "600", "margin": "20px 0 4px"})
    ]
    if question.help:
        text.append(html.P(question.help, style={**MUTED_STYLE, "margin": "0 0 8px"}))
    if question.kind == "age":
        low, high = tasks.AGE_RANGE
        return [
            *text,
            dcc.Input(
                id=about_id("age"), type="number", min=low, max=high, step=1, style=FIELD_STYLE
            ),
            dcc.Checklist(
                id=about_id("age_prefer_not"),
                options=[{"label": PREFER_NOT, "value": PREFER_NOT}],
                value=[],
                inputStyle={"marginRight": "8px"},
                style={"marginTop": "8px"},
            ),
        ]
    if question.kind == "matrix":
        rows = []
        for row in question.rows:
            rows += [
                html.P(row, style={"margin": "10px 0 4px"}),
                dcc.RadioItems(
                    id=about_id(f"{question.key}/{row}"),
                    options=[{"label": o, "value": o} for o in question.options],
                    value=None,
                    labelStyle={"display": "inline-block", "marginRight": "16px"},
                    inputStyle={"marginRight": "6px"},
                ),
            ]
        return [*text, *rows]
    fields = [
        dcc.RadioItems(
            id=about_id(question.key),
            options=[{"label": o, "value": o} for o in question.options],
            value=None,
            labelStyle={"display": "block", "margin": "6px 0"},
            inputStyle={"marginRight": "8px"},
        )
    ]
    if question.other_key is not None:
        fields.append(
            dcc.Input(
                id=about_id(question.other_key),
                type="text",
                placeholder=f"{OTHER}: please say",
                maxLength=200,
                style=FIELD_STYLE,
            )
        )
    return [*text, *fields]


def demographics_screen() -> html.Div:
    """About you: once per participant, at the end. docs/study-design.md section 6.2.

    Every question on one page for now; the design handoff's one-per-page version replaces it.
    """
    body = []
    for title, questions in ABOUT_SECTIONS:
        body.append(html.H2(title, style=SUBHEADING_STYLE))
        for question in questions:
            body += _about_question(question)
    return interim_page(
        heading("About you"),
        html.P(ABOUT_INTRO, style=PROMPT_STYLE),
        html.P(SKIP_NOTE, style=MUTED_STYLE),
        *body,
        primary_button("Continue", "demographics-button"),
    )


def practice_complete_screen() -> html.Main:
    """Between the practice and the first scored task, first condition only. The design handoff's
    screen 6 (docs/study-design.md section 8)."""
    return stage_page(
        screen_title("Practice Complete!", "😉"),
        html.P("That was the practice question. It was not scored."),
        html.P(
            "The next six questions are the ones that count. The charts use the same version "
            "(static/interactive) that you experienced in the practice question."
        ),
        html.P(
            "For each question, choose one answer, then write a short sentence response about your "
            "decision. After the sixth question, there are a few quick reflecting questions about "
            "your experience with this version."
        ),
        html.P(
            "You may skip a question at any time. If you leave one unanswered, you will be asked "
            "to confirm."
        ),
        # Its own id: `begin-button` leaves the instructions, and sharing it would make the two
        # indistinguishable in the callback -- how the break once skipped the instructions.
        actions(button("Start the questions", "practice-done-button")),
        error_slot(),
    )


# The instructions' wording: the design handoff's screens 4a, 4b, 9a and 9b, with the copy fixes in
# docs/study-redesign.md section 5 and its interactive bullets rewritten to describe the controls
# the charts have (docs/study-design.md section 8, where the approved wording is quoted).
PRACTICE_INTRO = (
    "Before the main set of questions, you'll try one practice question so you know what to "
    "expect. It won't be scored.",
    "You'll see a line chart of childhood vaccination coverage (the share of children who received "
    "a vaccine each year). Answer the question, then explain in one sentence how you decided.",
)
STATIC_BULLET = "The chart is an image. Read values by comparing the line to the gridlines."
INTERACTIVE_BULLETS = (
    "The charts are interactive. Move your pointer over any line, bar, dot, cell or country to see "
    "its value; on a line chart you also see its change from the year before.",
    "Under each chart, the country buttons show or hide countries, and Reset view undoes your "
    "changes.",
    "On line charts you can also click a line, or double-click a name in the legend, to see one "
    "country on its own; reorder the countries by coverage; and bring every line back with Show "
    "all.",
    "The bar chart and the coloured grid can sort their bars or rows. The map can highlight only "
    "the countries below a coverage you type.",
)
GAP_BULLET = "A break in a line means no value was reported for those years."
PRACTICE_SKIP_BULLET = (
    "You can skip the question. If you leave it blank, you'll be asked to confirm."
)
OTHER_CHARTS = (
    "In the main task, you'll see other kinds of charts too: bar charts, scatter plots, coloured "
    "grids and maps."
)
# An addition to the handoff, so the static wording names the colour key the heatmap and the map
# are read against, as the 2026-09-23 wording did.
STATIC_OTHER_CHARTS = (
    "Those are images too: read them against the gridlines, or against the colour key where there "
    "is one."
)
SECOND_HALF_INTRO = (
    "This half uses a different version of the charts. The tasks are similar, but the charts work "
    "differently."
)
SECOND_HALF_STATIC = (
    " images. They don't respond to your mouse pointer and have no controls. Read them against the "
    "gridlines, or against the colour key where there is one."
)
SECOND_HALF_POINTING = (
    "Pointing at any line, bar, dot, cell or country shows its value. On line charts, it also "
    "shows the change from the year before."
)
SECOND_HALF_CLOSE = (
    "As before, you'll answer a question about each chart and then say in one sentence how you "
    "decided. A break in a line means no value was reported for those years. You may skip any "
    "question, and you'll be asked to confirm if you leave one blank."
)


def instructions_screen(interactive: bool, practice: bool = False) -> html.Main:
    """Instructions. The wording differs by condition ONLY in describing what the chart can do.

    Describing controls that are not present, or failing to describe controls that are, would be a
    procedural difference rather than a visual one — but it has to be accurate or the interactive
    condition is handicapped by not knowing its affordances exist.

    **Shown before BOTH conditions.** `practice=True` marks the first, which is the only one leading
    into the practice item. The second condition reaches this screen from the break, and needs it
    precisely because its affordances differ from the first's — a participant who gets the
    interactive version second would otherwise never learn the controls exist. Both halves'
    interactive versions list the same controls.

    The copy's sizes (21, 22 and 23 px) and its line breaks are the handoff's, screen by screen.
    """
    if practice:
        bullets = [*(INTERACTIVE_BULLETS if interactive else [STATIC_BULLET])]
        bullets += [GAP_BULLET, PRACTICE_SKIP_BULLET]
        closing = OTHER_CHARTS if interactive else f"{OTHER_CHARTS} {STATIC_OTHER_CHARTS}"
        subtitle = "Practice Question"
        body = html.Div(
            [
                PRACTICE_INTRO[0],
                html.Br(),
                html.Br(),
                PRACTICE_INTRO[1],
                html.Ul([html.Li(bullet) for bullet in bullets]),
                closing,
            ],
            className="copy-21",
        )
    elif interactive:
        subtitle = "Second Half"
        body = html.Div(
            [
                SECOND_HALF_INTRO,
                html.Br(),
                html.Br(),
                "The charts in this half are ",
                html.B("interactive"),
                ":",
                html.Ul([html.Li(b) for b in (SECOND_HALF_POINTING, *INTERACTIVE_BULLETS[1:])]),
                SECOND_HALF_CLOSE,
            ],
            className="copy-22",
        )
    else:
        subtitle = "Second Half"
        body = html.P(
            [
                SECOND_HALF_INTRO,
                html.Br(),
                html.Br(),
                "The charts in this half are ",
                html.B("static"),
                SECOND_HALF_STATIC,
                html.Br(),
                html.Br(),
                SECOND_HALF_CLOSE,
            ],
            className="copy-23",
        )
    return stage_page(
        screen_title("Instructions", "📜"),
        html.P(subtitle, className="lead copy-26"),
        body,
        actions(
            button(
                "Start the practice question" if practice else "Start the questions",
                "begin-button",
            )
        ),
        error_slot(),
    )


def task_screen(
    task, interactive: bool, index: int, total: int, practice: bool = False
) -> html.Main:
    """One task: the position and question, then one card holding the chart column and the answer
    panel (the handoff's screen 5, visual-spec.md section 10).

    The chart column is the chart, the gap caption in both conditions, and in the interactive
    condition only the controls strip and the hint row, all under the chart, so the chart stands
    in the same place in both. The panel is the numbered steps: choose an answer, then say why,
    then Submit.

    The practice item uses this same screen, so what it teaches is the interface the scored tasks
    actually use.
    """
    position = "Practice — not scored" if practice else f"Question {index} of {total}"
    column = [chart(task, interactive)]
    note = gap_note(list(task.entities), task.vaccine, task.years, task.chart)
    if note is not None:
        column.append(note)
    # The controls are the interactive condition's whole point, and the static condition renders
    # nothing in their place. The CHART is identical either way.
    if interactive:
        column += [task_controls(task), hint_row(task)]

    panel = [
        html.P(
            [html.Span("1", className="ui-step-n"), tasks.CHOOSE_PROMPTS[task.kind]],
            className="ui-step ui-step--nowrap",
        ),
        dcc.RadioItems(
            id="answer-input",
            options=[{"label": option, "value": option} for option in task.options],
            value=None,
            className="ui-tiles",
            labelClassName="ui-tile-label",
        ),
        html.Div(
            [
                html.Label(
                    [html.Span("2", className="ui-step-n"), JUSTIFICATION_PROMPT],
                    htmlFor="justification-input",
                    className="ui-step",
                ),
                dcc.Textarea(id="justification-input", className="ui-textarea"),
                html.Button(
                    "Submit", id="submit-button", n_clicks=0, className="btn btn-primary btn-block"
                ),
                error_slot(),
            ],
            className="ui-decide",
        ),
    ]
    return page(
        html.Div(
            [html.P(position, className="position"), html.H1(task.prompt, className="question")],
            className="ui-head",
        ),
        html.Div(
            [html.Div(column, className="ui-main"), html.Div(panel, className="ui-panel")],
            className="ui-card ui-card--task",
        ),
    )


def _scale(item: str, question: str, points: int, anchors: dict[int, str], help_text: str = ""):
    options = [
        {"label": f"{n} — {anchors[n]}" if n in anchors else str(n), "value": n}
        for n in range(1, points + 1)
    ]
    block = choice_question(survey_id(item), question, options)
    if help_text:
        block.children.insert(1, html.P(help_text, style={**MUTED_STYLE, "margin": "0 0 8px"}))
    return block


def load_screen(interactive: bool, second_half: bool) -> html.Div:
    """The post-condition survey, asked after EACH condition. docs/study-design.md section 6.1.

    Paas first (the RQ3 measure), then a1-a9. The chart-controls items b1-b3 follow after the
    interactive condition only, and the comparison c1-c3 after the second condition only. The
    statements never say which version it was. Every question on one page for now; the design
    handoff's one-per-page version replaces it.
    """
    sections = [
        html.H2(EXPERIENCE_SECTION, style=SUBHEADING_STYLE),
        _scale("paas", LOAD_PROMPT, 9, LOAD_ANCHORS),
        *[
            _scale(key, statement, LIKERT_POINTS, LIKERT_ANCHORS)
            for key, statement in LIKERT_ITEMS.items()
        ],
    ]
    if interactive:
        sections += [
            html.H2(CONTROLS_SECTION, style=SUBHEADING_STYLE),
            *[
                _scale(key, statement, LIKERT_POINTS, LIKERT_ANCHORS, CONTROLS_HELP)
                for key, statement in CONTROLS_ITEMS.items()
            ],
        ]
    if second_half:
        sections += [
            html.H2(COMPARISON_SECTION, style=SUBHEADING_STYLE),
            *[
                choice_question(
                    survey_id(key), question, [{"label": o, "value": o} for o in COMPARISON_OPTIONS]
                )
                for key, question in COMPARISON_CHOICES.items()
            ],
            html.P(
                COMPARISON_TEXT, style={**PROMPT_STYLE, "fontWeight": "600", "margin": "20px 0 4px"}
            ),
            html.P(COMPARISON_TEXT_HELP, style={**MUTED_STYLE, "margin": "0 0 8px"}),
            dcc.Textarea(
                id=survey_id(COMPARISON_TEXT_KEY),
                maxLength=tasks.MAX_TEXT,
                style={
                    "fontFamily": config.FONT_FAMILY,
                    "fontSize": f"{config.FONT_SIZE_BASE}px",
                    "width": "100%",
                    "height": "90px",
                    "padding": "8px",
                },
            ),
        ]
    return interim_page(
        heading("About this part"),
        html.P(SURVEY_INTRO["second" if second_half else "first"], style=PROMPT_STYLE),
        html.P(SKIP_NOTE, style=MUTED_STYLE),
        *sections,
        primary_button("Continue", "load-button"),
    )


def break_screen() -> html.Main:
    return stage_page(
        screen_title("Halfway There!", "😊"),
        html.P(
            "Congratulations! The first half of the study is complete! The next set will ask "
            "different questions using the other version (static/interactive). Take a moment, then "
            "continue when you are ready.",
            className="copy-21",
        ),
        # Its own id, not `begin-button`: this leads to the second condition's INSTRUCTIONS, whereas
        # `begin-button` starts the tasks. Sharing an id would make the two indistinguishable in the
        # callback and is how the second condition lost its instructions in the first place.
        actions(button("Continue", "resume-button")),
        error_slot(),
    )


def complete_screen(participant_id: str | None = None) -> html.Main:
    """The end, with the withdrawal right IRB form item 13 promises to remind participants of."""
    who = f" (your participant ID is {participant_id})" if participant_id else ""
    email = consent.RESEARCHER_EMAIL
    return stage_page(
        screen_title("Finished! Thank you!", "🙂"),
        html.P("Your responses have been successfully recorded. You can close this tab."),
        html.P(
            [
                "If you change your mind, you can withdraw your responses within two weeks of "
                "today, without giving a reason. Email ",
                html.A(email, href=f"mailto:{email}"),
                f" and include your participant ID{who}.",
            ]
        ),
        error_slot(),
    )
