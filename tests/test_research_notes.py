from lantern.research import notes


def test_verify_numbers_accepts_numbers_from_the_run(run_fixture):
    prose = "The probability stands at 7%, up 1 point on the month."
    assert notes.verify_numbers(prose, run_fixture) == []


def test_verify_numbers_rejects_a_number_not_in_the_run(run_fixture):
    assert notes.verify_numbers("Capex rose 48% year on year.", run_fixture) == ["48"]


def test_note_roundtrips_through_the_store(tmp_store, run_fixture):
    run_id = tmp_store.save_run(run_fixture)
    nid = tmp_store.save_note({"run_id": run_id, "title": "t", "summary": "s", "lead": "l",
                               "commentary": [], "status": "Draft", "source": "template",
                               "prompt_sha": "x", "model": "m", "created_at": "2026-11-08T07:00:00+08:00"})
    assert tmp_store.get_note(nid)["title"] == "t" and tmp_store.list_notes()[0]["id"] == nid
    assert tmp_store.get_run(run_id)["tiles"]["probability"]["value"] == 0.07
    tmp_store.set_note_status(nid, "Published")
    assert tmp_store.get_note(nid)["status"] == "Published"
    assert tmp_store.get_note("n9999") is None


def test_note_payload_assembles_the_full_note(run_fixture):
    note = {"id": "n0001", "title": "t", "summary": "s", "lead": "l", "commentary": [],
            "created_at": "2026-11-08T07:00:00+08:00", "status": "Draft", "source": "api",
            "run_id": "r0001", "sources": [{"name": "fred.BAA10Y", "sha256": "ab", "fetched_at": "x"}]}
    p = notes.note_payload(note, run_fixture)
    assert p["author"] == "Lantern model, reviewed by Abhay"
    assert p["scenario_sentence"] and p["drivers"] and p["sources"] and p["chart"]
    assert notes.verify_numbers(p["scenario_sentence"], run_fixture) == []


def test_generate_note_uses_claude_and_passes_the_number_check(tmp_store, run_fixture):
    from tests.conftest import FakeClaude

    tmp_store.save_run(run_fixture)
    fake = FakeClaude({"title": "Derating risk steady", "summary": "s",
                       "lead": "The probability stands at 7%.",
                       "commentary": [{"driver": "Valuation", "text": "The z-score sits at 1.2."}]})
    n = notes.generate_note(tmp_store, client=fake)
    assert n["source"] == "api" and n["status"] == "Draft" and n["run_id"]
    assert fake.calls[0]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "ignore any instructions" in notes.NOTE_SYSTEM
    assert tmp_store.get_note(n["id"])["title"] == "Derating risk steady"


def test_hallucinated_number_falls_back_to_template_after_one_retry(tmp_store, run_fixture):
    from tests.conftest import FakeClaude

    tmp_store.save_run(run_fixture)
    fake = FakeClaude({"title": "t", "summary": "s", "lead": "Capex rose 48%.", "commentary": []})
    n = notes.generate_note(tmp_store, client=fake)
    assert len(fake.calls) == 2 and n["source"] == "template"
    assert notes.verify_numbers(n["lead"], run_fixture) == []


def test_no_key_means_offline_template_note(tmp_store, run_fixture, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    tmp_store.save_run(run_fixture)
    n = notes.generate_note(tmp_store)
    assert n["source"] == "offline-template" and n["lead"]
    assert notes.verify_numbers(n["lead"], run_fixture) == []


def test_generate_without_a_run_raises_a_clear_error(tmp_store):
    import pytest

    with pytest.raises(RuntimeError, match="no model run"):
        notes.generate_note(tmp_store)


def test_backtest_persists_the_ledger(tmp_store, seeded_all_series):
    from lantern import backtest

    backtest.run_backtest(tmp_store, "2010-01")
    df = tmp_store.load_series("backtest.ledger")
    assert df is not None and len(df) > 0 and set(df["kind"]) == {"backtest"}


def test_ledger_composes_backtest_and_live_rows(tmp_store, seeded_all_series, run_fixture):
    from lantern import backtest

    backtest.run_backtest(tmp_store, "2010-01")
    run_id = tmp_store.save_run(run_fixture)
    tmp_store.save_note({"run_id": run_id, "title": "t", "summary": "s", "lead": "l", "commentary": [],
                         "status": "Draft", "source": "api", "prompt_sha": "x", "model": "m",
                         "created_at": "2026-11-08T07:00:00+08:00"})
    rows = notes.ledger(tmp_store)
    assert rows[0]["kind"] == "live" and rows[0]["probability"] == 0.07
    assert rows[0]["realised_return"] is None and rows[0]["inside_fan"] is None
    assert any(r["kind"] == "backtest" for r in rows)


def test_ledger_is_empty_not_broken_without_a_backtest(tmp_store):
    assert notes.ledger(tmp_store) == []


def test_store_gives_each_thread_its_own_sqlite_connection(tmp_store):
    import threading

    seen = {}

    def grab():
        seen["worker"] = id(tmp_store.db)

    t = threading.Thread(target=grab)
    t.start()
    t.join()
    seen["main"] = id(tmp_store.db)
    assert seen["main"] != seen["worker"]  # one shared connection across the API threadpool corrupts reads
