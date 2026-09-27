"""The questionnaire exported for IRB request form item 18.

It exists to show the IRB exactly what participants see. These tests hold it to that: every question
and option the app can show is in it, every chart is drawn, and nothing from the answer key is.
"""

from __future__ import annotations

import ast
import html
import importlib.util
import re
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
    """They differ only in what the chart can do; the IRB sees both, before each half."""
    wording = [layout.STATIC_BULLET, layout.STATIC_OTHER_CHARTS, *layout.INTERACTIVE_BULLETS]
    wording += [layout.SECOND_HALF_POINTING, layout.SECOND_HALF_STATIC.strip()]
    wording += [*layout.PRACTICE_INTRO, layout.SECOND_HALF_INTRO, layout.SECOND_HALF_CLOSE]
    for text in wording:
        assert html.escape(text) in page, text
    assert "<b>static</b>" in page and "<b>interactive</b>" in page


def test_every_chart_is_drawn(page):
    """Practice, twelve items, and one interactive example per chart type: eighteen charts."""
    assert page.count('class="chart"') == 1 + 12 + 5
    assert "Plotly.newPlot" in page


def test_every_chart_types_interactive_version_is_shown(page):
    for chart in ("line", "bar", "scatter", "heatmap", "map"):
        assert f"The interactive version of a question: {chart} chart" in page


def test_the_map_highlight_is_printed_with_its_starting_value(page):
    """The box starts at 100, which highlights nothing (visual-spec.md section 7.4)."""
    assert page.count(f'type="number" value="{layout.THRESHOLD_START}"') == 1
    assert "Below" in page


def test_the_map_prints_without_fetching_its_shapes(page):
    """The page embeds the geometry the app serves, so printing needs no call to Plotly's CDN."""
    assert 'window.PlotlyGeoAssets.topojson["africa_110m"]' in page


def test_the_interactive_controls_are_shown_once_per_chart_type(page):
    for hint in layout.HINTS.values():
        assert page.count(html.escape(hint)) == 1, hint


def test_a_chips_flag_and_name_print_not_the_components_repr(page):
    """A chip's label is a flag and a name, as components. Both must print, never a repr, and the
    flag from inside the page: the file goes to the IRB with nothing beside it."""
    assert "Img(" not in page and "Span(" not in page
    assert 'class="chip-flag"' in page
    assert 'src="assets/' not in page
    assert 'src="data:image/png;base64,' in page


def test_the_screens_print_in_the_apps_own_styles(page):
    """The questionnaire shows the IRB what participants see: the app's three stylesheets are in
    the page, and the markup carries the classes and Dash's option markup they style."""
    for sheet in ("study.css", "zz-bridge.css", "zz-overrides.css"):
        css = (ROOT / "src" / "assets" / sheet).read_text(encoding="utf-8")
        assert css in page, sheet
    assert 'class="dash-options-list-option"' in page
    assert 'class="scale scale-7"' in page and 'class="stage-col pager"' in page


def test_nothing_prints_disabled_and_the_tools_table_spans_its_columns(page):
    """A disabled control is drawn greyed out, which no participant sees. The tools question's
    radios span the five level columns, as on screen."""
    markup = re.sub(r"<(style|script)\b.*?</\1>", "", page, flags=re.S)
    assert not re.search(r"<[a-z]+\b[^>]*\sdisabled[\s=>]", markup)
    assert page.count(f'colspan="{len(tasks.TOOL_LEVELS) + 1}"') == 5


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
