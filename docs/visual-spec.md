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

**OPEN — how is "not reported" communicated?** A participant seeing nothing where the UK's line
should be may reasonably conclude coverage was *zero* rather than *unrecorded*. In the interactive
condition a tooltip can say so; in the static condition, with no hover, it cannot. Options: a caption
listing which series have gaps, an in-chart annotation, or accepting the ambiguity as part of what is
being measured. This must be resolved identically for both conditions.

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
| Gridline | `#B3B3B3` | 2.10:1 | **exempt** |

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

**OPEN — which entities does each condition show?** If interactive participants can filter to any of
the 17 entities while static participants see a fixed 5, then interactivity is not only changing
*interaction*, it is changing *how much data is reachable*, and the two effects cannot be separated
in analysis. Recommended: both conditions show the same fixed set per task, and filtering in the
interactive condition operates only within that set. This belongs in `docs/study-design.md` and must
be settled before `layout.py` is written.

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
| Year-over-year indicators | none | yes |

Plotly is interactive by default, so a plain `dcc.Graph` would leave the static condition hoverable
and zoomable and the manipulation would be invalid. `staticPlot: True` is what makes "static"
actually static.

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

1. §3 — how "not reported" is communicated, given the static condition has no tooltip.
2. §6 — whether both conditions show the same entity set.
3. Continent aggregates have **no 2024 data** for any vaccine, while countries do. A chart mixing
   them shows continent lines stopping a year short. Decide: exclude 2024, exclude continents from
   mixed charts, or annotate.
