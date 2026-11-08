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
| claude-opus-5-5 (production, paper judge) | 12/40 | 0.83 | 0.83 / 0.80 / 1.00 | — |

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
