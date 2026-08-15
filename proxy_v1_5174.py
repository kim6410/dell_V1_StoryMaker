from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TARGET = "http://127.0.0.1:8011"


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self._proxy()

    def do_HEAD(self):
        self._proxy(head=True)

    def do_POST(self):
        self._proxy(with_body=True)

    def do_PUT(self):
        self._proxy(with_body=True)

    def do_PATCH(self):
        self._proxy(with_body=True)

    def do_DELETE(self):
        self._proxy()

    def _proxy(self, head=False, with_body=False):
        path = self.path
        if path == "/" or path == "/static/v1/":
            path = "/v1/"
        elif path.startswith("/v1-api/"):
            path = "/api/" + path[len("/v1-api/"):]
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))) if with_body else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in {"host", "connection"}}
        req = Request(TARGET + path, data=body, headers=headers, method=self.command)
        try:
            with urlopen(req, timeout=60) as res:
                data = b"" if head else res.read()
                self.send_response(res.status)
                for key, value in res.headers.items():
                    if key.lower() in {"connection", "transfer-encoding", "content-length"}:
                        continue
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if not head:
                    self.wfile.write(data)
        except HTTPError as exc:
            data = b"" if head else exc.read()
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() in {"connection", "transfer-encoding", "content-length"}:
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not head:
                self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 5174), Proxy).serve_forever()

