// Chart directions sheet: draws the five Form A charts as SVG strings, one style per direction.
// Plot area is 400 px for 0-100 on every chart (4 px a point, as study-design §4 assumes).
import { DATA } from './chart-data.js';

export const W = 1050, H = 446;
const PT = 22, PB = 422;
const yv = v => PB - v * 4;
const SERIES = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#960600', '#062AA8', '#246648', '#845472'];
const SHAPES = ['circle', 'square', 'diamond', 'triangle-up', 'x', 'triangle-down', 'cross', 'star'];
const CIV = [[0, '#00224E'], [0.111, '#123570'], [0.222, '#3B496C'], [0.333, '#575D6D'], [0.444, '#707173'], [0.556, '#8A8678'], [0.667, '#A59C74'], [0.778, '#C3B369'], [0.889, '#E1CC55'], [1, '#FEE838']];
const INK = '#241C18', MUTED = '#5F544D';
// Sequential scales without yellow (2026-10-09). Built in OKLCH; lightness rises 12-15 -> 91-92 L*,
// 0.77-0.79 L* a point, and stays monotonic under simulated protanopia and deuteranopia. White
// borders reach 4.0:1 at 50% on each.
export const RAMPS = {
  cividis: CIV,
  blue: [[0,"#0A2347"],[0.111,"#0A3569"],[0.222,"#08498A"],[0.333,"#095EA9"],[0.444,"#1A75C3"],[0.556,"#348DD8"],[0.667,"#54A5E8"],[0.778,"#78BDF4"],[0.889,"#9ED4FD"],[1,"#CCE9FF"]],
  teal: [[0,"#1F1B41"],[0.111,"#242F62"],[0.222,"#1E4681"],[0.333,"#086098"],[0.444,"#037BA6"],[0.556,"#0996B3"],[0.667,"#16B2BF"],[0.778,"#4FCAC6"],[0.889,"#87E0CD"],[1,"#B9F4D9"]],
  warm: [[0,"#3B1D15"],[0.111,"#572B1B"],[0.222,"#733A20"],[0.333,"#8E4C27"],[0.444,"#A76132"],[0.556,"#BD7944"],[0.667,"#CF935C"],[0.778,"#E0AD7B"],[0.889,"#EEC99E"],[1,"#FCE4C4"]],
};
let RAMP = CIV, RAMPN = 'cividis', BARMODE = 'single';

const S = {
  a: { tick: 13, lab: 13, axis: '#4A3F38', grid: '#BBAEA4', minor: null, vgrid: true, axisLine: true, lineW: 2.5, labGap: 18, dotR: 6, keyW: 18, cellGap: 2, land: '#EEE8E2', coast: '#BBAEA4', border: 1 },
  q: { tick: 12, lab: 12, axis: '#5F544D', grid: '#DDD3CA', minor: null, vgrid: false, axisLine: false, lineW: 2, labGap: 16, dotR: 5, keyW: 10, cellGap: 2, land: '#EEE8E2', coast: null, border: 1 },
  h: { tick: 16, lab: 16, axis: '#3E342E', grid: '#A89A8F', minor: '#E4D8CC', vgrid: true, axisLine: true, lineW: 3.5, labGap: 22, dotR: 9, keyW: 22, cellGap: 3, land: 'url(#hatch)', coast: '#A89A8F', border: 2 },
};

const CVD = {
  protanopia: '0.152286 1.052583 -0.204868 0 0 0.114503 0.786281 0.099216 0 0 -0.003882 -0.048116 1.051998 0 0 0 0 0 1 0',
  deuteranopia: '0.367322 0.860646 -0.227968 0 0 0.280085 0.672501 0.047413 0 0 -0.011820 0.042940 0.968881 0 0 0 0 0 1 0',
  tritanopia: '1.255528 -0.076749 -0.178779 0 0 -0.078411 0.930809 0.147602 0 0 0.004733 0.691367 0.303900 0 0 0 0 0 1 0',
  greyscale: '0.2126 0.7152 0.0722 0 0 0.2126 0.7152 0.0722 0 0 0.2126 0.7152 0.0722 0 0 0 0 0 1 0',
};

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const r1 = v => Math.round(v * 10) / 10;
function T(x, y, s, o = {}) {
  return `<text x="${r1(x)}" y="${r1(y)}" font-size="${o.size || 13}" fill="${o.fill || INK}"` +
    (o.anchor ? ` text-anchor="${o.anchor}"` : '') + (o.weight ? ` font-weight="${o.weight}"` : '') +
    (o.mid ? ` dominant-baseline="central"` : '') +
    (o.halo ? ` stroke="${o.halo}" stroke-width="3" stroke-linejoin="round" paint-order="stroke"` : '') +
    (o.rot ? ` transform="rotate(${o.rot} ${r1(x)} ${r1(y)})"` : '') + `>${esc(s)}</text>`;
}
const L = (x1, y1, x2, y2, c, w = 1, extra = '') => `<line x1="${r1(x1)}" y1="${r1(y1)}" x2="${r1(x2)}" y2="${r1(y2)}" stroke="${c}" stroke-width="${w}"${extra}/>`;

function shape(kind, x, y, r, fill, outline) {
  const st = outline ? ` stroke="${outline}" stroke-width="1.2"` : '';
  const P = pts => `<polygon points="${pts.map(p => p.map(r1).join(',')).join(' ')}" fill="${fill}"${st}/>`;
  switch (kind) {
    case 'circle': return `<circle cx="${r1(x)}" cy="${r1(y)}" r="${r}" fill="${fill}"${st}/>`;
    case 'square': { const s = r * 0.88; return `<rect x="${r1(x - s)}" y="${r1(y - s)}" width="${r1(2 * s)}" height="${r1(2 * s)}" fill="${fill}"${st}/>`; }
    case 'diamond': { const d = r * 1.22; return P([[x, y - d], [x + d, y], [x, y + d], [x - d, y]]); }
    case 'triangle-up': return P([[x, y - r * 1.2], [x + r * 1.1, y + r * 0.8], [x - r * 1.1, y + r * 0.8]]);
    case 'triangle-down': return P([[x, y + r * 1.2], [x + r * 1.1, y - r * 0.8], [x - r * 1.1, y - r * 0.8]]);
    case 'x': { const a = r * 0.95, w = r * 0.36; return P([[x - a, y - a + w], [x - a + w, y - a], [x, y - w], [x + a - w, y - a], [x + a, y - a + w], [x + w, y], [x + a, y + a - w], [x + a - w, y + a], [x, y + w], [x - a + w, y + a], [x - a, y + a - w], [x - w, y]]); }
    case 'cross': { const a = r * 1.05, w = r * 0.34; return P([[x - w, y - a], [x + w, y - a], [x + w, y - w], [x + a, y - w], [x + a, y + w], [x + w, y + w], [x + w, y + a], [x - w, y + a], [x - w, y + w], [x - a, y + w], [x - a, y - w], [x - w, y - w]]); }
    case 'star': { const pts = []; for (let i = 0; i < 10; i++) { const ang = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.55 : r * 1.3; pts.push([x + rr * Math.cos(ang), y + rr * Math.sin(ang)]); } return P(pts); }
  }
  return '';
}

function spread(ps, gap, lo, hi) {
  const n = ps.length, blocks = [];
  ps.map((p, i) => p - i * gap).forEach(v => {
    blocks.push([v, 1]);
    while (blocks.length > 1 && blocks[blocks.length - 2][0] > blocks[blocks.length - 1][0]) {
      const [m, s] = blocks.pop(), [pm, psz] = blocks.pop();
      blocks.push([(pm * psz + m * s) / (psz + s), psz + s]);
    }
  });
  const w = []; blocks.forEach(([m, s]) => { for (let i = 0; i < s; i++) w.push(m); });
  const ceil = hi - (n - 1) * gap;
  return w.map((v, i) => Math.min(Math.max(v, lo), ceil) + i * gap);
}

const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
function civ(v) {
  const t = Math.max(0, Math.min(1, v / 100));
  for (let i = 1; i < RAMP.length; i++) if (t <= RAMP[i][0]) {
    const [p0, c0] = RAMP[i - 1], [p1, c1] = RAMP[i], f = (t - p0) / (p1 - p0);
    const a = hex(c0), b = hex(c1);
    return '#' + a.map((x, k) => Math.round(x + (b[k] - x) * f).toString(16).padStart(2, '0')).join('');
  }
  return RAMP[RAMP.length - 1][1];
}

function yAxis(s, left, right, title, { every = 10, grid = true } = {}) {
  let g = '';
  for (let v = 0; v <= 100; v += 10) {
    const y = yv(v);
    if (grid && !(v === 0 && s.axisLine)) g += L(left, y, right, y, v === 0 ? '#BBAEA4' : s.grid, 1);
    if (v % every === 0) g += T(left - 8, y, v, { size: s.tick, fill: s.axis, anchor: 'end', mid: true });
  }
  if (s.axisLine) g += L(left, PB, right, PB, s.axis, 1) + L(left, PT, left, PB, s.axis, 1);
  if (title) g += T(16, s === S.h ? 12 : 14, title, { size: s.lab, fill: s.axis, weight: s === S.h ? 700 : 400 });
  return g;
}

function svgWrap(dir, cvd, label, body) {
  const s = S[dir];
  const defs = `<defs>` +
    (CVD[cvd] ? `<filter id="cvd-${cvd}" color-interpolation-filters="linearRGB"><feColorMatrix type="matrix" values="${CVD[cvd]}"/></filter>` : '') +
    `<pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="7" height="7" fill="#F4EFEA"/><line x1="0" y1="0" x2="0" y2="7" stroke="#D5C9BF" stroke-width="1.6"/></pattern>` +
    `</defs>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}" font-family="Helvetica, Arial, sans-serif" style="display:block;font-variant-numeric:tabular-nums">${defs}<g${CVD[cvd] ? ` filter="url(#cvd-${cvd})"` : ''}><rect width="${W}" height="${H}" fill="#FFFFFF"/>${body}</g></svg>`;
}

// ---------- Line ----------
function line(dir) {
  const s = S[dir], names = Object.keys(DATA.line);
  const lft = dir === 'h' ? 62 : dir === 'q' ? 46 : 52, rgt = dir === 'h' ? 840 : dir === 'q' ? 900 : 860;
  const x = yr => lft + (yr - 1999.5) / 25 * (rgt - lft);
  let g = '';
  if (s.minor) for (let yr = 2000; yr <= 2024; yr++) if (yr % 5) g += L(x(yr), PT, x(yr), PB, s.minor, 1);
  if (s.vgrid) for (let yr = 2000; yr <= 2020; yr += 5) g += L(x(yr), PT, x(yr), PB, s.grid, 1);
  g += yAxis(s, lft, rgt, 'Coverage (%)');
  for (let yr = 2000; yr <= 2020; yr += 5) g += T(x(yr), PB + (dir === 'h' ? 21 : 18), yr, { size: s.tick, fill: s.axis, anchor: 'middle' });
  const ends = [];
  names.forEach((n, i) => {
    const c = SERIES[i], vals = DATA.line[n];
    let d = '', prev = null;
    vals.forEach((v, k) => { if (v == null) { prev = null; return; } d += (prev == null ? 'M' : 'L') + r1(x(2000 + k)) + ',' + r1(yv(v)); prev = v; });
    g += `<path d="${d}" fill="none" stroke="${c}" stroke-width="${s.lineW}" stroke-linejoin="round" stroke-linecap="round"/>`;
    vals.forEach((v, k) => {
      if (v == null) return;
      const isEnd = k === vals.length - 1 || vals.slice(k + 1).every(u => u == null);
      if (dir === 'a') g += `<circle cx="${r1(x(2000 + k))}" cy="${r1(yv(v))}" r="2.6" fill="${c}"/>`;
      else if (dir === 'h') g += shape(SHAPES[i], x(2000 + k), yv(v), 4.6, c, '#FFFFFF');
      else if (isEnd) g += `<circle cx="${r1(x(2000 + k))}" cy="${r1(yv(v))}" r="3" fill="${c}"/>`;
    });
    let k = vals.length - 1; while (k >= 0 && vals[k] == null) k--;
    if (k >= 0) ends.push({ n, i, c, xe: x(2000 + k), ye: yv(vals[k]), v: vals[k] });
  });
  ends.sort((a, b) => a.ye - b.ye);
  const ys = spread(ends.map(e => e.ye), s.labGap, PT - 10, PB);
  ends.forEach((e, j) => {
    const yl = ys[j];
    if (dir === 'a') {
      g += `<polyline points="${r1(e.xe + 5)},${r1(e.ye)} ${r1(e.xe + 14)},${r1(yl)} ${r1(e.xe + 22)},${r1(yl)}" fill="none" stroke="${e.c}" stroke-width="1.6"/>`;
      g += `<text x="${r1(e.xe + 27)}" y="${r1(yl)}" font-size="13" dominant-baseline="central" fill="${INK}">${esc(e.n)}<tspan fill="${MUTED}" dx="6">${e.v}%</tspan></text>`;
    } else if (dir === 'h') {
      g += `<polyline points="${r1(e.xe + 7)},${r1(e.ye)} ${r1(e.xe + 16)},${r1(yl)} ${r1(e.xe + 22)},${r1(yl)}" fill="none" stroke="${e.c}" stroke-width="2"/>`;
      g += shape(SHAPES[e.i], e.xe + 31, yl, 6, e.c);
      g += T(e.xe + 44, yl, e.n, { size: 16, weight: 700, mid: true });
    } else {
      if (Math.abs(yl - e.ye) > 1.5) g += `<polyline points="${r1(e.xe + 5)},${r1(e.ye)} ${r1(e.xe + 12)},${r1(yl)}" fill="none" stroke="${e.c}" stroke-width="1"/>`;
      g += T(e.xe + 15, yl, e.n, { size: 12, fill: MUTED, mid: true });
    }
  });
  return { body: g, label: `Line chart of DTP3 coverage, 2000 to 2024, one line per country: ${names.join(', ')}. Vertical axis 0 to 100 percent.` };
}

// ---------- Bar ----------
function bar(dir) {
  const s = S[dir], names = Object.keys(DATA.bar);
  const lft = dir === 'h' ? 62 : dir === 'q' ? 46 : 52, rgt = 1026;
  const slot = (rgt - lft) / names.length, frac = dir === 'h' ? 0.66 : dir === 'q' ? 0.34 : 0.56;
  let g = yAxis(s, lft, rgt, 'Coverage (%)');
  names.forEach((n, i) => {
    const v = DATA.bar[n], cx = lft + slot * (i + 0.5), bw = slot * frac;
    const fill = BARMODE === 'value' ? civ(v) : BARMODE === 'series' ? SERIES[i] : SERIES[0];
    g += `<rect x="${r1(cx - bw / 2)}" y="${r1(yv(v))}" width="${r1(bw)}" height="${r1(v * 4)}" fill="${fill}"${BARMODE === 'value' ? ` stroke="${s.axis}" stroke-width="1"` : ''}/>`;
    if (dir === 'h') for (let t = 10; t < v; t += 10) g += L(cx - bw / 2, yv(t), cx + bw / 2, yv(t), '#FFFFFF', 1.5, ' stroke-opacity="0.85"');
    g += T(cx, PB + (dir === 'h' ? 21 : 18), n, { size: s.tick, fill: dir === 'h' ? INK : s.axis, anchor: 'middle', weight: dir === 'h' ? 700 : 400 });
  });
  if (s.axisLine) g += L(lft, PB, rgt, PB, s.axis, 1);
  if (dir === 'a') g += T(rgt, 14, 'Countries in alphabetical order', { size: 13, fill: MUTED, anchor: 'end' });
  return { body: g, label: `Bar chart of DTP3 coverage in 2017, one bar per country in alphabetical order: ${names.join(', ')}. Vertical axis 0 to 100 percent.` };
}

// ---------- Scatter ----------
function scatter(dir) {
  const s = S[dir], names = Object.keys(DATA.sc);
  const xl = dir === 'a' ? 300 : 250, xv = v => xl + v * 4;
  let g = '';
  for (let v = 0; v <= 100; v += 10) {
    if (!(v === 0 && s.axisLine)) g += L(xv(v), PT, xv(v), PB, v === 0 ? '#BBAEA4' : s.grid, 1) + L(xl, yv(v), xl + 400, yv(v), v === 0 ? '#BBAEA4' : s.grid, 1);
    g += T(xl - 8, yv(v), v, { size: s.tick, fill: s.axis, anchor: 'end', mid: true });
    g += T(xv(v), PB + (dir === 'h' ? 21 : 18), v, { size: s.tick, fill: s.axis, anchor: 'middle' });
  }
  if (s.axisLine) g += L(xl, PB, xl + 400, PB, s.axis, 1) + L(xl, PT, xl, PB, s.axis, 1);
  const bold = dir === 'h' ? 700 : 400;
  g += T(xl - 40, dir === 'h' ? 12 : 14, '↑ Coverage in 2024 (%)', { size: s.lab, fill: s.axis, weight: bold });
  g += T(xl + 412, PB - 2, 'Coverage in 2000 (%) →', { size: s.lab, fill: s.axis, weight: bold });
  g += L(xv(0), yv(0), xv(100), yv(100), s.axis, dir === 'h' ? 2 : 1.5, ' stroke-dasharray="6 5"');
  const nc = dir === 'a' ? 78 : 14;
  const halo = 'rgba(255,255,255,.92)';
  g += T(xv(nc), yv(nc) - 8, 'no change', { size: s.tick, fill: MUTED, anchor: 'middle', rot: -45, halo });
  if (dir === 'a') {
    g += T(xv(2), yv(96), 'Above the line: higher in 2024 than in 2000', { size: 13, fill: MUTED, halo });
    g += T(xv(98), yv(18), 'Below the line: lower in 2024 than in 2000', { size: 13, fill: MUTED, anchor: 'end', halo });
  }
  const side = { 'Burkina Faso': 1, 'Chad': 1, 'Ethiopia': -1, 'Mali': 1, 'Niger': -1, 'Nigeria': -1 };
  names.forEach((n, i) => {
    const [a, b] = DATA.sc[n], px = xv(a), py = yv(b);
    g += shape(SHAPES[i], px, py, s.dotR, SERIES[i], '#FFFFFF');
    if (dir === 'a') g += T(px + side[n] * 12, py, n, { size: 13, anchor: side[n] > 0 ? 'start' : 'end', mid: true, halo: 'rgba(255,255,255,.85)' });
  });
  if (dir !== 'a') {
    const lx = xl + 470, row = dir === 'h' ? 32 : 22;
    names.forEach((n, i) => {
      const y = PT + 16 + i * row;
      g += shape(SHAPES[i], lx, y, dir === 'h' ? 8 : 5, SERIES[i]);
      g += T(lx + (dir === 'h' ? 18 : 13), y, n, { size: s.lab, mid: true, fill: dir === 'h' ? INK : MUTED, weight: bold });
    });
  }
  return { body: g, label: `Scatter plot of DTP3 coverage, one mark per country: coverage in 2000 across, coverage in 2024 up, with a dashed no-change diagonal. Countries: ${names.join(', ')}.` };
}

// ---------- Colour key (heatmap, map) ----------
function colourKey(dir, kx, top, h, extra = '') {
  const s = S[dir], w = s.keyW, id = `civ-${dir}-${RAMPN}`;
  let g = `<defs><linearGradient id="${id}" x1="0" y1="1" x2="0" y2="0">${RAMP.map(([p, c]) => `<stop offset="${p}" stop-color="${c}"/>`).join('')}</linearGradient></defs>`;
  g += T(kx, top - 14, 'Coverage (%)', { size: s.lab, fill: s.axis, weight: dir === 'h' ? 700 : 400 });
  g += `<rect x="${kx}" y="${top}" width="${w}" height="${h}" fill="url(#${id})"/>`;
  if (dir !== 'q') g += `<rect x="${kx}" y="${top}" width="${w}" height="${h}" fill="none" stroke="${s.axis}" stroke-width="1"/>`;
  const steps = dir === 'q' ? [0, 25, 50, 75, 100] : [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
  steps.forEach(v => {
    const y = top + h - v / 100 * h;
    g += L(kx + w, y, kx + w + 5, y, s.axis, 1);
    g += T(kx + w + 9, y, v, { size: s.tick, fill: s.axis, mid: true });
  });
  if (dir !== 'q') g += T(kx, top + h + (dir === 'h' ? 26 : 22), 'Darker means lower', { size: s.lab, fill: MUTED });
  return g + extra;
}

// ---------- Heatmap ----------
function heatmap(dir) {
  const s = S[dir], names = Object.keys(DATA.heat), years = [2000, 2005, 2010, 2015, 2020, 2024];
  const lft = dir === 'h' ? 236 : dir === 'q' ? 186 : 196, rgt = 840, cw = (rgt - lft) / years.length, rh = 400 / names.length, gp = s.cellGap;
  let g = '';
  names.forEach((n, r) => {
    const y = PT + r * rh;
    DATA.heat[n].forEach((v, c) => { if (v != null) g += `<rect x="${r1(lft + c * cw + gp / 2)}" y="${r1(y + gp / 2)}" width="${r1(cw - gp)}" height="${r1(rh - gp)}" fill="${civ(v)}"/>`; });
    g += T(lft - 10, y + rh / 2, n, { size: s.tick, anchor: 'end', mid: true, fill: dir === 'q' ? MUTED : INK, weight: dir === 'h' ? 700 : 400 });
  });
  years.forEach((yr, c) => { g += T(lft + (c + 0.5) * cw, PB + (dir === 'h' ? 21 : 18), yr, { size: s.tick, fill: s.axis, anchor: 'middle' }); });
  g += colourKey(dir, 900, PT + 34, 300);
  return { body: g, label: `Heatmap of DTP3 coverage: rows are countries (${names.join(', ')}), columns are the years 2000, 2005, 2010, 2015, 2020 and 2024. Darker cells mean lower coverage.` };
}

// ---------- Map ----------
const SHORT = { 'Democratic Republic of Congo': ['DR Congo'], 'Central African Republic': ['Central', 'African Rep.'] };
const OFF = { 'Mozambique': [16, -16], 'Tanzania': [0, 4], 'Kenya': [14, 4], 'Uganda': [-9, 2], 'Cameroon': [2, 14], 'Zambia': [-4, 4], 'Niger': [4, -6], 'Mali': [8, 6], 'Chad': [0, -14], 'Nigeria': [-2, 2], 'Central African Republic': [0, 0], 'Democratic Republic of Congo': [-6, 0], 'Madagascar': [40, 0] };
function map(dir) {
  const s = S[dir], geo = DATA.geo, k = 4.3, ox = 240, oy = 6;
  let g = `<g transform="translate(${ox},${oy}) scale(${k})">`;
  const all = geo.land.concat(Object.values(geo.named).map(o => o.d));
  if (s.coast) g += all.map(d => `<path d="${d}" fill="none" stroke="${s.coast}" stroke-width="2" vector-effect="non-scaling-stroke"/>`).join('');
  g += geo.land.map(d => `<path d="${d}" fill="${s.land}" stroke="#FFFFFF" stroke-width="${s.border}" vector-effect="non-scaling-stroke"/>`).join('');
  Object.entries(geo.named).forEach(([n, o]) => { g += `<path d="${o.d}" fill="${civ(DATA.map[n])}" stroke="#FFFFFF" stroke-width="${s.border}" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`; });
  g += `</g>`;
  if (dir === 'a') Object.entries(geo.named).forEach(([n, o]) => {
    const v = DATA.map[n], [dx, dy] = OFF[n] || [0, 0], lines = SHORT[n] || [n];
    const cx = ox + o.c[0] * k + dx, cy = oy + o.c[1] * k + dy, dark = v < 50;
    lines.forEach((ln, j) => { g += T(cx, cy + (j - (lines.length - 1) / 2) * 13, ln, { size: 11.5, anchor: 'middle', mid: true, fill: dark ? '#FFFFFF' : INK, weight: 700, halo: dark ? 'rgba(0,34,78,.55)' : 'rgba(255,255,255,.75)' }); });
  });
  const kx = 770;
  const sw = dir === 'h' ? 'url(#hatch)' : s.land, sy = PT + 34 + 300 + (dir === 'q' ? 36 : 52);
  const swatch = `<rect x="${kx}" y="${sy}" width="${dir === 'h' ? 26 : 18}" height="${dir === 'h' ? 18 : 12}" fill="${sw}" stroke="${dir === 'q' ? 'none' : s.grid}"/>` +
    T(kx + (dir === 'h' ? 34 : 26), sy + (dir === 'h' ? 9 : 6), 'Not in this question', { size: s.lab, fill: MUTED, mid: true });
  g += colourKey(dir, kx, PT + 34, 300, swatch);
  return { body: g, label: `Map of sub-Saharan Africa coloured by DTP3 coverage in 2013 for ${Object.keys(DATA.map).length} countries: ${Object.keys(DATA.map).join(', ')}. Other countries are not part of the question. Darker means lower coverage.` };
}

const B = { line, bar, scatter, heatmap, map };
export function render(dir, chart, cvd = 'none', opts = {}) {
  RAMPN = RAMPS[opts.ramp] ? opts.ramp : 'cividis'; RAMP = RAMPS[RAMPN]; BARMODE = opts.bar || 'single';
  const { body, label } = B[chart](dir);
  return svgWrap(dir, cvd, label, body);
}

export const _h = { T, L, shape, spread, esc, r1, hex, SERIES, SHAPES, INK, MUTED, CVD, OFF, SHORT };
