// Filings Q&A: question box, answer with verbatim evidence cards and page links, abstention with context, history rail, corpus table.
window.Lantern = window.Lantern || {};
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const CONF = { high: ['calm', 'High confidence'], medium: ['elevated', 'Medium confidence'], low: ['high', 'Low confidence'] };
  const SOURCE = { api: 'answered by the model', cache: 'answered from this morning\'s cache', none: 'nothing retrieved', offline: 'answer service offline', refusal: 'the model declined' };
  const asked = [];

  function fmtDate(iso) {
    const d = new Date(iso);
    return isNaN(d) ? '—' : d.toLocaleString('en-GB', { timeZone: 'Asia/Singapore', day: '2-digit', month: 'short', year: 'numeric' });
  }

  function render(root) {
    root.innerHTML = `
      <div class="head"><div><h1>Filings Q&amp;A</h1>
        <p>Answers come only from the eight annual reports in the corpus, each with the verbatim passage, the filing and the page. When the filings do not answer, the page says so.</p></div></div>
      <section class="grid filings">
        <div>
          <form id="ask-form" class="card ask" autocomplete="off">
            <input id="ask-input" type="text" maxlength="500" placeholder="Ask about any of the eight filings, for example: What was OCBC's net profit for 2025?">
            <button type="submit">Ask</button>
          </form>
          <div id="answer" class="card answer"><p class="sub">Ask a question to see the answer, its evidence and the page it comes from.</p></div>
          <div class="card side"><h2>This session</h2><ul id="history" class="history"><li class="ctx">No questions yet.</li></ul></div>
        </div>
        <div class="card side"><h2>Corpus</h2>
          <div class="tbl"><table id="corpus-table"><thead><tr><th>Company</th><th class="num">Pages</th><th class="num">No text</th><th>Ingested · SHA</th></tr></thead><tbody></tbody></table></div>
          <p class="src" id="index-line"></p>
        </div>
      </section>`;
    loadCorpus(root);
    const form = root.querySelector('#ask-form');
    form.addEventListener('submit', (ev) => { ev.preventDefault(); ask(root, root.querySelector('#ask-input').value); });
  }

  async function loadCorpus(root) {
    const body = root.querySelector('#corpus-table tbody');
    try {
      const r = await fetch('/api/filings/corpus');
      const d = await r.json();
      body.innerHTML = d.filings.map((m) => `<tr><td><div class="name">${esc(m.company)}</div><div class="desc">${esc(m.ticker)} · ${esc(m.filing)}</div></td><td class="num">${m.pages || '—'}</td><td class="num">${m.pages_without_text ?? '—'}</td><td><div class="desc">${m.ingested_at ? fmtDate(m.ingested_at) : 'not yet'}</div><div class="mono sha">${esc((m.sha256 || '').slice(0, 12) || '—')}</div></td></tr>`).join('') || '<tr><td colspan="4">No filings in the manifest.</td></tr>';
      root.querySelector('#index-line').textContent = d.index ? `${d.index.n_chunks.toLocaleString()} chunks · ${d.index.embed_model} · built ${fmtDate(d.index.built_at)}` : 'No index yet: run lantern filings build.';
    } catch (e) {
      body.innerHTML = '<tr><td colspan="6">The corpus list could not be loaded.</td></tr>';
    }
  }

  async function ask(root, question) {
    question = (question || '').trim();
    if (!question) return;
    const btn = root.querySelector('#ask-form button');
    const card = root.querySelector('#answer');
    btn.disabled = true; btn.textContent = 'Asking…';
    card.innerHTML = '<p class="sub">Searching the filings…</p>';
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 60000);
    try {
      const r = await fetch('/api/filings/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }), signal: abort.signal });
      const a = await r.json();
      if (!r.ok) { card.innerHTML = `<p class="offline">${esc(a.error || 'The server returned an error')} (HTTP ${r.status})</p>`; return; }
      card.innerHTML = answerHtml(a);
      if (!asked.includes(question)) asked.unshift(question);
      renderHistory(root);
    } catch (e) {
      card.innerHTML = e.name === 'AbortError' ? '<p class="offline">The answer took longer than a minute; the question is logged, try again.</p>' : '<p class="offline">The server could not be reached.</p>';
    } finally {
      clearTimeout(timer);
      btn.disabled = false; btn.textContent = 'Ask';
    }
  }

  function answerHtml(a) {
    const meta = `<p class="src">${esc(SOURCE[a.source] || a.source)}${a.latency_ms ? ` · ${a.latency_ms.toLocaleString()} ms` : ''}${a.model && a.source === 'api' ? ` · ${esc(a.model)}` : ''}</p>`;
    const context = (a.context || []).length
      ? `<p class="ctx-title">Nearest passages, shown as context, not as an answer</p><ul class="context">${a.context.slice(0, 5).map((c) => `<li><span class="mono">${esc(c.ticker)} · page ${c.page}</span> ${esc(c.text.slice(0, 300))}${c.text.length > 300 ? '…' : ''}</li>`).join('')}</ul>`
      : '';
    if (a.source === 'offline') return `<p class="offline">${esc(a.text)}</p>${context}${meta}`;
    if (!a.answerable) return `<p class="abstain">${esc(a.text)}</p>${context}${meta}`;
    const conf = CONF[a.confidence] || ['elevated', 'Confidence ' + esc(a.confidence)];
    return `<p class="answer-text">${esc(a.text)}</p><span class="pill ${conf[0]}"><i></i>${conf[1]}</span>` +
      a.evidence.map((e) => `<div class="evidence"><blockquote>${esc(e.quote)}</blockquote><div class="ev-meta">${esc(e.ticker)} · ${esc(e.filing)} · page ${e.page}<a target="_blank" rel="noopener" href="${esc(e.pdf_url)}">Open page</a></div></div>`).join('') + meta;
  }

  function renderHistory(root) {
    const ul = root.querySelector('#history');
    ul.innerHTML = asked.map((q) => `<li><button type="button">${esc(q)}</button></li>`).join('') || '<li class="ctx">No questions yet.</li>';
    ul.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { root.querySelector('#ask-input').value = b.textContent; ask(root, b.textContent); }));
  }

  window.Lantern.filings = { render };
})();
