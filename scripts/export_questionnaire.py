"""Export the study questionnaire -- every screen a participant sees -- for the IRB submission.

IRB request form item 18 asks for "a copy of any questionnaires ... For online surveys, please
provide the URL here and also attach a PDF copy of the survey." This builds that copy from the
app's own screen functions in `src/layout.py`. The PDF and the running study are rendered by the
same code, so their wording cannot drift apart.

It contains no answer key: it imports nothing from `analysis/`, and `tests/test_questionnaire.py`
checks that. The options are shown as participants see them, correct one included, unmarked.

Writes `irb/questionnaire.html` (gitignored, like everything in `irb/`), then prints it to
`irb/questionnaire.pdf` with headless Chrome or Edge. The browser is looked for on PATH and in the
standard install folders, or given with --browser. With no browser, open the HTML file and print it
to PDF from any browser.

Usage:
    uv run python scripts/export_questionnaire.py
    uv run python scripts/export_questionnaire.py --url https://<the study's Vercel URL>
    uv run python scripts/export_questionnaire.py --html-only
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plotly.graph_objects as go  # noqa: E402
from dash.development.base_component import Component  # noqa: E402
from plotly.offline import get_plotlyjs  # noqa: E402

from src import config, consent, figures, layout, runtime_data, tasks  # noqa: E402

DEFAULT_OUT = ROOT / "irb"
# The map's country shapes, which the app serves from src/assets (scripts/vendor_map_geometry.py).
GEOMETRY = ROOT / "src" / "assets" / "geo_africa.js"
# Charts print at their own fixed width (visual-spec.md section 5); STYLE scales them to the page.
PRINT_WIDTH = config.CHART_WIDTH
EXAMPLE_ID = "P07"

# What the browser's own confirmation popup says when a question is left unanswered. The text lives
# in the clientside JavaScript in `src/app.py`; `tests/test_questionnaire.py` checks it is still
# there, word for word.
SKIP_POPUPS = (
    "You have not answered the multiple-choice question or how you decided. Continue without "
    "answering?",
    "You have not written a description. Continue without answering?",
    "You have left 1 question unanswered. Continue without answering?",
)

_SKIPPED = {"Store", "Location", "Interval", "Download", "Upload"}
_TAGS = {
    "Div": "div",
    "P": "p",
    "H1": "h1",
    "H2": "h2",
    "H3": "h3",
    "Span": "span",
    "Label": "label",
    "Strong": "strong",
    "B": "b",
    "Em": "em",
    "A": "a",
    "Ul": "ul",
    "Ol": "ol",
    "Li": "li",
    "Main": "main",
    "Aside": "aside",
    "Header": "header",
    "Article": "article",
    "Table": "table",
    "Thead": "thead",
    "Tbody": "tbody",
    "Tr": "tr",
    "Th": "th",
    "Td": "td",
}


def _css(style: dict | None) -> str:
    """A Dash style dict as inline CSS: camelCase keys become kebab-case."""
    if not style:
        return ""
    return "; ".join(
        f"{re.sub(r'([A-Z])', lambda m: '-' + m.group(1).lower(), key)}: {value}"
        for key, value in style.items()
    )


def _attr(name: str, value) -> str:
    return f' {name}="{html.escape(str(value), quote=True)}"' if value not in (None, "") else ""


class Renderer:
    """Dash component trees to static HTML, with the app's classes and the markup Dash 4 renders for
    option lists and inputs, so the app's own stylesheets draw them as participants see them.
    Charts are collected and drawn by plotly.js on load.

    Nothing is disabled: a disabled control is drawn greyed out, and the page has no script that
    could submit anything anyway.
    """

    def __init__(self) -> None:
        self.figures: list[str] = []

    def render(self, node) -> str:
        if node is None:
            return ""
        if isinstance(node, (list, tuple)):
            return "".join(self.render(child) for child in node)
        if isinstance(node, (str, int, float)):
            return html.escape(str(node))
        spec = node.to_plotly_json()
        kind, props = spec["type"], spec["props"]
        if props.get("id") == "flow-error":
            # The validation-error slot on every screen: always empty on a fresh one.
            return ""
        classes = (props.get("className") or "").split()
        if "sr-only" in classes:
            # Names only a screen reader hears (each radio of the tools question).
            return ""
        if kind == "Canvas":
            return ""
        if props.get("hidden") and "pager-page" not in classes:
            # Hidden until something happens on screen. The survey's pages are the exception: the
            # questionnaire shows every question, where the screen shows one at a time.
            return ""
        if spec["namespace"] == "dash_core_components":
            return self._core(kind, props)
        attrs = _attr("class", props.get("className")) + _attr("style", _css(props.get("style")))
        if kind == "Img":
            size = _attr("width", props.get("width")) + _attr("height", props.get("height"))
            return f'<img{attrs}{_attr("src", _embedded(props.get("src")))} alt=""{size}>'
        if kind == "Br":
            return "<br>"
        if kind == "A":
            attrs += _attr("href", props.get("href"))
        if kind in ("Th", "Td"):
            attrs += _attr("colspan", props.get("colSpan")) + _attr("scope", props.get("scope"))
        if kind == "Progress":
            attrs += _attr("value", props.get("value")) + _attr("max", props.get("max"))
            return f"<progress{attrs}></progress>"
        inner = self.render(props.get("children"))
        if kind == "Button":
            return f'<button type="button"{attrs}>{inner}</button>'
        tag = _TAGS.get(kind, "div")
        return f"<{tag}{attrs}>{inner}</{tag}>"

    def _core(self, kind: str, props: dict) -> str:
        if kind in _SKIPPED:
            return ""
        classes = props.get("className") or ""
        if kind == "Graph":
            printed = go.Figure(props["figure"])
            printed.update_layout(width=PRINT_WIDTH)
            self.figures.append(printed.to_json())
            return (
                f'<div class="chart" data-figure="{len(self.figures) - 1}" '
                f'style="width: {PRINT_WIDTH}px; height: {config.CHART_HEIGHT}px"></div>'
            )
        if kind in ("RadioItems", "Checklist"):
            chosen = props.get("value")
            chosen = chosen if isinstance(chosen, list) else [chosen]
            kind_of_input = "radio" if kind == "RadioItems" else "checkbox"
            text_class = " ".join(
                filter(None, ["dash-options-list-option-text", props.get("labelClassName")])
            )
            options = []
            for option in props.get("options", []):
                label, value = (
                    (option["label"], option["value"])
                    if isinstance(option, dict)
                    else (option,) * 2
                )
                checked = " checked" if value is not None and value in chosen else ""
                # A chip's label is a flag and a name, as components; a scale point's, a number
                # and its anchor.
                if isinstance(label, (list, Component)):
                    text = self.render(label)
                else:
                    text = html.escape(str(label))
                options.append(
                    '<label class="dash-options-list-option">'
                    '<span class="dash-options-list-option-wrapper">'
                    f'<input type="{kind_of_input}" class="dash-options-list-option-checkbox"'
                    f"{checked}></span>"
                    f'<span class="{text_class}">{text}</span></label>'
                )
            return f"<div{_attr('class', classes)}>{''.join(options)}</div>"
        if kind == "Input":
            box = " ".join(filter(None, ["dash-input-container", classes]))
            return (
                f'<div class="{box}"><input class="dash-input-element"'
                f"{_attr('type', props.get('type', 'text'))}"
                f"{_attr('value', props.get('value'))}"
                f"{_attr('placeholder', props.get('placeholder'))}></div>"
            )
        if kind == "Textarea":
            area = " ".join(filter(None, ["dash-textarea", classes]))
            return f'<textarea class="{area}"{_attr("rows", props.get("rows"))}></textarea>'
        return self.render(props.get("children"))


def _embedded(source: str | None) -> str | None:
    """An image the app serves from src/assets (a chip's flag), as a data URI, so the file needs
    nothing beside it. Anything else (the undo icon is already a data URI) as it is."""
    if not source or not source.startswith("assets/"):
        return source
    data = (ROOT / "src" / source).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _hover_example() -> str:
    """A real tooltip from the interactive version, for the note that describes it."""
    series = runtime_data.series("India", "DTP3", runtime_data.load_rows())
    labels = dict(zip([r.year for r in series], figures.change_labels(series), strict=True))
    value = next(r.coverage_pct for r in series if r.year == 2017)
    return f"India / 2017: {value:.0f}% / {labels[2017]}"


# What the interactive version adds to each chart type (visual-spec.md section 7), for the notes
# beside its example screen. Hover is described, not shown: a tooltip value could be an item's key.
INTERACTIVE_NOTES = {
    "line": (
        "The interactive version adds the controls under it: a button for each country, which "
        "hides or shows its line; a View control, which lists the countries by coverage; Show "
        "all; and Reset view. Clicking a line shows it alone. Clicking a name in the legend hides "
        "or shows that line, and double-clicking shows it alone. Hovering a point shows its value "
        "and the change from the year before."
    ),
    "bar": (
        "The interactive version adds the controls under it: a button for each country, which "
        "fades or restores its bar; a Sort control (A-Z, High to low, Low to high), which reorders "
        "the bars; and Reset view. Hovering a bar shows its exact value."
    ),
    "scatter": (
        "The interactive version adds a button for each country under it, which hides or shows its "
        "dot, and Reset view. Hovering a dot shows the country's name and its two values."
    ),
    "heatmap": (
        "The interactive version adds the controls under it: a button for each country, which "
        "fades or restores its row; a Sort rows control (Default, Lowest value, Average), which "
        "reorders the rows; and Reset view. Hovering a cell shows its exact value."
    ),
    "map": (
        "The interactive version adds the controls under it: a button for each country, which "
        "fades or restores it; a Highlight box, which fades every country whose coverage is not "
        "below the number typed; and Reset view. Hovering a country shows its name and exact value."
    ),
}


def _screens() -> list[tuple[str, str, object]]:
    """(title, note, screen) for every screen, in the order a participant meets them."""
    screens: list[tuple[str, str, object]] = [
        (
            "Declining consent",
            "The first screen is the informed consent form, which is attached to this submission "
            "as a separate document and shown in the app word for word. A participant who presses "
            '"I do not agree" sees this screen instead, and nothing is recorded.',
            layout.declined_screen(),
        ),
        ("Participant ID", "After consent.", layout.participant_screen()),
    ]
    for interactive in (False, True):
        version = "interactive" if interactive else "static"
        screens.append(
            (
                f"Instructions before the first half: {version} version",
                "Each participant uses both versions of the chart, one in each half. Which comes "
                "first is counterbalanced.",
                layout.instructions_screen(interactive, practice=True),
            )
        )
    for interactive in (False, True):
        version = "interactive" if interactive else "static"
        screens.append(
            (
                f"Instructions before the second half: {version} version",
                "Shown again before the second half, describing the version about to be used.",
                layout.instructions_screen(interactive, practice=False),
            )
        )
    screens.append(
        (
            "Practice question",
            "Unscored. Shown once, in the first half, to teach the interface.",
            layout.task_screen(tasks.PRACTICE, False, index=0, total=0, practice=True),
        )
    )
    screens.append(
        (
            "After the practice question",
            "First half only, between the practice and the first scored question.",
            layout.practice_complete_screen(),
        )
    )
    for form in sorted(tasks.FORMS):
        items = tasks.for_form(form)
        for index, task in enumerate(items, start=1):
            screens.append(
                (
                    f"Form {form}, question {index} of {len(items)}",
                    "Each participant answers form A in one half and form B in the other, never "
                    "the same form twice. Shown here as in the static version.",
                    layout.task_screen(task, False, index=index, total=len(items)),
                )
            )
    items = tasks.for_form("A")
    for index, task in enumerate(items, start=1):
        if task.chart in INTERACTIVE_NOTES and not any(
            earlier.chart == task.chart for earlier in items[: index - 1]
        ):
            note = INTERACTIVE_NOTES[task.chart]
            if task.chart == "line":
                note += f' For example: "{_hover_example()}".'
            screens.append(
                (
                    f"The interactive version of a question: {task.chart} chart",
                    "The chart is identical in both versions. " + note,
                    layout.task_screen(task, True, index=index, total=len(items)),
                )
            )
    screens += [
        (
            "Survey after each half",
            "Asked after each half, so each version is rated on its own. The questions about the "
            "chart controls are asked only after the interactive half, and the comparison of the "
            "two versions only after the second half. Shown here as after an interactive second "
            "half, which asks every section.",
            layout.load_screen(interactive=True, second_half=True),
        ),
        ("Between the halves", "After the first half's survey.", layout.break_screen()),
        (
            "About you",
            "Once, at the end, after the second half's survey.",
            layout.demographics_screen(),
        ),
        (
            "The end",
            f"The participant's own ID is shown; {EXAMPLE_ID} is an example.",
            layout.complete_screen(EXAMPLE_ID),
        ),
    ]
    return screens


# The app's stylesheets, in the order Dash loads them, so each screen prints as it looks.
STYLESHEETS = [
    ROOT / "src" / "assets" / name for name in ("study.css", "zz-bridge.css", "zz-overrides.css")
]

STYLE = """
@page { size: Letter landscape; margin: 0.5in; }
/* Printed at once: a card caught mid-fade would print pale. */
* { animation: none !important; transition: none !important; }
html, body { background: #FFFFFF; }
body { font-family: Helvetica, Arial, sans-serif; color: #1A1A1A; margin: 0; }
.cover { max-width: 760px; }
.cover h1 { font-size: 24px; margin: 0 0 8px; }
.cover p, .cover li { font-size: 14px; line-height: 1.5; }
section { break-before: page; }
.q-label { font-size: 12px; color: #595959; text-transform: uppercase; letter-spacing: 0.04em;
           border-bottom: 1px solid #B3B3B3; padding-bottom: 4px; margin: 0 0 6px; }
.q-note { font-size: 13px; color: #595959; margin: 0 0 10px; line-height: 1.4; }
/* Each screen at 0.6 of its size, on its oat ground: the widest, the task screen at 1440 px, fits
   the landscape page's 960, and the longest instructions fit its height. */
.screen { border: 1px solid #B3B3B3; border-radius: 6px; zoom: 0.6; background: var(--c-page); }
/* The room a screen keeps below its content, for a window, is dropped on paper. */
.screen .page, .screen .stage { padding-bottom: 0; }
/* The part of Dash's own stylesheet a text box needs: the input fills the box the app's classes
   style, in the box's font. */
.dash-input-container { display: inline-flex; align-items: center; box-sizing: border-box; }
.dash-input-element { flex: 1 1 0; min-width: 0; font: inherit; color: inherit; background: none;
                      border: none; outline: none; }
/* Chrome's printing does not place an absolutely positioned grid item in its grid cell, so the
   text box laid over "Other" vanished from the PDF. On paper it is an ordinary item of the grid,
   in the same cell as that option (the last of pointer's, the last but one of field's). */
.screen .other-box { position: relative; inset: auto; z-index: 1; }
.screen .choice-grid:has(.other-box--r2c1) .dash-options-list-option:last-child {
  grid-row: 2 / 3; grid-column: 1 / 2; }
.screen .choice-grid:has(.other-box--r3c2) .dash-options-list-option:nth-last-child(2) {
  grid-row: 3 / 4; grid-column: 2 / 3; }
.popup { border: 1px solid #404040; border-radius: 6px; padding: 12px 16px; margin: 8px 0;
         font-size: 14px; max-width: 520px; }
"""


def build_html(url: str | None = None) -> str:
    """The whole questionnaire as one self-contained HTML document."""
    renderer = Renderer()
    sections = []
    for number, (title, note, screen) in enumerate(_screens(), start=2):
        sections.append(
            f'<section><p class="q-label">Screen {number}: {html.escape(title)}</p>'
            f'<p class="q-note">{html.escape(note)}</p>'
            f'<div class="screen">{renderer.render(screen)}</div></section>'
        )
    popups = "".join(f'<div class="popup">{html.escape(text)}</div>' for text in SKIP_POPUPS)
    sections.append(
        '<section><p class="q-label">Skipping a question</p>'
        '<p class="q-note">Any question may be skipped. Pressing Submit or Continue with a '
        "question unanswered opens the browser's own confirmation popup, which names what is "
        "missing. OK moves on; Cancel returns to the question. For example:</p>"
        f"{popups}</section>"
    )
    location = (
        f"<p>URL: {html.escape(url)}</p>"
        if url
        else "<p>URL: the study's Vercel address, as entered on the request form.</p>"
    )
    cover = f"""<div class="cover">
<h1>Study questionnaire</h1>
<p><strong>{html.escape(consent.TITLE)}</strong><br>
Student investigator: {html.escape(consent.INVESTIGATOR)}.
Faculty supervisor: {html.escape(consent.SUPERVISOR)}.</p>
<p>IRB approval request form, item 18: every screen and question a participant sees in the study's
web application, in the order they are shown.</p>
{location}
<p>One session, about 40 minutes:</p>
<ol>
<li>informed consent (attached separately), then a participant ID;</li>
<li>instructions, one practice question, six questions (the first a short written description of
two trends, the other five multiple choice), and a short survey, using one version of the
charts;</li>
<li>a break;</li>
<li>instructions, six different questions, and the same survey, using the other version, followed
by two questions comparing the versions;</li>
<li>ten background questions.</li>
</ol>
<p>Every question may be skipped. Each half asks about five kinds of chart: line charts, a bar
chart, a scatter plot, a grid of coloured cells and a map. The two versions show identical charts;
the interactive one adds hover tooltips to every chart and controls under each one: a button per
country that hides or shows it, and Reset view; on the line charts a clickable legend, reordering,
Show all and isolating a line; sorting on the bar chart and the grid; and a highlight on the map.
Each participant answers form A with one version and form B with the other, in one of four
counterbalanced orders.</p>
<p class="q-note">Generated {date.today().isoformat()} by scripts/export_questionnaire.py from the
application's own screen code. Consent text version {consent.CONSENT_VERSION}.</p>
</div>"""
    app_css = "\n".join(sheet.read_text(encoding="utf-8") for sheet in STYLESHEETS)
    payload = json.dumps(renderer.figures).replace("</", "<\\/")
    geometry = GEOMETRY.read_text(encoding="utf-8").replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Study questionnaire</title>
<style>{app_css}</style>
<style>{STYLE}</style>
</head><body>
{cover}
{"".join(sections)}
<script>{geometry}</script>
<script>{get_plotlyjs()}</script>
<script type="application/json" id="figures">{payload}</script>
<script>
var figures = JSON.parse(document.getElementById("figures").textContent);
document.querySelectorAll(".chart").forEach(function (div) {{
  var figure = JSON.parse(figures[Number(div.dataset.figure)]);
  Plotly.newPlot(div, figure.data, figure.layout, {{staticPlot: true}});
}});
</script>
</body></html>
"""


def find_browser(explicit: str | None = None) -> str | None:
    """A Chromium-based browser that can print to PDF, or None."""
    if explicit:
        return explicit
    for name in ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    folders = [os.environ.get(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    for folder in filter(None, folders):
        for relative in (
            ("Google", "Chrome", "Application", "chrome.exe"),
            ("Microsoft", "Edge", "Application", "msedge.exe"),
        ):
            candidate = Path(folder).joinpath(*relative)
            if candidate.exists():
                return str(candidate)
    return None


def print_pdf(browser: str, source: Path, target: Path) -> None:
    """Print the HTML to PDF in a throwaway browser profile, so a running browser is untouched."""
    target.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=30000",
                f"--print-to-pdf={target}",
                source.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"{browser} did not write {target}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="folder to write into")
    parser.add_argument("--url", help="the study's deployed URL, printed on the cover")
    parser.add_argument("--browser", help="path to Chrome, Chromium or Edge")
    parser.add_argument("--html-only", action="store_true", help="skip printing to PDF")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    page = args.out / "questionnaire.html"
    page.write_text(build_html(args.url), encoding="utf-8")
    print(f"Wrote {page}")
    if args.html_only:
        return 0

    browser = find_browser(args.browser)
    if browser is None:
        print(
            "No Chrome or Edge found. Open the HTML file in a browser and print it to PDF, "
            "or pass --browser.",
            file=sys.stderr,
        )
        return 1
    pdf = args.out / "questionnaire.pdf"
    try:
        print_pdf(browser, page, pdf)
    except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
        print(f"Printing to PDF failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
