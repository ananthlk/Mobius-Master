#!/bin/bash
# Run unit and integration tests for lexicon-maintenance.
# Unit tests: no dependencies.
# Integration tests: require API running at LEXICON_API_URL (default localhost:8010).
cd "$(dirname "$0")"
python -m pytest tests/ -v "$@"
