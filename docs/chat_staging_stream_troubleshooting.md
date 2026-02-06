# Chat staging: "Worker has logs but no frontend"

If the API writes to Redis, the worker picks up the request and has logs, but the frontend stays on "Request sent. Waiting for worker…", the failure is in **one of two places**:

1. **Worker’s response never reaches the same Redis the API reads** (or API can’t read it).
2. **Frontend loses the SSE connection**, and the poll fallback also fails because the API never sees the response.

## How responses get back to the frontend

- **Worker → Redis**  
  Worker calls `get_queue().publish_response(correlation_id, payload)`. That does a **Redis SET** on key  
  `{REDIS_RESPONSE_KEY_PREFIX}{correlation_id}` (e.g. `mobius:chat:response:<cid>`) with TTL.  
  No Pub/Sub for the final response—it’s a key/value.

- **API → frontend**  
  - **SSE stream** (`GET /chat/stream/:id`): each loop the API checks **Redis** (`q.get_response(correlation_id)` = GET that key), then **DB** (`get_response(correlation_id)`). When it gets a response, it sends a `completed` SSE event and closes.  
  - **Poll fallback**: if the frontend’s EventSource errors (e.g. proxy timeout), it calls `GET /chat/response/:id`, which uses the same Redis GET then DB lookup.

So the frontend only gets the answer if the **API** can read the response from **Redis** (or DB). If the API never sees the key, you get "no frontend" even when the worker has logs.

## What to check

### 1. Same Redis and key for API and worker

- **REDIS_URL** must be identical for both API and worker (same host, port, DB).  
  In `deploy_mobius_chat_staging.sh`, both use the same `REDIS_URL`; confirm no override in Cloud Run (env vars, secrets) that would make API and worker point at different Redis instances.
- **REDIS_RESPONSE_KEY_PREFIX** must match (default `mobius:chat:response:`).  
  Worker SETs and API GETs the same key only if both use the same prefix.

If the worker writes to one Redis (or key prefix) and the API reads from another, the API will never see the response.

### 2. API can read Redis

- The API must be able to **connect** to Redis (same VPC connector / network as worker so it can reach the Redis host).
- If the API could not connect at all, `POST /chat` would fail when publishing the request (LPUSH). So "request sent" implies the API **can** write to Redis.  
  The same connection is used for GET; the main thing to verify is that **no different Redis URL or prefix** is used for the API service.

### 3. Worker actually publishes the response

- In worker logs, look for: **"Response published for &lt;correlation_id&gt;"** (from `worker/run.py` after `publish_response`).  
  If this line appears, the worker has written the response to Redis (SET).  
  If the frontend still doesn’t get it, the API is not seeing that key (different Redis/prefix or API-side GET failure).
- If this line **never** appears, the worker may be crashing or erroring **after** processing but **before** `publish_response`. In that case fix worker stability or error handling so it always publishes before exiting.

### 4. Progress (thinking lines) vs final answer

- **Progress** (thinking lines) in staging comes from **DB** (`chat_progress_events`). The API stream polls that table when `use_db_poll` is true.  
  So for progress to show: (1) run the migration that creates `chat_progress_events`, (2) worker must write progress events to that table.
- **Final answer** comes from **Redis first**, then DB. So even if progress is broken (e.g. migration not run), the frontend can still get the final answer if the API sees the response key in Redis (or in DB after worker persists).

### 5. Frontend connection

- If the **SSE** connection is closed by a proxy/load balancer (e.g. 60s timeout) before the worker finishes, the frontend’s `es.onerror` runs and it **falls back to polling** `GET /chat/response/:id` every 400 ms.  
  So "frontend loses connection" alone only causes a brief switch to polling; the user should still get the answer **unless** the API never returns a completed response (i.e. API never sees Redis/DB response).  
  So if the UI never updates, the root cause is almost always that the **API never sees the response** (worker→Redis or API→Redis/DB), not only the SSE drop.

## Summary

- **Worker has logs but no frontend** → worker may be publishing to Redis, but the **API** is not seeing that response (wrong Redis/prefix, or API can’t read), or the worker never reaches `publish_response`.  
- Confirm **same REDIS_URL and REDIS_RESPONSE_KEY_PREFIX** for API and worker, and in worker logs that **"Response published for &lt;cid&gt;"** appears.  
- Use API stream logs: **"[stream] completed &lt;cid&gt; from Redis"** vs **"from DB"** and **"[stream] still waiting for response"** to see whether the API ever gets the response and from where.
