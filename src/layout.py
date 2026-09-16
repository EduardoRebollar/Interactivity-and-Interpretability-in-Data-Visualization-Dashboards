"""Shared layout components. No pandas — this ships to production.

Every component is used by BOTH conditions. Nothing here branches on `interactive`: the only
divergence permitted is the Plotly config from `figures.graph_config`, which is passed in.
"""

from __future__ import annotations

from dash import dcc, html

from src import config, figures

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


def primary_button(label: str, element_id: str) -> html.Button:
    """Keyboard-navigable by default; do not replace with a div."""
    return html.Button(
        label,
        id=element_id,
        n_clicks=0,
        style={
            "fontFamily": config.FONT_FAMILY,
            "fontSize": f"{config.FONT_SIZE_BASE}px",
            "padding": "10px 20px",
            "color": config.BACKGROUND,
            "backgroundColor": config.SERIES_COLORS[0],
            "border": "none",
            "borderRadius": "4px",
            "cursor": "pointer",
        },
    )
