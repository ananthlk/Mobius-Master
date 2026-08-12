FROM python:3.11-slim

WORKDIR /app

# Copy specs catalog
COPY index.html .
COPY specs/ ./specs/ 2>/dev/null || true

# Simple HTTP server
RUN echo 'import http.server\nimport socketserver\nimport os\n\nPORT = int(os.getenv("PORT", "8080"))\n\nclass MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):\n    def end_headers(self):\n        # Allow for CORS and cache policy\n        self.send_header("Cache-Control", "public, max-age=3600")\n        super().end_headers()\n\nwith socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:\n    print(f"Server running on port {PORT}")\n    httpd.serve_forever()' > server.py

EXPOSE 8080

CMD ["python", "server.py"]
