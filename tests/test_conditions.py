"""The single-toggle constraint, enforced.

CLAUDE.md's central methodological claim is that any observed difference between conditions is
attributable to interactivity and not to appearance. These tests are that claim made checkable:
the figure must be byte-identical across conditions, and the only divergence must be the Plotly
config.
"""

from __future__ import annotations

import json

import pytest

from src import config, figures, runtime_data
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
