# mobius-skills-core

Shared skill implementations for Mobius.

## What this package is

One implementation per capability — google search, web scrape, healthcare
lookup, corpus search (published RAG), lazy retrieval, per-thread upload
search. Consumers wrap these for their surface:

- **`mobius-chat`** imports the functions directly into its in-process
  builtin registry — fast-path, no network hop.
- **`mobius-skills-mcp`** wraps the same functions as MCP tools — reachable
  by any external MCP client (Claude Desktop, other Mobius modules).

Both surfaces call the same code. Fix a bug once, both get it.

## Why it exists

Before this package, each capability was implemented twice — once in the
chat's builtin registry and once in the MCP server. The duplication forced
maintainers to keep two copies in sync (literal `# keep in sync with …`
comments in the codebase), doubled the test surface, and let the two
surfaces drift on spec minutiae (timeouts, retry counts, response
formats). This package is the single source of truth.

## Adding a new skill — decision rubric

Every skill has two independent dimensions:

| Dimension | Options |
|---|---|
| **Implementation** | Lives here, always |
| **Surface** | Direct-import into chat, MCP tool, or both |

### Pick your surface

A skill goes into chat as a direct import when:
- It's called on most turns (latency compounds — in-process beats localhost HTTP)
- Dependency footprint is small (no heavy ML/vector libs, no native builds)
- Chat is the only realistic consumer

A skill stays MCP-only when:
- Dependencies are heavy or exotic (large models, native libs)
- Chat rarely calls it
- Other Mobius modules or external agents are primary consumers
- Independent release cadence is desirable

A skill registers on **both** surfaces when:
- Chat uses it frequently (import for perf) AND
- Other modules / external agents also want it (MCP for reach)

You can change the surface later without touching the implementation.
That's the point.

## Layout

```
mobius_skills_core/
├─ _types.py               # SkillResult, SourceRef, ChunkRef, SkillUsage
├─ skills/
│  ├─ google_search.py     # run_google_search(query, n) → SkillResult
│  ├─ web_scrape.py        # run_web_scrape(url, mode) → SkillResult
│  ├─ healthcare.py        # run_healthcare_query(entity) → SkillResult
│  ├─ document_upload.py   # run_document_upload_info() → SkillResult
│  ├─ list_thread_uploads.py
│  ├─ corpus_search.py     # full-pipeline RAG against approved corpus
│  ├─ lazy_rag.py          # lazy vector-only retrieval (shared by
│  │                       # thread_corpus_search + lazy_corpus_search)
│  └─ __init__.py
└─ __init__.py
```

## Testing

`pytest` in this package tests the core functions with mocked HTTP / DB.
Integration coverage (chat end-to-end, MCP over the wire) lives in the
respective consumer repos.

## License

Internal to Mobius.
