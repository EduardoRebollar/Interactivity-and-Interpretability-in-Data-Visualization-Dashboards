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
labelling by chart type (§6), and the bar sort, the map's coverage range and the modebar (§7). A
change to any of §1–8 needs this document edited first, then the code.

---

## 1. Chart forms

Each task names one chart type (`flow.Task.chart`) and the years it shows (`Task.years`). There is
one figure builder per type, and none takes an `interactive` argument (§7).

| Type | Items | Encoding |
|---|---|---|
| Line | T1, T6, practice | Coverage over 2000–2024, one line per entity, World dashed where shown (T6 draws two countries and no World line) |
| Bar | T2 | One year's coverage, one bar per country, in the listed order |
| Scatter | T3 | Each country a dot: coverage in 2000 across, in 2024 up, with a dashed no-change diagonal |
| Heatmap | T4 | Countries down, years across (2000, 2005, 2010, 2015, 2020, 2024), coverage as colour |
| Map | T5 | One year's coverage as colour on the countries of sub-Saharan Africa the item names |

**Line.** Multi-series, x year 2000–2024 (linear, integer ticks), y coverage. Markers on every
observed point, radius 5. Markers are not decoration: after a gap, a lone observation with no
neighbours draws no line segment at all, and without a marker it would silently vanish.

**Bar.** Vertical bars, one colour (§4), named on the x axis. The y axis is the line chart's.

**Scatter.** One trace per country, so each has its own colour and marker shape (§6) and a legend
entry. Both axes run 0–100 on **one scale** (`scaleanchor`), so the diagonal is a true 45° line of no
change and the distance above it is the improvement. The diagonal is a shape, dashed in the axis
colour, labelled "no change" in the empty lower-left corner. It has no legend entry and no hover.

**Heatmap.** Rows in the task's order, the first at the top. Columns are categories, so 2020–2024
takes the same width as the other five-year steps. Cells are separated by 2 px white gaps, so two
adjacent cells of one colour stay two cells. **No number is written in a cell**: that would give
the static condition the exact value (§7).

**Map.** A choropleth on Plotly's Africa scope at 110m resolution, framed at 36°S–26°N and 20°W–53°E.
26°N rather than the Sahel's edge because Mali reaches 25°N, and a frame that cuts a coloured country
hides part of it. The countries an item names are coloured on the sequential scale (§4); every other
country is plain grey land. Borders are white (§4). The geometry is Plotly's own file, served from
`src/assets/geo_africa.js` (written by `scripts/vendor_map_geometry.py`) rather than fetched from
Plotly's CDN in each participant's browser mid-task.

## 2. Axes

| Property | Value | Reason |
|---|---|---|
| Coverage axis (line and bar y; both scatter axes) | **fixed 0–100, never auto-scaled** | An axis that rescales between tasks or conditions changes how steep a trend or how tall a bar looks. That would confound interpretation accuracy with axis framing. |
| Colour scale (heatmap, map) | **fixed 0–100** (`zmin`/`zmax`) | For the same reason: a scale fitted to the data would give the same colour to different values on different tasks. |
| Line x range | 2000–2024 | Locked scope. |
| Coverage ticks | every 10 | Fine enough to estimate against without hover, coarse enough to stay readable. |
| Colour-key ticks | every 10 | So 50% is marked, the threshold T5 asks about. |
| Axis line & tick labels | `#404040`, 10.37:1 | Well above the 4.5:1 text floor. |
| Gridlines (line, bar, scatter) | `#B3B3B3`, 2.10:1 | See §4 — a documented exemption. |
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
what information is available, only how it is reached.

No chart in the current task bank shows a gap: the acceptance rule refuses an item with a missing
bar, dot, cell or country (`docs/study-design.md` §4), and every line in the line items is complete
for 2000–2024. The caption stays for a data refresh that opens a gap.

Enforced by `tests/test_app.py::test_gap_note_names_the_series_with_unreported_years`.

## 4. Color

Every ratio below is **measured** by `src/contrast.py`, not estimated. Regenerate the tables with
`uv run python scripts/check_contrast.py`. Floors come from WCAG 2.1 AA: 4.5:1 for text, 3:1 for
graphical objects.

Background: `#FFFFFF`.

### Series colors (floor 3:1)

Colour tells lines apart on the line charts and dots apart on the scatter. Assigned by position in
the task's entity list, so a chart with *k* series uses the first *k*.

| Order | Hex | Ratio | Luminance | Note |
|---|---|---|---|---|
| 1 | `#0072B2` | 5.19:1 | 0.152 | Okabe-Ito blue, unmodified |
| 2 | `#D55E00` | 3.87:1 | 0.222 | Okabe-Ito vermillion, unmodified |
| 3 | `#009E73` | 3.42:1 | 0.257 | Okabe-Ito bluish green, unmodified |
| 4 | `#CC79A7` | 3.06:1 | 0.293 | Okabe-Ito reddish purple, unmodified |
| 5 | `#960600` | 9.04:1 | 0.066 | dark red, added 2026-09-23 |
| 6 | `#062AA8` | 11.03:1 | 0.045 | royal blue, added 2026-09-23 |
| 7 | `#246648` | 6.84:1 | 0.103 | forest green, added 2026-09-23 |
| 8 | `#845472` | 6.01:1 | 0.125 | mauve, added 2026-09-23 |

Reference series (World): `#000000`, 21.00:1, dashed. Black and dashed so it reads as a baseline
rather than as one more competing country.

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

**The palette is in `config.SERIES_COLORS` in this order.** Each colour after the four Okabe-Ito
ones is the one furthest from those before it, so a chart with fewer series uses the most separable
subset. `tests/test_palette.py` holds the contrast floor, the luminance gap, the ΔE floor
(`config.MIN_CVD_DISTANCE`) and the distance from World.

Colour is never the only channel for a series, whatever the palette (§6).

### Sequential scale (heatmap and map)

Cividis, written out as ten stops in `config.SEQUENTIAL_SCALE`: dark blue `#00224E` at 0, yellow
`#FEE838` at 100. **Dark is low coverage**, as the prompts say. Cividis was chosen because its
lightness rises steadily and reads the same under deuteranopia and protanopia. The tests check that
lightness rises at every stop in normal vision and under both simulations. One coverage point moves
lightness by 0.73–0.86 L*, which is what `docs/study-design.md` §4 uses to set the colour floor.

**DELIBERATE EXEMPTION from the 3:1 floor**, like the gridline. The light end is 1.25:1 on white.
No sequential scale can put every step at 3:1 on white and still span enough lightness to read a
difference in. No cell or country is *found* by its colour:

- heatmap cells sit on a grid labelled by country and year;
- map countries are separated by white borders and named on hover.

What must hold instead is enforced: **white borders reach 3:1 against every fill up to 50%**, the
dark countries T5 asks participants to count. That is 15.69:1 at 0% and 4.89:1 at 44%.
(`AXIS_COLOR` borders were rejected: 1.51:1 against the darkest fill, so two adjacent dark
countries, such as CAR and Chad, would merge.)

| Map element | Colour |
|---|---|
| Coloured countries | sequential scale, fixed 0–100 |
| Every other country | `#EFEFEF`, plain land |
| Borders between countries | `#FFFFFF` |
| Coastlines | `#B3B3B3`, the gridline grey |
| Countries outside the chosen coverage range (interactive, §7.4) | same colour, opacity 0.15 |

### Text and structure

| Role | Hex | Ratio | Floor |
|---|---|---|---|
| Primary text | `#1A1A1A` | 17.40:1 | 4.5:1 |
| Muted text | `#595959` | 7.00:1 | 4.5:1 |
| Axis | `#404040` | 10.37:1 | 4.5:1 |
| Validation error | `#C35600` | 4.51:1 | 4.5:1 |
| Gridline | `#B3B3B3` | 2.10:1 | **exempt** |

**The error colour is UI chrome, not a series colour.** It never appears on a chart, so it does not
count against `MAX_SERIES` and needs no separation from the palette. It is derived from the
vermillion series colour by `contrast.darken_to_ratio`, which scales all three channels equally and
so preserves the hue. The vermillion itself is 3.87:1 — above the 3:1 graphic floor that applies to
a 2.5px line, below the 4.5:1 floor that applies to text.

**The gridline exemption is deliberate and recorded.** No grey reaches 3:1 against white while still
reading as a gridline rather than as data. `#B3B3B3` is darker than a typical default because the
static condition has no hover, so participants estimate values against the grid. The values are
carried by tick labels at 10.37:1. `config.GRIDLINE_EXEMPT` makes the exemption explicit, and a test
fails if the gridline ever drifts too faint to use (< 1.8:1).

## 5. Typography and dimensions

| Property | Value |
|---|---|
| Family | Helvetica, Arial, sans-serif |
| Base | 14 px |
| Title | 18 px |
| Axis labels, legend, colour key | 13 px |
| Line width | 2.5 px |
| Line marker radius | 5 px |
| Scatter marker size | 12 px |
| Heatmap cell gap | 2 px |
| Chart height, every type | 520 px |

**The chart's 520 px is reserved from the moment a task screen appears (2026-09-16), in both
conditions.** Plotly is loaded on demand, the first time a chart is drawn in a session. Until it
arrives, `dcc.Graph` renders at zero height, so the question, answers and Submit first appeared
directly under the prompt and then jumped 520 px down about 600 ms later — long enough for a click
to land on the wrong option. A fixed-height container around the chart holds the space.

## 6. Series limits and labelling

- **At most 8 colour-coded series on one chart** (line and scatter), World not counted. Bars share
  one colour; heatmap rows and map countries use the sequential scale; neither is capped by the
  palette.
- **Colour is never the only channel identifying a series.** Each chart type carries a second one:

| Type | Identity carried by |
|---|---|
| Line | the series name at the right end of the line, in its colour |
| Bar | the country name on the x axis |
| Scatter | a legend pairing each colour with its own marker shape |
| Heatmap | the country name on each row |
| Map | the country's place on the map, and its name on hover |

- **End labels never overlap (added 2026-09-22).** Each sits at its series' last reported point, in
  the series colour. Where two would be closer than **18 px** (4.5 points), they are spread apart
  vertically, by the smallest spread that separates them and keeps their order. The spread is
  computed in `build_figure`, which takes no `interactive` argument, so both conditions get
  identical labels.
- **Labels may rise into the top margin by one label's height (amended 2026-09-23).** A-T1 has eight
  countries ending between 67 and 97. Holding every label under 100 moved World's label 7.5 points
  off its line; with the headroom, no label moves more than 5.44. Labels are placed in paper
  coordinates vertically, because Plotly does not draw an annotation whose data coordinate lies
  outside its axis range. The first build did exactly that, and China's label on A-T1 never
  appeared (found in headless Chrome).
- **The scatter's legend is part of the task.** Its item asks which country improved most; without
  hover, the dot is named by matching its colour and shape to the legend. Legend clicks are
  disabled, because a click hides a series — a filter no event would record.

**RESOLVED (2026-09-15) — the same fixed set per task, in both conditions.** If interactive
participants could reach entities that static participants could not, interactivity would be
changing *how much data is reachable* as well as *how it is worked with*. Each task names its own
fixed entity set, both conditions see it, and no control reaches an entity the static condition
cannot see (`docs/study-design.md` §3).

The World reference is excluded from the line filter (`layout.filterable`): it is the baseline the
lines are read against, and switching it off would remove part of what the question is about.

Enforced by `tests/test_conditions.py::test_the_task_screen_opens_on_the_same_chart_in_both_conditions`,
for every task.

## 7. Condition differences

The **only** permitted difference. Everything in §1–6 is identical across conditions.

| | Static | Interactive |
|---|---|---|
| `staticPlot` | `True` | `False` |
| Hover tooltips | none | every chart: the value; on lines, also the change from the year before |
| Line charts | image | filter, sort the list, isolate a line, zoom and pan the x axis |
| Bar chart | image | sort the bars by coverage |
| Scatter, heatmap | image | hover only, announced by a line of text above the chart |
| Map | image | show only countries within a coverage range |

Plotly is interactive by default, so a plain `dcc.Graph` would leave the static condition hoverable
and zoomable and the manipulation would be invalid. `staticPlot: True` is what makes "static"
actually static.

**The chart itself is identical.** Every difference above is either a Plotly config flag or a control
rendered *beside* the chart. Nothing in this table adds, removes or restyles a mark at rest.
`build_figure` takes no `interactive` argument, and `tests/test_conditions.py` proves both conditions
open on byte-identical figure JSON for every task. Once a control is used, it changes the chart only
through a view function that hides, reorders or fades what is already there (`figures.set_visible`,
`sort_bars`, `set_band`).

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

### 7.2 Sorting (defined 2026-09-15; bars added 2026-09-23)

**On a line chart, sorting reorders the entity control list. It never reorders the chart.** A
time-series line chart has no meaningful row order: the x axis is time and the lines are where the
data puts them.

- Control: `Order: (as listed) (by coverage)`, default `as listed` (the task's own order).
- `by coverage` sorts the checkbox list by each entity's most recently **reported** value, highest
  first, and shows the value in the label (`Brazil — 91%`).
- An entity with nothing reported sorts last and reads `not reported`.

**On the bar chart, sorting moves the bars** (2026-09-23). A bar chart's x axis has no order of its
own, so reordering it changes no meaning: each bar keeps its colour, its label and its height. The
same two options, on a control of its own (`bar-sort`). `by coverage` puts the bars highest first,
and `as listed` puts them back. A bar with no value would sort last.

### 7.3 Filtering and line isolation (line charts)

- **Filtering** hides series via `visible`; it does **not** rebuild the chart from a shorter list.
  Colour is assigned by position (§4), so a rebuild would recolour the survivors. An end label is
  hidden with its series. The filter cannot empty the chart — the last series cannot be unchecked.
- **Line isolation** is a click on the line itself. Clicking an isolated line again releases it, as
  does *Show all*. The World reference stays visible throughout and cannot itself be isolated. A
  click on any other chart type does nothing.
- Both reset between tasks: no task inherits the previous task's view.

### 7.4 The map's coverage range (defined 2026-09-23)

- Control: a range slider, 0–100% in steps of 1, with a number box at each end, and *Show all*. The
  participant sets the range. A preset "below 50%" button was rejected: it would name the
  question's own threshold and answer T5 in one click.
- **Countries outside the range fade to 0.15 opacity.** They keep their colour and their place, and
  the ends of the range are included.
- Drawn as a **selection**. The countries in the range are selected and the rest take the trace's
  `unselected` opacity. plotly.js 4 applies a choropleth's `marker.opacity` to the whole trace, so
  the first build's per-country opacity list faded nothing. Only a browser showed it.
- The full range clears the selection, so an unfiltered map is exactly the figure at rest.
- A handle can be dragged, moved with the arrow, Page Up/Down, Home and End keys, or set by typing
  in its box. Dash 4 commits a typed value only when the box loses focus; `src/assets/slider_enter.js`
  makes Enter commit it too. Without it, a participant who typed 49 and pressed Enter saw the handle
  move and the map ignore them.
- *Show all* moves both handles back to the ends.

### 7.5 The modebar (defined 2026-09-23)

The interactive condition shows Plotly's modebar. Each figure lists the buttons it drops in its own
layout (`modebar.remove`), so the list is part of the figure and identical in both conditions; the
static condition shows no modebar at all.

- **Box and lasso select are removed from every chart.** They dim the unselected marks, which changes
  what is on screen, and no event records it. On the map they would also override the coverage
  range, which is drawn as a selection. They had been available on the line charts since those were
  built; they went with this amendment.
- **Zoom and pan are removed from the bar, scatter, heatmap and map**, whose views are fixed (§2);
  on the map, so are the map zoom buttons. The line chart keeps zoom and pan on its x axis, logged
  as `view_change`.

**Consequence for task design:** static participants cannot read exact values; they estimate against
gridlines or a colour key. A task asking "what was Nigeria's DTP3 coverage in 2012?" therefore
measures whether hover exists, not interpretation ability. Every item must survive the reading
errors of a participant without hover — the acceptance rule in `docs/study-design.md` §4. This is a
study-design decision, recorded here because it follows directly from the visual spec.

## 8. Accessibility

- Contrast floors above are enforced by `tests/test_palette.py`, so an inaccessible palette fails the
  build rather than reaching a participant. So is the palette's separation under simulated
  colour-vision deficiency (§4), and the sequential scale's steady lightness under it.
- All controls are keyboard-operable (CLAUDE.md baseline):
  - the line chart's checkboxes and radios and the bar chart's radios are native form elements;
  - the map's slider handles take the arrow, Page Up/Down, Home and End keys, and its number boxes
    take typing.
- Hover, line isolation and zoom are mouse-only. A keyboard-only participant in the interactive
  condition therefore meets the scatter and heatmap items with no affordance at all, as in the
  static condition. This is recorded in `docs/study-design.md` §10.
- Direct labelling and marker shapes mean colour is never the sole channel for a series (§6).
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

Nothing in §1–8 is open. A change to any of it needs this document edited first, then the code.
