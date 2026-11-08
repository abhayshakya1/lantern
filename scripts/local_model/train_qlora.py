"""QLoRA fine-tune of an open-weight model on the grounded-answer format from prep_data.py.

  python scripts/local_model/train_qlora.py --train train.jsonl --out adapter/

4-bit NF4 base, LoRA on attention and MLP projections, one epoch. Sized for a shared 48GB A6000
with another job resident: ~10-12GB peak.
"""

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--max-len", type=int, default=2048)
    args = ap.parse_args()

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map={"": 0})
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    ds = load_dataset("json", data_files=args.train, split="train").shuffle(seed=7)

    import dataclasses

    wanted = dict(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=20,
        save_strategy="epoch",
        bf16=True,
        max_length=args.max_len,
        max_seq_length=args.max_len,
        packing=False,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        report_to=[],
    )
    accepted = {f.name for f in dataclasses.fields(SFTConfig)}
    dropped = sorted(set(wanted) - accepted)
    cfg = SFTConfig(**{k: v for k, v in wanted.items() if k in accepted})  # trl versions disagree on fields
    if dropped:
        print(f"SFTConfig fields not in this trl, left at defaults: {dropped}")
    trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds, peft_config=lora, processing_class=tok)
    trainer.train()
    trainer.save_model(args.out)
    print(f"adapter saved -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
