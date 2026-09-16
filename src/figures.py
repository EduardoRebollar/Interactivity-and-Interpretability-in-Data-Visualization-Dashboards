"""Chart construction. Implements `docs/visual-spec.md`. No pandas — this ships to production.

**The figure is identical in both conditions.** Interactivity is not a property of the chart; it is
a property of how the chart is rendered, and lives entirely in `graph_config(interactive)`. Keeping
the split here means the two conditions are visually identical *by construction* rather than by
discipline, and `tests/test_conditions.py` proves it.

Year-over-year directional change is carried in the **hover tooltip**, not as a mark on the chart —
see `docs/visual-spec.md` section 7. A drawn indicator would have to appear in one condition and not
the other, which is exactly the divergence `build_figure` is built to make impossible. Putting it in
the tooltip keeps the figure identical in both conditions while leaving the information reachable
only where hover works, which under `staticPlot: True` is the interactive condition alone.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from src import config, runtime_data
from src.runtime_data import Row


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


def build_figure(
    entities: list[str],
    vaccine: str,
    rows: tuple[Row, ...] | None = None,
) -> go.Figure:
    """A coverage chart for `entities` over the locked year range.

    Identical in both study conditions. Applies the locked spec: gaps stay broken, y is pinned to
    0-100, colors come from the verified palette, World is a dashed black reference, and every
    series is labelled at its right end so colour is never the only channel.
    """
    _validate(entities, vaccine)
    source = rows if rows is not None else runtime_data.load_rows()

    figure = go.Figure()
    color_index = 0
    for entity in entities:
        is_reference = entity == "World"
        if is_reference:
            color, dash, width = config.REFERENCE_COLOR, config.REFERENCE_DASH, config.LINE_WIDTH
        else:
            color = config.SERIES_COLORS[color_index % len(config.SERIES_COLORS)]
            dash, width = "solid", config.LINE_WIDTH
            color_index += 1
        _add_series(figure, entity, vaccine, source, color, dash, width)

    _apply_layout(figure, vaccine)
    _add_end_labels(figure, entities, vaccine, source)
    return figure


def set_visible(figure: go.Figure, entities: Sequence[str]) -> go.Figure:
    """Show only `entities`, leaving every remaining series the colour it already had.

    **Filtering hides series; it never rebuilds the chart with a shorter list.** `build_figure`
    assigns colour by position among the non-World entities, so rebuilding from four entities
    instead of five would recolour the survivors — a participant who filtered one country out would
    watch the others change colour mid-task, and the "visual design is held constant" constraint
    would be broken by the interactive condition's own controls.

    The end labels are filtered alongside the traces, since a label for a hidden series would
    otherwise be left floating over the chart.
    """
    visible = set(entities)
    unknown = visible - {trace.name for trace in figure.data}
    if unknown:
        raise FigureError(f"Cannot show entities that are not on the figure: {sorted(unknown)}")

    for trace in figure.data:
        trace.visible = trace.name in visible
    figure.layout.annotations = [
        annotation for annotation in figure.layout.annotations if annotation.text in visible
    ]
    return figure


def _validate(entities: list[str], vaccine: str) -> None:
    if not entities:
        raise FigureError("No entities requested")
    if vaccine not in config.VACCINES:
        raise FigureError(f"Unknown vaccine {vaccine!r}")

    unknown = [e for e in entities if e not in config.ENTITIES]
    if unknown:
        raise FigureError(f"Unknown entities: {unknown}")
    if len(set(entities)) != len(entities):
        raise FigureError("Duplicate entities requested")

    # The cap is not cosmetic: it is the number of colors that are simultaneously
    # contrast-compliant, color-blind separable, and separated in luminance.
    # See docs/visual-spec.md section 4.
    colored = [e for e in entities if e != "World"]
    if len(colored) > config.MAX_SERIES:
        raise FigureError(
            f"{len(colored)} series requested but only {config.MAX_SERIES} distinguishable "
            "colors exist; World is exempt as the dashed reference"
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


def change_labels(series: tuple[Row, ...]) -> list[str]:
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


def _apply_layout(figure: go.Figure, vaccine: str) -> None:
    axis_font = {"family": config.FONT_FAMILY, "size": config.FONT_SIZE_AXIS}
    figure.update_layout(
        title={
            "text": f"{vaccine} coverage, {config.YEAR_MIN}-{config.YEAR_MAX}",
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
        height=config.CHART_HEIGHT,
        plot_bgcolor=config.BACKGROUND,
        paper_bgcolor=config.BACKGROUND,
        # Series are labelled at the line ends, so the legend would be redundant clutter and would
        # make legend-reading part of the task.
        showlegend=False,
        # Right margin holds the end labels.
        margin={"l": 70, "r": 150, "t": 60, "b": 60},
        hovermode="closest",
    )
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
    figure.update_yaxes(
        title={"text": "Coverage (%)", "font": axis_font},
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


def _add_end_labels(
    figure: go.Figure,
    entities: list[str],
    vaccine: str,
    source: tuple[Row, ...],
) -> None:
    """Label each series at its last observed point, so colour is never the only channel."""
    for trace in figure.data:
        entity = trace.name
        series = [
            r for r in runtime_data.series(entity, vaccine, source) if r.coverage_pct is not None
        ]
        if not series:
            # A series with no observations at all in range has nothing to anchor a label to.
            continue
        last = series[-1]
        figure.add_annotation(
            x=last.year,
            y=last.coverage_pct,
            text=entity,
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
