import json

import anthropic
import pytest
import requests

from lantern.filings import local_llm


class _Resp:
    def __init__(self, content):
        self._c = content
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"role": "assistant", "content": self._c}}]}


def test_create_flattens_messages_adds_json_instruction_and_wraps_the_reply(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured.update(url=url, payload=json, timeout=timeout)
        return _Resp('{"answerable": true}')

    monkeypatch.setattr(local_llm.requests, "post", fake_post)
    client = local_llm.LocalChat(url="http://gpu:8411/v1/chat/completions", model="local-qwen")
    resp = client.messages.create(
        model="ignored-upstream-name",
        max_tokens=4000,
        system=[{"type": "text", "text": "SYSTEM RULES", "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": {"type": "object"}}},
        messages=[{"role": "user", "content": "Passages...\n\nQuestion: q?"}],
    )
    assert captured["url"] == "http://gpu:8411/v1/chat/completions" and captured["timeout"]
    msgs = captured["payload"]["messages"]
    assert msgs[0] == {"role": "system", "content": "SYSTEM RULES"}
    assert msgs[1]["role"] == "user" and "Question: q?" in msgs[1]["content"]
    assert "only a JSON object" in msgs[1]["content"]  # no schema enforcement server-side
    assert captured["payload"]["model"] == "local-qwen" and captured["payload"]["temperature"] == 0
    assert resp.stop_reason == "end_turn"
    assert resp.content[0].type == "text" and json.loads(resp.content[0].text)["answerable"] is True


def test_transport_errors_become_the_exception_ask_already_catches(monkeypatch):
    def dead_post(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(local_llm.requests, "post", dead_post)
    client = local_llm.LocalChat(url="http://gpu:8411/v1/chat/completions", model="m")
    with pytest.raises(anthropic.APIConnectionError):
        client.messages.create(model="m", max_tokens=10, system=[{"type": "text", "text": "s"}],
                               messages=[{"role": "user", "content": "u"}])
