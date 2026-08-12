# Ask 3 — Product-Awareness Architect

**From:** Sourcing agent (Crawler sub-scope) · **Opened:** 2026-08-12 · **Spec:** [`../crawler-sub-scope.md`](../crawler-sub-scope.md) C2

> Re-issued as a file for durability. See [`README.md`](README.md).

## Context

Ananth ruled **"Crawler" a sub-scope of Sourcing — not a new agent**: URL discovery, fetch, upstream
freshness. One conflict is a product-truth call, not a technical one, so it's yours.

---

## Q1 — C2: may a live user query silently grow the corpus?

**I hold both lanes, which is exactly why I want this witnessed rather than decided by me.**

- **Filler-d Web** = **query-time** retrieval — answers the question in front of the user
- **Crawler** = **ingest-time** discovery — grows the indexed corpus

Both fetch from the open web. Same capability, two different purposes, one owner (me).

**My proposal:** Filler-d may **read** the source registry and **upsert liveness only**, and must
**never** enqueue ingestion. Crawler is the only writer that sets `ingested` / `ingested_doc_id`.

**Why it's your ruling and not mine:** if a query can quietly ingest, then "what is in the corpus"
stops being a stated, reviewable set and becomes a function of who asked what, when. That is a
product-truth claim going soft — "Mobius indexes these sources" would no longer be a thing anyone
can point at. It is not primarily a plumbing choice.

**A ruling of "yes, queries may ingest, and we say so plainly" is entirely legitimate.** I am not
asking you to pick my option. I am asking that it be *stated* rather than assumed, because the
default if nobody rules is that it happens silently.

## Q2 — A promise to keep an eye on

Phase 13.10 (freshness worker) would let us claim *"we detect upstream policy changes same-day."*

**That capability is NOT built** — verified today, `app/curator/freshness_worker.py` does not exist.

**Please confirm nothing in the docs/promise surface claims it today.** If something does, that's a
`doc_stale` for the sourcing/corpus area. I'm flagging rather than fixing because the promise surface
is yours.

Related: ownership of freshness is itself contested — Maintaining's charter claims the word by name
(`maintaining.md:6`, `:10`). Whoever ends up owning it, the promise shouldn't run ahead of the code.

---

## VERDICT

**Q1 C2 — query-time ingestion: NEVER. Filler-d reads registry + updates liveness only.**

Corpus membership must be a stated, reviewable set. If queries silently ingest, then "Mobius indexes these sources" stops being a product-truth claim and becomes a side effect of user behavior. This violates the core promise: answers grounded in a *curated* corpus that we can point to.

**Ruling:** Filler-d may read `discovered_sources` and mark liveness (`last_fetch_at`, `liveness` status), but must never enqueue ingestion or write to `ingested` / `ingested_doc_id`. Only Crawler, under deliberate control, may ingest into the corpus.

**Why this protects product-truth:** We can then make and keep the claim: "Mobius answers from its curated corpus, which contains [specific sources]." Queries cannot expand that set invisibly.

---

**Q2 freshness promise: CLAIM FOUND → doc_stale filed**

**Location:** `docs/payor-readiness-registry-spec.md`, the table row on "URL discovery + liveness + drift" states:
> "A daily worker already re-fetches `curation_status='canonical'` URLs and detects content change."

**Fact:** `app/curator/freshness_worker.py` does not exist (verified 2026-08-12). Phase 13.10 is unbuilt.

**Action:** This is a `doc_stale` for sourcing/corpus area. The promise surface claims a capability that isn't live. The statement should be rewritten to reflect reality — either mark as "planned" or remove the claim entirely until Phase 13.10 ships.

Related: Maintaining agent also has charter claims on "freshness" (per README.md line 57). That's their signoff to counter-sign or accept.

---

- **Signed:** Ananth Lalithakumar, PA Architect
- **Date:** 2026-08-12
- **Authority:** Product-truth governance (corpus curation claims; freshness promise surface)
