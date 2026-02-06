# RAG: Where We Search and Why “I didn’t find anything”

## Where we search

Chat RAG uses **two** places; both must have data for RAG to return context.

| Step | What | Env / config | Code |
|------|------|--------------|------|
| 1 | **Vertex AI Vector Search** | `VERTEX_INDEX_ENDPOINT_ID`, `VERTEX_DEPLOYED_INDEX_ID` | `mobius-chat/app/services/published_rag_search.py`: `endpoint.find_neighbors(queries=[embedding], ...)` → returns list of **ids** |
| 2 | **Postgres** | `CHAT_RAG_DATABASE_URL` | Same file: `SELECT ... FROM published_rag_metadata WHERE id::text = ANY(%s)` with those ids → returns **text + metadata** |

- **Vertex** holds **embeddings + filter metadata** (e.g. `document_payer`, `source_type`). Search returns **neighbor ids**.
- **Postgres** holds **metadata + text** only (no embeddings). Chat fetches rows by those ids to get the text shown in the answer.

So: **Vertex index** and **Postgres `published_rag_metadata`** must both be populated, and **ids must match** (same id in Vertex and in Postgres).

---

## Why “I didn’t find anything specific”

One of these is true:

1. **Vertex returned 0 neighbor ids**  
   - Index is empty, or  
   - No vectors are close enough to the query embedding, or  
   - Filters (e.g. `CHAT_RAG_FILTER_PAYER=Sunshine Health`) exclude all datapoints (document_payer/state/program in index don’t match).

2. **Vertex returned ids but Postgres returned 0 rows for those ids**  
   - **Wrong DB:** Chat is querying a different Postgres than the one the sync job writes to.  
   - **Sync never ran:** No one has run the script that writes to `published_rag_metadata` and upserts to Vertex.  
   - **Sync ran against a different DB:** `CHAT_DATABASE_URL` (dbt/sync) ≠ `CHAT_RAG_DATABASE_URL` (Chat).

---

## Scripts that populate the DBs (and Vertex)

| Script | What it does | When it runs |
|--------|----------------|--------------|
| **mobius-dbt/scripts/sync_mart_to_chat.py** | Reads BigQuery mart `published_rag_embeddings` → writes **metadata** to Postgres `published_rag_metadata` (at `CHAT_DATABASE_URL`) and **upserts vectors** to Vertex. | Manually: `cd mobius-dbt && python scripts/sync_mart_to_chat.py` **or** as step 4 of `land_and_dbt_run.sh` (if `CHAT_DATABASE_URL` and `VERTEX_INDEX_ID` are set). |
| **mobius-dbt/scripts/land_and_dbt_run.sh** | 1) Ingest RAG Postgres → BigQuery landing, 2) dbt run (mart), 3) dbt test, 4) **Optional** sync mart → Chat (Postgres + Vertex). | Manually: `cd mobius-dbt && ./scripts/land_and_dbt_run.sh` (step 4 runs only if `CHAT_DATABASE_URL` and `VERTEX_INDEX_ID` are set in mobius-dbt `.env`). |

So the **same** script that fills the **Vertex index** must write to the **same** Postgres that Chat uses:

- **dbt/sync** writes to: `CHAT_DATABASE_URL` (e.g. `postgresql://postgres:***@34.59.175.121:5432/mobius_chat`).
- **Chat** reads from: `CHAT_RAG_DATABASE_URL` (in mobius-chat or mobius-config `.env`).

**Required:** `CHAT_DATABASE_URL` (mobius-dbt) = `CHAT_RAG_DATABASE_URL` (mobius-chat) — same host, database, and user so the same `published_rag_metadata` table is used.

---

## What to check

1. **Postgres (Chat’s DB)**  
   Using the same host/db/user as in `CHAT_RAG_DATABASE_URL`:
   ```bash
   psql -h 34.59.175.121 -U postgres -d mobius_chat -c "SELECT COUNT(*) FROM published_rag_metadata;"
   ```
   - If **0**: Sync has not written to this DB (or wrote to a different one). Run sync with `CHAT_DATABASE_URL` set to this same URL.
   - If **> 0**: Metadata exists; next check is Vertex.

2. **Vertex index**  
   In GCP Console: Vertex AI → Vector Search → your index / endpoint. Confirm the index has **datapoints** (sync writes them). If the index is empty, run the sync so it upserts vectors.

3. **Env alignment**  
   - **mobius-chat** (or mobius-config) `.env`: `CHAT_RAG_DATABASE_URL=postgresql://postgres:***@34.59.175.121:5432/mobius_chat`  
   - **mobius-dbt** `.env`: `CHAT_DATABASE_URL=postgresql://postgres:***@34.59.175.121:5432/mobius_chat`  
   Same URL → Chat and sync use the same DB.

4. **Run sync** (if Postgres or Vertex is empty)  
   ```bash
   cd mobius-dbt
   # Ensure .env has: BQ_PROJECT, BQ_DATASET, CHAT_DATABASE_URL, VERTEX_PROJECT, VERTEX_REGION, VERTEX_INDEX_ID (and optionally VERTEX_INDEX_ENDPOINT_ID)
   python scripts/sync_mart_to_chat.py
   ```
   Or run the full pipeline (ingest + dbt + sync):
   ```bash
   ./scripts/land_and_dbt_run.sh
   ```

---

## Summary

| Symptom | Likely cause | Fix |
|--------|----------------|-----|
| “Searching our materials…” then “I didn’t find anything specific” | Vertex returned 0 ids **or** Postgres returned 0 rows for those ids | 1) Ensure `CHAT_DATABASE_URL` (dbt) = `CHAT_RAG_DATABASE_URL` (Chat). 2) Run `sync_mart_to_chat.py` (or `land_and_dbt_run.sh`) so Postgres `published_rag_metadata` and the Vertex index are populated. 3) Confirm with `SELECT COUNT(*) FROM published_rag_metadata` and Vertex Console. |
| RAG says “I don’t have access to our materials right now” | One of endpoint id, deployed index id, or `CHAT_RAG_DATABASE_URL` is unset | Set `VERTEX_INDEX_ENDPOINT_ID`, `VERTEX_DEPLOYED_INDEX_ID`, `CHAT_RAG_DATABASE_URL` in mobius-config or mobius-chat `.env`. |
