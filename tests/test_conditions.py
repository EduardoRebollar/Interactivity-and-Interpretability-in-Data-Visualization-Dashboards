"""The single-toggle constraint, enforced.

CLAUDE.md's central methodological claim is that any observed difference between conditions is
attributable to interactivity and not to appearance. These tests are that claim made checkable:
the figure must be byte-identical across conditions, and the only divergence must be the Plotly
config.
"""

from __future__ import annotations

import json

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


def test_the_task_screen_opens_on_the_same_chart_in_both_conditions(rows):
    """The interactive condition gains CONTROLS, not a different chart.

    Both conditions must open on an identical chart: every series shown, nothing filtered, nothing
    isolated. If the controls ever changed the resting state, the manipulation would confound
    interactivity with what is on screen.
    """
    task = tasks.for_form("A")[0]
    static = layout.task_screen(task, interactive=False, index=1, total=6)
    interactive = layout.task_screen(task, interactive=True, index=1, total=6)

    def figure_of(screen):
        graphs = [
            node
            for node in _walk(screen)
            if getattr(node, "id", None) == "chart" and hasattr(node, "figure")
        ]
        assert len(graphs) == 1
        return graphs[0].figure

    assert figure_of(static).to_json() == figure_of(interactive).to_json()


def test_only_the_interactive_condition_renders_controls(rows):
    task = tasks.for_form("A")[0]
    static_ids = {getattr(n, "id", None) for n in _walk(layout.task_screen(task, False, 1, 6))}
    live_ids = {getattr(n, "id", None) for n in _walk(layout.task_screen(task, True, 1, 6))}
    controls = {"entity-filter", "entity-sort", "reset-view", "control-state"}
    assert not (controls & static_ids), "the static condition must have no controls"
    assert controls <= live_ids


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
    """Six coloured series cannot be told apart; the spec caps it at five."""
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
