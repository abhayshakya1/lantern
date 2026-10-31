from datetime import UTC, datetime

from lantern import backtest, pull
from lantern.sources.base import SourceError


def test_one_failing_source_keeps_cache_and_marks_cached(tmp_store, seeded_all_series):
    def good(store):
        return {"fred.DFII10": seeded_all_series["fred.DFII10"]}

    def bad(store):
        raise SourceError("spy", "boom")

    tmp_store.set_meta("last_pull", {"at": "2026-11-06T22:40:00+00:00", "ok": True})
    st = pull.run_pull(tmp_store, [good, bad])
    assert [i["status"] for i in st.items] == ["ok", "error"]
    assert st.items[1]["detail"].startswith("spy")
    assert tmp_store.get_meta("last_pull")["at"] == "2026-11-06T22:40:00+00:00"  # the old pull stands
    assert tmp_store.get_meta("last_pull_attempt")["ok"] is False
    assert tmp_store.load_series("fred.DFII10") is not None
    b = pull.badge(tmp_store, now=datetime(2026, 11, 8, 1, 0, tzinfo=UTC))  # 09:00 SGT on 8 Nov
    assert b["state"] == "cached" and b["label"] == "Cached data · pulled 07 Nov"


def test_badge_live_same_sgt_day(tmp_store):
    tmp_store.set_meta("last_pull", {"at": "2026-11-06T22:40:00+00:00", "ok": True})  # 06:40 SGT on 7 Nov
    b = pull.badge(tmp_store, now=datetime(2026, 11, 7, 1, 30, tzinfo=UTC))
    assert b["state"] == "live" and b["label"] == "Live data · pulled 06:40 SGT"


def test_badge_none_without_pull(tmp_store):
    assert pull.badge(tmp_store)["state"] == "none"


def test_run_model_builds_payload(tmp_store, seeded_all_series):
    backtest.run_backtest(tmp_store, "2010-01")
    run = pull.run_model(tmp_store, now=datetime(2026, 11, 7, 1, 0, tzinfo=UTC))
    tiles, chart = run["tiles"], run["chart"]
    assert 0.01 <= tiles["probability"]["value"] <= 0.99 and tiles["probability"]["status"] in {"calm", "elevated", "high"}
    assert len(run["drivers"]) == 7 and run["drivers"] == sorted(run["drivers"], key=lambda d: -d["contribution_pts"])
    assert abs(sum(chart["scenarios"][k]["prob"] for k in ("base", "derating", "meltup")) - 1) < 1e-9
    assert len(chart["months"]) == 37 and len(chart["price"]) == 25 and len(chart["fair_value"]) == 37
    assert len(chart["fan"]["p50"]) == 13 and chart["fan"]["p50"][0] == chart["price"][-1]
    assert [t["id"] for t in run["triggers"]] == ["rates", "revisions", "concentration", "capex"]
    assert run["notes"][0]["title"] == "Model run complete" and "41" not in run["model"]["version"]
    assert run["model"]["run_at"].endswith("+08:00") and run["as_of"] == run["model"]["run_at"]
    assert tmp_store.latest_run()["model"]["run_at"] == run["model"]["run_at"]
    assert all(len(d["spark"]) == 24 for d in run["drivers"]) and len(tiles["probability"]["spark"]) == 24
    assert tiles["top10"]["peak_2000"] == 0.27 and tiles["forward_pe"]["value"] == 30.0
