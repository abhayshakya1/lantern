import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "fetch_market", Path(__file__).parent.parent / "scripts/market/fetch_market.py")
fm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fm)


def test_name_token_skips_sgx_abbreviations():
    # "Hldgs" is SGX's abbreviation; it never appears in the report itself
    assert fm._name_token("Jep Hldgs Ltd") == "jep"
    assert fm._name_token("Hgh Hldgs Ltd") == "hgh"
    assert fm._name_token("Micro-Mechanics (Hldgs) Ltd") == "mechanics"
    assert fm._name_token("Koh Brothers Eco Engineering Ltd") == "engineering"
