"""The single-toggle constraint, enforced.

CLAUDE.md's central methodological claim is that any observed difference between conditions is
attributable to interactivity and not to appearance. These tests are that claim made checkable:
the figure must be byte-identical across conditions, for every chart type and every task, and the
only divergence must be the Plotly config and the controls rendered beside the chart.
"""

from __future__ import annotations

import json

import plotly.graph_objects as go
import pytest

from src import config, figures, layout, runtime_data, tasks
from src.figures import FigureError

pytestmark = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)

ENTITIES = ["Nigeria", "India", "Brazil", "World"]
VACCINE = "DTP3"


@pytest.fixture(scope="module")
def rows():
    return runtime_data.load_rows()


def _walk(node):
    """Every component in a rendered tree, the root included."""
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


# --- Condition parity ---------------------------------------------------------------------------


def test_figure_does_not_depend_on_condition(rows):
    """There is no `interactive` argument to build_figure, so parity holds by construction."""
    first = figures.build_figure(ENTITIES, VACCINE, rows)
    second = figures.build_figure(ENTITIES, VACCINE, rows)
    assert first.to_json() == second.to_json()


def test_only_the_config_differs_between_conditions():
    static = figures.graph_config(interactive=False)
    interactive = figures.graph_config(interactive=True)
    assert static != interactive
    assert static["staticPlot"] is True
    assert interactive["staticPlot"] is False


def test_static_config_disables_every_affordance():
    """No hover, no zoom, no pan, no modebar — otherwise 'static' is not static."""
    static = figures.graph_config(interactive=False)
    assert static["staticPlot"] is True
    assert static["displayModeBar"] is False


def test_interactive_config_does_not_enable_scroll_zoom():
    """Scroll zoom fires accidentally while reading and would pollute the interaction log."""
    assert figures.graph_config(interactive=True)["scrollZoom"] is False


ALL_TASKS = [tasks.PRACTICE, *tasks.FORM_A, *tasks.FORM_B]


def _task_id(task) -> str:
    return f"{task.form}-{task.task_id}"


def _figure_on(screen):
    graphs = [
        node
        for node in _walk(screen)
        if getattr(node, "id", None) == "chart" and hasattr(node, "figure")
    ]
    assert len(graphs) == 1
    return graphs[0].figure


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_the_task_screen_opens_on_the_same_chart_in_both_conditions(rows, task):
    """The interactive condition gains CONTROLS, not a different chart.

    Both conditions must open on an identical chart: every series shown, bars in their listed
    order, no country faded. If the controls ever changed the resting state, the manipulation would
    confound interactivity with what is on screen. Checked for every task, so every chart type.
    """
    static = layout.task_screen(task, interactive=False, index=1, total=6)
    interactive = layout.task_screen(task, interactive=True, index=1, total=6)
    assert _figure_on(static).to_json() == _figure_on(interactive).to_json()


# Each chart type's controls (visual-spec.md section 7). The scatter and heatmap have none: their
# affordance is hover.
CONTROL_IDS = {
    "line": {"entity-filter", "entity-sort", "reset-view"},
    "bar": {"bar-sort"},
    "scatter": set(),
    "heatmap": set(),
    "map": {"coverage-band", "band-reset"},
}
EVERY_CONTROL = set().union(*CONTROL_IDS.values())


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_only_the_interactive_condition_renders_controls(rows, task):
    static_ids = {getattr(n, "id", None) for n in _walk(layout.task_screen(task, False, 1, 6))}
    live_ids = {getattr(n, "id", None) for n in _walk(layout.task_screen(task, True, 1, 6))}
    # `control-state` is not here: it is a store in the app's base layout, present in both.
    assert not (EVERY_CONTROL & static_ids), "the static condition must have no controls"
    assert EVERY_CONTROL & live_ids == CONTROL_IDS[task.chart], (
        "each chart type gets its own controls and no other type's"
    )


# --- Year-over-year change, carried in the hover layer --------------------------------------------


def test_change_labels_report_the_delta_against_the_previous_year(rows):
    series = runtime_data.series("Brazil", VACCINE, rows)
    labels = figures.change_labels(series)
    by_year = {row.year: label for row, label in zip(series, labels, strict=True)}
    # Brazil DTP3: 2014 -> 2015 rises by 3 points, 2015 -> 2016 falls by 7.
    assert by_year[2015] == "+3 pts vs 2014"
    assert by_year[2016] == "-7 pts vs 2015"


def test_the_first_year_shown_has_no_delta_to_report(rows):
    series = runtime_data.series("Brazil", VACCINE, rows)
    assert figures.change_labels(series)[0] == "first year shown"


def test_a_flat_year_says_so_rather_than_showing_zero(rows):
    series = runtime_data.series("Brazil", VACCINE, rows)
    by_year = dict(zip([r.year for r in series], figures.change_labels(series), strict=True))
    assert by_year[2001] == "no change vs 2000"


def test_no_delta_is_invented_across_a_gap(rows):
    """The UK's first reported HepB3 year is 2019. Differencing it against 2000 would be fiction."""
    series = runtime_data.series("United Kingdom", "HepB3", rows)
    by_year = dict(zip([r.year for r in series], figures.change_labels(series), strict=True))
    assert by_year[2019] == "no 2018 value reported"


def test_unreported_points_carry_no_label(rows):
    series = runtime_data.series("United Kingdom", "HepB3", rows)
    labels = figures.change_labels(series)
    for row, label in zip(series, labels, strict=True):
        if row.coverage_pct is None:
            assert label == ""


def test_the_delta_agrees_with_the_rounded_value_on_screen(rows):
    """The tooltip shows 0dp, so a delta off raw values could contradict what is on screen."""
    for entity in ("Africa", "Asia", "World"):
        series = runtime_data.series(entity, VACCINE, rows)
        labels = figures.change_labels(series)
        for index, (row, label) in enumerate(zip(series, labels, strict=True)):
            if not label.endswith(f"vs {series[index - 1].year}") or "pts" not in label:
                continue
            expected = round(row.coverage_pct) - round(series[index - 1].coverage_pct)
            assert label.startswith(f"{expected:+d} pts")


def test_the_change_label_is_in_both_conditions_figures(rows):
    """Interactive-only because staticPlot suppresses hover, NOT because the figure differs."""
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    for trace in figure.data:
        assert trace.customdata is not None
        assert "%{customdata}" in trace.hovertemplate


# --- Filtering hides series without recolouring them ----------------------------------------------


def test_hiding_a_series_leaves_the_others_their_colour(rows):
    """Rebuilding from a shorter list would recolour the survivors mid-task."""
    figure = figures.build_figure(["Nigeria", "India", "Brazil", "World"], VACCINE, rows)
    before = {trace.name: trace.line.color for trace in figure.data}

    figures.set_visible(figure, ["India", "Brazil", "World"])
    after = {trace.name: trace.line.color for trace in figure.data}
    assert after == before, "colour is assigned by position and must not shift when filtering"


def test_hidden_series_are_invisible_and_visible_ones_are_not(rows):
    figure = figures.build_figure(["Nigeria", "India", "World"], VACCINE, rows)
    figures.set_visible(figure, ["India", "World"])
    by_name = {trace.name: trace.visible for trace in figure.data}
    assert by_name == {"Nigeria": False, "India": True, "World": True}


def test_hiding_a_series_also_removes_its_end_label(rows):
    """A label with no line under it would float over the chart naming nothing."""
    figure = figures.build_figure(["Nigeria", "India", "World"], VACCINE, rows)
    figures.set_visible(figure, ["India", "World"])
    labelled = {annotation.text for annotation in figure.layout.annotations}
    assert labelled == {"India", "World"}


def test_showing_an_entity_that_is_not_on_the_figure_is_refused(rows):
    figure = figures.build_figure(["Nigeria", "World"], VACCINE, rows)
    with pytest.raises(FigureError, match="not on the figure"):
        figures.set_visible(figure, ["Nigeria", "Brazil"])


# --- Locked visual decisions --------------------------------------------------------------------


def test_y_axis_is_pinned_to_full_scale(rows):
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    assert list(figure.layout.yaxis.range) == list(config.Y_RANGE)
    assert figure.layout.yaxis.fixedrange is True


def test_gaps_are_never_bridged(rows):
    """connectgaps=False on every trace; a bridged line would invent unreported data."""
    figure = figures.build_figure(["United Kingdom", "World"], "HepB3", rows)
    for trace in figure.data:
        assert trace.connectgaps is False


def test_uk_hepb3_gap_survives_into_the_figure(rows):
    """The 19 unreported UK years must reach Plotly as None, not 0 and not dropped."""
    figure = figures.build_figure(["United Kingdom"], "HepB3", rows)
    y_values = list(figure.data[0].y)
    assert len(y_values) == config.YEAR_MAX - config.YEAR_MIN + 1
    assert sum(1 for v in y_values if v is None) == 19
    assert 0.0 not in [v for v in y_values if v is not None]


def test_series_use_the_verified_palette(rows):
    figure = figures.build_figure(["Nigeria", "India", "Brazil"], VACCINE, rows)
    used = [trace.line.color for trace in figure.data]
    assert used == config.SERIES_COLORS[:3]


def test_world_is_the_dashed_black_reference(rows):
    figure = figures.build_figure(["Nigeria", "World"], VACCINE, rows)
    world = [t for t in figure.data if t.name == "World"][0]
    assert world.line.color == config.REFERENCE_COLOR
    assert world.line.dash == config.REFERENCE_DASH
    # World must not consume a palette slot meant for a country.
    nigeria = [t for t in figure.data if t.name == "Nigeria"][0]
    assert nigeria.line.color == config.SERIES_COLORS[0]


def test_every_series_is_labelled_directly(rows):
    """Colour must never be the only channel identifying a line."""
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    labelled = {a.text for a in figure.layout.annotations}
    assert labelled == set(ENTITIES)


def _label_heights(figure) -> list[float]:
    return sorted(figures.label_height(annotation) for annotation in figure.layout.annotations)


LINE_TASKS = [task for task in ALL_TASKS if task.chart == "line"]


@pytest.mark.parametrize("task", LINE_TASKS, ids=_task_id)
def test_end_labels_never_overlap_on_any_task_chart(rows, task):
    """visual-spec.md section 6. Before 2026-09-22, labels collided on 9 of the 13 charts, leaving
    colour as the only channel. A-T1 now has eight countries ending between 67 and 97."""
    figure = figures.build_figure(list(task.entities), task.vaccine, rows)
    heights = _label_heights(figure)
    gaps = [upper - lower for lower, upper in zip(heights, heights[1:], strict=False)]
    assert min(gaps, default=config.LABEL_MIN_GAP) >= config.LABEL_MIN_GAP - 1e-9
    for annotation in figure.layout.annotations:
        reported = [
            r
            for r in runtime_data.series(annotation.text, task.vaccine, rows)
            if r.coverage_pct is not None
        ]
        # Spread, not relocated: a label stays close enough to its line to read as its label.
        assert abs(figures.label_height(annotation) - reported[-1].coverage_pct) <= 6.0, (
            annotation.text
        )
        assert annotation.x == reported[-1].year
    # Labels may rise into the top margin by LABEL_HEADROOM, never above it or below the axis.
    assert config.Y_RANGE[0] <= heights[0]
    assert heights[-1] <= config.Y_RANGE[1] + config.LABEL_HEADROOM


def test_spreading_leaves_well_separated_labels_where_they_are():
    assert figures.spread_labels([10.0, 50.0, 90.0], 0, 100, 4.5) == [10.0, 50.0, 90.0]


def test_spreading_moves_colliding_labels_apart_symmetrically():
    assert figures.spread_labels([94.0, 94.0], 0, 100, 4.5) == [91.75, 96.25]


def test_spreading_keeps_labels_inside_the_axis():
    assert figures.spread_labels([98.0, 99.0, 100.0], 0, 100, 4.5) == [91.0, 95.5, 100.0]
    assert figures.spread_labels([0.0, 1.0], 0, 100, 4.5) == [0.0, 4.5]


def test_spreading_refuses_more_labels_than_fit():
    with pytest.raises(FigureError, match="cannot sit"):
        figures.spread_labels([50.0] * 30, 0, 100, 4.5)


def test_legend_is_hidden_because_lines_are_labelled(rows):
    assert figures.build_figure(ENTITIES, VACCINE, rows).layout.showlegend is False


def test_gridline_and_axis_colors_come_from_config(rows):
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    assert figure.layout.yaxis.gridcolor == config.GRIDLINE_COLOR
    assert figure.layout.xaxis.linecolor == config.AXIS_COLOR


def test_figure_is_json_serialisable(rows):
    """Dash sends the figure over the wire; an unserialisable value fails only at runtime."""
    json.loads(figures.build_figure(ENTITIES, VACCINE, rows).to_json())


# --- Guards -------------------------------------------------------------------------------------


def test_too_many_series_is_refused(rows):
    """Beyond the palette, series cannot be told apart; the spec caps it at its size."""
    too_many = config.COUNTRIES[: config.MAX_SERIES + 1]
    with pytest.raises(FigureError, match="distinguishable"):
        figures.build_figure(too_many, VACCINE, rows)


def test_world_does_not_count_against_the_series_cap(rows):
    at_cap = config.COUNTRIES[: config.MAX_SERIES] + ["World"]
    figures.build_figure(at_cap, VACCINE, rows)


def test_unknown_entity_is_refused(rows):
    with pytest.raises(FigureError, match="Unknown entities"):
        figures.build_figure(["Atlantis"], VACCINE, rows)


def test_unknown_vaccine_is_refused(rows):
    with pytest.raises(FigureError, match="Unknown vaccine"):
        figures.build_figure(["Nigeria"], "BCG", rows)


def test_duplicate_entities_refused(rows):
    with pytest.raises(FigureError, match="Duplicate"):
        figures.build_figure(["Nigeria", "Nigeria"], VACCINE, rows)


def test_empty_entity_list_refused(rows):
    with pytest.raises(FigureError, match="No entities"):
        figures.build_figure([], VACCINE, rows)


# --- The bar, scatter, heatmap and map (visual-spec.md sections 1 and 7) --------------------------

TASK_BY_CHART = {
    chart: next(task for task in tasks.FORM_A if task.chart == chart)
    for chart in ("bar", "scatter", "heatmap", "map")
}
NEW_CHARTS = tuple(TASK_BY_CHART)
SAMPLE_YEARS = {"bar": (2010,), "map": (2010,), "scatter": (2000, 2024), "heatmap": (2000, 2010)}


def _chart(chart_type, rows):
    return figures.task_figure(TASK_BY_CHART[chart_type], rows)


@pytest.mark.parametrize("chart_type", NEW_CHARTS)
def test_every_chart_type_carries_its_hover_text_in_both_conditions(rows, chart_type):
    """Hover is interactive-only because staticPlot suppresses it, not because figures differ."""
    for trace in _chart(chart_type, rows).data:
        assert trace.hovertemplate and trace.hovertemplate.endswith("<extra></extra>")


def test_bars_share_one_colour_and_open_in_the_listed_order(rows):
    task = TASK_BY_CHART["bar"]
    figure = _chart("bar", rows)
    (bars,) = figure.data
    assert bars.marker.color == config.BAR_COLOR
    assert list(figure.layout.xaxis.categoryarray) == list(task.entities)
    assert list(figure.layout.yaxis.range) == list(config.Y_RANGE)
    assert figure.layout.yaxis.fixedrange is True


def test_sorting_bars_moves_them_highest_first_and_back(rows):
    """The one control that moves marks (visual-spec.md section 7.2). Each bar keeps its data."""
    task = TASK_BY_CHART["bar"]
    figure = _chart("bar", rows)
    before = figure.data[0].to_plotly_json()
    figures.sort_bars(figure, by_coverage=True)
    values = dict(zip(figure.data[0].x, figure.data[0].y, strict=True))
    assert list(figure.layout.xaxis.categoryarray) == sorted(values, key=lambda n: -values[n])
    assert figure.data[0].to_plotly_json() == before, "only the axis order changes"
    figures.sort_bars(figure, by_coverage=False)
    assert list(figure.layout.xaxis.categoryarray) == list(task.entities)


def test_a_bar_with_no_value_sorts_last():
    figure = go.Figure(go.Bar(x=["A", "B", "C"], y=[50, None, 90]))
    figures.sort_bars(figure, by_coverage=True)
    assert list(figure.layout.xaxis.categoryarray) == ["C", "A", "B"]


def test_scatter_dots_differ_in_colour_and_in_shape(rows):
    """Colour is never the only channel (visual-spec.md section 6), and the scatter has no line
    ends to label, so every dot has its own shape as well as its own colour."""
    figure = _chart("scatter", rows)
    colours = [trace.marker.color for trace in figure.data]
    shapes = [trace.marker.symbol for trace in figure.data]
    assert colours == config.SERIES_COLORS[: len(colours)]
    assert shapes == config.MARKER_SYMBOLS[: len(shapes)]
    assert len(set(shapes)) == len(shapes)


def test_the_scatter_axes_share_one_scale_so_the_diagonal_means_no_change(rows):
    figure = _chart("scatter", rows)
    assert figure.layout.yaxis.scaleanchor == "x" and figure.layout.yaxis.scaleratio == 1
    assert list(figure.layout.xaxis.range) == list(config.Y_RANGE)
    assert list(figure.layout.yaxis.range) == list(config.Y_RANGE)
    (diagonal,) = figure.layout.shapes
    assert (diagonal.x0, diagonal.y0, diagonal.x1, diagonal.y1) == (0, 0, 100, 100)


def test_the_scatter_legend_names_every_dot_and_cannot_hide_one(rows):
    """A legend click would hide a dot: an uncontrolled filter that nothing logs."""
    figure = _chart("scatter", rows)
    assert figure.layout.showlegend is True
    assert figure.layout.legend.itemclick is False
    assert figure.layout.legend.itemdoubleclick is False
    assert [trace.name for trace in figure.data] == list(TASK_BY_CHART["scatter"].entities)


def test_hiding_a_series_leaves_annotations_that_name_no_series(rows):
    figure = _chart("scatter", rows)
    figures.set_visible(figure, [trace.name for trace in figure.data][:2])
    assert [annotation.text for annotation in figure.layout.annotations] == ["no change"]


def test_the_heatmap_carries_value_in_colour_alone(rows):
    """No number in a cell: that would hand static participants the exact value."""
    figure = _chart("heatmap", rows)
    (cells,) = figure.data
    assert (cells.zmin, cells.zmax) == config.Y_RANGE
    assert [(float(p), c.upper()) for p, c in cells.colorscale] == [
        (p, c.upper()) for p, c in config.SEQUENTIAL_SCALE
    ]
    assert cells.texttemplate is None and cells.text is None
    assert figure.layout.yaxis.autorange == "reversed", "the first country listed is the top row"


def test_the_map_colours_each_country_by_its_iso_code(rows):
    task = TASK_BY_CHART["map"]
    figure = _chart("map", rows)
    (countries,) = figure.data
    codes = [runtime_data.series(e, task.vaccine, rows)[0].iso_code for e in task.entities]
    assert list(countries.locations) == codes
    assert countries.locationmode == "ISO-3"
    assert (countries.zmin, countries.zmax) == config.Y_RANGE
    assert figure.layout.geo.scope == figures.MAP_SCOPE
    assert figure.layout.dragmode is False, "a fixed view: no drag-to-pan"


def test_the_coverage_band_fades_countries_outside_it_and_moves_nothing(rows):
    """Drawn as a selection: plotly.js 4 drops a per-country marker.opacity list without a word,
    which is how the filter first shipped -- fading nothing (visual-spec.md section 7.4)."""
    figure = _chart("map", rows)
    (countries,) = figure.data
    assert countries.unselected.marker.opacity == config.MAP_FADED_OPACITY
    assert countries.marker.opacity is None, "a per-country opacity list is never rendered"
    before = list(countries.locations), list(countries.z)
    figures.set_band(figure, 0, 49)
    shown = figures.in_band(figure)
    assert shown == [value <= 49 for value in countries.z]
    assert (list(countries.locations), list(countries.z)) == before
    figures.set_band(figure, 0, 100)
    assert countries.selectedpoints is None, "unfiltered is the figure build_figure made"
    assert all(figures.in_band(figure))


def test_a_band_that_is_not_a_range_within_0_to_100_is_refused(rows):
    with pytest.raises(FigureError, match="coverage band"):
        figures.set_band(_chart("map", rows), 60, 40)
    with pytest.raises(FigureError, match="coverage band"):
        figures.set_band(_chart("map", rows), -5, 40)


def test_an_aggregate_cannot_be_mapped(rows):
    with pytest.raises(FigureError, match="aggregate"):
        figures.build_figure(["Africa"], VACCINE, rows, chart_type="map", years=(2013,))


def test_the_map_geometry_ships_with_the_app_and_covers_every_mapped_country(rows):
    """Plotly would fetch the shapes from its CDN in each participant's browser mid-task. The copy
    in src/assets must hold a shape for every country a map item colours."""
    asset = (config.PROJECT_ROOT / "src" / "assets" / "geo_africa.js").read_text(encoding="utf-8")
    name = f"{figures.MAP_SCOPE}_{figures.MAP_RESOLUTION}m"
    prefix = f'window.PlotlyGeoAssets.topojson["{name}"] = '
    topology = json.loads(asset[asset.index(prefix) + len(prefix) :].rstrip().rstrip(";"))
    shapes = {geometry.get("id") for geometry in topology["objects"]["countries"]["geometries"]}
    for task in ALL_TASKS:
        if task.chart == "map":
            codes = {runtime_data.series(e, task.vaccine, rows)[0].iso_code for e in task.entities}
            assert codes <= shapes, f"{_task_id(task)}: no shape for {sorted(codes - shapes)}"


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_no_chart_offers_selection_and_fixed_views_offer_no_zoom(rows, task):
    """visual-spec.md section 7. Box and lasso select dim marks without any event recording it, and
    on the map they would override the coverage filter. The map's view is fixed, like the bar,
    scatter and heatmap axes, so their zoom and pan buttons go too."""
    removed = set(figures.task_figure(task, rows).layout.modebar.remove)
    assert {"select", "lasso"} <= removed
    if task.chart == "map":
        assert {"pan", "zoomInGeo", "zoomOutGeo", "resetGeo"} <= removed
    elif task.chart != "line":
        assert {"zoom", "pan"} <= removed
    else:
        assert not {"zoom", "pan"} & removed, "the line chart's zoom and pan are logged affordances"


def test_the_modebar_is_the_figures_business_not_the_conditions():
    """graph_config stays the single condition switch; which buttons exist is part of the figure."""
    assert "modeBarButtonsToRemove" not in figures.graph_config(interactive=True)


@pytest.mark.parametrize("chart_type", NEW_CHARTS)
def test_world_is_the_line_charts_reference_and_nothing_else(rows, chart_type):
    with pytest.raises(FigureError, match="reference"):
        figures.build_figure(
            ["Nigeria", "World"],
            VACCINE,
            rows,
            chart_type=chart_type,
            years=SAMPLE_YEARS[chart_type],
        )


@pytest.mark.parametrize(
    ("chart_type", "years"),
    [
        ("line", (2010,)),
        ("bar", ()),
        ("bar", (2000, 2010)),
        ("scatter", (2010,)),
        ("heatmap", (2010,)),
        ("heatmap", (2010, 2005)),
        ("map", (1999,)),
    ],
)
def test_a_chart_is_refused_the_wrong_years(rows, chart_type, years):
    with pytest.raises(FigureError):
        figures.build_figure(["Nigeria"], VACCINE, rows, chart_type=chart_type, years=years)


def test_an_unknown_chart_type_is_refused(rows):
    with pytest.raises(FigureError, match="chart type"):
        figures.build_figure(["Nigeria"], VACCINE, rows, chart_type="pie")


def test_the_scatter_is_capped_by_the_palette_like_the_line(rows):
    too_many = config.COUNTRIES[: config.MAX_SERIES + 1]
    with pytest.raises(FigureError, match="distinguishable"):
        figures.build_figure(too_many, VACCINE, rows, chart_type="scatter", years=(2000, 2024))


def test_bars_and_heatmaps_are_not_capped_by_the_palette(rows):
    """Bars are named on their axis and share one colour; rows are named and use the scale."""
    many = config.COUNTRIES[: config.MAX_SERIES + 4]
    figures.build_figure(many, VACCINE, rows, chart_type="bar", years=(2010,))
    figures.build_figure(many, VACCINE, rows, chart_type="heatmap", years=(2000, 2010))


@pytest.mark.parametrize("task", LINE_TASKS, ids=_task_id)
def test_every_end_label_is_placed_where_plotly_will_draw_it(rows, task):
    """Plotly skips an annotation whose data coordinate is off its axis. A-T1's China label sat at
    102 on the 0-100 axis and was never drawn; a paper coordinate above 1 is drawn in the margin."""
    figure = figures.build_figure(list(task.entities), task.vaccine, rows)
    for annotation in figure.layout.annotations:
        assert annotation.yref == "paper", annotation.text
        assert 0 <= annotation.y <= 1 + config.LABEL_HEADROOM / 100, annotation.text
