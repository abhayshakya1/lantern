"""The on-prem answerer client: the anthropic client surface that `answer.ask` uses, implemented
against an OpenAI-compatible /v1/chat/completions endpoint (the judge server on Deathstar).

The server enforces no JSON schema, so the user turn gains a JSON-only instruction; an unparseable
reply already falls to abstention inside `ask()`. Transport failures raise the exception types `ask`
already catches, so a dead endpoint degrades to the OFFLINE answer, never a traceback."""

import json
import os
from types import SimpleNamespace

import anthropic
import requests

TIMEOUT = 120.0


class LocalChat:
    def __init__(self, url: str | None = None, model: str | None = None):
        self.url = url or os.environ.get("LANTERN_LLM_URL", "")
        self.model = model or os.environ.get("LANTERN_LLM_MODEL", "local-model")
        self.messages = self  # client.messages.create(...) resolves here

    def create(self, *, model=None, max_tokens=1000, system=None, output_config=None, messages=None, **_):
        flat = [{"role": "system", "content": b["text"]} for b in (system or [])]
        for m in messages or []:
            content = m["content"]
            if m["role"] == "user" and output_config:
                schema = json.dumps((output_config.get("format") or {}).get("schema", {}))
                content += f"\n\nReply with only a JSON object matching this schema, nothing else: {schema}"
            flat.append({"role": m["role"], "content": content})
        try:
            r = requests.post(self.url, json={"model": self.model, "temperature": 0,
                                              "max_tokens": max_tokens, "messages": flat}, timeout=TIMEOUT)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, LookupError, ValueError, TypeError) as exc:  # a half-dead endpoint degrades like a dead one
            raise anthropic.APIConnectionError(request=None) from exc
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])
