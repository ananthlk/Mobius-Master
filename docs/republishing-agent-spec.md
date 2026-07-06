# Republishing Agent — Status & Lift Tracking Spec

**Role of this agent:** drive the corpus from *coherent at lexicon revision N* to *coherent at
revision N+1*, **prove** coherence across every surface chat serves from, then **measure the lift**
on a held-constant eval bank. The agent owns the instrument, not the lexicon authoring.

---

## 1. The cycle (validated with the user, 2026-06-30)

```
Lexicon vN  →  tag + embed docs (docs carry vN tags)
              ↓
   [STEADY STATE: chat expands the query via the vN lexicon AND matches
    it against docs tagged at vN — lexicon and corpus are coherent]
              ↓
   analyze → suggest lexicon improvements
              ↓
   Lexicon vN+1 (new/changed tags)   ← bump_revision()
              ↓
   retag docs → vN+1   ← Path B; the migration window
              ↓
   [STEADY STATE at vN+1: coherent again]   ← only now is re-eval valid
```

**Lift is only measurable between two *coherent* states.** The agent's job is to (a) detect the
incoherent window, (b) close it, (c) assert closure, (d) re-eval.

---

## 2. What already exists (reuse — do not rebuild)

| Capability | Where | Notes |
|---|---|---|
| Lexicon version source of truth | `policy_lexicon_meta.revision` (BIGINT) + `lexicon_version` (text) | `bump_revision()` in `mobius-rag/app/services/policy_lexicon_repo.py` increments on edit |
| Per-doc tag stamp | `document_tags.lexicon_revision` + `tagged_at` | migration `add_document_tags_lexicon_revision.py`; written by Path B `mobius-rag/app/worker/path_b.py:364` |
| **Stale detection (RAG side)** | `GET /documents/retag/status` (`mobius-rag/app/main.py:2924`) | compares each doc's `document_tags.lexicon_revision` vs `current_lexicon_revision`; returns `current_lexicon_revision`, `stale_count`, `untagged_count`, `stale[]` |
| Retag trigger | `POST /documents/retag` (`main.py:2838`) | bulk Path B; re-extracts facts + retags; **stamps new revision**; skips embedding |
| Per-doc publish status | `DocumentStatusTab.tsx` | shows `Lexicon rev N` badge, stale count, "Retag N stale" button, `published_at`/`published_rows`/`publish_verification_passed` |
| Tags read **live** at query time | `corpus_search.py` `LEFT JOIN document_tags dt ON dt.document_id = rag_published_embeddings.document_id` (main.py:988, 1301) | **Key:** within RAG, retag alone updates served tags — no republish needed for the tag-match path |
| Lexicon query-expansion | `corpus_search_lexicon.py` | in-process snapshot of `active` entries, **5-min TTL cache** |
| Eval runner + storage | `mobius-rag/eval/run.py` → `rag_eval_runs` / `rag_eval_results` | run carries `bank_version` (sha of bank) + `priors_version` (text label) |
| End-to-end chat eval | `mobius-qa/mobius-chat-qa/run_eval.py` → `reports/*.md` | runs against the live chat server (true end-to-end) |

**Consequence of "tags read live":** my earlier "retag-without-republish = incoherent" warning is
**overstated for the RAG-internal path.** Retag updates `document_tags`, which corpus_search joins
live. Republish (`rag_published_embeddings`) is only needed when the *embeddings/chunks/facts text*
changed, not for tag changes.

---

## 3. The three real gaps (what to build)

### Gap A — Chat-side coherence is unverified (the load-bearing gate)
`GET /documents/retag/status` proves the **RAG** corpus is at revision N. But chat can serve from its
**own synced copy** — Chroma collection `published_rag` + Postgres `published_rag_metadata`
(`mobius-chat/app/chat_config.py:87`), populated by `publish_sync.sync_document_to_retrieval_stores()`.
There are two chat retrieval paths in the code:
- calls RAG's `corpus_search_agent` endpoint (`RAG_API_URL`, `main.py:971`) → **live tags, auto-coherent after retag**
- queries its own Chroma/PG snapshot directly (`RAG_DATABASE_URL`, `RAG_TOP_K`, `RAG_FILTER_*`) → **stale until re-synced**

**Until we confirm which path serves production, the gate cannot assume retag-status == coherent.**
The robust gate is an **empirical smoke query through the actual chat agent**, not a code assumption.

**Build:** a `chat_coherence_probe` — fire 1–3 canary queries (whose answers depend on a vN+1
tag/alias) through the real chat endpoint and assert the vN+1 behavior shows up. Green probe = chat is
actually coherent, regardless of which internal path it took.

### Gap B — Eval runs aren't bound to a lexicon revision
`rag_eval_runs` has `priors_version` (free-text) but **no `lexicon_revision`**. So "lift" can't be
computed automatically — you can't assert run X was at rev N and run Y at rev N+1.

**Build:** add `lexicon_revision BIGINT` to `rag_eval_runs`; `eval/run.py` reads
`policy_lexicon_meta.revision` at run start and stamps it. Lift = `run(rev=N+1).avg_score −
run(rev=N).avg_score` on the **same `bank_version`**.

### Gap C — No single status rollup for the agent to read
The agent needs one call that answers: *current rev? % corpus coherent (RAG + chat)? last eval per
rev? computed lift? is re-eval unblocked?*

**Build:** `GET /republish/status` rollup that composes existing pieces:
```jsonc
{
  "current_lexicon_revision": 7,
  "rag_coherence":  { "total": 412, "at_current": 412, "stale": 0, "untagged": 0, "pct": 100.0 },
  "chat_coherence": { "probe": "green", "checked_at": "...", "canaries": [...] },
  "evals": [
    { "lexicon_revision": 6, "bank_version": "abc123", "avg_score": 0.505, "n_correct": 7, "run_id": "2346aefc" },
    { "lexicon_revision": 7, "bank_version": "abc123", "avg_score": null, "status": "blocked: chat probe pending" }
  ],
  "lift": null,                       // computed once both runs exist on same bank_version
  "re_eval_unblocked": false          // true iff rag pct==100 AND chat probe green AND cache TTL elapsed
}
```

---

## 4. Acceptance criteria per loop step

| Step | Action | DONE when |
|---|---|---|
| 1. Baseline | `eval/run.py --bank queries_cmhc.yaml` | run row in `rag_eval_runs` stamped `lexicon_revision = N`; this is the frozen baseline |
| 2. New lexicon | author vN+1, `bump_revision()`, sync QA→RAG (`sync_qa_lexicon_to_rag.py`) → RAG→chat | `policy_lexicon_meta.revision == N+1` in RAG; chat lexicon copy synced |
| 3. Retag | `POST /documents/retag` | `GET /documents/retag/status` → `stale_count == 0 && untagged_count == 0`, `current == N+1` |
| 4. **Coherence gate** | run `chat_coherence_probe`; wait out 5-min expansion cache | RAG pct == 100 **AND** chat probe green **AND** cache TTL elapsed → `re_eval_unblocked == true` |
| 5. Re-eval | `eval/run.py` same `bank_version` | run row stamped `lexicon_revision = N+1`; **lift** computed vs baseline |

Republish (`POST /documents/{id}/publish` / `publish_unpublished_documents.py`) is required in step 3
**only if** the retag changed embeddings/chunk text (Path B normally skips embedding) **or** chat
serves from its own snapshot (then re-sync via publish is how vN+1 reaches chat — confirmed by Gap A
probe).

---

## 5. Open question to resolve first
**Which retrieval path does the production chat agent use** — live RAG `corpus_search_agent`, or its
own Chroma/`published_rag_metadata` snapshot? This decides whether retag-alone reaches chat or whether
republish+sync is mandatory in step 3. Resolve empirically with the Gap-A probe rather than by
reading config, since deploys differ.

---

## 6. Build order (smallest trustworthy increment first)
1. **Gap B** (`lexicon_revision` on `rag_eval_runs`) — 1 column + 1 read in `eval/run.py`. Without it,
   no lift number exists. Cheapest, unblocks everything.
2. **Gap A** (`chat_coherence_probe`) — the gate that makes re-eval trustworthy.
3. **Gap C** (`/republish/status` rollup) — the agent's dashboard; pure composition of 1+2+existing.
