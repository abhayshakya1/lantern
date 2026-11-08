# On-prem model workstream — status 2026-11-08

Goal: the on-premise story made concrete — an open-weight model fine-tuned on Abhay's own
FinSafeQA-XL data, benchmarked on the Lantern filings gold set through the production pipeline
(same retrieval, same prompt, same verbatim-quote verification as the Opus path).

| Answerer | Abstention precision | Abstention recall | Abstained | Judge (llm_correct) |
|---|---|---|---|---|
| claude-opus-5-5 (production) | 0.83 | 1.00 | 12/40 | 0.83 / 0.80 / 1.00 by tier |
| Qwen2.5-7B zero-shot (baseline) | 0.26 | 1.00 | 38/40 | pending OpenRouter credits |
| Qwen2.5-7B + FinSafeQA QLoRA | training (tmux lantern-ft, GPU-bfe80d06) | | | pending |

Reading the baseline: zero-shot Qwen abstains on nearly everything because its quotes fail the
verbatim check — the exact behaviour the fine-tune teaches (6,000 answerable examples with the
evidence among distractors, 2,000 mismatched-context abstentions, all under the deployed prompt).

Pipeline: scripts/local_model/{prep_data,bench,train_qlora}.py + pipeline.sh; work at
~/Abhay/lantern-local on Deathstar; no API keys on the shared server. Judge scoring runs from the
laptop (bfq_score.py --judge deepseek/deepseek-v4-pro-0813) once OpenRouter has credits; the
baseline pred file is already at data/filings/eval/pred_qwen_base.jsonl.
