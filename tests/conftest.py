from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES / name


@pytest.fixture
def tmp_store(tmp_path):
    from lantern.store import Store

    return Store(tmp_path)
