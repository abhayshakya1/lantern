# On-prem model workstream — status 2026-11-08 (evening)

Goal: the on-premise story made concrete — open-weight models fine-tuned on Abhay's own FinSafeQA-XL
data, benchmarked on the Lantern filings gold draft through the production pipeline (same retrieval,
same prompt, same verbatim-quote verification as the Opus path). Everything below ran on Deathstar;
no external API is involved anywhere (judging included).

Judge: **local** Qwen2.5-14B-Instruct served by scripts/local_model/judge_server.py (vLLM cannot run
on this host: a broken GPU poisons its NVML enumeration). Local-judge numbers are not directly
comparable to the paper's pinned DeepSeek-V4-Pro judge; re-judge with the pinned slug if credits
ever matter for a citable figure.

## Zero-shot baselines (gold draft, n=40: 24 easy / 8 medium / 8 hard)

| Model (4-bit) | Abstained | Abst. precision | llm_correct e/m/h | Bench minutes |
|---|---|---|---|---|
| Qwen2.5-3B  | 29/40 | 0.34 | 0.17 / 0.40 / 0.00 | 7.5 |
| Qwen2.5-7B  | 38/40 | 0.26 | 0.04 / 0.00 / 0.00 | 3.2 |
| Qwen2.5-14B | 16/40 | 0.62 | 0.58 / 0.60 / 0.00 | 13.7 |
| Qwen2.5-3B + FinSafeQA QLoRA | 33/40 | 0.30 (recall 1.00) | 0.21 / 0.20 / 0.00 | — |
| Qwen2.5-7B + FinSafeQA QLoRA | 26/40 | 0.31 (recall 0.80) | 0.33 / 0.40 / 0.00 | 10.8 |
| Qwen2.5-14B + FinSafeQA QLoRA | 24/40 | 0.33 (recall 0.80) | 0.38 / 0.40 / 1.00* | 30.4 |
| claude-opus-5-5 (production, paper judge) | 12/40 | 0.83 | 0.83 / 0.80 / 1.00 | — |

Fine-tune read: the 7B went from answering 2 questions to 14, and from 0.04 to 0.33 easy-tier
judge-correct — a clear lift from Abhay's own data, with a cost: abstention recall slipped from 1.00
to 0.80 (it now answers 2 of the 10 unanswerable probes with verbatim-but-non-responsive quotes) and
medium-tier refusal consistency (H-Ref) fell to 0.67. Zero-shot 14B still beats fine-tuned 7B; the
queued 14B fine-tune is the interesting row. If the recall slip persists there, raise the abstention
share of the training mix above 25% before any production talk.

Reading: abstention recall is 1.0 everywhere (nobody answers the unanswerable probes wrong — the
verbatim-quote gate does its job), and quality scales hard with size. The 7B abstains on nearly
everything zero-shot because its quotes fail the verbatim check — precisely the behaviour the
fine-tune teaches. Hard-tier questions defeat every zero-shot open model.

## In flight

- 7B QLoRA (6,000 grounded + 2,000 abstention examples, 1 epoch): step ~326/500.
- 3B QLoRA: step ~164/500 (sharing the A6000).
- 14B QLoRA: queued; starts automatically when a card frees, then benches itself.
- Retrieval sweep (bge-small vs base vs large against the gold evidence): running on CPU.
- Judge server stays up on 192.168.3.6:8411; `LANTERN_JUDGE_URL` points Lantern's own eval at it.

## Retrieval sweep (gold evidence vs embedding model, 30 answerable rows)

| Embedding | hit@8 (production TOP_K) | hit@30 | mean rank when found |
|---|---|---|---|
| bge-small-en-v1.5 (production) | 0.67 | 0.80 | 4.8 |
| bge-base-en-v1.5 | 0.67 | 0.83 | 5.7 |
| bge-large-en-v1.5 | 0.70 | 0.83 | 4.8 |

Finding: swapping embeddings buys one question (0.67 → 0.70); the same nine items miss under every
model (g002/3/6/7/9/14/18/26/29), g014 and g018 among them. The gate's misses are a chunking problem
on table-dense pages, not an embedding problem — the tuning pass after Abhay's verification should
target table-aware chunking (or a larger candidate pool), not a bigger encoder. Caveat: hit@gold-chunk
is a lower bound — another chunk can carry the same fact, which is how Opus answers questions whose
gold chunk ranks below 8.

## Verdict after the full ladder (2026-11-09)

*Hard-tier caveat: only one hard item is answerable (the rest are probes), so a hard llm_correct of
1.00 or 0.00 is a single question. Second caveat: the local judge is Qwen2.5-14B judging its own
family — treat close calls with suspicion until re-judged with the pinned DeepSeek judge.

- The fine-tune transforms the 7B (0.04 → 0.33 easy) but REGRESSES the 14B on easy/medium
  (0.58 → 0.38 / 0.60 → 0.40): style overfit to the pool's short answers, plus the recall slip to
  0.80 at both sizes. One epoch at lr 2e-4 is too hot for a model that already knows the task.
- Today's best on-prem answerer is therefore **zero-shot Qwen2.5-14B behind the verbatim-quote gate**
  (0.58 / 0.60, recall 1.00): the architecture supplies the safety, the model supplies fluency.
- If the fine-tune is pursued further: lower LR (5e-5), half an epoch, raise the abstention share
  above 25%, and mix in longer-form answers. The pipeline reruns end to end with one tmux command.

## The on-prem swap, live (2026-11-09)

`LANTERN_LLM_URL` now routes Filings Q&A to the Deathstar endpoint behind the unchanged interface:
same prompt, verbatim gate, abstention sentence, cache and logging; answers are labelled `local`
with the real model id. Live exchanges (Qwen2.5-14B zero-shot, ~3-11 s over the LAN):

- "Since when has Rajat Verma been CEO of DBS Bank India?" → "...since March 2025", quote verified,
  DBS AR2025 p.94 — `[local, 10229 ms]`.
- Two fresh harder questions → the exact abstention sentence with nearest passages — honest, no cloud.
- Cached prepared questions keep serving from the cache regardless of backend (scope is prompt+index).

Demo-day default remains Anthropic + cache; the local path is one environment variable.

## v2 recipe and judge robustness (2026-11-09)

The scorecard's own prescription (lr 5e-5, half epoch, abstention share 35%) was run on the 14B:

| Variant | Judge-correct e/m | Abstention precision / recall | Answer form (token F1, easy) |
|---|---|---|---|
| 14B zero-shot | 0.58 / 0.60 | 0.62 / 1.00 | 0.21 |
| 14B + v1 QLoRA (lr 2e-4, 1 epoch) | 0.38 / 0.40 | 0.33 / **0.80** | 0.34 |
| **14B + v2 QLoRA (lr 5e-5, 0.5 epoch, 35% abstain)** | **0.58 / 0.40** | 0.48 / **1.00** | **0.50** |

v2 recovers the easy tier to zero-shot level, restores perfect refusal recall and H-Ref 1.0, and
more than doubles answer-form quality (token F1 0.21 → 0.50: tighter, more extractive answers).
Medium dips 0.60 → 0.40 on n=8 (≈1.6 questions — within draft-set noise). Net: the gentle fine-tune
keeps the model's knowledge, teaches the format, and keeps the safety floor. This is the on-prem
answerer to demo.

Judge robustness: every prediction set was scored independently by local Qwen2.5-14B and
Qwen2.5-32B judges. Agreement is exact on 5 of 7 sets and within one question on the other two
(base-14b 0.58 vs 0.62 easy; base-3b 0.17 vs 0.21 easy). The scores are not an artifact of one
judge. The pinned paper judge (DeepSeek-V4-Pro) remains the citable reference if ever needed.
## Chunking and retrieval prototype (branch lantern-chunking, 2026-11-09)

Found and fixed: PyMuPDF table extraction detaches thousands separators ("6,106" → "6106\n,") on the
real filings — every indexed table row carried mangled numbers. The branch repairs the commas,
renders each table row self-describing with its column headers, and emits every table as its own
chunk instead of diluting prose windows (this last fix alone cured a long-flaky ranking test).

Quote-in-top-8 on the draft gold (ceiling 27/30: three old quotes were drafted from the mangled text
and can no longer exist verbatim):

| Configuration | hit@8 | notes |
|---|---|---|
| old chunking (baseline) | 0.70 | |
| clean chunking | 0.70 | structural win, no retrieval delta; all 6 real misses are PROSE, ranks 10–43 |
| + bge-reranker-base over 50 candidates | 0.73 | recovers g014/g018/g026 (the gate failures); demotes g001/g024 |
| + bge-reranker-v2-m3 over 50 candidates | 0.77 (= 0.85 of ceiling) | recovers g002/g014/g018/g026; still demotes g001/g024 |

Tuning-pass candidate (apply only after gold verification): v2-m3 reranker over 50 candidates,
with the lexical top-3 pinned to protect easy hits. Sequencing: after this branch merges, the
production index must be rebuilt and the prepared questions re-cached — pre-answer through the
on-prem model (LANTERN_LLM_URL) needs no API credits; gold-draft regeneration does.

Post-review measurement: 33.7% of table chunks (643 of 1,908) still carry extraction-level mangling
beyond the repaired comma artifact — detached decimal points, comma-only cells, glued words — which
cell-level repair cannot reconstruct confidently. Documented ceiling: table chunks are retrieval
aids; the prose text layer holds the correctly printed numbers and is where quotes verify, so the
mangling costs retrieval recall, never answer correctness. Escalation path if the verified gold set
demands more: a layout-aware extractor (Docling) behind the same ingest interface.

## Gold draft regenerated against the new index (2026-11-09, on-prem drafter)

The old draft's quotes were drawn from the pre-fix chunks, so the gold set was regenerated with the
on-prem model (no API credits; the old Opus draft is kept at gold/gold_draft_opus_old_index.jsonl).
40 rows, 30 answerable across all eight companies, every quote verbatim in the current chunks by
construction. Prepared questions re-promoted and re-cached on-prem (14 answered / 6 abstained).

Clean-baseline retrieval on the fresh draft: quote-in-top8 0.67; with the v2-m3 reranker 0.70 (+1
question — far smaller than its effect on the old draft's table-dense misses). Honest status: the
reranker is a measured candidate for the tuning pass, not a guaranteed win; the pass gets designed
against the VERIFIED gold set once Abhay has been through the draft.

## Finance embeddings vs the general embedder (2026-11-09, Deathstar)

Same index (7,267 chunks), same 30 answerable questions, quote-in-top8:

| Embedder | Score |
|---|---|
| bge-small-en-v1.5 (current) | 0.67 |
| FinLang finance-embeddings-investopedia | 0.57 |
| FinModernBERT | 0.67 |
| bge-m3 | 0.63 |
| FinLang + v2-m3 reranker | 0.70 |

Verdict: no finance embedder beats the general one on SGX annual reports; the misses are the same
table-dense questions for every model, which points to extraction (chunk quality), not embeddings.
bge-small stays. The reranker's +1 is the same as on bge-small, so it remains the only candidate
for the tuning pass.
