// Browser smoke test for the monitor screen. Run: LANTERN_URL=http://127.0.0.1:8787 node smoke.mjs
import fs from 'node:fs';
import puppeteer from 'puppeteer-core';

const url = process.env.LANTERN_URL || 'http://127.0.0.1:8787';
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const failures = [];
const fail = (msg) => failures.push(msg);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.setViewport({ width: 1440, height: 1000 });
  await page.goto(url + '/#monitor', { waitUntil: 'networkidle0', timeout: 60000 });
  await wait(300);

  const tile = await page.$eval('[data-tile="probability"] .v', (el) => el.textContent).catch(() => null);
  if (!tile || !/\d{1,2}\s*%/.test(tile)) fail('probability tile not found');

  const paths = await page.$$eval('#main-chart path', (els) => els.length).catch(() => 0);
  if (paths < 8) fail(`main chart has ${paths} paths`);

  const before = await page.$eval('#scenario-sentence', (el) => el.textContent).catch(() => '');
  await page.click('[data-scenario="derating"]').catch(() => fail('scenario control missing'));
  await wait(200);
  const after = await page.$eval('#scenario-sentence', (el) => el.textContent).catch(() => '');
  if (!before || before === after) fail('scenario sentence did not change');

  await page.click('#driver-table tbody tr').catch(() => fail('driver table row missing'));
  await wait(400);
  const panel = await page.$eval('#driver-panel', (el) => el.textContent).catch(() => '');
  if (!/weight/i.test(panel)) fail('driver panel did not open with its weight');

  const text = await page.$eval('#main', (el) => el.textContent).catch(() => '');
  if (/\b(null|NaN|undefined)\b/.test(text)) fail('main shows null, NaN or undefined');
  if (!/Brier/.test(text)) fail('calibration footer missing');
  if (!/watch/i.test(text)) fail('watch indicators not marked');
  // Filings Q&A page: corpus table, a prepared question answered from the cache or abstained, history rail
  const prepared = JSON.parse(fs.readFileSync(new URL('../data/filings/prepared_questions.json', import.meta.url), 'utf8'));
  await page.goto(url + '/#filings', { waitUntil: 'networkidle0', timeout: 60000 });
  await wait(300);
  const rows = await page.$$eval('#corpus-table tbody tr', (els) => els.length).catch(() => 0);
  if (rows < 1) fail('corpus table missing');
  const form = await page.$('#ask-form');
  if (!form) fail('ask form missing');
  else {
    await page.type('#ask-input', prepared[0]);
    await page.click('#ask-form button[type="submit"]');
    for (let i = 0; i < 40; i++) { await wait(250); if (await page.$('#answer .evidence, #answer .abstain, #answer .offline')) break; }
    const answerText = await page.$eval('#answer', (el) => el.textContent).catch(() => '');
    const hasEvidence = await page.$('#answer .evidence');
    if (!hasEvidence && !/do not answer this|offline/.test(answerText)) fail('answer card shows neither evidence nor the abstention or offline sentence');
    if (/\b(null|NaN|undefined)\b/.test(answerText)) fail('answer shows null, NaN or undefined');
    const items = await page.$$eval('#history li', (els) => els.length).catch(() => 0);
    if (items < 1) fail('history rail empty');
  }
  // Research desk: feed, note view with chart and sources, accuracy ledger
  await page.goto(url + '/#research', { waitUntil: 'networkidle0', timeout: 60000 });
  await wait(400);
  const noteRows = await page.$$eval('#note-feed .note-row', (els) => els.length).catch(() => 0);
  if (noteRows < 1) fail('research feed has no notes (run lantern note first)');
  if (!(await page.$('#generate-note'))) fail('generate button missing');
  const pdfHref = await page.$eval('#note-feed .note-row a.pdf', (el) => el.getAttribute('href')).catch(() => '');
  if (!/\/api\/research\/note\/.+\/pdf/.test(pdfHref)) fail('feed PDF link missing');
  await page.click('#note-feed .note-row .open').catch(() => fail('note open control missing'));
  await wait(500);
  const byline = await page.$eval('#note-view .byline', (el) => el.textContent).catch(() => '');
  if (!byline.includes('Lantern model, reviewed by Abhay')) fail('note author line missing');
  const noteView = await page.$eval('#note-view', (el) => el.textContent).catch(() => '');
  if (!/Sources/.test(noteView) || !/[0-9a-f]{8}/.test(noteView)) fail('note sources with hashes missing');
  if (!/Drivers/.test(noteView) || !/Triggers/.test(noteView)) fail('note driver table or triggers missing');
  if (!(await page.$('#note-view svg'))) fail('note chart svg missing');
  if (!(await page.$('#note-view a.export-pdf'))) fail('note export PDF link missing');
  const ledgerRows = await page.$$eval('#ledger tbody tr', (els) => els.length).catch(() => 0);
  if (ledgerRows < 1) fail('accuracy ledger empty');
  const ledgerText = await page.$eval('#ledger', (el) => el.textContent).catch(() => '');
  if (!/backtest/.test(ledgerText)) fail('ledger backtest tag missing');
  const researchText = await page.$eval('#main', (el) => el.textContent).catch(() => '');
  if (/\b(null|NaN|undefined)\b/.test(researchText)) fail('research shows null, NaN or undefined');
  // LLM prose must arrive escaped: render a crafted note through the real module with fetch stubbed
  const escVerdict = await page.evaluate(async () => {
    const hostile = 'L <b>bold</b> <img src=x onerror=window.__pwned=1>';
    const note = { id: 'x', title: 'T <b>t</b>', summary: 's', author: 'Lantern model, reviewed by Abhay',
      as_of: '2026-11-08', created_at: '2026-11-08', status: 'Draft', source: 'api', run_id: 'r',
      lead: hostile, commentary: [{ driver: 'D <i>d</i>', text: 'c <b>c</b>' }], scenario_sentence: 's',
      drivers: [], triggers: [], tiles: {}, chart: { source_line: '' }, sources: [] };
    const feed = [{ id: 'x', title: note.title, summary: 's', status: 'Draft', run_id: 'r', created_at: '2026-11-08' }];
    const control = document.createElement('div');
    control.innerHTML = 'x <b>y</b>'; // proves the detector sees unescaped HTML (no img: its onerror would fire here)
    const detectorWorks = !!control.querySelector('b');
    control.remove();
    const realFetch = window.fetch;
    window.fetch = (url) => Promise.resolve({ ok: true, json: () => Promise.resolve(String(url).includes('/note/') ? note : String(url).includes('/notes') ? feed : []) });
    const div = document.createElement('div');
    document.body.appendChild(div);
    try {
      window.Lantern.research.render(div);
      await new Promise((r) => setTimeout(r, 400));
    } finally { window.fetch = realFetch; }
    const injected = !!div.querySelector('b, i, img');
    const literal = div.textContent.includes('<b>bold</b>');
    const pwned = !!window.__pwned;
    div.remove();
    return { detectorWorks, injected, literal, pwned };
  }).catch(() => null);
  if (!escVerdict) fail('escape check could not run');
  else {
    if (!escVerdict.detectorWorks) fail('escape detector is blind');
    if (escVerdict.injected || escVerdict.pwned || !escVerdict.literal) fail('note prose is not escaped');
  }
  if (errors.length) fail('console errors: ' + errors.join(' | '));
} finally {
  await browser.close();
}
if (failures.length) {
  console.error('smoke FAIL\n - ' + failures.join('\n - '));
  process.exit(1);
}
console.log('smoke ok');
