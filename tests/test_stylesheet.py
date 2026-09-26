"""The page chrome's stylesheet: the design handoff's, unchanged, plus the few overrides Dash needs.

docs/visual-spec.md section 10, docs/study-redesign.md section 7. Colour contrast of the chrome is
in `tests/test_palette.py`.
"""

from __future__ import annotations

import re

from src import app, config, tasks
from src.flow import SessionState, Stage

ASSETS = config.PROJECT_ROOT / "src" / "assets"
HANDOFF = config.PROJECT_ROOT / "docs" / "design-handoff" / "assets" / "study.css"
STUDY = ASSETS / "study.css"
OVERRIDES = ASSETS / "zz-overrides.css"

# The props through which a Dash component takes a class: its own, and a radio or checkbox list's
# labels and inputs.
CLASS_PROPS = ("className", "labelClassName", "inputClassName")

# The handoff's component sheet previews states with these; the real states come from :hover,
# :focus-visible and :checked (docs/study-redesign.md section 7).
PREVIEW_ONLY = {"is-hover", "is-focus", "is-selected"}


def _css(path) -> str:
    """A stylesheet without its comments, which quote hex codes and class names they do not use."""
    return re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)


def _rules(css: str) -> dict[str, str]:
    """Selector -> its declarations, sorted, for every innermost rule in a block of CSS."""
    found: dict[str, str] = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        declarations = ";".join(sorted(d.strip() for d in body.split(";") if d.strip()))
        for selector in selectors.split(","):
            found[" ".join(selector.split())] = declarations
    return found


def _defined_classes() -> set[str]:
    return set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", _css(STUDY) + _css(OVERRIDES)))


def _screens():
    """Every screen a participant can see: each stage, in each condition and half, and at the task
    stage every item of both forms, since each chart type brings its own controls."""
    for stage in Stage:
        for condition in ("static", "interactive"):
            for index in (0, 1):
                forms = ("A", "B") if stage is Stage.TASK else ("A",)
                for form in forms:
                    positions = range(len(tasks.for_form(form))) if stage is Stage.TASK else (0,)
                    for position in positions:
                        state = SessionState.from_dict(
                            {
                                "stage": stage.value,
                                "participant_id": "P01",
                                "first_condition": condition,
                                "first_form": form,
                                "condition_index": index,
                                "task_index": position,
                            }
                        )
                        yield (
                            f"{stage.value}/{condition}/{index}/{form}{position}",
                            app.render(state),
                        )


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


def _classes(node) -> set[str]:
    found: set[str] = set()
    for prop in CLASS_PROPS:
        value = getattr(node, prop, None)
        if isinstance(value, str):
            found.update(value.split())
    return found


def test_the_stylesheet_is_the_handoffs_unchanged():
    """study.css is copied, never edited; a rule Dash needs goes in zz-overrides.css instead."""
    assert STUDY.read_bytes() == HANDOFF.read_bytes()


def test_the_overrides_load_after_the_stylesheet():
    """Dash serves assets/ in alphabetical order, and of two equal selectors the later one wins."""
    assert sorted(path.name for path in ASSETS.glob("*.css")) == ["study.css", "zz-overrides.css"]


def test_compact_mode_declares_exactly_what_the_stylesheet_declares():
    """The media query stands in for study.css's `.app.is-compact` rules, which only a script could
    switch on. It must say the same thing, so a change to study.css cannot leave it behind."""
    wanted = {
        selector.replace(".app.is-compact ", ".app "): declarations
        for selector, declarations in _rules(_css(STUDY)).items()
        if selector.startswith(".app.is-compact ")
    }
    media = re.search(
        r"@media \(max-height: 800px\)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}", _css(OVERRIDES)
    )
    assert media is not None, "no compact media query in zz-overrides.css"
    assert _rules(media.group(1)) == wanted
    assert {".app .appbar", ".app .page", ".app .ui-head", ".app .ui-main"} <= set(wanted)


def test_every_class_a_screen_uses_is_defined():
    """A class the stylesheet does not define styles nothing: a typo would pass every other test."""
    defined = _defined_classes()
    problems = []
    for name, screen in _screens():
        for node in _walk(screen):
            missing = _classes(node) - defined
            if missing:
                problems.append(f"{name}: {sorted(missing)}")
    assert not problems, "\n".join(sorted(set(problems)))


def test_no_screen_ships_a_preview_only_state():
    """Real states come from the browser (:hover, :focus-visible, :checked), not from classes or
    data attributes that would pin a control in one look."""
    problems = []
    for name, screen in _screens():
        for node in _walk(screen):
            if _classes(node) & PREVIEW_ONLY:
                problems.append(f"{name}: {sorted(_classes(node) & PREVIEW_ONLY)}")
            props = node.to_plotly_json()["props"] if hasattr(node, "to_plotly_json") else {}
            if {"data-checked", "data-value"} & set(props):
                problems.append(f"{name}: a data-checked or data-value attribute")
    assert not problems, "\n".join(sorted(set(problems)))


def test_the_chart_colours_never_appear_in_the_chrome():
    """Two palettes that never mix (visual-spec.md section 10): no series colour and no step of the
    sequential scale is used anywhere in the page's stylesheets."""
    used = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", _css(STUDY) + _css(OVERRIDES))}
    chart = {c.upper() for c in config.SERIES_COLORS}
    chart |= {c.upper() for _stop, c in config.SEQUENTIAL_SCALE}
    assert not used & chart
