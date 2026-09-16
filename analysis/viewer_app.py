"""The local data viewer: health checks, participants and answers, raw events, the section 7 report.

A researcher tool, not a study condition: `docs/visual-spec.md` does not govern it, and nothing here
changes what a participant sees. It lives in `analysis/`, which never ships, because it shows
correctness and so needs the answer key. `scripts/view_data.py` serves it on 127.0.0.1 only.

Data is loaded once per Reload and held server-side. There is deliberately no polling interval: a
timer would keep waking Neon's compute for as long as the tab stays open.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import dash
import pandas as pd
from dash import Input, Output, State, dash_table, dcc, html

from analysis import keys
from analysis import viewer_data as vd

# () -> (records, registered participants or None, a label naming the source)
Loader = Callable[[], tuple[list[dict[str, Any]], list[dict[str, Any]] | None, str]]

NUMERIC = {
    "sessions",
    "static Paas",
    "static accuracy",
    "interactive Paas",
    "interactive accuracy",
    "condition_order",
    "client_elapsed_ms",
    "task_elapsed_ms",
    "server_elapsed_ms",
    "schema_version",
    "duration_ms",
    *vd.INTERACTION_COUNT_COLUMNS,
}

CSS = """
body { margin: 0; background: #FFFFFF; color: #1A1A1A;
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
.page { max-width: 1440px; margin: 0 auto; padding: 16px 24px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h3 { font-size: 16px; margin: 24px 0 4px; }
h4 { font-size: 14px; margin: 16px 0 6px; }
.header { display: flex; flex-wrap: wrap; gap: 12px 24px; align-items: center;
          justify-content: space-between; border-bottom: 1px solid #D0D0D0; padding-bottom: 12px; }
.source { color: #4A4A4A; }
button { font: inherit; padding: 6px 14px; border: 1px solid #5A5A5A; border-radius: 4px;
         background: #F4F4F4; color: #1A1A1A; cursor: pointer; }
button:hover { background: #E6E6E6; }
button:disabled { color: #767676; border-color: #B0B0B0; cursor: not-allowed; }
button:focus-visible, input:focus-visible { outline: 2px solid #1F3A68; outline-offset: 2px; }
.badge { display: inline-block; min-width: 44px; text-align: center; font-weight: 600;
         font-size: 12px; padding: 2px 6px; border-radius: 3px; }
.ok { background: #E3F2E6; color: #1B5E2B; }
.warn { background: #FEF3C7; color: #6B4200; }
.fail { background: #FDE8E8; color: #8A1C1C; }
.info { background: #E6EEF9; color: #1F3A68; }
.banner { padding: 10px 14px; border-radius: 4px; margin: 12px 0; }
table.plain { border-collapse: collapse; margin: 4px 0 8px; }
table.plain td, table.plain th { border-bottom: 1px solid #E0E0E0; padding: 6px 10px;
                                 text-align: left; vertical-align: top; }
table.plain th { background: #F4F4F4; }
details summary { cursor: pointer; color: #1F3A68; margin-top: 2px; }
.muted { color: #4A4A4A; }
.tab-body { padding-top: 12px; }
.downloads { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.session { border: 1px solid #D0D0D0; border-radius: 4px; padding: 4px 16px 12px; margin: 16px 0; }
"""

INDEX = f"""<!DOCTYPE html>
<html lang="en">
<head>{{%metas%}}<title>{{%title%}}</title>{{%favicon%}}{{%css%}}<style>{CSS}</style></head>
<body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer></body>
</html>"""

TABLE_STYLE = {
    "style_table": {"overflowX": "auto"},
    "style_cell": {
        "textAlign": "left",
        "fontFamily": 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        "fontSize": "13px",
        "padding": "6px 8px",
        "whiteSpace": "normal",
        "height": "auto",
        "maxWidth": "420px",
    },
    # Long text gets room; without it DataTable squeezes a prompt into a ten-line sliver.
    "style_cell_conditional": [
        {"if": {"column_id": "prompt"}, "minWidth": "320px"},
        {"if": {"column_id": "payload"}, "minWidth": "360px", "fontSize": "12px"},
        {"if": {"column_id": "justification"}, "minWidth": "200px"},
        {"if": {"column_id": "answer"}, "minWidth": "140px"},
        {"if": {"column_id": "server_ts"}, "minWidth": "200px"},
        {"if": {"column_id": "session_id"}, "minWidth": "150px"},
    ],
    "style_header": {"fontWeight": "600", "backgroundColor": "#F4F4F4"},
}


@dataclass
class Snapshot:
    """One load of the data, with everything derived from it."""

    loaded_at: datetime
    source: str = ""
    records: list[dict[str, Any]] = field(default_factory=list)
    participants: list[dict[str, Any]] | None = None
    checks: list[vd.Check] = field(default_factory=list)
    scoring: vd.Scoring = field(default_factory=vd.Scoring)
    load_error: str | None = None

    @property
    def token(self) -> str:
        return self.loaded_at.isoformat()


def build_snapshot(loader: Loader) -> Snapshot:
    """Load and derive. A failure to load is shown, not raised: the page must still render."""
    now = datetime.now(UTC)
    try:
        records, participants, source = loader()
    except Exception as exc:
        return Snapshot(
            loaded_at=now, load_error=f"Could not load data: {type(exc).__name__}: {exc}"
        )
    records = vd.normalise(records)
    key_problems = keys.check()
    return Snapshot(
        loaded_at=now,
        source=source,
        records=records,
        participants=participants,
        checks=vd.health(records, participants, now=now, key_problems=key_problems),
        scoring=vd.score(records, key_problems=key_problems),
    )


# --- Rendering helpers ---------------------------------------------------------------------------


def _columns(names: list[str]) -> list[dict[str, str]]:
    return [
        {"name": name, "id": name, "type": "numeric" if name in NUMERIC else "text"}
        for name in names
    ]


def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """DataTable rows: JSON-safe, NaN as empty, booleans as text so they display and filter."""
    out = []
    for row in frame.astype(object).where(frame.notna(), None).to_dict("records"):
        out.append({k: (str(v).lower() if isinstance(v, bool) else v) for k, v in row.items()})
    return out


def _plain_table(frame: pd.DataFrame) -> html.Table:
    rows = _rows(frame)
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(c) for c in frame.columns])),
            html.Tbody(
                [
                    html.Tr([html.Td("" if r[c] is None else str(r[c])) for c in frame.columns])
                    for r in rows
                ]
            ),
        ],
        className="plain",
    )


def _banner(status: str, text: str) -> html.Div:
    return html.Div([html.Strong(f"{status.upper()}: "), text], className=f"banner {status}")


def _source_line(snapshot: Snapshot) -> list[Any]:
    if snapshot.load_error:
        return [_banner(vd.FAIL, snapshot.load_error)]
    people = {r["participant_id"] for r in snapshot.records}
    local = snapshot.loaded_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return [
        f"Source: {snapshot.source} · {len(snapshot.records)} events · "
        f"{len(people)} participants with data · loaded {local}"
    ]


def health_panel(snapshot: Snapshot) -> list[Any]:
    if snapshot.load_error:
        return [_banner(vd.FAIL, snapshot.load_error)]
    counts = {
        s: sum(c.status == s for c in snapshot.checks) for s in (vd.FAIL, vd.WARN, vd.INFO, vd.OK)
    }
    rows = []
    for check in snapshot.checks:
        detail: list[Any] = [check.detail]
        if check.ids:
            detail.append(
                html.Details(
                    [
                        html.Summary(f"{len(check.ids)} affected"),
                        html.Ul([html.Li(item) for item in check.ids]),
                    ]
                )
            )
        rows.append(
            html.Tr(
                [
                    html.Td(html.Span(check.status.upper(), className=f"badge {check.status}")),
                    html.Td(html.Strong(check.name)),
                    html.Td(detail),
                ]
            )
        )
    return [
        html.P(" · ".join(f"{n} {s}" for s, n in counts.items()), className="muted"),
        html.Table(
            [
                html.Thead(html.Tr([html.Th("Status"), html.Th("Check"), html.Th("Detail")])),
                html.Tbody(rows),
            ],
            className="plain",
        ),
        html.H3("Counterbalancing cells"),
        html.P("Participants per cell, by what they were shown first.", className="muted"),
        _plain_table(vd.cell_balance(snapshot.records)),
    ]


def summary_panel(snapshot: Snapshot) -> list[Any]:
    if snapshot.load_error:
        return [_banner(vd.FAIL, snapshot.load_error)]
    body: list[Any] = [
        html.P(
            "The same numbers scripts/score_study.py prints. Descriptive only; inferential tests "
            "belong in the analysis notebook.",
            className="muted",
        )
    ]
    if not snapshot.scoring.ok:
        body.append(_banner(vd.FAIL, snapshot.scoring.error))
    for title, frame in vd.report_tables(snapshot.scoring):
        body += [html.H3(title), _plain_table(frame)]
    return body


def detail_panel(snapshot: Snapshot, participant_id: str | None, show: bool) -> list[Any]:
    if not participant_id:
        return [
            html.P("Select a participant in the table to see their sessions.", className="muted")
        ]
    details = vd.participant_detail(
        snapshot.records, snapshot.scoring, participant_id, show_justifications=show
    )
    body: list[Any] = [html.H3(f"Participant {participant_id}")]
    if not details:
        body.append(html.P("Registered, but no events were logged.", className="muted"))
    if not snapshot.scoring.ok:
        body.append(_banner(vd.WARN, f"Correctness unavailable. {snapshot.scoring.error}"))
    for detail in details:
        body.append(
            html.Div(
                [
                    html.H3(detail.title),
                    html.P(detail.summary, className="muted"),
                    html.H4("Answers"),
                    dash_table.DataTable(
                        data=_rows(detail.answers),
                        columns=_columns(list(detail.answers.columns)),
                        sort_action="native",
                        **TABLE_STYLE,
                    ),
                    html.H4("Event timeline"),
                    dash_table.DataTable(
                        data=_rows(detail.events),
                        columns=_columns(list(detail.events.columns)),
                        page_size=25,
                        **TABLE_STYLE,
                    ),
                ],
                className="session",
            )
        )
    return body


# --- App -----------------------------------------------------------------------------------------


def create_app(loader: Loader) -> dash.Dash:
    app = dash.Dash(__name__, title="Study data", update_title=None)
    app.index_string = INDEX
    held: dict[str, Snapshot] = {}

    def current() -> Snapshot | None:
        return held.get("snapshot")

    app.layout = html.Div(
        [
            dcc.Store(id="snapshot-token"),
            dcc.Download(id="download"),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("Study data"),
                            html.Div("Loading…", id="source-line", className="source"),
                        ]
                    ),
                    html.Div(
                        [
                            dcc.Checklist(
                                id="show-justifications",
                                options=[
                                    {
                                        "label": " Show justifications (breaks the coding blind, "
                                        "study-design.md §7)",
                                        "value": "show",
                                    }
                                ],
                                value=[],
                            ),
                            html.Button("Reload", id="reload"),
                        ],
                        style={"display": "flex", "gap": "16px", "alignItems": "center"},
                    ),
                ],
                className="header",
            ),
            dcc.Tabs(
                id="tabs",
                value="health",
                children=[
                    dcc.Tab(
                        label="Health",
                        value="health",
                        children=html.Div(id="health-panel", className="tab-body"),
                    ),
                    dcc.Tab(
                        label="Participants",
                        value="participants",
                        children=html.Div(
                            [
                                dash_table.DataTable(
                                    id="participants-table",
                                    columns=_columns(vd.OVERVIEW_COLUMNS),
                                    data=[],
                                    row_selectable="single",
                                    filter_action="native",
                                    sort_action="native",
                                    page_size=25,
                                    **TABLE_STYLE,
                                ),
                                html.Div(id="participant-detail"),
                            ],
                            className="tab-body",
                        ),
                    ),
                    dcc.Tab(
                        label="Events",
                        value="events",
                        children=html.Div(
                            [
                                html.P(
                                    "Every event, oldest first. Type in the header row to filter "
                                    "(e.g. answer_submit, or > 5000 on a number).",
                                    className="muted",
                                ),
                                dash_table.DataTable(
                                    id="events-table",
                                    columns=_columns(vd.EVENT_TABLE_COLUMNS),
                                    data=[],
                                    filter_action="native",
                                    sort_action="native",
                                    page_size=50,
                                    **TABLE_STYLE,
                                ),
                            ],
                            className="tab-body",
                        ),
                    ),
                    dcc.Tab(
                        label="Summary",
                        value="summary",
                        children=html.Div(
                            [
                                html.Div(
                                    [
                                        html.Button("Download events.csv", id="download-events"),
                                        html.Button("Download tasks.csv", id="download-tasks"),
                                        html.Button(
                                            "Download conditions.csv", id="download-conditions"
                                        ),
                                    ],
                                    className="downloads",
                                ),
                                html.P(
                                    "Downloads are unmasked and include justifications: they are "
                                    "the analysis input. events.csv is the export_logs.py format, "
                                    "readable by score_study.py --events.",
                                    className="muted",
                                ),
                                html.Div(id="summary-panel"),
                            ],
                            className="tab-body",
                        ),
                    ),
                ],
            ),
        ],
        className="page",
    )

    @app.callback(
        Output("snapshot-token", "data"),
        Output("source-line", "children"),
        Output("health-panel", "children"),
        Output("summary-panel", "children"),
        Output("participants-table", "data"),
        Output("download-tasks", "disabled"),
        Output("download-conditions", "disabled"),
        Input("reload", "n_clicks"),
    )
    def reload(_clicks):
        snapshot = build_snapshot(loader)
        held["snapshot"] = snapshot
        overview = vd.participant_overview(
            snapshot.records, snapshot.scoring, snapshot.participants, now=snapshot.loaded_at
        )
        unscored = not snapshot.scoring.ok
        return (
            snapshot.token,
            _source_line(snapshot),
            health_panel(snapshot),
            summary_panel(snapshot),
            _rows(overview),
            unscored,
            unscored,
        )

    @app.callback(
        Output("events-table", "data"),
        Input("snapshot-token", "data"),
        Input("show-justifications", "value"),
    )
    def events(_token, show):
        snapshot = current()
        if snapshot is None:
            return []
        return _rows(vd.events_table(snapshot.records, show_justifications=bool(show)))

    @app.callback(
        Output("participant-detail", "children"),
        Input("participants-table", "selected_row_ids"),
        Input("snapshot-token", "data"),
        Input("show-justifications", "value"),
    )
    def detail(selected, _token, show):
        snapshot = current()
        if snapshot is None:
            return []
        return detail_panel(snapshot, selected[0] if selected else None, bool(show))

    @app.callback(
        Output("download", "data"),
        Input("download-events", "n_clicks"),
        Input("download-tasks", "n_clicks"),
        Input("download-conditions", "n_clicks"),
        State("snapshot-token", "data"),
        prevent_initial_call=True,
    )
    def download(_events, _tasks, _conditions, _token):
        snapshot = current()
        if snapshot is None:
            return dash.no_update
        stamp = snapshot.loaded_at.strftime("%Y%m%d-%H%M%S")
        trigger = dash.ctx.triggered_id
        if trigger == "download-events":
            return {
                "content": vd.events_csv(snapshot.records),
                "filename": f"events-{stamp}.csv",
                "type": "text/csv",
            }
        frame = {
            "download-tasks": snapshot.scoring.tasks,
            "download-conditions": snapshot.scoring.conditions,
        }.get(trigger)
        if frame is None:
            return dash.no_update
        name = trigger.removeprefix("download-")
        return dcc.send_data_frame(frame.to_csv, f"{name}-{stamp}.csv", index=False)

    return app
