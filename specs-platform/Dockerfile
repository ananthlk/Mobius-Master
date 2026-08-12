FROM python:3.11-slim

WORKDIR /app

# Copy catalog HTML
COPY specs-platform/index.html .

# Copy all spec documents from git into /specs/ so Cloud Run serves them locally
# This makes specs accessible both in the catalog AND as standalone files
COPY docs ./specs

EXPOSE 8080

# Serve on PORT (default 8080 for Cloud Run)
CMD exec python3 -m http.server ${PORT:-8080} 2>&1
