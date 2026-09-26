"""The questionnaire exported for IRB request form item 18.

It exists to show the IRB exactly what participants see. These tests hold it to that: every question
and option the app can show is in it, every chart is drawn, and nothing from the answer key is.
"""

from __future__ import annotations

import ast
import html
import importlib.util
from pathlib import Path

import pytest

from src import app, layout, runtime_data, tasks

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "export_questionnaire.py"

pytestmark = pytest.mark.skipif(
    not runtime_data.DEPLOY_CSV.exists(),
    reason="deploy CSV absent; run scripts/export_deploy_data.py",
)


def _script():
    spec = importlib.util.spec_from_file_location("export_questionnaire", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def page() -> str:
    return _script().build_html("https://example.test/study")


def _all_tasks():
    return [tasks.PRACTICE, *tasks.for_form("A"), *tasks.for_form("B")]


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: f"{t.form}-{t.task_id}")
def test_every_question_and_its_options_are_in_the_questionnaire(page, task):
    assert html.escape(task.prompt) in page
    for option in task.options:
        assert html.escape(option) in page, f"{task.task_id}: {option!r} missing"


def test_every_survey_and_background_question_is_in_it(page):
    expected = [tasks.JUSTIFICATION_PROMPT, tasks.LOAD_PROMPT, *tasks.LOAD_ANCHORS.values()]
    expected += list(tasks.LIKERT_ITEMS.values()) + list(tasks.LIKERT_ANCHORS.values())
    expected += list(tasks.CONTROLS_ITEMS.values()) + list(tasks.COMPARISON_CHOICES.values())
    expected += [*tasks.COMPARISON_OPTIONS, tasks.COMPARISON_TEXT]
    for question in tasks.ABOUT_QUESTIONS:
        expected += [question.text, *question.options, *question.rows]
    for text in expected:
        assert html.escape(text) in page, text


def test_the_practice_complete_screen_is_in_it(page):
    assert "That was the practice question. It was not scored." in page


def test_both_versions_of_the_instructions_are_in_it(page):
    """They differ only in what the chart can do; the IRB sees both."""
    assert html.escape("The charts are images: read values against the gridlines") in page
    assert html.escape("You can hover over any line, bar, dot, cell or country") in page
    assert html.escape(layout.SKIP_NOTE) in page


def test_every_chart_is_drawn(page):
    """Practice, twelve items, and one interactive example per chart type: eighteen charts."""
    assert page.count('class="chart"') == 1 + 12 + 5
    assert "Plotly.newPlot" in page


def test_every_chart_types_interactive_version_is_shown(page):
    for chart in ("line", "bar", "scatter", "heatmap", "map"):
        assert f"The interactive version of a question: {chart} chart" in page


def test_the_coverage_slider_is_described_on_paper(page):
    """A slider draws itself in the browser; printed, it would otherwise vanish."""
    assert page.count('class="slider"') == 1
    assert "set to 0% and 100%" in page


def test_the_map_prints_without_fetching_its_shapes(page):
    """The page embeds the geometry the app serves, so printing needs no call to Plotly's CDN."""
    assert 'window.PlotlyGeoAssets.topojson["africa_110m"]' in page


def test_the_interactive_controls_are_shown_once(page):
    assert page.count("Click a line to show it on its own") == 1


def test_the_skip_popups_match_the_app(page):
    """The popup text lives in the app's JavaScript. If it changes there, this must change too."""
    script = _script()
    for text in script.SKIP_POPUPS:
        assert html.escape(text) in page
    assert '"You have not answered "' in app.SUBMIT_JS
    assert '"the multiple-choice question"' in app.SUBMIT_JS
    assert '"how you decided"' in app.SUBMIT_JS
    assert '". Continue without answering?"' in app.SUBMIT_JS
    confirm = app.confirm_js("load-button")
    assert '"You have left "' in confirm and '" question"' in confirm
    assert '" unanswered. Continue without answering?"' in confirm


def test_the_url_is_printed_when_given(page):
    assert "https://example.test/study" in page


def test_no_answer_key_reaches_the_questionnaire():
    """It goes to the IRB, and a copy may go further. The key must not be in it."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
    assert "analysis" not in imported


def test_html_only_writes_the_page_and_needs_no_browser(tmp_path, monkeypatch):
    script = _script()
    monkeypatch.setattr(script, "find_browser", lambda explicit=None: None)
    assert script.main(["--out", str(tmp_path), "--html-only"]) == 0
    assert (tmp_path / "questionnaire.html").exists()
    assert not (tmp_path / "questionnaire.pdf").exists()


def test_without_a_browser_it_says_how_to_print(tmp_path, monkeypatch, capsys):
    script = _script()
    monkeypatch.setattr(script, "find_browser", lambda explicit=None: None)
    assert script.main(["--out", str(tmp_path)]) == 1
    assert (tmp_path / "questionnaire.html").exists(), "the HTML is still written"
    assert "print it to PDF" in capsys.readouterr().err
