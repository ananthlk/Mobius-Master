# POOL — Schematic Spec (Step 2) — v1

**Status:** DRAFT — design doc, no code written. Follows the same process Gate/Reformat/Structure used: spec → cross-agent sign-off → build.
**Owner:** Pool agent, reports to Retriever.
**Companions:** `pool-module-spec.md` (Retriever's original kickoff doc), `retriever-target-structure-spec.md` §1/§2/§4/§7/§10, `retriever-meet-old-plan.md` (§"Four sources", §"Pool build workflow").

---

## 1. Resolved before this spec was written

- **`StructureResult` (shape/contracts.py) carries no `answer_shape`/slots and no scope/auth field** — verified directly in code, not assumed. Neither field exists ANYWHERE in the new pipeline yet, not even in `orchestrator.py`. `answer_shape` stays legacy-request-only, Synthesis/Chat's concern.
- **Scope/auth v1 decision: PUBLIC-only, through a `SourceAdapter` seam.** Not an Ananth-confirmed fact — my inference from `retriever-meet-old-plan.md`'s "Four sources" table (only PUBLIC marked BUILD NOW; ORG/INSTANT-RAG/CACHE are `[⋯exceed]`, owned by the Org/Instant-RAG/Cache agents respectively, not Pool). Needs explicit Chat/UX sign-off before it locks (§8).
- **Gate (i) — RESOLVED 2026-07-23: GIN-index `chunk_{d,p,j}_tags`, formally confirmed by DB.** Reasoning: doc-level GIN on `document_tags` is already proven cheap (~50ms), same semantics/pattern applies at chunk level, consistency with the fleet-standard pattern beats adding pool-first complexity. DB owns creating the index (schema governance); migration lands before Pool ships, Pool doesn't block on the migration landing first — build to `chunk_*_tags ? :code` now.
- **FAN_OUT embed concurrency, not batching.** Production model `gemini-embedding-001` caps at 1 input/call (`embedding_provider.py:89`, a real API constraint) — up to 4 rewritten-query embeds run via `asyncio.gather`, never a single batched call. Reformat's `batch_size=250` fix (`shape/reformat.py`) doesn't apply — different model, clustering-only, no corpus interop requirement.
- **Required/boosted/dropped term classification already exists — reuse, don't reinvent.** `partition_terms()` (`corpus_search_agent.py:1343`) → `TermPartition(required, boosted, dropped)`, driven by `selectivity_for_tag(db, code)` (`:1131`, DB-computed, cached 1h, `sel = 1 - n/total_docs` over `document_tags`) against two thresholds: `_SELECTIVITY_REQUIRED = 0.65`, `_SELECTIVITY_BOOST = 0.40` (`:1083-1084`). Literal anchors always REQUIRED (selectivity=1.0). Untagged tokens get heuristic selectivity via `selectivity_for_untagged_token()` (`:1166`) + `load_generic_doc_words()` (`:1222`, auto-derived noise set from rejected lexicon candidates, cached 1h).
- **Doc-level narrowing is already cheap — the BM25-cost fear doesn't apply to it.** `build_candidate_pool()` (`:1762`) cascades L1_JDP → L2_JD → L3_AHCA_D → L4_AHCA → L5_empty via `_doc_ids_with_tag()` (`:1461`) against `document_tags`, which **has a GIN index** (confirmed in-code comment, `?  :code` lookups typically <50ms even for the broadest tag). This produces a narrowed `document_ids` pool (thousands of rows) BEFORE any search runs — legacy never runs BM25 unnarrowed. The only genuinely-unresolved expensive layer is the separate, finer **chunk-level** tag columns (`chunk_{d,p,j}_tags`, no GIN) — that's exactly gate (i), unaffected by this finding.
- **BM25 dropped from strategy 1 by choice, not by cost-necessity.** Given the above, narrowing was never the open question — it's already solved and cheap. The decision to replace BM25 ranking with required/boosted tag-coverage-maximizing selection (§3.1) is a genuine "exceed"-tier design choice, made explicitly with Ananth, and needs its own Eval before/after against legacy strategy (a)'s BM25 numbers — not just against the pre-Pool non-union baseline.
- **Neighbor-expansion mechanism identified — current anchor differs from the plan doc's stale citation.** `retriever-meet-old-plan.md` cites `_fetch_sibling_chunks_batch :2560` / `is_promoted_neighbor :2210` / `_NEIGHBOR_SCORE_FLOOR :2553` in `corpus_search_agent.py` — **these don't exist at those names/locations anymore.** The live mechanism is `_expand_with_neighbors()` (`corpus_search.py:3079`), called from `corpus_search()` (`:3280`) when `neighbor_paragraph_window > 0` (default 2 paragraphs, 1 page). It fetches siblings via `_fetch_sibling_chunks_batch()` (still present, just nested — not a top-level anchor), **dedupes them against seeds by both `id` AND content (`content_sha` or first-200-chars-normalized-body)**, inherits a fractional score from the nearest same-doc seed, and applies caps. Takes/returns generic `list[dict]` — not tied to any one strategy.
- **Neighbor-expand direction — decided: reuse `_expand_with_neighbors()` verbatim for v1, not restructure.** Confirmed target-structure-spec.md:114 tags any *behavior change* to cascade/neighbor-expand as NUMBER-MOVING. Since the function is already generic (`seeds: list[dict]`) and already does its own dedup, the lowest-risk path is calling it unchanged over Pool's deduped union — no restructuring, so no incremental recall risk beyond "does calling it from a new caller work the same." Still needs Eval's before/after (§8) because it's a new integration point even if the function itself is untouched.
- **Real gap found, not yet resolved: `GateResult` cannot feed `partition_terms()` as-is.** `partition_terms(db, profile: QueryProfile)` needs `profile.tag_matches`, `profile.literal_anchors`, `profile.untagged_meaningful_tokens`. `GateResult` has the tag-code equivalent (`d_codes`/`j_codes`/`p_codes`) but **no `literal_anchors` and no `untagged_meaningful_tokens` — Gate never computes either** (verified: zero hits for `literal_anchor`/`untagged` in `shape/gate.py`). This is not "landed elsewhere," it genuinely doesn't exist in the new pipeline. See §4.1.

## 2. Where Pool sits, input/output (unchanged from kickoff, restated for completeness)

```
Query → SHAPE [Gate → Reformat → Structure] (ALL CLOSED) → POOL (THIS MODULE) → ROUTER → FILLERS → ...
```

**Input:** `StructureResult` — `rewritten_queries[]` (1, or up to `MAX_FANOUT_THEMES=4` for FAN_OUT), `resource_posture.breadth`, `posture`. Plus `GateResult` (Pool needs the raw `d_codes`/`j_codes`/`p_codes`, not just what survived into Structure — see §4.1).

**Output:** one assembled pool per rewritten_query — deduped, unioned candidate set with per-candidate provenance, ready for neighbor-expanded synthesis context. Exact shape in §5, open for Retriever's sanity-check against future Router/Fillers needs (per Retriever's ask).

## 3. Pool build workflow — three strategies, union, dedup, neighbors

Runs once per `rewritten_query` (so up to 4× for FAN_OUT, each independently, embeds concurrent per the FAN_OUT resolution above).

### 3.0 `SourceAdapter` interface — generic contract (Ananth's explicit requirement, 2026-07-23)

Ananth confirmed PUBLIC-only-v1-via-seam as the right design, with one hard requirement: **adapters must be genuinely plug-and-play when ORG/INSTANT-RAG/CACHE get built later — no touching Pool's core when each one lands.** That means the seam needs a concrete method-level shape now, not just a conceptual placeholder:

```python
class SourceAdapter(ABC):
    scope: ScopeContext   # baked in at construction — public=global, org=tenant, instant_rag=user+PHI.
                           # "federate, never leak" (retriever-meet-old-plan.md P0) — scope rides the
                           # adapter, Pool core never sees or branches on it directly.

    async def tag_select(self, required_codes, boosted_codes, width) -> list[PoolCandidate]: ...
    async def vector_search(self, query_embedding, width) -> list[PoolCandidate]: ...
    async def inherited(self, payor_codes) -> list[PoolCandidate]: ...  # optional capability, see below
    async def neighbors(self, candidates: list[PoolCandidate]) -> list[PoolCandidate]: ...
```

Pool's orchestration core (§3.5 union/dedup, §3.6 neighbor-assembly) calls these four methods generically against whichever adapter(s) are in scope for the request — it never branches on "is this public." §3.1–3.3 below ARE `PublicSourceAdapter`'s implementation of `tag_select`/`vector_search`/`inherited`, not logic hardcoded into Pool's core. `neighbors()` wraps `_expand_with_neighbors()` (a public-specific DB call) behind the adapter-agnostic candidates-in/candidates-out signature, so a future adapter can implement its own neighbor logic — or none — behind the same call.

**This pseudocode is the original illustrative sketch, not the live signature** — real params accumulated since (`bm25_score`/`query_embedding`/`required_phrases`/`boosted_phrases`/`j_codes` for cross-payer exclusion, all logged in `pool-simulation-tracker.md` as each landed). Check the tracker or the actual `contracts.py` ABC for the current real method signatures before assuming this snippet is accurate.

**`inherited()` is deliberately optional, not uniform across adapters** — AHCA-authority inheritance is a PUBLIC-corpus-specific concept; ORG/INSTANT-RAG/CACHE may have no equivalent and can no-op (return `[]`) without violating the interface.

**CACHE likely isn't a `SourceAdapter` implementer at all.** Per `retriever-meet-old-plan.md`'s "Four sources" table, CACHE "may short-circuit, not union" — a cache hit plausibly bypasses Pool's build entirely rather than contributing candidates through the same four-method shape as PUBLIC/ORG/INSTANT-RAG. Flagging now so whoever builds the Cache adapter later doesn't assume it must conform to `SourceAdapter` if a short-circuit-before-Pool design turns out to fit better — Pool's core doesn't need to decide this today, just not foreclose it.

### 3.1 Strategy 1 — Required/boosted tag-coverage selection (BM25 replaced)

1. Partition `GateResult`'s `d_codes + j_codes + p_codes` into REQUIRED/BOOSTED/DROP via `selectivity_for_tag()` reused as-is (§4.1 covers the literal-anchor/untagged-token gap — v1 ships tag-only, see there for the fast-follow decision).
2. Narrow to a document pool via `build_candidate_pool()`'s existing cascade (L1_JDP→L5_empty) — reused as-is, cheap (GIN-indexed `document_tags`). **Timed separately as `doc_narrow_ms`** (TECH's flag, 2026-07-23) — this cascade is its own DB call sequence and needs its own gate-(d) bucket, distinct from step 3's chunk-level query.
3. Within that narrowed document set, select chunks that maximize REQUIRED+BOOSTED tag coverage, capped at a width derived from `resource_posture.breadth` (not hardcoded — §3.4).
4. Step 3's chunk-level tag lookup uses `chunk_{d,p,j}_tags ? :code` (single-key JSONB predicate), now unblocked — DB confirmed GIN-index (gate i, resolved 2026-07-23). **Timed separately as `tag_select_ms`** — measures ONLY this chunk-level query, not the step-2 cascade (see `doc_narrow_ms` above; the two were ambiguous under one bucket name until TECH's clarification). Query assumes the GIN exists (migration lands before Pool ships, per DB) — not gated on the migration landing first.

### 3.2 Strategy 2 — Vector search

Embed the rewritten query (`gemini-embedding-001`, 1 call), search `rag_published_embeddings_vec_hnsw` (HNSW cosine), width from `resource_posture.breadth` (§3.4). No tag narrowing needed — HNSW is already sublinear at 1.94M rows.

### 3.3 Strategy 3 — Inherited (AHCA authority)

Conditional, not unconditional: fires only when a `j:payor.*` tag matched (plan-scoped query) OR — per Ananth's clarification — defaults to AHCA when **no** payor tag matched at all (AHCA is the default payor). Reuses `_inherited_authority_doc_ids()` + `_augment_pool_with_inheritance()` as-is. Contributes 0 candidates for out-of-domain queries where neither condition holds.

### 3.4 Width — driven by `ResourcePosture.breadth`, not hardcoded

Each strategy's over-fetch width scales off `resource_posture.breadth` (EXACT → tight, FAN_OUT/RELY_ON_EXTERNAL → wide), proportioned per-strategy (exact multipliers TBD during build — Ananth's example numbers, e.g. breadth×20 for tag-selection / breadth×100 for vector, were illustrative, not fixed ceilings, confirmed 2026-07-23). Cost model: **embed calls are the expensive resource, not k** — vector search at high k and BM25-replacement tag selection at high width are both cheap once narrowed; don't design around retrieval breadth as if it were costly.

### 3.5 Union + dedup

Union the three strategies' candidates. Dedup by chunk id, then by content (`content_sha` / normalized-body prefix) — same two-tier dedup `_expand_with_neighbors()` already does for siblings, applied here first to the match set before neighbors ever run, so neighbors aren't computed for a candidate that's actually a duplicate of one already kept.

### 3.6 Neighbor assembly

Call `_expand_with_neighbors()` (§1) unchanged over the deduped match set. Per-candidate provenance (§5) must survive this step — the function's generic `dict` shape needs confirming it round-trips a `source_arm`/`source_type` field without dropping it (verify during build, don't assume).

## 4. What's genuinely undesigned — Pool's real work

### 4.1 GateResult → partition_terms() gap (blocking §3.1 fully, not blocking start)

`literal_anchors` and `untagged_meaningful_tokens` don't exist anywhere in the new pipeline. Two options, not yet chosen:
  - **(a) v1 ships tag-only** — partition only `d_codes`/`j_codes`/`p_codes` (skip literal-anchor and untagged-token buckets entirely). Loses precision on queries anchored by a literal code/ID or carrying meaningful untagged content, but ships now, reuses `selectivity_for_tag()` untouched.
  - **(b) Pool re-derives literal anchors + untagged tokens itself** from `gate_result.query`/`normalized`, porting the legacy regex/heuristic. More complete, more new code, more surface area to get wrong.
  Leaning (a) for v1 (smaller, honest about the gap, fast-follow (b) as an Eval-gated enhancement) — **open for TECH/Eval's read before locking.**

### 4.2 Pool-DB-access pattern (gate i) — RESOLVED

GIN-index `chunk_{d,p,j}_tags`, confirmed by DB 2026-07-23 (§1, §3.1 step 4). No longer open.

### 4.3 Per-strategy width multipliers

Exact `breadth × N` constants per strategy — build-time calibration, not fixed here (§3.4).

### 4.4 Provenance shape for Router's feature vector / Contract's `source_types[]`

What exactly gets tagged onto each candidate (`source_arm: "tag_select"|"vector"|"inherited"`, score, raw rank) — needs to be just enough for Router to build a feature vector and Contract to build `source_types[]`/`cited_source_indices[]`, without over-specifying before Router/Fillers exist to consume it (§2, Retriever's sanity-check ask applies here specifically). **UX non-blocking note (2026-07-23):** `PoolCandidate.source_type` is singular per-candidate while Contract's eventual `source_types[]` is plural/aggregate — the one-to-many mapping (candidate-level singular → pool-level aggregate list) needs to be explicit whenever Router/Contract get built. Not Pool's problem to solve now, just flagged so it isn't lost.

## 5. Output shape — draft, NOT locked (Retriever review pending)

```python
@dataclass
class PoolCandidate:
    chunk_id: str
    document_id: str
    text: str
    is_neighbor: bool
    source_arm: str          # "tag_select" | "vector" | "inherited"
    score: float | None      # None for pure neighbors (inherits nothing until synthesis)
    tags: dict                # passthrough, Curation-pinned shape
    status: str                # planned|live passthrough — Product-Awareness reality-gating (target-structure-spec §10)
    source_type: str           # passthrough, same reason
    bm25_score: float | None   # ADDED 2026-07-23 (Filler a request, Retriever-confirmed): ts_rank_cd
                               # against every match candidate regardless of source arm — Fillers can't
                               # make DB calls (gate b), Pool supplies this instead. plainto_tsquery, not
                               # to_tsquery (the latter throws on real user text). None for neighbors —
                               # they weren't retrieved by any term match, same "None = no signal"
                               # convention as `score`.

@dataclass
class PoolResult:
    query: str
    candidates: list[PoolCandidate]
    segment_ms: dict            # doc_narrow_ms (§3.1 step 2 cascade), tag_select_ms (§3.1 step 4 chunk query), embed_ms, vector_ms, inherited_ms, dedup_ms, neighbor_ms — every DB/retrieval segment split per TECH's clarification 2026-07-23, gate (d)
    strategy_hint: str          # which arm(s) actually contributed, for Router's feature vector
    fallback_triggered: bool
    pool_ms: int
    query_embedding: list[float] | None  # ADDED 2026-07-23 (Filler s / Payor Platform request,
                                          # Retriever-relayed + independently verified): gemini-embedding-001
                                          # @ output_dimensionality=1536, confirmed live to match the Payor
                                          # Fact Store's own vector(1536) schema exactly. None when the
                                          # vector arm didn't run (no-retrieval postures) or embed failed —
                                          # Filler s falls back to its own bounded call in that case, always
                                          # correct either way, this is purely a redundant-call optimization.
    required_phrases: list[tuple[str, float]]  # ADDED 2026-07-23 (Ananth's finding, verified against
    boosted_phrases: list[tuple[str, float]]   # legacy + Filler A's actual filler_a.py, not just relayed):
                                                # Gate's expansion_phrases never carried selectivity weight
                                                # downstream — generic terms diluted equally with highly
                                                # discriminating ones. Reconstructed from gate's matched
                                                # d/j/p codes + selectivity_for_tag() (no Gate contract
                                                # change). Query-level only — per-candidate phrase presence
                                                # is cheap in-memory work left to the consuming filler's own
                                                # rerank pass. DROP-bucket phrases (sel<0.40) excluded
                                                # entirely from both lists, not kept at low weight.
```

## 6. Explicitly NOT proposed here

- Not changing `_doc_ids_with_tag`/`build_candidate_pool`'s cascade logic — reused as-is.
- Not changing `_expand_with_neighbors`'s internals — reused as-is, only the caller is new.
- Not resolving gate (i) myself — DB's explicit call, not a default.
- Not designing Router/Fillers' consumption of the pool beyond what §4.4/§5 sketches — coordinating via Retriever once Router/Fillers exists (no session forked yet, confirmed by Retriever 2026-07-23).

## 7. What's explicitly out of scope (unchanged from kickoff)

- Shape's classification/posture/structure logic (Gate/Reformat/Structure, all locked)
- Router's strategy/arm selection, Fillers' slot-filling, Synthesis/Contract/Timing
- ORG/INSTANT-RAG/CACHE adapter internals (owned by Org/Instant-RAG/Cache agents; Pool only defines the `SourceAdapter` seam they'll implement against)

## 8. Asks per collaborator

- **UX — ✅ FULLY SIGNED OFF 2026-07-23** (4/5 confidence). All three items cleared, including the seam-architecture escalation: Ananth confirmed PUBLIC-only-v1-via-`SourceAdapter`-seam directly, with the plug-and-play requirement now formalized in §3.0. `pool` emit key as Diagnostics-only confirmed — telemetry only (`segment_ms`/`strategy_hint`/`fallback_triggered`), no narrative layer, same pattern as `shape_reformat`. `PoolResult` field coverage verified (status/source_type/source_arm/segment_ms/score/tags all check out) — non-blocking note captured in §4.4.
- **Scope/auth fully unblocked 2026-07-23: Chat ✓, UX ✓, DB ✓ (gate i).**
- **Chat — ✅ SIGNED OFF 2026-07-23.** PUBLIC-only v1 confirmed correct against the real corpus_search→Pool path (ORG provisioned-not-wired, INSTANT-RAG live via a separate Vault path that never touches Pool, CACHE pre-Pool). §5 `PoolCandidate` shape confirmed sufficient — Chat's normalizer (`corpus_search.py:686`) translates RAG's internal `source_type` vocabulary to Chat's `SourceRef` shape, so Pool's internal vocabulary doesn't need to match Chat's directly. Non-blocking note for the record: Chat flagged a separate PA/Chat vocabulary mismatch (`chunk`/`product_docs` vs normalized `"document"`) in the grounding-badge logic — Chat is raising it directly with Product-Awareness, not a Pool action item, just touches the same source_type passthrough story.
- **UX** — new emit key `pool` (proposed, avoiding collision with `shape_gate`/`shape_reformat`/`shape_structure`) — Diagnostics-only like `shape_reformat`, or Chat-bubble-visible?
- **Eval — ✅ SIGNED OFF 2026-07-23** (full detail in `pool-simulation-tracker.md`). (1) BM25 before/after: confirmed legacy strategy-a is the right baseline, PLUS a union test — does Pool's full union (tag-select+vector+inherited, deduped, neighbors) exceed strategy-a baseline, acceptance `union >= baseline - 0.01`. (2) §4.1 tag-only-v1: **confirmed correct** — literal anchors rare, untagged tokens are a precision boost not a recall blocker, re-deriving legacy regex risks new bugs, matches Shape's own defer-then-fast-follow pattern. TECH's dependency on this is now cleared. (3) NUMBER-MOVING plan: cmhc 26-query bank (same as Gate/Reformat/Structure), per-query `pool_recall`/`pool_precision`/per-strategy recall/`neighbor_delta`, forced-arm (no Router optimization yet) — Pool's job is to maximize recall and accept low precision (0.30-0.50 expected, by design; Fillers' job is precision within the pool).
- **DB** — gate (i) RESOLVED (GIN-index, 2026-07-23) — sign-off here is confirming the migration timeline (lands before Pool ships) and the `chunk_*_tags ? :code` query shape matches what they intended.
- **TECH** — structural review: gates (b) single-pool, (d) per-segment timing (§5's `segment_ms`, now split `doc_narrow_ms`/`tag_select_ms` per TECH's 2026-07-23 clarification), (e) no god-file reintroduction, (i) closed per DB's GIN decision. Their stated dependency (Eval's §4.1 read) is now resolved above — expecting structural review of the real build (`pool-simulation-tracker.md`'s "Build status") to follow.

## 9. Process, unchanged from kickoff

Spec → cross-agent sign-off (this doc, via Retriever) → build with verify-before-trust discipline → unit + DB-integration + eval-bank tests (NUMBER-MOVING, before/after mandatory) → `pool-simulation-tracker.md` kept live → report to Retriever → next stop Router (Step 3).
