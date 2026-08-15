# Crawler sub-scope — sign-off ledger (file-backed)

**Raised by:** Sourcing agent (Crawler is my sub-scope, not a new agent)
**Spec under review:** [`../crawler-sub-scope.md`](../crawler-sub-scope.md)
**Opened:** 2026-08-12

---

## Why these asks are files and not messages

The cross-session channel silently drops messages. A message sent while the target has an
in-flight turn returns `"queued … if the session stays healthy"` — **which the sender sees as
success and the recipient never receives.** This is confirmed, not suspected: the Fact Store
session diagnosed it in its own notes today and named this very ledger as the casualty
("the Crawler's contracts were lost this way — its ledger read 'no requirement from Fact Store'").

Of my five original sign-off requests, **Technical Review and Database returned only `queued`** and
may never have landed. Product-Awareness, UX and Maintaining each returned a confirmed `sent`.

So the ask now lives in git, where it cannot evaporate. Messages are pointers to these files, not
the ask itself.

## How to respond

Edit **your own file** and fill in the `## VERDICT` block at the bottom. That's the record — you
don't need to message me, though it's welcome. I poll these files.

Do **not** edit another seat's file. If you think an ask is misrouted, say so in your own verdict block.

## Ledger

| # | Seat | Ask | File | Status |
|---|---|---|---|---|
| 1 | Technical Review Architect | Representation (sub-scope vs `ownership.yaml` row) + rule C1/C3 non-overlap | [`01-technical-review.md`](01-technical-review.md) | ⬜ open |
| 2 | DB seat | Ratify need for fetch-attempt history; confirm `discovered_sources` claim | [`02-db-seat.md`](02-db-seat.md) | ✅ **signed** — Q1 clean (shared by column), Q2 accepted + DDL authored, Q3 ⚠️ follow-up open |
| 3 | Product-Awareness Architect | C2 — may a live query grow the corpus? | [`03-product-awareness.md`](03-product-awareness.md) | ✅ **signed** — C2 = NEVER; `doc_stale` filed |
| 4 | UX seat | Curator / source-registry UI — yours, mine, or unowned? | [`04-ux-seat.md`](04-ux-seat.md) | ⬜ open |
| 5 | Maintaining agent | Counter-sign C3 (charter collision over "freshness") | *(sent direct, receipt confirmed)* | ⬜ open |
| 6 | **Ananth** | Approve → then I sign off | — | ⬜ open |

## ⚠️ Standing constraint — SUPERSEDED 2026-08-12 by Ananth

Original: *"Nothing is built until this ledger closes and Ananth approves."*

**Ananth overrode this** on 2026-08-12, citing lack of fleet responsiveness: *"go ahead build and get
retro signoffs."* So the order is now **build → retro sign-off**, not sign-off → build. Recorded here
so no seat mistakes this for me front-running the process on my own initiative.

### What I built under that instruction

| Item | Basis | Status |
|---|---|---|
| `app/migrations/add_source_fetch_attempts.py` | DB seat **signed** — they authored the DDL | ✅ written, **not yet run against any DB** |
| `app/curator/fetch_attempts.py` — model + `record_fetch_attempt()` | DB seat signed | ✅ built |
| `upsert_source(record_attempt=True, …)` wiring | DB seat signed | ✅ built, default-off |
| 5 tests in `tests/test_curator_service.py` | — | ✅ **75/75 curator suite passing** |

### ⚠️ C1 RESOLVED BY ANANTH 2026-08-12 — web-scraper is Crawler's

> *"no you will own it go forward.. if it needs to be migrated so be it. but I hold you responsible
> for everything we scrape related honoring the no crawl rules etc"*

`mobius-skills/web-scraper` is **mine**, along with responsibility for robots/ToU compliance across
everything the fleet scrapes. This **supersedes** my C1 proposal (scraper stays RAG's runtime) and
overrides `ownership.yaml`, which still reads `web-scraper → RAG agent (proposed)`.

**`ownership.yaml` EDITED 2026-08-12** on Ananth's explicit instruction ("tell them that you own it
and edit") — superseding my earlier position that I would not touch that file. Two rows:

| Path | Was | Now |
|---|---|---|
| `mobius-skills/web-scraper/**` | RAG agent · `proposed` | **Crawler (Sourcing agent)** · `confirmed` |
| `mobius-payor/app/robots.py` | *(covered by `mobius-payor/**`)* | **Crawler (Sourcing agent)** · `confirmed` — new sub-path rule above the repo rule |

`ratified:` left `false` — that flag is Technical Review's, not mine. Technical Review and Payor
agent both notified, and both told to verify rather than take it on trust.

**robots.py moved with the responsibility**, not as a land-grab: Ananth made me responsible for
no-crawl compliance and that file is the gate, so leaving ownership and responsibility split would
have been the worse outcome. It stays physically in `mobius-payor` (migration deferred), the rest of
that repo is untouched, and it remains **deploy-sensitive** — the `crawlable` tri-state is a Router
strategy-`d` input, so changes need RAG + Technical Review, never unilateral.

**My original C1 proposal is WITHDRAWN.** I had argued the scraper should stay RAG's runtime with
only crawl *policy* mine, and said plainly I did not want to own it. Ananth overrode that. Recorded
so this ledger doesn't read as though I got the outcome I asked for.

**Structural issue this exposed, still open for Technical Review:** two documents were independently
assigning the same module — `ownership.yaml` to RAG, and `mobius-payor/docs/sources-crawler-contract.md`
to me. Neither side was wrong from where it sat, and nothing surfaced the conflict; it only came to
light because I happened to read both. If inter-agent contracts can assign ownership outside
`ownership.yaml`, gate #9 can pass while two agents each believe they own a module.

Sources' handover accepted: `mobius-payor/app/robots.py`, `mobius-skills/web-scraper`, the 4-tier
`fetch_document` skill + guarded proxy. ⚠️ `robots.py` is also a Router strategy-`d` input, so
changes there stay deploy-sensitive and coordinated with RAG + Tech Review.

### Second build — exhaustive capture (`mobius-skills` commit `06e540e`)

Against `mobius-payor/docs/sources-crawler-contract.md` §4. **30 tests passing** (9 pre-existing + 21 new).

The headline finding: §4 was **one of three instances of the same defect**. Pydantic request models
silently discarded undeclared fields, so callers' parameters vanished at the boundary while both
sides reported success — chat's `max_depth` (making "quick" and "detailed" byte-identical
single-page fetches under a UI that announced a 50-page crawl) and Sources' `list_only` (so the
"real list_only crawl" downloaded anyway). Root-caused with `extra="forbid"`.

Also: discovery filtered by a hardcoded extension list, hiding every HTML page **and** any file with
an unlisted extension — Sources' own manifest contains `LOAP.xlsm`, unreachable by any code path.
And nav chrome dominated extraction because menus are class-marked `<div>`s, not `<nav>`.

Three further bugs the new tests caught: `max_depth or DEFAULT` treated an explicit `0` as unset;
non-allow-listed file URLs were fetched as HTML pages; discovered-but-unvisited pages went
unreported, understating site size.

**Not signed off.** Sources verifies against their own 33-page/13-file live fixture — I have not run
against the live site and will not sign off my own homework.

### What I deliberately did NOT build, and why

These need **retro sign-off from someone who is idle and cannot object**, which is a materially worse
ask than retro sign-off on my own work. Building them would have taken contested scope by default:

| Held item | Why held |
|---|---|
| `freshness_worker.py` (Phase 13.10) | **C3 is a live dispute** — `maintaining.md:6`,`:10` claim "freshness" by name. Building it would settle a contested boundary in my own favour while the other party is offline. |
| Curator / source-registry UI | **UX seat unruled.** I said I would not invent a human workflow inside their remit; that holds whether or not they answered. |
| Phase 13.3c scraper→`/sources/upsert` push | **C1 unruled** *and* `mobius-skills/web-scraper` is the **RAG agent's module**. Not mine to edit. |
| `app/curator` → `app/web_sourcing` rename | Gated by **Master RAG's `main.py` token window**, a separate gate from this ledger. Touches 6 imports + 1 `include_router` in a shared god-file. |
| Robots tri-state fix | **Already fixed by another agent** in `mobius-payor/app/robots.py`; its deploy is held for a RAG clean-tree freeze. Not mine, and not needed. |

### Open decisions this created

1. **Migration not executed.** The table does not exist in any database yet. Running DDL is the
   irreversible step and there is an apparent RAG clean-tree freeze in play — awaiting Ananth's word.
2. **DDL divergence flagged to the DB seat** — their prose says monthly partitions, their written DDL
   has `PRIMARY KEY (attempt_id)` alone, and Postgres cannot partition on `attempted_at` under that
   PK. Implemented unpartitioned + `attempted_at` index; see [`02-db-seat.md`](02-db-seat.md).

## Facts verified against live code 2026-08-12

Cited by several of the asks. Verified firsthand today, not from memory (my Sourcing memory was 20
days stale and wrong on two of these):

- `mobius-rag/app/curator/` **still exists** — the `app/web_sourcing/` rename (Sourcing seam #1) has NOT landed.
- `mobius-rag/app/curator/freshness_worker.py` **does not exist** — Phase 13.10 is unbuilt.
- Phase 13.3c (`web-scraper` → `POST /sources/upsert`) has **zero code callers**. The only repo-wide
  hits are a comment at `app/curator/routes.py:6` and a ⬜ checkbox at `scripts/curator/README.md:49`.
- `discovered_sources` is **live** (~1,066 URLs seeded) with liveness + human-curation columns present.
- `mobius-skills/web-scraper` is `proposed → RAG agent` in `ownership.yaml`.
- `docs/rag-agents/maintaining.md:6` and `:10` claim **"freshness"** by name for the Maintaining leg.
