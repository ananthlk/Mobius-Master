#!/usr/bin/env bash
# Run all MCP and skills-related tests.
# Usage: ./scripts/run_mcp_skills_tests.sh
# Optional: run with mstart active for integration tests (real Google search, web scrape).
set -e
cd "$(dirname "$0")/.."

echo "=== mobius-chat: MCP manager, tool agent, route triggers (unit) ==="
python -m pytest mobius-chat/tests/test_mcp_manager.py mobius-chat/tests/test_tool_agent.py mobius-chat/tests/test_route_triggers.py -v

echo ""
echo "=== mobius-skills-mcp: tool validation ==="
python -m pytest mobius-skills-mcp/tests/test_server_tools.py -v

echo ""
echo "=== mobius-chat: MCP integration (real Google search, web scrape) ==="
echo "These skip if MCP + google-search + web-scraper are not running (e.g. via mstart)."
python -m pytest mobius-chat/tests/test_mcp_skills_integration.py -v -s

echo ""
echo "=== All MCP/skills tests completed ==="
