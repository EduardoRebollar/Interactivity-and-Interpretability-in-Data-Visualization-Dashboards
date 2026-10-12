# Handoff: Vaccination coverage study — chart style (direction 4a)

## Overview
The visual style for the five chart types in the study (line, bar, scatter, heatmap, map), shown with Form A data. The same style is used in both conditions (static and interactive). Each chart is a 1050 × 520 card that fills the chart slot on the task screen (see `design_handoff_study_ui`, screen 5).

## About the design files
The files here are **design references built in HTML/SVG**, not production code. Recreate them in the study app's existing stack (Plotly Dash: `dcc.Graph` figures). `assets/chart-render-v3.js` draws every chart as an SVG string and is the exact source for every coordinate, colour and label below; read it when a value here is unclear.

Open `Study Chart Directions.dc.html` in a browser (it needs `support.js` and `assets/` next to it). The Tweaks panel has `turn4Scale` (colour scale; **blue is the chosen one**), `cvd` (colour-vision simulation, review only) and `showNotes`.

## Fidelity
**High-fidelity.** Final colours, type, sizes and positions. Match the screenshots.

## Precedence
1. This README and `screenshots/`
2. `Study Chart Directions.dc.html` + `assets/chart-render-v3.js`
3. Anything older. The project's `Chart Style Amendments (4a).md` is out of date (it describes printed heatmap values and an Africa-only map) and is not included.

## Screenshots (2×, 2100 × 1040)
- `01-line.png` — Line · T1, T6 and practice
- `02-bar.png` — Bar · T2
- `03-scatter.png` — Scatter · T3
- `04-heatmap.png` — Heatmap · T4
- `05-map-world.png` — Map · T5

## Shared card
- Card 1050 × 520, background `#FFFFFF`, no border. (The sheet adds a shadow `0 1px 2px rgba(36,28,24,.06), 0 8px 28px rgba(36,28,24,.06)`; on the task screen the card sits inside `.ui-card`, which already has it.)
- Title band 0–30: padding 4 / 16 / 0, title Helvetica 18 px bold, line-height 22, `#241C18`. Titles: line "DTP3 coverage, 2000–2024"; bar "DTP3 coverage, 2017"; scatter "DTP3 coverage, 2000 and 2024"; heatmap "DTP3 coverage, selected years"; map "DTP3 coverage, 2013".
- Chart area 30–492 (1050 × 462).
- Source line at 502 (10 px gap), 12 px, line-height 16, `#5F544D`, one line, padding-left 16, verbatim: "Source: WHO/UNICEF coverage estimates (WUENIC), via Our World in Data. These are estimates; how reliably coverage is measured varies by country."
- No subtitle or reading line under the title.
- Font: Helvetica, Arial, sans-serif; tabular numerals.
- Type: 13 px everywhere except heatmap (15 px) and scatter dot names (11.5 px).
- Axis numbers and country names in **medium weight (500)**. The SVG mock fakes it with a 0.45 px stroke in the text colour; use real `font-weight: 500` where the font supports it.
- Colours: axis text and axis lines `#4A3F38`; names `#241C18`; secondary text `#5F544D`; gridlines `#BBAEA4` 1 px; soft edge `#E4D8CC`; no-data land `#EEE8E2`.
- Axis lines 1 px, left and bottom only. No top/right frame.
- Line, bar and scatter: fixed 0–100 axes at **4 px a point** (plot is 400 px tall).
- Y-axis numbers carry "%". Axis titles carry no unit. The y title sits horizontally, left-aligned at x 16 (scatter: x 246), 24 px above the 100% label.

### Plot rectangles in card coordinates (for Plotly margins on a 1050 × 520 figure)
Plot top y 68 (= 100%), bottom y 468 (= 0%), so `margin.t = 68`, `margin.b = 52` on line, bar and scatter.
- Line: x 52 → 846 → `margin.l = 52`, `margin.r = 204` (name tags live in the right margin)
- Bar: x 52 → 1026 → `l = 52`, `r = 24`
- Scatter: x 290 → 690 (square 400 × 400) → `l = 290`, `r = 360` (key in the right margin)
If you draw title and source in Plotly instead of HTML, keep them at the positions above.

## Line (practice, T1, T6)
- X: 2000 at the y axis (x 52), 2024 at x 846. Tick labels 2000, 2005, 2010, 2015, 2020, 13 px medium `#4A3F38`, 18 px below the axis. X title "Year" right-aligned at the axis end, same baseline. Vertical guides at 2005, 2010, 2015, 2020 (1 px `#BBAEA4`).
- Y: gridlines every 10 (10–100), labels "0%"…"100%" every 10, right-aligned 8 px left of the axis, vertically centred. Title "Coverage".
- Series: 2.5 px lines, round joins/caps, a 2.6 px-radius dot at every year in the series colour. Gaps (null years) break the line.
- End of each line: 4.6 px-radius dot with a 2 px white ring, then a 1.4 px curved leader in the series colour to a name tag.
  - Leader: cubic Bézier from (xEnd + 6, yEnd), controls (tagX − 4, yEnd) and (xEnd + 14, yTag), to (tagX, yTag). tagX = 860.
  - Tag: 20 px tall, fully rounded (rx 10), white fill, 1 px `#E4D8CC` edge; a 4 px-radius colour dot at tagX + 10; name at tagX + 19, 13 px medium `#241C18`, 7 px right padding. No value in the tag.
  - Tags are sorted by end value and spread so centres are ≥ 23 px apart (`spread()` in `chart-render.js`).
  - "Central African Republic" → "Central African Rep."
- Series colours (by position in the T1 data): Brazil `#0072B2`, China `#D55E00`, Ethiopia `#009E73`, India `#CC79A7`, Indonesia `#960600`, Nigeria `#062AA8`, Pakistan `#246648`, Ukraine `#845472`. Practice and T6 reuse a country's T1 colour; new countries (World, Central African Republic) take the first unused colour in that list.
- No legend.

## Bar (T2)
- 10 countries in alphabetical order, 2017: Afghanistan 64, Brazil 83, China 99, Ethiopia 65, India 89, Kenya 81, Mali 77, Nigeria 55, Pakistan 75, Vietnam 94.
- Slot = 974 / 10; bar width = min(62% of slot, 64 px). Tops rounded 6 px, square base (Plotly `marker.cornerradius = 6`).
- One colour per bar: line-chart countries keep their line colour; Afghanistan `#B07A00`, Kenya `#2C8DBF`, Mali `#7A5C00`, Vietnam `#5E5E9E`.
- Country names centred under bars, 13 px medium `#241C18`, 18 px below the axis. No values on bars.
- Y axis as the line chart (gridlines and labels every 10, title "Coverage").
- "Countries in alphabetical order" right-aligned at x 1026, same baseline as the y title, 13 px regular `#5F544D`.
- Check: Afghanistan/Ethiopia, Pakistan/Mali and Kenya/Brazil are 1–2 points apart, under the 5-point gap the T2 acceptance rule assumes.

## Scatter (T3)
- Square plot 400 × 400: x = coverage in 2000, y = coverage in 2024, both 0–100.
- Gridlines every 25 both ways; tick labels "0%", "25%" … "100%" (13 px medium). Y title "Coverage in 2024" at x 246; x title "Coverage in 2000" at x 718 on the x tick baseline.
- Diagonal y = x, 1.5 px `#5F544D`, dash 6 5. "No change" (13 px regular muted) centred on it at (16, 16), rotated −45°, on a white knockout 20 px tall so the line breaks around it.
- Corner labels (13 px medium, centred): "Coverage rose ↑" at (12.5, 95) in `#0F3F78`; "Coverage fell ↓" at (87.5, 4) in `#6E1D20`.
- Dots: 9 px (r 4.5), no outline, coloured by change (2024 − 2000) in seven steps:
  - > +40 `#0F3F78` · +20 to +40 `#1C5FAF` · +5 to +20 `#3A80CF` · −5 to +5 `#8E8781` · −5 to −20 `#D9473F` · −20 to −40 `#A3262C` · < −40 `#6E1D20`
- Each dot is named beside it, 11.5 px medium `#241C18`, 8 px from the dot centre, vertically centred. Default side is right; left for Niger, Ethiopia, Nigeria, Central African Rep., Madagascar, Kenya, Tanzania (Form A) and Nepal, Iraq, India, Philippines (Form B); Bangladesh (Form B) sits above.
- Each dot + name sits on a white knockout 20 px tall (from 9 px behind the dot to 5 px past the text), so gridlines and the diagonal stop before it. Draw order: grid → axes → diagonal → knockouts → names → dots. In Plotly, annotations with `bgcolor="#FFFFFF"` give the same effect.
- No legend. Stepped key on the right instead:
  - x 820 (card), top = plot top + 58 px. Title "Change since 2000" 16 px above, 13 px medium `#4A3F38`.
  - Seven bands 20 × 36 px, top to bottom the blues, grey, reds (order as listed above), 2 px gaps, outer ends rounded 6 px.
  - Boundary labels at x + 30, on the boundaries: "+100%", "+40%", "+20%", "+5%", "−5%", "−20%", "−40%", "−100%" (13 px medium `#4A3F38`; true minus sign).
  - Names at x + 80, 13 px medium ink: "↑ Coverage rose" (centre of band 1), "Little or no change" (band 4), "↓ Coverage fell" (band 7).
- Data: Form A = 16 African countries, Form B = 16 Asian countries (`SC4`, `SCB` in `chart-render-v3.js`).
- Check: naming dots removes T3's legend lookup, and the darkest blues mark the largest rises, which bears on "which country improved the most". The key's % values are percentage-point changes.

## Heatmap (T4)
- 8 rows A–Z (Burkina Faso, Cambodia, Central African Rep., Chad, India, Indonesia, Mali, Pakistan) × 6 columns (2000, 2005, 2010, 2015, 2020, 2024).
- All heatmap text 15 px.
- Cells: grid x 215 → 995 (130 px columns), chart-area y 88 → 462 (row height 46.75), 4 px gaps, 4 px corners. **No values printed in cells.**
- Column headings: years, 15 px medium `#4A3F38`, centred, 9 px above the grid. "A–Z" 15 px regular muted, right-aligned over the row names.
- Row names 15 px medium ink, right-aligned 12 px left of the grid.
- Nine colour bands: 0–20, then every 10 points to 90–100 (a value v falls in the band whose lower bound ≤ v). Colours (blue scale, evenly spaced, darkest = lowest): `#0A2347` `#0A386D` `#084E92` `#0F67B3` `#2781CE` `#489CE2` `#6FB7F1` `#99D1FC` `#CCE9FF`.
- Missing value: `#EEE8E2` cell with "No data" (15 px muted).
- Key centred above the grid: "Coverage" (15 px medium, right-aligned 12 px left of the bar), then a 560 × 16 bar of nine 62.2 px blocks, 2 px gaps, rx 5 clip, 1 px `#BBAEA4` outline. Labels on the boundaries below it: "0%", "20%", "30%" … "90%", "100%" (15 px medium).
- Check: two cells in the same band look identical (say 82% and 87%), coarser than the scale T4 was designed around.

## Map (T5)
- The world on an **Equal Earth** projection, Antarctica removed. Projected paths are precomputed in `assets/world-geo.js` (`GEO_W`, drawn at scale 3.95, offset (16, 34) in the chart area). In Plotly: `geo.projection.type = "equal earth"`, no frame, no Antarctica.
- 165 countries coloured by 2013 coverage in seven bands; 11 with no 2013 value stay `#EEE8E2`.
- Strokes: a 2 px `#BBAEA4` coast outline under all land; 1 px white between no-data land; 1.25 px white borders between coloured countries.
- No country names (most are too small).
- Band colours (blue scale): < 40 `#0A3569` · 40–50 `#08498A` · 50–60 `#095EA9` · 60–70 `#1A75C3` · 70–80 `#54A5E8` · 80–90 `#9ED4FD` · ≥ 90 `#CCE9FF`.
- Stepped key at x 890 (chart area), top 78: "Coverage" 16 px above (13 px medium). Seven blocks 22 × 26, rx 4, 5 px gaps, highest band at the top. Labels at x + 32: "100%" at the top edge, "90%"…"40%" in the gaps, "0%" at the bottom edge (13 px medium `#4A3F38`). Then a "No data" block 14 px below: `#EEE8E2` fill, 1 px `#BBAEA4` edge, label 13 px regular muted.
- 50% is a band boundary, so T5's count is the two darkest bands.
- Check: map values come from the raw OWID file (`coverage.csv` holds only the study's countries). The four countries below 50% (Central African Rep., Chad, Nigeria, Somalia) are small at world scale. The Q5 task-screen mockup in `design_handoff_study_ui` still shows the Africa map; this world map replaces it.

## Colour scale
Blue is final (`RAMPS.blue` in `chart-render.js`, 10 stops built in OKLCH, monotonic lightness, no yellow):
`0 #0A2347 · .111 #0A3569 · .222 #08498A · .333 #095EA9 · .444 #1A75C3 · .556 #348DD8 · .667 #54A5E8 · .778 #78BDF4 · .889 #9ED4FD · 1 #CCE9FF`
Heatmap bands are sampled evenly along it; map bands use stops 1, 2, 3, 4, 6, 8, 9. Teal, warm and cividis exist for review only.

## Interactions
Out of scope here; this bundle is visual style only. Interaction, controls and logging are in `design_handoff_study_ui/README.md`. Interactive charts must look identical to static ones at rest.

## Data used in the mock
`assets/chart-data.js` (`DATA.line`, `DATA.bar`, `DATA.heat`), plus in `chart-render-v3.js`: `LINE_EXTRA` (World, Central African Republic for practice/T6), `BAR4` (adds Afghanistan, Kenya, Mali), `SC4`/`SCB` (scatter, [2000, 2024]). World map values: `GEO_W.values`. In the app, read from the study's data files; these values only show what the mock draws.

## Files
- `Study Chart Directions.dc.html` — the chart sheet (needs `support.js`)
- `assets/chart-render-v3.js` — renderer for all five charts (`render(chart, cvd, {ramp})`, `card(chart, opts)`)
- `assets/chart-render.js` — shared helpers, series colours, colour scales
- `assets/chart-data.js`, `assets/world-geo.js`, `assets/africa-geo.js` — data and projected geometry
- `screenshots/` — the five charts at 2×
