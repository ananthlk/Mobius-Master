#!/usr/bin/env bash
# Run from mobius-skills/email: ./scripts/test_email_cli.sh
# Requires: python with app deps (pip install -r requirements.txt)
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD:$PYTHONPATH"

echo "=== 1. Prepare (direct) ==="
python -m app.cli prepare --to "you@example.com" --subject "CLI test" --body "Hello from CLI"

echo ""
echo "=== 2. Mailto URL (user client) ==="
python -m app.cli mailto --to "you@example.com" --subject "Hi" --body "Open in your mail client"

echo ""
echo "=== 3. Python test script (no send) ==="
python scripts/test_email.py

echo ""
echo "=== 4. Optional: prepare with LLM (if OPENAI_API_KEY set) ==="
python -m app.cli prepare --to "you@example.com" --llm "Remind them about the meeting tomorrow" || true

echo ""
echo "Done. To actually send via system: python -m app.cli send --to YOUR_EMAIL --subject Test --body Test"
