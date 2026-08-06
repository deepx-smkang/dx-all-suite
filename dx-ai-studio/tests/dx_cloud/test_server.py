"""DX Cloud (AWS) server unit tests."""

import urllib.request

import pytest

from tests.server_helpers import start_module_server


@pytest.fixture(scope="module")
def server():
    srv, port = start_module_server("dx_cloud")
    yield port
    srv.shutdown()
    srv.server_close()


def _get(path, port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def test_create_server_returns_http_server():
    from dx_cloud.server import create_server
    srv = create_server(port=28100)
    try:
        assert srv.server_address[1] == 28100
    finally:
        srv.server_close()


def test_index_serves_html(server):
    status, body = _get("/", server)
    assert status == 200
    assert "AWS Compiler" in body
    assert "AWS Greengrass" in body


def test_index_has_marketplace_links(server):
    _, body = _get("/", server)
    assert "aws.amazon.com/marketplace" in body


def test_hb(server):
    status, body = _get("/api/hb", server)
    assert status == 200
    assert "true" in body or '"ok"' in body
