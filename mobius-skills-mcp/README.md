# Mobius Skills MCP

MCP server exposing Mobius skills as tools: `google_search`, `web_scrape_review`.

## Tools

- **google_search**(query, max_results=5): Search the web via mobius-skills/google-search (Google CSE or DuckDuckGo fallback)
- **web_scrape_review**(url, include_summary=False): Scrape a single page via mobius-skills/web-scraper

## Prerequisites

- mobius-skills/google-search running on port 8004
- mobius-skills/web-scraper running on port 8002

Set env vars (or use mstart defaults):

- `CHAT_SKILLS_GOOGLE_SEARCH_URL=http://localhost:8004/search?`
- `CHAT_SKILLS_WEB_SCRAPER_URL=http://localhost:8002/scrape/review`

## Run

```bash
# From Mobius root (uses shared .venv)
cd mobius-skills-mcp && python -m app

# Or via mstart (starts on port 8006)
./mstart
```

Default: `http://localhost:8006/mcp`

## Cursor MCP config

Add to `.cursor/mcp.json` (or Cursor Settings → MCP):

```json
{
  "mcpServers": {
    "mobius-skills": {
      "url": "http://localhost:8006/mcp"
    }
  }
}
```

Ensure mobius-skills-mcp is running (`./mstart` or `python -m app` in mobius-skills-mcp).
