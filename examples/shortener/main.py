# Harness / wiring only — not an llmlang Component.
import http.server
import json
import socketserver
from pathlib import Path

from Backend.CodeGenerator import CodeGenerator
from Backend.UrlShortener import UrlShortener

shortener = UrlShortener(CodeGenerator())
PAGE = (Path(__file__).parent / "Frontend" / "ShortenerUI.html").read_text()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        code = self.path.lstrip("/")
        url = shortener.get_url(code)
        if url is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not found")
            return

        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/shorten":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        url = payload.get("url", "")

        code = shortener.create_short_code(url)

        body = json.dumps({"code": code}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    port = 8000
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Serving on http://localhost:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
