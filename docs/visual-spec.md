# Visual specification

Source of truth for every visual decision in the dashboard. **Change this document first, then the
code.** The values here are mirrored in `src/config.py` and enforced by `tests/test_palette.py` and
`tests/test_conditions.py`.

Both study conditions use these values identically. A visual change applies to both conditions or to
neither — that is the methodological premise of the whole study, so a difference in appearance
between static and interactive is a defect, not a variation.

Status: **settled, 2026-09-15.** Every section is decided and built. Amended 2026-09-22 (end-label
spacing, §6). **Amended 2026-09-23 for the redesigned task bank** (`docs/study-design.md` §4): five
chart types instead of one (§1), eight series colours instead of five and a sequential scale (§4),
labelling by chart type (§6), and the bar sort, the map's coverage range and the modebar (§7).
**Amended 2026-09-25 for the redesign** (`docs/design-handoff/`, `docs/study-redesign.md`): a fixed
1050 × 520 chart (§5), a legend on line charts beside the end labels (§6), controls under every chart
with a heatmap row sort and a typed map highlight in place of the range (§7), and the page chrome
around the chart (§10). **Amended 2026-10-11:** the scatter draws sixteen dots, so its eight colours
are used twice each and every dot has its own marker shape (§4, §6). **Amended again 2026-10-11 for
the chart handoff** (`docs/chart-handoff/`): every chart restyled; the line chart's legend gives way
to name tags; the scatter names its dots and colours them by change, in place of the legend and the
shapes; a colour per bar; nine and seven blue bands in place of Cividis; the map shows the whole
continent and names its countries (§1–7, §10). A change to any of §1–8 or §10 needs this document
edited first, then the code.

**The chart handoff sets the look, not the content (2026-10-11).** `docs/chart-handoff/` (its README,
`screenshots/`, `africa map.png` and `scatterplot.png`) draws Form A's five chart types to fix the
visual style. Which countries, years and forms each chart shows is `docs/study-design.md` §4. Form
B, T6 and the practice follow the same style, applied here. Where the handoff and this document
differ, this document says so and why. The handoff's world map (`05-map-world.png`) was not taken:
T5 stays on Africa (§1).

---

## 1. Chart forms

Each task names one chart type (`flow.Task.chart`) and the years it shows (`Task.years`). There is
one figure builder per type, and none takes an `interactive` argument (§7).

| Type | Items | Encoding |
|---|---|---|
| Line | T1, T6, practice | Coverage over 1985–2024 (2000–2024 until 2026-10-12), one line per entity, a name tag at each line's end; World dashed where shown (only the practice draws it; T1 and T6 draw eight countries each) |
| Bar | T2 | One year's coverage, one bar per country in the listed order, each in its country's colour |
| Scatter | T3 | Each country a named dot: coverage in 2000 across, in 2024 up, coloured by its change, with a dashed no-change diagonal |
| Heatmap | T4 | Countries down, years across (2000, 2005, 2010, 2015, 2020, 2024), coverage as one of nine colour bands |
| Map | T5 | One year's coverage as one of seven colour bands on the African countries the item names, each named on the map |

Every chart is one 1050 × 520 figure holding its own title and source line (§5).

**Line.** Multi-series, x year 1985–2024 (linear, integer ticks every five years from 1985, the
last labelled 2020), y coverage. Lines 2.5 px with round joins and caps, and a dot of radius 2.6 px
in the line's colour at every observed year. Markers are not decoration: after a gap, a lone
observation with no neighbours draws no line segment at all, and without a marker it would silently
vanish. A line's last point is a 4.6 px dot with a 2 px white ring, joined to its name tag (§6).
Vertical guides every five years from 1990 to 2020, drawn as shapes on the axes so a zoom clips
them to the plot; none stands at 1985, which the handoff leaves to the axis line. No legend (§6).

**Drawn from 1985 (2026-10-12, Eduardo; 2000–2024 until then),** so the Years slider (§7.6) has
years to set aside. Every line item still asks about 2000 onward (`docs/study-design.md` §4). 2000
is drawn like any other year, with a guide and a tick label like 1990's: a mark of its own would
point at the questions' window in both conditions and do part of the slider's work. A year is 20 px
wide where it was 32. The acceptance rule's floors are in years and points, so they still hold,
but each year a static reader places is 38% narrower.

**One departure from the handoff: the x axis runs from 1984.6 to 2024.4**, where the handoff puts
the first year on the y axis and 2024 at the plot's right edge. Plotly clips markers at the plot's
edge, so the first dot and the ringed end dot (5.6 px to the ring's outer edge) would be cut. The
margin is 8 px. It was a quarter year from 2026-10-11 (1999.75–2024.25). Drawn from 1985 a
quarter year is 5 px, which would cut the ring, so since 2026-10-12 it is 0.4 year
(`config.LINE_X_PAD`). A marker drawn unclipped would spill into the margins as soon as the
participant zoomed. Reset axis restores 1984.6–2024.4 (§7.5).

**Bar.** Vertical bars, one per country, each in its country's colour (§4) and named under it. Tops
rounded 6 px (`marker.cornerradius`), the base square; a bar is 62% of its slot, at most 64 px wide.
No value on a bar. The y axis is the line chart's. "Countries in alphabetical order" stands at the
top right and names the order the bars stand in (§7.2).

**Scatter.** A square 400 × 400 plot. Both axes run 0–100 on **one scale** (`scaleanchor`), so the
diagonal is a true 45° line of no change and the distance above it is the improvement. Gridlines
every 25 points. The diagonal is a shape, 1.5 px in the muted text colour, dashed 6 5, with "No
change" on it at (16, 16), turned −45°, on a white knockout so the line breaks around it. "Coverage
rose ↑" stands at (12.5, 95) and "Coverage fell ↓" at (87.5, 4), each in its end colour of the change
scale (§4). No hover on the diagonal.

Dots are 9 px, unoutlined, **coloured by their change** from 2000 to 2024 in seven steps (§4), and
**named beside them** (§6). Each name sits 8 px from its dot's centre, to the right unless that would
collide, on a white knockout 20 px tall that runs from just behind the dot to 5 px past the name, so
gridlines and the diagonal stop short of it. The side is set per form, as the handoff sets Form A's
(left for Niger, Ethiopia, Nigeria, the Central African Republic, Madagascar, Kenya and Tanzania;
in Form B left for Nepal, Iraq, India and the Philippines, and above for Bangladesh). Draw order:
grid, axes, diagonal, knockouts, names, dots. No legend: a stepped key stands in the right margin
(§4). **Dots are never clipped at the plot's edge (2026-10-11).** Plotly clips a marker to the axes
by default, and B-T3's Oman sits at 99, 99.

**Heatmap.** Rows in the task's order, the first at the top. Columns are categories, so 2020–2024
takes the same width as the other five-year steps. Cells 130 px wide and 46.75 px tall, with 4 px
white gaps and 4 px rounded corners, so two adjacent cells of one band stay two cells. Plotly cannot
round a heatmap's cells, so the cells are drawn as shapes, and the heatmap trace beneath them,
fully transparent, carries the hover; its tooltips are every chart's white card (§7.1), edged in
the cell's band. **No number is written in a cell**: that would give the
static condition the exact value (§7). A cell with no value is `#EEE8E2` and reads "No data" (§3).
Row names right-aligned 12 px left of the grid, years 9 px above it, and "A–Z" over the row names
naming the row order (§7.2). The key is centred above the grid (§4).

**Map.** A choropleth on Plotly's Africa scope (Mercator) at 110m resolution, framed on the whole
continent, Madagascar included (2026-10-11, the handoff's `africa map.png`; it was cropped at
26°N). The countries an item names are coloured in seven bands (§4) and **named on the map**, 10 px
bold: inside the country where the name fits, in white on the four darkest bands and in ink on the
rest (whichever reads better, as the handoff picks), and otherwise beside it, on a 1 px ink leader from a 2 px dot. "Central African Republic" is
written "CAR" and "Democratic Republic of Congo" "DR Congo". Each form sets its own placements.
Every other country is plain land (§4). The handoff's key carries a "No data" block for that land;
this one does not, because those countries do report coverage and are only outside the question,
and no item's country lacks a value (`docs/study-design.md` §4). **No land but Africa is drawn**
(2026-10-12, Eduardo): Plotly's Africa file fills only Africa, but its coastline also traced Spain,
Italy, Greece, Turkey and Arabia across the top of the frame. The coastline is now the land's own
outline, so it runs round Africa and nowhere else, Sinai's land border included. The geometry is
Plotly's own file with that one change, served from `src/assets/geo_africa.js` (written by
`scripts/vendor_map_geometry.py`) rather than fetched from Plotly's CDN in each participant's
browser mid-task. The figure is unchanged: the outline is in the geometry, so both conditions draw
it alike.

## 2. Axes

| Property | Value | Reason |
|---|---|---|
| Coverage axis (line and bar y; both scatter axes) | **fixed 0–100, never auto-scaled** | An axis that rescales between tasks or conditions changes how steep a trend or how tall a bar looks. That would confound interpretation accuracy with axis framing. |
| Colour bands (heatmap, map, scatter) | **fixed** (§4) | For the same reason: a scale fitted to the data would give the same colour to different values on different tasks. A value's band depends on the value alone. |
| Line x range | 1985–2024 (2000–2024 until 2026-10-12) | The scope's years. Drawn from 1985 so the Years slider has years to set aside; every line item asks about 2000 onward (§1). |
| Coverage ticks | every 10 on the line and bar charts; every 25 on both scatter axes | Every 10 is fine enough to estimate against without hover, coarse enough to stay readable. The scatter's dots are named and coloured by change, so its grid only places them. |
| Tick labels | "0%" … "100%", right-aligned 8 px left of the y axis; years and percentages 18 px below the x axis | As the handoff draws them. |
| Axis titles | no unit, horizontal, left-aligned 24 px above the 100% label: "Coverage" (line, bar), "Coverage in 2024" (scatter y). "Year" and "Coverage in 2000" stand at the x axis's end, on the tick labels' baseline. | Read before the axis, not along it. |
| Colour-key labels | on the band boundaries | So 50% is marked, the threshold T5 asks about. |
| Axis lines and tick labels | `#4A3F38`, 10.20:1, lines 1 px, left and bottom only | Well above the 4.5:1 text floor. No frame on the top or right. |
| Gridlines (line, bar, scatter) | `#BBAEA4`, 2.16:1, 1 px | See §4 — a documented exemption. |
| Names and years on category axes | no gridlines | The categories are labelled; a grid would add nothing. |

Only the line chart's x axis can be zoomed (§7.5). Every other axis, and the map, are fixed.

## 3. Missing data

**Gaps render as gaps.** `connectgaps=False`, always. A line that bridges a NaN invents data that was
never reported, and gaps can be part of what participants interpret.

**RESOLVED (2026-09-15) — a caption, shown in both conditions.** A participant seeing nothing where a
line should be may reasonably conclude coverage was *zero* rather than *unrecorded*. In the
interactive condition a tooltip could say so; in the static condition it cannot.

The caption below the chart names every series with unreported years among those the chart shows —
`layout.gap_note`, e.g. *"No data reported for: United Kingdom (2000–2018). A break in a line means
the value was not reported, which is not the same as zero coverage."* On the other chart types the
second sentence names what is missing instead: a bar, a dot, a cell, or a country's colour.

It appears in **both** conditions, which is what makes it admissible: interactivity must not change
what information is available, only how it is reached. It sits directly under the chart, above the
interactive condition's controls, so it is in the same place in both.

**One chart shows a gap, A-T1, since 2026-10-12.** The line charts are drawn from 1985, and
Ukraine, A-T1's falling line, reports DTP3 only from 1992 (it was part of the USSR). Its line
starts there, and A-T1 carries the caption *"No data reported for: Ukraine (1985–1991)"* in both
conditions. Every other line on every line chart reports every year from 1985. The acceptance rule
still refuses a missing bar, dot, cell or country, and a named line missing any year a question asks
about (`docs/study-design.md` §4). Until 2026-10-12 no chart showed a gap.

Enforced by `tests/test_app.py::test_gap_note_names_the_series_with_unreported_years`.

## 4. Color

Every ratio below is **measured** by `src/contrast.py`, not estimated. Regenerate the tables with
`uv run python scripts/check_contrast.py`. Floors come from WCAG 2.1 AA: 4.5:1 for text, 3:1 for
graphical objects.

Background: `#FFFFFF`.

### Series colors (floor 3:1)

Colour tells lines apart on the line charts, and bars apart on the bar chart (below). **Assigned by
country, not by position (2026-10-11, the chart handoff).** Each of Form A's T1 countries owns one
colour, in the table's order, and keeps it on every line chart and bar chart it appears on. Any other
country on a line chart takes the first colour that chart does not already use: on B-T1, Nepal takes
4 and Uganda 8; on the practice, Myanmar takes 1. T6 draws eight lines since 2026-10-11, so each
chart uses every colour: on A-T6 Afghanistan takes 1, the Central African Republic 2, Chad 4, Côte
d'Ivoire 5, DR Congo 7 and Somalia 8; on B-T6 Benin takes 1, Gabon 2, Ghana 3, Guinea 4, Kenya 5,
Mozambique 6 and Sudan 8 (until 2026-10-12, Cameroon 2, Gabon 3, Kenya 4 and Madagascar 5; the
named pair's colours did not move). Since 2026-10-12 Gabon stands on A-T1 where Nigeria stood
(`docs/study-design.md` §4) and takes 6, Nigeria's colour, as the one A-T1 leaves unused. Nigeria
keeps 6 on B-T1 and A-T6, so no other chart changes. A hidden line keeps its colour, so filtering
never recolours (§7.3). The scatter
no longer uses these colours: its dots are coloured by change (below).

| Order | Country | Hex | Ratio | Luminance | Note |
|---|---|---|---|---|---|
| 1 | Brazil | `#0072B2` | 5.19:1 | 0.152 | Okabe-Ito blue, unmodified |
| 2 | China | `#D55E00` | 3.87:1 | 0.222 | Okabe-Ito vermillion, unmodified |
| 3 | Ethiopia | `#009E73` | 3.42:1 | 0.257 | Okabe-Ito bluish green, unmodified |
| 4 | India | `#CC79A7` | 3.06:1 | 0.293 | Okabe-Ito reddish purple, unmodified |
| 5 | Indonesia | `#960600` | 9.04:1 | 0.066 | dark red, added 2026-09-23 |
| 6 | Nigeria | `#062AA8` | 11.03:1 | 0.045 | royal blue, added 2026-09-23 |
| 7 | Pakistan | `#246648` | 6.84:1 | 0.103 | forest green, added 2026-09-23 |
| 8 | Ukraine | `#845472` | 6.01:1 | 0.125 | mauve, added 2026-09-23 |

Reference series (World): `#000000`, 21.00:1, dashed. Black and dashed so it reads as a baseline
rather than as one more competing country. The chart handoff draws World as one more series colour;
that was not taken (2026-10-11), for this reason.

### Why eight, and how they were chosen (2026-09-23)

The task bank's isolation items draw eight countries and World, which five colours cannot do.
Eduardo chose to extend the palette rather than trim the charts.

Contrast on white does not say whether two colours can be told **apart**, so the extension measured
that too. `src/contrast.py` simulates colour-vision deficiency (Machado, Oliveira and Fernandes 2009,
severity 1.0, i.e. dichromacy) and measures CIEDE2000 between every pair. It is checked against the
published test pairs of Sharma, Wu and Dalal (2005).

That measurement exposed a defect in the old palette. Okabe-Ito orange, darkened to `#9C6C00` to
pass contrast, was **1.1 ΔE from vermillion under simulated protanopia** — the same colour.
Darkening had removed the lightness difference protanopes separate those two by. It was dropped.

The four new colours were chosen by search. Every candidate was at least 3:1 on white, at least
0.02 in luminance from every other colour, and at least 20 ΔE from the black World line. Among
those, the search kept the four that hold every pair furthest apart under normal vision,
deuteranopia and protanopia.

| Vision | Weakest pair | ΔE2000 | Floor |
|---|---|---|---|
| Normal | reddish purple / mauve | 19.8 | 12.0 |
| Protanopia | blue / reddish purple | 12.2 | 12.0 |
| Deuteranopia | forest green / mauve | 14.7 | 12.0 |
| Tritanopia | blue / forest green | 12.1 | reported only |

The weakest pair under the red-green deficiencies is two unmodified Okabe-Ito colours, so no
extension of those four could do better. Red-green colour-vision deficiency affects about 1 in 12
men, and the palette is held apart under its most severe forms. Tritanopia affects about 1 in
10,000 people and is reported, not held to the floor. **Colours are also
separated in luminance** (minimum gap 0.021, floor 0.02). An earlier palette darkened three swatches
to one contrast target, and they came out luminance-identical.

**The palette is in `config.SERIES_COLORS` in this order.** Every pair of the eight clears the
floor, so any set of them does, whichever countries a chart draws. `tests/test_palette.py` holds the
contrast floor, the luminance gap, the ΔE floor (`config.MIN_CVD_DISTANCE`) and the distance from
World.

Colour is never the only channel for a series, whatever the palette (§6).

### Bar colours (2026-10-11, the chart handoff)

One colour per bar, by country. A country with a series colour keeps it. Every other bar country
has its own colour, held to the same floors as the series colours on each chart it appears on: at
least 3:1 on white, and **every pair of bars on one chart at least 12 ΔE2000 apart** under normal
vision, deuteranopia and protanopia. A chart is ten bars: A-T2's five countries without a series
colour are Afghanistan, Guinea, Kenya, Mali and Vietnam, and B-T2's seven are Algeria, Cameroon,
Colombia, Egypt, Mali, Mozambique and the United States.

When T2 moved to MCV1 (2026-10-11, `docs/study-design.md` §4), A-T2 swapped Brazil's bar for
Guinea's and B-T2 Cambodia's for Algeria's. Each newcomer takes the colour of the bar it replaced,
Guinea Brazil's series blue and Algeria Cambodia's violet, so each chart carries exactly the set of
colours measured below. Guinea draws no line, so it never meets Brazil on a chart.

- **The handoff's four extra colours are not kept.** Its Afghanistan, `#B07A00`, is 1.1 ΔE from
  China's vermillion under protanopia, the defect that removed the old orange from the palette
  (above). Its Vietnam is 3.5 from Brazil's blue on the same chart, and its Mali is 6.0 from
  Indonesia's dark red on B-T2.
- **No exemption is needed.** A search over sRGB found ten-colour sets for both charts with every
  pair at least 12.2 ΔE apart on A-T2 and 12.6 on B-T2. The luminance gap is not held: with ten
  colours, A-T2 has no room for it between 3:1 and the darkest series colour. Saturation (C*) is held
  between 30 and 70, so no bar reads as grey, the colour of land with no question attached, or as
  neon. Contrast is held between 3:1 and 10:1. Where the handoff gave a colour, the search took the
  nearest that passes; the rest are the furthest from every other bar on their chart.

| Country | Hex | Ratio | Chart | Handoff's |
|---|---|---|---|---|
| Afghanistan | `#705000` | 7.40:1 | A | `#B07A00` |
| Guinea | `#0072B2` | 5.19:1 | A | (Brazil's series colour) |
| Kenya | `#0098E8` | 3.15:1 | A | `#2C8DBF` |
| Mali | `#108078` | 4.79:1 | A, B | `#7A5C00` |
| Vietnam | `#683860` | 9.04:1 | A | `#5E5E9E` |
| Algeria | `#A080F8` | 3.03:1 | B | (Cambodia's, until 2026-10-11) |
| Cameroon | `#C06000` | 4.27:1 | B | |
| Colombia | `#703040` | 9.61:1 | B | |
| Egypt | `#1070A8` | 5.38:1 | B | |
| Mozambique | `#30A0A8` | 3.13:1 | B | |
| United States | `#A84848` | 5.70:1 | B | |

  They are `config.BAR_COLORS`, and `tests/test_palette.py` holds each T2 chart to the floors.

The name under each bar identifies it (§6), so colour is never the only channel there either.

### Change scale (scatter, 2026-10-11)

Each dot is coloured by its change from 2000 to 2024, in seven steps: three blues for a rise, grey
within 5 points, three reds for a fall. A dot exactly on a boundary takes the step nearer zero.

| Step | Change | Hex | Ratio |
|---|---|---|---|
| 1 | more than +40 | `#0F3F78` | 10.49:1 |
| 2 | +20 to +40 | `#1C5FAF` | 6.35:1 |
| 3 | +5 to +20 | `#3A80CF` | 4.06:1 |
| 4 | −5 to +5 | `#8E8781` | 3.54:1 |
| 5 | −5 to −20 | `#D9473F` | 4.27:1 |
| 6 | −20 to −40 | `#A3262C` | 7.31:1 |
| 7 | less than −40 | `#6E1D20` | 11.29:1 |

Every step clears 3:1 on white. Adjacent steps are 10.9–27.2 ΔE apart in normal vision, and 7.9 at
the least under protanopia (steps 6 and 7). **Exempt from the 12 ΔE floor**, like the sequential
scale below: the change is also the dot's height above the diagonal, and the name beside the dot,
not its colour, says which country it is. The key labels the boundaries in percentage points,
"+40 pts" to "−40 pts", with "+100 pts" and "−100 pts" at the ends: the handoff writes "%", and the
difference between two percentages is points (§7.1).

**A consequence for T3.** The darkest steps mark the largest rises, the very quantity T3 asks about.
The key never stands alone in its step: in Form A Niger (+52) shares the darkest blue with Burkina
Faso (+46) and Ethiopia (+43); in Form B India (+36) shares step 2 with Pakistan (+28), Cambodia
(+24) and Nepal (+23). `docs/study-design.md` §4 makes that a rule.

### Sequential scale (heatmap and map, 2026-10-11)

A blue scale, ten stops built in OKLCH with lightness rising at every stop and no yellow (the
handoff's `RAMPS.blue`, replacing Cividis): `#0A2347`, `#0A3569`, `#08498A`, `#095EA9`, `#1A75C3`,
`#348DD8`, `#54A5E8`, `#78BDF4`, `#9ED4FD`, `#CCE9FF`. **Dark is low coverage**, as the prompts say.
Neither chart blends it: each draws **bands**, so a cell or country takes one flat colour and is
matched to a stepped key.

| Heatmap band | Hex | | Map band | Hex |
|---|---|---|---|---|
| 0–20 | `#0A2347` | | under 40 | `#0A3569` |
| 20–30 | `#0A386D` | | 40–50 | `#08498A` |
| 30–40 | `#084E92` | | 50–60 | `#095EA9` |
| 40–50 | `#0F67B3` | | 60–70 | `#1A75C3` |
| 50–60 | `#2781CE` | | 70–80 | `#54A5E8` |
| 60–70 | `#489CE2` | | 80–90 | `#9ED4FD` |
| 70–80 | `#6FB7F1` | | 90 and over | `#CCE9FF` |
| 80–90 | `#99D1FC` | | | |
| 90–100 | `#CCE9FF` | | | |

A value falls in the band whose lower bound it reaches. The heatmap's nine are sampled evenly along
the scale; the map's seven are stops 1, 2, 3, 4, 6, 8 and 9. Lightness rises at every band in normal
vision and under deuteranopia, protanopia and tritanopia. Each band boundary moves lightness by 9.4–
9.8 L* on the heatmap and by 8.3–17.4 on the map; adjacent bands are at least 7.2 ΔE apart on the
heatmap and 6.6 on the map, under any of normal vision, deuteranopia and protanopia. `docs/study-design.md` §4 rests T4's and
T5's colour floors on these numbers. Two values in one band look identical (82% and 87% on the
heatmap), which no item turns on: T4's and T5's keys sit at least a band clear (§4 there).

**DELIBERATE EXEMPTION from the 3:1 floor**, like the gridline. The light end is 1.26:1 on white.
No sequential scale can put every step at 3:1 on white and still span enough lightness to read a
difference in. No cell or country is *found* by its colour:

- heatmap cells sit on a grid labelled by country and year;
- map countries are separated by white borders and named on the map.

What must hold instead is enforced: **white borders and gaps reach 3:1 against every band below
50%**, the dark countries T5 asks participants to count and the dark cells T4 asks about. The least
is 5.82:1, the heatmap's 40–50 band; on the map it is 9.01:1. (`AXIS_COLOR` borders were rejected
on 2026-09-23: against the darkest fill two adjacent dark countries, such as CAR and Chad, would
merge.)

**The keys.** The heatmap's sits centred above the grid: "Coverage", then a 560 × 16 bar of nine
62.2 px blocks with 2 px gaps, rounded 5 px at its ends, outlined 1 px in the gridline colour, with
"0%", "20%", "30%" … "100%" on the boundaries below it, 15 px. The map's stands at the right: seven
blocks 22 × 26 px, rounded 4 px, 5 px apart, the highest band at the top, "100%" at the top edge,
"90%" … "40%" in the gaps and "0%" at the bottom edge, 13 px. The scatter's is the map's shape,
seven 20 × 36 px blocks 2 px apart with the outer ends rounded 6 px, titled "Change since 2000",
with "↑ Coverage rose", "Little or no change" and "↓ Coverage fell" beside blocks 1, 4 and 7. All
three keys are drawn into the figure, so both conditions have them.

| Map element | Colour |
|---|---|
| Coloured countries | the seven map bands |
| Every other country | `#EEE8E2`, plain land, 1 px white borders |
| Borders between coloured countries | `#FFFFFF`, 1.25 px |
| Coastline | `#BBAEA4`, the gridline colour, 2 px, under all land; Africa's outline only (§1) |
| Countries hidden by a chip, or not below the highlight (interactive, §7.3–7.4) | same colour, opacity 0.15 |

### Text and structure

| Role | Hex | Ratio | Floor |
|---|---|---|---|
| Primary text (names, titles) | `#241C18` | 16.74:1 | 4.5:1 |
| Muted text (source, "No change", order labels) | `#5F544D` | 7.34:1 | 4.5:1 |
| Axis lines and tick labels | `#4A3F38` | 10.20:1 | 4.5:1 |
| Validation error | `#C35600` | 4.51:1 | 4.5:1 |
| Gridline | `#BBAEA4` | 2.16:1 | **exempt** |
| Name-tag edge | `#E4D8CC` | 1.40:1 | **exempt**: decorative; the tag's name carries it |
| Plain land, empty heatmap cell | `#EEE8E2` | 1.22:1 | **exempt**: a surface, never a mark |

The chart's text colours are the page chrome's ink and muted tokens since the chart handoff
(2026-10-11), with a warm axis and gridline to match (§10).

**The error colour is UI chrome, not a series colour.** It never appears on a chart, so it does not
count against `MAX_SERIES` and needs no separation from the palette. It is derived from the
vermillion series colour by `contrast.darken_to_ratio`, which scales all three channels equally and
so preserves the hue. The vermillion itself is 3.87:1 — above the 3:1 graphic floor that applies to
a 2.5px line, below the 4.5:1 floor that applies to text.

**The gridline exemption is deliberate and recorded.** No grey reaches 3:1 against white while still
reading as a gridline rather than as data. `#BBAEA4` is darker than a typical default because the
static condition has no hover, so participants estimate values against the grid. The values are
carried by tick labels at 10.20:1. `config.GRIDLINE_EXEMPT` makes the exemption explicit, and a test
fails if the gridline ever drifts too faint to use (< 1.8:1).

## 5. Typography and dimensions

| Property | Value |
|---|---|
| Family | Helvetica, Arial, sans-serif; tabular numerals |
| Base | 14 px |
| Title | 18 px bold, line height 22 px |
| Axis labels, names, name tags, scatter and map keys | 13 px, medium (below) |
| Heatmap text, all of it | 15 px |
| Scatter dot names | 11.5 px, medium |
| Map country names | 10 px bold |
| Source line | 12 px, line height 16 px, muted |
| Line width | 2.5 px |
| Line marker radius | 2.6 px; the end dot 4.6 px with a 2 px white ring |
| Scatter marker size | 9 px |
| Heatmap cell gap | 4 px |
| Chart size, every type | 1050 × 520 px, fixed (2026-09-25) |

**Fixed at 1050 × 520 (2026-09-25).** The figure's own layout sets the width, and `dcc.Graph` is not
responsive, so the chart is the same size on every screen and in both conditions. Margins are in
pixels.

**The card (2026-10-11, the chart handoff).** The figure holds three bands, all drawn in it so both
conditions have them by construction:

- **Title**, 0–30 px: padded 4 px at the top and 16 px at the left. "{vaccine} coverage, 1985–2024"
  on line charts (2000–2024 until 2026-10-12), "{vaccine} coverage, {year}" on the bar chart and the map, "{vaccine} coverage,
  2000 and 2024" on the scatter, "{vaccine} coverage, selected years" on the heatmap, where
  {vaccine} is the item's: MCV1 on T2 and T4 since 2026-10-11, DTP3 elsewhere. No subtitle.
- **Chart**, 30–492 px.
- **Source line**, at 502 px, 16 px from the left, on one line: "Source: WHO/UNICEF coverage
  estimates (WUENIC), via Our World in Data. These are estimates; how reliably coverage is measured
  varies by country."

The line, bar and scatter plots run from 68 px (100%) to 468 px (0%), 400 px tall, so one coverage
point is 4 px, which the acceptance rule's floors rest on (`docs/study-design.md` §4). Margins:

| Chart | Left | Right | Top | Bottom | Plot width |
|---|---|---|---|---|---|
| Line | 52 | 204 (the name tags) | 68 | 52 | 794 px, 33 px a year |
| Bar | 52 | 24 | 68 | 52 | 974 px, ten 97.4 px slots |
| Scatter | 290 | 360 (the key) | 68 | 52 | 400 px, square |

**Medium weight.** Axis numbers and names are drawn at weight 500. Helvetica and Arial have no 500
on most participants' computers, so the browser would draw them regular. The handoff draws the
weight as a 0.45 px stroke in the text's own colour; the app draws the same as a text shadow a
quarter of that each way (`figures.medium`), set in the figure's fonts, so both conditions carry
it by construction.

**Tabular numerals** come from one rule in `src/assets/zz-overrides.css` on the chart's SVG text:
Plotly's fonts have no setting for them. Both conditions load the stylesheet.

**Margins are fixed, not grown.** Plotly widens a margin to fit its tick labels unless told not to,
which moved the line plot 5 px off the handoff's place (measured in Chrome); every figure turns
that off.

**The chart's size is reserved from the moment a task screen appears (2026-09-16), in both
conditions.** Plotly is loaded on demand, the first time a chart is drawn in a session. Until it
arrives, `dcc.Graph` renders at zero height, so the question, answers and Submit first appeared
directly under the prompt and then jumped 520 px down about 600 ms later — long enough for a click
to land on the wrong option. A fixed-height container around the chart holds the space.

## 6. Series limits and labelling

- **At most 8 lines on one chart**, World not counted, and **at most 16 dots on a scatter**
  (2026-10-11). Bars take their countries' colours (§4); heatmap rows and map countries use the
  blue bands; scatter dots the change scale. Only lines are capped by the palette.
- **Colour is never the only channel identifying a series.** Each chart type carries a second one:

| Type | Identity carried by |
|---|---|
| Line | a name tag at the line's end, joined to it by a leader in its colour |
| Bar | the country name under the bar |
| Scatter | the country name beside its dot |
| Heatmap | the country name on each row |
| Map | the country name on the map, and its place |

- **Name tags (2026-10-11, the chart handoff; they replace the 2026-09-22 end labels).** Each tag is
  a white pill 20 px tall, fully rounded, with a 1 px `#E4D8CC` edge, at x 860; inside it, a 4 px dot
  in the line's colour and the name, 13 px medium ink, 7 px from the right end. No value. A 1.4 px
  leader in the line's colour, a cubic Bézier from 6 px right of the end dot to the tag's left end,
  joins them ("Central African Republic" is written "Central African Rep.", and "Democratic Republic
  of Congo", since A-T6 drew it on 2026-10-11, "DR Congo", as on the map). World's tag is drawn the
  same way.
- **Tags never overlap.** They keep the order of their lines' last reported values and are spread
  so their centres are at least **23 px** apart, by the handoff's `spread()`, between 10 px above
  the plot's top and 4 px above its bottom. The spread is computed in `build_figure`, which takes no
  `interactive` argument, so both conditions get identical tags. Tags are placed in paper
  coordinates vertically, because Plotly does not draw an annotation whose data coordinate lies
  outside its axis range (on 2026-09-23 China's label on A-T1 never appeared, found in headless
  Chrome).
- **No legend on line charts (2026-10-11, the chart handoff).** The legend of 2026-09-25 stood to the
  right of the end labels; the handoff gives that margin to the name tags. Both its jobs are done
  elsewhere: the tags identify lines for every reader, and in the interactive condition the chips
  hide and show lines and a click on a line focuses it (§7.3).
- **The scatter names its dots (2026-10-11, the chart handoff).** Its legend and the sixteen marker
  shapes chosen earlier that day are gone: every dot is a circle, named beside it (§1) and coloured
  by its change (§4). The static reader no longer matches a dot to a legend entry, which changes
  what T3 costs without hover (`docs/study-design.md` §4). The colour-and-shape table is in the git
  history.

**RESOLVED (2026-09-15) — the same fixed set per task, in both conditions.** If interactive
participants could reach entities that static participants could not, interactivity would be
changing *how much data is reachable* as well as *how it is worked with*. Each task names its own
fixed entity set, both conditions see it, and no control reaches an entity the static condition
cannot see (`docs/study-design.md` §3).

The World reference is excluded from the line filter (`layout.filterable`), and has no chip: it is
the baseline the lines are read against, and switching it off would remove part of what the
question is about.

Enforced by `tests/test_conditions.py::test_the_task_screen_opens_on_the_same_chart_in_both_conditions`,
for every task.

## 7. Condition differences

The **only** permitted difference. Everything in §1–6 is identical across conditions.

| | Static | Interactive |
|---|---|---|
| `staticPlot` | `True` | `False` |
| Hover tooltips | none | every chart: the value; on lines, also the change from the year before |
| Country chips | none | every chart: show or hide each country drawn |
| Line charts | image | Years (a range slider), Show all, focus a line, zoom and pan the x axis |
| T1 only | image | four more, unannounced: Coverage, Order, Regions, Show (§7.7) |
| Bar chart | image | Sort: A–Z, High → low, Low → high |
| Scatter | image | the key's colours: a click highlights the dots in that band |
| Heatmap | image | Sort rows: A–Z, Lowest cell first, Highest cell first; the key's colours highlight cells |
| Map | image | the key's colours: a click highlights the countries in that band |
| Every chart | none | a hint row saying what the chart can do, and Reset view |

The line chart's hint named its legend. From 2026-10-11 it read "Click a line to show only that
country; click it again to bring the others back." Since 2026-10-12 it reads "Hover a line to read
its values. Click a line to focus on it; click it again to bring the others back." The pilot's
participant asked whether the line chart gave exact values: every other chart's hint named hover,
and the line chart's did not. A click now fades the other lines rather than hiding them (§7.3).

Plotly is interactive by default, so a plain `dcc.Graph` would leave the static condition hoverable
and zoomable and the manipulation would be invalid. `staticPlot: True` is what makes "static"
actually static.

**The chart itself is identical.** Every difference above is either a Plotly config flag or a control
rendered *under* the chart. Nothing in this table adds, removes or restyles a mark at rest.
`build_figure` takes no `interactive` argument, and `tests/test_conditions.py` proves both conditions
open on byte-identical figure JSON for every task. Once a control is used, it changes the chart only
through a view function that hides, reorders or fades what is already there (`figures.set_visible`,
`sort_bars` and their 2026-09-25 companions for rows, fades and the highlight). T1's extra controls
(§7.7) also zoom the coverage axis, re-placing the name tags for it, and turn off the points or the
name tags. They too act only on what is drawn, and only after a participant uses them. Two labels name an
order and follow it when a sort changes it: the bar chart's "Countries in alphabetical order" and the
heatmap's "A–Z" (§7.2). At rest each reads as in both conditions.

**No click lands while the chart is being redrawn (2026-10-12).** Every control goes through one
callback, and Dash keeps only the newest reply to it: a reply still on its way when the next
control fires is dropped, and the next is worked out from the view before the first. The log has
already recorded the first by then, so the chart, the controls and the log could disagree. A full
session in headless Chrome found it on the heatmap, whose redraw then took over a second: Reset
view straight after a sort and a key click did nothing and logged nothing. Two fixes, the same day:
- the heatmap draws its cells in one step, so it redraws in about 0.1 s, as the other charts do;
- while Dash marks the chart as updating, the controls, the key's buttons, Reset view and the
  chart take no pointer events (`zz-overrides.css`). Nothing changes on screen.

The keyboard is not held: two controls changed from the keyboard within that tenth of a second can
still meet the old view.

**The controls sit under the chart (2026-09-25).** The controls strip and the hint row come after
the chart and the gap caption, and exist only in the interactive condition, so the chart is at the
same place on the page in both conditions (§10).

### 7.1 Year-over-year change (defined 2026-09-15)

A signed change against the previous year, as a **third line in the line chart's hover tooltip**:

```
India
2017: 82%
+3 pts vs 2016
```

| Case | Text |
|---|---|
| Previous year reported | `+3 pts vs 2016` / `-7 pts vs 2015` |
| Previous year equal | `no change vs 2016` |
| Previous year unreported | `no 2018 value reported` |
| First year on the chart | `first year shown` |

- **In the tooltip, not on the chart.** A drawn glyph would have to be present in one condition and
  absent in the other. The tooltip text sits in *both* figures; `staticPlot: True` simply means a
  static participant never fires a hover to read it.
- **"pts", not "%".** The difference between two percentages is percentage points.
- **Deltas are computed from the rounded values the tooltip displays.**
- **No delta is invented across a gap.**

The other chart types' tooltips carry the value (bar, heatmap, map), or both values (scatter), and
the country's name. Like the change line, they are in both conditions' figures.

**Every tooltip is one white card (2026-10-12).** White fill, ink text at 14 px, the name bold
after a dot in the mark's colour, a 1 px edge in the same colour, no pointer arrow, and a soft
shadow (`zz-overrides.css`). The change line is muted ink at 13 px. The mark's colour is the line's,
the bar's, the dot's change step, or the cell's or country's band. Plotly's default filled each
tooltip with the mark's colour, and no one text colour reaches 4.5:1 on every band (white and ink
are both about 4.1:1 on 50–60), so the text sits on white and the colour moves to the edge and the
dot. The dot and edge repeat what the name already says, so the pale bands' weak contrast against
white hides nothing. Plotly cannot round a tooltip's corners. The card is set in the figure, so it
is in both conditions' figures, and the shadow rule matches nothing in the static condition, which
draws no tooltip.

### 7.2 Sorting (defined 2026-09-15; bars added 2026-09-23)

**A line chart has no sort (since 2026-10-12).** A time-series line chart has no meaningful row
order: the x axis is time and the lines are where the data puts them. Until 2026-10-12 a **View**
control (`as listed` / `by coverage`) reordered the chips, by each entity's most recently reported
value, and never the chart. It moved nothing on the chart, and the first pilot session found it had
no purpose. The Years slider took its place (§7.6). Chip labels carry no value (2026-09-25).

**On the bar chart, sorting moves the bars** (2026-09-23). A bar chart's x axis has no order of its
own, so reordering it changes no meaning: each bar keeps its colour, its label and its height.
Control: **Sort**, `A–Z` (the listed order, which is alphabetical), `High → low`, `Low → high`
(three options since 2026-09-25). A bar with no value sorts last either way. The label at the
chart's top right says the order (2026-10-11): "Countries in alphabetical order", "Countries by
coverage, highest first" or "Countries by coverage, lowest first".

**On the heatmap, sorting moves the rows** (2026-09-25), for the same reason: its rows are names,
not a scale. Control: **Sort rows**:
- `A–Z`, the listed order;
- `Lowest cell first`: each row's lowest cell, lowest first;
- `Highest cell first`: each row's highest cell, highest first.

Ties keep the listed order, and a row with nothing reported sorts last. Each row keeps its cells and
its label; no cell changes colour. The label over the row names says the order: "A–Z", "Lowest
cell first" or "Highest cell first".

The options are named as their order labels are, since 2026-10-12. Until then they were `Default`,
`Lowest value` and `Average` (each row's mean, lowest first). The first pilot session found that
sort unclear, and of no use on B-T4, which asks for the highest cell (`docs/study-design.md` §4).
Average answered neither form's question.

### 7.3 Filtering and line isolation

- **Chips on every chart (2026-09-25).** One chip per country the chart draws, with its flag, in
  the task's entity order. World has none.
- **At most six chips to a row (2026-10-12).** The rows are as even as the count allows, the first
  taking any extra:
  - 16 run 6/5/5 (T3);
  - 18 run 6/6/6 (T5);
  - 10 run 5/5 (T2);
  - 8 run 4/4 (T1, T4, T6).

  Until the map's Highlight box went (§7.4, later the same day), the map's ran five to a row: six
  beside the box wrapped at every window size (headless Chrome).

  A chip names its country as the chart prints it (`figures.drawn_name`): "CAR" and "DR Congo" on
  the map, "Central African Rep." and "DR Congo" elsewhere. Spelled out, "Democratic Republic of
  Congo" still wrapped form A's map row. The chip's value, which is what is logged, stays the full
  name.

  Until then there were always two rows, each wrapping on its own. The scatter's sixteen chips then
  stood in four ragged rows, which the first pilot session found awkward. Each row is its own
  checklist (`layout.chip_rows`).
- **Filtering hides; it does not rebuild the chart from a shorter list.** A rebuild would move
  every name tag, and before 2026-10-11, when colour went by position, it would also have recoloured
  the survivors.
  - A hidden **line or scatter dot** disappears (`visible="legendonly"`), and with it the line's end
    dot, leader and name tag, or the dot's name and knockout. The other tags stay where they are.
  - A hidden **bar, heatmap row or map country** fades to opacity 0.15, keeping its place, its
    colour and its name. A hidden row must not look like an empty cell, which means "not reported"
    (§3).
- The filter cannot empty the chart: the last country cannot be unchecked. On the practice chart
  that leaves one chip, Myanmar, which cannot be unchecked.
- **Focusing a line** (2026-10-12; until then, *isolating* it) is a click on the line itself.
  - Every other line fades to 0.15 opacity: its end dot, leader and name tag too. Each keeps its
    place and colour.
  - A faded line takes no hover and no click (`hoverinfo: "skip"`), so the closest-point tooltip
    cannot jump to it.
  - The chips stay as they are: nothing is hidden.
  - Clicking the focused line again releases it. So do *Show all*, which also shows every hidden
    line, a chip, and Reset view.
  - The World reference stays at full strength throughout and cannot itself be focused. A click on
    any other chart type does nothing.
  - **Why fade (pilot session 1):** a hidden line took its context with it, where the question is
    how one line relates to the others. Every other chart already faded rather than hid what a
    control set aside. An isolated line hid the others, and its chip alone stayed ticked.
- **Reset view**, on every chart, undoes filtering, sorting, focusing, a highlight from the key and,
  since 2026-10-12, a zoom: the line chart returns to 1985–2024, as first drawn. Until then a zoom was left to the
  modebar's own reset. The zoom is kept by the app, not by Plotly: every control redraws the chart,
  and each redraw keeps the range the participant zoomed to.
- All of it resets between tasks: no task inherits the previous task's view.

### 7.4 Highlighting from the key (defined 2026-10-12, replacing the map's highlight box)

On the scatter, the heatmap and the map, each block of the stepped key (§4) is a button, in the
interactive condition only.
- **A click highlights its band.** Every mark in another band fades to 0.15 opacity:
  - a scatter dot, with its name and knockout;
  - a heatmap cell (a single cell, not its row), with "No data" cells and their labels;
  - a map country.

  Each keeps its place and colour. A second click on the same block releases its band. Several
  bands may be chosen at once, and their marks show together. With none chosen, the chart is as
  drawn.
- **With the chips.** A mark is at full strength only if its chip shows it and, when bands are
  chosen, it is in one of them. A dot its chip hid stays hidden; a row or country its chip faded
  stays faded.
- **The buttons are an overlay, not the figure.** Native buttons stand over the key's blocks, inside
  the chart's own box, at the positions the figure draws the blocks (`figures.key_blocks`, one
  source for both). The figure carries nothing new, so it stays byte-identical in both conditions
  (§7). Their positions are inline styles set from that data, as the chips' spacing is (§10).
  - A pressed block carries a 2 px ink outline.
  - Keyboard focus shows the focus ring.
  - Each button is named by its band ("Highlight 40–50%", "Highlight +20 to +40 pts") and carries
    `aria-pressed`.
  - The heatmap's blocks are 16 px tall, so each button reaches 6 px above and below its block.
- **Drawn as the chips draw.** Dots and cells by opacity. Countries by **selection**: the countries
  at full strength are selected and the rest take the trace's `unselected` opacity, since plotly.js
  4 applies a choropleth's `marker.opacity` to the whole trace. Only a browser showed it, for the
  map's first filter.
- **Reset view** releases every band.
- **The hints** on these three charts name it: "Click a colour in the key to highlight its dots"
  (cells, countries).
- **Why (the first pilot session, 2026-10-12).**
  - The participant, on the scatter, wanted to click the key to filter.
  - On the map, they found the "Below [n] %" box "almost cheating": it echoed the question's own
    words.
  - The key names no threshold. 50 is one of its six boundaries, and a reader must work out which
    bands lie below it.
  - One mechanism now serves every chart with a key. Eduardo removed the map's box rather than keep
    both.
- **Before 2026-10-12** the map had a **Highlight** box, "Below [n] %", from 0 to 100, which faded
  every country at n or above. It replaced a range slider on 2026-09-25, and a preset "below 50%"
  button was rejected on 2026-09-23 for naming the threshold. The box's code is in the git history.

### 7.5 The modebar (defined 2026-09-23)

The interactive condition shows Plotly's modebar. Each figure lists the buttons it drops in its own
layout (`modebar.remove`), so the list is part of the figure and identical in both conditions; the
static condition shows no modebar at all.

- **Box and lasso select are removed from every chart.** They dim the unselected marks, which changes
  what is on screen, and no event records it. On the map they would also override the coverage
  range, which is drawn as a selection. They had been available on the line charts since those were
  built; they went with this amendment.
- **Zoom and pan are removed from the bar, scatter, heatmap and map**, whose views are fixed (§2);
  on the map, so are the map zoom buttons. The line chart's x axis still zooms, logged as
  `view_change`.
- **Download as PNG and Share chart are removed from every chart** (2026-09-27). Share chart uploads
  the chart to Plotly Cloud. The bar, scatter, heatmap and map therefore show no buttons at all.
- **The line chart shows Zoom in, Zoom out and Reset axis** (2026-09-27). Dragging across the plot
  still zooms, and so does a mouse wheel or a touchpad's two-finger scroll or pinch, in whichever
  direction the participant's system scrolls (`scrollZoom`, line charts only: over a fixed chart
  Plotly would still take the wheel, and the page could not be scrolled there). Each gesture is
  one `view_change`. Scroll zoom was off until this date, for fear of zooms made by accident while
  reading; the pilot should look for them. The Zoom and Pan mode buttons are gone.
- **Zoomed in, a sideways swipe moves the line chart's x axis** (2026-09-27): a touchpad's
  two-finger swipe, a tilt wheel, or Shift with the wheel, in the direction the participant's
  system scrolls (`assets/chart_pan.js`). It moves only within the chart's own view (1984.6–2024.4 since 2026-10-12; 1999.75–2024.25 from 2026-10-11)
  and does nothing when not zoomed in; over the plot it never scrolls the page or triggers the
  browser's swipe back. Each swipe is one `view_change`, logged once it pauses, like a wheel zoom. Reset axis is Plotly's "Reset axes", retitled
  in `graph_config` because only the x axis moves; it restores 1984.6–2024.4. Autoscale is removed:
  after a zoom it fits the axis to everything drawn, end labels included, and on the chart drawn
  from 2000 landed on 1998.4–2027.0 (measured in Chrome), which is not the chart's own view.
- **Zoomed in, the name tags and leaders stay where they are** (2026-10-11): they are drawn in paper
  coordinates and name where each line ends, in 2024, which a zoom may move out of view.
- **No chart has a legend** (2026-10-11, §6), so none has legend clicks.

**Consequence for task design:** static participants cannot read exact values; they estimate against
gridlines or a colour key. A task asking "what was Nigeria's DTP3 coverage in 2012?" therefore
measures whether hover exists, not interpretation ability. Every item must survive the reading
errors of a participant without hover — the acceptance rule in `docs/study-design.md` §4. This is a
study-design decision, recorded here because it follows directly from the visual spec.

### 7.6 The Years slider (defined 2026-10-12)

On every line chart, in the controls strip, where View stood. *Show all* sits under it.
- **Control:** **Years**, a range slider from 1985 to 2024 (2000 to 2024 until 2026-10-12), in
  whole years, its two handles at least a year apart. It starts at 1985–2024. It commits when a
  handle is let go, not while one is dragged. Marked every 13 years, 1985, 1998, 2011 and 2024, so
  both ends are marked and the marks are evenly spaced (every six years, 2000–2024, until
  2026-10-12). 2000 has no mark of its own, as it has none on the chart (§1).
- **What it does:** sets the x axis to the first year − 0.4 through the last + 0.4, the same
  margin as the chart's own view (1984.6–2024.4; ± 0.25 until 2026-10-12, §1). 1985–2024 is the
  chart as first drawn.
- **It follows every other zoom:** a drag across the plot, the wheel or touchpad, a sideways swipe
  (§7.5), and the modebar's Zoom in, Zoom out and Reset axis. It then shows the whole years inside
  the range (an axis zoomed to 2005.2–2015.8 reads 2006–2015).
- **Logged:** each change is one `view_change` with `control` `years`, `value` and `previous` as
  `[first, last]`. A zoom it follows is the chart's own `view_change`, as before.
- **Reset view** puts it back to 1985–2024 (§7.3).
- **Drawn from 1985 (2026-10-12, Eduardo).** Over 2000–2024 the slider could only narrow a chart
  that already showed everything a question asked about. The line charts now draw fifteen years
  before the questions' window. Setting the slider to start at 2000 sets those years aside
  (`docs/study-design.md` §4).
- **Why (the first pilot session, 2026-10-12):** View had no purpose (§7.2). Zoom was named nowhere
  a participant reads, sat in the modebar, and could not be reached from the keyboard. The slider
  makes the zoom a visible control under the chart, as every other control is, and its handles take
  the arrow keys. Eduardo's decision; zoom is named once in the instructions and nowhere else.

### 7.7 Question 1's extra controls (defined 2026-10-12)

T1, in both forms and in the interactive condition only, carries four controls no other chart has.
They sit in a second controls strip, under the first and above the hint row.
- **Why.** The supervisor asked, after the first pilot session, for at least one case where
  interactivity might be too much: a chart overloaded with controls it does not need. Eduardo chose
  to overload T1 rather than add an item (`docs/study-design.md` §4, T1).
- **Unannounced.** Neither the instructions nor T1's hint row name them (Eduardo). T1 is the only
  chart with controls the participant is not told about. Finding them is part of what T1 shows.

The four, each with its log event:
- **Coverage**, a range slider from 0 to 100% in steps of 5, its handles at least 10 points apart.
  - It zooms the y axis to the chosen range, so lines look steeper or flatter.
  - The name tags are placed again for the new scale: in the same order, spread as at rest, each
    leader starting from where its line ends inside the plot (clamped to the plot's edge when the end
    lies outside the range).
  - 0–100% is the chart as drawn. It commits when a handle is let go; no number boxes.
  - Logged as `view_change`, `control` `coverage`, `value` and `previous` `[low, high]`.
- **Order**, three radios: `A–Z` (the listed order), `Highest in 2000`, `Highest in 2024`.
  - They reorder the chips, never the lines, as View did (§7.2).
  - Not an order by change since 2000, which would rank the countries by how far they rose or fell.
    That hands over part of T1's rubric, and T1 stays in RQ1.
  - 2000, not 1985, though the chart starts there since 2026-10-12. 2000 is where T1's question
    starts, and Ukraine has no 1985 value to order by.
  - Logged as `sort_change`, `key` `alpha`, `start` or `end`, with direction `none`, `desc`, `desc`.
- **Regions**, four checkboxes: Africa, Asia, Americas, Europe.
  - A region is ticked while all its countries are shown. Unticking hides them all; ticking shows
    them all. The chips follow, and a region follows its chips.
  - A region with no country on the chart is disabled (Europe on B-T1), so both forms carry the
    same four.
  - The last countries on the chart cannot be hidden this way.
  - Logged as `filter_change`, `control` `region`, `action` `hide` or `show`, `value` and
    `previous` the countries shown.
- **Show**, two checkboxes, both ticked: `Points` (the dots on each line, the end dot with them)
  and `Name tags` (tags and leaders).
  - Unticking one hides it until it is ticked again.
  - Logged as `view_change`, `control` `display`, `value` and `previous` the parts shown.

All four follow the rules of the others:
- **What they change:** they act only on the chart as drawn, and never reach data the static chart
  lacks.
- **Order of drawing:** coverage zoom, then hiding, then focusing, then the Show toggles.
- **Reset:** Reset view undoes them, and every task starts fresh.
- **Keyboard:** slider handles take the arrow keys; radios and checkboxes are native.

## 8. Accessibility

- Contrast floors above are enforced by `tests/test_palette.py`, so an inaccessible palette fails the
  build rather than reaching a participant. So is the separation of the series and bar colours under
  simulated colour-vision deficiency (§4), and the blue bands' steady lightness under it.
- All controls are keyboard-operable (CLAUDE.md baseline):
  - the chips are native checkboxes, and Sort and Sort rows are native radios;
  - Show all, Reset view and the key's colours (2026-10-12) are native buttons;
  - Years' handles take the arrow keys (2026-10-12), as do T1's Coverage handles; T1's Order
    radios and Regions and Show checkboxes are native (§7.7).
- Focus rings appear only for keyboard focus (`:focus-visible`), as a 2 px white gap and a 2 px
  accent ring (§10).
- Hover and focusing a line are mouse-only. So were zoom and pan until 2026-10-12; Years now reaches
  them from the keyboard. A keyboard-only participant in the interactive condition therefore meets
  the scatter item with only the chips and the heatmap item with only the row sort. This is
  recorded in `docs/study-design.md` §10.
- Every mark is named: tags on lines, names under bars, beside dots, on rows and on the map. Colour
  is never the sole channel for a series (§6).
- Full screen-reader support is explicitly out of scope; nothing here should make it worse.

## 9. Open items

All earlier items are settled. They are kept, rather than deleted, so the reasoning survives into
the write-up.

1. ~~§3 — how "not reported" is communicated, given the static condition has no tooltip.~~
   **Resolved 2026-09-15:** a caption in both conditions. See §3.
2. ~~§6 — whether both conditions show the same entity set.~~
   **Resolved 2026-09-15:** the same fixed set per task; controls operate only within it. See §6.
3. ~~Continent aggregates have no 2024 data.~~ **Resolved:** no task uses a continent at all, and
   `tests/test_tasks.py::test_no_task_depends_on_a_continent_in_2024` fails the build if one ever
   does.
4. ~~More than five series.~~ **Resolved 2026-09-23:** eight colours, measured under simulated
   colour-vision deficiency, with the scatter's second channel in marker shape. See §4 and §6.
5. ~~More than eight scatter dots.~~ **Resolved 2026-10-11:** the colours repeat in pairs and every
   dot has its own shape. **Superseded the same day** by the chart handoff: every dot is named and
   coloured by its change. See §6.

Nothing in §1–8 is open. A change to any of it needs this document edited first, then the code.

## 10. Page chrome (defined 2026-09-25)

Everything around the chart: the header, the stepper, the cards, the answer panel, the controls
strip, the buttons and the short screens. It is identical in both conditions except the controls
strip and the hint row under the chart (§7).

- **Source of truth: the design handoff's stylesheet**, `docs/design-handoff/assets/study.css`,
  copied unchanged to `src/assets/study.css`, where Dash loads it automatically. Where Dash's markup
  cannot match one of its selectors, the smallest possible rule goes in `src/assets/zz-overrides.css`,
  each commented with why. No inline style dicts in `layout.py`, beyond the data-driven values the
  handoff sets inline itself (the chips' spacing on line charts) and, since 2026-10-12, the key
  buttons' positions, which come from the figure's own key geometry (§7.4).
- **Dash 4's option lists (2026-09-26).** The stylesheet puts a class on each option's `<label>`
  (`.chip`, `.ui-tile`, `.seg-item`). Dash 4 cannot: its labels are `.dash-options-list-option`,
  and `labelClassName` goes on the text beside the input. `src/assets/zz-bridge.css`, generated from
  `study.css` by `scripts/bridge_stylesheet.py`, copies every such rule with its selector re-aimed at
  Dash's label inside the list that carries the handoff's list class (`.chips`, `.ui-tiles`, `.seg`),
  declarations untouched; a test holds it to the stylesheet. `dcc.Input` puts its class on a box
  around the input, so the number box's and the ID field's states (focus, the invalid mark, the
  placeholder) are read through that box. Dash's own accent colour and focus outlines are
  overridden in `zz-overrides.css`.
- **The short screens (2026-09-26).** Declined, the participant ID, the instructions, practice
  complete, the break and the finish: one white card centred on the page. The instructions scroll:
  their approved wording runs past a 790 px window on every version but 9a (accepted by Eduardo,
  2026-09-26; they are untimed). The handoff's Screens
  file centres their copy and sizes it screen by screen with inline styles (21 to 26 px, against
  the stylesheet's 20); those values are classes in `zz-overrides.css` (`copy-21` to `copy-26`,
  `id-row`), so `layout.py` still sets no style. The ID field's "ID:" is a `<label>`, where the
  handoff hides it from screen readers, so the field has a name. An empty ID marks the field
  `aria-invalid` and links it to the message under it (S2); a database refusal leaves it
  unmarked.
- **The consent sheet (2026-09-26).** The handoff's screen 1: the pending-approval banner, then the
  form as a Letter sheet in Times New Roman, built from the text `consent.py` hashes, and signed
  inside the sheet: the pad, the date and the printed name on one black rule with the form's
  labels under them, the paper-copy box, then "I agree" and "I do not agree" at full width, with a
  refusal (S3) under them. Its inline styles are classes in `zz-overrides.css`, like the short
  screens'. "Clear signature" appears after the first stroke. **One departure:** the pad keeps its
  canvas's proportions, 600 × 150 (120 px tall at the sheet's width), where screen 1 squeezes it
  to 74 px, which would have stretched the signature 1.6 times on the signed copy; the handoff's
  S3 draws the pad at its proportions. A text field's focus ring is drawn on dcc.Input's box
  alone, and the date field's on any focus, since Chrome never gives a date input
  `:focus-visible`.
- **S4, when nothing can be saved (2026-09-26).** The screen's content is replaced by the
  handoff's blocking message, announced, on the plain ground, under the position label of the
  screen it replaced (a task's "Question k of 6"); the header and stepper stay. The stores keep
  what was written, so a reload shows the stage again, with the researcher at hand.
- **The survey and About you (2026-09-26).** The handoff's screens 7 and 10: a band-coloured rail
  (title, intro, skip note, the sections with their progress) beside one question per page, with
  Back and Next, and Continue on the last page. Every page is on the screen and only shown or
  hidden, in the browser, so answers stay put and nothing reaches the server before Continue.
  Paas, which the handoff lacks, is the first page, on a 9-point version of the same scale. Its
  inline styles are classes in `zz-overrides.css`. Three departures, all invisible at rest: the
  text box beside "Other" is laid over that option's cell rather than inside its label, since
  Dash cannot read a field nested in an option; the rail's buttons get a focus ring, which the
  handoff's `all: unset` removes; and when Next or Back disappears or goes dead under the
  keyboard, focus moves to the button that replaces it.
- **Two palettes, one ink (amended 2026-10-11).** The chart's text uses the chrome's ink `#241C18`
  and muted `#5F544D`, as the chart handoff draws it, with a warm axis `#4A3F38` and gridline
  `#BBAEA4` (§4). The rest of the chrome's colours (the stylesheet's `:root` tokens: oat page
  `#F8F3EE`, band `#EFE4DA`, cocoa accent `#5A4034`, error `#C35600` and the rest) are never used
  inside the chart, and the series, bar, change and blue colours (§4) are never used in the
  chrome.
- **Contrast.** Every chrome pair the stylesheet uses is measured with `src/contrast.py` and held to
  the §4 floors by `tests/test_palette.py`. One deliberate exemption: Submit's fill while saving,
  `#91796E`, gives white text about 3.9:1. The button is disabled at that moment, and WCAG 1.4.3
  exempts inactive controls.
- **Layout of the task screen.** A header band with the title and the stepper; the position label
  and the question on one line; one card holding the chart column (the 1050 px chart plus 16 px each
  side) and the answer panel. Under the chart: the gap caption (§3), then, in the interactive
  condition only, the controls strip and the hint row. Submit sits above the fold of a 1440 × 900
  laptop with a one-line question. **Scrolling accepted (Eduardo, 2026-09-26):** on a window 790 px
  tall or less, the interactive scatter and map cards run past the fold (at 1366 × 768 the
  scatter's by 42 px, the map's by 30–66), so a participant scrolls to Submit there. The question
  wraps under the position label, and the map's chips take three rows. The static condition fits
  everywhere. **Since 2026-10-11 the scatter's sixteen chips take four rows, not two**, and its
  interactive card ends 72 px lower: Submit's bottom edge sits at 862 px in compact mode, where
  with six chips it ended at exactly 790 (measured in headless Chrome, both forms, against the
  committed six-dot version). **The map's chips went from 13 (A) and 11 (B) to 18 in each form
  (2026-10-11, `study-design.md` §4).** Measured in headless Chrome after the chart handoff, both
  forms alike, Submit's bottom edge:

  | Window | Scatter, interactive | Map, interactive | Scatter, static | Map, static |
  |---|---|---|---|---|
  | 1440 × 790 (compact) | 862 | 807 | 658 | 603 |
  | 1366 × 768 (compact) | 862 | 836 | 674 | 648 |
  | 1440 × 801 or taller | 898 | 843 | 690 | 635 |

  So the interactive scatter card scrolls on any window under 898 px tall (862 in compact mode),
  and the map card on any under 843 px (807–836 in compact mode, by width). The record before
  2026-10-11 gave the scatter's split as 862 px for every window; outside compact mode it was
  already 898. The static cards fit everywhere.

  **Since 2026-10-12 the scatter's chips take three rows** (§7.3), and its interactive card ends
  36 px higher in both forms. Measured in headless Chrome against the committed version; nothing
  else on any task screen moved:

  | Window | Scatter, interactive | Map, interactive | T1, interactive |
  |---|---|---|---|
  | 1440 × 790 (compact) | 826 | 807 | 802 |
  | 1366 × 768 (compact) | 826 | 836 | 802 |
  | 1440 × 900 | 862 | 843 | 838 |

  The same run found that the interactive T1 card also ran past a 790 px window, by 12 px, in both
  forms. That was already so before these changes: T1's two-line question sits above its card. Its
  static card ends at 658.

  **The Years slider (§7.6), later the same day,** is shorter than the View control it replaced, so
  every interactive line-chart card ends 12 px higher, in both forms:
  - T1 at 790 px in compact mode, exactly a 790 px window's height; at 1366 × 768 it still runs
    22 px past. Outside compact mode it ends at 826.
  - T6 at 735 (A at 1366 × 768: 764).
  
  Nothing else moved (headless Chrome, against the commit before it).

  **The map's highlight box went the same day** (§7.4). Its chips now run three rows of six, not
  four of five, so the interactive map card ends 36 px higher in both forms:
  - 771 at 1440 × 790, inside the window;
  - 800 at 1366 × 768, still 32 px past;
  - 807 outside compact mode.

  The key's buttons sit over the chart and take no room. The scatter, heatmap and map hints, one
  sentence longer, stay on one line. Nothing else moved.

  **T1's four extra controls (§7.7), later the same day,** take a second strip under the first,
  and the interactive T1 card ends 106 px lower in both forms:
  - 896 at 1440 × 790 and at 1366 × 768 (compact mode), 106 and 128 px past the window;
  - 932 outside compact mode, so it runs past a 1440 × 900 window by 32 px, the only card that
    does.

  Its static card is unchanged, and nothing else moved (headless Chrome, both forms, against
  the commit before it).
- **T1's answer panel (2026-09-27).** T1 is written, not chosen (`study-design.md` §4, §5). Its
  panel has one numbered step:
  - "1 Write your description:" heads the handoff's own `.ui-textarea`, the justification's box,
    in place of the six tiles;
  - the heading wraps (no `.ui-step--nowrap`, 2026-10-12): at 21 px, on one line, it ran past
    the panel's edge and was clipped on a narrower window (at 1536 px wide it fits with 5 px to
    spare). Measured in headless Chrome, both forms and conditions: one line from 1440 px wide up,
    two at 1366 × 768, Submit unmoved. At 1280 × 720 the panel is narrower than "description:"
    itself, the open question of narrow windows. The tiles' shorter headings keep the class;
  - there is no step 2 and no justification box;
  - the box fills the height the tiles and the justification took, so Submit stays where the tiles
    would leave it. No new CSS: the handoff's own `.ui-decide` and `.ui-textarea` rules
    (`flex: 1`) grow the box. Measured in headless Chrome (2026-09-27): Submit sits at the same
    place in the card as on T6, the other line chart, in both conditions. The card's height is set
    by the chart column, so line charts, which carry the most controls, set Submit 8 px lower than
    the bar chart in the interactive condition, T1 and T6 alike.

  It is identical in both conditions; the chart, the controls and the hint row are untouched.
- **Answer tiles' text, 15 px (2026-10-12, Eduardo).** study.css sets `.ui-tile-label` at 17 px,
  where a long one-word option ran past its tile: B-T2's key, Mozambique, by 8 px at 1440 × 790,
  and A-T2's Ethiopia and Vietnam by about 4 px at 1366 × 768. `zz-overrides.css` sets it 2 px
  smaller, in both conditions. Measured in headless Chrome on every item, both forms and
  conditions: at 1440 × 790, 1440 × 900 and 1536 × 864 every option sits inside its tile's border
  (Mozambique 2 px into the padding). At 1366 × 768 the tiles are 102 px wide and form B's
  Mozambique and Bangladesh still run past the border, clipping the radio button; at 1280 × 720
  they are 59 px wide and 108 of the 132 options do. Both are open (`study-design.md` §10).
- **Header.** On every screen: a band with the title, "Vaccination coverage study", and a seven-step
  indicator: Consent, Practice, Part 1, Break, Part 2, About you, Finished. It is display only, not
  links. The current step carries `aria-current="step"`, and the steps before it are ticked. The
  first half's instructions, practice and practice-complete screens are "Practice"; its tasks and
  survey are "Part 1"; everything in the second half before About you is "Part 2".
- **Backgrounds.** The oat ground on every screen, with nothing behind a chart: the task screen is
  plain. The other screens have a sand fade with a slow glow, and practice complete, the break and
  the finished screen a warmer one. The handoff's README calls the survey and About you plain; its
  Screens file draws them with the fade, and the Screens file outranks it.
- **Compact mode.** At a window height of 800 px or less, the chrome above the chart tightens so the
  card fits a 1366 × 768 screen, except the interactive scatter and map cards (above). The chart
  itself does not change size. It is a media query, not a class set by script, so it applies before
  a screen first paints and nothing moves once a task's clock has started.
- **Motion.** Only on screens without a chart: cards fade in over 180 ms and a slow background glow
  drifts. None on the task screen, and none at all under `prefers-reduced-motion`.
- **Flags.** The chips' flags are image files bundled under `src/assets/flags/` by
  `scripts/vendor_flags.py`, one per country in the scope, never fetched from a CDN during a task, as
  the map's shapes are (§1). They are part of the controls, so only the interactive condition has
  them.
