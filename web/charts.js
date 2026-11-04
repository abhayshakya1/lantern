// Hand-drawn SVG charts for the monitor. One axis per chart, hairline grid, thin marks, labels on the few points that matter.
window.Lantern = window.Lantern || {};
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const COLORS = { ink: '#171A1F', quiet: '#8A93A0', line: '#ECEEF1', axis: '#CFD5DC', accent: '#1F5FBF', fv: '#9AA3AE', s2: '#D96B2E', s3: '#1A9E74' };

  function el(tag, attrs, text) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function clear(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }
  function niceTicks(lo, hi, n) {
    const span = hi - lo || 1;
    const raw = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((s) => s * mag).find((s) => s >= raw) || mag * 10;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }
  const fmtPct = (x, d = 0) => (x >= 0 ? '+' : '−') + Math.abs(x * 100).toFixed(d) + '%';

  // Price against fair value with a forecast fan and three scenario paths.
  function lineFan(svg, chart, selected) {
    clear(svg);
    const W = 880, H = 300, mL = 44, mR = 150, mT = 14, mB = 30;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const N = chart.months.length - 1;
    const x = (i) => mL + (i * (W - mL - mR)) / N;
    const all = [].concat(chart.price, chart.fair_value, chart.fv_band.low, chart.fv_band.high, chart.fan.p10, chart.fan.p90,
      chart.scenarios.derating.path, chart.scenarios.meltup.path).filter((v) => v != null);
    const lo = Math.min(...all), hi = Math.max(...all);
    const pad = (hi - lo) * 0.08;
    const yMin = lo - pad, yMax = hi + pad;
    const y = (v) => mT + ((yMax - v) / (yMax - yMin)) * (H - mT - mB);
    const path = (vals, offset) => vals.map((v, i) => (i ? 'L' : 'M') + x(offset + i) + ' ' + y(v)).join(' ');

    for (const t of niceTicks(yMin, yMax, 5)) {
      svg.appendChild(el('line', { x1: mL, x2: W - mR, y1: y(t), y2: y(t), stroke: COLORS.line }));
      svg.appendChild(el('text', { x: mL - 8, y: y(t) + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono, monospace', 'font-size': 11, fill: COLORS.quiet }, Math.round(t)));
    }
    chart.months.forEach((m, i) => {
      if (i % 6 === 0 || i === N) svg.appendChild(el('text', { x: x(i), y: H - 8, 'text-anchor': 'middle', 'font-family': 'IBM Plex Mono, monospace', 'font-size': 11, fill: COLORS.quiet }, m));
    });
    svg.appendChild(el('line', { x1: mL, x2: W - mR, y1: y(yMin), y2: y(yMin), stroke: COLORS.axis }));

    // fair value band and line (history and forecast)
    const up = chart.fv_band.high.map((v, i) => (i ? 'L' : 'M') + x(i) + ' ' + y(v)).join(' ');
    const dn = chart.fv_band.low.map((v, i) => 'L' + x(N - i) + ' ' + y(chart.fv_band.low[N - i])).join(' ');
    svg.appendChild(el('path', { d: up + ' ' + dn + ' Z', fill: COLORS.fv, 'fill-opacity': 0.1 }));
    svg.appendChild(el('path', { d: path(chart.fair_value, 0), fill: 'none', stroke: COLORS.fv, 'stroke-width': 1.5 }));

    // forecast fan
    const todayIdx = chart.price.length - 1;
    const band = (hiArr, loArr) => hiArr.map((v, i) => (i ? 'L' : 'M') + x(todayIdx + i) + ' ' + y(v)).join(' ') +
      ' ' + loArr.map((v, i) => 'L' + x(todayIdx + loArr.length - 1 - i) + ' ' + y(loArr[loArr.length - 1 - i])).join(' ') + ' Z';
    svg.appendChild(el('path', { d: band(chart.fan.p90, chart.fan.p10), fill: COLORS.accent, 'fill-opacity': 0.08 }));
    svg.appendChild(el('path', { d: band(chart.fan.p75, chart.fan.p25), fill: COLORS.accent, 'fill-opacity': 0.14 }));

    // scenario paths
    const sc = chart.scenarios;
    const styles = { derating: [COLORS.s2, 1.5], meltup: [COLORS.s3, 1.5], base: [COLORS.accent, 2] };
    for (const key of ['derating', 'meltup', 'base']) {
      const [color, w] = styles[key];
      svg.appendChild(el('path', { d: path(sc[key].path, todayIdx), fill: 'none', stroke: color, 'stroke-width': selected === key ? w + 1.5 : w, 'stroke-dasharray': '5 4', 'stroke-linejoin': 'round', opacity: selected && selected !== key ? 0.45 : 1 }));
    }
    // today rule and price line
    svg.appendChild(el('line', { x1: x(todayIdx), x2: x(todayIdx), y1: mT, y2: y(yMin), stroke: COLORS.axis, 'stroke-dasharray': '3 4' }));
    svg.appendChild(el('text', { x: x(todayIdx) + 5, y: mT + 10, 'font-family': 'IBM Plex Sans, sans-serif', 'font-size': 11, fill: COLORS.quiet }, 'Today'));
    svg.appendChild(el('path', { d: path(chart.price, 0), fill: 'none', stroke: COLORS.accent, 'stroke-width': 2, 'stroke-linejoin': 'round' }));
    const pToday = chart.price[todayIdx];
    svg.appendChild(el('circle', { cx: x(todayIdx), cy: y(pToday), r: 4, fill: COLORS.accent, stroke: '#fff', 'stroke-width': 2 }));

    // end labels
    const labels = [
      ['meltup', `Melt-up ${Math.round(sc.meltup.path[12])} · ${fmtPct(sc.meltup.end_return)} · ${Math.round(sc.meltup.prob * 100)}%`, COLORS.s3],
      ['base', `Base ${Math.round(sc.base.path[12])} · ${fmtPct(sc.base.end_return)} · ${Math.round(sc.base.prob * 100)}%`, COLORS.accent],
      ['derating', `De-rating ${Math.round(sc.derating.path[12])} · ${fmtPct(sc.derating.end_return)} · ${Math.round(sc.derating.prob * 100)}%`, COLORS.s2],
    ];
    let lastY = -100;
    labels.map(([k, t, c]) => ({ k, t, c, y: y(sc[k].path[12]) })).sort((a, b) => a.y - b.y).forEach((l) => {
      const yy = Math.max(l.y, lastY + 14);
      lastY = yy;
      svg.appendChild(el('text', { x: x(N) + 8, y: yy + 4, 'font-family': 'IBM Plex Sans, sans-serif', 'font-size': 11.5, 'font-weight': 500, fill: l.c }, l.t));
    });
    const gap = chart.gap_today;
    svg.appendChild(el('text', { x: x(todayIdx) - 8, y: y(pToday) - 10, 'text-anchor': 'end', 'font-family': 'IBM Plex Sans, sans-serif', 'font-size': 11.5, 'font-weight': 500, fill: COLORS.ink },
      `${Math.round(pToday)}` + (gap == null ? '' : ` · ${fmtPct(gap)} vs fair value`)));
    const fvToday = chart.fair_value[todayIdx];
    if (fvToday != null) svg.appendChild(el('text', { x: x(todayIdx) - 8, y: y(fvToday) + 14, 'text-anchor': 'end', 'font-family': 'IBM Plex Sans, sans-serif', 'font-size': 11, fill: '#596270' }, `Fair value ${Math.round(fvToday)}`));
  }

  function spark(svg, values, color) {
    clear(svg);
    const w = 72, h = 26;
    svg.setAttribute('width', w); svg.setAttribute('height', h);
    const pts = values.filter((v) => v != null);
    if (pts.length < 2) return;
    const min = Math.min(...pts), max = Math.max(...pts);
    const d = pts.map((v, i) => (i ? 'L' : 'M') + (2 + (i * (w - 4)) / (pts.length - 1)).toFixed(1) + ' ' + (h - 3 - ((v - min) / (max - min || 1)) * (h - 6)).toFixed(1)).join(' ');
    svg.appendChild(el('path', { d, fill: 'none', stroke: color || COLORS.accent, 'stroke-width': 1.5 }));
    const last = pts[pts.length - 1];
    svg.appendChild(el('circle', { cx: w - 2, cy: h - 3 - ((last - min) / (max - min || 1)) * (h - 6), r: 2.5, fill: color || COLORS.accent }));
  }

  function zbar(container, z) {
    if (z == null) { container.innerHTML = '<span class="ztext">—</span>'; return; }
    const pct = Math.min(Math.abs(z) / 3, 1) * 50;
    const color = z >= 1.5 ? '#C62828' : z >= 0.8 ? '#B7791F' : z >= 0 ? '#1F5FBF' : '#1E8E3E';
    const left = z >= 0 ? 50 : 50 - pct;
    container.innerHTML = `<span class="z"><i></i><b style="left:${left}%;width:${pct}%;background:${color}"></b></span><span class="ztext">${z >= 0 ? '+' : ''}${z.toFixed(1)}σ</span>`;
  }

  function segbar(container, probs) {
    const order = [['base', 'Base', 'var(--accent)'], ['derating', 'De-rating', 'var(--s2)'], ['meltup', 'Melt-up', 'var(--s3)']];
    container.innerHTML = `<div class="segbar">${order.map(([k, , c]) => `<b style="width:${(probs[k] * 100).toFixed(1)}%;background:${c}"></b>`).join('')}</div>` +
      `<div class="segleg">${order.map(([k, l, c]) => `<span><i style="background:${c}"></i>${l} ${Math.round(probs[k] * 100)}%</span>`).join('')}</div>`;
  }

  function tableView(container, chart) {
    const todayIdx = chart.price.length - 1;
    const rows = chart.months.map((m, i) => {
      const f = (arr, off) => (arr && arr[i - off] != null ? Math.round(arr[i - off]) : '');
      return `<tr><td>${m}</td><td class="num">${i <= todayIdx ? Math.round(chart.price[i]) : ''}</td><td class="num">${Math.round(chart.fair_value[i])}</td><td class="num">${f(chart.fan.p10, todayIdx)}</td><td class="num">${f(chart.fan.p50, todayIdx)}</td><td class="num">${f(chart.fan.p90, todayIdx)}</td></tr>`;
    });
    container.innerHTML = `<table class="table-view"><thead><tr><th>Month</th><th class="num">Price</th><th class="num">Fair value</th><th class="num">p10</th><th class="num">p50</th><th class="num">p90</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
  }

  // Simple line of a driver's history for the detail panel.
  function line(svg, points, color) {
    clear(svg);
    const W = 400, H = 160, mL = 44, mR = 12, mT = 10, mB = 24;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const pts = points.filter((p) => p.value != null);
    if (pts.length < 2) return;
    const vals = pts.map((p) => p.value);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.1 || 1;
    const y = (v) => mT + ((hi + pad - v) / (hi - lo + 2 * pad)) * (H - mT - mB);
    const x = (i) => mL + (i * (W - mL - mR)) / (pts.length - 1);
    for (const t of niceTicks(lo - pad, hi + pad, 4)) {
      svg.appendChild(el('line', { x1: mL, x2: W - mR, y1: y(t), y2: y(t), stroke: COLORS.line }));
      svg.appendChild(el('text', { x: mL - 6, y: y(t) + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono, monospace', 'font-size': 10, fill: COLORS.quiet }, +t.toFixed(2)));
    }
    [0, Math.floor(pts.length / 2), pts.length - 1].forEach((i) => svg.appendChild(el('text', { x: x(i), y: H - 6, 'text-anchor': i === 0 ? 'start' : i === pts.length - 1 ? 'end' : 'middle', 'font-family': 'IBM Plex Mono, monospace', 'font-size': 10, fill: COLORS.quiet }, pts[i].date.slice(0, 7))));
    svg.appendChild(el('path', { d: pts.map((p, i) => (i ? 'L' : 'M') + x(i) + ' ' + y(p.value)).join(' '), fill: 'none', stroke: color || COLORS.accent, 'stroke-width': 1.5, 'stroke-linejoin': 'round' }));
  }

  window.Lantern.charts = { lineFan, spark, zbar, segbar, tableView, line, fmtPct };
})();
