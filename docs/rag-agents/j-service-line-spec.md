# Spec: `j:service_line.*` — service line as a doc-level jurisdiction tag

**Owner:** Lexicon (Curation leg) · **Directed by:** Ananth 2026-08-19 · **With:** Service Line Registry · **Status:** implementing

## Why

Clinical-concept (`d:`) tags retrieve a concept's whole pool, not one line. `substance_use_disorders` (35,841 chunks) is shared by sud_residential + withdrawal_management + marchman_act. To **serve by service line**, a doc needs a line-level tag. Two independent facts (verified by Registry) kill the code-only alternative:

- **24 of 31 lines have zero `rendered_as` HCPCS codes** — they are per-diem/facility lines, never billed as a procedure. No code to filter on.
- **80 of 81 held AHCA 59G policy docs contain no HCPCS code** — policies describe services in prose and incorporate codes by reference. A code filter reaches the fee schedule, not the policy that defines the service.

So `j:service_line.<line_key>` is the right axis — a doc-level partition tag on the `j:` arm retrieval already filters, mirroring `j:doc_type`.

## Two constraints (learned the hard way — Registry, 2026-08-19)

1. **Never derive `j:service_line` from concept tags.** Inferring it from `substance_use_disorders` inherits the exact ambiguity we are removing. It comes from the document's **own provenance** — the rule number it cites — or an explicit assignment. Provenance in, not concept in.
2. **A doc carries MORE THAN ONE line tag.** `59G-4.031` maps to both bh_community_support and bh_therapy; the CBH fee schedule covers four lines across its pages. `j_tags` is multi-valued — single-valued would force a wrong choice.

## The two faces (kept separate — same guardrail as `j:doc_type`)

| face | source | mechanism |
|---|---|---|
| **doc assignment** (which docs carry the tag) | Registry's deterministic `(document_id, line_key, basis)` seed — from `line.rule_ref` → filename, or explicit assignment | written to `document_tags.j_tags` + propagated to `rag_published_embeddings.chunk_j_tags`; multi-valued |
| **query recognition** (query names the line → filter) | `spec.query_expansion_phrases` — the line's identity vernacular (Registry-owned under the hybrid split), seeded here from `canonical_name` | query-side only; read by Gate's `expand_query_via_lexicon` |

Entries carry `query_expansion_phrases` ONLY — `strong_phrases`/`aliases` stay EMPTY, so no doc is content-tagged and retrieval is unchanged until doc-side ASSIGNMENT happens. Corpus-neutral, freeze-safe.

## Shape

`kind='j'`, container `code='service_line'` (`parent_code=NULL`, sibling to `payor`/`state`/`regulatory_authority`/`doc_type`); children `code='service_line.<line_key>'`, `parent_code='service_line'`. 31 children (the FL Medicaid BH lines the Registry binds today).

## Coverage reality (measured 2026-08-19)

- 18 lines carry a `rule_ref`; **~7–8 resolve to a held document today** (≈13 doc→line assignments as the first seed). e.g. inpatient_psych_adult → 5 docs (59G-4.150), fact → 2 (59G-4.127), bh_community_support → 2 (59G-4.031).
- The other rule_ref lines resolve to zero because the policy isn't ingested — **Deep Research acquisition targets, not assignment problems**. Mapping a line before its doc lands = mapping to nothing.
- The statute/facility lines (Baker Act, Marchman, CSU, SUD residential, withdrawal) have no 59G doc — assignment is explicit or awaits the statute doc.

## v2 — DURABLE doc-side (Ananth sign-off 2026-09-07, after the v1 erasure)

v1 stored the doc-side in the phrase-derived `j_tags` tables. Two rebuild mechanisms
erased it (nightly QA→RAG lexicon rebuild wiped the RAG-only query entries;
`retag-in-place` recomputes `j_tags` from phrase-matching and an explicit assignment
has no phrases). See LEXICON_REGISTRY_CONTRACT.md §5.1. `document_doc_type` (a
**column**) survived every rebuild — 1.03M chunks intact. So the durable shape is a
dedicated column, exactly like `j:doc_type`, NOT `j_tags`.

**Durable design (mirrors document_doc_type, multi-valued):**
- **Source of truth:** Registry's doc→line assignment (their `service_line.*` store /
  `service-line-doc-assignment.seed.json`). Registry owns it (§1). Explicit provenance
  (`rule_ref`/`cited_source`), never concept-derived.
- **Index column:** `rag_published_embeddings.document_service_lines text[]` — array of
  `line_key`s (multi-valued: a doc can be several lines). New DDL → **route through DB
  seat** (Platform Architects). Retag/rebuild never touch a column → durable.
- **Null convention (Registry, 2026-09-07 — sourced-vs-applicable):** column is
  **nullable**, `DEFAULT NULL`. `NULL` = never assigned (no provenance yet — 22 of 31
  lines today); `'{}'` (empty array) = assessed and belongs to no line; `{lk,…}` =
  assigned lines. Retriever MUST treat `NULL` (unknown → don't exclude) differently
  from `'{}'` (explicit none). The sync writes an array only for docs in Registry's
  seed; it never writes `'{}'` unless Registry explicitly marks assessed-no-line.
  Chosen over "extend the seed to all 31 first" because completeness never holds as
  new lines arrive.
- **Sync:** a `sync_service_lines` step (same pattern as `/admin/sync-doc-metadata` +
  the nightly `sync_metadata`) reads Registry's assignments → writes the column →
  survives every rebuild. Lexicon/Curation owns this.
- **Query-side:** the 32 `j:service_line` entries — now persisted in **QA and RAG**
  (2026-09-07) so the nightly keeps them. Expansion yields `j:service_line.<lk>`.
- **Read-side (Retriever):** filter on `document_service_lines` when the query carries a
  `j:service_line.<lk>` tag. Column name + text[] + empty-array null convention.

**Interim:** the 562 v1 index `chunk_j_tags` are left inert (Ananth 2026-09-07) — harmless,
superseded when the column lands. Not stripped.

## Sequencing

1. Create the 32 entries (this spec) — corpus-neutral, safe under freeze. **[done at implement]**
2. Registry supplies `(document_id, line_key, basis)` seed. Lexicon applies `j:service_line.<line_key>` to `j_tags` + propagates to the index (same path as the `document_doc_type` sync). Multi-valued.
3. Query phrases enriched as Registry authors identity aliases (hybrid: identity vernacular is Registry's).
4. Contract §4 carries the decision (Registry writes it per §5 before downstream change).
