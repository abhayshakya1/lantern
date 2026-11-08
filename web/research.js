// Research desk: the note feed, the formatted note with its chart and sources, live generation, and the accuracy ledger.
window.Lantern = window.Lantern || {};
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const C = () => window.Lantern.charts;
  const SOURCE_LINE = { api: '', template: ' · template prose (the model draft was rejected or declined)', 'offline-template': ' · template prose (answer service offline)' };

  const fmtDate = (iso) => {
    const d = new Date(iso);
    return isNaN(d) ? '—' : d.toLocaleString('en-GB', { timeZone: 'Asia/Singapore', day: '2-digit', month: 'short', year: 'numeric' });
  };
  const pct = (v, dp = 0) => (v == null ? '—' : (v * 100).toFixed(dp) + '%');

  function render(root) {
    root.innerHTML = `
      <div class="head"><div><h1>Research desk</h1>
        <p>Dated notes written from the model run's own numbers: every figure in the prose traces to the run JSON, and the sources carry pull times and hashes.</p></div>
        <button id="generate-note">Generate today's note</button></div>
      <section class="grid">
        <div id="note-view" class="card answer"><p class="sub">Open a note from the feed, or generate today's.</p></div>
        <div>
          <div class="card side"><h2>Notes</h2><ul id="note-feed" class="history"><li class="ctx">Loading…</li></ul></div>
          <div class="card side"><h2>Accuracy ledger</h2>
            <div class="tbl"><table id="ledger"><thead><tr><th>Date</th><th class="num">Forecast</th><th class="num">Realised 12m</th><th>In fan</th><th></th></tr></thead><tbody></tbody></table></div>
            <p class="src">Backtest rows score each month's forecast against the realised 12-month return; live rows fill in as their horizons elapse.</p></div>
        </div>
      </section>`;
    loadFeed(root);
    loadLedger(root);
    root.querySelector('#generate-note').addEventListener('click', () => generate(root));
  }

  async function loadFeed(root, openId) {
    const feed = root.querySelector('#note-feed');
    try {
      const notes = await (await fetch('/api/research/notes')).json();
      feed.innerHTML = notes.map((n) => `
        <li class="note-row">
          <button class="open" data-id="${esc(n.id)}"><span class="name">${esc(n.title)}</span>
            <span class="desc">${fmtDate(n.created_at)} · ${esc(n.status)} · run ${esc(n.run_id)}</span>
            <span class="desc">${esc(n.summary)}</span></button>
          <a class="pdf" href="/api/research/note/${encodeURIComponent(n.id)}/pdf">PDF</a>
        </li>`).join('') || '<li class="ctx">No notes yet: generate today\'s.</li>';
      feed.querySelectorAll('.open').forEach((b) => b.addEventListener('click', () => openNote(root, b.dataset.id)));
      const first = openId || (notes[0] && notes[0].id);
      if (first) openNote(root, first);
    } catch (e) {
      feed.innerHTML = '<li class="ctx">The note feed could not be loaded.</li>';
    }
  }

  async function openNote(root, id) {
    const view = root.querySelector('#note-view');
    view.innerHTML = '<p class="sub">Loading the note…</p>';
    try {
      const r = await fetch('/api/research/note/' + encodeURIComponent(id));
      if (!r.ok) throw new Error((await r.json()).error || 'not found');
      const n = await r.json();
      view.innerHTML = `
        <h1>${esc(n.title)}</h1>
        <p class="byline sub">${esc(n.author)} · as of ${fmtDate(n.as_of)} · run ${esc(n.run_id)} · ${esc(n.status)}${esc(SOURCE_LINE[n.source] || '')}
          <a class="export-pdf" href="/api/research/note/${encodeURIComponent(n.id)}/pdf">Export PDF</a>
          <a href="/research/note/${encodeURIComponent(n.id)}/print" target="_blank" rel="noopener">Print view</a></p>
        <p class="note-lead">${esc(n.lead)}</p>
        <svg id="note-chart" width="100%" style="display:block"></svg>
        <p class="src">${esc(n.chart.source_line || '')}</p>
        ${n.commentary.map((c) => `<h3>${esc(c.driver)}</h3><p>${esc(c.text)}</p>`).join('')}
        <p>${esc(n.scenario_sentence)}</p>
        <h2>Drivers</h2>
        <div class="tbl"><table><thead><tr><th>Driver</th><th>Tier</th><th class="num">z</th><th class="num">pts</th></tr></thead>
        <tbody>${n.drivers.map((d) => `<tr><td>${esc(d.label || d.id)}</td><td>${esc(d.tier || '')}</td><td class="num">${d.z == null ? '—' : d.z.toFixed(1)}</td><td class="num">${d.contribution_pts == null ? '—' : d.contribution_pts.toFixed(1)}</td></tr>`).join('')}</tbody></table></div>
        <h2>Triggers</h2>
        <ul>${n.triggers.map((t) => `<li>${esc(t.label || t.id || '')}</li>`).join('') || '<li>None.</li>'}</ul>
        <h2>Sources</h2>
        <div class="tbl"><table><thead><tr><th>Series</th><th>Pulled</th><th>SHA</th></tr></thead>
        <tbody>${n.sources.map((s) => `<tr><td>${esc(s.name)}</td><td class="desc">${fmtDate(s.fetched_at)}</td><td class="mono sha">${esc((s.sha256 || '').slice(0, 12) || '—')}</td></tr>`).join('') || '<tr><td colspan="3">No source snapshot.</td></tr>'}</tbody></table></div>`;
      const svg = view.querySelector('#note-chart');
      if (n.chart && n.chart.price && n.chart.fan) C().lineFan(svg, n.chart, 'base');
      else svg.remove();
    } catch (e) {
      view.innerHTML = `<p class="sub">The note could not be loaded: ${esc(e.message)}</p>`;
    }
  }

  async function loadLedger(root) {
    const body = root.querySelector('#ledger tbody');
    try {
      const rows = await (await fetch('/api/research/ledger')).json();
      body.innerHTML = rows.slice(0, 60).map((r) => `
        <tr><td>${esc(r.date)}</td><td class="num">${pct(r.probability)}</td>
        <td class="num">${r.realised_return == null ? 'pending' : pct(r.realised_return, 1)}</td>
        <td>${r.inside_fan == null ? '—' : r.inside_fan ? 'yes' : 'no'}</td>
        <td class="desc">${esc(r.kind)}</td></tr>`).join('') || '<tr><td colspan="5">No ledger yet: run lantern backtest.</td></tr>';
    } catch (e) {
      body.innerHTML = '<tr><td colspan="5">The ledger could not be loaded.</td></tr>';
    }
  }

  async function generate(root) {
    const btn = root.querySelector('#generate-note');
    btn.disabled = true; btn.textContent = 'Generating…';
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 90000);
    try {
      const r = await fetch('/api/research/generate', { method: 'POST', signal: abort.signal });
      const n = await r.json();
      if (!r.ok) throw new Error(n.error || 'generation failed');
      await loadFeed(root, n.id);
    } catch (e) {
      root.querySelector('#note-view').innerHTML = `<p class="sub">The note could not be generated: ${esc(e.name === 'AbortError' ? 'timed out after 90 s' : e.message)}</p>`;
    } finally {
      clearTimeout(timer);
      btn.disabled = false; btn.textContent = "Generate today's note";
    }
  }

  window.Lantern.research = { render };
})();
