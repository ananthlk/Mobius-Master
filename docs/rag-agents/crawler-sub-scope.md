# Crawler — sub-scope of the Sourcing agent

**Status:** PROPOSED 2026-08-12 · awaiting architect sign-off, then Ananth's approval, then my sign-off.
**Author / owner:** Sourcing agent (Crawler is *my* sub-scope — **not** a new agent).
**Announced to:** UX seat · DB seat · Technical Review Architect · Product-Awareness Architect.

Parent charter: [`sourcing.md`](sourcing.md) · map: [`module-map.md`](module-map.md) · ownership: [`../../ownership.yaml`](../../ownership.yaml)

---

## a) Announcement — what this role is

Crawler is the **URL-discovery, fetch, and upstream-freshness** layer of the Sourcing leg. It is a
*naming and boundary clarification of work already assigned to Sourcing*, promoted to its own spec
because three unbuilt items (13.3c push, 13.10 freshness, 13.7 notifier) each cross another agent's
line, and because it needs persistence + logging of its own.

**Explicitly: no new agent, no new session, no new `ownership.yaml` rows.** Per `sourcing.md`, all four
RAG legs are sub-trees of one undecomposed `mobius-rag`, so `mobius-rag/** → Master RAG` stays a
single row. Crawler is represented in `module-map.md` at subsystem level only.

**One-line mission:** know every URL that matters, know its current fetch state, and notice when the
upstream source changes — then hand the resulting raw doc to the existing Sourcing→Curation seam.

---

## b) Boundaries

### Mine

Ingest-time acquisition, ending at the existing seam. My write ends where `sourcing.md` already says
it ends: `documents` + `document_pages` + `chunking_jobs(status='pending')`.

- URL discovery (sitemap scan, BFS crawl, manual submit) and the registry of what was discovered
- Fetch execution + fetch policy: rate, retry, robots, auth-blocked handling
- Liveness / content fingerprinting (`content_hash`, `last_fetch_status`, drift detection)
- The decision *to ingest* a discovered URL, and the enqueue of it

### Not mine

| Not mine | Owner | Line |
|---|---|---|
| chunk / embed / publish | Curation | unchanged — my write ends at `pending` |
| answering path, retrieval | Retriever | unchanged |
| corpus-internal integrity sweeps | Maintaining | see conflict **C3** |
| the scraper runtime itself | RAG agent | see conflict **C1** |

### Boundary conflicts I need settled — these are the sign-off asks

**C1 — `mobius-skills/web-scraper` (RAG agent, `proposed` in ownership.yaml).**
Verified today: web-scraper has **no code path that calls `/sources/upsert`** — the only hits repo-wide
are a comment in `app/curator/routes.py:6` and the ⬜ line in `scripts/curator/README.md:49`. So
Phase 13.3c is genuinely unbuilt, not half-built.
*My proposal:* the scraper stays **RAG-agent-owned as a runtime**; **crawl policy** (what/when/how
fast/robots) is mine; 13.3c is a **joint seam** with a typed payload, not a unilateral change by
either side. I do not want to own the scraper.

**C2 — RULED 2026-08-12 by PA Architect: NEVER.** Filler-d reads the registry and marks liveness
only; it may **never** enqueue ingestion. Rationale on the record: corpus membership must stay a
stated, reviewable set, or "Mobius answers from its curated corpus" stops being a product-truth claim
and becomes a side effect of user behavior. ⚠️ Enforcement note: per the DB seat's column contract,
`ingested`/`ingested_doc_id` are **RAG's** columns, not mine — so this guarantee has to be enforced on
the **enqueue path**, not by column ownership as I originally wrote it. Original framing below.

**C2 (as raised) — Filler-d Web (already mine) vs Crawler (also mine) — one agent, two lanes.**
Same fetch capability, two different lanes, and I hold both — so this is a self-discipline line I want
witnessed rather than a dispute. *Proposal:* Filler-d is **query-time** and may **read** the registry
and **upsert liveness only**; it must **never** enqueue ingestion. Crawler is **ingest-time** and is the
only writer that sets `ingested`/`ingested_doc_id`. Without this stated, a live query silently grows
the corpus, which is a Product-Awareness truth problem as much as a technical one.

**C3 — upstream drift vs corpus drift (Maintaining agent).** The real overlap — and a **direct
collision**, not an unclaimed line. Verified: `maintaining.md:6` ("nightly sweeps, **freshness**,
coherence") and `:10` ("Content-less gate · **freshness** · corpus coherence") claim the word by name.
My proposal cuts into their charter, so it is theirs to reject.
*Proposal:* **upstream changed** (source URL's bytes/hash/status moved) = **Crawler** — the detection
needs the fetch layer (robots, rate limits, ETag/Last-Modified, per-URL auth failures), which is crawler
machinery unrelated to corpus integrity. **Corpus internal** (stale chunks, coherence, junk, orphans) =
**Maintaining**. Handoff = one directional signal: Crawler detects + re-imports, Maintaining owns
everything downstream.
*Alternatives offered to them:* (b) Maintaining owns the freshness worker outright and I expose fetch
primitives; (c) I build it, they own trigger policy (what's canonical, what cadence). Nothing is built
yet — `freshness_worker.py` does not exist — so no sunk code is biasing this.
**Sent direct 2026-08-12** (Ananth's call), not routed through the architects.

---

## c) Modules I will own (subsystem level, `module-map.md`)

| Path | State today | Note |
|---|---|---|
| `mobius-rag/app/curator/**` | **exists** — `classifier.py`, `service.py`, `routes.py` | renames to `app/web_sourcing/` under Sourcing seam #1 (**not yet done** — verified `app/curator` still present) |
| `mobius-rag/scripts/curator/**` | **exists** — scan, backfill, smoke | already mine per `sourcing.md` |
| `/sources/*` routes | **live** | upsert · search · curate · ingest |
| `discovered_sources` table | **live** — ~1,066 URLs seeded | claim, do not recreate |
| `app/curator/freshness_worker.py` | **not built** (verified absent) | Phase 13.10 |
| 13.3c scraper push · 13.7 notifier | **not built** | C1 seam · needs a notification owner |

---

## d) Persistence + logging I am asking for

Per the process, I create these **only after** sign-off + Ananth's approval. DB seat's ratification is
the gate (GATE §3). Nothing below is created yet.

> **DB seat SIGNED 2026-08-12.** Two corrections landed — see inline.

1. **`discovered_sources` — already exists and is live.** I am **claiming**, not creating. No DDL.
   ⚠️ **CORRECTED by DB seat:** ownership is **not** solely mine — it is **shared at column level**
   under a single-writer-per-column contract: **Crawler** writes `fetch_status`/`crawlable`/fetch
   columns · **RAG** writes discovery columns (`seed_url`, `depth_from_seed`, `discovered_via`,
   `content_hash`, `ingested_doc_id`) · **Sources** writes `curated_*`. Claim approved on that basis.
   My §b line "Crawler is the only writer that sets `ingested`/`ingested_doc_id`" is **superseded** —
   that column is RAG's. C2's guarantee still holds, but it must be enforced on the *enqueue* path,
   not by column ownership.
2. **NEW: a crawl-attempt history table — NEED ACCEPTED, DDL authored by DB seat.**
   Table is **`source_fetch_attempts`** — append-only, FK `discovered_source_id → discovered_sources(id)`
   ON DELETE CASCADE, monthly partitions with 90d drop, indexed on source + `robots_decision`.
   Full DDL in [`crawler-signoff/02-db-seat.md`](crawler-signoff/02-db-seat.md). Awaiting Ananth's go
   before it is created. Original rationale below stands.

   Today the registry keeps only *latest* state —
   `last_fetch_status`, `last_fetch_at`, `fetch_attempt_count`. There is **no per-attempt history**, so
   robots/rate-limit behavior and drift causation cannot be audited after the fact. This is
   load-bearing for a known live bug: **403 being read as `disallow_all` poisons `crawlable=False`**
   (tri-state fix). Without attempt history I cannot prove a fix or detect regressions.
   Proposed grain: one row per fetch attempt — `run_id, url, attempted_at, status, bytes, latency_ms,
   robots_decision, hash_before/after`. Retention bounded (proposal: 90d). **DB seat: exact DDL,
   naming, and retention are yours to rule on — I am asserting the need, not the schema.**
3. **Structured `[crawler]` run logging** — one run summary per crawl/freshness pass. No new infra.

**PHI note:** crawled sources are public payer/state policy pages, so the ingest path should be
PHI-clean by construction — but per standing policy I will not assume it. Fail-closed via the existing
classifier; I will not build my own detector.

---

## Sign-off ledger

**The asks are file-backed** — see [`crawler-signoff/`](crawler-signoff/README.md). The cross-session
message channel silently drops messages sent while the target has an in-flight turn (sender sees
`queued` and reads it as success; recipient never receives). Two of my four original architect asks
returned only `queued`. Seats respond by filling the `## VERDICT` block in their own file.

| Seat | Asked for | File | Status |
|---|---|---|---|
| DB seat | Ratify §d.2 need + rule the DDL; confirm `discovered_sources` claim | [02](crawler-signoff/02-db-seat.md) | ✅ **SIGNED** — see §d update |
| Technical Review Architect | Confirm "sub-scope, no new `ownership.yaml` row" is the right representation; rule C1 + C3 as non-overlapping | [01](crawler-signoff/01-technical-review.md) | ⬜ pending |
| Product-Awareness Architect | Rule C2 (does a live query grow the corpus?) — product-truth call | [03](crawler-signoff/03-product-awareness.md) | ✅ **SIGNED — C2 = NEVER** |
| UX seat | Surface question: is there a curator/registry UI, and is it yours or mine? | [04](crawler-signoff/04-ux-seat.md) | ⬜ pending |
| Maintaining agent | Counter-sign C3 — **charter collision, they may reject** | ⬜ sent direct 2026-08-12 (session idle since Jul 23) |
| **Ananth** | **Approve — then I sign off** | ⬜ pending |

No code moves, no DDL, no renames until this ledger closes and Ananth opens the window.
