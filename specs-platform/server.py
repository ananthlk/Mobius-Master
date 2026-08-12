#!/usr/bin/env python3
import os
import sys
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get('PORT', '8080'))
GITHUB_RAW = "https://raw.githubusercontent.com/ananthlk/Mobius-Master/main/docs"
SPEC_DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Serve index.html for root
        if self.path == '/' or self.path == '':
            try:
                with open(os.path.join(SPEC_DIR, 'index.html'), 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f.read())
                return
            except:
                self.send_error(500)
                return
        
        # Proxy /specs/* to GitHub
        if self.path.startswith('/specs/'):
            spec_path = self.path[7:]
            url = f"{GITHUB_RAW}/{spec_path}"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(r.read())
                    return
            except:
                self.send_error(404)
                return
        
        self.send_error(404)
    
    def log_message(self, format, *args):
        pass  # suppress logs

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Server running on port {PORT}")
    server.serve_forever()
