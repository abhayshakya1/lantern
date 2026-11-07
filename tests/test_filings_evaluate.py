import json

from lantern import config
from lantern.filings import evaluate
from tests.conftest import FakeClaude


def _dividend_chunk(retriever):
    return next(h.chunk.id for h in retriever.search("final dividend", k=3) if "42 cents" in h.chunk.text)


def test_draft_gold_keeps_only_verified_quotes_and_marks_unanswerable(retriever):
    fake = FakeClaude({"question": "What final dividend did ACME recommend for 2025?", "answer": "42 cents per share",
                       "quote": "The Board recommends a final dividend of 42 cents per share.", "difficulty": "easy"})
    rows = evaluate.draft_gold(retriever, fake, n_answerable=2, n_unanswerable=1)
    answerable = [r for r in rows if not r["unanswerable"]]
    assert len(answerable) == 1 and answerable[0]["evidence"]["page"] == 2 and answerable[0]["company"] == "ACME"  # the quote verifies against one chunk only
    assert answerable[0]["difficulty"] == "easy" and answerable[0]["evidence"]["chunk_id"] == _dividend_chunk(retriever)
    assert sum(r["unanswerable"] for r in rows) == 1 and all(r["item_id"].startswith("g") for r in rows)


class Router(FakeClaude):
    """Answers the dividend question with verified evidence and abstains on everything else."""

    def __init__(self, cid):
        super().__init__(None)
        self.good = {"answerable": True, "answer": "ACME recommended a final dividend of 42 cents per share for 2025. Net profit rose 7%.",
                     "evidence": [{"chunk_id": cid, "quote": "The Board recommends a final dividend of 42 cents per share."}], "confidence": "high"}
        self.abstain = {"answerable": False, "answer": "", "evidence": [], "confidence": "low"}

    def create(self, **kw):
        self.payload = self.good if "dividend" in kw["messages"][0]["content"].split("Question:")[-1] else self.abstain
        return super().create(**kw)


def test_run_eval_scores_abstention_precision_and_gate(tmp_store, tmp_path, retriever, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cid = _dividend_chunk(retriever)
    gold = [
        {"item_id": "g001", "question": "What final dividend did ACME recommend?", "company": "ACME", "answer": "42 cents per share",
         "evidence": {"file": "ACME-AR2025.pdf", "page": 2, "chunk_id": cid, "quote": "42 cents"}, "unanswerable": False, "difficulty": "easy"},
        {"item_id": "g002", "question": "What was ACME's net profit in 2019?", "company": "ACME", "answer": "", "evidence": None, "unanswerable": True, "difficulty": "hard"},
    ]
    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text("\n".join(json.dumps(g) for g in gold) + "\n")
    monkeypatch.setattr(evaluate.config, "FILINGS_DIR", tmp_path)
    res = evaluate.run_eval(tmp_store, retriever, gold_path, client=Router(cid))
    assert res["n"] == 2 and res["gate"]["threshold"] == config.GOLD_GATE and res["judge"] is None
    assert res["abstention"] == {"precision": 1.0, "recall": 1.0, "n_abstained": 1, "n_unanswerable": 1, "n": 2} and res["gate"]["pass"] is True
    assert res["bfq"]["manifest"]["scored_n"] == 2 and res["bfq"]["manifest"]["judge_model"] is None  # deterministic metrics run without a judge
    assert json.loads((tmp_path / "eval" / "results.json").read_text())["n"] == 2 and (tmp_path / "eval" / "pred.jsonl").exists()
    assert tmp_store.questions(2)[0]["source"] == "api"  # the eval never reads the answer cache
