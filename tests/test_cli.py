import os

from lantern import cli


def test_load_env_fills_missing_variables_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# FRED key for the morning pull\nFRED_API_KEY=abc123\nLANTERN_OTHER='quoted'\n\n")
    monkeypatch.setattr(os, "environ", dict(os.environ))  # a copy, so nothing leaks into the other tests
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("LANTERN_OTHER", "already")
    cli.load_env(env)
    assert os.environ["FRED_API_KEY"] == "abc123"
    assert os.environ["LANTERN_OTHER"] == "already"  # a real environment variable wins over the file
    cli.load_env(tmp_path / "missing.env")  # no file: no error


def test_cli_challenger_prob_prints_both_briers(tmp_path, monkeypatch, capsys):
    from lantern import challenger, cli, config

    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(challenger, "challenger_prob", lambda store: {
        "n": 203, "brier_tabpfn": 0.0785, "brier_champion_wf": 0.0767, "brier_champion_insample": 0.0644,
        "brier_base_rate_wf": 0.0395, "model": "TabPFN v2"})
    assert cli.main(["challenger", "--prob"]) == 0
    out = capsys.readouterr().out
    assert "0.0785" in out and "0.0767" in out and "0.0395" in out


def test_cli_challenger_prob_without_tabpfn_is_a_message_not_a_traceback(tmp_path, monkeypatch, capsys):
    from lantern import challenger, cli, config

    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    def missing(store):
        raise RuntimeError("tabpfn is not installed; run `uv sync --extra challenger`")

    monkeypatch.setattr(challenger, "challenger_prob", missing)
    assert cli.main(["challenger", "--prob"]) == 1
    assert "tabpfn is not installed" in capsys.readouterr().out
