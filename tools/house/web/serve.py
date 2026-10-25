"""Local preview server for the house page: plain static files, never cached by the browser.

    python3 博客陪伴小屋/web/tools/serve.py 8765 博客陪伴小屋
    python3 博客陪伴小屋/web/tools/serve.py 8767 博客陪伴小屋 cache    (cacheable, as a real host: for
                                                                     testing the returning-visitor path)
"""
import http.server, functools, sys
from pathlib import Path

CACHE = len(sys.argv) > 3 and sys.argv[3] == 'cache'

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Keep old preview links working after mounting web/ at the URL root.
        if self.path == '/web' or self.path.startswith('/web/'):
            self.send_response(302)
            self.send_header('Location', self.path[4:] or '/index.html')
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'max-age=3600' if CACHE else 'no-store')
        super().end_headers()

port = int(sys.argv[1])
root = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parents[1]
if (root / 'web' / 'index.html').is_file():
    root = root / 'web'
http.server.ThreadingHTTPServer(('', port), functools.partial(Handler, directory=root)).serve_forever()
