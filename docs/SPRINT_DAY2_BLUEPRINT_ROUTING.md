# Sprint: Day 2 — Blueprint / Routing + Tool Agent Production

**Focus module:** `app/planner/blueprint.py`, `app/planner/route_triggers.py`, `app/services/tool_agent.py`  
**Gate:** `test_agent_routing.py` — Search and capability questions route to tool; skills integration tests pass

---

## Quick Status Summary

| Area | Status | Notes |
|------|--------|-------|
| **Explicit routing** | DONE | "Search for X", "What can you do?", "Scrape URL" → tool |
| **Route triggers** | DONE | TRIGGERS_WEB expanded: scrape, capability phrases |
| **Blueprint override** | DONE | detect_route overrides planner for first sq when conf=1.0 |
| **Tool agent production** | DONE | Top-level try/except, null safety, MCP retries |
| **MCP server production** | DONE | Logging, input validation, HTTPError fix |
| **Gate scripts** | DONE | test_agent_routing.py, test_skills_integration.py |

---

## Task Checklist

### 1. Route triggers: explicit routing to tool

| Task | Status | Notes |
|------|--------|-------|
| "Search for X" → tool | DONE | TRIGGERS_WEB |
| "What can you do?" → tool | DONE | Added to TRIGGERS_WEB |
| "Scrape https://..." → tool | DONE | scrape, scrape this, read this webpage, etc. |
| Clash handling (web + RAG) | DONE | detect_route returns clarify_choices |

### 2. Blueprint deterministic override

| Task | Status | Notes |
|------|--------|-------|
| detect_route(user_message) in build_blueprint | DONE | blueprint.py |
| First subquestion gets agent override when conf=1.0 | DONE | |
| Patient subquestions skip override | DONE | sq.kind != "patient" |

### 3. Tool agent production-ready

| Task | Status | Notes |
|------|--------|-------|
| Top-level try/except in answer_tool | DONE | Catches unexpected errors, returns graceful message |
| Null safety (result_text) | DONE | result_text or "" |
| call_mcp_tool wrapped in try/except | DONE | Per-call error handling |
| Actionable before capability (scrape+URL) | DONE | Fixes "Scrape URL" returning capability answer |

### 4. MCP + mobius-skills-mcp production (from MCP plan)

| Task | Status | Notes |
|------|--------|-------|
| mcp_manager: event loop safety, timeouts, retries | DONE | |
| mobius-skills-mcp: logging, validation, HTTPError fix | DONE | |
| tool_agent: defensive try/except, null checks | DONE | |

---

## Gate Tests

### Agent routing (fast, no external services)

```bash
cd /Users/ananth/Mobius
PYTHONPATH=mobius-chat python mobius-chat/scripts/test_agent_routing.py
```

**Expected:** All 5 tests pass.

### Skills integration (requires mstart for e2e)

```bash
cd /Users/ananth/Mobius
# Unit tests (always run):
python -m pytest mobius-chat/tests/test_tool_agent.py mobius-chat/tests/test_mcp_manager.py mobius-chat/tests/test_route_triggers.py -v

# Full skills suite (integration skips when MCP not running):
./scripts/run_mcp_skills_tests.sh
```

---

## Files Modified

| File | Changes |
|------|---------|
| `app/planner/route_triggers.py` | Added scrape, "what can you do", capability triggers |
| `app/services/tool_agent.py` | Top-level try/except, _answer_tool_impl extraction; actionable-before-capability |
| `mobius-chat/scripts/test_agent_routing.py` | NEW — Day 2 gate script |
| `mobius-chat/scripts/test_skills_integration.py` | NEW — Day 16 gate script |
| `mobius-chat/tests/test_route_triggers.py` | test_scrape_url, test_what_can_you_do |

---

## Definition of Done (Day 2 Gate)

- [x] "Search for X" routes to tool
- [x] "What can you do?" routes to tool
- [x] "Scrape https://..." routes to tool
- [x] Blueprint assigns agent=tool for these
- [x] test_agent_routing.py passes (5/5)
- [x] Tool agent + MCP + mobius-skills-mcp production-ready
- [x] run_mcp_skills_tests.sh covers unit + integration

---

## Regression One-Liner

```bash
cd /Users/ananth/Mobius && PYTHONPATH=mobius-chat python mobius-chat/scripts/test_agent_routing.py && python -m pytest mobius-chat/tests/test_tool_agent.py mobius-chat/tests/test_route_triggers.py mobius-chat/tests/test_mcp_manager.py -v -q
```
