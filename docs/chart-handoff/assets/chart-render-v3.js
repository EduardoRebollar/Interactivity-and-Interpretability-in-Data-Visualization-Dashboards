// Turn 4: the 1a line chart's style carried to bar, scatter, heatmap and map. 4 px a point kept.
import { DATA } from './chart-data.js';
import { RAMPS, _h } from './chart-render.js';
import { GEO_AF } from './africa-geo.js';
import { GEO_W } from './world-geo.js';
const { T, L, shape, spread, esc, r1, hex, SERIES, SHAPES, INK, MUTED, CVD, OFF, SHORT } = _h;

const W = 1050, H = 462, PT = 22, PB = 422, yv = v => PB - v * 4;
const AXIS = '#4A3F38', GRID = '#BBAEA4', LAND = '#EEE8E2', SOFT = '#E4D8CC';
let RAMP = RAMPS.warm, RN = 'warm';
function civ(v) {
  const t = Math.max(0, Math.min(1, v / 100));
  for (let i = 1; i < RAMP.length; i++) if (t <= RAMP[i][0]) {
    const [p0, c0] = RAMP[i - 1], [p1, c1] = RAMP[i], f = (t - p0) / (p1 - p0), a = hex(c0), b = hex(c1);
    return '#' + a.map((x, k) => Math.round(x + (b[k] - x) * f).toString(16).padStart(2, '0')).join('');
  }
  return RAMP[RAMP.length - 1][1];
}
const relL = c => hex(c).map(x => { x /= 255; return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }).reduce((a, b, i) => a + b * [0.2126, 0.7152, 0.0722][i], 0);
const YINK = relL(INK);
const darkFill = c => { const Y = relL(c); return 1.05 / (Y + 0.05) > (Y + 0.05) / (YINK + 0.05); };

function yAxis(lft, rgt, from = 0) {
  let g = '';
  for (let v = 10; v <= 100; v += 10) g += L(lft, yv(v), rgt, yv(v), GRID, 1);
  for (let v = from; v <= 100; v += 10) g += TM(lft - 8, yv(v), v + '%', { size: 13, fill: AXIS, anchor: 'end', mid: true });
  return g + TM(16, -2, 'Coverage', { size: 13, fill: AXIS });
}
// Medium weight for axis text and country names: a hairline stroke in the text colour, standing in for font-weight 500.
const MW = 0.45;
const TM = (x, y, s, o = {}) => T(x, y, s, o).replace('<text ', `<text stroke="${o.fill || INK}" stroke-width="${MW}" `);
const axes = (lft, rgt) => L(lft, PB, rgt, PB, AXIS, 1) + L(lft, PT, lft, PB, AXIS, 1);

function key(kx, top, h, swatch) {
  const id = `k4-${RN}`, w = 12;
  let g = `<defs><linearGradient id="${id}" x1="0" y1="1" x2="0" y2="0">${RAMP.map(([p, c]) => `<stop offset="${p}" stop-color="${c}"/>`).join('')}</linearGradient></defs>`;
  g += T(kx, top - 14, 'Coverage', { size: 13, fill: AXIS });
  g += `<rect x="${kx}" y="${top}" width="${w}" height="${h}" fill="url(#${id})" stroke="${GRID}" stroke-width="1"/>`;
  for (let v = 0; v <= 100; v += 10) {
    const y = top + h - v / 100 * h;
    g += L(kx + w, y, kx + w + 5, y, AXIS, 1) + T(kx + w + 9, y, v + '%', { size: 13, fill: AXIS, mid: true });
  }
  g += T(kx, top + h + 24, 'Darker means lower', { size: 13, fill: MUTED });
  if (swatch) {
    const sy = top + h + 52;
    g += `<rect x="${kx}" y="${sy - 6}" width="18" height="12" fill="${LAND}" stroke="${GRID}" stroke-width="1"/>`;
    g += T(kx + 26, sy, 'No data', { size: 13, fill: MUTED, mid: true });
  }
  return g;
}

// 1a line, with 2000 at the y axis (origin 0 / 2000) and a horizontal x-axis title.
// Extra series for the practice item and Q6 (data/deploy/coverage.csv, DTP3, 2000-2024).
const LINE_EXTRA = {
  'World': [72,72,72,74,76,77,78,78,81,83,83,84,84,83,85,85,86,86,86,86,83,82,85,84,85],
  'Central African Republic': [37,40,44,47,51,54,51,48,45,42,45,47,47,23,45,43,42,42,40,38,37,35,33,40,42],
};
function line(opts = {}) {
  const src = opts.series ? Object.fromEntries(opts.series.map(n => [n, DATA.line[n] || LINE_EXTRA[n]])) : DATA.line;
  const base = Object.keys(DATA.line), used = Object.keys(src).map(n => base.indexOf(n)).filter(i => i >= 0);
  const colOf = n => { const i = base.indexOf(n); if (i >= 0) return SERIES[i]; let f = 0; while (used.includes(f)) f++; used.push(f); return SERIES[f]; };
  const names = Object.keys(src), lft = 52, rgt = 846, x = yr => lft + (yr - 2000) / 24 * (rgt - lft);
  let g = '';
  for (let yr = 2005; yr <= 2020; yr += 5) g += L(x(yr), PT, x(yr), PB, GRID, 1);
  g += yAxis(lft, rgt) + axes(lft, rgt);
  for (let yr = 2000; yr <= 2020; yr += 5) g += TM(x(yr), PB + 18, yr, { size: 13, fill: AXIS, anchor: 'middle' });
  g += TM(rgt, PB + 18, 'Year', { size: 13, fill: AXIS, anchor: 'end' });
  const ends = [];
  names.forEach((n, i) => {
    const c = colOf(n), vals = src[n];
    let d = '', prev = null;
    vals.forEach((v, k) => { if (v == null) { prev = null; return; } d += (prev == null ? 'M' : 'L') + r1(x(2000 + k)) + ',' + r1(yv(v)); prev = v; });
    g += `<path d="${d}" fill="none" stroke="${c}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`;
    vals.forEach((v, k) => { if (v != null) g += `<circle cx="${r1(x(2000 + k))}" cy="${r1(yv(v))}" r="2.6" fill="${c}"/>`; });
    let k = vals.length - 1; while (k >= 0 && vals[k] == null) k--;
    if (k >= 0) ends.push({ n: n === 'Central African Republic' ? 'Central African Rep.' : n, c, xe: x(2000 + k), ye: yv(vals[k]), v: vals[k] });
  });
  ends.sort((a, b) => a.ye - b.ye);
  const ys = spread(ends.map(e => e.ye), 23, PT - 10, PB - 4);
  ends.forEach((e, j) => {
    const yl = ys[j], x0 = rgt + 14, w = 19 + e.n.length * 13 * 0.58 + 7;
    g += `<circle cx="${r1(e.xe)}" cy="${r1(e.ye)}" r="4.6" fill="${e.c}" stroke="#FFFFFF" stroke-width="2"/>`;
    g += `<path d="M${r1(e.xe + 6)},${r1(e.ye)}C${r1(x0 - 4)},${r1(e.ye)} ${r1(e.xe + 14)},${r1(yl)} ${r1(x0)},${r1(yl)}" fill="none" stroke="${e.c}" stroke-width="1.4"/>`;
    g += `<rect x="${r1(x0)}" y="${r1(yl - 10)}" width="${r1(w)}" height="20" rx="10" fill="#FFFFFF" stroke="${SOFT}"/>`;
    g += `<circle cx="${r1(x0 + 10)}" cy="${r1(yl)}" r="4" fill="${e.c}"/>`;
    g += `<text x="${r1(x0 + 19)}" y="${r1(yl)}" font-size="13" dominant-baseline="central" fill="${INK}"><tspan stroke="${INK}" stroke-width="${MW}">${esc(e.n)}</tspan></text>`;
  });
  return { body: g, label: `Line chart of DTP3 coverage, 2000 to 2024, one line per country: ${names.join(', ')}. Vertical axis 0 to 100 percent.` };
}

// Form A T2 (2017), with three added countries; alphabetical order.
const BAR4 = Object.fromEntries(Object.entries({ ...DATA.bar, Kenya: 81, Mali: 77, Afghanistan: 64 }).sort(([a], [b]) => a.localeCompare(b)));
// One colour per bar: countries in the line chart keep their line colour; the rest get new ones (all ≥ 3.7:1 on white).
const BARCOL = { Afghanistan: '#B07A00', Kenya: '#2C8DBF', Mali: '#7A5C00', Vietnam: '#5E5E9E' };
const barCol = n => { const i = Object.keys(DATA.line).indexOf(n); return i >= 0 ? SERIES[i] : BARCOL[n]; };
function bar() {
  const names = Object.keys(BAR4), lft = 52, rgt = 1026, slot = (rgt - lft) / names.length, bw = Math.min(slot * 0.62, 64), col = civ(33);
  let g = yAxis(lft, rgt);
  names.forEach((n, i) => {
    const v = BAR4[n], cx = lft + slot * (i + 0.5);
    const x0 = cx - bw / 2, x1 = cx + bw / 2, yt = yv(v), rr = 6;
    g += `<path d="M${r1(x0)},${PB}V${r1(yt + rr)}Q${r1(x0)},${r1(yt)} ${r1(x0 + rr)},${r1(yt)}H${r1(x1 - rr)}Q${r1(x1)},${r1(yt)} ${r1(x1)},${r1(yt + rr)}V${PB}Z" fill="${barCol(n) || col}"/>`;
    g += TM(cx, PB + 18, n, { size: 13, anchor: 'middle' });
  });
  g += axes(lft, rgt) + T(rgt, -2, 'Countries in alphabetical order', { size: 13, fill: MUTED, anchor: 'end' });
  return { body: g, label: `Bar chart of DTP3 coverage in 2017, one bar per country in alphabetical order: ${names.join(', ')}. Vertical axis 0 to 100 percent.` };
}

// Form A T3: 16 countries, alphabetical. Colour k mod 8, shape k (no two dots share a shape).
const SC4 = { 'Benin': [78, 63], 'Burkina Faso': [45, 91], 'Cameroon': [62, 77], 'Central African Republic': [37, 42], 'Chad': [38, 68], 'Egypt': [98, 97], 'Ethiopia': [30, 73], 'Kenya': [82, 91], 'Libya': [94, 86], 'Madagascar': [57, 60], 'Mali': [43, 82], 'Mozambique': [70, 70], 'Niger': [34, 86], 'Nigeria': [29, 67], 'Sudan': [62, 39], 'Tanzania': [79, 83] };
// Change (2024 minus 2000) in seven steps: three blues for rises, grey within 5 points, three reds for falls. All >= 3:1 on white.
const CHG = { blue: ['#0F3F78', '#1C5FAF', '#3A80CF'], grey: '#8E8781', red: ['#D9473F', '#A3262C', '#6E1D20'] };
const chg = d => d > 40 ? CHG.blue[0] : d > 20 ? CHG.blue[1] : d > 5 ? CHG.blue[2] : d >= -5 ? CHG.grey : d >= -20 ? CHG.red[0] : d >= -40 ? CHG.red[1] : CHG.red[2];
const SCSIDE = { 'Niger': -1, 'Ethiopia': -1, 'Nigeria': -1, 'Central African Republic': -1, 'Madagascar': -1, 'Kenya': -1, 'Tanzania': -1 };

const SCB = { 'Bangladesh': [82, 97], 'Cambodia': [59, 83], 'India': [58, 94], 'Indonesia': [75, 78], 'Iraq': [80, 90], 'Jordan': [91, 96], 'Kyrgyzstan': [99, 85], 'Laos': [51, 67], 'Lebanon': [83, 49], 'Nepal': [74, 97], 'Oman': [99, 99], 'Pakistan': [59, 87], 'Philippines': [78, 71], 'Syria': [86, 73], 'Thailand': [97, 92], 'Yemen': [74, 42] };
// Label side: 1 right, -1 left, 0 above the dot.
const SIDEB = { 'Nepal': -1, 'Iraq': -1, 'India': -1, 'Philippines': -1, 'Bangladesh': 0 };
export const SCATTER_NAMES = { A: Object.keys(SC4), B: Object.keys(SCB) };
function scatter(opts = {}) {
  const SD = opts.form === 'B' ? SCB : SC4, SIDE = opts.form === 'B' ? SIDEB : SCSIDE;
  const names = Object.keys(SD), xl = 290, xv = v => xl + v * 4, halo = 'rgba(255,255,255,.92)';
  let g = '';
  for (let v = 25; v <= 100; v += 25) g += L(xv(v), PT, xv(v), PB, GRID, 1) + L(xl, yv(v), xl + 400, yv(v), GRID, 1);
  for (let v = 0; v <= 100; v += 25) {
    g += TM(xl - 8, yv(v), v + '%', { size: 13, fill: AXIS, anchor: 'end', mid: true });
    g += TM(xv(v), PB + 18, v + '%', { size: 13, fill: AXIS, anchor: 'middle' });
  }
  g += axes(xl, xl + 400);
  g += TM(xl - 44, -2, 'Coverage in 2024', { size: 13, fill: AXIS });
  g += TM(xl + 428, PB + 18, 'Coverage in 2000', { size: 13, fill: AXIS });
  g += L(xv(0), yv(0), xv(100), yv(100), MUTED, 1.5, ' stroke-dasharray="6 5"');
  { const cx = xv(16), cy = yv(16), w = 'No change'.length * 13 * 0.55 + 10;
    g += `<rect x="${r1(cx - w / 2)}" y="${r1(cy - 10)}" width="${r1(w)}" height="20" fill="#FFFFFF" transform="rotate(-45 ${r1(cx)} ${r1(cy)})"/>`;
    g += T(cx, cy, 'No change', { size: 13, fill: MUTED, anchor: 'middle', mid: true, rot: -45 }); }
  g += TM(xv(12.5), yv(95), 'Coverage rose ↑', { size: 13, fill: CHG.blue[0], anchor: 'middle' });
  g += TM(xv(87.5), yv(4), 'Coverage fell ↓', { size: 13, fill: CHG.red[2], anchor: 'middle' });
  // Each name sits on a white knockout, so gridlines and the diagonal stop before the text and resume after it.
  let ko = '', lab = '', dots = '';
  names.forEach(n => {
    const [x0, y0] = SD[n], px = xv(x0), py = yv(y0), f = chg(y0 - x0), sd = SIDE[n] ?? 1;
    const t = n === 'Central African Republic' ? 'Central African Rep.' : n, w = t.length * 11.5 * 0.56;
    dots += `<circle cx="${r1(px)}" cy="${r1(py)}" r="4.5" fill="${f}"/>`;
    if (sd === 0) {
      const ty = py - 13;
      ko += `<rect x="${r1(px - w / 2 - 5)}" y="${r1(ty - 10)}" width="${r1(w + 10)}" height="${r1(py + 9 - (ty - 10))}" fill="#FFFFFF"/>`;
      lab += TM(px, ty, t, { size: 11.5, anchor: 'middle', mid: true });
      return;
    }
    const tx = px + sd * 8, x0k = sd > 0 ? px - 9 : tx - w - 5, x1k = sd > 0 ? tx + w + 5 : px + 9;
    ko += `<rect x="${r1(x0k)}" y="${r1(py - 10)}" width="${r1(x1k - x0k)}" height="20" fill="#FFFFFF"/>`;
    lab += TM(tx, py, t, { size: 11.5, anchor: sd > 0 ? 'start' : 'end', mid: true });
  });
  g += ko + lab + dots;
  // Stepped key: seven bands, boundaries labelled in percentage points, ends and the grey band named.
  const kx = 820, top = PT + 58, sh = 36, gp = 2, kw = 20, bands = [...CHG.blue, CHG.grey, ...CHG.red], kh = bands.length * sh;
  g += TM(kx, top - 16, 'Change since 2000', { size: 13, fill: AXIS });
  g += `<defs><clipPath id="k4-chg"><rect x="${kx}" y="${top}" width="${kw}" height="${kh}" rx="6"/></clipPath></defs><g clip-path="url(#k4-chg)">`;
  bands.forEach((c, i) => { g += `<rect x="${kx}" y="${r1(top + i * sh + (i ? gp / 2 : 0))}" width="${kw}" height="${r1(sh - (i ? gp / 2 : 0) - (i < bands.length - 1 ? gp / 2 : 0))}" fill="${c}"/>`; });
  g += '</g>';
  ['+100%', '+40%', '+20%', '+5%', '−5%', '−20%', '−40%', '−100%'].forEach((t, i) => { g += TM(kx + kw + 10, top + i * sh, t, { size: 13, fill: AXIS, mid: true }); });
  const nx = kx + kw + 60;
  g += TM(nx, top + sh / 2, '↑ Coverage rose', { size: 13, mid: true });
  g += TM(nx, top + 3.5 * sh, 'Little or no change', { size: 13, mid: true });
  g += TM(nx, top + 6.5 * sh, '↓ Coverage fell', { size: 13, mid: true });
  return { body: g, label: `Scatter plot of DTP3 coverage, one named dot per country: coverage in 2000 across, coverage in 2024 up, with a dashed no-change diagonal. Dot colour shows change since 2000 in seven steps, from dark red (fell by more than 40 points) through grey (within 5 points) to dark blue (rose by more than 40 points). Countries: ${names.join(', ')}.` };
}

// Heatmap after the reference: horizontal stepped key on top (7 bands), years as headings, rows A–Z,
// large rounded cells, optional printed values. Band colours are taken from the ramp at stops 1,2,3,4,6,8,9.
const HB = [40, 50, 60, 70, 80, 90], HSTOP = [1, 2, 3, 4, 6, 8, 9];
const band = v => HB.filter(t => v >= t).length;
const bandCol = i => RAMP[HSTOP[i]][1];
const onCol = c => { const Y = relL(c), dk = RAMP[0][1]; return 1.05 / (Y + 0.05) >= (Math.max(Y, relL(dk)) + 0.05) / (Math.min(Y, relL(dk)) + 0.05) ? '#FFFFFF' : dk; };
let SHOWVAL = true;
// Heatmap bands: 0–20, then 10-point steps to 90–100 (9 colours), spaced evenly along the ramp.
const HB12 = [20, 30, 40, 50, 60, 70, 80, 90], NB = HB12.length + 1;
const band12 = v => HB12.filter(t => v >= t).length;
const bandCol12 = i => civ(i / (NB - 1) * 100);
function heatmap() {
  const names = Object.keys(DATA.heat), years = [2000, 2005, 2010, 2015, 2020, 2024];
  // Names (~148 px at 15 px) + 12 px gap + 780 px of cells = 940 px, centred in the 1050 px chart.
  const lft = 215, rgt = 995, cw = (rgt - lft) / years.length, top = 72, rh = (446 - top) / names.length, gp = 4;
  let g = '';
  // Key: 'Coverage' + 12 px + 560 px bar, centred over the heatmap.
  const bw = 560 / NB, bx = 525 - (NB * bw - 84) / 2, by = -6, bh = 16;
  g += TM(bx - 12, by + bh / 2, 'Coverage', { size: 15, fill: AXIS, mid: true, anchor: 'end' });
  g += `<defs><clipPath id="k4-hm"><rect x="${bx}" y="${by}" width="${r1(NB * bw)}" height="${bh}" rx="5"/></clipPath></defs><g clip-path="url(#k4-hm)">`;
  for (let i = 0; i < NB; i++) g += `<rect x="${r1(bx + i * bw + (i ? 1 : 0))}" y="${by}" width="${r1(bw - (i ? 1 : 0) - (i < NB - 1 ? 1 : 0))}" height="${bh}" fill="${bandCol12(i)}"/>`;
  g += '</g>' + `<rect x="${bx}" y="${by}" width="${r1(NB * bw)}" height="${bh}" rx="5" fill="none" stroke="${GRID}" stroke-width="1"/>`;
  [0, ...HB12, 100].forEach((t, i) => { g += TM(bx + i * bw, by + bh + 18, t + '%', { size: 15, fill: AXIS, anchor: 'middle' }); });
  g += T(lft - 12, top - 9, 'A–Z', { size: 15, fill: MUTED, anchor: 'end' });
  years.forEach((yr, c) => { g += TM(lft + (c + 0.5) * cw, top - 9, yr, { size: 15, fill: AXIS, anchor: 'middle' }); });
  names.forEach((n, r) => {
    const y = top + r * rh;
    g += TM(lft - 12, y + rh / 2, n === 'Central African Republic' ? 'Central African Rep.' : n, { size: 15, anchor: 'end', mid: true });
    DATA.heat[n].forEach((v, c) => {
      const x = lft + c * cw + gp / 2, cx = lft + (c + 0.5) * cw, cy = y + rh / 2;
      if (v == null) { g += `<rect x="${r1(x)}" y="${r1(y + gp / 2)}" width="${r1(cw - gp)}" height="${r1(rh - gp)}" rx="4" fill="${LAND}"/>` + T(cx, cy, 'No data', { size: 15, fill: MUTED, anchor: 'middle', mid: true }); return; }
      const f = bandCol12(band12(v));
      g += `<rect x="${r1(x)}" y="${r1(y + gp / 2)}" width="${r1(cw - gp)}" height="${r1(rh - gp)}" rx="4" fill="${f}"/>`;
    });
  });
  return { body: g, label: `Heatmap of DTP3 coverage: rows are countries in alphabetical order (${names.join(', ')}), columns are the years 2000, 2005, 2010, 2015, 2020 and 2024. Cells are coloured in 9 bands: 0–20%, then 10-point steps to 90–100%; darker means lower coverage.` };
}

// Label offsets in px from each country's centroid. lead: drawn outside the country on a leader line
// (start/end: beside the leader's end; middle: above it; below: under it).
const LAB = {
  'Mali': [6, 3], 'Niger': [4, -4], 'Chad': [0, -10], 'Nigeria': [-2, 2], 'Central African Republic': [0, 0],
  'Democratic Republic of Congo': [-6, 0], 'Kenya': [1, 4], 'Tanzania': [0, 4], 'Zambia': [-9, 4],
  'Cameroon': [-32, 28, 'end'], 'Egypt': [0, 0], 'Libya': [0, 0], 'Sudan': [0, 0], 'Ethiopia': [5, -4],
  'Benin': [0, 30, 'below'], 'Burkina Faso': [-30, 40, 'end'], 'Somalia': [26, 6, 'start'], 'Uganda': [-6, -26, 'middle'], 'Mozambique': [22, 76, 'start', -6, 44], 'Madagascar': [24, 0, 'start'],
};
// Stepped key for the map: the heatmap's seven bands as separate rounded blocks, highest at the top,
// boundaries labelled between blocks, then a "No data" block.
function stepKey(kx, top) {
  const bh = 26, gp = 5, w = 22;
  let g = TM(kx, top - 16, 'Coverage', { size: 13, fill: AXIS });
  for (let i = 0; i < 7; i++) g += `<rect x="${kx}" y="${top + i * (bh + gp)}" width="${w}" height="${bh}" rx="4" fill="${bandCol(6 - i)}"/>`;
  [90, 80, 70, 60, 50, 40].forEach((v, i) => { g += TM(kx + w + 10, top + (i + 1) * (bh + gp) - gp / 2, v + '%', { size: 13, fill: AXIS, mid: true }); });
  g += TM(kx + w + 10, top, '100%', { size: 13, fill: AXIS, mid: true }) + TM(kx + w + 10, top + 7 * (bh + gp) - gp, '0%', { size: 13, fill: AXIS, mid: true });
  const ny = top + 7 * (bh + gp) + 14;
  g += `<rect x="${kx}" y="${ny}" width="${w}" height="${bh}" rx="4" fill="${LAND}" stroke="${GRID}" stroke-width="1"/>`;
  g += T(kx + w + 10, ny + bh / 2, 'No data', { size: 13, fill: MUTED, mid: true });
  return g;
}
function map(opts = {}, geo = GEO_AF, LABS = LAB, ox = 220, kx = 694, region = 'Africa') {
  const k = geo.k || 4.1, oy = 18, ns = ' vector-effect="non-scaling-stroke"', named = Object.entries(geo.named);
  const cid = 'mclip-' + region.replace(/\W/g, '');
  let g = geo.clip ? `<defs><clipPath id="${cid}"><rect x="${ox}" y="${oy}" width="${r1(geo.w * k)}" height="${r1(geo.h * k)}"/></clipPath></defs><g clip-path="url(#${cid})">` : '';
  g += `<g transform="translate(${ox},${oy}) scale(${k})">`;
  g += geo.land.concat(named.map(([, o]) => o.d)).map(d => `<path d="${d}" fill="none" stroke="${GRID}" stroke-width="2"${ns}/>`).join('');
  g += geo.land.map(d => `<path d="${d}" fill="${LAND}" stroke="#FFFFFF" stroke-width="1"${ns}/>`).join('');
  g += named.map(([n, o]) => `<path d="${o.d}" fill="${bandCol(band(geo.values[n]))}" stroke="#FFFFFF" stroke-width="1.25" stroke-linejoin="round"${ns}/>`).join('');
  g += geo.clip ? `</g></g>` : `</g>`;
  named.forEach(([n, o]) => {
    if (LABS[n] === false) return;
    const [dx, dy, lead, sx = 0, sy = 0] = LABS[n] || [0, 0], lines = geo.disp && geo.disp[n] ? [geo.disp[n]] : n === 'Central African Republic' ? ['CAR'] : n === 'United Kingdom' ? ['UK'] : SHORT[n] || [n], cx = ox + o.c[0] * k + dx, cy = oy + o.c[1] * k + dy, px = ox + o.c[0] * k + sx, py = oy + o.c[1] * k + sy;
    if (lead) {
      const ex = lead === 'end' ? cx + 4 : lead === 'start' ? cx - 4 : cx, ey = lead === 'middle' ? cy + 8 : lead === 'below' ? cy - 7 : cy;
      g += `<circle cx="${r1(px)}" cy="${r1(py)}" r="2" fill="${INK}"/>` + L(px, py, ex, ey, INK, 1);
      g += T(cx, cy, n, { size: 10, anchor: lead === 'below' ? 'middle' : lead, mid: true, weight: 700 });
      return;
    }
    const dark = darkFill(bandCol(band(geo.values[n])));
    lines.forEach((ln, j) => { g += T(cx, cy + (j - (lines.length - 1) / 2) * 11, ln, { size: geo.fs || 10, anchor: 'middle', mid: true, weight: 700, fill: dark ? '#FFFFFF' : INK }); });
  });
  g += stepKey(kx, PT + 40);
  return { body: g, label: `Map of ${region} coloured by DTP3 coverage in 2013 for ${named.length} countries: ${named.map(([n]) => n).join(', ')}. Other countries have no data. Darker means lower coverage.` };
}

// World exploration: Equal Earth, same bands and year, no names (too many small countries).
const mapworld = opts => map(opts, { ...GEO_W, k: 3.95 }, new Proxy({}, { get: () => false }), 16, 890, 'the world');
const B = { line, bar, scatter, heatmap, map, mapworld };
export function render(chart, cvd = 'none', opts = {}) {
  RN = RAMPS[opts.ramp] ? opts.ramp : 'warm'; RAMP = RAMPS[RN]; SHOWVAL = opts.values !== false;
  const { body, label } = B[chart](opts);
  const f = CVD[cvd] ? `<filter id="cvd4-${cvd}" color-interpolation-filters="linearRGB"><feColorMatrix type="matrix" values="${CVD[cvd]}"/></filter>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}" font-family="Helvetica, Arial, sans-serif" style="display:block;font-variant-numeric:tabular-nums"><defs>${f}</defs><g${f ? ` filter="url(#cvd4-${cvd})"` : ''}><rect width="${W}" height="${H}" fill="#FFFFFF"/><g transform="translate(0,16)">${body}</g></g></svg>`;
}

const TITLES = { line: 'DTP3 coverage, 2000–2024', bar: 'DTP3 coverage, 2017', scatter: 'DTP3 coverage, 2000 and 2024', heatmap: 'DTP3 coverage, selected years', map: 'DTP3 coverage, 2013', mapworld: 'DTP3 coverage, 2013' };
// Whole chart card (title band 30, chart 462, 10 gap, source line) as one scalable SVG, for the task screens.
export function card(chart, opts = {}) {
  RN = RAMPS[opts.ramp] ? opts.ramp : 'warm'; RAMP = RAMPS[RN]; SHOWVAL = opts.values !== false;
  const { body, label } = B[chart](opts);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1050 520" width="100%" role="img" aria-label="${esc(label)}" font-family="Helvetica, Arial, sans-serif" style="display:block;height:auto;font-variant-numeric:tabular-nums"><rect width="1050" height="520" fill="#FFFFFF"/>` +
    T(16, 21, TITLES[chart], { size: 18, weight: 700 }) + `<g transform="translate(0,46)">${body}</g>` +
    T(16, 514, 'Source: WHO/UNICEF coverage estimates (WUENIC), via Our World in Data. These are estimates; how reliably coverage is measured varies by country.', { size: 12, fill: MUTED }) + '</svg>';
}
