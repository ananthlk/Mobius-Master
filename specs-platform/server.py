#!/usr/bin/env python3
"""
Specs Catalog Server
- Serves index.html (catalog UI)
- Proxies /specs/* requests to GitHub raw content URLs
- No copying files — specs sourced directly from git
"""

import os
import sys
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = int(os.environ.get('PORT', sys.argv[1] if len(sys.argv) > 1 else 8080))
GITHUB_RAW = "https://raw.githubusercontent.com/ananthlk/Mobius-Master/main/docs"

class SpecsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests."""

        # Serve index.html for root
        if self.path == '/' or self.path == '':
            self.serve_file('index.html', 'text/html')
            return

        # Proxy spec requests to GitHub
        if self.path.startswith('/specs/'):
            spec_path = self.path[7:]  # Remove '/specs/' prefix
            github_url = f"{GITHUB_RAW}/{spec_path}"

            try:
                with urllib.request.urlopen(github_url, timeout=5) as response:
                    content = response.read()
                    content_type = self.get_content_type(spec_path)

                    self.send_response(200)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', len(content))
                    self.send_header('Cache-Control', 'public, max-age=3600')  # Cache 1 hour
                    self.end_headers()
                    self.wfile.write(content)
                    return

            except urllib.error.HTTPError as e:
                self.send_error(e.code, f"Spec not found in git: {spec_path}")
                return
            except urllib.error.URLError as e:
                self.send_error(503, f"GitHub unreachable: {e}")
                return

        # Serve static files (CSS, JS) if they exist locally
        if self.path.startswith('/'):
            file_path = self.path.lstrip('/')
            if Path(file_path).exists() and not '..' in file_path:
                self.serve_file(file_path, self.get_content_type(file_path))
                return

        self.send_error(404, f"Not found: {self.path}")

    def serve_file(self, file_path, content_type):
        """Serve a local file."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def get_content_type(self, path):
        """Determine content type from file extension."""
        if path.endswith('.md'):
            return 'text/markdown'
        elif path.endswith('.html'):
            return 'text/html'
        elif path.endswith('.css'):
            return 'text/css'
        elif path.endswith('.js'):
            return 'application/javascript'
        elif path.endswith('.json'):
            return 'application/json'
        else:
            return 'text/plain'

    def log_message(self, format, *args):
        """Suppress verbose logging."""
        if '200' in format or '304' in format:
            return  # Don't log successful requests
        print(f"{self.client_address[0]} - {format % args}", file=sys.stderr)

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), SpecsHandler)
    print(f"Specs Catalog Server running on port {PORT}")
    print(f"  Catalog: http://localhost:{PORT}/")
    print(f"  Specs sourced from: {GITHUB_RAW}/")
    print(f"  No files copied — all specs fetched on-demand from git")
    server.serve_forever()
