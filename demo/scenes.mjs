// The demo script: one scene = one recorded segment with its narration.
// Choreography uses the helpers from record.mjs: h.zoom, h.unzoom, h.click, h.pause, h.type.

export const VOICE_ID = 'EXAVITQu4vr4xnSDxMaL'; // Sarah: mature, professional

export const scenes = [
  {
    id: '01-title',
    card: 'title.html',
    narration:
      'This is Lantern — a research and forecasting workspace that turns public market data and primary filings into defensible, auditable research. Everything you are about to see runs on one machine, from live data pulled this morning.',
    run: async (page, h) => { await h.pause(9000); },
  },
  {
    id: '02-monitor',
    url: '/#monitor',
    narration:
      'The centre screen is the AI-bubble monitor. The badge in the top bar says exactly what you are looking at — live data, and the time it was pulled — and every figure on this page traces back to a named public source.',
    run: async (page, h) => {
      await h.pause(2500);
      await h.zoom('#chip-badge', 2.2);
      await h.pause(4000);
      await h.unzoom();
      await h.pause(2500);
    },
  },
  {
    id: '03-probability',
    narration:
      'The headline number: the model’s probability that the AI basket de-rates by twenty per cent or more over the next twelve months. It is calibrated only on the drivers with real statistical signal — valuation, concentration and leverage — and the status label stays honest about how calm or stretched conditions are.',
    run: async (page, h) => {
      await h.click('[data-tile="probability"]', { ripple: false });
      await h.zoom('[data-tile="probability"]', 2.0);
      await h.pause(9000);
      await h.unzoom();
      await h.pause(1500);
    },
  },
  {
    id: '04-tiles',
    narration:
      'Alongside it: the fair-value gap, the basket’s earnings multiple against its ten-year median, capital expenditure against operating cash flow, and top-ten index concentration — each tile carrying its own history as a sparkline.',
    run: async (page, h) => {
      for (const t of ['fv_gap', 'forward_pe', 'capex_ocf', 'top10']) {
        await h.zoom(`[data-tile="${t}"]`, 1.9);
        await h.pause(2600);
      }
      await h.unzoom();
      await h.pause(1200);
    },
  },
  {
    id: '05-chart',
    narration:
      'The chart puts price against modelled fair value, with a forecast fan drawn from what actually happened in comparable months. Click a scenario and the sentence beneath restates it in plain English — here, the de-rating path. And the dashed grey band is a challenger: Google’s TimesFM foundation model forecasting the same series, kept on screen so the house model is always measured against a strong outside benchmark.',
    run: async (page, h) => {
      await h.zoom('#main-chart', 1.5);
      await h.pause(5000);
      await h.unzoom();
      await h.click('[data-scenario="derating"]');
      await h.pause(2500);
      await h.zoom('#scenario-sentence', 1.9);
      await h.pause(4500);
      await h.unzoom();
      await h.zoom('#main-chart', 1.6);
      await h.pause(5000);
      await h.unzoom();
    },
  },
  {
    id: '06-drivers',
    narration:
      'Seven drivers feed the composite. The three that carry weight are tagged calibrated; the other four are watch indicators — shown, but deliberately unweighted, because the table never pretends to signal that is not there. Opening a driver reveals its source, its transformation, its full history, and any proxy used before live data begins. Complete provenance, one click deep.',
    run: async (page, h) => {
      await h.zoom('#driver-table', 1.5);
      await h.pause(6000);
      await h.unzoom();
      await h.click('#driver-table tbody tr');
      await h.pause(1500);
      await h.zoom('#driver-panel', 1.35);
      await h.pause(7000);
      await h.unzoom();
      await page.keyboard.press('Escape').catch(() => {});
      await h.pause(800);
    },
  },
  {
    id: '07-triggers',
    url: '/#monitor',
    narration:
      'Triggers quantify what would move the probability — one standard deviation of valuation, a jump in credit spreads — and the footer discloses the calibration itself: the fit window, the hit rate, and the Brier score against the base rate. Nothing lives in an appendix.',
    run: async (page, h) => {
      await h.pause(1500);
      await h.zoom('.card.side:has(.trig)', 1.45);
      await h.pause(5500);
      await h.unzoom();
      await h.scrollToBottom();
      await h.zoom('.tfoot', 1.7);
      await h.pause(4000);
      await h.unzoom();
    },
  },
  {
    id: '08-filings-ask',
    url: '/#filings',
    narration:
      'The second module answers questions from primary documents: eight complete annual reports from SGX-listed companies, around six thousand indexed passages. Ask a question, and the answer returns with the exact sentences it rests on — quoted verbatim, checked character by character against the filing, with the company, the document, and the page. When the filings cannot answer, Lantern says so in one fixed sentence instead of guessing; that refusal behaviour is measured on a gold set, not promised.',
    run: async (page, h, ctx) => {
      await h.pause(1500);
      await h.zoom('#corpus-table', 1.35);
      await h.pause(4500);
      await h.unzoom();
      await h.click('#ask-input');
      await h.type('#ask-input', ctx.preparedQuestion);
      await h.click('#ask-form button[type="submit"]');
      await page.waitForSelector('#answer .evidence, #answer .abstain, #answer .offline', { timeout: 30000 }).catch(() => {});
      await h.pause(1200);
      await h.zoom('#answer', 1.4);
      await h.pause(8000);
      await h.unzoom();
    },
  },
  {
    id: '09-evidence',
    narration:
      'Every quote links straight to the source page in the original PDF, so a claim is never more than one click from the document behind it. And the session log keeps every question asked, with the model, the prompt hash, and the passages retrieved.',
    run: async (page, h) => {
      await h.zoom('#answer .evidence', 1.7);
      await h.pause(5500);
      await h.unzoom();
      await h.zoom('#history', 1.5);
      await h.pause(3500);
      await h.unzoom();
    },
  },
  {
    id: '09b-onprem',
    url: '/#filings',
    narration:
      'Everything so far could run on a cloud model. Now the same pipeline with no cloud at all: this question is being answered live by an open-weight model running on the bank\u2019s own GPU server, behind the identical interface, with the identical verbatim-quote verification. The answer declares its true source \u2014 the on-premise model, by name. Data, documents and models never leave the building.',
    run: async (page, h) => {
      await h.pause(1000);
      await h.click('#ask-input');
      await h.type('#ask-input', 'Since when has Rajat Verma been Chief Executive Officer of DBS Bank India?');
      await h.click('#ask-form button[type="submit"]');
      await page.waitForSelector('#answer .evidence, #answer .abstain, #answer .offline', { timeout: 60000 }).catch(() => {});
      await h.pause(800);
      await h.zoom('#answer', 1.4);
      await h.pause(6000);
      await h.unzoom();
      await h.zoom('#answer .src', 1.6);
      await h.pause(4500);
      await h.unzoom();
    },
  },
  {
    id: '10-research',
    url: '/#research',
    narration:
      'The research desk turns each morning’s model run into a dated, formatted note. One rule governs the prose: every number must appear in the model run’s own output — a draft that invents a figure is rejected automatically and replaced by a deterministic fallback, clearly labelled. The note carries the chart, the driver table, the triggers, and a sources table with pull times and cryptographic hashes — and it exports to PDF through the same pipeline.',
    run: async (page, h) => {
      await h.pause(2000);
      await h.zoom('#note-view', 1.25);
      await h.pause(5000);
      await h.unzoom();
      await h.zoom('#note-view .byline', 1.9);
      await h.pause(3500);
      await h.unzoom();
      await h.scrollTo('#note-view h2:last-of-type');
      await h.pause(1000);
      await h.zoom('#note-view table:last-of-type', 1.5);
      await h.pause(5000);
      await h.unzoom();
      await h.scrollTo('#note-view');
    },
  },
  {
    id: '11-ledger',
    narration:
      'Beside the feed sits the accuracy ledger: every past forecast, its horizon, what the market then did, and whether the outcome landed inside the fan — seeded from a twenty-year backtest and extended live with every note. The desk keeps its own score, in public.',
    run: async (page, h) => {
      await h.scrollTo('#ledger');
      await h.zoom('#ledger', 1.45);
      await h.pause(8000);
      await h.unzoom();
    },
  },
  {
    id: '12-modelrisk',
    url: '/#modelrisk',
    narration:
      'Model risk is a first-class page, built for the governance review a bank will run. The question-answering system is scored against a gold set with a hard gate on abstention precision, and the forecast fan is benchmarked against the TimesFM challenger over two hundred and fifty-two months of walk-forward history — the house fan held seventy-seven per cent coverage against the challenger’s fifty. Behind this page sits a full open-model scorecard: three model sizes fine-tuned on in-house research data and scored by a locally served judge, so even the evaluation needs no outside API.',
    run: async (page, h) => {
      await h.pause(2500);
      await h.zoom('#main table', 1.35);
      await h.pause(6000);
      await h.unzoom();
      await h.scrollToBottom();
      await h.pause(5000);
    },
  },
  {
    id: '13-sources',
    url: '/#sources',
    narration:
      'Finally, every series on the platform is accounted for here: the source, the last pull, its status, and the hash of the raw response. When a reviewer asks where a number came from, the answer is already on screen.',
    run: async (page, h) => {
      await h.pause(2500);
      await h.zoom('#main table', 1.3);
      await h.pause(6500);
      await h.unzoom();
    },
  },
  {
    id: '14-outro',
    card: 'outro.html',
    narration:
      'Lantern runs end to end on infrastructure you control: the answers, the forecasts, the challenger and even the judge are local models — the cloud is an option, never a dependency. Thank you for watching.',
    run: async (page, h) => { await h.pause(8000); },
  },
];
