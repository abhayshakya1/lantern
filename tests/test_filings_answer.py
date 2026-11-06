from datetime import UTC, datetime

from lantern import config
from lantern.filings import answer, retrieve
from tests.conftest import FakeClaude


def _dividend_chunk(retriever):
    return next(h.chunk.id for h in retriever.search("final dividend", k=3) if "42 cents" in h.chunk.text)


def test_answer_keeps_only_verbatim_quotes_and_cites_page(tmp_store, retriever):
    cid = _dividend_chunk(retriever)
    fake = FakeClaude({
        "answerable": True,
        "answer": "ACME recommended a final dividend of 42 cents per share for 2025. The payout follows a 7% rise in net profit.",
        "evidence": [{"chunk_id": cid, "quote": "The Board recommends a final dividend of 42 cents per share."},
                     {"chunk_id": cid, "quote": "a final dividend of roughly forty-two cents"}],
        "confidence": "high",
    })
    a = answer.ask(tmp_store, retriever, "What final dividend did ACME recommend?", client=fake, now=datetime(2026, 11, 20, 1, tzinfo=UTC))
    assert a.answerable and len(a.evidence) == 1 and a.evidence[0].page == 2 and a.evidence[0].ticker == "ACME" and a.source == "api"
    assert fake.calls[0]["model"] == config.LLM_MODEL and fake.calls[0]["output_config"]["format"]["type"] == "json_schema"
    assert fake.calls[0]["system"][0]["cache_control"] == {"type": "ephemeral"}
    row = tmp_store.questions(1)[0]
    assert row["prompt_sha"] == answer.PROMPT_SHA and cid in row["chunk_ids"] and "forty-two" in row["response"] and row["source"] == "api"


def test_no_surviving_quote_becomes_abstention_with_context(tmp_store, retriever):
    fake = FakeClaude({"answerable": True, "answer": "Profit rose.", "evidence": [{"chunk_id": "nope", "quote": "profit rose a lot"}], "confidence": "medium"})
    a = answer.ask(tmp_store, retriever, "Did profit rise?", client=fake)
    assert not a.answerable and a.text == config.ABSTAIN and a.evidence == [] and a.context and "chunk_id" in a.context[0]


def test_no_hits_means_abstention_without_an_api_call(tmp_store, tmp_path):
    retrieve.build_index([], tmp_path / "index", retrieve.HashEmbedder())
    empty = retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder())
    fake = FakeClaude({"answerable": True, "answer": "x", "evidence": [], "confidence": "low"})
    a = answer.ask(tmp_store, empty, "Anything?", client=fake)
    assert a.text == config.ABSTAIN and fake.calls == [] and a.source == "none"


def test_cache_serves_before_the_api_and_offline_state_on_connection_error(tmp_store, retriever):
    import anthropic

    cid = retriever.search("total assets")[0].chunk.id
    good = FakeClaude({"answerable": True, "answer": "Total assets were S$9,876 million at year end. That is the balance-sheet size.",
                       "evidence": [{"chunk_id": cid, "quote": "Total assets stood at S$9,876 million at year end."}], "confidence": "high"})
    first = answer.ask(tmp_store, retriever, "What were BETA's total assets?", client=good)
    tmp_store.cache_put(answer.cache_key("What were BETA's total assets?"), first.to_dict(), datetime.now(UTC))
    dead = FakeClaude(None, raise_exc=anthropic.APIConnectionError(request=None))
    cached = answer.ask(tmp_store, retriever, "what were beta's total assets", client=dead)
    assert cached.source == "cache" and cached.answerable and dead.calls == []
    adhoc = answer.ask(tmp_store, retriever, "How many employees does BETA have?", client=dead)
    assert adhoc.source == "offline" and adhoc.text == answer.OFFLINE and adhoc.context


def test_refusal_stop_reason_is_an_abstention(tmp_store, retriever):
    fake = FakeClaude(None, stop_reason="refusal")
    a = answer.ask(tmp_store, retriever, "What final dividend did ACME recommend?", client=fake)
    assert a.text == config.ABSTAIN and tmp_store.questions(1)[0]["source"] == "refusal"
