import importlib.util
from pathlib import Path

from lantern import config


def test_fetch_uses_the_honest_user_agent():
    spec = importlib.util.spec_from_file_location("fetch_filings", Path(__file__).parent.parent / "scripts" / "fetch_filings.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.UA == {"User-Agent": config.SEC_USER_AGENT}  # no browser impersonation anywhere in the project
