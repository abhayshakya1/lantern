// Routing by hash, the top bar chips, and the one fetch of the monitor payload.
window.Lantern = window.Lantern || {};
(function () {
  const L = window.Lantern;
  let payload = null;
  const TITLES = { monitor: 'AI-bubble monitor', research: 'Research desk', filings: 'Filings Q&A', rates: 'Rates and macro', modelrisk: 'Model risk', sources: 'Data sources', settings: 'Settings' };

  function chips(p) {
    const asof = new Date(p.as_of);
    document.getElementById('asof-text').textContent = 'As of ' + asof.toLocaleString('en-GB', { timeZone: 'Asia/Singapore', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) + ' SGT';
    document.getElementById('chip-model').textContent = `Model v${p.model.version} · run ${asof.toLocaleTimeString('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit' })}`;
    const badge = document.getElementById('chip-badge');
    badge.textContent = p.badge.label;
    badge.className = 'chip ' + p.badge.state;
    document.querySelector('#chip-asof .dot').style.background = p.badge.state === 'live' ? 'var(--good)' : p.badge.state === 'cached' ? 'var(--warn)' : 'var(--ink-3)';
  }

  async function load() {
    if (payload) return payload;
    const r = await fetch('/api/monitor');
    if (!r.ok) throw new Error((await r.json()).error || 'no data');
    payload = await r.json();
    chips(payload);
    return payload;
  }

  async function route() {
    const key = (location.hash || '#monitor').slice(1) || 'monitor';
    const target = key === 'overview' ? 'monitor' : key;
    document.querySelectorAll('.nav a').forEach((a) => a.classList.toggle('active', a.dataset.route === target || (target === 'monitor' && a.dataset.route === 'overview' && key === 'overview')));
    document.getElementById('crumb-title').textContent = TITLES[target] || 'AI-bubble monitor';
    document.getElementById('driver-panel').hidden = true;
    const root = document.getElementById('main');
    if (target === 'monitor') {
      try {
        L.monitor.render(root, await load());
      } catch (e) {
        root.innerHTML = `<div class="page"><h1>No model run yet</h1><p>Run <code>lantern pull</code>, <code>lantern backtest</code> and <code>lantern model</code>, then reload. (${e.message})</p></div>`;
      }
      return;
    }
    if (target === 'research') return L.research.render(root);
    if (target === 'filings') return L.filings.render(root);
    if (target === 'sources') return L.placeholders.sources(root);
    if (L.placeholders.PAGES[target]) return L.placeholders.page(root, target);
    location.hash = '#monitor';
  }

  window.addEventListener('hashchange', route);
  load().catch(() => {}).finally(route);
})();
