import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { marked } from 'marked';
import puppeteer from 'puppeteer-core';

const [,, mdPath, outPdf] = process.argv;
const work = path.dirname(outPdf);
const md = fs.readFileSync(mdPath, 'utf8');
const dir = path.dirname(path.resolve(mdPath));
const TITLE = 'OCBC Bank: End-to-End Research';
const DATE = '7 November 2026';

marked.setOptions({ gfm: true });
const src = md.replace(/\)\{[^}]*\}/g, ')');
let body = marked.parse(src);
body = body.replace(/<img src="([^"]+)"/g, (m, s) => {
  const p = path.resolve(dir, decodeURIComponent(s));
  if (!fs.existsSync(p)) return m;
  return `<img src="data:image/png;base64,${fs.readFileSync(p).toString('base64')}"`;
});
body = body.replace(/<p>(<img [^>]*alt="([^"]*)"[^>]*>)<\/p>/g, '<figure>$1<figcaption>$2</figcaption></figure>');

const chunks = body.split(/(?=<h1)/).filter(c => c.trim());
const titles = chunks.map(c => (c.match(/<h1[^>]*>([\s\S]*?)<\/h1>/) || [, ''])[1]);
let chapters = chunks.map((c, i) => `<section class="chapter" id="ch${i + 1}">${c}</section>`).join('\n');
chapters = chapters.replace(/<table>([\s\S]*?)<\/table>/, (m, tbl) => {
  const rows = [...tbl.matchAll(/<tr>\s*<td>([\s\S]*?)<\/td>\s*<td>([\s\S]*?)<\/td>\s*<\/tr>/g)];
  if (!rows.length) return m;
  return `<div class="tiles">${rows.map(r => `<div class="tile"><div class="v">${r[2]}</div><div class="l">${r[1]}</div></div>`).join('')}</div>`;
});

const cover = `<section class="cover">
  <div class="band">
    <div class="kicker">Research document &middot; as of ${DATE}</div>
    <div class="t1">OCBC Bank</div>
    <div class="t2">End-to-End Research</div>
    <p class="sub">Corporate profile, segments, financials, strategy, technology and AI, regulation, competitors, and where an AI-driven forecasting, research-publishing and dashboard platform fits.</p>
  </div>
  <div class="cover-stats">
    <div><div class="v">S$675.7bn</div><div class="l">Total assets, end-2025</div></div>
    <div><div class="v">S$6.24bn</div><div class="l">Record net profit, nine months 2026</div></div>
    <div><div class="v">S$358bn</div><div class="l">Banking wealth AUM, September 2026</div></div>
    <div><div class="v">14.0%</div><div class="l">CET1 fully phased-in, September 2026</div></div>
  </div>
  <div class="cover-foot"><span>Prepared by Abhay</span><span>Built from OCBC, MAS, Great Eastern, Bank of Singapore, DBS and UOB disclosures, with about 750 source links in the research notes</span></div>
</section>`;

const tocHtml = (pages) => `<section class="toc"><h1>Contents</h1><ol>${titles.map((t, i) => `<li><a href="#ch${i + 1}"><span class="n">${String(i + 1).padStart(2, '0')}</span><span class="t">${t}</span><span class="p">${pages ? pages[i] : ''}</span></a></li>`).join('')}</ol></section>`;

const css = `
:root{--navy:#0F2A4A;--accent:#1D6FD1;--ink:#1F2933;--muted:#5B6773;--line:#D9DEE3;--tint:#F2F6FB}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:-apple-system,"Helvetica Neue",Helvetica,Arial,sans-serif;color:var(--ink);font-size:9.6pt;line-height:1.45;counter-reset:chapter}
p{margin:0 0 2.6mm;orphans:3;widows:3}
a{color:var(--accent);text-decoration:none}
strong{color:var(--navy)}
h1,h2,h3{break-after:avoid;break-inside:avoid}
.cover{height:255mm;display:flex;flex-direction:column;justify-content:space-between}
.cover .band{background:var(--navy);color:#fff;border-radius:6px;padding:26mm 16mm 20mm;flex:0 0 152mm;display:flex;flex-direction:column;justify-content:flex-end}
.cover .kicker{font-size:9pt;letter-spacing:.14em;text-transform:uppercase;color:#9CC3F5;margin-bottom:10mm}
.cover .t1{font-size:44pt;font-weight:700;line-height:1;letter-spacing:-.02em}
.cover .t2{font-size:26pt;font-weight:400;line-height:1.1;margin-top:3mm;color:#CFE0F7}
.cover .sub{font-size:10.5pt;color:#DCE7F5;margin:8mm 0 0;max-width:150mm;line-height:1.45}
.cover-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:4mm;margin-top:6mm}
.cover-stats>div{border-top:3px solid var(--accent);padding-top:3mm}
.cover-stats .v{font-size:19pt;font-weight:700;color:var(--navy);letter-spacing:-.01em}
.cover-stats .l{font-size:8pt;color:var(--muted);margin-top:1mm}
.cover-foot{display:flex;justify-content:space-between;gap:10mm;font-size:8pt;color:var(--muted);border-top:1px solid var(--line);padding-top:3mm}
.cover-foot span:last-child{text-align:right;max-width:120mm}
.toc{break-after:page}
.toc h1{font-size:22pt;color:var(--navy);margin:0 0 6mm;letter-spacing:-.01em}
.toc ol{list-style:none;padding:0;margin:0}
.toc li{border-bottom:1px solid var(--line);padding:2.6mm 0}
.toc li a{display:flex;gap:6mm;color:var(--ink);font-size:11pt;align-items:baseline}
.toc .n{color:var(--accent);font-weight:700;width:10mm;flex:0 0 auto}
.toc .p{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums;font-size:10pt}
.chapter+.chapter{margin-top:11mm}
.chapter h1{font-size:21pt;color:var(--navy);margin:0 0 4mm;padding-bottom:2.5mm;border-bottom:2px solid var(--accent);letter-spacing:-.01em;line-height:1.15}
.chapter h1::before{counter-increment:chapter;content:counter(chapter,decimal-leading-zero);display:block;font-size:10pt;color:var(--accent);font-weight:700;letter-spacing:.14em;margin-bottom:1.5mm}
.chapter h1+p{font-size:11pt;color:var(--navy);line-height:1.45;margin-bottom:4mm;break-before:avoid}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:3mm;margin:3mm 0 5mm;break-inside:avoid}
.tile{background:var(--tint);border-top:3px solid var(--accent);border-radius:0 0 4px 4px;padding:2.5mm 3mm 3mm}
.tile .v{font-size:14pt;font-weight:700;color:var(--navy);letter-spacing:-.01em;line-height:1.1}
.tile .l{font-size:7.3pt;color:var(--muted);margin-top:1.4mm;line-height:1.3}
table{width:100%;border-collapse:collapse;font-size:8.2pt;line-height:1.35;margin:2mm 0 5mm}
thead{display:table-header-group}
th{text-align:left;background:var(--navy);color:#fff;padding:1.8mm 2.2mm;font-weight:600;vertical-align:bottom}
td{padding:1.7mm 2.2mm;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:nth-child(even) td{background:var(--tint)}
tr{break-inside:avoid}
td:first-child{font-weight:600;color:var(--navy)}
figure{margin:3mm 0 5mm;break-inside:avoid}
figure img{width:100%;display:block;border:1px solid var(--line);border-radius:4px}
figcaption{font-size:8.2pt;color:var(--muted);margin-top:1.6mm}
blockquote{margin:4mm 0;padding:3.5mm 5mm;background:var(--tint);border-left:4px solid var(--accent);border-radius:0 4px 4px 0;break-inside:avoid}
blockquote p{margin:0}
ol,ul{padding-left:5.5mm;margin:0 0 3mm}
li{margin-bottom:1.2mm}
#ch14{font-size:8.6pt}
#ch14 li{word-break:break-word}
`;
const wrap = inner => `<!doctype html><html><head><meta charset="utf-8"><title>${TITLE}</title><style>${css}</style></head><body>${inner}</body></html>`;

const browser = await puppeteer.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--no-sandbox'] });
const common = 'font-family:Helvetica,Arial,sans-serif;font-size:8px;color:#6B7580;width:100%;padding:0 16mm;display:flex;justify-content:space-between;';
async function render(html, file, hf) {
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'load' });
  await page.emulateMediaType('print');
  const opts = { path: file, format: 'A4', printBackground: true, margin: { top: '20mm', bottom: '18mm', left: '16mm', right: '16mm' }, outline: true, displayHeaderFooter: hf };
  if (hf) {
    opts.headerTemplate = `<div style="${common}"><span>${TITLE}</span><span>As of ${DATE}</span></div>`;
    opts.footerTemplate = `<div style="${common}"><span>Prepared by Abhay</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`;
  }
  await page.pdf(opts);
  await page.close();
}
const coverPdf = path.join(work, 'cover.pdf'), bodyPdf = path.join(work, 'body.pdf');
await render(wrap(cover), coverPdf, false);
await render(wrap(tocHtml(null) + chapters), bodyPdf, true);
const pagesText = execFileSync('pdftotext', ['-layout', bodyPdf, '-'], { encoding: 'utf8' }).split('\f');
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const pageOf = titles.map((t, i) => {
  const re = new RegExp(`(^|\\n)\\s*${String(i + 1).padStart(2, '0')}\\s*\\n\\s*${esc(t)}\\s*(\\n|$)`);
  for (let p = 1; p < pagesText.length; p++) if (re.test(pagesText[p])) return p + 1;
  return '';
});
await render(wrap(tocHtml(pageOf) + chapters), bodyPdf, true);
await browser.close();
fs.writeFileSync(path.join(work, 'ocbc-report-print.html'), wrap(cover + tocHtml(pageOf) + chapters));
execFileSync('pdfunite', [coverPdf, bodyPdf, outPdf]);
console.log('chapter pages:', JSON.stringify(pageOf));
