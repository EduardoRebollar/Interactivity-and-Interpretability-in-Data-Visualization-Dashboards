"""The single-toggle constraint, enforced.

CLAUDE.md's central methodological claim is that any observed difference between conditions is
attributable to interactivity and not to appearance. These tests are that claim made checkable:
the figure must be byte-identical across conditions, for every chart type and every task, and the
only divergence must be the Plotly config and the controls rendered beside the chart.
"""

from __future__ import annotations

import json
from collections import Counter

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


@pytest.mark.parametrize("chart_type", ["line", "bar", "scatter", "heatmap", "map"])
def test_scroll_zoom_is_on_for_the_line_chart_only(chart_type):
    """A mouse wheel or touchpad zooms the line chart's x axis (2026-09-27; it was off until then,
    for fear of accidental zooms while reading). Every other view is fixed, and Plotly would still
    take the wheel over one, so the page could not be scrolled with the pointer on the chart."""
    config = figures.graph_config(interactive=True, chart_type=chart_type)
    assert config["scrollZoom"] == ("cartesian" if chart_type == "line" else False)
    assert "scrollZoom" not in figures.graph_config(interactive=False, chart_type=chart_type)


@pytest.mark.parametrize("task", [tasks.PRACTICE, *tasks.FORM_A, *tasks.FORM_B], ids=str)
def test_each_chart_is_rendered_with_its_own_config(task):
    (graph,) = [
        node
        for node in _walk(layout.chart(task, interactive=True))
        if getattr(node, "id", None) == "chart"
    ]
    assert graph.config == figures.graph_config(True, task.chart)


@pytest.mark.parametrize("task", [*tasks.FORM_A, *tasks.FORM_B], ids=str)
def test_only_an_interactive_chart_with_a_key_carries_key_buttons(task):
    """The buttons are an overlay beside the graph, not part of the figure (visual-spec.md 7.4)."""
    for interactive in (False, True):
        buttons = [
            node
            for node in _walk(layout.chart(task, interactive=interactive))
            if isinstance(getattr(node, "id", None), dict) and node.id["control"] == "key-band"
        ]
        expected = (
            len(figures.key_blocks(task.chart))
            if interactive and (task.chart in figures.KEY_CHARTS)
            else 0
        )
        assert len(buttons) == expected, (task.task_id, interactive)
        assert [b.id["index"] for b in buttons] == list(range(expected))


ALL_TASKS = [tasks.PRACTICE, *tasks.FORM_A, *tasks.FORM_B]
FORM_A_T6 = next(t for t in tasks.FORM_A if t.task_id == "T6")
FORM_B_T6 = next(t for t in tasks.FORM_B if t.task_id == "T6")


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


# Each chart type's controls (visual-spec.md section 7), by the `control` of their pattern ids:
# chips (in their group) and Reset view on every chart, a sort on the bar and heatmap, the Years
# slider and Show all on the line (its View went on 2026-10-12), and buttons over the key on the
# scatter, heatmap and map (the map's highlight box went the same day).
_EVERY_CHART = {"chip-group", "chips", "reset"}
CONTROL_IDS = {
    "line": _EVERY_CHART | {"years", "show-all"},
    "bar": _EVERY_CHART | {"sort"},
    "scatter": _EVERY_CHART | {"key-band"},
    "heatmap": _EVERY_CHART | {"sort", "key-band"},
    "map": _EVERY_CHART | {"key-band"},
}


def _controls(screen) -> set[str]:
    return {
        node.id["control"]
        for node in _walk(screen)
        if isinstance(getattr(node, "id", None), dict) and "control" in node.id
    }


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_only_the_interactive_condition_renders_controls(rows, task):
    static = _controls(layout.task_screen(task, False, 1, 6))
    live = _controls(layout.task_screen(task, True, 1, 6))
    # `control-state` is not here: it is a store in the app's base layout, present in both.
    assert not static, "the static condition must have no controls"
    expected = CONTROL_IDS[task.chart]
    if tasks.has_extra_controls(task):
        # T1's four more, the overload (visual-spec.md section 7.7).
        expected = expected | T1_EXTRA_IDS
    assert live == expected, "each chart type gets its own controls and no other's"


T1_EXTRA_IDS = {"coverage", "chip-order", "regions", "display"}


def test_only_t1_is_overloaded_and_in_both_forms():
    """The extra controls are T1's alone: not the practice, not T6, the other line chart."""
    overloaded = [(t.form, t.task_id) for t in ALL_TASKS if tasks.has_extra_controls(t)]
    assert overloaded == [("A", "T1"), ("B", "T1")]


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
    """Colour goes by country, so a hidden line changes no other line's colour."""
    figure = figures.build_figure(["Nigeria", "India", "Brazil", "World"], VACCINE, rows)
    before = {trace.name: trace.line.color for trace in figure.data}
    figures.set_visible(figure, ["India", "Brazil", "World"])
    assert {trace.name: trace.line.color for trace in figure.data} == before


def test_hidden_series_are_legend_only_and_visible_ones_are_not(rows):
    """Hidden, not removed: the trace stays, so `curveNumber` still indexes the task's entities."""
    figure = figures.build_figure(["Nigeria", "India", "World"], VACCINE, rows)
    figures.set_visible(figure, ["India", "World"])
    by_name = {trace.name: trace.visible for trace in figure.data}
    assert by_name == {"Nigeria": "legendonly", "India": True, "World": True}


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
    """The 34 unreported UK years (1985-2018; 19 when the scope began at 2000) must reach Plotly as
    None, not 0 and not dropped."""
    figure = figures.build_figure(["United Kingdom"], "HepB3", rows)
    y_values = list(figure.data[0].y)
    assert len(y_values) == config.YEAR_MAX - config.YEAR_MIN + 1
    assert sum(1 for v in y_values if v is None) == 34
    assert 0.0 not in [v for v in y_values if v is not None]


def test_series_take_their_countrys_colour(rows):
    """visual-spec.md section 4: Form A's T1 countries own a colour each, wherever they appear."""
    figure = figures.build_figure(["Nigeria", "India", "Brazil"], VACCINE, rows)
    used = {trace.name: trace.line.color for trace in figure.data}
    assert used == {name: config.COUNTRY_COLORS[name] for name in used}


@pytest.mark.parametrize(
    ("entities", "expected"),
    [
        # A-T6 and B-T6: eight lines, so every colour is used; each country without one of its own
        # takes the first one free.
        (
            list(FORM_A_T6.entities),
            {
                "Afghanistan": 0,
                "Central African Republic": 1,
                "Chad": 3,
                "Cote d'Ivoire": 4,
                "Democratic Republic of Congo": 6,
                "Ethiopia": 2,
                "Nigeria": 5,
                "Somalia": 7,
            },
        ),
        # B-T6 since 2026-10-12, Ghana and Guinea for Cameroon and Madagascar: the named pair keep
        # their colours (Mozambique 5, Pakistan 6).
        (
            list(FORM_B_T6.entities),
            {
                "Benin": 0,
                "Gabon": 1,
                "Ghana": 2,
                "Guinea": 3,
                "Kenya": 4,
                "Mozambique": 5,
                "Pakistan": 6,
                "Sudan": 7,
            },
        ),
        # A-T1 since 2026-10-12: Gabon, standing where Nigeria stood, takes the colour Nigeria
        # owns, the one A-T1's seven owners leave.
        (
            ["Brazil", "China", "Ethiopia", "Gabon", "India", "Indonesia", "Pakistan", "Ukraine"],
            {"Gabon": 5},
        ),
        # B-T1: Nepal and Uganda take the two colours its six owners leave.
        (
            ["Brazil", "China", "Ethiopia", "Indonesia", "Nepal", "Nigeria", "Pakistan", "Uganda"],
            {"Nepal": 3, "Uganda": 7},
        ),
        (["Myanmar", "World"], {"Myanmar": 0}),
    ],
)
def test_a_country_without_a_colour_takes_the_first_one_free(entities, expected):
    colors = figures.series_colors(entities)
    for name, index in expected.items():
        assert colors[name] == config.SERIES_COLORS[index]
    countries = [colors[e] for e in entities if e != figures.REFERENCE]
    assert len(set(countries)) == len(countries)


def test_every_task_line_chart_keeps_its_colours_apart():
    for task in ALL_TASKS:
        if task.chart == "line":
            colors = figures.series_colors(list(task.entities))
            assert len(set(colors.values())) == len(colors), task


def test_world_is_the_dashed_black_reference(rows):
    figure = figures.build_figure(["Nigeria", "World"], VACCINE, rows)
    world = [t for t in figure.data if t.name == "World"][0]
    assert world.line.color == config.REFERENCE_COLOR
    assert world.line.dash == config.REFERENCE_DASH
    nigeria = [t for t in figure.data if t.name == "Nigeria"][0]
    assert nigeria.line.color == config.COUNTRY_COLORS["Nigeria"]


def _tag_parts(figure, entity):
    name = f"{figures.TAG}{entity}"
    shapes = [s for s in figure.layout.shapes if s.name == name]
    annotations = [a for a in figure.layout.annotations if a.name == name]
    return shapes, annotations


def test_hiding_a_series_also_removes_its_name_tag(rows):
    """A tag with no line under it would name nothing. Leader, pill, dot and name all go; the other
    tags stay exactly where they were, and so does everything that names no line."""
    figure = figures.build_figure(["Nigeria", "India", "World"], VACCINE, rows)
    centres = figures.tag_centres(figure)
    others = [s for s in figure.layout.shapes if not (s.name or "").startswith(figures.TAG)]
    figures.set_visible(figure, ["India", "World"])
    assert _tag_parts(figure, "Nigeria") == ([], [])
    shapes, annotations = _tag_parts(figure, "India")
    assert len(shapes) == 3 and len(annotations) == 1
    assert figures.tag_centres(figure) == {k: v for k, v in centres.items() if k != "Nigeria"}
    kept = [s for s in figure.layout.shapes if not (s.name or "").startswith(figures.TAG)]
    assert kept == others
    names = {a.name for a in figure.layout.annotations}
    assert {"title", "source", "axis-title"} <= names


def test_every_series_is_named_by_a_tag(rows):
    """Colour must never be the only channel identifying a line."""
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    assert set(figures.tag_centres(figure)) == set(ENTITIES)
    for entity in ENTITIES:
        shapes, (annotation,) = _tag_parts(figure, entity)
        assert annotation.text == figures.tag_name(entity)
        assert len(shapes) == 3


def test_the_central_african_republic_is_shortened_on_its_tag():
    assert figures.tag_name("Central African Republic") == "Central African Rep."
    assert figures.tag_name("Democratic Republic of Congo") == "DR Congo"
    assert figures.tag_name("Ethiopia") == "Ethiopia"


LINE_TASKS = [task for task in ALL_TASKS if task.chart == "line"]


@pytest.mark.parametrize("task", LINE_TASKS, ids=_task_id)
def test_name_tags_never_overlap_on_any_task_chart(rows, task):
    """visual-spec.md section 6: centres 23 px apart at least, between 10 px above the plot's top
    and 4 px above its bottom, in the order of the lines' last reported values."""
    figure = figures.build_figure(list(task.entities), task.vaccine, rows)
    centres = figures.tag_centres(figure)
    heights = sorted(centres.values())
    gaps = [b - a for a, b in zip(heights, heights[1:], strict=False)]
    assert min(gaps, default=config.TAG_GAP) >= config.TAG_GAP - 1e-3
    margin = figure.layout.margin
    assert margin.t - 10 - 1e-3 <= heights[0]
    assert heights[-1] <= figure.layout.height - margin.b - 4 + 1e-3
    last = {}
    for entity in task.entities:
        reported = [
            r for r in runtime_data.series(entity, task.vaccine, rows) if r.coverage_pct is not None
        ]
        last[entity] = reported[-1].coverage_pct
    by_height = sorted(centres, key=lambda e: centres[e])
    values = [last[e] for e in by_height]
    assert values == sorted(values, reverse=True), "tags keep their lines' order"


@pytest.mark.parametrize("task", LINE_TASKS, ids=_task_id)
def test_every_tag_is_placed_where_plotly_will_draw_it(rows, task):
    """Plotly skips an annotation whose data coordinate is off its axis (A-T1's China label,
    2026-09-23), so everything a tag draws is in paper coordinates."""
    figure = figures.build_figure(list(task.entities), task.vaccine, rows)
    for item in [*figure.layout.annotations, *figure.layout.shapes]:
        if (item.name or "").startswith(figures.TAG):
            assert (item.xref, item.yref) == ("paper", "paper"), item.name


def test_a_leader_starts_at_its_line_end_and_ends_at_its_tag(rows):
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    margin = figure.layout.margin.to_plotly_json()
    centres = figures.tag_centres(figure)
    for entity in ENTITIES:
        reported = [
            r for r in runtime_data.series(entity, VACCINE, rows) if r.coverage_pct is not None
        ]
        leader = _tag_parts(figure, entity)[0][0]
        x = figures._paper(margin, x=figures._x_px(reported[-1].year) + 6)
        y = figures._paper(margin, y=figures._y_px(reported[-1].coverage_pct))
        assert leader.path.split()[0] == f"M{x},{y}"
        tag_x = figures._paper(margin, x=config.TAG_X)
        assert leader.path.split()[-1] == f"{tag_x},{figures._paper(margin, y=centres[entity])}"


def test_each_line_ends_in_a_ringed_dot(rows):
    figure = figures.build_figure(["United Kingdom"], "HepB3", rows)
    (trace,) = figure.data
    last = max(i for i, v in enumerate(trace.y) if v is not None)
    for i, (size, ring) in enumerate(zip(trace.marker.size, trace.marker.line.width, strict=True)):
        if i == last:
            assert (size, ring) == (config.END_DOT_SIZE, config.END_DOT_RING)
        else:
            assert (size, ring) == (config.MARKER_SIZE, 0)
    assert trace.marker.line.color == config.BACKGROUND


def test_a_line_chart_has_no_legend(rows):
    """visual-spec.md section 6 (2026-10-11): the name tags and the chips do the legend's work."""
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    assert figure.layout.showlegend is False


def test_the_line_plot_keeps_4_px_a_point_and_794_px_across(rows):
    """visual-spec.md section 5: the acceptance rule's floors rest on 4 px a coverage point."""
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    margin = figure.layout.margin
    assert (margin.t, margin.b, margin.l, margin.r) == (68, 52, 52, 204)
    assert (figure.layout.height - margin.t - margin.b) / 100 == 4
    assert figure.layout.width - margin.l - margin.r == 794
    # Plotly would widen a margin to fit tick labels and move the plot off the handoff's place.
    assert figure.layout.xaxis.automargin is False and figure.layout.yaxis.automargin is False


def test_the_line_x_axis_pads_8_px_and_guides_stand_at_1990_to_2020(rows):
    """Drawn from 1985 since 2026-10-12 (visual-spec.md section 1). 2000 is ticked and guided like
    any other fifth year, with no mark of its own."""
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    low, high = figure.layout.xaxis.range
    assert [low, high] == [1984.6, 2024.4]
    assert list(figure.layout.xaxis.tickvals) == [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
    assert figure.layout.xaxis.showgrid is False
    guides = [s.x0 for s in figure.layout.shapes if s.name == "guide"]
    assert guides == [1990, 1995, 2000, 2005, 2010, 2015, 2020]
    # The margin holds the ringed end dot, 5.6 px to the ring's outer edge: 8 px, as the quarter
    # year was over 2000-2024.
    pad_px = config.LINE_X_PAD * 794 / (high - low)
    ring = config.END_DOT_SIZE / 2 + config.END_DOT_RING / 2
    assert 7.9 < pad_px < 8.1 and pad_px > ring


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_every_chart_carries_its_title_and_the_source_line(rows, task):
    """visual-spec.md section 5: drawn in the figure, so both conditions have them."""
    figure = figures.task_figure(task, rows)
    by_name = {a.name: a for a in figure.layout.annotations if a.name in ("title", "source")}
    assert by_name["source"].text == config.SOURCE_TEXT
    assert by_name["title"].text.startswith(f"{task.vaccine} coverage, ")
    assert by_name["title"].font.weight == 700


def test_axis_text_is_drawn_at_medium_weight(rows):
    figure = figures.build_figure(ENTITIES, VACCINE, rows)
    assert figure.layout.yaxis.tickfont.shadow == figures.medium(config.AXIS_COLOR)
    assert figure.layout.yaxis.ticksuffix == "%"


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


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_every_chart_is_fixed_at_1050_by_520(rows, task):
    figure = figures.task_figure(task, rows)
    assert (figure.layout.width, figure.layout.height) == (1050, 520)
    assert figure.layout.autosize is False


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_no_figure_asks_plotly_to_keep_changes_of_its_own(rows, task):
    """Without `uirevision`, every redraw is the figure as sent. The chart is reused from task to
    task, so a kept change could carry one task's zoom or hidden line into the next."""
    assert figures.task_figure(task, rows).layout.uirevision is None


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


# --- Focusing a line and the Years slider (visual-spec.md sections 7.3 and 7.6) -----------------


def test_focusing_a_line_fades_every_other_line_with_its_tag(rows):
    task = tasks.FORM_A[0]
    figure = figures.task_figure(task, rows)
    figures.focus_line(figure, "India")
    others = {name for name in task.entities if name != "India"}
    for trace in figure.data:
        if trace.name == "India":
            assert trace.opacity is None and trace.hoverinfo is None
            assert trace.hovertemplate
        else:
            assert trace.opacity == config.FADED_OPACITY and trace.hoverinfo == "skip"
            # plotly.js ignores `hoverinfo` on a trace with a `hovertemplate`.
            assert trace.hovertemplate is None
            assert trace.visible is None, "faded, not hidden"
    tagged = [*figure.layout.shapes, *figure.layout.annotations]
    faded = {item.name for item in tagged if item.opacity == config.FADED_OPACITY}
    assert faded == {f"{figures.TAG}{name}" for name in others}
    assert all(item.opacity in (None, 1) for item in tagged if item.name == f"{figures.TAG}India")


def test_focusing_moves_nothing_and_none_is_the_chart_as_drawn(rows):
    task = tasks.FORM_A[0]
    drawn = figures.task_figure(task, rows)
    focused = figures.focus_line(figures.task_figure(task, rows), "India")
    assert [t.y for t in focused.data] == [t.y for t in drawn.data]
    assert [a.y for a in focused.layout.annotations] == [a.y for a in drawn.layout.annotations]
    untouched = figures.focus_line(figures.task_figure(task, rows), None)
    assert untouched.to_plotly_json() == drawn.to_plotly_json()


def test_world_is_never_faded_and_cannot_be_focused(rows):
    figure = figures.task_figure(tasks.PRACTICE, rows)
    figures.focus_line(figure, "Myanmar")
    assert all(trace.opacity is None for trace in figure.data)
    with pytest.raises(FigureError):
        figures.focus_line(figure, "World")
    with pytest.raises(FigureError):
        figures.focus_line(_chart("bar", rows), "India")


def test_a_coverage_zoom_places_every_tag_where_its_line_ends(rows):
    """T1's Coverage (visual-spec.md section 7.7): the y axis narrows, and every leader starts
    where its line now ends on the plot, or at the plot's edge when the end lies outside."""
    task = tasks.FORM_A[0]
    figure = figures.set_y_range(figures.task_figure(task, rows), (40, 100))
    assert list(figure.layout.yaxis.range) == [40, 100]
    margin = figure.layout.margin.to_plotly_json()
    height = config.CHART_HEIGHT - margin["t"] - margin["b"]
    top, bottom = margin["t"], config.CHART_HEIGHT - margin["b"]
    # The leader is one curve: a move, then "C" at once. The pill's path draws lines first.
    leaders = {
        s.name: s.path
        for s in figure.layout.shapes
        if (s.name or "").startswith(figures.TAG)
        and s.type == "path"
        and s.path.split()[1].startswith("C")
    }
    for trace in figure.data:
        value = [y for y in trace.y if y is not None][-1]
        expected = bottom - (value - 40) / 60 * height
        expected = min(max(expected, top), bottom)
        start_paper = float(leaders[f"{figures.TAG}{trace.name}"].split()[0].split(",")[1])
        start_px = config.CHART_HEIGHT - margin["b"] - start_paper * height
        assert abs(start_px - expected) < 0.01, trace.name
    assert len(figures.tag_centres(figure)) == len(task.entities), "one tag per line, no more"


def test_no_coverage_zoom_is_the_chart_as_drawn_and_a_bad_one_is_refused(rows):
    task = tasks.FORM_A[0]
    drawn = figures.task_figure(task, rows).to_plotly_json()
    assert figures.set_y_range(figures.task_figure(task, rows), None).to_plotly_json() == drawn
    for bad in ((50, 50), (60, 40), (-10, 50), (0, 120)):
        with pytest.raises(FigureError):
            figures.set_y_range(figures.task_figure(task, rows), bad)
    with pytest.raises(FigureError):
        figures.set_y_range(_chart("bar", rows), (40, 100))


def test_show_turns_off_points_or_tags_and_both_on_is_the_chart_as_drawn(rows):
    task = tasks.FORM_A[0]
    drawn = figures.task_figure(task, rows).to_plotly_json()
    both = figures.set_display(figures.task_figure(task, rows), ["points", "tags"])
    assert both.to_plotly_json() == drawn
    no_points = figures.set_display(figures.task_figure(task, rows), ["tags"])
    assert all(t.mode == "lines" for t in no_points.data)
    no_tags = figures.set_display(figures.task_figure(task, rows), ["points"])
    tagged = [
        item
        for item in (*no_tags.layout.shapes, *no_tags.layout.annotations)
        if (item.name or "").startswith(figures.TAG)
    ]
    assert tagged and all(item.visible is False for item in tagged)
    assert all(t.mode == "lines+markers" for t in no_tags.data)
    with pytest.raises(FigureError):
        figures.set_display(figures.task_figure(task, rows), ["labels"])


@pytest.mark.parametrize(
    ("first", "last"),
    [(1985, 2024), (1985, 1986), (2000, 2024), (2023, 2024), (2005, 2015), (2012, 2013)],
)
def test_the_years_slider_and_the_axis_agree_both_ways(first, last):
    """A slider value becomes an x range with the chart's own margin, and that range reads back as
    the same years."""
    window = figures.year_window(first, last)
    assert figures.years_shown(window) == [first, last]
    if (first, last) == (1985, 2024):
        assert window is None
    else:
        assert window == [first - config.LINE_X_PAD, last + config.LINE_X_PAD]


@pytest.mark.parametrize(
    ("xrange", "years"),
    [
        ([2005.2, 2015.8], [2006, 2015]),
        ([2005.0, 2015.0], [2005, 2015]),
        ([1983.4, 2027.0], [1985, 2024]),
        ([1984.6, 2024.4], [1985, 2024]),
        ([2005.3, 2005.8], [2006, 2007]),
        ([2023.6, 2024.4], [2023, 2024]),
        ([1990.0, 1995.0], [1990, 1995]),
        ([1970.0, 1980.0], [1985, 1986]),
        (None, [1985, 2024]),
    ],
)
def test_a_zoom_reads_as_the_whole_years_it_shows(xrange, years):
    """Always two whole years, at least a year apart, within 1985-2024, as the slider's handles
    are."""
    assert figures.years_shown(xrange) == years


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
        if (trace.name or "").startswith("label:"):
            assert trace.hoverinfo == "skip", "a map name is not a mark: no hover of its own"
            continue
        assert trace.hovertemplate and trace.hovertemplate.endswith("<extra></extra>")


@pytest.mark.parametrize("chart_type", ("line", *NEW_CHARTS))
def test_every_tooltip_is_the_white_card_edged_in_its_marks_colour(rows, chart_type):
    """visual-spec.md section 7.1: white, ink text, no arrow; the dot and the edge in the colour
    of the mark hovered, point by point where the marks differ."""
    figure = (
        figures.build_figure(ENTITIES, VACCINE, rows)
        if chart_type == "line"
        else _chart(chart_type, rows)
    )
    hovered = [t for t in figure.data if not (t.name or "").startswith("label:")]
    assert hovered
    for trace in hovered:
        label = trace.hoverlabel
        assert label.bgcolor == config.BACKGROUND
        assert label.font.color == config.TEXT_PRIMARY
        assert label.showarrow is False
        if chart_type == "line":
            mark = trace.line.color
        elif chart_type == "scatter":
            mark = trace.marker.color
        else:
            mark = trace.customdata
        edge = label.bordercolor
        assert (list(map(list, edge)) if chart_type == "heatmap" else edge) == (
            list(map(list, mark)) if chart_type == "heatmap" else mark
        )
        dot = "%{customdata}" if chart_type in ("bar", "heatmap", "map") else mark
        assert f'<span style="color:{dot}">●</span>' in trace.hovertemplate
    if chart_type == "bar":
        (bars,) = hovered
        assert list(bars.customdata) == list(bars.marker.color)


def test_each_bar_is_its_countrys_colour_and_opens_in_the_listed_order(rows):
    """visual-spec.md sections 1 and 4: a colour per bar, rounded tops, 62% of a slot."""
    task = TASK_BY_CHART["bar"]
    figure = _chart("bar", rows)
    (bars,) = figure.data
    assert list(bars.marker.color) == [figures.bar_color(e) for e in task.entities]
    for entity in task.entities:
        expected = config.COUNTRY_COLORS.get(entity) or config.BAR_COLORS[entity]
        assert figures.bar_color(entity) == expected
    assert bars.marker.cornerradius == 6
    assert bars.width == pytest.approx(0.62)
    assert list(figure.layout.xaxis.categoryarray) == list(task.entities)
    assert list(figure.layout.yaxis.range) == list(config.Y_RANGE)
    assert figure.layout.yaxis.fixedrange is True
    assert not bars.text and not bars.texttemplate, "no value on a bar"


def test_a_bar_country_without_a_colour_is_refused(rows):
    with pytest.raises(FigureError, match="no bar colour"):
        figures.build_figure(["United Kingdom"], VACCINE, rows, chart_type="bar", years=(2010,))


def _order_label(figure):
    (label,) = [a for a in figure.layout.annotations if a.name == figures.ORDER_LABEL]
    return label.text


def test_the_bar_order_label_follows_the_sort(rows):
    figure = _chart("bar", rows)
    assert _order_label(figure) == "Countries in alphabetical order"
    figures.sort_bars(figure, "desc")
    assert _order_label(figure) == "Countries by coverage, highest first"
    figures.sort_bars(figure, "asc")
    assert _order_label(figure) == "Countries by coverage, lowest first"
    figures.sort_bars(figure, "alpha")
    assert figure.to_plotly_json() == _chart("bar", rows).to_plotly_json()


def test_sorting_bars_moves_them_and_changes_nothing_else(rows):
    """Sorting moves the bars (visual-spec.md section 7.2). Each bar keeps its data."""
    task = TASK_BY_CHART["bar"]
    figure = _chart("bar", rows)
    before = figure.data[0].to_plotly_json()
    values = dict(zip(figure.data[0].x, figure.data[0].y, strict=True))
    figures.sort_bars(figure, "desc")
    assert list(figure.layout.xaxis.categoryarray) == sorted(values, key=lambda n: -values[n])
    figures.sort_bars(figure, "asc")
    assert list(figure.layout.xaxis.categoryarray) == sorted(values, key=lambda n: values[n])
    assert figure.data[0].to_plotly_json() == before, "only the axis order changes"
    figures.sort_bars(figure, "alpha")
    assert list(figure.layout.xaxis.categoryarray) == list(task.entities)


def test_a_z_is_the_order_the_bars_are_first_drawn_in():
    """The Sort control opens on A-Z, so A-Z must be the chart as first drawn."""
    for task in (*tasks.FORM_A, *tasks.FORM_B):
        if task.chart == "bar":
            assert list(task.entities) == sorted(task.entities)


def test_a_bar_with_no_value_sorts_last_either_way():
    figure = go.Figure(go.Bar(x=["A", "B", "C"], y=[50, None, 90]))
    figures.sort_bars(figure, "desc")
    assert list(figure.layout.xaxis.categoryarray) == ["C", "A", "B"]
    figures.sort_bars(figure, "asc")
    assert list(figure.layout.xaxis.categoryarray) == ["A", "C", "B"]


def test_an_unknown_sort_is_refused(rows):
    with pytest.raises(FigureError, match="bar sort"):
        figures.sort_bars(_chart("bar", rows), "coverage")
    with pytest.raises(FigureError, match="row sort"):
        figures.sort_rows(_chart("heatmap", rows), "alpha")


def test_a_hidden_bar_fades_in_place(rows):
    """Faded, not removed: it keeps its place, its colour and its label (section 7.3)."""
    figure = _chart("bar", rows)
    names = list(figure.data[0].x)
    figures.set_visible(figure, names[1:])
    assert list(figure.data[0].marker.opacity) == [config.FADED_OPACITY] + [1.0] * (len(names) - 1)
    assert list(figure.data[0].x) == names
    figures.set_visible(figure, names)
    assert figure.data[0].marker.opacity is None, "nothing hidden is the figure as first drawn"


SCATTERS = [t for t in (*tasks.FORM_A, *tasks.FORM_B) if t.chart == "scatter"]


@pytest.mark.parametrize("task", SCATTERS, ids=_task_id)
def test_every_scatter_dot_is_named_and_coloured_by_its_change(rows, task):
    """visual-spec.md sections 1 and 4 (the chart handoff): a name beside every dot, on a knockout,
    and the dot coloured by its change in seven steps. No legend and no shapes."""
    figure = figures.build_figure(
        list(task.entities), task.vaccine, rows, chart_type="scatter", years=task.years
    )
    assert figure.layout.showlegend is False
    for trace in figure.data:
        (x,), (y,) = trace.x, trace.y
        assert trace.marker.color == figures.change_color(y - x)
        assert trace.marker.size == config.SCATTER_MARKER_SIZE
        assert trace.marker.symbol is None
        name = f"dot:{trace.name}"
        (label,) = [a for a in figure.layout.annotations if a.name == name]
        assert label.text == figures.drawn_name(trace.name, "scatter")
        (knockout,) = [s for s in figure.layout.shapes if s.name == name]
        assert knockout.fillcolor == config.BACKGROUND and knockout.layer == "between"


@pytest.mark.parametrize("task", SCATTERS, ids=_task_id)
def test_no_dot_name_touches_another_name_or_dot(rows, task):
    """visual-spec.md section 1: each name sits beside its dot, on the side
    config.SCATTER_LABEL_SIDES gives it, clear of every other name and dot. Twenty-one dots since
    2026-10-13, and a country on both scatters takes one side on both, so both charts are checked.

    Measured in the plot's pixels (4 px a point) as `figures._name_dot` estimates a name: 0.56 em a
    character at 11.5 px, 12 px tall. Calibrated against both charts in headless Chrome."""
    figure = figures.build_figure(
        list(task.entities), task.vaccine, rows, chart_type="scatter", years=task.years
    )
    px, em, half_height, radius = 4, 11.5, 6, config.SCATTER_MARKER_SIZE / 2
    dots = {trace.name: (trace.x[0] * px, trace.y[0] * px) for trace in figure.data}
    boxes = {}
    for label in figure.layout.annotations:
        if not (label.name or "").startswith("dot:"):
            continue
        x, y, width = label.x * px, label.y * px, len(label.text) * em * 0.56
        if label.yshift:  # above, centred
            left, y = x - width / 2, y + label.yshift
        elif label.xanchor == "left":  # right of the dot
            left = x + label.xshift
        else:  # left of the dot
            left = x + label.xshift - width
        boxes[label.name[4:]] = (left, left + width, y - half_height, y + half_height)
    assert set(boxes) == set(dots)

    def overlap(a, b):
        return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]

    def covers(box, dot):
        nearest_x = min(max(dot[0], box[0]), box[1])
        nearest_y = min(max(dot[1], box[2]), box[3])
        return (nearest_x - dot[0]) ** 2 + (nearest_y - dot[1]) ** 2 < radius**2

    for name, box in boxes.items():
        on_dots = [other for other, dot in dots.items() if other != name and covers(box, dot)]
        on_names = [other for other, b in boxes.items() if other != name and overlap(box, b)]
        assert not on_dots and not on_names, (name, on_dots, on_names)


@pytest.mark.parametrize(
    ("change", "step"),
    [
        (52, 0),
        (40.5, 0),
        (40, 1),
        (20, 2),
        (5.5, 2),
        (5, 3),
        (0, 3),
        (-5, 3),
        (-5.5, 4),
        (-20, 4),
        (-21, 5),
        (-40, 5),
        (-41, 6),
    ],
)
def test_a_change_on_a_boundary_takes_the_step_nearer_zero(change, step):
    assert figures.change_color(change) == config.CHANGE_STEPS[step][1]


@pytest.mark.parametrize("task", SCATTERS, ids=_task_id)
def test_the_key_never_stands_alone_in_its_change_colour(rows, task):
    """study-design.md section 4 (2026-10-11): the colour alone never names T3's answer. A-T3's
    Niger shares the darkest blue with two dots, B-T3's India its step with three."""
    figure = figures.build_figure(
        list(task.entities), task.vaccine, rows, chart_type="scatter", years=task.years
    )
    colours = [trace.marker.color for trace in figure.data]
    gains = [trace.y[0] - trace.x[0] for trace in figure.data]
    key = colours[gains.index(max(gains))]
    assert colours.count(key) >= 2


def test_no_scatter_dot_is_clipped_at_the_plot_edge(rows):
    """B-T3's Oman sits at 99, 99; clipped to the axes, half the dot would be cut away
    (visual-spec.md section 1)."""
    figure = _chart("scatter", rows)
    assert all(trace.cliponaxis is False for trace in figure.data)


def test_the_scatter_axes_share_one_scale_so_the_diagonal_means_no_change(rows):
    figure = _chart("scatter", rows)
    assert figure.layout.yaxis.scaleanchor == "x" and figure.layout.yaxis.scaleratio == 1
    assert list(figure.layout.xaxis.range) == list(config.Y_RANGE)
    assert list(figure.layout.yaxis.range) == list(config.Y_RANGE)
    assert figure.layout.xaxis.dtick == 25 and figure.layout.yaxis.dtick == 25
    margin = figure.layout.margin
    assert figure.layout.width - margin.l - margin.r == 400
    assert figure.layout.height - margin.t - margin.b == 400
    (diagonal,) = [s for s in figure.layout.shapes if s.name == "diagonal"]
    assert (diagonal.x0, diagonal.y0, diagonal.x1, diagonal.y1) == (0, 0, 100, 100)
    assert figure.layout.shapes[0].name == "diagonal", "drawn first, under the knockouts"


def test_a_chip_hides_a_dot_with_its_name_and_knockout(rows):
    figure = _chart("scatter", rows)
    names = [trace.name for trace in figure.data]
    figures.set_visible(figure, names[1:])
    hidden = f"dot:{names[0]}"
    assert not [a for a in figure.layout.annotations if a.name == hidden]
    assert not [s for s in figure.layout.shapes if s.name == hidden]
    assert [a for a in figure.layout.annotations if a.name == f"dot:{names[1]}"]


def test_hiding_a_series_leaves_annotations_that_name_no_series(rows):
    """A chip takes a dot's name with it, and nothing else: the title, the axes, the diagonal's
    label, the corners and the key stay."""
    figure = _chart("scatter", rows)

    def unnamed(figure):
        return [a.text for a in figure.layout.annotations if not (a.name or "").startswith("dot:")]

    before = unnamed(figure)
    figures.set_visible(figure, [trace.name for trace in figure.data][:2])
    assert unnamed(figure) == before
    assert "No change" in before


def _cells(figure, name):
    return [shape for shape in figure.layout.shapes if shape.name == f"cell:{name}"]


def test_the_heatmap_carries_value_in_colour_alone(rows):
    """No number in a cell: that would hand static participants the exact value. The trace is
    transparent and carries the hover; the cells are banded shapes (visual-spec.md section 1)."""
    figure = _chart("heatmap", rows)
    (trace,) = figure.data
    assert (trace.zmin, trace.zmax) == config.Y_RANGE
    assert trace.opacity == 0 and trace.showscale is False
    assert trace.texttemplate is None and trace.text is None
    assert figure.layout.yaxis.autorange == "reversed", "the first country listed is the top row"
    for name, row in zip(trace.y, trace.z, strict=True):
        cells = _cells(figure, name)
        assert len(cells) == len(row)
        for cell, value in zip(cells, row, strict=True):
            assert cell.fillcolor == figures.band_color(value, config.HEATMAP_BANDS)
            assert cell.opacity == 1
    assert not [a for a in figure.layout.annotations if (a.name or "").startswith("cell:")]


def test_the_banded_scale_steps_at_each_bound():
    scale = figures.banded_scale(config.HEATMAP_BANDS)
    assert scale[0] == [0.0, config.HEATMAP_BANDS[0][1]]
    assert scale[1] == [0.2, config.HEATMAP_BANDS[0][1]]
    assert scale[2] == [0.2, config.HEATMAP_BANDS[1][1]]
    assert scale[-1] == [1.0, config.HEATMAP_BANDS[-1][1]]
    assert figures.band_color(26, config.HEATMAP_BANDS) == "#0A386D"
    assert figures.band_color(30, config.HEATMAP_BANDS) == "#084E92"
    assert figures.band_color(100, config.HEATMAP_BANDS) == "#CCE9FF"


def test_the_heatmap_order_label_follows_the_sort(rows):
    figure = _chart("heatmap", rows)
    assert _order_label(figure) == "A–Z"
    figures.sort_rows(figure, "min")
    assert _order_label(figure) == "Lowest cell first"
    figures.sort_rows(figure, "max")
    assert _order_label(figure) == "Highest cell first"


def test_the_row_sort_options_are_named_as_their_order_labels():
    """The control and the label over the rows say the same thing (visual-spec.md section 7.2)."""
    _legend, options = layout.SORTS["heatmap"]
    assert dict(options) == figures.ROW_ORDER_LABELS
    assert tuple(value for value, _label in options) == figures.ROW_SORTS


def test_each_t4_key_row_comes_to_the_top_in_one_sort():
    """A-T4 asks for the lowest cell and B-T4 for the highest: Lowest cell first and Highest cell
    first each put that form's key row on top (study-design.md section 4, 2026-10-12)."""
    for form, key, expected in (("A", "min", "Chad"), ("B", "max", "Nepal")):
        (task,) = [t for t in tasks.for_form(form) if t.chart == "heatmap"]
        figure = figures.task_figure(task)
        figures.sort_rows(figure, key)
        assert list(figure.layout.yaxis.categoryarray)[0] == expected, form


def test_sorting_rows_orders_them_by_lowest_or_highest_cell_and_back(rows):
    task = TASK_BY_CHART["heatmap"]
    figure = _chart("heatmap", rows)
    (cells,) = figure.data
    before = cells.to_plotly_json()
    reported = {
        name: [v for v in row if v is not None] for name, row in zip(cells.y, cells.z, strict=True)
    }
    figures.sort_rows(figure, "min")
    assert list(figure.layout.yaxis.categoryarray) == sorted(
        task.entities, key=lambda n: min(reported[n])
    )
    figures.sort_rows(figure, "max")
    assert list(figure.layout.yaxis.categoryarray) == sorted(
        task.entities, key=lambda n: -max(reported[n])
    )
    assert figure.data[0].to_plotly_json() == before, "no cell changes"
    figures.sort_rows(figure, "default")
    assert figure.to_plotly_json() == _chart("heatmap", rows).to_plotly_json()


def test_a_hidden_row_fades_where_it_is_drawn_and_follows_a_sort(rows):
    """A hidden row's cells fade to FADED_OPACITY in place: never white like an empty cell."""
    figure = _chart("heatmap", rows)
    names = list(figure.data[0].y)
    hidden = names[2]
    figures.set_visible(figure, [name for name in names if name != hidden])
    for name in names:
        expected = config.FADED_OPACITY if name == hidden else 1
        assert {cell.opacity for cell in _cells(figure, name)} == {expected}
    before = {name: [c.fillcolor for c in _cells(figure, name)] for name in names}
    figures.sort_rows(figure, "min")
    position = list(figure.layout.yaxis.categoryarray).index(hidden)
    row_px = (config.CHART_HEIGHT - figure.layout.margin.t - figure.layout.margin.b) / len(names)
    top = round(position - 0.5 + 2 / row_px, 6)  # 2 px of the 4 px gap, in rows
    for cell in _cells(figure, hidden):
        assert cell.opacity == config.FADED_OPACITY
        assert f",{top} " in cell.path, "the faded row is drawn where the sort put it"
    assert {name: [c.fillcolor for c in _cells(figure, name)] for name in names} == before


def test_the_map_colours_each_country_by_its_iso_code(rows):
    task = TASK_BY_CHART["map"]
    figure = _chart("map", rows)
    countries = figures._only(figure, go.Choropleth)
    codes = [runtime_data.series(e, task.vaccine, rows)[0].iso_code for e in task.entities]
    assert list(countries.locations) == codes
    assert countries.locationmode == "ISO-3"
    assert (countries.zmin, countries.zmax) == config.Y_RANGE
    assert figure.layout.geo.scope == figures.MAP_SCOPE
    assert figure.layout.dragmode is False, "a fixed view: no drag-to-pan"
    assert countries.colorscale == tuple(
        tuple(step) for step in figures.banded_scale(config.MAP_BANDS)
    ) or [list(step) for step in countries.colorscale] == figures.banded_scale(config.MAP_BANDS)
    assert countries.showscale is False


@pytest.mark.parametrize("task", [t for t in ALL_TASKS if t.chart == "map"], ids=_task_id)
def test_every_coloured_country_is_named_on_the_map(rows, task):
    """visual-spec.md section 1: a name inside each coloured country or beside it on a leader;
    the plain countries are not named, and no name has a hover of its own."""
    figure = figures.task_figure(task, rows)
    labels = [t for t in figure.data if (t.name or "").startswith("label:")]
    named = {t.name[len("label:") :] for t in labels}
    assert named == set(task.entities)
    for trace in labels:
        texts = [text for text in (trace.text or []) if text]
        entity = trace.name[len("label:") :]
        if texts:
            assert texts == [config.MAP_SHORT_NAMES.get(entity, entity)]
        assert trace.hoverinfo == "skip"


def test_the_map_key_has_no_no_data_block(rows):
    """The plain countries report coverage; they are only outside the question (visual-spec.md
    section 1). The handoff's key carries a "No data" block, which would be false here."""
    figure = _chart("map", rows)
    texts = {a.text for a in figure.layout.annotations}
    assert "No data" not in texts
    assert {"100%", "50%", "0%", "Coverage"} <= texts


def test_a_key_band_on_the_map_fades_the_rest_and_moves_nothing(rows):
    """Drawn as a selection: plotly.js 4 drops a per-country marker.opacity list without a word,
    which is how the map's first filter shipped -- fading nothing (visual-spec.md section 7.4)."""
    figure = _chart("map", rows)
    countries = figures._only(figure, go.Choropleth)
    assert countries.unselected.marker.opacity == config.FADED_OPACITY
    assert countries.marker.opacity is None, "a per-country opacity list is never rendered"
    before = list(countries.locations), list(countries.z)
    figures.set_bands(figure, [0, 40])
    assert figures.full_strength(figure) == [value < 50 for value in countries.z]
    assert (list(countries.locations), list(countries.z)) == before


@pytest.mark.parametrize("chart_type", ["scatter", "heatmap", "map"])
def test_no_band_chosen_is_the_figure_as_drawn(rows, chart_type):
    figure = figures.set_bands(_chart(chart_type, rows), [])
    assert figure.to_plotly_json() == _chart(chart_type, rows).to_plotly_json()


def test_a_country_hidden_by_its_chip_stays_faded_in_a_chosen_band(rows):
    figure = _chart("map", rows)
    countries = figures._only(figure, go.Choropleth)
    names = list(countries.text)
    lowest = names[min(range(len(names)), key=lambda i: countries.z[i])]
    figures.set_visible(figure, [name for name in names if name != lowest])
    figures.set_bands(figure, [0])
    assert figures.full_strength(figure)[names.index(lowest)] is False


@pytest.mark.parametrize("chart_type", ["line", "bar"])
def test_only_a_chart_with_a_key_has_bands(chart_type):
    with pytest.raises(FigureError, match="no stepped key"):
        figures.key_blocks(chart_type)


def test_a_band_the_key_does_not_offer_is_refused(rows):
    with pytest.raises(FigureError, match="Not a band"):
        figures.set_bands(_chart("map", rows), [55])


@pytest.mark.parametrize(
    ("chart_type", "lowers", "first_label"),
    [
        ("scatter", [40, 20, 5, -5, -20, -40, -100], "+40 to +100 pts"),
        ("heatmap", [0, 20, 30, 40, 50, 60, 70, 80, 90], "0–20%"),
        ("map", [90, 80, 70, 60, 50, 40, 0], "90–100%"),
    ],
)
def test_each_key_block_names_its_band_in_reading_order(chart_type, lowers, first_label):
    blocks = figures.key_blocks(chart_type)
    assert [b.lower for b in blocks] == lowers
    assert [b.index for b in blocks] == list(range(len(blocks)))
    assert blocks[0].label == first_label
    assert len({b.color for b in blocks}) == len(blocks), "a band is told by its colour"


@pytest.mark.parametrize("chart_type", ["scatter", "heatmap", "map"])
def test_each_key_button_stands_over_the_block_it_names(rows, chart_type):
    """`key_blocks` and the drawn key come from one geometry: every block's box holds a key shape
    filled with that block's colour, in the card's pixels (visual-spec.md section 7.4)."""
    figure = _chart(chart_type, rows)
    margin = figure.layout.margin.to_plotly_json()
    width = config.CHART_WIDTH - margin["l"] - margin["r"]
    height = config.CHART_HEIGHT - margin["t"] - margin["b"]

    def card(x_paper, y_paper):
        return margin["l"] + x_paper * width, config.CHART_HEIGHT - margin["b"] - y_paper * height

    keys = [s for s in figure.layout.shapes if s.name == "key" and s.fillcolor]
    for block in figures.key_blocks(chart_type):
        x, y, w, h = block.box
        filled = [s for s in keys if s.fillcolor == block.color]
        assert filled, block
        for shape in filled:
            if shape.type == "rect":
                (x0, y0), (x1, y1) = card(shape.x0, shape.y0), card(shape.x1, shape.y1)
                assert x - 0.01 <= min(x0, x1) and max(x0, x1) <= x + w + 0.01, block
                assert y - 0.01 <= min(y0, y1) and max(y0, y1) <= y + h + 0.01, block


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


def test_the_map_draws_no_land_but_africa(rows):
    """Plotly's Africa file traced Europe's and Asia's coasts across the top of the frame. The land
    and the coastline the map draws must both be exactly Africa's outline: the arcs only one
    country uses (visual-spec.md section 1)."""
    asset = (config.PROJECT_ROOT / "src" / "assets" / "geo_africa.js").read_text(encoding="utf-8")
    name = f"{figures.MAP_SCOPE}_{figures.MAP_RESOLUTION}m"
    prefix = f'window.PlotlyGeoAssets.topojson["{name}"] = '
    objects = json.loads(asset[asset.index(prefix) + len(prefix) :].rstrip().rstrip(";"))["objects"]

    def arcs(value) -> list[int]:
        if isinstance(value, int):
            return [value if value >= 0 else ~value]
        return [arc for part in value for arc in arcs(part)]

    uses = Counter(arc for g in objects["countries"]["geometries"] for arc in arcs(g["arcs"]))
    outline = {arc for arc, count in uses.items() if count == 1}
    for layer in ("land", "coastlines"):
        drawn = {arc for g in objects[layer]["geometries"] for arc in arcs(g["arcs"])}
        assert drawn == outline, f"{layer}: {sorted(drawn ^ outline)}"
    # The map shows the land and the coastline from this file, and nothing else of the base map's.
    task = next(t for t in ALL_TASKS if t.chart == "map")
    figure = figures.build_figure(
        list(task.entities), task.vaccine, rows, chart_type="map", years=task.years
    )
    geo = figure.layout.geo
    assert (geo.showland, geo.showcoastlines, geo.showcountries) == (True, True, True)
    assert not (geo.showocean or geo.showlakes or geo.showrivers or geo.showsubunits)


@pytest.mark.parametrize("task", ALL_TASKS, ids=_task_id)
def test_no_chart_offers_selection_and_fixed_views_offer_no_zoom(rows, task):
    """visual-spec.md section 7.5. Box and lasso select dim marks without any event recording it,
    and on the map they would override the coverage filter. Download as PNG and Share chart (an
    upload to Plotly Cloud) go everywhere. The map's view is fixed, like the bar, scatter and
    heatmap axes, so their zoom and pan buttons go too. The line chart keeps Zoom in, Zoom out and
    Reset axes, and drops its Zoom and Pan modes and Autoscale, which does not restore its view."""
    removed = set(figures.task_figure(task, rows).layout.modebar.remove)
    assert {"select", "lasso", "toimage", "sendcharttocloud"} <= removed
    if task.chart == "map":
        assert {"pan", "zoomInGeo", "zoomOutGeo", "resetGeo"} <= removed
    elif task.chart != "line":
        assert {"zoom", "pan", "zoomin", "zoomout", "autoscale", "resetscale"} <= removed
    else:
        assert {"zoom", "pan", "autoscale"} <= removed
        assert not {"zoomin", "zoomout", "resetscale"} & removed


def test_reset_axes_is_titled_reset_axis():
    """The line chart's one reset resets its one moving axis. Plotly takes button titles only from
    the config's dictionary; the static condition has no modebar to title."""
    dictionary = figures.graph_config(interactive=True)["locales"]["en-US"]["dictionary"]
    assert dictionary == {"Reset axes": "Reset axis"}


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
        ("map", (1984,)),
    ],
)
def test_a_chart_is_refused_the_wrong_years(rows, chart_type, years):
    with pytest.raises(FigureError):
        figures.build_figure(["Nigeria"], VACCINE, rows, chart_type=chart_type, years=years)


def test_an_unknown_chart_type_is_refused(rows):
    with pytest.raises(FigureError, match="chart type"):
        figures.build_figure(["Nigeria"], VACCINE, rows, chart_type="pie")


def test_the_scatter_is_capped_at_twenty_one_named_dots(rows):
    """Not by the palette, as the line is: dots are coloured by change (visual-spec.md s. 6).
    Sixteen until 2026-10-13."""
    too_many = config.COUNTRIES[: config.MAX_SCATTER_DOTS + 1]
    with pytest.raises(FigureError, match="at most 21"):
        figures.build_figure(too_many, VACCINE, rows, chart_type="scatter", years=(2000, 2024))


def test_bars_and_heatmaps_are_not_capped_by_the_palette(rows):
    """Bars are named on their axis and have colours of their own; rows are named, banded."""
    coloured = [*config.COUNTRY_COLORS, *config.BAR_COLORS]
    assert len(coloured) > config.MAX_SERIES
    figures.build_figure(coloured, VACCINE, rows, chart_type="bar", years=(2010,))
    many = config.COUNTRIES[: config.MAX_SERIES + 4]
    figures.build_figure(many, VACCINE, rows, chart_type="heatmap", years=(2000, 2010))
