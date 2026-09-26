# Vaccination coverage study — UI style spec

Implementation: put `assets/study.css` (the only stylesheet) in the Dash `assets/` folder. Everything below is already encoded there; class names in `code`. Mockups: `Study UI Screens.dc.html` (screen 5 is the task-screen reference); states: `Study UI Components.dc.html`; full spec: `Study UI Spec.dc.html`.

## Colour
| Token | Hex | Use | Contrast |
|---|---|---|---|
| page | `#F8F3EE` | page ground, segmented track | — |
| card | `#FFFFFF` | cards, tiles, inputs, chart ground | — |
| band | `#EFE4DA` | header, answer/action panel, chips, selected fill | — |
| ink | `#241C18` | text | 16.7 on white · 13.4 on band |
| muted | `#5F544D` | labels, helper text | 7.3 on white · 5.9 on band |
| accent | `#5A4034` | primary button, step numbers, selected edge, focus ring, links | white on it 9.5 |
| accent-hover | `#4A342A` | primary hover | white on it 11.6 |
| accent-busy | `#91796E` | Submit while saving (`aria-busy="true"`) | white on it 3.9 (bold 18 px) |
| line | `#8F8076` | tile / input / button edges | 3.8 on white · 3.0 on band (non-text) |
| group | `#DDC8B8` | legend-group outline (decorative) | — |
| line-soft | `#E4D8CC` | dividers | — |
| soft-hover | `#E6D6C8` | soft button hover | — |
| disabled | `#E6DDD4` | disabled fill (muted text 5.5) | — |
| error | `#C35600` | error edges, "!" icon, banner fill | 4.5 on white |
| error-text | `#A34700` | error text | 6.0 on white |
Chart series colours are not used in the chrome.

## Type (Helvetica, Arial, sans-serif)
| Role | Size / weight | Line height |
|---|---|---|
| Heading line — label | 18 px bold, uppercase, .06em | 1.3 |
| Heading line — heading | 20 px bold | 1.3 |
| Step heading (`.ui-step`) | 21 px bold, 26 px circle with 14 px number | 26 px |
| Tile label | 17 px bold (`.ui-tile-label`), tabular numbers | 1.2 |
| Body / prose | 18 px regular | 1.55, max 64ch |
| Panel text | 16 px | 1.5 |
| Helper (`.ui-help`) | 15 px, muted | 1.45 |
| Chart hint, legend | 14 px (hint) · 14 px bold uppercase .06em (legend) | 1.3 |
| Buttons | 18 px bold (primary/soft) · 15 px regular (sm/xs) | — |
| Textarea | 18 px | 1.45 |
| Consent sheet | Times New Roman 19 px | 1.25 |

## Spacing scale
4 · 8 · 12 · 16 · 24 · 32 · 48 px (`--s-1`…`--s-7`).
- Page padding 16 top, 24 sides (16 below 1400 px wide), 32 bottom.
- Heading line → card: 16 (8 in compact mode).
- Card main: 14 / 16 / 12 (task) · 28 / 32 / 32 (other screens). Panel: 20.
- Gaps: tiles 8, chips 6, groups 24, stacked questions 28, panel items 12.

## Radii
Controls, tiles, inputs 6 px · legend groups 8 px · cards 12 px (panel takes the card's right corners) · chips, stepper pill 999 px · step numbers 50 %.

## Shadows and focus
- Card: `0 1px 2px rgba(36,28,24,.06), 0 8px 28px rgba(36,28,24,.06)`
- Raised pill (current step, selected segment/chip): `0 1px 2px rgba(36,28,24,.12)`
- Focus ring (all controls): `0 0 0 2px #FFFFFF, 0 0 0 4px #5A4034`, via `:focus-visible`.

## Control heights
Primary / soft button 44 · text input 44 · tile 56 (text tile 48, scale tile 64) · chip 30 · segmented item 22 in a 2 px track · Show all 26 · small button 30 · stepper item 30.

## Layout
- Header (`.appbar`): 48 px band; icon tile 26 px accent + title 18 px bold; stepper right.
- Task screen (screen 5): `.ui-card.ui-card--task` = fixed chart column 1082 px (1050 chart + 2×16) + `.ui-panel` `minmax(0,1fr)` (310 px at 1440, 252 at 1366). Inside `.ui-main`: the chart (1050 × 520) first, then `.ui-controls` (omitted on static/scatter/heatmap charts), then `.ui-hint-row`.
- Compact (window height ≤ 800, i.e. 1366 × 768 full screen): add `.is-compact` to `.app` → header 44, page top 8, heading gap 8, chart column padding 8 / 6 and gaps 6. The card ends ≈2 px above a 768 fold; see Study UI Spec §5.
- Other screens: short screens `.ui-short` (960 px centred) + `.ui-card.ui-card--short` (min 300 px). Wide screens (About you, survey) span the page. Consent: `.ui-card--consent`, 400 px panel with sticky `.ui-panel-inner`.

## Components
- **Stepper** `ol.steps > li.is-done | li.is-current[aria-current=step] | li`. Display only.
- **Legend group** `.ui-group > .ui-legend`. Legend background must match what's behind the border (`--legend-bg`).
- **Numbered step** `.ui-step > .ui-step-n`; sub-line `.ui-step-sub`.
- **Option tile** `dcc.RadioItems(className="ui-tiles", labelClassName="ui-tile")`; `ui-tiles--pns` makes the last option ("Prefer not to say") full width and muted; `.ui-tile--text`, `.ui-tile--scale`, `.ui-scale--7/9`.
- **Controls strip** `.ui-controls` under the chart: `.ui-group.ui-group--grow` (Countries), `.ui-group.ui-group--fit` (View / Highlight), then `.ui-hint-row` with `.tb-hint` and Reset view (`.btn.btn-quiet.btn-sm.btn-reset`).
- **Chips** `dcc.Checklist(className="chips ui-chips", labelClassName="chip")`; flag + name in `.chip-name` / `.chip-flag`.
- **Segmented** `dcc.RadioItems(className="seg ui-seg ui-seg--stack", labelClassName="seg-item")`.
- **Buttons** `.btn.btn-primary.btn-block` (panel foot, `.ui-push`), `.btn.btn-soft` (secondary), `.btn-sm`, `.btn-xs` (Show all). Submit while saving: `disabled` + `aria-busy="true"`.
- **Inputs** `.field`, `.ui-textarea` (flex-fills the panel), labels `.ui-label`.
- **Errors** `.field-error` under a field, `.msg-error` under an action, `.ui-group.is-error` / `.ui-tile.is-error`, `.ui-alert` for blocking, `.msg-block.msg-block--system` for "cannot save", `.banner.banner--static` for pending approval.

## States (none rely on colour alone)
| | Hover | Selected | Focus | Disabled | Error |
|---|---|---|---|---|---|
| Tile | accent edge, oat fill | filled radio + 2 px accent edge + band fill | ring | dashed edge, grey fill, muted, not-allowed | 2 px error edge + "!" message |
| Chip | oat fill + edge | checkbox ticked, band fill, raised | ring | grey fill, dashed feel, muted | — |
| Segment | ink text | bold + raised band pill | ring | struck through | — |
| Button | darker fill | — | ring | grey fill, muted text | — |
| Input | accent edge | — | accent edge + ring | grey fill | 2 px error edge + "!" + text, `aria-invalid` |
