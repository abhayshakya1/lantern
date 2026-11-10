import importlib.util
import json
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


def test_row_name_token_override():
    # a report may only print its brand ("ST Engineering"), so a manifest row can name the token
    assert fm._row_token({"company": "Singapore Technologies Engineering", "name_token": "engineering"}) == "engineering"
    assert fm._row_token({"company": "Jep Hldgs Ltd"}) == "jep"


def _pdf_bytes(text: str) -> bytes:
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def test_name_found_after_image_only_cover_pages(tmp_path, monkeypatch):
    # ThaiBev's report opens with four image-only pages; its name first prints on page 6
    import pymupdf
    monkeypatch.setattr(fm, "MARKET", tmp_path / "market")
    (tmp_path / "market").mkdir()
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    doc = pymupdf.open()
    for _ in range(5):
        doc.new_page()
    doc.new_page().insert_text((72, 72), "Thai Beverage Public Company Limited")
    (inbox / "THBEV_AR.pdf").write_bytes(doc.tobytes())
    rows = [{"company": "Thai Beverage", "stock_code": "Y92", "url": "", "browser_glob": "THBEV_AR*.pdf"}]
    (tmp_path / "market" / "manifest_market.json").write_text(json.dumps(rows))
    fm.main(import_dir=inbox)
    assert json.loads((tmp_path / "market" / "manifest_market.json").read_text())[0]["status"] == "ok"


def test_browser_saved_file_is_imported_and_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(fm, "MARKET", tmp_path / "market")
    (tmp_path / "market").mkdir()
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    (inbox / "VCL_Annual_Report_2025.pdf").write_bytes(_pdf_bytes("Venture Corporation Limited Annual Report 2025"))
    rows = [
        {"company": "Venture Corporation", "stock_code": "V03", "url": "", "browser_glob": "VCL_Annual_Report_2025*.pdf"},
        {"company": "Thai Beverage", "stock_code": "Y92", "url": "", "browser_glob": "THBEV_Annual*.pdf"},
    ]
    (tmp_path / "market" / "manifest_market.json").write_text(json.dumps(rows))
    fm.main(import_dir=inbox)
    out = json.loads((tmp_path / "market" / "manifest_market.json").read_text())
    assert out[0]["status"] == "ok" and out[0]["source"] == "sgx-browser" and out[0]["pages"] == 1
    assert out[1]["status"] == "awaiting-browser-save"  # not saved yet: no fetch attempted, not a failure
