FROM python:3.11-slim

WORKDIR /app

# Copy catalog HTML and simple proxy server
COPY index.html .
COPY server.py .

EXPOSE 8080

# Serve specs directly from GitHub + HTML catalog
# No need to copy /docs/ — fetched on-demand from git
CMD exec python3 server.py ${PORT:-8080} 2>&1
