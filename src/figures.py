"""Chart construction. Implements `docs/visual-spec.md`. No pandas — this ships to production.

**The figure is identical in both conditions.** Interactivity is not a property of the chart; it is
a property of how the chart is rendered, and lives entirely in `graph_config(interactive)`. Keeping
the split here means the two conditions are visually identical *by construction* rather than by
discipline, and `tests/test_conditions.py` proves it for every chart type.

Five chart types (visual-spec.md section 1): the line chart, and the bar, scatter, heatmap and map
added for the task bank of 2026-09-23. There is still one builder per chart, not a static and an
interactive pair: `build_figure` takes no `interactive` argument, whatever it draws.

Everything a hover reveals -- a value, a year-over-year change, a country's name -- is in the hover
text of BOTH conditions' figures. `staticPlot: True` is what keeps the static participant from
reaching it, so the information is interactive-only without the figures differing.

The controls change a figure only through the view functions below (`set_visible`, `sort_bars`,
`sort_rows`, `set_threshold`). Each hides, reorders or fades what is already there; none
rebuilds the chart from a shorter list, which would move every name tag on a line chart.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from src import config, runtime_data
from src.runtime_data import Row

CHART_TYPES = ("line", "bar", "scatter", "heatmap", "map")
REFERENCE = "World"

# How many years each chart type takes: a line spans the whole range and takes none.
_YEAR_COUNTS = {
    "line": (0, 0),
    "bar": (1, 1),
    "map": (1, 1),
    "scatter": (2, 2),
    "heatmap": (2, None),
}

# The map is drawn on the Africa scope at 110m resolution. Plotly would fetch that geometry from its
# CDN in each participant's browser; `src/assets/geo_africa.js` supplies it instead.
MAP_SCOPE = "africa"
MAP_RESOLUTION = 110


class FigureError(RuntimeError):
    """Raised when a figure is requested that the visual spec does not permit."""


def graph_config(interactive: bool, chart_type: str = "line") -> dict:
    """Plotly config for `dcc.Graph`. **The single decision point between conditions.**

    `staticPlot=True` removes hover, zoom, pan, selection, and the modebar. Plotly is interactive by
    default, so without this the static condition would still be hoverable and the manipulation
    would be invalid.

    `chart_type` is not a second switch: it says only where scroll zoom has an axis to move.
    """
    if interactive:
        return {
            "staticPlot": False,
            "displayModeBar": True,
            "displaylogo": False,
            # A mouse wheel or a touchpad (two-finger scroll or pinch, in whatever direction the
            # participant's system scrolls) zooms the line chart's x axis, beside Zoom in and Zoom
            # out (2026-09-27), logged as view_change. The line chart only: every other view is
            # fixed, and with scroll zoom on Plotly still takes the wheel over a fixed chart, so
            # the page would not scroll there -- and the scatter card must scroll to reach Submit
            # on a window under 862 px tall (measured in Chrome, 2026-10-11).
            "scrollZoom": "cartesian" if chart_type == "line" else False,
            # The line chart's one view button, Plotly's "Reset axes", is titled "Reset axis": it
            # resets the one axis that moves. Titles come only from the config's dictionary.
            "locales": {"en-US": {"dictionary": {"Reset axes": "Reset axis"}}},
        }
    return {"staticPlot": True, "displayModeBar": False}


# Modebar buttons each chart type drops, set in the FIGURE's layout (`modebar.remove`) so the figure
# carries them in both conditions; the static condition shows no modebar at all. visual-spec.md
# section 7.
#
# Box and lasso select are gone from every chart: they dim unselected marks, a change to what is on
# screen that no event records, and on the map they would override the coverage filter, which is
# drawn as a selection. The bar, scatter, heatmap and map views are fixed -- their axes, or the map,
# cannot move -- so their zoom and pan buttons would do nothing but invite a click. Download as PNG
# and Share chart (which uploads the chart to Plotly Cloud) go from every chart (2026-09-27).
#
# The line chart keeps drag-to-zoom, Zoom in, Zoom out and Reset axes (titled "Reset axis" in
# graph_config). Its Zoom and Pan mode buttons go, and so does Autoscale: after a zoom it fits the
# axis to everything drawn, end labels included (1998.4-2027.0, measured in Chrome), where Reset
# axes restores the chart's own 1999.75-2024.25.
_SELECTION_BUTTONS = ["select", "lasso"]
_SHARING_BUTTONS = ["toimage", "sendcharttocloud"]
_VIEW_BUTTONS = ["zoom", "pan", "zoomin", "zoomout", "autoscale", "resetscale"]
_MODEBAR_REMOVE = {
    "line": _SELECTION_BUTTONS + _SHARING_BUTTONS + ["zoom", "pan", "autoscale"],
    "bar": _SELECTION_BUTTONS + _SHARING_BUTTONS + _VIEW_BUTTONS,
    "scatter": _SELECTION_BUTTONS + _SHARING_BUTTONS + _VIEW_BUTTONS,
    "heatmap": _SELECTION_BUTTONS + _SHARING_BUTTONS + _VIEW_BUTTONS,
    "map": _SELECTION_BUTTONS + _SHARING_BUTTONS + ["pan", "zoomInGeo", "zoomOutGeo", "resetGeo"],
}


def build_figure(
    entities: Sequence[str],
    vaccine: str,
    rows: tuple[Row, ...] | None = None,
    *,
    chart_type: str = "line",
    years: Sequence[int] = (),
) -> go.Figure:
    """A coverage chart of `entities`. Identical in both study conditions.

    `chart_type` picks the chart; `years` are the years it shows (see `flow.Task`). A line chart
    always spans the locked range, so it takes no years.
    """
    entities, years = list(entities), tuple(years)
    _validate(entities, vaccine, chart_type, years)
    source = rows if rows is not None else runtime_data.load_rows()
    figure = _BUILDERS[chart_type](entities, vaccine, years, source)
    figure.update_layout(modebar={"remove": list(_MODEBAR_REMOVE[chart_type])})
    return figure


def task_figure(task, rows: tuple[Row, ...] | None = None) -> go.Figure:
    """The figure for one `flow.Task`, as it first appears: nothing hidden, sorted or filtered.

    No `uirevision`: every redraw is the figure exactly as sent, the zoom included (the app keeps
    the zoom in the view, `app._zoomed_range`). Plotly's own record of a zoom does not survive
    dcc.Graph, and whatever Plotly did keep would be a change the app had not drawn.
    """
    return build_figure(
        list(task.entities), task.vaccine, rows, chart_type=task.chart, years=task.years
    )


# --- The view functions: what the interactive controls change --------------------------------

BAR_SORTS = ("alpha", "desc", "asc")
# Each row's lowest cell, lowest first, or its highest, highest first: A-T4 asks for the lowest
# cell and B-T4 for the highest, so each form's key row comes to the top in one click. "mean" (each
# row's average) went after the first pilot session (2026-10-12); neither question turns on it.
ROW_SORTS = ("default", "min", "max")
# The label naming the order the bars or rows stand in (visual-spec.md section 7.2). It follows the
# sort, so it never says "alphabetical" over bars that are not.
ORDER_LABEL = "order"
BAR_ORDER_LABELS = {
    "alpha": "Countries in alphabetical order",
    "desc": "Countries by coverage, highest first",
    "asc": "Countries by coverage, lowest first",
}
ROW_ORDER_LABELS = {"default": "A–Z", "min": "Lowest cell first", "max": "Highest cell first"}


def _set_order_label(figure: go.Figure, text: str) -> None:
    for annotation in figure.layout.annotations:
        if annotation.name == ORDER_LABEL:
            annotation.text = text


def chart_type_of(figure: go.Figure) -> str:
    """Which of CHART_TYPES a built figure is, read from its traces."""
    kinds = {type(trace) for trace in figure.data}
    if go.Choropleth in kinds:
        return "map"
    if kinds == {go.Heatmap}:
        return "heatmap"
    if kinds == {go.Bar}:
        return "bar"
    if kinds == {go.Scatter}:
        return "scatter" if all(trace.mode == "markers" for trace in figure.data) else "line"
    raise FigureError(f"Not a figure build_figure makes: {sorted(k.__name__ for k in kinds)}")


def entity_names(figure: go.Figure) -> list[str]:
    """The entities a figure draws, in the order it was built with."""
    chart = chart_type_of(figure)
    if chart in ("line", "scatter"):
        return [trace.name for trace in figure.data]
    if chart == "bar":
        return [str(name) for name in _only(figure, go.Bar).x]
    if chart == "heatmap":
        return [str(name) for name in _only(figure, go.Heatmap).y]
    return [str(name) for name in _only(figure, go.Choropleth).text]


def set_visible(figure: go.Figure, entities: Sequence[str]) -> go.Figure:
    """Show only `entities`, leaving every remaining mark the colour it already had.

    **Filtering hides or fades; it never rebuilds the chart with a shorter list.** A rebuild would
    spread the name tags afresh and move every one that is left (visual-spec.md section 7.3).

    How a mark is hidden depends on the chart. A line or a scatter dot goes `legendonly` and
    disappears; a line's name tag -- leader, pill, dot and name, all named `tag:<entity>` -- goes
    with it, and the other tags stay where they are. Annotations and shapes that name no series are
    left alone. A bar, a heatmap row or a map country fades to FADED_OPACITY and keeps its place,
    its colour and its label: a hidden row must not look like an empty cell, which means "not
    reported".
    """
    visible = set(entities)
    names = entity_names(figure)
    unknown = visible - set(names)
    if unknown:
        raise FigureError(f"Cannot show entities that are not on the figure: {sorted(unknown)}")
    everything = visible >= set(names)
    chart = chart_type_of(figure)

    if chart in ("line", "scatter"):
        for trace in figure.data:
            trace.visible = True if trace.name in visible else "legendonly"
        hidden = {
            f"{prefix}{name}" for name in names if name not in visible for prefix in (TAG, _DOT)
        }
        figure.layout.annotations = [
            a for a in figure.layout.annotations if (a.name or "") not in hidden
        ]
        figure.layout.shapes = [s for s in figure.layout.shapes if (s.name or "") not in hidden]
    elif chart == "bar":
        bars = _only(figure, go.Bar)
        bars.marker.opacity = (
            None
            if everything
            else [1.0 if str(name) in visible else config.FADED_OPACITY for name in bars.x]
        )
    elif chart == "heatmap":
        _draw_cells(figure, _row_order(figure), [name for name in names if name not in visible])
    else:
        # A selection, as the highlight is (`set_threshold`): plotly.js 4 ignores a per-country
        # opacity list on a choropleth.
        countries = _only(figure, go.Choropleth)
        countries.selectedpoints = (
            None if everything else [i for i, name in enumerate(names) if name in visible]
        )
    return figure


def _row_order(figure: go.Figure) -> list[str]:
    """The heatmap's rows as drawn, top first."""
    order = figure.layout.yaxis.categoryarray
    return [str(name) for name in order] if order else entity_names(figure)


def _faded_rows(figure: go.Figure) -> list[str]:
    """The heatmap rows a chip has faded: their cells are drawn at FADED_OPACITY."""
    return sorted(
        {
            shape.name[len(_CELL) :]
            for shape in figure.layout.shapes
            if (shape.name or "").startswith(_CELL) and shape.opacity != 1
        }
    )


def sort_bars(figure: go.Figure, key: str) -> go.Figure:
    """Order the bars A to Z, highest first or lowest first (visual-spec.md section 7.2).

    **Sorting moves the bars.** On a line chart it reorders the chips only: the x
    axis is time, and the lines are where the data puts them. A bar chart's x axis has no order of
    its own. Each bar keeps its colour and its label; ties keep the listed order, and a bar with no
    value sorts last either way.
    """
    if key not in BAR_SORTS:
        raise FigureError(f"Unknown bar sort {key!r}; expected one of {BAR_SORTS}")
    bars = _only(figure, go.Bar)
    listed = [str(name) for name in bars.x]
    values = dict(zip(listed, bars.y, strict=True))
    if key == "alpha":
        order = sorted(listed)
    else:
        sign = -1 if key == "desc" else 1
        order = sorted(
            listed,
            key=lambda n: (values[n] is None, sign * (values[n] or 0), listed.index(n)),
        )
    figure.update_xaxes(categoryorder="array", categoryarray=order)
    _set_order_label(figure, BAR_ORDER_LABELS[key])
    return figure


def sort_rows(figure: go.Figure, key: str) -> go.Figure:
    """Order the heatmap's rows: as listed, by each row's lowest cell, lowest first, or by its
    highest cell, highest first (visual-spec.md section 7.2). Each row keeps its cells and its
    label, so no cell changes colour; ties keep the listed order, and a row with nothing reported
    sorts last."""
    if key not in ROW_SORTS:
        raise FigureError(f"Unknown row sort {key!r}; expected one of {ROW_SORTS}")
    cells = _only(figure, go.Heatmap)
    listed = [str(name) for name in cells.y]
    reported = {
        name: [value for value in row if value is not None]
        for name, row in zip(listed, cells.z, strict=True)
    }

    def statistic(name: str) -> float | None:
        values = reported[name]
        if not values:
            return None
        return min(values) if key == "min" else max(values)

    if key == "default":
        order = listed
    else:
        sign = 1 if key == "min" else -1
        order = sorted(
            listed,
            key=lambda n: (statistic(n) is None, sign * (statistic(n) or 0), listed.index(n)),
        )
    faded = _faded_rows(figure)
    figure.update_yaxes(categoryorder="array", categoryarray=order)
    _draw_cells(figure, order, faded)
    _set_order_label(figure, ROW_ORDER_LABELS[key])
    return figure


def set_threshold(figure: go.Figure, threshold: float | None) -> go.Figure:
    """Fade every country on the map whose coverage is `threshold` or more (visual-spec.md 7.4).

    None, or 100, means no highlight, so the map at rest is the figure `build_figure` made. A
    country the chips hid stays faded. Faded, not removed: the map keeps its shape, and a faded
    country is still where it was; the colour scale is fixed to 0-100, so no colour changes.

    Drawn as a SELECTION: the countries at full strength are selected and the rest take the trace's
    `unselected` opacity. plotly.js 4 applies a choropleth's `marker.opacity` to the whole trace,
    so a list of per-country opacities is silently dropped -- the map's first filter shipped that
    way and faded nothing, which only a browser showed.
    """
    if threshold is None or threshold >= config.Y_RANGE[1]:
        return figure
    if threshold < config.Y_RANGE[0]:
        raise FigureError(f"A highlight threshold must be 0-100, got {threshold}")
    countries = _only(figure, go.Choropleth)
    strong = full_strength(figure)
    countries.selectedpoints = [
        index
        for index, (keep, value) in enumerate(zip(strong, countries.z, strict=True))
        if keep and value is not None and value < threshold
    ]
    return figure


def full_strength(figure: go.Figure) -> list[bool]:
    """Which countries the map shows at full strength: all of them until a control fades some."""
    countries = _only(figure, go.Choropleth)
    if countries.selectedpoints is None:
        return [True] * len(countries.z)
    chosen = set(countries.selectedpoints)
    return [index in chosen for index in range(len(countries.z))]


def _only(figure: go.Figure, kind: type) -> go.BaseTraceType:
    traces = [trace for trace in figure.data if isinstance(trace, kind)]
    if len(traces) != 1:
        raise FigureError(f"Expected one {kind.__name__} trace, found {len(traces)}")
    return traces[0]


# --- Validation ----------------------------------------------------------------------------------


def _validate(entities: list[str], vaccine: str, chart_type: str, years: tuple[int, ...]) -> None:
    if not entities:
        raise FigureError("No entities requested")
    if vaccine not in config.VACCINES:
        raise FigureError(f"Unknown vaccine {vaccine!r}")
    if chart_type not in CHART_TYPES:
        raise FigureError(f"Unknown chart type {chart_type!r}; expected one of {CHART_TYPES}")

    unknown = [e for e in entities if e not in config.ENTITIES]
    if unknown:
        raise FigureError(f"Unknown entities: {unknown}")
    if len(set(entities)) != len(entities):
        raise FigureError("Duplicate entities requested")

    fewest, most = _YEAR_COUNTS[chart_type]
    if len(years) < fewest or (most is not None and len(years) > most):
        raise FigureError(f"A {chart_type} chart takes {fewest}-{most or 'any'} years, got {years}")
    if any(not config.YEAR_MIN <= year <= config.YEAR_MAX for year in years):
        raise FigureError(f"Years outside {config.YEAR_MIN}-{config.YEAR_MAX}: {years}")
    if list(years) != sorted(set(years)):
        raise FigureError(f"Years must be distinct and ascending, got {years}")

    # World is the line chart's dashed reference. On any other chart it would be one more bar, dot,
    # row or -- impossibly -- country, with nothing to say it is not a country.
    if chart_type != "line" and REFERENCE in entities:
        raise FigureError(
            f"{REFERENCE} is the line chart's reference; a {chart_type} cannot show it"
        )

    # The cap is not cosmetic: it is the number of colors that are simultaneously
    # contrast-compliant, color-blind separable, and separated in luminance.
    # See docs/visual-spec.md section 4. Only lines and dots are told apart by colour.
    if chart_type == "line":
        colored = [e for e in entities if e != REFERENCE]
        if len(colored) > config.MAX_SERIES:
            raise FigureError(
                f"{len(colored)} series requested but only {config.MAX_SERIES} distinguishable "
                "colors exist; World is exempt as the dashed reference"
            )
    # Sixteen dots, each named beside it (visual-spec.md section 6): T3's number.
    if chart_type == "scatter" and len(entities) > config.MAX_SCATTER_DOTS:
        raise FigureError(
            f"{len(entities)} dots requested; a scatter names at most {config.MAX_SCATTER_DOTS}"
        )


# --- Shared styling ------------------------------------------------------------------------------


def medium(color: str) -> str:
    """Weight 500 drawn as the handoff draws it (visual-spec.md section 5): a hairline stroke in the
    text's own colour, here as a text shadow a quarter of `MEDIUM_STROKE` each way."""
    d = round(config.MEDIUM_STROKE / 2, 3)
    return f"{d}px 0 0 {color}, -{d}px 0 0 {color}, 0 {d}px 0 {color}, 0 -{d}px 0 {color}"


def _axis_font() -> dict:
    return {
        "family": config.FONT_FAMILY,
        "size": config.FONT_SIZE_AXIS,
        "color": config.AXIS_COLOR,
        "shadow": medium(config.AXIS_COLOR),
    }


def _name_font(size: float = config.FONT_SIZE_AXIS) -> dict:
    """Countries' names: ink, medium weight."""
    return {
        "family": config.FONT_FAMILY,
        "size": size,
        "color": config.TEXT_PRIMARY,
        "shadow": medium(config.TEXT_PRIMARY),
    }


def hover_label(edge) -> dict:
    """Every chart's tooltip (visual-spec.md section 7.1): a white card with ink text, edged in its
    mark's colour, no pointer arrow. `edge` is one colour, or one per point. The shadow is in
    zz-overrides.css: Plotly has no setting for it."""
    return {
        "bgcolor": config.BACKGROUND,
        "bordercolor": edge,
        "font": {
            "family": config.FONT_FAMILY,
            "size": config.FONT_SIZE_BASE,
            "color": config.TEXT_PRIMARY,
        },
        "align": "left",
        "showarrow": False,
    }


def _hover_head(name: str, color: str) -> str:
    """A tooltip's first line: a dot in the mark's colour, then the name in bold. Either may be a
    template field, such as `%{customdata}` for a colour that differs from point to point."""
    return f'<span style="color:{color}">●</span> <b>{name}</b>'


def _hover_aside(text: str) -> str:
    """A tooltip's secondary line, such as the year-over-year change: muted, a size down."""
    style = f"color:{config.TEXT_MUTED};font-size:{config.FONT_SIZE_AXIS}px"
    return f'<span style="{style}">{text}</span>'


def _paper(margin: dict, x: float | None = None, y: float | None = None) -> float:
    """A point in the card's pixels (x from the left, y from the top) in paper coordinates, which
    run 0-1 across the plot area. Exactly one of `x` and `y`."""
    if x is not None:
        width = config.CHART_WIDTH - margin["l"] - margin["r"]
        return round((x - margin["l"]) / width, 6)
    height = config.CHART_HEIGHT - margin["t"] - margin["b"]
    return round((config.CHART_HEIGHT - margin["b"] - y) / height, 6)


def _middle(baseline: float, size: float) -> float:
    """Where a line of text of `size` px sits, as Plotly anchors it (by the middle of its box), for
    the handoff's baseline: the box's middle is a third of the size above the baseline."""
    return baseline - size / 3


def _text(figure, margin, x, baseline, text, font, anchor="left", name=None) -> None:
    """Text at a point in the card's pixels, by its baseline, as the handoff places it."""
    figure.add_annotation(
        x=_paper(margin, x=x),
        y=_paper(margin, y=_middle(baseline, font["size"])),
        xref="paper",
        yref="paper",
        text=text,
        showarrow=False,
        xanchor=anchor,
        yanchor="middle",
        font=font,
        name=name,
    )


def _apply_base(figure: go.Figure, title: str, margin: dict) -> None:
    """What every chart type shares: the card's title and source line, fonts, size, background, no
    legend, hover mode (visual-spec.md section 5). Title and source are drawn in the figure, so both
    conditions have them by construction."""
    figure.update_layout(
        font={
            "family": config.FONT_FAMILY,
            "size": config.FONT_SIZE_BASE,
            "color": config.TEXT_PRIMARY,
        },
        # Fixed (visual-spec.md section 5): the same size on every screen and in both conditions.
        # The margins too: Plotly would otherwise widen one to fit its tick labels, and the plot
        # would move off the handoff's place (5 px on the line chart, measured in Chrome).
        xaxis_automargin=False,
        yaxis_automargin=False,
        width=config.CHART_WIDTH,
        height=config.CHART_HEIGHT,
        autosize=False,
        plot_bgcolor=config.BACKGROUND,
        paper_bgcolor=config.BACKGROUND,
        showlegend=False,
        margin=margin,
        hovermode="closest",
    )
    _text(
        figure,
        margin,
        config.TITLE_X,
        config.TITLE_BASELINE,
        title,
        {
            "family": config.FONT_FAMILY,
            "size": config.FONT_SIZE_TITLE,
            "color": config.TEXT_PRIMARY,
            "weight": 700,
        },
        name="title",
    )
    _text(
        figure,
        margin,
        config.TITLE_X,
        config.SOURCE_BASELINE,
        config.SOURCE_TEXT,
        {"family": config.FONT_FAMILY, "size": config.FONT_SIZE_SOURCE, "color": config.TEXT_MUTED},
        name="source",
    )


def _coverage_axis(update, title: str | None = None) -> None:
    """A 0-100 coverage axis: pinned, gridded every 10, "0%" to "100%", a line on the plot's edge
    and no ticks. `update` is update_xaxes or update_yaxes. Its title, where it has one, is
    drawn by the chart as horizontal text above it (`_axis_title`); `title` puts one along the
    axis instead."""
    axis_font = _axis_font()
    update(
        title={"text": title, "font": axis_font} if title else None,
        # Pinned. An axis that rescales would change apparent steepness between tasks.
        range=list(config.Y_RANGE),
        dtick=10,
        ticksuffix="%",
        tickfont=axis_font,
        ticks="",
        ticklabelstandoff=8,
        gridcolor=config.GRIDLINE_COLOR,
        gridwidth=1,
        showline=True,
        linecolor=config.AXIS_COLOR,
        linewidth=1,
        showgrid=True,
        zeroline=False,
        fixedrange=True,
    )


def _axis_title(figure, margin, text: str, x: float = config.TITLE_X) -> None:
    """A y axis's title, horizontal, left-aligned, 24 px above the 100% label (visual-spec.md 2)."""
    _text(figure, margin, x, margin["t"] - 24, text, _axis_font(), name="axis-title")


def _category_axis(update, title: str | None = None, **extra) -> None:
    """An axis of names or years: no gridlines, no zoom."""
    axis_font = _axis_font()
    settings = {
        "title": {"text": title, "font": axis_font} if title else None,
        "type": "category",
        "tickfont": axis_font,
        "ticks": "",
        "ticklabelstandoff": 8,
        "showline": True,
        "linecolor": config.AXIS_COLOR,
        "linewidth": 1,
        "showgrid": False,
        "zeroline": False,
        "fixedrange": True,
    }
    update(**{**settings, **extra})


def _color_key() -> dict:
    """The colour key for the sequential scale, ticked every 10 so the 50% step is marked."""
    axis_font = _axis_font()
    return {
        "title": {"text": "Coverage (%)", "font": axis_font},
        "tickmode": "linear",
        "tick0": 0,
        "dtick": config.COLOR_KEY_DTICK,
        "tickfont": axis_font,
        "outlinecolor": config.AXIS_COLOR,
        "outlinewidth": 1,
        "thickness": 18,
        "len": 0.9,
    }


def _sequential() -> list[list]:
    return [[position, color] for position, color in config.SEQUENTIAL_SCALE]


def _value(entity: str, vaccine: str, year: int, source: tuple[Row, ...]) -> float | None:
    for row in runtime_data.series(entity, vaccine, source):
        if row.year == year:
            return row.coverage_pct
    raise FigureError(f"No row for {entity} {vaccine} {year}")


# --- Line ----------------------------------------------------------------------------------------

# The plot runs from x 52 to 846 and from y 68 (100%) to 468 (0%): 4 px a point. The right margin
# holds the name tags (visual-spec.md section 5).
_LINE_MARGIN = {"l": 52, "r": 204, "t": 68, "b": 52}
_LINE_X_RANGE = (config.YEAR_MIN - config.LINE_X_PAD, config.YEAR_MAX + config.LINE_X_PAD)
TAG = "tag:"


def series_colors(entities: Sequence[str]) -> dict[str, str]:
    """Each line's colour (visual-spec.md section 4): Form A's T1 countries keep their own; any
    other country takes the first colour this chart does not already use; World is the reference."""
    colors = {e: config.COUNTRY_COLORS[e] for e in entities if e in config.COUNTRY_COLORS}
    for entity in entities:
        if entity == REFERENCE:
            colors[entity] = config.REFERENCE_COLOR
        elif entity not in colors:
            used = set(colors.values())
            colors[entity] = next(c for c in config.SERIES_COLORS if c not in used)
    return colors


# Names too long for a tag's margin: the handoff's one, and DR Congo's (on A-T6 since 2026-10-11)
# as the map writes it.
_TAG_NAMES = {
    "Central African Republic": "Central African Rep.",
    "Democratic Republic of Congo": "DR Congo",
}


def tag_name(entity: str) -> str:
    """The name a tag shows, shortened where it would not fit the margin."""
    return _TAG_NAMES.get(entity, entity)


def drawn_name(entity: str, chart_type: str) -> str:
    """The name a chart of this type prints for `entity`: on the map its short name
    (`_name_country`), elsewhere its tag name. The chips use it too (2026-10-12), so a chip says
    what the chart says, and "Democratic Republic of Congo" no longer wraps a row of chips."""
    if chart_type == "map":
        return config.MAP_SHORT_NAMES.get(entity, entity)
    return tag_name(entity)


def _line(
    entities: list[str], vaccine: str, _years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """Coverage over the locked year range. Applies the locked spec: gaps stay broken, y is pinned
    to 0-100, colours go by country, World is a dashed black reference, and every line ends in a
    name tag, so colour is never the only channel. No legend (visual-spec.md section 6)."""
    figure = go.Figure()
    colors = series_colors(entities)
    for entity in entities:
        dash = config.REFERENCE_DASH if entity == REFERENCE else "solid"
        _add_series(figure, entity, vaccine, source, colors[entity], dash)

    margin = _LINE_MARGIN
    _apply_base(figure, f"{vaccine} coverage, {config.YEAR_MIN}–{config.YEAR_MAX}", margin)
    figure.update_xaxes(
        range=list(_LINE_X_RANGE),
        tickvals=list(range(config.YEAR_MIN, config.YEAR_MAX, 5)),
        tickfont=_axis_font(),
        ticks="",
        # Plotly sets a label 17 px under the axis before its standoff; the handoff says 18.
        ticklabelstandoff=1,
        showline=True,
        linecolor=config.AXIS_COLOR,
        linewidth=1,
        showgrid=False,
        zeroline=False,
    )
    _coverage_axis(figure.update_yaxes)
    # The vertical guides, as shapes on the axes, so they stand at 2005-2020 and not at 2000, which
    # the handoff leaves to the axis line.
    for year in range(config.YEAR_MIN + 5, config.YEAR_MAX, 5):
        figure.add_shape(
            type="line",
            xref="x",
            yref="y",
            x0=year,
            x1=year,
            y0=config.Y_RANGE[0],
            y1=config.Y_RANGE[1],
            line={"color": config.GRIDLINE_COLOR, "width": 1},
            layer="below",
            name="guide",
        )
    _axis_title(figure, margin, "Coverage")
    _text(
        figure,
        margin,
        config.CHART_WIDTH - margin["r"],
        config.CHART_HEIGHT - margin["b"] + 18,
        "Year",
        _axis_font(),
        anchor="right",
        name="axis-title",
    )
    _add_tags(figure, vaccine, source)
    return figure


def _add_series(
    figure: go.Figure,
    entity: str,
    vaccine: str,
    source: tuple[Row, ...],
    color: str,
    dash: str,
) -> None:
    series = runtime_data.series(entity, vaccine, source)
    last = max((i for i, row in enumerate(series) if row.coverage_pct is not None), default=None)
    sizes = [config.END_DOT_SIZE if i == last else config.MARKER_SIZE for i in range(len(series))]
    rings = [config.END_DOT_RING if i == last else 0 for i in range(len(series))]
    figure.add_trace(
        go.Scatter(
            x=[row.year for row in series],
            # None, not 0 and not omitted: Plotly breaks the line here, which is the point.
            y=[row.coverage_pct for row in series],
            name=entity,
            mode="lines+markers",
            connectgaps=False,
            line={"color": color, "width": config.LINE_WIDTH, "dash": dash},
            marker={
                "color": color,
                # Explicit: with a list of sizes Plotly takes a bubble chart and draws at 0.7.
                "opacity": 1,
                "size": sizes,
                "line": {"color": config.BACKGROUND, "width": rings},
            },
            customdata=change_labels(series),
            hovertemplate=(
                f"{_hover_head(entity, color)}<br>%{{x}}: %{{y:.0f}}%"
                f"<br>{_hover_aside('%{customdata}')}<extra></extra>"
            ),
            hoverlabel=hover_label(color),
        )
    )


def change_labels(series: Sequence[Row]) -> list[str]:
    """Year-over-year change text for the hover tooltip, one entry per point.

    Interactive-only BY CONSTRUCTION rather than by branching: the text sits in both conditions'
    figures, and `staticPlot: True` means a static participant never fires a hover to read it. A
    drawn indicator could not work that way — it would make the two figures differ.

    Deltas are computed from the ROUNDED values the tooltip displays, so the arithmetic a
    participant can do on screen always agrees with the numbers they were shown.

    A gap is reported as a gap. Differencing across one would invent a year-over-year change out of
    two values that are not a year apart, which is the same error the chart refuses to make by
    leaving `connectgaps` off.
    """
    labels: list[str] = []
    for index, row in enumerate(series):
        if row.coverage_pct is None:
            # Never displayed — Plotly renders no point here — but the array must stay aligned.
            labels.append("")
        elif index == 0:
            labels.append("first year shown")
        elif series[index - 1].coverage_pct is None:
            labels.append(f"no {series[index - 1].year} value reported")
        else:
            delta = round(row.coverage_pct) - round(series[index - 1].coverage_pct)
            previous_year = series[index - 1].year
            labels.append(
                f"no change vs {previous_year}"
                if delta == 0
                else f"{delta:+d} pts vs {previous_year}"
            )
    return labels


def _x_px(year: float) -> float:
    """A year's place across the line chart, in the card's pixels."""
    low, high = _LINE_X_RANGE
    width = config.CHART_WIDTH - _LINE_MARGIN["l"] - _LINE_MARGIN["r"]
    return _LINE_MARGIN["l"] + (year - low) / (high - low) * width


def _y_px(value: float) -> float:
    """A coverage value's height on the line chart, in the card's pixels from the top."""
    height = config.CHART_HEIGHT - _LINE_MARGIN["t"] - _LINE_MARGIN["b"]
    return config.CHART_HEIGHT - _LINE_MARGIN["b"] - value / config.Y_RANGE[1] * height


def tag_centres(figure: go.Figure) -> dict[str, float]:
    """Each name tag's centre, in the card's pixels from the top, by the line it names."""
    height = config.CHART_HEIGHT - _LINE_MARGIN["t"] - _LINE_MARGIN["b"]
    return {
        annotation.name[len(TAG) :]: round(
            config.CHART_HEIGHT - _LINE_MARGIN["b"] - annotation.y * height, 3
        )
        for annotation in figure.layout.annotations
        if (annotation.name or "").startswith(TAG)
    }


def _add_tags(figure: go.Figure, vaccine: str, source: tuple[Row, ...]) -> None:
    """A name tag at the end of every line, joined to it by a leader (visual-spec.md section 6).

    Tags keep the order of their lines' last reported values and are spread so their centres are
    at least TAG_GAP px apart, between 10 px above the plot's top and 4 px above its bottom: the
    handoff's `spread()`, which is `spread_labels`. Computed here, in `build_figure`, so both
    conditions get the same tags.

    Everything a tag draws -- leader, pill, dot and name -- is named `tag:<entity>`, so hiding a
    line takes its tag with it (`set_visible`). All of it is in paper coordinates: Plotly does not
    draw an annotation whose data coordinate lies outside its axis range (China's label on A-T1,
    2026-09-23), and a tag stays put when the x axis is zoomed.
    """
    margin = _LINE_MARGIN
    ends = []
    for trace in figure.data:
        reported = [
            r
            for r in runtime_data.series(trace.name, vaccine, source)
            if r.coverage_pct is not None
        ]
        if reported:
            ends.append((_y_px(reported[-1].coverage_pct), _x_px(reported[-1].year), trace))
    ends.sort(key=lambda end: end[0])
    top, bottom = margin["t"], config.CHART_HEIGHT - margin["b"]
    centres = spread_labels([y for y, _x, _t in ends], top - 10, bottom - 4, config.TAG_GAP)

    def point(x: float, y: float) -> str:
        return f"{_paper(margin, x=x)},{_paper(margin, y=y)}"

    tag_x, half = config.TAG_X, config.TAG_HEIGHT / 2
    for (y_end, x_end, trace), centre in zip(ends, centres, strict=True):
        name = f"{TAG}{trace.name}"
        color = trace.line.color
        label = tag_name(trace.name)
        # The handoff's own width estimate: 19 px to the name, 0.58 em a character, 7 px after it.
        width = 19 + len(label) * config.FONT_SIZE_AXIS * 0.58 + 7
        figure.add_shape(
            type="path",
            xref="paper",
            yref="paper",
            path=(
                f"M{point(x_end + 6, y_end)} C{point(tag_x - 4, y_end)} "
                f"{point(x_end + 14, centre)} {point(tag_x, centre)}"
            ),
            line={"color": color, "width": 1.4},
            layer="above",
            name=name,
        )
        figure.add_shape(
            type="path",
            xref="paper",
            yref="paper",
            path=_pill(tag_x, centre - half, width, config.TAG_HEIGHT, point),
            fillcolor=config.BACKGROUND,
            line={"color": config.TAG_EDGE_COLOR, "width": 1},
            layer="above",
            name=name,
        )
        figure.add_shape(
            type="circle",
            xref="paper",
            yref="paper",
            x0=_paper(margin, x=tag_x + 6),
            x1=_paper(margin, x=tag_x + 14),
            y0=_paper(margin, y=centre + 4),
            y1=_paper(margin, y=centre - 4),
            fillcolor=color,
            line={"width": 0},
            layer="above",
            name=name,
        )
        figure.add_annotation(
            x=_paper(margin, x=tag_x + 19),
            y=_paper(margin, y=centre),
            xref="paper",
            yref="paper",
            text=label,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=_name_font(),
            name=name,
        )


def _pill(x: float, y: float, width: float, height: float, point) -> str:
    """A fully rounded rectangle as an SVG path, its ends drawn with cubic curves: Plotly's paths
    take no arcs. `point` turns card pixels into the path's coordinates."""
    r, k = height / 2, 0.5523 * height / 2
    left, right, top, bottom, mid = x + r, x + width - r, y, y + height, y + r
    return (
        f"M{point(left, top)} L{point(right, top)} "
        f"C{point(right + k, top)} {point(x + width, mid - k)} {point(x + width, mid)} "
        f"C{point(x + width, mid + k)} {point(right + k, bottom)} {point(right, bottom)} "
        f"L{point(left, bottom)} "
        f"C{point(left - k, bottom)} {point(x, mid + k)} {point(x, mid)} "
        f"C{point(x, mid - k)} {point(left - k, top)} {point(left, top)} Z"
    )


def spread_labels(values: list[float], lower: float, upper: float, gap: float) -> list[float]:
    """Heights for labels wanting to sit at `values` (ascending), at least `gap` apart.

    Moves the labels as little as possible in total (least squares), keeps their order, and keeps
    them within [lower, upper]. Labels already far enough apart do not move at all.

    Writing each height as `w[i] + i * gap` turns "at least `gap` apart" into "`w` never
    decreases", which is isotonic regression -- solved exactly by pooling adjacent violators. A
    common bound on every `w` is then a clip, because clipping an isotonic fit to one interval
    gives the best fit within it.
    """
    if not values:
        return []
    if (len(values) - 1) * gap > upper - lower:
        raise FigureError(f"{len(values)} labels cannot sit {gap} apart within {lower}-{upper}")
    targets = [value - index * gap for index, value in enumerate(values)]
    blocks: list[list[float]] = []  # [mean, size] of each pooled run
    for target in targets:
        blocks.append([target, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            mean, size = blocks.pop()
            previous_mean, previous_size = blocks.pop()
            pooled = previous_size + size
            blocks.append([(previous_mean * previous_size + mean * size) / pooled, pooled])
    fitted = [mean for mean, size in blocks for _ in range(int(size))]
    ceiling = upper - (len(values) - 1) * gap
    return [round(min(max(w, lower), ceiling) + index * gap, 3) for index, w in enumerate(fitted)]


# --- Bar -----------------------------------------------------------------------------------------


def _bar(
    entities: list[str], vaccine: str, years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """One year's coverage, one bar per country, in the order listed (visual-spec.md section 1).

    Each bar is its country's colour (`bar_color`), its top rounded, named under it; no value on
    it. The y axis is the line chart's, pinned to 0-100 and gridded every 10. "Countries in
    alphabetical order" names the order, and `sort_bars` rewrites it.
    """
    (year,) = years
    colors = [bar_color(entity) for entity in entities]
    figure = go.Figure(
        go.Bar(
            x=entities,
            y=[_value(entity, vaccine, year, source) for entity in entities],
            name=f"{vaccine} {year}",
            # 62% of each slot, at most 64 px: ten bars on 974 px are 60.4 px wide.
            width=min(0.62, 64 / (_BAR_PLOT_WIDTH / len(entities))),
            marker={"color": colors, "cornerradius": 6, "line": {"width": 0}},
            # Each bar's colour, for its tooltip's dot. A sort reorders the axis, not the points.
            customdata=colors,
            hovertemplate=(
                f"{_hover_head('%{x}', '%{customdata}')}<br>{year}: %{{y:.0f}}%<extra></extra>"
            ),
            hoverlabel=hover_label(colors),
        )
    )
    margin = _BAR_MARGIN
    _apply_base(figure, f"{vaccine} coverage, {year}", margin)
    _category_axis(
        figure.update_xaxes,
        categoryorder="array",
        categoryarray=entities,
        tickfont=_name_font(),
        ticklabelstandoff=1,
    )
    _coverage_axis(figure.update_yaxes)
    _axis_title(figure, margin, "Coverage")
    _text(
        figure,
        margin,
        config.CHART_WIDTH - margin["r"],
        margin["t"] - 24,
        BAR_ORDER_LABELS["alpha"],
        {"family": config.FONT_FAMILY, "size": config.FONT_SIZE_AXIS, "color": config.TEXT_MUTED},
        anchor="right",
        name=ORDER_LABEL,
    )
    return figure


_BAR_MARGIN = {"l": 52, "r": 24, "t": 68, "b": 52}
_BAR_PLOT_WIDTH = config.CHART_WIDTH - _BAR_MARGIN["l"] - _BAR_MARGIN["r"]


def bar_color(entity: str) -> str:
    """A bar's colour: its country's line colour, or its own (visual-spec.md section 4)."""
    color = config.COUNTRY_COLORS.get(entity) or config.BAR_COLORS.get(entity)
    if color is None:
        raise FigureError(f"{entity} has no bar colour; add one to config.BAR_COLORS by the search")
    return color


# --- Scatter -------------------------------------------------------------------------------------


def _scatter(
    entities: list[str], vaccine: str, years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """Each country one named dot: coverage in the first year across, in the second year up
    (visual-spec.md sections 1 and 4, the chart handoff).

    The axes share one scale on a square 400 px plot, so the dashed diagonal is a true 45-degree
    line of no change and the distance above it is the improvement. Each dot is coloured by its
    change (`change_color`) and named beside it on a white knockout, so gridlines and the diagonal
    stop short of the name. No legend: a stepped key stands in the right margin.
    """
    first, last = years
    margin = _SCATTER_MARGIN
    figure = go.Figure()
    for entity in entities:
        x, y = _value(entity, vaccine, first, source), _value(entity, vaccine, last, source)
        color = change_color(y - x)
        figure.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                name=entity,
                mode="markers",
                # A dot at 99 would be cut in half at the plot's edge.
                cliponaxis=False,
                marker={"color": color, "size": config.SCATTER_MARKER_SIZE, "line": {"width": 0}},
                hovertemplate=(
                    f"{_hover_head(entity, color)}<br>{first}: %{{x:.0f}}%"
                    f"<br>{last}: %{{y:.0f}}%<extra></extra>"
                ),
                hoverlabel=hover_label(color),
            )
        )
        _name_dot(figure, entity, x, y)
    _apply_base(figure, f"{vaccine} coverage, {first} and {last}", margin)
    for update in (figure.update_xaxes, figure.update_yaxes):
        _coverage_axis(update)
        update(dtick=25)
    figure.update_xaxes(ticklabelstandoff=1)
    figure.update_yaxes(scaleanchor="x", scaleratio=1)
    _axis_title(figure, margin, f"Coverage in {last}", x=margin["l"] - 44)
    _text(
        figure,
        margin,
        margin["l"] + 428,
        config.CHART_HEIGHT - margin["b"] + 18,
        f"Coverage in {first}",
        _axis_font(),
        name="axis-title",
    )
    # The diagonal, between the gridlines and the dots, under the names' knockouts.
    figure.add_shape(
        type="line",
        x0=config.Y_RANGE[0],
        y0=config.Y_RANGE[0],
        x1=config.Y_RANGE[1],
        y1=config.Y_RANGE[1],
        line={"color": config.TEXT_MUTED, "width": 1.5, "dash": "6px,5px"},
        layer="between",
        name="diagonal",
    )
    # Knockouts go after the diagonal so they cover it: move them to the end of the shape list.
    shapes = list(figure.layout.shapes)
    figure.layout.shapes = [s for s in shapes if s.name == "diagonal"] + [
        s for s in shapes if s.name != "diagonal"
    ]
    figure.add_annotation(
        x=16,
        y=16,
        text="No change",
        showarrow=False,
        textangle=-45,
        bgcolor=config.BACKGROUND,
        borderpad=3,
        font={
            "family": config.FONT_FAMILY,
            "size": config.FONT_SIZE_AXIS,
            "color": config.TEXT_MUTED,
        },
        name="no-change",
    )
    for (x, y), text, color in (
        ((12.5, 95), "Coverage rose ↑", config.CHANGE_STEPS[0][1]),
        ((87.5, 4), "Coverage fell ↓", config.CHANGE_STEPS[-1][1]),
    ):
        figure.add_annotation(
            x=x,
            y=y,
            yshift=round(config.FONT_SIZE_AXIS / 3, 3),
            text=text,
            showarrow=False,
            font={
                "family": config.FONT_FAMILY,
                "size": config.FONT_SIZE_AXIS,
                "color": color,
                "shadow": medium(color),
            },
            name="corner",
        )
    _change_key(figure, first)
    return figure


_SCATTER_MARGIN = {"l": 290, "r": 360, "t": 68, "b": 52}
_DOT = "dot:"
_DOT_NAME_SIZE = 11.5


def change_color(change: float) -> str:
    """A dot's colour by its change in points (visual-spec.md section 4). A change exactly on a
    boundary takes the step nearer zero."""
    steps = config.CHANGE_STEPS
    if change > steps[0][0]:
        return steps[0][1]
    for (upper, _upper_color), (lower, color) in zip(steps, steps[1:], strict=False):
        if lower is None:
            return color
        if lower >= 0 and change > lower:
            return color
        if lower < 0 and change >= lower:
            return color
        del upper
    return steps[-1][1]


def _name_dot(figure: go.Figure, entity: str, x: float, y: float) -> None:
    """A dot's name beside it, on a white knockout 20 px tall that runs from 9 px behind the dot to
    5 px past the name (visual-spec.md section 1). Both are named `dot:<entity>`, so a chip that
    hides the dot hides them too. The handoff's width estimate: 0.56 em a character."""
    side = config.SCATTER_LABEL_SIDES.get(entity, "right")
    label = tag_name(entity)
    width = len(label) * _DOT_NAME_SIZE * 0.56
    point = 1 / 4  # data units per pixel: 4 px a point
    name = f"{_DOT}{entity}"
    if side == "above":
        x0, x1 = x - (width / 2 + 5) * point, x + (width / 2 + 5) * point
        y0, y1 = y - 9 * point, y + 23 * point
        figure.add_annotation(
            x=x,
            y=y,
            yshift=13,
            text=label,
            showarrow=False,
            font=_name_font(_DOT_NAME_SIZE),
            name=name,
        )
    else:
        sign = 1 if side == "right" else -1
        near, far = x - sign * 9 * point, x + sign * (8 + width + 5) * point
        x0, x1 = min(near, far), max(near, far)
        y0, y1 = y - 10 * point, y + 10 * point
        figure.add_annotation(
            x=x,
            y=y,
            xshift=sign * 8,
            xanchor="left" if sign > 0 else "right",
            yanchor="middle",
            text=label,
            showarrow=False,
            font=_name_font(_DOT_NAME_SIZE),
            name=name,
        )
    figure.add_shape(
        type="rect",
        x0=round(x0, 4),
        x1=round(x1, 4),
        y0=round(y0, 4),
        y1=round(y1, 4),
        fillcolor=config.BACKGROUND,
        line={"width": 0},
        layer="between",
        name=name,
    )


def _change_key(figure: go.Figure, first: int) -> None:
    """The stepped key in the right margin (visual-spec.md section 4): seven 20 x 36 px blocks 2 px
    apart, the outer ends rounded 6 px, the boundaries in percentage points, three names beside."""
    margin = figure.layout.margin.to_plotly_json()
    left, top, step, width = 820, margin["t"] + 58, 36, 20

    def x(px: float) -> float:
        return _paper(margin, x=px)

    def y(px: float) -> float:
        return _paper(margin, y=px)

    _text(figure, margin, left, top - 16, f"Change since {first}", _axis_font(), name="key")
    colors = [color for _bound, color in config.CHANGE_STEPS]
    for index, color in enumerate(colors):
        y0 = top + index * step + (1 if index else 0)
        y1 = top + (index + 1) * step - (1 if index < len(colors) - 1 else 0)
        if index in (0, len(colors) - 1):
            figure.add_shape(
                type="path",
                xref="paper",
                yref="paper",
                path=_rounded_rect(
                    x(left),
                    y(y0),
                    x(left + width),
                    y(y1),
                    x(left + 6) - x(left),
                    y(top + 6) - y(top),
                ),
                fillcolor=color,
                line={"width": 0},
                layer="above",
                name="key",
            )
            inner = (y1 - 7, y1) if index == 0 else (y0, y0 + 7)
            y0, y1 = inner
        figure.add_shape(
            type="rect",
            xref="paper",
            yref="paper",
            x0=x(left),
            x1=x(left + width),
            y0=y(y1),
            y1=y(y0),
            fillcolor=color,
            line={"width": 0},
            layer="above",
            name="key",
        )
    bounds = ["+100", "+40", "+20", "+5", "−5", "−20", "−40", "−100"]
    for index, bound in enumerate(bounds):
        _text(
            figure,
            margin,
            left + width + 10,
            top + index * step + config.FONT_SIZE_AXIS / 3,
            f"{bound} pts",
            _axis_font(),
            name="key",
        )
    for band, text in (
        (0.5, "↑ Coverage rose"),
        (3.5, "Little or no change"),
        (6.5, "↓ Coverage fell"),
    ):
        _text(
            figure,
            margin,
            left + width + 74,
            top + band * step + config.FONT_SIZE_AXIS / 3,
            text,
            _name_font(),
            name="key",
        )


# --- Heatmap -------------------------------------------------------------------------------------


def _heatmap(
    entities: list[str], vaccine: str, years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """Countries down, years across, coverage as one of nine bands: dark is low (visual-spec.md
    sections 1 and 4).

    Plotly cannot round a heatmap's cells, so the cells are drawn as shapes (`_draw_cells`), and
    the heatmap trace beneath them is fully transparent: it carries the hover, and its banded
    colour scale gives the tooltip each cell's colour. No value is written in a cell. The static
    condition reads colour against the key above the grid; the exact value is in the hover text,
    out of the static participant's reach.
    """
    margin = _HEAT_MARGIN
    z = [[_value(entity, vaccine, year, source) for year in years] for entity in entities]
    # Each cell's band, for its tooltip's dot and edge. A transparent trace would otherwise give
    # its tooltips Plotly's default grey. A gap has no tooltip (`hoverongaps`).
    bands = [
        [config.NO_DATA_COLOR if v is None else band_color(v, config.HEATMAP_BANDS) for v in row]
        for row in z
    ]
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=[str(year) for year in years],
            y=entities,
            zmin=config.Y_RANGE[0],
            zmax=config.Y_RANGE[1],
            colorscale=banded_scale(config.HEATMAP_BANDS),
            showscale=False,
            opacity=0,
            hoverongaps=False,
            customdata=bands,
            hovertemplate=(
                f"{_hover_head('%{y}', '%{customdata}')}<br>%{{x}}: %{{z:.0f}}%<extra></extra>"
            ),
            hoverlabel=hover_label(bands),
        )
    )
    _apply_base(figure, f"{vaccine} coverage, selected years", margin)
    heat_font = {**_axis_font(), "size": _HEAT_FONT}
    _category_axis(figure.update_xaxes, side="top", tickfont=heat_font, showline=False)
    # The first country listed is the top row, as it would be read. The order is written out, so
    # the row sort's Default (`sort_rows`) is exactly this figure.
    _category_axis(
        figure.update_yaxes,
        autorange="reversed",
        categoryorder="array",
        categoryarray=entities,
        tickfont=_name_font(_HEAT_FONT),
        tickvals=entities,
        ticktext=[tag_name(entity) for entity in entities],
        ticklabelstandoff=12,
        showline=False,
    )
    _text(
        figure,
        margin,
        margin["l"] - 12,
        margin["t"] - 9,
        ROW_ORDER_LABELS["default"],
        {"family": config.FONT_FAMILY, "size": _HEAT_FONT, "color": config.TEXT_MUTED},
        anchor="right",
        name=ORDER_LABEL,
    )
    _heat_key(figure)
    _draw_cells(figure, entities, faded=())
    return figure


# The grid runs from x 215 to 995 and y 118 to 492 in the card: six 130 px columns, rows 46.75 px
# tall for eight rows, 4 px gaps, 4 px corners (visual-spec.md section 1).
_HEAT_MARGIN = {"l": 215, "r": 55, "t": 118, "b": 28}
_HEAT_FONT = 15
_CELL = "cell:"
_CELL_GAP = 4
_CELL_RADIUS = 4


def banded_scale(bands: Sequence[tuple[int, str]]) -> list[list]:
    """A Plotly colour scale that steps at each band's lower bound instead of blending."""
    low, high = config.Y_RANGE
    scale = []
    for index, (bound, color) in enumerate(bands):
        upper = bands[index + 1][0] if index + 1 < len(bands) else high
        scale += [[(bound - low) / (high - low), color], [(upper - low) / (high - low), color]]
    return scale


def band_color(value: float, bands: Sequence[tuple[int, str]]) -> str:
    """The colour of the band whose lower bound `value` reaches."""
    return [color for bound, color in bands if value >= bound][-1]


def _rounded_rect(x0: float, y0: float, x1: float, y1: float, rx: float, ry: float) -> str:
    """A rectangle with rounded corners as an SVG path, corners drawn as cubic curves (Plotly's
    paths take no arcs). `rx` and `ry` are the corner's radius in each axis's own units, signed
    as the axis runs from (x0, y0) to (x1, y1): in paper coordinates, which run upward, `ry` is
    negative when y0 is the top."""
    kx, ky = 0.5523 * rx, 0.5523 * ry
    return (
        f"M{x0 + rx},{y0} L{x1 - rx},{y0} C{x1 - rx + kx},{y0} {x1},{y0 + ry - ky} {x1},{y0 + ry} "
        f"L{x1},{y1 - ry} C{x1},{y1 - ry + ky} {x1 - rx + kx},{y1} {x1 - rx},{y1} "
        f"L{x0 + rx},{y1} C{x0 + rx - kx},{y1} {x0},{y1 - ry + ky} {x0},{y1 - ry} "
        f"L{x0},{y0 + ry} C{x0},{y0 + ry - ky} {x0 + rx - kx},{y0} {x0 + rx},{y0} Z"
    )


def _draw_cells(figure: go.Figure, order: Sequence[str], faded: Sequence[str]) -> None:
    """Draw every cell where its row now stands, the rows in `faded` at FADED_OPACITY.

    The cells are shapes on the axes, placed by row position, so a sort moves them by redrawing:
    each row keeps its cells and colours, and nothing else moves. A cell with no value is plain
    `NO_DATA_COLOR` and reads "No data", never the white of the page.
    """
    cells = _only(figure, go.Heatmap)
    margin = figure.layout.margin.to_plotly_json()
    columns, rows = len(cells.x), len(cells.y)
    width = (config.CHART_WIDTH - margin["l"] - margin["r"]) / columns
    height = (config.CHART_HEIGHT - margin["t"] - margin["b"]) / rows
    # Data units per pixel: one column is one unit across, one row one unit down.
    gap_x, gap_y = _CELL_GAP / 2 / width, _CELL_GAP / 2 / height
    rx, ry = _CELL_RADIUS / width, _CELL_RADIUS / height
    figure.layout.shapes = [
        shape for shape in figure.layout.shapes if not (shape.name or "").startswith(_CELL)
    ]
    figure.layout.annotations = [
        a for a in figure.layout.annotations if not (a.name or "").startswith(_CELL)
    ]
    values = dict(zip((str(name) for name in cells.y), cells.z, strict=True))
    for position, name in enumerate(order):
        opacity = config.FADED_OPACITY if name in faded else 1
        for column, value in enumerate(values[name]):
            figure.add_shape(
                type="path",
                xref="x",
                yref="y",
                path=_rounded_rect(
                    round(column - 0.5 + gap_x, 6),
                    round(position - 0.5 + gap_y, 6),
                    round(column + 0.5 - gap_x, 6),
                    round(position + 0.5 - gap_y, 6),
                    round(rx, 6),
                    round(ry, 6),
                ),
                fillcolor=(
                    config.NO_DATA_COLOR
                    if value is None
                    else band_color(value, config.HEATMAP_BANDS)
                ),
                line={"width": 0},
                opacity=opacity,
                layer="below",
                name=f"{_CELL}{name}",
            )
            if value is None:
                figure.add_annotation(
                    x=column,
                    y=position,
                    xref="x",
                    yref="y",
                    text="No data",
                    showarrow=False,
                    font={
                        "family": config.FONT_FAMILY,
                        "size": _HEAT_FONT,
                        "color": config.TEXT_MUTED,
                    },
                    opacity=opacity,
                    name=f"{_CELL}{name}",
                )


def _heat_key(figure: go.Figure) -> None:
    """The stepped key centred above the grid (visual-spec.md section 4): "Coverage", then a 560 x
    16 bar of nine blocks with 2 px gaps, rounded 5 px at its ends and outlined in the gridline
    colour, its boundaries labelled under it."""
    margin = figure.layout.margin.to_plotly_json()
    bands = config.HEATMAP_BANDS
    block = 560 / len(bands)
    # "Coverage" (about 84 px) and the bar together are centred on the card's 525 px middle.
    left, top, height = 525 - (560 - 84) / 2, 40, 16
    right = left + block * len(bands)

    def x(px: float) -> float:
        return _paper(margin, x=px)

    def y(px: float) -> float:
        return _paper(margin, y=px)

    _text(
        figure,
        margin,
        left - 12,
        top + height / 2 + _HEAT_FONT / 3,
        "Coverage",
        {**_axis_font(), "size": _HEAT_FONT},
        anchor="right",
        name="key",
    )
    for index, (_bound, color) in enumerate(bands):
        x0 = left + index * block + (1 if index else 0)
        x1 = left + (index + 1) * block - (1 if index < len(bands) - 1 else 0)
        if index in (0, len(bands) - 1):
            # The bar's two ends are rounded: draw the end block rounded and square off its inner
            # side with a plain rectangle laid over it.
            figure.add_shape(
                type="path",
                xref="paper",
                yref="paper",
                path=_rounded_rect(
                    x(x0),
                    y(top),
                    x(x1),
                    y(top + height),
                    x(left + 5) - x(left),
                    y(top + 5) - y(top),
                ),
                fillcolor=color,
                line={"width": 0},
                layer="above",
                name="key",
            )
            inner = (x1 - 6, x1) if index == 0 else (x0, x0 + 6)
            figure.add_shape(
                type="rect",
                xref="paper",
                yref="paper",
                x0=x(inner[0]),
                x1=x(inner[1]),
                y0=y(top + height),
                y1=y(top),
                fillcolor=color,
                line={"width": 0},
                layer="above",
                name="key",
            )
        else:
            figure.add_shape(
                type="rect",
                xref="paper",
                yref="paper",
                x0=x(x0),
                x1=x(x1),
                y0=y(top + height),
                y1=y(top),
                fillcolor=color,
                line={"width": 0},
                layer="above",
                name="key",
            )
    figure.add_shape(
        type="path",
        xref="paper",
        yref="paper",
        path=_rounded_rect(
            x(left), y(top), x(right), y(top + height), x(left + 5) - x(left), y(top + 5) - y(top)
        ),
        line={"color": config.GRIDLINE_COLOR, "width": 1},
        layer="above",
        name="key",
    )
    labels = [0, *[bound for bound, _color in bands[1:]], config.Y_RANGE[1]]
    for index, value in enumerate(labels):
        _text(
            figure,
            margin,
            left + index * block,
            top + height + 18,
            f"{value}%",
            {**_axis_font(), "size": _HEAT_FONT},
            anchor="center",
            name="key",
        )


# --- Map -----------------------------------------------------------------------------------------


def _map(
    entities: list[str], vaccine: str, years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """One year's coverage as one of seven bands on a map of Africa, one country per entity
    (visual-spec.md sections 1 and 4, the chart handoff).

    Only the countries the item names are coloured; the rest are plain land. Each coloured country
    is named on the map, inside it or beside it on a leader. The view is fixed. The stepped key
    stands at the right, with no "No data" block: the plain countries report coverage, they are
    only outside the question.
    """
    (year,) = years
    codes, values = [], []
    for entity in entities:
        row = next(r for r in runtime_data.series(entity, vaccine, source) if r.year == year)
        if row.iso_code.startswith("OWID"):
            raise FigureError(f"{entity} is an aggregate, not a country; it has no shape to colour")
        codes.append(row.iso_code)
        values.append(row.coverage_pct)
    margin = _MAP_MARGIN
    # Each country's band, for its tooltip's dot and edge.
    bands = [config.NO_DATA_COLOR if v is None else band_color(v, config.MAP_BANDS) for v in values]
    figure = go.Figure(
        go.Choropleth(
            locations=codes,
            z=values,
            locationmode="ISO-3",
            text=entities,
            zmin=config.Y_RANGE[0],
            zmax=config.Y_RANGE[1],
            colorscale=banded_scale(config.MAP_BANDS),
            showscale=False,
            marker={"line": {"color": config.MAP_BORDER_COLOR, "width": 1.25}},
            # How the highlight and the chips draw (`set_threshold`, `set_visible`): countries at
            # full strength are selected, the rest fade. Nothing is selected until a control acts.
            selected={"marker": {"opacity": 1.0}},
            unselected={"marker": {"opacity": config.FADED_OPACITY}},
            customdata=bands,
            hovertemplate=(
                f"{_hover_head('%{text}', '%{customdata}')}<br>{year}: %{{z:.0f}}%<extra></extra>"
            ),
            hoverlabel=hover_label(bands),
        )
    )
    _apply_base(figure, f"{vaccine} coverage, {year}", margin)
    figure.update_geos(
        scope=MAP_SCOPE,
        resolution=MAP_RESOLUTION,
        projection_type="mercator",
        showframe=False,
        showland=True,
        landcolor=config.MAP_LAND_COLOR,
        showcountries=True,
        countrycolor=config.MAP_BORDER_COLOR,
        countrywidth=1,
        showcoastlines=True,
        coastlinecolor=config.MAP_COAST_COLOR,
        coastlinewidth=2,
        showlakes=False,
        showocean=False,
        bgcolor=config.BACKGROUND,
        lataxis_range=list(config.MAP_LAT_RANGE),
        lonaxis_range=list(config.MAP_LON_RANGE),
    )
    for entity, code, value in zip(entities, codes, values, strict=True):
        _name_country(figure, entity, code, value)
    _map_key(figure)
    # A fixed view: no drag-to-pan. The modebar's map zoom buttons are removed in graph_config.
    figure.update_layout(dragmode=False)
    return figure


# The continent fills about x 220 to 584 and y 64 to 474 in the card, as in the handoff's africa
# map.png; the frame runs wider, x 150 to 654, so names on leaders beside the coast are not cut off
# (a geo trace's text is clipped to its frame). The key stands at x 694 (visual-spec.md section 4).
_MAP_MARGIN = {"l": 150, "r": 396, "t": 64, "b": 46}
_LABEL = "label:"
_MAP_NAME_SIZE = 10
# White on the four darkest bands, ink on the rest: whichever reads better, as the handoff picks
# (visual-spec.md section 1). On 60-70 white is 4.80:1 and ink 3.49:1; on 70-80 ink wins.
_WHITE_ON = {color for _bound, color in config.MAP_BANDS[:4]}


def map_centroid(code: str) -> tuple[float, float]:
    """A country's centre as Plotly's own geometry gives it (`ct`, longitude and latitude)."""
    return _centroids()[code]


_CENTROIDS: dict[str, tuple[float, float]] = {}


def _centroids() -> dict[str, tuple[float, float]]:
    """Read once from the geometry the app serves (`src/assets/geo_africa.js`)."""
    if not _CENTROIDS:
        import json

        text = (config.PROJECT_ROOT / "src" / "assets" / "geo_africa.js").read_text(
            encoding="utf-8"
        )
        topology = json.loads(text[text.index("= {") + 2 : text.rindex("}") + 1])
        for geometry in topology["objects"]["countries"]["geometries"]:
            _CENTROIDS[geometry["id"]] = tuple(geometry["properties"]["ct"])
    return _CENTROIDS


def _name_country(figure: go.Figure, entity: str, code: str, value: float | None) -> None:
    """A coloured country's name: inside it, or beside it on a leader (visual-spec.md section 1).
    Every part is a text-only geo trace named `label:<entity>`, with no hover of its own."""
    lon, lat = map_centroid(code)
    text = config.MAP_SHORT_NAMES.get(entity, entity)
    name = f"{_LABEL}{entity}"
    outside = config.MAP_LABEL_OUTSIDE.get(entity)
    if outside is None:
        dlon, dlat = config.MAP_LABEL_NUDGE.get(entity, (0, 0))
        fill = band_color(value, config.MAP_BANDS) if value is not None else None
        color = config.BACKGROUND if fill in _WHITE_ON else config.TEXT_PRIMARY
        figure.add_trace(
            go.Scattergeo(
                lon=[lon + dlon],
                lat=[lat + dlat],
                mode="text",
                text=[text],
                textfont={
                    "family": config.FONT_FAMILY,
                    "size": _MAP_NAME_SIZE,
                    "color": color,
                    "weight": 700,
                },
                hoverinfo="skip",
                showlegend=False,
                name=name,
            )
        )
        return
    label_lon, label_lat, side = outside
    figure.add_trace(
        go.Scattergeo(
            lon=[lon, label_lon],
            lat=[lat, label_lat],
            mode="lines",
            line={"color": config.TEXT_PRIMARY, "width": 1},
            hoverinfo="skip",
            showlegend=False,
            name=name,
        )
    )
    position = {
        "left": "middle left",
        "right": "middle right",
        "above": "top center",
        "below": "bottom center",
    }[side]
    figure.add_trace(
        go.Scattergeo(
            lon=[lon, label_lon],
            lat=[lat, label_lat],
            mode="markers+text",
            marker={"size": [4, 0], "color": config.TEXT_PRIMARY, "line": {"width": 0}},
            text=["", text],
            textposition=position,
            textfont={
                "family": config.FONT_FAMILY,
                "size": _MAP_NAME_SIZE,
                "color": config.TEXT_PRIMARY,
                "weight": 700,
            },
            hoverinfo="skip",
            showlegend=False,
            name=name,
        )
    )


def _map_key(figure: go.Figure) -> None:
    """The stepped key at the right (visual-spec.md section 4): seven 22 x 26 px blocks, rounded
    4 px, 5 px apart, the highest band at the top, the boundaries labelled between them."""
    margin = figure.layout.margin.to_plotly_json()
    left, top, height, gap, width = 694, 108, 26, 5, 22

    def x(px: float) -> float:
        return _paper(margin, x=px)

    def y(px: float) -> float:
        return _paper(margin, y=px)

    _text(figure, margin, left, top - 16, "Coverage", _axis_font(), name="key")
    for index, (_bound, color) in enumerate(reversed(config.MAP_BANDS)):
        y0 = top + index * (height + gap)
        figure.add_shape(
            type="path",
            xref="paper",
            yref="paper",
            path=_rounded_rect(
                x(left),
                y(y0),
                x(left + width),
                y(y0 + height),
                x(left + 4) - x(left),
                y(top + 4) - y(top),
            ),
            fillcolor=color,
            line={"width": 0},
            layer="above",
            name="key",
        )
    bounds = [bound for bound, _color in config.MAP_BANDS[1:]]
    labels = [(top, "100%")]
    labels += [
        (top + (index + 1) * (height + gap) - gap / 2, f"{bound}%")
        for index, bound in enumerate(reversed(bounds))
    ]
    labels.append((top + len(config.MAP_BANDS) * (height + gap) - gap, "0%"))
    for centre, text in labels:
        _text(
            figure,
            margin,
            left + width + 10,
            centre + config.FONT_SIZE_AXIS / 3,
            text,
            _axis_font(),
            name="key",
        )


_BUILDERS = {
    "line": _line,
    "bar": _bar,
    "scatter": _scatter,
    "heatmap": _heatmap,
    "map": _map,
}
