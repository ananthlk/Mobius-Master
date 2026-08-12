FROM python:3.11-slim

WORKDIR /app

# Copy specs catalog
COPY index.html .
COPY specs ./specs

# Install dependencies (none needed for basic server)
RUN pip install --no-cache-dir gunicorn

# Create Flask app to serve static files
RUN cat > app.py << 'EOF'
from flask import Flask
from flask.helpers import send_file
import os

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_file(path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
EOF

RUN pip install --no-cache-dir flask

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "app:app"]
