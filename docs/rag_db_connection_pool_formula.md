# RAG database connection pool: formula from concurrency

Size Postgres connection pools from **concurrent users** and **concurrent docs**, then secure the right `max_connections` on the instance.

---

## 1. Inputs (what you plan for)

| Input | Meaning | You choose |
|-------|--------|------------|
| **N_internal** | Concurrent internal users (RAG UI: Document Input, Status, Read, etc.) | e.g. 3, 5, 10 |
| **N_chat** | Concurrent chat users (end users hitting mobius-chat on this Postgres instance) | e.g. 20, 50, 100 |
| **D_chunk** | Max concurrent docs we plan to chunk at once (across all chunking workers) | e.g. 2, 5, 10 |
| **D_embed** | Max concurrent docs (or embedding tasks) we plan to embed at once | e.g. 2, 4, 8 |

---

## 2. Conversion factors (users/tasks → connections)

- **UI:** Each concurrent internal user can have several in-flight requests (list + detail + polling + import). Use a factor **R_ui** = requests per concurrent user (e.g. 2).
- **Chat:** Each concurrent chat user typically has 1 active request at a time. Use **R_chat** = 1 (or 1.2 for spikes).
- **Workers:** Each doc in chunking = 1 connection for the duration of the job. Each doc/task in embedding = 1 connection. No extra factor; connection count = concurrency.

So:

- **UI_slots** = N_internal × R_ui  
- **Chat_slots** = N_chat × R_chat  
- **Chunking_slots** = D_chunk  
- **Embedding_slots** = D_embed  

---

## 3. Master formula (total connections)

```
total_connections =
  (N_internal × R_ui)           // UI: internal users → connections
  + (D_chunk)                    // RAG workers: concurrent docs chunking
  + (D_embed)                    // RAG workers: concurrent docs embedding
  + (N_chat × R_chat)            // Chat: concurrent chat users → connections
  + HEADROOM                     // migrations, admin, monitoring (e.g. 5)
```

**Constraint:** `total_connections ≤ max_connections` (Postgres instance).

---

## 4. Recommended factors (tunable)

| Factor | Suggested | Notes |
|--------|------------|--------|
| **R_ui** | 2 | Each internal user: ~1–2 active requests (list/detail + polling or import). Use 2 for safety; 3 if heavy multi-tab. |
| **R_chat** | 1 | One request per chat user at a time. Use 1.2 if you want a small buffer. |
| **HEADROOM** | 5 | Admin, migrations, one-off scripts. |

---

## 5. How this maps to pools (per process)

Connections are consumed by **processes**; each process has one pool (pool_size + max_overflow).

- **RAG API (one or more instances)**  
  Serves all UI traffic. So the **RAG API pool total** (across all API instances) must be ≥ UI_slots.  
  - Single instance: `pool_size + max_overflow ≥ N_internal × R_ui`.  
  - Multiple instances: sum over instances ≥ N_internal × R_ui (and balance load so no instance gets more than its pool).

- **Chunking worker(s)**  
  Each process holds 1 connection per doc it's chunking. So **total chunking worker connections** = number of chunking worker processes × connections per process. To support D_chunk concurrent docs, you need at least D_chunk connections (and at least D_chunk worker "slots", e.g. processes or concurrency).  
  - So: sum over chunking workers of (pool_size + max_overflow) ≥ D_chunk.  
  - Typical: one process per doc or a small pool per process (e.g. pool_size=1, max_overflow=1 per process), and **number of processes (or concurrency) ≥ D_chunk**.

- **Embedding worker(s)**  
  Each process holds one connection per concurrent embedding task. So **total embedding connections** must be ≥ D_embed.  
  - So: sum over embedding workers of (pool_size + max_overflow) ≥ D_embed.  
  - Typical: pool_size = concurrency per process, max_overflow = 1–2; **total (concurrency × N_embedding_workers) ≥ D_embed**.

- **Chat (if same instance)**  
  Chat app's pool total must be ≥ N_chat × R_chat.

So you **first** compute:

- UI_slots = N_internal × R_ui  
- Chunking_slots = D_chunk  
- Embedding_slots = D_embed  
- Chat_slots = N_chat × R_chat  

Then **set**:

- `max_connections` ≥ UI_slots + Chunking_slots + Embedding_slots + Chat_slots + HEADROOM  
- Each app's pool (and number of workers / concurrency) so that the **sum of their peak usage** matches those slots.

---

## 6. Worked example

**Planned concurrency:**

- 5 concurrent internal users (RAG UI)  
- 20 concurrent chat users  
- Up to 3 docs chunking at once  
- Up to 4 docs embedding at once  
- R_ui = 2, R_chat = 1, HEADROOM = 5  

**Slots:**

- UI_slots     = 5 × 2 = **10**  
- Chunking     = **3**  
- Embedding    = **4**  
- Chat_slots   = 20 × 1 = **20**  
- HEADROOM     = **5**  

**Total:** 10 + 3 + 4 + 20 + 5 = **42** → set Postgres `max_connections` ≥ 42 (e.g. 50).

**Pool allocation:**

- RAG API: pool_size + max_overflow ≥ 10 (e.g. 8 + 4).  
- Chunking: 3 connections total (e.g. 3 workers with pool 1+1, or 1 worker with pool 3+1).  
- Embedding: 4 connections total (e.g. 2 workers with concurrency 2, pool 2+2 each).  
- Chat: pool_size + max_overflow ≥ 20.

---

## 7. Formula summary (copy-paste)

```
UI_slots       = N_concurrent_internal_users × R_ui
Chunking_slots = N_concurrent_docs_chunking
Embedding_slots= N_concurrent_docs_embedding
Chat_slots     = N_concurrent_chat_users × R_chat

total_connections = UI_slots + Chunking_slots + Embedding_slots + Chat_slots + HEADROOM

max_connections ≥ total_connections
```

Then size each app's pool so that, at peak, they use at most UI_slots, Chunking_slots, Embedding_slots, and Chat_slots respectively.

---

## 8. Dynamic scaling in production

Chunkers/embedders can scale up or down based on queue depth; chat users vary over time. Dynamic management is the right production approach, as long as you **cap usage by a fixed connection budget**.

### Principle: reserve a budget, scale within it

1. **Fix the ceiling:** Set Postgres `max_connections` using the formula with the **maximum** concurrency you're willing to support (max N_internal, max N_chat, max D_chunk, max D_embed). That's your total connection budget.
2. **Reserve slots per category:** UI_slots, Chunking_slots, Embedding_slots, Chat_slots + HEADROOM. Each category can use up to its slots; in practice they won't all peak at once.
3. **Scale workers based on queue:** Run 0 to D_chunk chunking workers (or 0 to D_embed embedding tasks). When the queue grows, add workers/tasks; when it drains, scale down. Each worker's **pool size is fixed**; what changes is **how many worker processes (or concurrent tasks) are running**. Total worker connections at any time ≤ Chunking_slots + Embedding_slots.
4. **Chat varies naturally:** N_chat goes up and down. Size the chat app's pool(s) to **Chat_slots** (peak). Actual in-use connections will vary with load; you don't resize the pool at runtime—you just don't exceed the reserved slots.

So: **reserve the right amount once (formula), then dynamically scale how many consumers use that reservation (workers, chat instances), without exceeding the budget.**

### Is this the best way in production?

| Approach | Pros | Cons |
|----------|------|------|
| **Fixed budget + scale worker count / chat instances** (above) | Simple, predictable, no connection churn. Fits Cloud Run / K8s scale-to-zero or scale-by-queue. | Must choose a peak; if you exceed it, you need to raise the budget (or add a pooler). |
| **Dynamic pool resize per process** | Could shrink pool when idle. | SQLAlchemy supports it but adds complexity and connection churn; rarely worth it. |
| **Connection pooler (PgBouncer, Supabase pooler, etc.)** | Many app connections multiplex to fewer real DB connections. Lets you oversubscribe (e.g. 100 app conns → 20 real). | Extra component; transaction or session mode and timeouts must be tuned. Good when you have many small services or serverless. |
| **Separate DB for workers** | Isolate worker traffic from UI/chat. | More cost and ops; two databases to maintain. |

**Recommendation:** Use **fixed budget + dynamic worker/instance scaling** as the default. Add a **pooler** if you have many short-lived processes (e.g. serverless) or want to oversubscribe safely. Use **separate DB** only if you need strict isolation or different scaling profiles.

### Practical setup (dynamic workers, variable chat)

- **RAG API:** Fixed pool size (e.g. 8+4) per instance; scale API instances for availability, not usually for connection count (internal users are limited).
- **Chunking workers:** Scale 0..D_chunk based on chunking queue depth (e.g. Cloud Run jobs or K8s HPA on queue length). Each worker has a small fixed pool (1+1). Total chunking connections ≤ D_chunk.
- **Embedding workers:** Scale 0..D_embed tasks (or scale worker replicas with fixed concurrency per replica). Total embedding connections ≤ D_embed.
- **Chat:** Horizontal scale of chat app instances; each instance has a fixed pool. Total pool across instances ≥ peak N_chat × R_chat. Actual connections in use track concurrent chat users.

Ensure: `max_connections` ≥ UI_slots + D_chunk + D_embed + Chat_slots + HEADROOM, with D_chunk and D_embed as the **max** you'll ever run. Then scale up/down within those caps.
