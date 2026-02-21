# Retriever Integration – Change Investigation

Investigation from last committed state (`fa2b3f0`) to current working tree to identify what changed and what may have been lost or broken.

## Baseline: Last Committed State

- **mobius-chat branch**: `product-demo-feb-6`
- **Last commit**: `fa2b3f0` – "feat: jurisdiction build - clarification, context, RAG filters, integrator caveats"
- **Note**: The retriever backend (`retriever_backend.py`, `retrieval_emit_adapter.py`, `retrieval_persistence.py`, `doc_assembly.py`) and RAG API path were **already present** in the committed code; `non_patient_rag` already called `retrieve_for_chat` from `retriever_backend`.

---

## Uncommitted Changes Summary

| Area | Files | Summary |
|------|-------|---------|
| **Emissions / progress** | `app/storage/progress.py`, `app/main.py` | DB fallback for thinking when Redis queue used; `get_progress_from_db` |
| **Retriever / RAG** | `app/services/non_patient_rag.py`, `app/services/retriever_backend.py` | Defensive handling for list/dict, emit adapter wiring |
| **Worker / turns** | `app/worker/run.py` | `insert_turn`, clarification persistence, `append_turn_messages` |
| **API** | `app/main.py` | `NoCacheStaticFiles`, `thread_id`, `ensure_thread`, DB warning |
| **Frontend** | `frontend/src/app.ts`, `frontend/static/app.js` | `loadRecentTurns`, thinking auto-expand, cited sources |
| **Schema / config** | Various | `.env.example`, migrations, `paragraph_index` in published_rag_search |

---

## Critical Finding: Frontend app.js Size Drop

| State | Lines | Size |
|-------|-------|------|
| **Committed** (`fa2b3f0`) | 3,647 | ~120kb (incl. mobius-auth) |
| **Current (built)** | ~435 | ~16kb |

**Cause**: The committed `app.js` included `@mobius/auth` (AuthService, normalizeUser, etc.). The current `app.ts` does not import it, so the build only contains the chat app.

**Implications**:
- If auth was previously used, it was removed or never wired in the current app.ts.
- `frontend/package.json` still lists `"@mobius/auth": "file:../../mobius-auth"`.
- Current `frontend/src/app.ts` has no auth import, so auth is not bundled.

---

## File-by-File Changes (Uncommitted vs fa2b3f0)

### app/main.py
- Added `NoCacheStaticFiles` for cache-busting
- Added `ensure_thread`, `thread_id` to `post_chat`
- Added `get_progress_from_db` fallback for Redis queue (emissions from DB)
- Added DB warning on startup when `CHAT_RAG_DATABASE_URL` unset
- Added `Cache-Control` headers for index and static files

### app/storage/progress.py
- Added `get_progress_from_db()` for DB-backed thinking when worker is separate
- `get_progress_events_from_db`: defensive `_norm_data()` for `event_data`
- No breaking changes to existing behavior

### app/services/non_patient_rag.py
- Import and use `wrap_emitter_for_user` for doc assembly
- Defensive `_to_dict` and `isinstance(c, dict)` for chunks
- Pass `wrap_emitter_for_user(emitter)` to `assemble_docs`

### app/worker/run.py
- Added `insert_turn` for completed and clarification responses
- Added `append_turn_messages` for thread history
- Added `duration_ms`, `config_sha`, `thread_id` to payload
- Jurisdiction clarification now runs even without `thread_id`
- Many lines added; logic preserved

### app/services/retriever_backend.py (untracked; referenced by non_patient_rag)
- Handles RAG API response when top-level is a list (fix for `'list' object has no attribute 'get'`)
- Wires emit adapter; not in the diff because it’s untracked

### app/services/published_rag_search.py
- Added `paragraph_index` to SELECT and row mapping

### frontend/src/app.ts
- `addLine`: auto-expand thinking block when new lines arrive
- `renderSourceCiter`: supports `cited_source_indices` for cited styling
- `loadRecentTurns()`: fetch and display recent searches; populate on load and after send

### frontend/static/app.js
- Rebuilt from app.ts; smaller due to no auth bundle

### frontend/static/styles.css
- Minor updates (4 lines)

---

## Untracked Files (New Retriever / Persistence)

- `app/services/doc_assembly.py`
- `app/services/retrieval_emit_adapter.py`
- `app/services/retriever_backend.py`
- `app/storage/retrieval_persistence.py`
- `db/schema/014_lexicon_and_document_tags.sql`
- `db/schema/015_policy_line_tags.sql`
- `db/schema/016_retrieval_efficiency.sql`
- Various scripts under `scripts/`
- `tests/test_doc_assembly*.py`

---

## Suggested Next Steps

1. **Capture current state**
   - Stage and commit the intended changes in mobius-chat.
   - Separate commits for: emissions/progress, retriever, frontend (recent + thinking), worker/turns.

2. **Restore or drop auth**
   - If auth is required: restore `@mobius/auth` import and wiring in `app.ts`, rebuild, and verify.
   - If auth was never used: remove `@mobius/auth` from `package.json` and clean up references.

3. **Audit sidebar and helpful/documents**
   - `loadRecentTurns` populates `#recentList`.
   - Confirm `#helpfulList` and `#documentsList` are populated by their respective APIs (e.g. `/chat/history/most-helpful-searches`, `/chat/history/most-helpful-documents`).

4. **Trace emissions**
   - Confirm `chat_progress_events` is written when `QUEUE_TYPE=redis` and `CHAT_RAG_DATABASE_URL` is set.
   - Add logging or tests around `get_progress_from_db` and poll responses.

---

## Commands for Further Investigation

```bash
# mobius-chat uncommitted diff
cd mobius-chat && git diff fa2b3f0 --stat

# Specific file diff
cd mobius-chat && git diff fa2b3f0 -- app/services/non_patient_rag.py

# Compare committed vs current app.js
cd mobius-chat && git show fa2b3f0:frontend/static/app.js | wc -l
wc -l frontend/static/app.js
```
