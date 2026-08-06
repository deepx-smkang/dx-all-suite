"""DX Cloud (AWS) server unit tests."""

import json
import urllib.request
from http.server import ThreadingHTTPServer

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
    from dx_cloud.server import DXCloudHandler, create_server
    srv = create_server(port=0)
    try:
        assert isinstance(srv, ThreadingHTTPServer)
        assert srv.RequestHandlerClass is DXCloudHandler
        assert srv.server_address[1] > 0
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
    assert json.loads(body) == {"ok": True}


def test_index_has_all_language_spans(server):
    """Every UI string carries all 6 language spans (8 spans per language)."""
    _, body = _get("/", server)
    for lang in ("ko", "en", "es", "ja", "zh-CN", "zh-TW"):
        assert body.count(f'<span class="{lang}">') == 8, lang


def test_css_has_lang_visibility_and_card_rules(server):
    """dx-cloud.css must hide inactive language spans and define layout classes."""
    status, css = _get("/static/css/dx-cloud.css", server)
    assert status == 200
    assert "html[lang=" in css or "body.lang-" in css
    assert ".card{" in css
