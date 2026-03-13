# Mobius Google Search Skill

Web search service for Chat doc assembly fallback. When corpus confidence is low, Chat calls this skill to add external search results.

## Setup

1. **Create venv and install deps:**
   ```bash
   cd mobius-skills/google-search
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Optional – Google Custom Search (higher quality):**
   - In GCP Console: **APIs & Services** → **Enable APIs** → search for **Custom Search API** → Enable
   - Create [Programmable Search Engine](https://programmablesearchengine.google.com/controlpanel/create) (search the whole web)
   - Create API key at [Custom Search Overview](https://developers.google.com/custom-search/v1/overview) (Get a Key)
   - Add to `.env`:
     ```
     GOOGLE_CSE_API_KEY=your-api-key
     GOOGLE_CSE_CX=your-search-engine-id
     ```

3. **Fallback – DuckDuckGo (default, no API key):**  
   If Google isn’t configured or returns nothing, DuckDuckGo is used. Set `GOOGLE_SEARCH_USE_DUCKDUCKGO_FALLBACK=false` to disable.

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8004
```

## Chat integration

In `mobius-chat/.env`:

```
CHAT_SKILLS_GOOGLE_SEARCH_URL=http://localhost:8004/search?
```

For Cloud Run: use the deployed URL instead.
