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
