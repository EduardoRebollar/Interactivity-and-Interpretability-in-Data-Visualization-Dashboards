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
`sort_rows`, `order_legend`, `set_threshold`). Each hides, reorders or fades what is already there;
none rebuilds the chart from a shorter list, because colour is assigned by position and a rebuild
would recolour what is left.
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


def graph_config(interactive: bool) -> dict:
    """Plotly config for `dcc.Graph`. **The single decision point between conditions.**

    `staticPlot=True` removes hover, zoom, pan, selection, and the modebar. Plotly is interactive by
    default, so without this the static condition would still be hoverable and the manipulation
    would be invalid.
    """
    if interactive:
        return {
            "staticPlot": False,
            "displayModeBar": True,
            "displaylogo": False,
            "scrollZoom": False,
        }
    return {"staticPlot": True, "displayModeBar": False}


# Modebar buttons each chart type drops, set in the FIGURE's layout (`modebar.remove`) so the figure
# carries them in both conditions; the static condition shows no modebar at all. visual-spec.md
# section 7.
#
# Box and lasso select are gone from every chart: they dim unselected marks, a change to what is on
# screen that no event records, and on the map they would override the coverage filter, which is
# drawn as a selection. The bar, scatter, heatmap and map views are fixed -- their axes, or the map,
# cannot move -- so their zoom and pan buttons would do nothing but invite a click.
_SELECTION_BUTTONS = ["select", "lasso"]
_VIEW_BUTTONS = ["zoom", "pan", "zoomin", "zoomout", "autoscale", "resetscale"]
_MODEBAR_REMOVE = {
    "line": _SELECTION_BUTTONS,
    "bar": _SELECTION_BUTTONS + _VIEW_BUTTONS,
    "scatter": _SELECTION_BUTTONS + _VIEW_BUTTONS,
    "heatmap": _SELECTION_BUTTONS + _VIEW_BUTTONS,
    "map": _SELECTION_BUTTONS + ["pan", "zoomInGeo", "zoomOutGeo", "resetGeo"],
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
ROW_SORTS = ("default", "min", "mean")
_FADED_ROW = "faded-row:"


def chart_type_of(figure: go.Figure) -> str:
    """Which of CHART_TYPES a built figure is, read from its traces."""
    kinds = {type(trace) for trace in figure.data}
    if kinds == {go.Choropleth}:
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

    **Filtering hides or fades; it never rebuilds the chart with a shorter list.** `build_figure`
    assigns colour by position among the non-World entities, so rebuilding from four entities
    instead of five would recolour the survivors, and the "visual design is held constant"
    constraint would be broken by the interactive condition's own controls.

    How a mark is hidden depends on the chart (visual-spec.md section 7.3). A line or a scatter dot
    goes `legendonly`: it disappears, and its legend entry stays, greyed, to bring it back. A line's
    end label goes with it; annotations that name no series are left alone. A bar, a heatmap row or
    a map country fades to FADED_OPACITY and keeps its place, its colour and its label: a hidden row
    must not look like an empty cell, which means "not reported".
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
        figure.layout.annotations = [
            annotation
            for annotation in figure.layout.annotations
            if annotation.text not in names or annotation.text in visible
        ]
    elif chart == "bar":
        bars = _only(figure, go.Bar)
        bars.marker.opacity = (
            None
            if everything
            else [1.0 if str(name) in visible else config.FADED_OPACITY for name in bars.x]
        )
    elif chart == "heatmap":
        _fade_rows(figure, [name for name in names if name not in visible])
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
    return [
        shape.name[len(_FADED_ROW) :]
        for shape in figure.layout.shapes
        if (shape.name or "").startswith(_FADED_ROW)
    ]


def _fade_rows(figure: go.Figure, rows: Sequence[str]) -> None:
    """Fade whole heatmap rows by covering them with white at 1 - FADED_OPACITY.

    A heatmap has one opacity for the whole trace, so a row cannot be faded on its own. On the white
    plot, white over a cell at 0.85 is exactly the cell at 0.15. The cover is a shape, so it takes
    no hover, and it sits at the row's place as drawn: a category axis numbers its categories in
    the order shown, the top row 0 here.
    """
    figure.layout.shapes = [
        shape for shape in figure.layout.shapes if not (shape.name or "").startswith(_FADED_ROW)
    ]
    order = _row_order(figure)
    columns = len(_only(figure, go.Heatmap).x)
    for name in rows:
        position = order.index(name)
        figure.add_shape(
            type="rect",
            name=f"{_FADED_ROW}{name}",
            xref="x",
            yref="y",
            x0=-0.5,
            x1=columns - 0.5,
            y0=position - 0.5,
            y1=position + 0.5,
            fillcolor=config.BACKGROUND,
            opacity=round(1 - config.FADED_OPACITY, 6),
            line={"width": 0},
            layer="above",
        )


def sort_bars(figure: go.Figure, key: str) -> go.Figure:
    """Order the bars A to Z, highest first or lowest first (visual-spec.md section 7.2).

    **Sorting moves the bars.** On a line chart it reorders the chips and the legend only: the x
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
    return figure


def sort_rows(figure: go.Figure, key: str) -> go.Figure:
    """Order the heatmap's rows: as listed, by each row's lowest cell, or by its average, lowest
    first (visual-spec.md section 7.2). Each row keeps its cells and its label, so no cell changes
    colour; ties keep the listed order, and a row with nothing reported sorts last."""
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
        return min(values) if key == "min" else sum(values) / len(values)

    if key == "default":
        order = listed
    else:
        order = sorted(
            listed, key=lambda n: (statistic(n) is None, statistic(n) or 0, listed.index(n))
        )
    faded = _faded_rows(figure)
    figure.update_yaxes(categoryorder="array", categoryarray=order)
    _fade_rows(figure, faded)
    return figure


def order_legend(figure: go.Figure, order: Sequence[str] | None) -> go.Figure:
    """List a line chart's legend in `order`, or in the order the lines were listed when None.

    The View control's `by coverage` (visual-spec.md section 7.2). It reorders the legend and the
    chips, never the lines: `legendrank` changes only where an entry is listed.
    """
    if chart_type_of(figure) != "line":
        raise FigureError("Only a line chart's legend follows the View control")
    ranks = {name: index + 1 for index, name in enumerate(order or [])}
    for trace in figure.data:
        trace.legendrank = ranks.get(trace.name)
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
    if chart_type in ("line", "scatter"):
        colored = [e for e in entities if e != REFERENCE]
        if len(colored) > config.MAX_SERIES:
            raise FigureError(
                f"{len(colored)} series requested but only {config.MAX_SERIES} distinguishable "
                "colors exist; World is exempt as the dashed reference"
            )


# --- Shared styling ------------------------------------------------------------------------------


def _axis_font() -> dict:
    return {"family": config.FONT_FAMILY, "size": config.FONT_SIZE_AXIS}


def _apply_base(figure: go.Figure, title: str, margin: dict) -> None:
    """What every chart type shares: title, fonts, size, background, no legend, hover mode."""
    figure.update_layout(
        title={
            "text": title,
            "font": {
                "family": config.FONT_FAMILY,
                "size": config.FONT_SIZE_TITLE,
                "color": config.TEXT_PRIMARY,
            },
        },
        font={
            "family": config.FONT_FAMILY,
            "size": config.FONT_SIZE_BASE,
            "color": config.TEXT_PRIMARY,
        },
        # Fixed (visual-spec.md section 5): the same size on every screen and in both conditions.
        width=config.CHART_WIDTH,
        height=config.CHART_HEIGHT,
        autosize=False,
        plot_bgcolor=config.BACKGROUND,
        paper_bgcolor=config.BACKGROUND,
        # Only the line chart and the scatter have a legend (visual-spec.md section 6).
        showlegend=False,
        margin=margin,
        hovermode="closest",
    )


def _coverage_axis(update, title: str = "Coverage (%)") -> None:
    """A 0-100 coverage axis: pinned, gridded every 10. `update` is update_xaxes or update_yaxes."""
    axis_font = _axis_font()
    update(
        title={"text": title, "font": axis_font},
        # Pinned. An axis that rescales would change apparent steepness between tasks.
        range=list(config.Y_RANGE),
        dtick=10,
        tickfont=axis_font,
        color=config.AXIS_COLOR,
        gridcolor=config.GRIDLINE_COLOR,
        linecolor=config.AXIS_COLOR,
        showgrid=True,
        zeroline=False,
        fixedrange=True,
    )


def _category_axis(update, title: str | None = None, **extra) -> None:
    """An axis of names or years: no gridlines, no zoom."""
    axis_font = _axis_font()
    update(
        title={"text": title, "font": axis_font} if title else None,
        type="category",
        tickfont=axis_font,
        color=config.AXIS_COLOR,
        linecolor=config.AXIS_COLOR,
        showgrid=False,
        zeroline=False,
        fixedrange=True,
        **extra,
    )


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


def _line(
    entities: list[str], vaccine: str, _years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """Coverage over the locked year range. Applies the locked spec: gaps stay broken, y is pinned
    to 0-100, colors come from the verified palette, World is a dashed black reference, and every
    series is labelled at its right end so colour is never the only channel."""
    figure = go.Figure()
    color_index = 0
    for entity in entities:
        is_reference = entity == REFERENCE
        if is_reference:
            color, dash, width = config.REFERENCE_COLOR, config.REFERENCE_DASH, config.LINE_WIDTH
        else:
            color = config.SERIES_COLORS[color_index % len(config.SERIES_COLORS)]
            dash, width = "solid", config.LINE_WIDTH
            color_index += 1
        _add_series(figure, entity, vaccine, source, color, dash, width)

    _apply_base(figure, f"{vaccine} coverage, {config.YEAR_MIN}-{config.YEAR_MAX}", _LINE_MARGIN)
    axis_font = _axis_font()
    figure.update_xaxes(
        title={"text": "Year", "font": axis_font},
        range=[config.YEAR_MIN - 0.5, config.YEAR_MAX + 0.5],
        dtick=5,
        tickfont=axis_font,
        color=config.AXIS_COLOR,
        gridcolor=config.GRIDLINE_COLOR,
        linecolor=config.AXIS_COLOR,
        showgrid=True,
        zeroline=False,
    )
    _coverage_axis(figure.update_yaxes)
    _add_end_labels(figure, vaccine, source)
    _add_line_legend(figure)
    return figure


# The right margin holds the end labels and, beyond them, the legend: the plot is 640 px wide.
_LINE_MARGIN = {"l": 70, "r": 340, "t": 60, "b": 60}
# How far right of the plot the legend starts, past the widest end label.
_LABEL_SPACE = 170


def _add_line_legend(figure: go.Figure) -> None:
    """A vertical legend right of the end labels (visual-spec.md section 6, 2026-09-25).

    A control in the interactive condition: a click hides or shows a line, a double click shows
    that line alone. `staticPlot` leaves it drawn and inert in the static condition. World has no
    entry, as it has no chip: it cannot be hidden, and its dash and end label name it.
    """
    plot_width = config.CHART_WIDTH - _LINE_MARGIN["l"] - _LINE_MARGIN["r"]
    for trace in figure.data:
        if trace.name == REFERENCE:
            trace.showlegend = False
    figure.update_layout(
        showlegend=True,
        legend={
            "font": _axis_font(),
            "x": round(1 + _LABEL_SPACE / plot_width, 6),
            "xanchor": "left",
            "y": 1,
            "yanchor": "top",
            "bordercolor": config.GRIDLINE_COLOR,
            "borderwidth": 1,
            "itemclick": "toggle",
            "itemdoubleclick": "toggleothers",
        },
    )


def _add_series(
    figure: go.Figure,
    entity: str,
    vaccine: str,
    source: tuple[Row, ...],
    color: str,
    dash: str,
    width: float,
) -> None:
    series = runtime_data.series(entity, vaccine, source)
    figure.add_trace(
        go.Scatter(
            x=[row.year for row in series],
            # None, not 0 and not omitted: Plotly breaks the line here, which is the point.
            y=[row.coverage_pct for row in series],
            name=entity,
            mode="lines+markers",
            connectgaps=False,
            line={"color": color, "width": width, "dash": dash},
            marker={"color": color, "size": config.MARKER_SIZE},
            customdata=change_labels(series),
            hovertemplate=(
                f"<b>{entity}</b><br>%{{x}}: %{{y:.0f}}%<br>%{{customdata}}<extra></extra>"
            ),
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


def _add_end_labels(figure: go.Figure, vaccine: str, source: tuple[Row, ...]) -> None:
    """Label each series at its last observed point, so colour is never the only channel.

    Labels that would overlap are spread apart vertically (`docs/visual-spec.md` section 6): many
    countries end between 85 and 94, and two labels at the same height leave colour as the only
    way to tell the lines apart -- exactly where the static condition cannot hover to check.

    Labels may rise into the top margin by up to LABEL_HEADROOM (visual-spec.md section 6). With
    eight countries ending between 67 and 97 (A-T1), holding every label under 100 pushed World's
    label 7.5 points below its line.

    Placed in PAPER coordinates vertically (`label_height` converts). Plotly does not draw an
    annotation whose data coordinate lies outside its axis range, so a label placed at y=102 on
    the 0-100 axis simply vanished -- China's, on A-T1, found in headless Chrome. A paper
    coordinate above 1 is drawn in the margin like any other.
    """
    anchors = []
    for trace in figure.data:
        series = [
            r
            for r in runtime_data.series(trace.name, vaccine, source)
            if r.coverage_pct is not None
        ]
        if not series:
            # A series with no observations at all in range has nothing to anchor a label to.
            continue
        anchors.append((series[-1].coverage_pct, series[-1].year, trace))

    anchors.sort(key=lambda anchor: anchor[0])
    heights = spread_labels(
        [value for value, _year, _trace in anchors],
        lower=config.Y_RANGE[0],
        upper=config.Y_RANGE[1] + config.LABEL_HEADROOM,
        gap=config.LABEL_MIN_GAP,
    )
    low, high = config.Y_RANGE
    for (_value, year, trace), height in zip(anchors, heights, strict=True):
        figure.add_annotation(
            x=year,
            y=round((height - low) / (high - low), 5),
            yref="paper",
            text=trace.name,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            xshift=8,
            font={
                "family": config.FONT_FAMILY,
                "size": config.FONT_SIZE_AXIS,
                "color": trace.line.color,
            },
        )


def label_height(annotation) -> float:
    """An end label's height in coverage points, whichever reference it was placed in."""
    if annotation.yref == "paper":
        low, high = config.Y_RANGE
        return low + annotation.y * (high - low)
    return annotation.y


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
    """One year's coverage, one bar per country, in the order listed.

    One colour for every bar: each is named on the x axis, so colour carries nothing. The y axis is
    the line chart's, pinned to 0-100 and gridded every 10.
    """
    (year,) = years
    figure = go.Figure(
        go.Bar(
            x=entities,
            y=[_value(entity, vaccine, year, source) for entity in entities],
            name=f"{vaccine} {year}",
            marker={"color": config.BAR_COLOR},
            hovertemplate=f"<b>%{{x}}</b><br>{year}: %{{y:.0f}}%<extra></extra>",
        )
    )
    _apply_base(figure, f"{vaccine} coverage, {year}", {"l": 70, "r": 40, "t": 60, "b": 60})
    _category_axis(figure.update_xaxes, categoryorder="array", categoryarray=entities)
    _coverage_axis(figure.update_yaxes)
    return figure


# --- Scatter -------------------------------------------------------------------------------------


def _scatter(
    entities: list[str], vaccine: str, years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """Each country as one dot: coverage in the first year across, in the second year up.

    The axes share one scale, so the dashed diagonal is a true 45-degree line of no change and the
    distance above it is the improvement. Dots are told apart by colour AND shape, named in a
    legend: the scatter has no line ends to label, and reading the legend is the static cost this
    chart's item measures (docs/study-design.md section 4).
    """
    first, last = years
    figure = go.Figure()
    for index, entity in enumerate(entities):
        figure.add_trace(
            go.Scatter(
                x=[_value(entity, vaccine, first, source)],
                y=[_value(entity, vaccine, last, source)],
                name=entity,
                mode="markers",
                marker={
                    "color": config.SERIES_COLORS[index],
                    "symbol": config.MARKER_SYMBOLS[index],
                    "size": config.SCATTER_MARKER_SIZE,
                },
                hovertemplate=(
                    f"<b>{entity}</b><br>{first}: %{{x:.0f}}%<br>{last}: %{{y:.0f}}%<extra></extra>"
                ),
            )
        )
    # A shape, not a trace: no legend entry, no hover, drawn beneath the dots.
    figure.add_shape(
        type="line",
        x0=config.Y_RANGE[0],
        y0=config.Y_RANGE[0],
        x1=config.Y_RANGE[1],
        y1=config.Y_RANGE[1],
        line={"color": config.AXIS_COLOR, "width": 1.5, "dash": "dash"},
        layer="below",
    )
    figure.add_annotation(
        x=14,
        y=14,
        text="no change",
        showarrow=False,
        textangle=-45,
        yshift=10,
        font={
            "family": config.FONT_FAMILY,
            "size": config.FONT_SIZE_AXIS,
            "color": config.TEXT_MUTED,
        },
    )
    _apply_base(
        figure, f"{vaccine} coverage, {first} and {last}", {"l": 70, "r": 40, "t": 60, "b": 60}
    )
    axis_font = _axis_font()
    figure.update_layout(
        showlegend=True,
        legend={
            "font": axis_font,
            "x": 1.02,
            "xanchor": "left",
            "y": 1,
            "yanchor": "top",
            "bordercolor": config.GRIDLINE_COLOR,
            "borderwidth": 1,
            # A legend click hides a series: an uncontrolled filter that nothing would log.
            "itemclick": False,
            "itemdoubleclick": False,
        },
    )
    _coverage_axis(figure.update_xaxes, f"Coverage in {first} (%)")
    _coverage_axis(figure.update_yaxes, f"Coverage in {last} (%)")
    figure.update_xaxes(constrain="domain")
    figure.update_yaxes(scaleanchor="x", scaleratio=1, constrain="domain")
    return figure


# --- Heatmap -------------------------------------------------------------------------------------


def _heatmap(
    entities: list[str], vaccine: str, years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """Countries down, years across, coverage as colour: dark is low (visual-spec.md section 4).

    No value is written in a cell. The static condition reads colour against the key; the exact
    value is in the hover text, out of the static participant's reach.
    """
    figure = go.Figure(
        go.Heatmap(
            z=[[_value(entity, vaccine, year, source) for year in years] for entity in entities],
            x=[str(year) for year in years],
            y=entities,
            zmin=config.Y_RANGE[0],
            zmax=config.Y_RANGE[1],
            colorscale=_sequential(),
            # White gaps between cells, so two adjacent cells of one colour stay two cells.
            xgap=2,
            ygap=2,
            colorbar=_color_key(),
            hoverongaps=False,
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.0f}%<extra></extra>",
        )
    )
    _apply_base(figure, f"{vaccine} coverage by year", {"l": 190, "r": 40, "t": 60, "b": 60})
    _category_axis(figure.update_xaxes, "Year")
    # The first country listed is the top row, as it would be read. The order is written out, so
    # the row sort's Default (`sort_rows`) is exactly this figure.
    _category_axis(
        figure.update_yaxes, autorange="reversed", categoryorder="array", categoryarray=entities
    )
    return figure


# --- Map -----------------------------------------------------------------------------------------


def _map(
    entities: list[str], vaccine: str, years: tuple[int, ...], source: tuple[Row, ...]
) -> go.Figure:
    """One year's coverage as colour on a map of sub-Saharan Africa, one country per entity.

    Only the countries the item names are coloured; the rest are plain land. The view is fixed.
    """
    (year,) = years
    codes, values = [], []
    for entity in entities:
        row = next(r for r in runtime_data.series(entity, vaccine, source) if r.year == year)
        if row.iso_code.startswith("OWID"):
            raise FigureError(f"{entity} is an aggregate, not a country; it has no shape to colour")
        codes.append(row.iso_code)
        values.append(row.coverage_pct)
    figure = go.Figure(
        go.Choropleth(
            locations=codes,
            z=values,
            locationmode="ISO-3",
            text=entities,
            zmin=config.Y_RANGE[0],
            zmax=config.Y_RANGE[1],
            colorscale=_sequential(),
            marker={"line": {"color": config.MAP_BORDER_COLOR, "width": 1}},
            # How the highlight and the chips draw (`set_threshold`, `set_visible`): countries at
            # full strength are selected, the rest fade. Nothing is selected until a control acts.
            selected={"marker": {"opacity": 1.0}},
            unselected={"marker": {"opacity": config.FADED_OPACITY}},
            colorbar=_color_key(),
            hovertemplate=f"<b>%{{text}}</b><br>{year}: %{{z:.0f}}%<extra></extra>",
        )
    )
    _apply_base(figure, f"{vaccine} coverage, {year}", {"l": 10, "r": 10, "t": 60, "b": 10})
    figure.update_geos(
        scope=MAP_SCOPE,
        resolution=MAP_RESOLUTION,
        showframe=False,
        showland=True,
        landcolor=config.MAP_LAND_COLOR,
        showcountries=True,
        countrycolor=config.MAP_BORDER_COLOR,
        showcoastlines=True,
        coastlinecolor=config.MAP_COAST_COLOR,
        showlakes=False,
        bgcolor=config.BACKGROUND,
        lataxis_range=list(config.MAP_LAT_RANGE),
        lonaxis_range=list(config.MAP_LON_RANGE),
    )
    # A fixed view: no drag-to-pan. The modebar's map zoom buttons are removed in graph_config.
    figure.update_layout(dragmode=False)
    return figure


_BUILDERS = {
    "line": _line,
    "bar": _bar,
    "scatter": _scatter,
    "heatmap": _heatmap,
    "map": _map,
}
