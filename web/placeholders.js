// The modules that are labelled entries in this version, and the Data sources page.
window.Lantern = window.Lantern || {};
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PAGES = {
    research: ['Research desk', 'Publishes dated research notes written from the model\'s own numbers, with the chart, the driver table and sources embedded, exportable to PDF, and keeps the accuracy ledger that compares each past forecast with what the market then did. Arrives with the next plan.'],
    rates: ['Rates and macro', 'A rates and macro transmission engine: SORA, Fed and HIBOR scenarios through to net interest income, and policy event studies. It answers the research finding that OCBC discloses a S$1,951m parallel-down NII loss while guiding NII flat.'],
    modelrisk: ['Model risk', 'Model inventory entries, materiality ratings, validation sets and prompt logs for every model, the evidence the MAS Guidelines on AI Risk Management ask for by about October 2027. The calibration curve and the gold-set scores land here.'],
    settings: ['Settings', 'Workspace name, data directory, API keys for the FRED feed and the language model, and the demo-morning schedule.'],
  };

  function page(root, key) {
    const [title, text] = PAGES[key];
    root.innerHTML = `<div class="page"><h1>${esc(title)}</h1><p>${esc(text)}</p></div>`;
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
