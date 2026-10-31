"""Local preview of the site: python3 tools/serve.py [port] → http://localhost:8000/

Like "python3 -m http.server", but it serves an address without an extension from the .html
file of the same name ("programok" → programok.html), as GitHub Pages does: the pages link to
each other without ".html".
"""
import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        local = super().translate_path(path)
        if not os.path.exists(local) and os.path.exists(local + '.html'):
            return local + '.html'
        return local


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(Handler, directory=ROOT)
    with http.server.ThreadingHTTPServer(('127.0.0.1', port), handler) as server:
        print(f'Előnézet: http://localhost:{port}/ (leállítás: Ctrl+C)')
        server.serve_forever()
