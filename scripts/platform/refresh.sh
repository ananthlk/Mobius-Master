#!/usr/bin/env bash
# Regenerate every chat-schema artifact from source, in dependency order.
#
# Ananth 2026-09-08: "as things get updated keep updating your node diagrams,
# so that we have a clean version."
#
# One command, fixed paths inside the repo. Everything below is DERIVED from
# scripts/platform/chat_node_content.py + refactor_roadmap.py — never hand-edit
# an output. Run this after any content change and commit the result, so the
# published page, the bug log and the roadmap can never disagree.
#
#   ./scripts/platform/refresh.sh            regenerate (no tests)
#   ./scripts/platform/refresh.sh --eval     also run the full suite + gate
#
# Exits non-zero if the roadmap has an unassigned bug — a new finding must be
# sequenced into a phase or given an explicit reason for sitting outside.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$PWD"
OUT="$ROOT/docs/chat-schema"
DATA="$OUT/chat-dev.json"
mkdir -p "$OUT"

echo "── 1/4  extract + merge  ────────────────────────────────────────────"
python3 scripts/platform/gen_chat_dev.py "$DATA"

echo "── 2/4  page  ───────────────────────────────────────────────────────"
python3 scripts/platform/gen_chat_dev_page.py "$DATA" "$OUT/index.html"

echo "── 3/4  bug log  ────────────────────────────────────────────────────"
python3 scripts/platform/gen_findings_log.py

echo "── 4/4  roadmap  ────────────────────────────────────────────────────"
python3 scripts/platform/gen_roadmap.py

if [ "${1:-}" = "--eval" ]; then
  echo "── eval: full suite + frozen-baseline gate  ───────────────────────"
  python3 scripts/platform/gen_eval_report.py || true
fi

echo
echo "clean version at docs/chat-schema/index.html"
echo "  serve:  python3 -m http.server 8144 --directory docs/chat-schema"
