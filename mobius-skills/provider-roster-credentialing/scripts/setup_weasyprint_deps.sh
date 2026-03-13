#!/bin/bash
# Install system dependencies for WeasyPrint (PDF generation) in provider-roster-credentialing.
# Run this once on the host where the provider-roster service runs.
# For Ubuntu/Debian; macOS uses Homebrew (see below).

set -e

if [[ "$(uname)" == "Darwin" ]]; then
  echo "macOS detected. Install WeasyPrint deps with Homebrew:"
  echo "  brew install pango"
  echo "  pip install weasyprint"
  exit 0
fi

if command -v apt-get >/dev/null 2>&1; then
  echo "Installing WeasyPrint system deps (Debian/Ubuntu)..."
  sudo apt-get update
  sudo apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libffi-dev \
    shared-mime-info
  echo "Done. Verify with: weasyprint --info"
  exit 0
fi

if command -v apk >/dev/null 2>&1; then
  echo "Alpine detected. Installing WeasyPrint deps..."
  apk add --no-cache \
    py3-pip \
    so:libgobject-2.0.so.0 \
    so:libpango-1.0.so.0 \
    so:libharfbuzz.so.0 \
    so:libharfbuzz-subset.so.0 \
    so:libfontconfig.so.1 \
    so:libpangoft2-1.0.so.0
  echo "Done. Verify with: weasyprint --info"
  exit 0
fi

echo "Unsupported OS. Install Pango and related libs manually."
echo "See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
exit 1
