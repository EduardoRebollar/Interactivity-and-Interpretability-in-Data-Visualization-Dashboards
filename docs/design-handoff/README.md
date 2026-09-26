# Handoff: Vaccination coverage study — participant UI

## Overview
The participant-facing screens of a Plotly Dash study app. It compares static and interactive data-visualization dashboards: consent → participant ID → instructions → practice → Part 1 (6 questions) → survey → break → Part 2 → survey → About you → finished. Each task screen shows one chart (line, bar, scatter, heatmap or map) with a multiple-choice answer and a one-sentence justification.

## About the design files
The `.dc.html` files are **design references built in HTML**. They show the intended look and behaviour and are not production code. Recreate them in the Dash app with `html.*` / `dcc.*` components. The one exception is `assets/study.css`, which is production-ready: put it in the Dash `assets/` folder and Dash loads it automatically. Every class named below is defined there.

Open the `.dc.html` files in a browser (they need `support.js` next to them). `Study UI Screens.dc.html` is a pan/zoom canvas of 1440 × 900 artboards. The dashed violet line at y = 790 marks the browser fold on a 1440 × 900 laptop.

## Fidelity
**High-fidelity.** Final colours, type, spacing and states. Match them exactly, using the classes in `study.css` and not inline styles. In the mockups, the only remaining inline styles are artboard framing, the grey chart placeholder, the consent-document reproduction, and data-driven values (grid columns, chip justification).

## Reference order (if files disagree)
1. `assets/study.css`: the source of truth for values
2. Screen **5** in `Study UI Screens.dc.html`: the task-screen reference
3. `Study UI Spec.dc.html`: tokens, states, layout budget, Dash hooks
4. `Study UI Style Spec.md`: the same spec in plain text
5. `Study UI Components.dc.html`: the component state sheet (`.is-hover`, `.is-focus`, `.is-selected` are preview-only classes; don't ship them)

## Screens
The ids match the badges in `Study UI Screens.dc.html`.

| id | Screen | Root classes |
|---|---|---|
| 1 | Consent: finalized .docx reproduced as a Letter sheet (Times New Roman), signature pad, date, printed name, "signed a paper copy" checkbox, Agree / Do not agree | `app app--deco` › `page page--desk` › `banner banner--static` + `sheet` |
| 2 | Declined | `app app--deco` › `page page--fill` › `stage` › `stage-col` |
| 3 | Participant ID + download consent copy | same as 2; `field`, `field-error`, `actions` |
| 4a / 4b | Instructions, first half (static / interactive wording) | same as 2 |
| 5 | **Task screen** (clickable: Practice/Q1–Q6, Static/Interactive) | see below |
| 6 | Practice complete (first half only) | same as 2 |
| 7a–7d | Post-part survey (static/interactive × first/second half); 7-point Likert; second half adds a comparison section | `app`, `.ui-*` scale tiles |
| 8 | Halfway break | `app app--celebrate` |
| 9a / 9b | Instructions, second half | same as 2 |
| 10 | About you (five steps, clickable, left section rail) | `app`, `.ui-*` tiles |
| 11 | Finished | `app app--celebrate` |
| S1 | Submit disabled after press | task screen, Submit `disabled` + `aria-busy="true"` |
| S2 | ID validation error | `field[aria-invalid=true]` + `field-error` |
| S3 | Consent could not be recorded | `msg msg-error` under the actions |
| S4 | Blocking "cannot save" message | `msg msg-block msg-block--system` |
| S5 | Line chart, View = "by coverage" | task screen; chips reorder, nothing else moves |

### Task screen (5): layout at 1440 × 900, measured
- **Header** `.appbar` 0–48: band `#EFE4DA`; title 18/700 with a 26 px cocoa icon tile (CSS only); step indicator `ol.steps` on the right (display only, not links).
- **Heading line** `.ui-head` 64–93: `p.position` (18/700 uppercase, .06em, muted) + `h1.question` (20/700, ink) on one baseline.
- **Card** `.ui-card.ui-card--task`, top 109, ends 802: white, radius 12, shadow `0 1px 2px rgba(36,28,24,.06), 0 8px 28px rgba(36,28,24,.06)`. Columns: 1082 px chart column + `minmax(0,1fr)` panel (310 at 1440, 252 at 1366).
- **Chart column** `.ui-main` (padding 14 / 16 / 12, gap 8):
  - Chart 123–643: exactly **1050 × 520**, fixed. Plotly margins in px.
  - Controls `.ui-controls` 653–752, interactive only, omitted on static charts:
    - Countries group `.ui-group.ui-group--grow` with legend `.ui-legend` ("COUNTRIES", 13/700 caps on the 1 px `#DDC8B8` border, radius 8). Two rows of chips `dcc.Checklist(className="chips ui-chips", labelClassName="chip")`, 30 px tall, with a flag (24 × 16, `.chip-flag`) and name. Line charts: `justify-content: space-between`.
    - View / Sort / Sort rows group `.ui-group.ui-group--fit`: stacked segmented control `dcc.RadioItems(className="seg ui-seg ui-seg--stack", labelClassName="seg-item")`. On line charts, `Show all` (`btn btn-quiet btn-xs`, 26 px) sits under it.
    - Map only: Highlight group, "Below [number] %" (`tb-inline`, `tb-num` 64 px).
  - Hint row `.ui-hint-row` 760–790: `p.tb-hint` (14 px muted) + Reset view (`btn btn-quiet btn-sm btn-reset`, 30 px, oat fill, undo icon).
- **Answer panel** `.ui-panel`: band `#EFE4DA`, padding 20, gap 12, takes the card's right corners.
  - Step 1 `p.ui-step.ui-step--nowrap` (21/700, 26 px cocoa number circle `.ui-step-n`): "Choose one year:" / "Choose one country:" / "Choose a range:" / "Choose one number:" / "Choose an answer:" (practice).
  - Tiles `dcc.RadioItems(className="ui-tiles", labelClassName="ui-tile")`: 2 columns, gap 8, 56 px, white, 1 px `#8F8076`, radius 6, 17/700 label (`.ui-tile-label`). Practice: "It stayed about level" spans both columns.
  - Step 2 `.ui-decide`: label `.ui-step` "In one sentence, describe why you chose your answer?", `dcc.Textarea(className="ui-textarea")` (18 px, flexes to fill), Submit `btn btn-primary btn-block` (44 px, cocoa `#5A4034`, white 18/700), then `msg msg-error`.
- **Compact** (window height ≤ 800, e.g. 1366 × 768 full screen): add `is-compact` to `.app` with a clientside callback. That gives header 44, page top 8, heading gap 8, and chart-column padding 8 / 6 with 6 px gaps. The card should end about 2 px above the 768 fold; confirm this in the browser.

Every question's copy, answer options, chart type, countries and hint text are in the `taskVals()` data (`T.A`, `HINT`, `SORT`) inside `Study UI Screens.dc.html`. Use them verbatim.

## Interactions and behaviour
- **Submit:** requires a tile choice and a non-empty sentence. On press, set `disabled` + `aria-busy="true"` (fill `#91796E`). Re-enable only if the step is refused. The label doesn't change, there's no spinner, and nothing moves. A refusal shows in `msg msg-error` under Submit.
- **Chips:** toggle a country's visibility. Selected = band pill with a ticked box and a 1 px raised shadow.
- **View / Sort:** reorders entities. On line charts, "by coverage" reorders the chips and the legend, and the layout doesn't move (S5).
- **Chart clicks:** clicking a line isolates it; clicking again or pressing Show all restores. Clicking a legend entry hides/shows; double-clicking shows only that one. Hover shows exact values (line charts also show change from the previous year).
- **Reset view:** undoes all filtering, sorting and isolating on the current chart.
- **Logging hooks:** controls carry `data-log` (`filter`, `sort`, `legend-isolate`, `threshold`, `reset`), `data-chart` (e.g. `q1-line`) and `data-value`. Keep these as the event-logging schema.
- **Participant ID:** Continue with an empty ID → `aria-invalid="true"` on the field and `field-error` (linked via `aria-describedby`, `role="alert"`): "Please enter your participant ID."
- **Consent:** a signature pad (`canvas.pad`, pointer events, Clear button appears after the first stroke) **or** the "signed a paper copy" checkbox. Save failure → the S3 message. The pending-approval banner (`banner banner--static`) must stay until approval.
- **Blocking failure** (responses can't be saved): replace the screen's content with S4.
- **Motion:** non-task screens only. Cards enter over 180 ms (fade + 6 px rise), and a slow 28 s background glow drifts on `app--deco` / `app--celebrate`. Task screens have no motion. Everything is off under `prefers-reduced-motion`.
- **Focus:** keyboard only (`:focus-visible`), a 2 px white gap + 2 px `#5A4034` ring on every control.

## State
Per participant: form (A/B), condition order (static/interactive first), current step (0–6 for the step indicator), question index, and per question: picked answer, justification, submit status (idle/busy/refused), chart view state (visible countries, sort, isolated line, threshold). The server must persist responses and interaction logs; a persistence failure triggers S4.

## Design tokens
See `study.css` `:root` and §1–3 of `Study UI Spec.dc.html`. Key values:
- Colour: page `#F8F3EE`, card `#FFFFFF`, band `#EFE4DA`, ink `#241C18`, muted `#5F544D`, accent `#5A4034`, accent-hover `#4A342A`, accent-busy `#91796E`, line `#8F8076`, line-soft `#E4D8CC`, group `#DDC8B8`, soft-hover `#E6D6C8`, disabled `#E6DDD4`, error `#C35600`, error-text `#A34700`. Chart series (Okabe–Ito, Cividis) are never used in the page chrome around the chart.
- Type: Helvetica, Arial, sans-serif; no web fonts. The consent sheet uses Times New Roman.
- Spacing: 4 · 8 · 12 · 16 · 24 · 32 · 48 (`--s-1`…`--s-7`).
- Radii: 6 controls, 8 groups, 12 cards, 999 pills, 50 % step numbers.
- Heights: button/field 44, tile 56, chip 30, Reset 30, Show all / segmented item / number input 26.

## Assets
- Flags: `https://flagcdn.com/w40/<iso2>.png` (mockup only). Bundle them locally for the study, since the stylesheet itself is designed to fetch nothing.
- The header icon and undo icon are inline CSS/SVG; no other image assets.
- Charts are placeholders; the real ones are Plotly figures.

## Known open items
- The Submit-while-saving fill `#91796E` gives white text about 3.9:1 contrast, which is below the WCAG 4.5:1 requirement for 18 px bold. Darken it if strict AA is needed.
- Confirm the compact 1366 × 768 fit in a real browser.

## Files
- `assets/study.css`: the production stylesheet (the only one)
- `Study UI Screens.dc.html`: all screen mockups plus states S1–S5
- `Study UI Spec.dc.html`: tokens, control states, layout budget, Dash hooks
- `Study UI Components.dc.html`: component state sheet
- `Study UI Style Spec.md`: the plain-text spec
- `support.js`: runtime so the `.dc.html` files open in a browser (design-only)
- `screenshots/`: one 1440 px-wide PNG per screen and state, named by id (`05-task.png`, `S1-submit-disabled.png`, …). The capture doesn't render checked-checkbox ticks; in the live mockup, and in the app, the country chips start checked.
