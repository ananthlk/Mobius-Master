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

echo "── 1/7  parse the flow from orchestrator.py  ────────────────────────"
# THIS STEP WAS MISSING and the page silently drew a deleted branch for hours.
# gen_chat_submodules.py is what re-parses run_pipeline, so leaving it out of
# the chain meant the flow (branch_on, classic_path, react_phases) was frozen
# at whenever it was last run by hand — the schema kept showing a `use_react ?`
# decision and a Classic path lane that P1a had already deleted. Exactly the
# drift this whole file exists to prevent, in the tool meant to prevent it.
python3 scripts/platform/gen_chat_submodules.py > docs/chat-submodules.json

echo "── 2/7  readiness signals (measured from source)  ───────────────────"
# MUST run before the merge. The signals it writes used to come from a dead
# session scratchpad, and the `else {}` fallback rendered zeros as measurements.
python3 scripts/platform/gen_readiness.py

echo "── 3/7  extract + merge  ────────────────────────────────────────────"
python3 scripts/platform/gen_chat_dev.py "$DATA"

echo "── 4/7  coverage (Eval Layer 1: reachability)  ──────────────────────"
# MUST run BEFORE the page. It used to be step 5/6, i.e. AFTER the page was
# written — so the page could never show a current coverage state even once
# it learned to read the file. A generated artifact whose only consumer runs
# before it: the same ordering defect that let gen_chat_submodules sit outside
# the chain, in the chain that exists to prevent it.
python3 scripts/platform/gen_coverage.py

echo "── 5/7  page  ───────────────────────────────────────────────────────"
python3 scripts/platform/gen_chat_dev_page.py "$DATA" "$OUT/index.html"

echo "── 6/7  bug log  ────────────────────────────────────────────────────"
python3 scripts/platform/gen_findings_log.py

echo "── 7/7  roadmap  ────────────────────────────────────────────────────"
python3 scripts/platform/gen_roadmap.py

if [ "${1:-}" = "--eval" ]; then
  echo "── eval: full suite + frozen-baseline gate  ───────────────────────"
  python3 scripts/platform/gen_eval_report.py || true
fi

echo
echo "clean version at docs/chat-schema/index.html"
echo "  serve:  python3 -m http.server 8144 --directory docs/chat-schema"
