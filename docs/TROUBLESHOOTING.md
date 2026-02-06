# Mobius troubleshooting

## Chat: GET /chat/stream returns 404

The frontend uses **Server-Sent Events** at `GET /chat/stream/{correlation_id}` for live thinking/message updates. If that URL returns **404**, the process listening on port 8000 is an **old** API that doesn’t have the stream route (e.g. a leftover from before the stream was added).

**Cause:** Another process is still bound to port 8000. New API processes started by `mstart` then fail with “address already in use” and exit, so the old process keeps serving (without `/chat/stream`).

**Fix:**

1. **Stop everything and free the port:** From the Mobius repo root run:
   ```bash
   ./mstop
   ```
   `mstop` now also kills any process still bound to Mobius ports (8000, 5001, 8001), so the port is freed even if the PID file was wrong or from another run.

2. **Start again:**
   ```bash
   ./mstart
   ```

3. **Confirm the API has the stream route:** Open `http://localhost:8000/openapi.json` and search for `"\/chat\/stream\/"`. If you see it, the new API is running.

---

## Chat: Debug trace (see which modules/functions run)

To pinpoint where a request goes (e.g. why RAG or LLM fails), enable **trace mode**. The worker log will show every key entry: `[trace] module.function entered` with optional kwargs.

**Enable:** In `mobius-chat/.env` (or `mobius-config/.env` before `inject_env.sh mobius-chat`) set:
```bash
CHAT_DEBUG_TRACE=1
# or
DEBUG_TRACE=1
```
Accepted values: `1`, `true`, `yes` (case-insensitive).

**Restart** the chat worker (`mstop` then `mstart`), send a message, then:
```bash
tail -200 .mobius_logs/mobius-chat-worker.log | grep '\[trace\]'
```
You’ll see the call order, e.g. `worker.run.process_one` → `planner.parser.parse` → `chat_config.get_chat_config` → `services.llm_provider.get_llm_provider` → `services.non_patient_rag.answer_non_patient` → `services.published_rag_search.search_published_rag`, etc.

**Disable:** Remove or comment out `CHAT_DEBUG_TRACE` / `DEBUG_TRACE`, or set to `0`/`false`, then restart the worker.

---

## Chat: Thinking / final message not streaming live (only 2 lines then full response)

When the **worker** runs in a separate process (Redis queue), progress (thinking lines and message chunks) lives in the worker’s memory. The API must subscribe to **Redis pub/sub** so the SSE stream can push it to the browser.

**Cause:** The API is not using Redis for the stream (e.g. `QUEUE_TYPE=memory` in .env overwrote the shell, or the API was started without mchatc).

**Fix — use the env switch:**

1. In **mobius-chat/.env** set:
   ```bash
   CHAT_LIVE_STREAM=1
   QUEUE_TYPE=redis
   REDIS_URL=redis://localhost:6379/0
   ```
   - `CHAT_LIVE_STREAM=1` forces the API to subscribe to Redis for progress (stream = live; no stream = polling).
   - `QUEUE_TYPE=redis` ensures the API and worker share the same queue so requests reach the worker.

2. **Restart both API and worker:** `mstop` then `mstart`.

3. **Check API log** when you send a message:
   - `Stream <id>: using Redis progress (subscribe)` — live stream is on.
   - `Stream <id>: using in-memory progress (...)` — set `CHAT_LIVE_STREAM=1` and `QUEUE_TYPE=redis` in .env and restart.

**Debug streaming with timestamps:** Progress events include `ts` (unix) and `ts_readable` (e.g. `13:45:02.123`) so you can see when each event was written vs when it was received.

- **Worker log** (`.mobius_logs/mobius-chat-worker.log`): `[progress] published event thinking cid=... written_at=13:45:02.123` — when the worker wrote and published to Redis.
- **API log** (`.mobius_logs/mobius-chat-api.log`): `[stream] received #N cid=... event=thinking written_at=13:45:02.123 received_at=13:45:02.456` — when the API received from Redis (compare `written_at` vs `received_at`).
- **Browser console** (F12 → Console): `[stream] thinking received_at=13:45:02.500 written_at=13:45:02.123` — when the frontend got the SSE event.

If you see `written_at` in the worker but no matching `[stream] received` in the API, the API may have subscribed to Redis **after** the worker published (Redis pub/sub does not retain messages). If you see `received_at` in the API but no `[stream]` lines in the browser, the SSE connection may not be established or the frontend may be using polling fallback.

---

## RAG frontend: `ERR_CONNECTION_REFUSED` to `localhost:8001`

The RAG UI (Document Status, Error Review, etc.) calls the **mobius-rag backend** at `http://localhost:8001`. This error means nothing is listening on port 8001.

**Cause:** The mobius-rag backend did not start or it crashed.

**Fix:**

1. **If you use `mstart`:** From your Mobius folder, check whether the RAG backend started:
   ```bash
   cd ~/Mobius
   tail -50 .mobius_logs/mobius-rag-backend.log
   ```
   (Use your actual path if different, e.g. `~/mobius`. The `.mobius_logs` folder exists only after you run `mstart` from that directory.)
   Look for Python/uvicorn errors (e.g. missing `.venv`, DB connection, import errors). Fix the cause, then run `mstop` and `mstart` again.

2. **Start the RAG backend manually** (same port the frontend expects when run via mstart):
   ```bash
   cd mobius-rag
   source .venv/bin/activate
   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```
   Keep this terminal open. The RAG frontend (e.g. http://localhost:5173) will then reach the backend at 8001.

3. **If you run RAG alone (no mstart):** The RAG frontend defaults to `http://localhost:8000`. Start the backend on 8000:
   ```bash
   cd mobius-rag && ./start_backend.sh
   ```
   Then run the frontend (it will use 8000 by default).

**Quick check:** In a browser or terminal, open `http://localhost:8001/health` (or any RAG backend route). If you get "connection refused", the backend is not running.

---

## RAG upload: "File ... was not found" (GCP credentials)

If upload fails with something like `File /Users/ananth/Mobius RAG/mobiusos-new-....json was not found`, the path in `GOOGLE_APPLICATION_CREDENTIALS` is wrong.

**Cause:** The path often has a space (`Mobius RAG`) or points to an old folder. The repo is `Mobius/mobius-rag` (no space).

**Fix:** In `mobius-rag/.env`, set the **full path** to your service account JSON with **no spaces** in the path, e.g.:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/Users/ananth/Mobius/mobius-rag/mobiusos-new-090a058b63d9.json
```

If the JSON lives elsewhere, use that path. Then restart the RAG backend (e.g. `mstop` and `mstart`, or restart the uvicorn process).

---

## RAG: "Index 'Endpoint_mobius_chat_published_rag' is not found" (404)

Chat RAG calls Vertex Vector Search with a **deployed index ID**. If you see:

```
Index 'Endpoint_mobius_chat_published_rag' is not found.
```

**Cause:** `VERTEX_DEPLOYED_INDEX_ID` in your `.env` is wrong. Vertex expects the **exact deployed index ID** (often auto-generated), not the display name.

**Fix:**

1. In **GCP Console:** Vertex AI → Vector S
earch → **Index Endpoints** → open your endpoint (e.g. `mobius_chat_published_rag_endpoint`).
2. In the **Deployed indexes** table, find the **ID** column (not the display name). It often looks like `endpoint_mobius_chat_publi_1769989702095` or similar.
3. Set that value in your env:
   - **mobius-config/.env:** `VERTEX_DEPLOYED_INDEX_ID=that_exact_id`
   - Then: `cd mobius-config && ./inject_env.sh mobius-chat`
4. Restart chat: `mstop && mstart`.

**If the error persists:** The worker may be running old code (e.g. from another clone or before the fix). Run `mstart` from the **same repo** where you edited the code (e.g. `cd /Users/ananth/Mobius` then `mstop && mstart`). After restart, the worker log should show a line like `[worker startup] _chat_root=... VERTEX_DEPLOYED_INDEX_ID=...`; when you send a RAG query you should see `[RAG find_neighbors] deployed_index_id=...`. If you still see the old error and no such lines, the worker is not loading this repo’s code.

**Optional (gcloud):** To list deployed index IDs for an endpoint:
```bash
gcloud ai index-endpoints describe 4513040034206580736 --region=us-central1 --project=mobiusos-new --format="yaml(deployedIndexes)"
```
Use the `id` field from the deployed index you want.

---

## Chat: "Vertex AI requires CHAT_VERTEX_PROJECT_ID or VERTEX_PROJECT_ID"

The chat LLM uses Vertex AI and needs a GCP project id.

**Fix:** In `mobius-chat/.env` set:
```bash
VERTEX_PROJECT_ID=mobiusos-new
VERTEX_LOCATION=us-central1
VERTEX_MODEL=gemini-2.5-flash
```
(Use your actual GCP project id.) Also set `GOOGLE_APPLICATION_CREDENTIALS` to the full path of your GCP service account JSON. Then restart the chat API and worker (`mstop` and `mstart`).

---

## mstop: Postgres connections still open after stopping

**Symptom:** After running `mstop`, `lsof -i :5432` still shows many Python processes connected to Postgres. You may see "too many clients" when starting services again.

**Cause:**
- **uvicorn --reload** spawns a child worker; killing the parent can leave the child running and holding DB connections.
- **Orphaned processes** from earlier runs that were not in the PID file.

**What mstop does now:**
1. Kills each PID from the file **and its child processes** (process tree).
2. Kills stragglers (uvicorn, workers, vite, etc.) by pattern.
3. Kills processes on Mobius ports (5001, 8000, 8001, etc.).
4. **Kills Python processes connected to Postgres** whose command line contains "mobius" (orphaned Mobius services).

**If connections still linger:**
```bash
# See what's connected
lsof -i :5432 | grep Python

# Force-kill those PIDs (replace with actual PIDs from above)
kill -9 <pid1> <pid2> ...
```

**Browser:** Closing the browser does **not** release Postgres connections. Connections are held by the **Python backends** (chat API, RAG backend, workers). Only stopping those processes releases them.
