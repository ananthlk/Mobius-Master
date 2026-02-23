#!/usr/bin/env bash
# Run Mobius regression test suite. Use after every change to catch breakage.
#
# Usage:
#   ./scripts/run_regression_tests.sh           # unit + agent routing (fast)
#   ./scripts/run_regression_tests.sh --full    # + comprehensive pipeline (slow)
#   ./scripts/run_regression_tests.sh --unit    # unit tests only
#
set -e
MOBIUS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$MOBIUS_ROOT"

export PYTHONPATH="${MOBIUS_ROOT}/mobius-chat"
FAILED=0

_run() {
  echo ""
  echo "=============================================="
  echo "$1"
  echo "=============================================="
  if eval "$2"; then
    echo "[OK] $1"
  else
    echo "[FAIL] $1"
    FAILED=1
  fi
}

# 1. Unit tests (fast)
_run "Unit tests (doc_assembly, refined_query, short_term_memory, parser, mobius_parse, intent_jurisdiction_continuity)" \
  "pytest mobius-chat/tests/test_doc_assembly.py mobius-chat/tests/test_refined_query.py mobius-chat/tests/test_short_term_memory.py mobius-chat/tests/test_parser.py mobius-chat/tests/test_mobius_parse.py mobius-chat/tests/test_intent_jurisdiction_continuity.py -v --tb=short -q"

# 2. Agent routing (LLM + blueprint) — skip with --unit
if [[ "$1" != "--unit" ]]; then
  _run "Agent routing" \
    "python mobius-chat/scripts/test_agent_routing.py"
fi

# 3. Optional: skills integration (skip if URLs not set or --unit)
if [[ "$1" == "--unit" ]]; then
  : # skip
elif [[ -n "${CHAT_SKILLS_GOOGLE_SEARCH_URL:-}" ]] || [[ -n "${CHAT_SKILLS_WEB_SCRAPER_URL:-}" ]]; then
  _run "Skills integration" \
    "python mobius-chat/scripts/test_skills_integration.py"
else
  echo ""
  echo "=============================================="
  echo "Skills integration (SKIP: CHAT_SKILLS_* not set)"
  echo "=============================================="
fi

# 4. Optional: comprehensive pipeline
if [[ "$1" == "--full" ]]; then
  _run "Comprehensive pipeline (all 7 scenarios)" \
    "python mobius-chat/scripts/test_chat_pipeline_comprehensive.py"
elif [[ "$1" == "--scenario1" ]]; then
  _run "Comprehensive pipeline (scenario 1 only)" \
    "python mobius-chat/scripts/test_chat_pipeline_comprehensive.py --scenario 1"
fi

echo ""
echo "=============================================="
if [[ $FAILED -eq 0 ]]; then
  echo "Regression suite: PASSED"
else
  echo "Regression suite: FAILED"
  exit 1
fi
