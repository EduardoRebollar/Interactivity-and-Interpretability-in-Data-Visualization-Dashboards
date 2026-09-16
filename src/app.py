"""Dash entry point. No pandas — this ships to production.

Run locally:
    uv run python -m src.app                  # condition from config.INTERACTIVE
    uv run python -m src.app --interactive    # force the interactive condition

Deployed, the condition comes from per-session state rather than from `config.INTERACTIVE`, because
one URL serves both conditions (see the amendment in CLAUDE.md). For reviewing a condition during
development, `?interactive=1` on the URL overrides it.

**The study flow UI (consent, participant ID, task prompts, answers) is not built yet.** It is
blocked on `docs/study-design.md`: the tasks, prompts, answer formats and rubric are protocol
decisions. `src/flow.py` holds the complete, tested state machine those screens will drive, and
`src/logging.py` already records `answer_submit`. What exists here is the chart view in both
conditions, which is what can be built without inventing the protocol.
"""

from __future__ import annotations

import argparse
import os

import dash
from dash import Input, Output, dcc, html

from src import config, figures, layout, runtime_data

# Shown until the study design names the entities each task uses. Five countries plus the World
# reference is the documented display ceiling; see docs/visual-spec.md section 6.
PREVIEW_ENTITIES = ["Nigeria", "India", "Brazil", "Pakistan", "Ethiopia", "World"]
PREVIEW_VACCINE = "DTP3"


def create_app() -> dash.Dash:
    """Build the Dash app. Kept a factory so tests and the Vercel entry point share one path."""
    app = dash.Dash(__name__, title="Vaccination coverage")

    app.layout = html.Div(
        [
            dcc.Location(id="url"),
            # Session state lives in the browser so a serverless container holds nothing per user.
            dcc.Store(id="session-state", storage_type="session"),
            # Browser clock origin. Timing is measured here, never on the server: each event is its
            # own request, so a server clock would fold cold starts into the measurement.
            dcc.Store(id="clock-origin", storage_type="session"),
            html.Div(id="page"),
        ]
    )

    _register_callbacks(app)
    return app


def _register_callbacks(app: dash.Dash) -> None:
    @app.callback(Output("page", "children"), Input("url", "search"))
    def render(search: str | None):
        return _chart_page(_interactive_from_query(search))

    # Establishes the browser time origin once per session. Clientside so it never touches the
    # server clock.
    app.clientside_callback(
        """
        function(_) {
            return window.performance.now();
        }
        """,
        Output("clock-origin", "data"),
        Input("url", "pathname"),
    )


def _interactive_from_query(search: str | None) -> bool:
    """Condition override for development review. Deployed, this comes from session state."""
    if search and "interactive=1" in search:
        return True
    if search and "interactive=0" in search:
        return False
    return config.INTERACTIVE


def _chart_page(interactive: bool) -> html.Div:
    condition = "interactive" if interactive else "static"
    children = [
        layout.heading(f"{PREVIEW_VACCINE} coverage"),
        html.P(
            "Vaccination coverage among one-year-olds, as reported by WHO and UNICEF.",
            style=layout.PROMPT_STYLE,
        ),
        layout.chart(PREVIEW_ENTITIES, PREVIEW_VACCINE, interactive),
    ]
    note = layout.gap_note(PREVIEW_ENTITIES, PREVIEW_VACCINE)
    if note is not None:
        children.append(note)
    children.append(
        html.P(
            f"Condition: {condition}. Preview only; the study flow is not built yet.",
            style=layout.MUTED_STYLE,
        )
    )
    return layout.page(*children)


# Module-level app so `api/index.py` and Dash's dev server share one instance. Building it at import
# time also means a warm serverless container skips the work entirely.
app = create_app()
server = app.server


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the study dashboard locally.")
    parser.add_argument(
        "--interactive", action="store_true", help="force the interactive condition"
    )
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()

    if args.interactive:
        config.INTERACTIVE = True

    rows = runtime_data.load_rows()
    condition = "interactive" if config.INTERACTIVE else "static"
    print(f"Condition: {condition}  ({len(rows)} rows loaded)")
    print(f"Toggle with ?interactive=1 / ?interactive=0 on http://127.0.0.1:{args.port}/")
    app.run(debug=bool(os.environ.get("DASH_DEBUG")), port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["app", "server", "create_app", "figures"]
