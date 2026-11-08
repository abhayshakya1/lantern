"""A tiny OpenAI-compatible chat-completions server for local judging on the GPU box.

vLLM crashes on this host (a broken GPU poisons its NVML enumeration), so this serves the judge the
boring way: transformers + 4-bit bnb, greedy, one request at a time — exactly what the BharatFinQA
judge needs (max_tokens 8, temperature 0, sequential calls).

  python scripts/local_model/judge_server.py --model Qwen/Qwen2.5-14B-Instruct --port 8411
"""

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-14B-Instruct")
    ap.add_argument("--port", type=int, default=8411)
    args = ap.parse_args()

    import torch
    import uvicorn
    from fastapi import FastAPI
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map={"": 0})
    model.eval()
    print(f"judge ready: {args.model}", flush=True)

    app = FastAPI()

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [{"id": args.model, "object": "model"}]}

    @app.post("/v1/chat/completions")
    def chat(body: dict):
        enc = tok.apply_chat_template(body["messages"], add_generation_prompt=True,
                                      return_tensors="pt", return_dict=True).to(model.device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=int(body.get("max_tokens", 64)),
                                 do_sample=False, pad_token_id=tok.eos_token_id)
        text = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        return {"id": "local", "object": "chat.completion", "model": args.model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
