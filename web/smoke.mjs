// Browser smoke test for the monitor screen. Run: LANTERN_URL=http://127.0.0.1:8787 node smoke.mjs
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
  if (errors.length) fail('console errors: ' + errors.join(' | '));
} finally {
  await browser.close();
}
if (failures.length) {
  console.error('smoke FAIL\n - ' + failures.join('\n - '));
  process.exit(1);
}
console.log('smoke ok');
