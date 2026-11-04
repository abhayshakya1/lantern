// Renders the AI-bubble monitor screen from the /api/monitor payload, and the driver detail panel.
window.Lantern = window.Lantern || {};
(function () {
  const C = () => window.Lantern.charts;
  const pct = (x, d = 0) => (x == null ? '—' : (x * 100).toFixed(d) + '%');
  const signedPct = (x, d = 0) => (x == null ? '—' : (x >= 0 ? '+' : '−') + Math.abs(x * 100).toFixed(d) + '%');
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const num = (x, d = 0) => (x == null ? '—' : x.toFixed(d));
  const signed = (x, d = 1, unit = '') => (x == null ? '—' : (x >= 0 ? '+' : '') + x.toFixed(d) + unit);
  const STATUS = { calm: 'Calm', elevated: 'Elevated', high: 'High' };
  const SCENARIO_TEXT = {
    base: (s, m) => `Base case: the basket ends near ${Math.round(s.path[12])} by ${m} (${C().fmtPct(s.end_return)}), probability ${Math.round(s.prob * 100)}%.`,
    derating: (s, m) => `De-rating case: a 25% drawdown takes the basket to about ${Math.round(s.path[12])} by ${m}, probability ${Math.round(s.prob * 100)}%.`,
    meltup: (s, m) => `Melt-up case: a 20% gain takes the basket to about ${Math.round(s.path[12])} by ${m}, probability ${Math.round(s.prob * 100)}%.`,
  };

  function tile(id, label, value, unit, rowHtml) {
    return `<div class="card kpi" data-tile="${id}"><div class="l">${label}</div><div class="v">${value}<small>${unit}</small></div><div class="row">${rowHtml}<svg data-spark="${id}"></svg></div></div>`;
  }

  function deltaClass(x, invert) {
    if (x == null || Math.abs(x) < 1e-9) return 'flat';
    const up = x > 0;
    return (invert ? !up : up) ? 'up' : 'dn';
  }

  function render(root, p) {
    const t = p.tiles, ch = p.chart;
    const lastMonth = ch.months[ch.months.length - 1];
    const prob = t.probability;
    root.innerHTML = `
      <div class="head">
        <div><h1>AI-bubble monitor</h1>
          <p>AI capex basket <span class="tick">${p.basket.tickers.join(' · ')}</span>, equal-weighted, indexed to 100 at ${esc(p.basket.index_base)}</p></div>
        <div class="seg" id="scenario-control">
          <button data-scenario="base" class="on">Base</button><button data-scenario="derating">De-rating</button><button data-scenario="meltup">Melt-up</button>
        </div>
      </div>
      <section class="kpis">
        ${tile('probability', '12-month de-rating probability', prob.value == null ? '—' : Math.round(prob.value * 100), '%',
          `<span class="pill ${prob.status}"><i></i>${STATUS[prob.status] || prob.status}</span><span class="d ${deltaClass(prob.delta_1m)}">${signedPct(prob.delta_1m)} pts</span>`)}
        ${tile('fv_gap', 'Price vs model fair value', t.fv_gap.value == null ? '—' : signedPct(t.fv_gap.value), t.fv_gap.value == null ? '' : '',
          `<span class="ctx">${t.fv_gap.value == null ? 'no fair value this month' : /^no real-yield/.test(p.model.fair_value_note || '') ? 'plain 10-yr median multiple: no real-yield feed' : `80% range ${signedPct(t.fv_gap.low)} to ${signedPct(t.fv_gap.high)}`}</span>`)}
        ${tile('forward_pe', 'Basket trailing P/E', t.forward_pe.trailing_pe == null ? '—' : t.forward_pe.trailing_pe.toFixed(1), 'x',
          `<span class="ctx">10-yr median ${t.forward_pe.median_10y == null ? '—' : t.forward_pe.median_10y.toFixed(1)}x${t.forward_pe.value == null ? '' : ` · forward ${t.forward_pe.value.toFixed(1)}x`}</span>`)}
        ${tile('capex_ocf', 'Hyperscaler capex to cash flow', t.capex_ocf.value == null ? '—' : Math.round(t.capex_ocf.value * 100), '%',
          t.capex_ocf.delta_vs_2024 == null ? '<span class="ctx">trailing four quarters</span>' : `<span class="d ${deltaClass(t.capex_ocf.delta_vs_2024)}">${signedPct(t.capex_ocf.delta_vs_2024)} pts vs 2024</span>`)}
        ${tile('top10', 'Top-10 weight in S&P 500', t.top10.value == null ? '—' : (t.top10.value * 100).toFixed(1), '%', `<span class="ctx">2000 peak ${pct(t.top10.peak_2000, 1)} (published figure)</span>`)}
      </section>
      <section class="grid">
        <div class="card ch">
          <div class="t"><h2>Basket price against model fair value, with the 12-month forecast</h2></div>
          <p class="sub" id="scenario-sentence"></p>
          <div class="legend">
            <span><i class="sw"></i>Basket price</span><span><i class="sw fv"></i>Model fair value</span><span><i class="sw band"></i>Forecast, 25 to 75 and 10 to 90 pct</span>
            <span><i class="sw dash"></i>Base case</span><span><i class="sw s2 dash"></i>De-rating</span><span><i class="sw s3 dash"></i>Melt-up</span>
          </div>
          <svg id="main-chart" width="100%" style="display:block"></svg>
          <div class="src"><span>${esc(ch.source_line)}</span><span>Conditional window ±${ch.window_band} composite points</span><button id="table-toggle" type="button">Table view</button></div>
          <div id="table-view" hidden></div>
        </div>
        <div class="card side">
          <h2>What would change the call</h2>
          <div>${p.triggers.map((tr) => `
            <div class="trig"><span class="n">${esc(tr.label)}</span><span class="m">${tr.current == null ? 'no reading' : fmtReading(tr)} · trigger ${fmtLevel(tr)}</span>
              <div class="bar"><b style="width:${tr.distance == null ? 0 : Math.round(tr.distance * 100)}%"></b><i style="left:100%"></i></div>
              <span class="k">${esc(tr.text)} (${signed(tr.effect_pts, 0, ' pts')})</span></div>`).join('')}</div>
          <div><h3>Scenario probabilities, 12 months</h3><div id="scenario-bar"></div></div>
        </div>
      </section>
      <section class="card" style="margin-bottom:12px">
        <div class="ch" style="padding-bottom:0"><div class="t"><h2>Drivers, ranked by contribution to the probability</h2></div>
          <p class="sub">Seven inputs, each scored against its own 10-year history. Positive contributions raise the de-rating probability. Click a row for its history and sources.</p></div>
        <div class="tbl"><table id="driver-table">
          <thead><tr><th>Driver</th><th>Current reading</th><th>Versus 10-year history</th><th class="num">Contribution</th><th>24-month trend</th><th class="num">Change, 1 month</th></tr></thead>
          <tbody>${p.drivers.map((d) => `
            <tr data-driver="${d.id}"><td><div class="name">${esc(d.label)}</div></td><td><div class="desc">${esc(d.reading_text)}</div></td>
              <td data-z="${d.id}"></td><td class="num">${signed(d.contribution_pts, 0, ' pts')}</td>
              <td><svg data-spark="d-${d.id}"></svg></td><td class="num"><span class="delta ${deltaClass(d.change_1m_z)}">${signed(d.change_1m_z, 1, 'σ')}</span></td></tr>`).join('')}</tbody>
        </table></div>
        <div class="tfoot"><span>${calibrationText(p.model.calibration)}</span><span>Model v${esc(p.model.version)}</span></div>
      </section>
      <section class="notes">${p.notes.map((n) => `<div class="card note"><div class="d">${esc(fmtDate(n.date))}</div><div class="h">${esc(n.title)}</div><p>${esc(n.text)}</p></div>`).join('')}</section>`;

    // charts and widgets
    const chart = Object.assign({}, ch, { gap_today: t.fv_gap.value });
    const main = root.querySelector('#main-chart');
    let selected = 'base';
    const draw = () => { C().lineFan(main, chart, selected); root.querySelector('#scenario-sentence').textContent = SCENARIO_TEXT[selected](ch.scenarios[selected], lastMonth); };
    draw();
    root.querySelectorAll('#scenario-control button').forEach((b) => b.addEventListener('click', () => {
      selected = b.dataset.scenario;
      root.querySelectorAll('#scenario-control button').forEach((x) => x.classList.toggle('on', x === b));
      draw();
    }));
    C().spark(root.querySelector('[data-spark="probability"]'), prob.spark);
    C().spark(root.querySelector('[data-spark="fv_gap"]'), t.fv_gap.spark);
    C().spark(root.querySelector('[data-spark="forward_pe"]'), t.forward_pe.spark);
    C().spark(root.querySelector('[data-spark="capex_ocf"]'), t.capex_ocf.spark);
    C().spark(root.querySelector('[data-spark="top10"]'), t.top10.spark);
    C().segbar(root.querySelector('#scenario-bar'), { base: ch.scenarios.base.prob, derating: ch.scenarios.derating.prob, meltup: ch.scenarios.meltup.prob });
    p.drivers.forEach((d) => { C().zbar(root.querySelector(`[data-z="${d.id}"]`), d.z); C().spark(root.querySelector(`[data-spark="d-${d.id}"]`), d.spark, '#596270'); });
    root.querySelectorAll('#driver-table tbody tr').forEach((tr) => tr.addEventListener('click', () => openDriver(tr.dataset.driver)));
    root.querySelector('#table-toggle').addEventListener('click', () => {
      const tv = root.querySelector('#table-view');
      if (tv.hidden) C().tableView(tv, ch);
      tv.hidden = !tv.hidden;
    });
  }

  function calibrationText(c) {
    const fit = c.in_sample === false ? 'out-of-sample' : 'in-sample';
    let s = `Penalised logistic model, ${fit} fit on monthly data ${esc(c.start)} to ${esc(c.end)} (${c.n_months} months): Brier ${num(c.brier, 3)} against ${num(c.brier_base, 3)} for always predicting the base rate.`;
    if (c.b != null && c.b <= 0) s += ' The slope is at its floor (0.00): no driver moves the probability this month, and the table ranks by z-score.';
    return s;
  }

  function fmtReading(tr) {
    if (tr.current == null) return 'no reading';
    if (tr.unit === '%') return tr.current.toFixed(2) + '%';
    if (tr.unit === 'ratio' || tr.unit === 'share') return (tr.current * 100).toFixed(1) + '%';
    if (tr.unit === 'growth') return (tr.current >= 0 ? '−' : '+') + Math.abs(tr.current * 100).toFixed(1) + '% earnings';
    return tr.current.toFixed(2);
  }
  function fmtLevel(tr) {
    if (tr.unit === '%') return tr.level.toFixed(2) + '%';
    if (tr.unit === 'ratio' || tr.unit === 'share') return (tr.level * 100).toFixed(0) + '%';
    if (tr.unit === 'growth') return 'earnings falling';
    return tr.level.toFixed(2);
  }
  function fmtDate(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString('en-GB', { timeZone: 'Asia/Singapore', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) + ' SGT';
  }

  async function openDriver(id) {
    const panel = document.getElementById('driver-panel');
    panel.hidden = false;
    panel.innerHTML = '<p class="loading">Loading…</p>';
    const r = await fetch(`/api/drivers/${id}`);
    if (!r.ok) { panel.innerHTML = '<p>Driver not found.</p>'; return; }
    const d = await r.json();
    panel.innerHTML = `
      <button class="close" type="button" aria-label="Close">×</button>
      <h2>${esc(d.label)}</h2>
      <p class="desc">${esc(d.reading_text || '')}</p>
      <svg id="driver-history" width="100%" style="display:block;margin:8px 0"></svg>
      <dl>
        <dt>Weight</dt><dd>${(d.weight * 100).toFixed(0)}% of the composite</dd>
        <dt>Current z</dt><dd class="mono">${d.z == null ? 'no reading' : signed(d.z, 2, 'σ')}, contributing ${signed(d.contribution_pts, 1, ' pts')}</dd>
        <dt>Data as of</dt><dd>${esc(d.asof || '—')}</dd>
        ${d.note ? `<dt>Note</dt><dd>${esc(d.note)}</dd>` : ''}
        <dt>Source</dt><dd>${esc(d.source)}</dd>
        <dt>Transform</dt><dd>${esc(d.transform)}</dd>
        <dt>Proxy</dt><dd>${d.proxy_before ? `Proxy used before ${esc(d.proxy_before)}` : 'None'}</dd>
        <dt>Trigger</dt><dd>${d.trigger ? `${esc(d.trigger.text)} (${d.trigger.direction} ${d.trigger.level == null ? 'the 10-year mean' : d.trigger.level})` : 'None'}</dd>
        <dt>Conditional drawdown share</dt><dd>${pct(d.conditional_drawdown_share)} of months with a composite near today's saw a 25% drawdown within 12 months</dd>
      </dl>`;
    panel.querySelector('.close').addEventListener('click', () => { panel.hidden = true; });
    const pts = d.history.filter((h) => h.reading != null);
    panel.querySelector('#driver-history').hidden = pts.length < 2;
    C().line(panel.querySelector('#driver-history'), pts.map((h) => ({ date: h.date, value: h.reading })));
  }

  window.Lantern.monitor = { render, openDriver };
})();
