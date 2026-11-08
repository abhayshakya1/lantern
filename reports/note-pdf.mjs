// Print a research note's standalone view to PDF through Chrome. Run: node note-pdf.mjs <print-url> <out.pdf>
import { createRequire } from 'node:module';
const require = createRequire(new URL('../web/package.json', import.meta.url));
const puppeteer = require('puppeteer-core');

const [, , url, outPdf] = process.argv;
if (!url || !outPdf) {
  console.error('usage: node note-pdf.mjs <print-url> <out.pdf>');
  process.exit(1);
}
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage();
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.pdf({ path: outPdf, format: 'A4', printBackground: true, margin: { top: '18mm', bottom: '18mm', left: '16mm', right: '16mm' } });
  console.log(outPdf);
} finally {
  await browser.close();
}
