// Record the demo scenes as 1080p webm segments with an animated cursor, click ripples and eased zooms.
// Run from demo/: node record.mjs   (the app must be serving on LANTERN_URL, default http://127.0.0.1:8787)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

import { scenes } from './scenes.mjs';

const require = createRequire(new URL('../web/package.json', import.meta.url));
const puppeteer = require('puppeteer-core');

const DIR = path.dirname(fileURLToPath(import.meta.url));
const URL_BASE = process.env.LANTERN_URL || 'http://127.0.0.1:8787';
const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const RAW = path.join(DIR, 'out', 'raw');
fs.mkdirSync(RAW, { recursive: true });

const INJECT = `(() => {
  if (window.__demo) return;
  const cur = document.createElement('div');
  cur.id = '__cursor';
  cur.style.cssText = 'position:fixed;left:960px;top:540px;width:26px;height:26px;z-index:999999;pointer-events:none;' +
    'transition:left .65s cubic-bezier(.33,.0,.2,1),top .65s cubic-bezier(.33,.0,.2,1);';
  cur.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 2 L20 12 L12 13.5 L9 21 Z" fill="#111" stroke="#fff" stroke-width="1.6"/></svg>';
  const style = document.createElement('style');
  style.textContent = '@keyframes __rip{from{transform:translate(-50%,-50%) scale(.3);opacity:.55}to{transform:translate(-50%,-50%) scale(2.4);opacity:0}}' +
    '.__ripple{position:fixed;width:44px;height:44px;border-radius:50%;background:#1F5FBF;z-index:999998;pointer-events:none;animation:__rip .7s ease-out forwards}' +
    'body{transition:transform .9s cubic-bezier(.45,.0,.15,1)}';
  const attach = () => { document.body.appendChild(cur); document.head.appendChild(style); };
  document.body ? attach() : addEventListener('DOMContentLoaded', attach);
  window.__demo = {
    move(x, y) { cur.style.left = x - 3 + 'px'; cur.style.top = y - 2 + 'px'; },
    ripple(x, y) {
      const r = document.createElement('div');
      r.className = '__ripple'; r.style.left = x + 'px'; r.style.top = y + 'px';
      document.body.appendChild(r); setTimeout(() => r.remove(), 750);
    },
    zoom(sel, scale) {
      const el = document.querySelector(sel);
      if (!el) return false;
      const b = el.getBoundingClientRect();
      const cx = b.left + b.width / 2 + scrollX, cy = b.top + b.height / 2 + scrollY;
      document.body.style.transformOrigin = cx + 'px ' + cy + 'px';
      document.body.style.transform = 'scale(' + scale + ')';
      return true;
    },
    unzoom() { document.body.style.transform = 'none'; },
  };
})();`;

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

function helpers(page) {
  const center = async (sel) => {
    const b = await page.evaluate((s) => {
      const el = document.querySelector(s);
      if (!el) return null;
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }, sel);
    if (!b) throw new Error(`selector not found: ${sel}`);
    return b;
  };
  return {
    pause,
    async click(sel, { ripple = true } = {}) {
      const { x, y } = await center(sel);
      await page.evaluate((px, py) => window.__demo.move(px, py), x, y);
      await pause(800);
      if (ripple) await page.evaluate((px, py) => window.__demo.ripple(px, py), x, y);
      await pause(250);
      await page.mouse.click(x, y);
      await pause(400);
    },
    async type(sel, text) {
      await page.focus(sel);
      await page.type(sel, text, { delay: 34 });
      await pause(500);
    },
    async zoom(sel, scale) {
      const { x, y } = await center(sel).catch(() => ({ x: null }));
      if (x != null) await page.evaluate((px, py) => window.__demo.move(px, py), x, y);
      const ok = await page.evaluate((s, sc) => window.__demo.zoom(s, sc), sel, scale);
      if (!ok) console.warn(`  zoom target missing: ${sel}`);
      await pause(1000);
    },
    async unzoom() {
      await page.evaluate(() => window.__demo.unzoom());
      await pause(1000);
    },
    async scrollTo(sel) {
      await page.evaluate((s) => document.querySelector(s)?.scrollIntoView({ block: 'center', behavior: 'smooth' }), sel);
      await pause(900);
    },
    async scrollToBottom() {
      await page.evaluate(() => scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
      await pause(900);
    },
  };
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--window-size=1920,1080', '--hide-scrollbars', '--force-device-scale-factor=1'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  await page.evaluateOnNewDocument(INJECT);
  const ctx = {
    preparedQuestion: JSON.parse(fs.readFileSync(path.join(DIR, '..', 'data', 'filings', 'prepared_questions.json'), 'utf8'))[0],
  };
  const h = helpers(page);
  const only = process.argv[2]; // optionally re-record one scene by id
  for (const scene of scenes) {
    if (only && scene.id !== only) continue;
    const dest = scene.card ? 'file://' + path.join(DIR, 'cards', scene.card) : scene.url ? URL_BASE + scene.url : null;
    if (dest) {
      await page.goto(dest, { waitUntil: 'networkidle0', timeout: 60000 });
      await pause(1200);
    }
    await page.evaluate(INJECT);
    if (scene.card) await page.evaluate(() => { const c = document.getElementById('__cursor'); if (c) c.style.display = 'none'; });
    const t0 = Date.now();
    const rec = await page.screencast({ path: path.join(RAW, `${scene.id}.webm`) });
    try {
      await scene.run(page, h, ctx);
    } catch (e) {
      console.error(`  scene ${scene.id} error: ${e.message}`);
    }
    await rec.stop();
    console.log(`${scene.id}: ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  }
} finally {
  await browser.close();
}
