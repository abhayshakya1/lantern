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
