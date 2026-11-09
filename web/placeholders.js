// The modules that are labelled entries in this version, and the Data sources page.
window.Lantern = window.Lantern || {};
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PAGES = {
    rates: ['Rates and macro', 'A rates and macro transmission engine: SORA, Fed and HIBOR scenarios through to net interest income, and policy event studies. It answers the research finding that OCBC discloses a S$1,951m parallel-down NII loss while guiding NII flat.'],
    modelrisk: ['Model risk', 'Model inventory entries, materiality ratings, validation sets and prompt logs for every model, the evidence the MAS Guidelines on AI Risk Management ask for by about October 2027. The calibration curve and the gold-set scores land here.'],
    settings: ['Settings', 'Workspace name, data directory, API keys for the FRED feed and the language model, and the demo-morning schedule.'],
  };

  function page(root, key) {
    const [title, text] = PAGES[key];
    root.innerHTML = `<div class="page"><h1>${esc(title)}</h1><p>${esc(text)}</p></div>`;
    if (key === 'modelrisk') evalResults(root);
    if (key === 'modelrisk') challengerCoverage(root);
  }

  async function challengerCoverage(root) {
    const r = await fetch('/api/challenger').catch(() => null);
    if (!r || !r.ok) return;
    const d = await r.json();
    const b = d.backtest;
    if (!b) return;
    const champ = b.champion_coverage == null ? '—' : Math.round(b.champion_coverage * 100) + '%';
    const pr = d.prob;
    const probLine = pr ? `<p class="src">Probability challenger: ${esc(pr.model)} Brier ${Number(pr.brier_tabpfn).toFixed(3)} vs champion walk-forward ${Number(pr.brier_champion_wf).toFixed(3)} vs walk-forward base-rate Brier ${Number(pr.brier_base_rate_wf).toFixed(3)} on ${esc(String(pr.n))} months.</p>` : '';
    root.insertAdjacentHTML('beforeend', `<div class="page"><h2>Fan coverage, champion vs challenger</h2>
      <p class="src">Walk-forward ${esc(String(b.horizon_months))}-month ${esc(b.band)} coverage over ${esc(String(b.n))} months (target ${Math.round((b.target || 0.8) * 100)}%):
      champion (conditional history) ${champ} · ${esc(b.model)} ${Math.round(b.coverage * 100)}%.</p>${probLine}</div>`);
  }

  const fmt = (x, d = 2) => (x == null ? '—' : typeof x === 'number' ? x.toFixed(d) : String(x));

  async function evalResults(root) {
    const r = await fetch('/api/filings/eval').catch(() => null);
    if (!r || !r.ok) { root.insertAdjacentHTML('beforeend', '<p class="src">Filings Q&A gold-set evaluation: no run yet.</p>'); return; }
    const d = await r.json();
    const ab = d.abstention || {};
    const gate = d.gate || {};
    const rows = [
      ['Run', new Date(d.run_at).toLocaleString('en-GB', { timeZone: 'Asia/Singapore', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) + ' SGT'],
      ['Model', d.model], ['Judge', d.judge || 'none (deterministic metrics only)'], ['Questions', d.n],
      ['Abstention precision', fmt(ab.precision)], ['Abstention recall', fmt(ab.recall)],
      ['Release gate', `<span class="pill ${gate.pass ? 'calm' : 'high'}"><i></i>${gate.pass ? 'pass' : 'fail'}</span> precision ≥ ${fmt(gate.threshold)}`],
    ];
    let bfq = '';
    if (d.bfq && d.bfq.models) {
      for (const [model, m] of Object.entries(d.bfq.models)) {
        bfq += `<tr><th colspan="2">BharatFinQA harness · ${esc(model)}</th></tr>`;
        for (const [k, v] of Object.entries(m)) bfq += `<tr><td>${esc(k)}</td><td class="mono">${esc(typeof v === 'object' ? JSON.stringify(v) : fmt(v))}</td></tr>`;
      }
    }
    root.insertAdjacentHTML('beforeend', `<div class="card" style="margin-top:12px;max-width:720px"><div class="ch"><h2>Filings Q&A gold-set evaluation</h2></div><table>${rows.map(([k, v]) => `<tr><td style="width:220px;color:var(--ink-3)">${esc(k)}</td><td>${v}</td></tr>`).join('')}${bfq}</table></div>`);
  }

  async function sources(root) {
    root.innerHTML = '<div class="page"><h1>Data sources</h1><p>Every pull writes the raw response to disk with a UTC timestamp and a SHA-256 hash; the rows below are the latest 200 fetches.</p></div><div class="card" style="margin-top:12px"><div class="tbl"><table id="provenance"><thead><tr><th>Series</th><th>Pulled (SGT)</th><th>Status</th><th>SHA-256</th><th>Source</th></tr></thead><tbody></tbody></table></div></div>';
    const r = await fetch('/api/provenance');
    const rows = r.ok ? await r.json() : [];
    const body = root.querySelector('#provenance tbody');
    body.innerHTML = rows.map((p) => `<tr><td class="mono">${esc(p.name)}</td><td>${esc(new Date(p.fetched_at).toLocaleString('en-GB', { timeZone: 'Asia/Singapore', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }))}</td><td><span class="delta ${p.status === 'ok' ? 'dn' : 'up'}">${esc(p.status)}</span></td><td class="mono">${esc((p.sha256 || '').slice(0, 12))}</td><td style="color:var(--ink-3)">${esc(p.url)}</td></tr>`).join('') || '<tr><td colspan="5">No pulls yet.</td></tr>';
  }

  window.Lantern.placeholders = { page, sources, PAGES };
})();
