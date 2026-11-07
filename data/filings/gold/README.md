# Filings Q&A gold set

`gold_draft.jsonl` is written by `lantern filings gold-draft`: 30 answerable questions, each with a quote that was verified verbatim against one chunk of one filing, and 10 unanswerable probes. The pitch states that the set was model-drafted and human-verified, so the verified file is yours.

## How to verify (about two hours)

For each row:

1. Open the PDF named in `evidence.file` at `evidence.page` (the app serves it at `/filings/pdf/<file>#page=<n>`).
2. Confirm that the quote is on that page and that it answers the question fully; tighten `answer` to the figure or phrase as written.
3. If the question is ambiguous or the quote does not answer it, fix the question or delete the row.
4. For an unanswerable probe (`"unanswerable": true`), confirm the report really does not answer it; if it does, either delete the row or turn it into an answerable one with evidence.
5. Set `difficulty` to `easy` (a stated figure), `medium` (one step of reading) or `hard` (a judgement the report states).

Save the result as `gold.jsonl` in this folder, keep `gold_draft.jsonl` beside it, and run `lantern filings eval`. The Model risk page shows the scores and the release gate: no demo below 90% abstention precision.

Row shape: `{"item_id", "question", "company", "answer", "evidence": {"file", "page", "chunk_id", "quote"} | null, "unanswerable", "difficulty"}`.
