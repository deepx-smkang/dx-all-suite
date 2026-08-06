#!/usr/bin/env python3
"""DX Cloud (AWS) 웹 서버 — 포트 8100.

AWS Marketplace 제품(DX-Compiler, DEEPX Greengrass Solution) 진입점.
DXBaseHandler 기반 정적 가이드 페이지 — 백엔드 AWS 호출 없음.
"""

from pathlib import Path

from shared.dx_server import DXBaseHandler, DXServer

DEFAULT_PORT = 8100
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
SERVER_NAME = "DX Cloud"


class DXCloudHandler(DXBaseHandler):
    """DX Cloud (AWS) HTTP 요청 핸들러."""

    server_name = SERVER_NAME
    static_dir = STATIC_DIR
    templates_dir = TEMPLATES_DIR
    log_silent = True

    def route(self):
        if self.route_common():
            return

        if self.command == "GET" and self.url_path == "/api/hb":
            return self.send_json({"ok": True})

        self.route_legacy()


def create_server(port=DEFAULT_PORT):
    """테스트용 서버 팩토리: HTTPServer 인스턴스를 반환."""
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", port), DXCloudHandler)
    srv.daemon_threads = True
    return srv


if __name__ == "__main__":
    DXServer(DXCloudHandler, SERVER_NAME, default_port=DEFAULT_PORT).start()
