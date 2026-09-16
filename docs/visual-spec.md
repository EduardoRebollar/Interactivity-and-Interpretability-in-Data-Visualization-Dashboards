# Visual specification

Source of truth for every visual decision in the dashboard. **Change this document first, then the
code.** The values here are mirrored in `src/config.py` and enforced by `tests/test_palette.py`.

Both study conditions use these values identically. A visual change applies to both conditions or to
neither — that is the methodological premise of the whole study, so a difference in appearance
between static and interactive is a defect, not a variation.

Status: **draft, 2026-09-09.** Sections marked OPEN need Eduardo's ruling before the UI is built.

---

## 1. Chart form

- **Type:** multi-series line chart. One chart per vaccine.
- **x:** year, 2000–2024, linear, integer ticks.
- **y:** coverage percentage.
- **Markers:** shown on every observed point, radius 5.

Markers are not decoration. After a gap, a lone observation with no neighbours draws no line segment
at all — the UK's HepB3 series would silently lose its 2019 value without a marker to carry it.

## 2. Axes

| Property | Value | Reason |
|---|---|---|
| y range | **fixed 0–100, never auto-scaled** | An axis that rescales between tasks or conditions changes how steep a trend looks. That would confound interpretation accuracy with axis framing. |
| x range | 2000–2024 | Locked scope. |
| y ticks | every 10 | Fine enough to estimate against without hover, coarse enough to stay readable. |
| axis line & tick labels | `#404040`, 10.37:1 | Well above the 4.5:1 text floor. |
| gridlines | `#B3B3B3`, 2.10:1 | See §4 — a documented exemption. |

## 3. Missing data

**Gaps render as gaps.** `connectgaps=False`, always. A line that bridges a NaN invents data that was
never reported, and the gaps are part of what participants are being asked to interpret.

Test case: UK HepB3 reports only 2019–2024, so 19 of 25 years are absent. That series must appear as
a short segment at the right edge, not a line spanning 2000–2024.

**RESOLVED (2026-09-15) — a caption, shown in both conditions.** A participant seeing nothing where
the UK's line should be may reasonably conclude coverage was *zero* rather than *unrecorded*. In the
interactive condition a tooltip can say so; in the static condition, with no hover, it cannot.

The decision is a caption below the chart naming every series with unreported years and the years
concerned — `layout.gap_note`, e.g. *"No data reported for: United Kingdom (2000–2018). A break in a
line means the value was not reported, which is not the same as zero coverage."*

It appears in **both** conditions, which is what makes it admissible. The alternative — letting the
interactive condition explain gaps through a tooltip the static condition cannot show — would mean
interactivity was changing what information is available, not just how it is reached, and the two
effects could not be separated in analysis. The in-chart annotation was rejected for adding a mark to
a locked chart; accepting the ambiguity was rejected because T6 measures gap reasoning specifically,
and an item nobody can answer measures nothing.

Enforced by `tests/test_app.py::test_gap_note_names_the_series_with_unreported_years`.

## 4. Color

Every ratio below is **measured** by `src/contrast.py`, not estimated. Regenerate the table with
`uv run python scripts/check_contrast.py`. Floors come from WCAG 2.1 AA: 4.5:1 for text, 3:1 for
graphical objects.

Background: `#FFFFFF`.

### Series colors (floor 3:1)

| Order | Hex | Ratio | Luminance | Note |
|---|---|---|---|---|
| 1 | `#0072B2` | 5.19:1 | 0.153 | Okabe-Ito blue, unmodified |
| 2 | `#9C6C00` | 4.61:1 | 0.178 | Okabe-Ito orange, darkened from `#E69F00` (2.25:1) |
| 3 | `#D55E00` | 3.87:1 | 0.222 | Okabe-Ito vermillion, unmodified |
| 4 | `#009E73` | 3.42:1 | 0.257 | Okabe-Ito bluish green, unmodified |
| 5 | `#CC79A7` | 3.06:1 | 0.293 | Okabe-Ito reddish purple, unmodified |

Reference series (World): `#000000`, 21.00:1, dashed. Black and dashed so it reads as a baseline
rather than as a sixth competing country.

### Why five, and not more

The base is Okabe-Ito, a palette designed for color-vision deficiency. Four members survive
unmodified, which preserves the separability it was validated for. Three were dropped, each for a
measured reason:

- **Yellow `#F0E442`** is 1.32:1 on white — far below the floor. Darkened enough to pass it becomes
  `#9F972C`, an olive that collides with the green.
- **Sky blue `#56B4E9`** is 2.31:1. Every form of it that passes lands near luminance 0.291, which is
  indistinguishable from the purple at 0.293.
- **Black** is reserved for the World reference.

**Colors are separated in luminance as well as hue** — minimum gap 0.025. This matters: an earlier
draft darkened three swatches to the same 3.2:1 target and produced luminance gaps of 0.0008, which
would have been indistinguishable in greyscale or under severe color-vision deficiency. All swatches
passed contrast individually; the palette was still broken. `test_series_colors_are_separated_in_luminance`
exists because of that.

**Consequence: at most five entities plus World may be plotted at once.** This is not an aesthetic
preference — it is the size of the largest set that is simultaneously accessible, color-blind safe,
and luminance-separated. See §6.

### Text and structure

| Role | Hex | Ratio | Floor |
|---|---|---|---|
| Primary text | `#1A1A1A` | 17.40:1 | 4.5:1 |
| Muted text | `#595959` | 7.00:1 | 4.5:1 |
| Axis | `#404040` | 10.37:1 | 4.5:1 |
| Validation error | `#C35600` | 4.51:1 | 4.5:1 |
| Gridline | `#B3B3B3` | 2.10:1 | **exempt** |

**The error colour is UI chrome, not a sixth series colour.** It never appears on a chart, so it does
not count against `MAX_SERIES` and needs no luminance separation from the palette. It is derived from
the vermillion series colour by `contrast.darken_to_ratio`, which scales all three channels equally
and so preserves the hue. The vermillion itself is 3.87:1 — above the 3:1 graphic floor that applies
to a 2.5px line, below the 4.5:1 floor that applies to text, which is why the error text needed its
own darker value rather than reusing the series swatch.

**The gridline exemption is deliberate and recorded.** No grey reaches 3:1 against white while still
reading as a gridline rather than as data — the lightest passing grey competes with the series lines.
`#B3B3B3` is darker than a typical chart default because the static condition has no hover, so
participants estimate values against the grid. No information depends on the gridline alone: the
values are carried by tick labels at 10.37:1. `config.GRIDLINE_EXEMPT` makes the exemption explicit,
and a test fails if the gridline ever drifts faint enough to be useless (< 1.8:1).

## 5. Typography and dimensions

| Property | Value |
|---|---|
| Family | Helvetica, Arial, sans-serif |
| Base | 14 px |
| Title | 18 px |
| Axis labels | 13 px |
| Line width | 2.5 px |
| Marker radius | 5 px |
| Chart height | 520 px |

## 6. Series limits and labelling

- **Maximum 5 entities plus the World reference on one chart.**
- Colour is never the only channel: every series is **directly labelled at the right end of its
  line**, so identification does not depend on matching a swatch to a legend entry.

**RESOLVED (2026-09-15) — the same fixed set per task, in both conditions.** If interactive
participants could filter to any of the 17 entities while static participants saw a fixed 5, then
interactivity would be changing *how much data is reachable* as well as *how it is worked with*, and
the two effects could not be separated in analysis.

The decision, recorded in full at `docs/study-design.md` §3: each task names its own fixed entity
set, both conditions see it, and filtering in the interactive condition operates **only within that
set**. No control reaches an entity the static condition cannot see.

The World reference is excluded from the filter (`layout.filterable`): it is the baseline several
items are read against, and switching it off would let a participant remove the subject of the
question.

Enforced by `tests/test_conditions.py::test_the_task_screen_opens_on_the_same_chart_in_both_conditions`.

## 7. Condition differences

The **only** permitted difference. Everything in §1–6 is identical across conditions.

| | Static | Interactive |
|---|---|---|
| `staticPlot` | `True` | `False` |
| Hover tooltips | none | yes |
| Zoom / pan / modebar | none | yes |
| Filtering | none | yes |
| Sorting | none | yes |
| Line isolation | none | yes |
| Year-over-year change | none | yes (in the tooltip — see below) |

Plotly is interactive by default, so a plain `dcc.Graph` would leave the static condition hoverable
and zoomable and the manipulation would be invalid. `staticPlot: True` is what makes "static"
actually static.

**The chart itself is identical.** Every difference above is either a Plotly config flag or a control
rendered *beside* the chart. Nothing in this table adds, removes or restyles a mark. `build_figure`
takes no `interactive` argument, so the figure cannot differ by construction, and
`tests/test_conditions.py` proves the two conditions open on byte-identical figure JSON.

### 7.1 Year-over-year change (defined 2026-09-15)

A signed change against the previous year, as a **third line in the hover tooltip**:

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
  absent in the other, which is the one thing the figure is built to make impossible. The tooltip
  text sits in *both* figures; `staticPlot: True` simply means a static participant never fires a
  hover to read it. Interactive-only by construction, with no new mark and no new colour — so no
  contrast work, and §4 is untouched.
- **"pts", not "%".** The difference between two percentages is percentage points. "+3%" would
  wrongly suggest a relative change.
- **Deltas are computed from the rounded values the tooltip displays**, so arithmetic a participant
  can check on screen always agrees with the numbers they were shown.
- **No delta is invented across a gap.** Differencing the UK's 2019 HepB3 value against its 2000 row
  would fabricate a "year-over-year" change between points 19 years apart — the same error
  `connectgaps=False` exists to prevent.

### 7.2 Sorting (defined 2026-09-15)

**Sorting reorders the entity control list. It never reorders the chart.** A time-series line chart
has no meaningful row order: the x axis is time and the lines are where the data puts them.

- Control: `Order: (as listed) (by coverage)`, default `as listed` (the task's own order).
- `by coverage` sorts the checkbox list by each entity's most recently **reported** value, highest
  first. Most recently reported, not the last year — every continent aggregate is missing 2024.
- The value is shown in the label **only** in this mode (`Brazil — 91%`). Sorting by a value without
  showing it is unusable; showing it by default would put numbers on a resting screen for no reason.
- An entity with nothing reported sorts last and reads `not reported`.

### 7.3 Filtering and line isolation

- **Filtering** hides series via `visible`; it does **not** rebuild the chart from a shorter list.
  Colour is assigned by position (§4), so a rebuild would recolour the survivors and a participant
  who hid one country would watch the others change colour mid-task. An end label is hidden with its
  series. The filter cannot empty the chart — the last series cannot be unchecked.
- **Line isolation** is a click on the line itself (there is no legend to click — §6). Clicking an
  isolated line again releases it, as does *Show all*. The World reference stays visible throughout
  and cannot itself be isolated.
- Both reset between tasks: no task inherits the previous task's view.

**Consequence for task design:** static participants cannot read exact values at all; they estimate
against gridlines. A task asking "what was Nigeria's DTP3 coverage in 2012?" therefore measures
whether hover exists, not interpretation ability. Tasks should target trends, comparisons, crossings,
and gaps. This is a `docs/study-design.md` decision, recorded here because it follows directly from
the visual spec.

## 8. Accessibility

- Contrast floors above are enforced by `tests/test_palette.py`, so an inaccessible palette fails the
  build rather than reaching a participant.
- All interactive controls must be keyboard-navigable (CLAUDE.md baseline).
- Direct labelling means color is never the sole information channel.
- Full screen-reader support is explicitly out of scope; nothing here should make it worse.

## 9. Open items

All three items previously listed here are now settled. Kept, rather than deleted, so the reasoning
survives into the write-up.

1. ~~§3 — how "not reported" is communicated, given the static condition has no tooltip.~~
   **Resolved 2026-09-15:** a caption in both conditions. See §3.
2. ~~§6 — whether both conditions show the same entity set.~~
   **Resolved 2026-09-15:** the same fixed set per task; filtering operates only within it. See §6
   and `docs/study-design.md` §3.
3. ~~Continent aggregates have no 2024 data.~~ **Resolved:** no task depends on a continent in 2024.
   No item currently uses a continent at all, and `tests/test_tasks.py::test_no_task_depends_on_a_continent_in_2024`
   fails the build if one ever does. The underlying gap is unchanged and is documented in CLAUDE.md;
   this constrains task design rather than the visual spec.

Nothing in §1–8 is open. A change to any of it needs this document edited first, then the code.
