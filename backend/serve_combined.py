"""
Combined server: serves the HTML frontend on /
and proxies /api/* requests to the FastAPI backend on port 8001.
Runs on port 7890 for the preview.
"""
import http.server
import urllib.request
import urllib.error
import json
import os
import sys
import threading
import subprocess
import time

HTML_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'cipp_e_IAPP_UmbertoMottolaSaas_v5_50_fix.html'
)
BACKEND_PORT = 8001
SERVE_PORT = 7890


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='/tmp', **kwargs)

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._serve_html()
        elif self.path.startswith('/api/'):
            self._proxy('GET')
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/'):
            self._proxy('POST')
        else:
            self.send_error(404)

    def _serve_html(self):
        try:
            with open(HTML_PATH, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, 'HTML file not found')

    def _proxy(self, method):
        url = f'http://127.0.0.1:{BACKEND_PORT}{self.path}'
        try:
            body = None
            headers = {}
            if method == 'POST':
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length) if length else None
                headers['Content-Type'] = self.headers.get('Content-Type', 'application/json')

            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
                self.send_header('Content-Length', str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def log_message(self, format, *args):
        sys.stderr.write(f"[PROXY] {args[0]}\n")


def start_backend():
    """Start FastAPI backend on port 8001 in background."""
    env = os.environ.copy()
    env['PORT'] = str(BACKEND_PORT)
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app',
         '--host', '127.0.0.1', '--port', str(BACKEND_PORT),
         '--loop', 'asyncio', '--http', 'h11'],
        cwd=os.path.dirname(__file__),
        env=env,
        stdout=sys.stderr,
        stderr=sys.stderr
    )
    return proc


if __name__ == '__main__':
    # Start FastAPI backend
    print(f"[BOOT] Starting FastAPI backend on port {BACKEND_PORT}...", file=sys.stderr)
    backend = start_backend()
    time.sleep(3)  # Wait for backend to start

    # Start proxy server
    print(f"[BOOT] Starting proxy server on port {SERVE_PORT}...", file=sys.stderr)
    print(f"[BOOT] Frontend: http://localhost:{SERVE_PORT}/", file=sys.stderr)
    print(f"[BOOT] API: http://localhost:{SERVE_PORT}/api/...", file=sys.stderr)

    server = http.server.ThreadingHTTPServer(('0.0.0.0', SERVE_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        backend.terminate()
        server.server_close()
