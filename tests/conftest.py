import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES / name


@pytest.fixture
def tmp_store(tmp_path):
    from lantern.store import Store

    return Store(tmp_path)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def fixture_server():
    """Serve tests/fixtures over HTTP on a free local port; yields the base URL."""
    handler = functools.partial(_QuietHandler, directory=str(FIXTURES))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
