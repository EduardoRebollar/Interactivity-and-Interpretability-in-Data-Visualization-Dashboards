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
markup needs, and the handoff's own inline values as classes (docs/visual-spec.md section 10).
Every screen sits in `shell`: the header band, the stepper, and the page's background. The short
screens are `stage_page`; the survey and About you are `pager_screen`. No screen sets an inline
style except where the value comes from the data (the chips' spacing on a line chart).
"""

from __future__ import annotations

from dash import dcc, html

from src import consent, figures, flow, tasks
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


# --- Study flow screens --------------------------------------------------------------------------
#
# Every screen is identical across conditions. The only permitted divergence is the Plotly config
# passed to `chart()`, plus the interactive-only controls, which render only when `interactive`.


PENDING_APPROVAL = (
    "PENDING HSRRC APPROVAL! This consent form has not been approved! Do not run participants!"
)
PAPER_COPY = "I have signed a paper copy of this form with the researcher instead"
# The lines under the signing fields, spaced as the handoff's screen 1 spaces them so each label
# sits under its field (the sheet keeps runs of spaces), and the researcher's countersignature line
# from the paper form.
SIGNOFF_LABEL = f"Participant Signature and Date{' ' * 38}/{' ' * 20}PRINTED NAME"
COUNTERSIGN_RULE = "_" * 104
COUNTERSIGN_LABEL = (
    f"Researcher or Research Assistant Signature and Date{' ' * 2}/{' ' * 20}PRINTED NAME"
)
# The form's title lines (title, investigator, supervisor) stand together under its heading;
# every later paragraph follows a blank line.
TITLE_LINES = 3


def _warned(text: str) -> list:
    """The banner's text between its warning signs, which screen readers are spared."""
    sign = {"aria-hidden": "true"}
    return [html.Span("⚠️", **sign), f" {text} ", html.Span("⚠️", **sign)]


def consent_sheet_text() -> list:
    """The form's text as the sheet sets it (the handoff's screen 1): the centred heading, the title
    lines, then every paragraph after a blank line, run-in headings in bold. Built from
    `consent.SECTIONS`, the text `consent.CONSENT_VERSION` hashes, so the two cannot differ."""
    lines = [html.P(html.B(line), className="sheet-center") for line in consent.FORM_HEADING]
    lines += [html.P(), html.P()]
    for index, (heading, body) in enumerate(consent.SECTIONS):
        if index >= TITLE_LINES:
            lines.append(html.P())
        if heading is None:
            lines.append(html.P(body))
        elif consent.runs_in(heading):
            lines.append(html.P([html.B(heading), f" {body}"]))
        else:
            lines += [html.P(html.B(heading)), html.P(), html.P(body)]
    return lines


def countersignature() -> list:
    """The researcher's line under the participant's: the paper form's blank rule, or, when
    `consent.researcher_signature()` finds the image, the signature, the date and the printed name
    on the rule. The date is the participant's browser's (`app.COUNTERSIGN_DATE_JS`), so it is the
    day the form is signed wherever the server is."""
    signature = consent.researcher_signature()
    if signature is None:
        return [
            html.P([html.Br(), COUNTERSIGN_RULE]),
            html.P(COUNTERSIGN_LABEL, className="sheet-label"),
        ]
    return [
        html.Div(
            [
                html.Div(
                    html.Img(src=signature, alt=f"Signed: {consent.INVESTIGATOR}"),
                    className="sheet-counter-sig",
                ),
                html.Span(id="countersign-date", className="sheet-counter-line"),
                html.Span(
                    consent.INVESTIGATOR, className="sheet-counter-line sheet-counter-line--name"
                ),
                html.P(COUNTERSIGN_LABEL, className="sheet-label sheet-label--row"),
            ],
            className="sheet-signoff sheet-countersign",
        )
    ]


def consent_screen() -> html.Main:
    """The Occidental informed consent form as a Letter sheet, signed inside it: signature, date and
    printed name, then agree or decline (the handoff's screen 1).

    IRB form item 12A: typed name and date, a signature, and an explicit "I agree to participate".
    Item 12B: declining must be possible and must lead somewhere that says no data was collected.

    The signature pad (`src/assets/signature.js`) cannot be used from a keyboard. The paper-copy box
    is the alternative, and it is a native checkbox: a participant who cannot draw signs the paper
    form the researcher brings, which item 12A already provides for. A consent that could not be
    stored shows under the buttons (S3).
    """
    banner = (
        []
        if consent.APPROVED
        else [html.P(_warned(PENDING_APPROVAL), className="banner banner--static", role="alert")]
    )
    signoff = html.Div(
        [
            html.Div(
                [
                    html.Canvas(
                        id="signature-pad",
                        width=consent.PAD_WIDTH,
                        height=consent.PAD_HEIGHT,
                        className="pad",
                        **{
                            "aria-label": "Participant signature — sign with your mouse, "
                            "trackpad or finger"
                        },
                    ),
                    # Shown by signature.js once there is a stroke to clear.
                    html.Button(
                        "Clear signature",
                        id="signature-clear",
                        n_clicks=0,
                        hidden=True,
                        className="btn btn-quiet pad-clear",
                    ),
                ],
                className="sheet-pad",
            ),
            # The form's own labels are the line under the fields; these name the fields for
            # screen readers, which dcc.Input's lack of aria-* properties leaves no other way to do.
            html.Label("Date", htmlFor="consent-date", className="sr-only"),
            dcc.Input(id="consent-date", type="date", className="sheet-line"),
            html.Label("Printed name", htmlFor="consent-name", className="sr-only"),
            dcc.Input(
                id="consent-name",
                type="text",
                autoComplete="name",
                className="sheet-line sheet-line--name",
            ),
            html.P(SIGNOFF_LABEL, className="sheet-label sheet-label--row"),
        ],
        className="sheet-signoff",
        role="group",
        **{"aria-label": "Participant sign-off"},
    )
    return page(
        *banner,
        html.Div(
            html.Article(
                [
                    html.H1("Informed consent", id="consent-title", className="sr-only"),
                    *consent_sheet_text(),
                    signoff,
                    html.P(),
                    *countersignature(),
                    dcc.Checklist(
                        id="consent-paper",
                        options=[{"label": PAPER_COPY, "value": "paper"}],
                        value=[],
                        className="checks sheet-paper",
                    ),
                    html.Div(
                        [
                            button("I agree to participate", "consent-button"),
                            button("I do not agree", "decline-button", "secondary"),
                            error_slot(role="alert"),
                        ],
                        className="sheet-actions",
                    ),
                ],
                className="sheet sheet--form",
                **{"aria-labelledby": "consent-title"},
            ),
            className="sheet-desk",
        ),
        class_name="page page--desk",
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


# --- The questionnaire screens: the survey and About you (the handoff's screens 7 and 10) --------
#
# One question per page, a rail of sections beside them, Back and Next under them. Every page is on
# the screen from the start and only shown or hidden, in the browser (`app.PAGER_JS`), so every
# answer stays in its component and the final Continue sends them all, as one step, through the
# screen's clock. The pager's state lives in `pager-state`, which also tells the browser which
# fields each page holds, so a skip is confirmed on the page it happens.


def pager_id(part: str, index: int) -> dict[str, object]:
    """A pattern id for one of the pager's repeated parts: a page, or a section's rail entry."""
    return {"pager": part, "index": index}


def _page(index: int, section: str, items: tuple[str, ...], question) -> tuple:
    """(section, field items, the page's component)."""
    return (
        section,
        items,
        html.Div(
            [html.H2(section, className="h1"), question],
            id=pager_id("page", index),
            hidden=index != 0,
            className="pager-page",
        ),
    )


def _question(key: str, text: str, field, help_text: str = "", group: bool = True) -> html.Div:
    """A question's text, with its help beneath it, then its field. A group of radios is labelled
    by the text, as the handoff's radiogroup is."""
    words = [text, html.Span(help_text, className="q-help")] if help_text else text
    if group:
        field = html.Div(field, role="radiogroup", **{"aria-labelledby": f"q-{key}"})
    return html.Div(
        [html.P(words, id=f"q-{key}", className="q-text"), field], className="pager-question"
    )


def _scale(field_id: dict, points: int, anchors: dict[int, str]) -> dcc.RadioItems:
    """A 1-to-`points` scale: each point's number, and its anchor where it has one."""
    return dcc.RadioItems(
        id=field_id,
        options=[
            {
                "label": [
                    html.Span(str(n), className="scale-num"),
                    html.Span(anchors.get(n, ""), className="scale-anchor"),
                ],
                "value": n,
            }
            for n in range(1, points + 1)
        ],
        value=None,
        className=f"scale scale-{points}",
    )


def _choices(field_id: dict, options, columns: str, prefer_not_apart: bool = False, other=None):
    """Answer options in a grid of `columns` (`cols-2`, `cols-3` or `row-5`). With
    `prefer_not_apart`, the last option, "Prefer not to say", sits alone beneath the rest. `other`
    is the text box laid over the "Other" option's cell, where the handoff draws it inside the
    option: Dash cannot put a field inside an option's label and still read its value."""
    classes = "options options--compact options--in-grid"
    if prefer_not_apart:
        classes += " options--pnts"
    radios = dcc.RadioItems(
        id=field_id,
        options=[{"label": option, "value": option} for option in options],
        value=None,
        className=classes,
    )
    return html.Div(
        [radios, *([other] if other is not None else [])],
        className=f"choice-grid options--{columns}",
    )


def _other_box(question, columns: int) -> html.Div:
    """The text box for "Other", laid over that option's cell: its row and column from the
    option's place in the grid. An unseen copy of the option's radio and word keeps the box clear
    of them, whatever the typeface."""
    row, column = divmod(question.options.index(OTHER), columns)
    return html.Div(
        [
            html.Span(
                [html.Span(className="other-radio"), OTHER],
                className="other-ghost",
                **{"aria-hidden": "true"},
            ),
            dcc.Input(
                id=about_id(question.other_key),
                type="text",
                maxLength=200,
                className="field other-field",
            ),
        ],
        className=f"other-box other-box--r{row + 1}c{column + 1}",
    )


def _matrix(question) -> html.Table:
    """The tools question: a row of radios per tool, one column per level of familiarity. Each
    radio's name is read out as "<tool>: <level>", as in the handoff."""
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(), *[html.Th(o, scope="col") for o in question.options]])),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Th(row, scope="row"),
                            html.Td(
                                dcc.RadioItems(
                                    id=about_id(f"{question.key}/{row}"),
                                    options=[
                                        {
                                            "label": html.Span(f"{row}: {o}", className="sr-only"),
                                            "value": o,
                                        }
                                        for o in question.options
                                    ],
                                    value=None,
                                    className="matrix-row",
                                ),
                                colSpan=len(question.options),
                            ),
                        ]
                    )
                    for row in question.rows
                ]
            ),
        ],
        className="matrix",
    )


def _age() -> html.Div:
    """The age in years, or "Prefer not to say", with the message Next shows for an age it cannot
    accept (app.PAGER_JS).

    No `min`, `max` or `step` on the field: dcc.Input reports a number the browser finds invalid as
    null, so an age of 7 would reach the study as a skip, never as an age to refuse. The range is
    checked by Next and again by the server (`tasks.AGE_RANGE`)."""
    return html.Div(
        [
            dcc.Input(id=about_id("age"), type="number", inputMode="numeric", className="field"),
            dcc.Checklist(
                id=about_id("age_prefer_not"),
                options=[{"label": PREFER_NOT, "value": PREFER_NOT}],
                value=[],
                className="options options--compact age-pnts",
            ),
            html.Div(id=pager_id("error", 0), className="field-error", role="alert"),
        ],
        className="age-row",
    )


def _about_field(question):
    """The field(s) for one About-you question, with the ids `app._demographic_answers` reads."""
    if question.kind == "age":
        return _age()
    if question.kind == "matrix":
        return _matrix(question)
    apart = question.options[-1] == PREFER_NOT and not question.prefer_not_inline
    main = question.options[:-1] if apart else question.options
    if question.ordinal:
        width, columns = len(main), f"row-{len(main)}"
    else:
        # The handoff's rule: three across when every option is short, else two.
        width = 3 if all(len(option) <= 24 for option in main) else 2
        columns = f"cols-{width}"
    other = _other_box(question, width) if question.other_key is not None else None
    return _choices(about_id(question.key), question.options, columns, apart, other)


def _count(n: int) -> str:
    return "1 question" if n == 1 else f"{n} questions"


def _rail_entry(index: int, section: str, count: int) -> html.Li:
    """One section in the rail, as it stands on the first page: the first section current, the
    rest not reached yet (app.PAGER_JS redraws them as the participant moves)."""
    current = index == 0
    return html.Li(
        [
            *([html.Div(className="pager-link", **{"aria-hidden": "true"})] if index else []),
            html.Button(
                [
                    html.Span(str(index + 1), id=pager_id("mark", index), className="pager-mark"),
                    html.Span(
                        [
                            html.Span(section, className="pager-title"),
                            html.Span(
                                f"Question 1 of {count}" if current else _count(count),
                                id=pager_id("sub", index),
                                className="pager-sub",
                            ),
                            html.Progress(
                                id=pager_id("bar", index),
                                value=1 if current else 0,
                                max=count,
                                hidden=not current,
                                className="pager-bar",
                                **{"aria-hidden": "true"},
                            ),
                        ],
                        className="pager-label",
                    ),
                ],
                id=pager_id("section", index),
                n_clicks=0,
                disabled=not current,
                className="pager-go pager-go--current" if current else "pager-go",
            ),
        ],
        className="pager-step",
    )


def pager_screen(title: str, intro: str, pages: list[tuple], finish_id: str) -> html.Main:
    """A questionnaire screen: the rail (title, intro, skip note, sections), then the pages, one
    shown at a time, with Back, Next and, on the last page, Continue (`finish_id`, the button the
    screen's clock callback reads)."""
    sections = list(dict.fromkeys(section for section, _items, _page in pages))
    section_of = [sections.index(section) for section, _items, _page in pages]
    state = {
        "page": 0,
        "max": 0,
        "pages": [list(items) for _section, items, _page in pages],
        "sections": section_of,
        "errors": sum("age" in items for _section, items, _page in pages),
        "finish": finish_id,
    }
    rail = html.Aside(
        [
            html.Div(
                [
                    html.H1(title, className="h1"),
                    html.P(intro, className="pager-lede"),
                    html.P(SKIP_NOTE, className="note"),
                ],
                className="pager-intro",
            ),
            html.Ol(
                [
                    _rail_entry(index, section, section_of.count(index))
                    for index, section in enumerate(sections)
                ],
                className="pager-steps",
            ),
        ],
        className="pager-rail",
    )
    main = html.Div(
        [
            html.P(f"Question 1 of {len(pages)}", id="pager-position", className="position"),
            *[component for _section, _items, component in pages],
            html.Div(
                [
                    html.Button(
                        "Back",
                        id="pager-back",
                        n_clicks=0,
                        disabled=True,
                        className="btn btn-secondary",
                    ),
                    html.Button("Next", id="pager-next", n_clicks=0, className="btn btn-primary"),
                    html.Span(button("Continue", finish_id), id="pager-finish", hidden=True),
                ],
                className="actions pager-actions",
            ),
            error_slot(),
            dcc.Store(id="pager-state", data=state),
        ],
        className="pager-main",
    )
    return page(
        html.Div(html.Div([rail, main], className="stage-col pager"), className="stage stage--top"),
        class_name="page page--fill",
    )


def demographics_screen() -> html.Main:
    """About you: once per participant, at the end, one question per page in four sections
    (docs/study-design.md section 6.2, the handoff's screen 10)."""
    pages = []
    for section, questions in ABOUT_SECTIONS:
        for question in questions:
            if question.kind == "age":
                items = ("age", "age_prefer_not")
            elif question.kind == "matrix":
                items = tuple(f"{question.key}/{row}" for row in question.rows)
            else:
                items = tuple(k for k in (question.key, question.other_key) if k is not None)
            block = _question(
                question.key,
                question.text,
                _about_field(question),
                question.help,
                group=question.kind == "choice",
            )
            pages.append(_page(len(pages), section, items, block))
    return pager_screen("About you", ABOUT_INTRO, pages, "demographics-button")


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


def position_label(index: int, total: int, practice: bool = False) -> str:
    """Where a task stands: the label above its question, and above S4 on a task's screen."""
    return "Practice — not scored" if practice else f"Question {index} of {total}"


# S4, word for word (docs/study-design.md section 8): the handoff breaks the line after the first
# sentence.
BLOCKED = (
    "The study cannot save responses right now, so it cannot continue.",
    "Please contact the researcher.",
)


def blocking_screen(position: str | None = None) -> html.Main:
    """S4: responses cannot be saved anywhere, so the screen's content is replaced by this message,
    announced, with the position label of the screen it replaces, if that screen had one."""
    return page(
        *([html.P(position, className="position")] if position else []),
        html.Div(
            html.Strong([*_warned(BLOCKED[0]), html.Br(), BLOCKED[1]]),
            className="msg msg-block msg-block--system",
            role="alert",
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
    position = position_label(index, total, practice)
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


def _rated(key: str, text: str, points: int, anchors: dict[int, str], help_text: str = ""):
    return _question(key, text, _scale(survey_id(key), points, anchors), help_text)


def survey_pages(interactive: bool, second_half: bool) -> list[tuple]:
    """The survey's pages, in order: Paas, then a1-a9 ("Your experience"); b1-b3 ("Chart
    controls") after the interactive condition only; c1-c3 ("Comparing the two versions") after
    the second condition only."""
    questions = [(EXPERIENCE_SECTION, "paas", _rated("paas", LOAD_PROMPT, 9, LOAD_ANCHORS))]
    questions += [
        (EXPERIENCE_SECTION, key, _rated(key, text, LIKERT_POINTS, LIKERT_ANCHORS))
        for key, text in LIKERT_ITEMS.items()
    ]
    if interactive:
        questions += [
            (CONTROLS_SECTION, key, _rated(key, text, LIKERT_POINTS, LIKERT_ANCHORS, CONTROLS_HELP))
            for key, text in CONTROLS_ITEMS.items()
        ]
    if second_half:
        questions += [
            (
                COMPARISON_SECTION,
                key,
                _question(key, text, _choices(survey_id(key), COMPARISON_OPTIONS, "cols-3")),
            )
            for key, text in COMPARISON_CHOICES.items()
        ]
        text_box = dcc.Textarea(
            id=survey_id(COMPARISON_TEXT_KEY),
            maxLength=tasks.MAX_TEXT,
            rows=4,
            className="field pager-text",
        )
        questions.append(
            (
                COMPARISON_SECTION,
                COMPARISON_TEXT_KEY,
                _question(
                    COMPARISON_TEXT_KEY,
                    COMPARISON_TEXT,
                    text_box,
                    COMPARISON_TEXT_HELP,
                    group=False,
                ),
            )
        )
    return [
        _page(index, section, (key,), block)
        for index, (section, key, block) in enumerate(questions)
    ]


def load_screen(interactive: bool, second_half: bool) -> html.Main:
    """The post-condition survey, asked after EACH condition. docs/study-design.md section 6.1.

    Paas first (the RQ3 measure), then a1-a9. The chart-controls items b1-b3 follow after the
    interactive condition only, and the comparison c1-c3 after the second condition only. The
    statements never say which version it was. One question per page (the handoff's screen 7).
    """
    return pager_screen(
        "About this part",
        SURVEY_INTRO["second" if second_half else "first"],
        survey_pages(interactive, second_half),
        "load-button",
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
