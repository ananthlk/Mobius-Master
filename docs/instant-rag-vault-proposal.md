# Instant RAG + Vault — Proposal (v1)

**Owner:** Instant RAG agent · **Status:** Draft for review · **Date:** 2026-07-09

Reviewers wanted: **chat**, **UX**, **RAG**, **lexicon**, **user/org-registry**.

This proposal takes ownership of the *instant RAG* surface (user uploads a file in
chat and asks about it) end-to-end: the upload entry points, the foreground/background
processing model, the **Vault** (a home for a user's uploaded docs), and
**permission-gated promotion** of a doc into broader corpus search.

---

## 1. Current reality (inventory)

### Entry points — two, overlapping
- **Composer paperclip + drag-drop** → always `file_purpose=instant_rag`, 25 MB client cap.
  (`mobius-chat/frontend/src/app.ts` `uploadStagedAttachmentForInstantRag`)
- **⋯ "Upload file" modal** → purpose dropdown mixing `roster_reconciliation`
  (credentialing's pipeline) with `instant_rag`, 100 MB cap. (`setupUploadModal`)
- Both POST the same, misleadingly-named `POST /chat/roster-upload`
  (`mobius-chat/app/main.py:1271`), which fans out by `file_purpose`.

### Backends — two implementations, one live
- **(A) Standalone `instant-rag` skill** (`mobius-skills/instant-rag/`, "envelope"
  pattern, Cloud Run). Half-built: tagging / quickfire / promote / re-dispatch are
  `TODO`, store is in-memory. **Chat bypasses it as of 2026-04-27** (it skipped
  lexicon expansion + hybrid retrieval + rerank). Still referenced by `doc-reader`,
  `appeals-agent`, `finance`, and the task-manager contract.
- **(B) Canonical path (LIVE)** — chat → `mobius-rag /upload?ttl_days=7&agent_scope=chat`
  (`mobius-rag/app/main.py:4788`) → Path B chunking at priority 0 (jumps the queue) →
  publish → `publish_sync` writes chunks to the shared stores flagged `instant_rag=true`.

> **Decision (2026-07-09): retire (A), fold into (B).** Migrate the remaining
> non-chat consumers (appeals-agent, doc-reader, finance) onto the canonical
> `/upload` path, then archive the standalone skill. One ingestion path to own.

### Processing / feedback — all-background (the core regression)
- Inline foreground was **removed** to dodge Cloud Run's 60 s LB idle-drop, so even a
  1-page doc is forced async (`mobius-chat/app/main.py:1094`).
- "Ready" = a detached thread polling `/documents/{id}/status` every 15 s, then posting
  a `role='system'` message into the thread (`_watch`, `main.py:865`). No SSE, no
  durable per-user notify.

### Storage & scoping
- Bytes → RAG GCS bucket (`mobius-rag-uploads-mobiusos`). Chunks → shared `published_rag`
  Chroma + `published_rag_metadata` + pgvector `rag_published_embeddings`.
- Ownership → durable catalog `instant_rag_uploads`
  (`mobius-chat/db/schema/031_instant_rag_uploads.sql`): `document_id`, `user_id`,
  `thread_id`, `status(active|expired|discarded|promoted)`, `expires_at`,
  `suggested_*`/`confirmed_*` tag columns.
- **Scoping is flag-based, not isolated.** Everything is in one shared collection;
  `instant_rag=true` partitions it (corpus search excludes it, per-thread search
  includes it). Per-doc pinning via `document_id` / `include_document_ids`.
  **No retrieval-time visibility gate exists** — no per-user/org ACL.

### Permissions (exist, unused for docs)
- `UserOrgMembership.roles` (open set incl. `rag_admin`, `corpus_curator`) + `org_slug`
  (`mobius-user/.../models/tenant.py`). Org registry approved
  (`docs/org-registry-proposal.md`). **Nothing consults roles on ingest or retrieval.**

---

## 2. Target flow

### 2.1 One upload surface
Collapse both entry points into the **composer attach** (paperclip + drag-drop + paste).
- Rename the endpoint `POST /chat/upload`; keep `/chat/roster-upload` as a back-compat alias.
- **Roster/credentialing stays the credentialing agent's** — we stop overloading the
  chat instant-rag surface with it. If a CSV/XLSX looks like a roster, offer
  reconciliation as an inline suggestion rather than a competing upload path.
- One consistent cap (100 MB server; client warns > 25 MB about processing time).

### 2.2 One adaptive path — not "foreground OR background" as two code paths
Latency + user attention decide the *feel*; the mechanism is single.

1. Upload returns immediately with `document_id` + `upload_id` and opens a **progress
   channel** (SSE from chat, backed by bridging RAG's existing `ChunkingEvent` SSE
   server-to-server up to the browser — replaces the 15 s poll thread).
2. **Foreground feel** — small/fast doc finishes (< ~15–20 s) while the user is still on
   the thread: progress ticks chunk → embed → ready, then we auto-fill their question
   ("what does it say about …?") and they ask. They never left.
3. **Background feel** — big/slow doc: the user navigates away or does other things. On
   completion we fire a **durable notify**: (a) the system message into the origin
   thread (kept), plus (b) a task-manager signal keyed to the owning `user_id`
   (`instant_rag_uploads.user_id`) so a Vault badge / task-card surfaces it wherever
   they are.
4. On failure/timeout: same channel reports the error with a retry affordance.

No user-facing toggle. If it's fast you stay; if it's slow you're freed and pinged.

### 2.3 Vault (v1 = registry + lifecycle)
The Vault is the **user-facing view of `instant_rag_uploads`** — no new physical store.
- List a user's uploaded docs **across threads**, with status + **TTL countdown**.
- Actions per doc: **extend TTL / keep**, **re-use in a thread** (existing
  `link-to-thread`), **delete/discard**, **promote** (§2.4).
- Wire the `MOBIUS_VAULT_URL` app-tile (currently `comingSoon`) to this view.
- **Deferred to Vault v2:** hard per-org/user/patient namespace isolation
  (HIPAA-grade separate collection/DB boundary — see `hipaa-compliance-gap-analysis.md`).
  v1 keeps the shared-store + flag model; v2 adds the isolation boundary.

### 2.3b Vault action endpoints — contract (settled w/ Vault agent 2026-07-13)

The Vault page (owned by the Vault agent) consumes these. Read + re-attach + download
exist today; delete + extend are mine to build; promote is P2-gated (stub in UI).

**EXISTS (live):** `GET /chat/uploads?user_id=&include_inactive=`, `GET /chat/uploads/{id}`,
`POST /chat/uploads/{id}/link-to-thread` (re-attach), `GET /chat/uploads/{id}/download`.

**TO BUILD — `DELETE /chat/uploads/{document_id}`** (chat, catalog-only for v1):
- `require_user` + ownership. Sets `instant_rag_uploads.status='discarded'`.
- Returns `200 {document_id, status:"discarded"}`; `404` not-found/not-owner;
  **idempotent** (already-discarded → 200 no-op). Drops from default list.
- v1: catalog soft-delete only; the RAG doc TTLs out naturally (≤7 d). RAG hard-expire
  (`documents.expires_at=now()`) is an optional follow-up to free it sooner.

**TO BUILD — `POST /chat/uploads/{document_id}/extend {days:N}`** (chat **+ RAG**):
- `require_user` + ownership. `N` optional → default `INSTANT_RAG_TTL_DAYS` (7).
- Updates `instant_rag_uploads.expires_at = now() + N` **AND** calls RAG to set
  `documents.expires_at = now() + N` — ⚠ **the RAG value is what drives cleanup**, so
  extend must update it too or the doc is cleaned despite the catalog. **RAG needs a small
  endpoint** (e.g. `POST /documents/{id}/extend {days}` / PATCH expires_at) — it doesn't
  have one today.
- Returns `200 {document_id, expires_at}` (ISO) for in-place countdown update. `404`
  not-found/not-owner. (Reactivating `expired`→`active` = nice-to-have, deferred to v1.)

**promote:** P2 — needs the physically-separate org-doc store (not built). UI stubs it disabled.

### 2.4 Permission-gated promotion — 3 tiers
A doc's `visibility` moves up a ladder; each rung is gated and changes retrieval.

| Tier | Who can search it | Gate to reach it | Mechanism |
|------|-------------------|------------------|-----------|
| **private** (default) | uploader, in their threads | — (default on upload) | `instant_rag=true`, `expires_at` set, scoped by `document_id` |
| **org** | members of the doc's `org_slug` | uploader (self-serve) | new `visibility='org'` + `org_slug` on chunks; retrieval filters `org ∈ my orgs` |
| **global** | everyone (authoritative corpus) | role `corpus_curator`/`rag_admin` **and** verification | enqueue into batch Path A pipeline → `verification_tier='verified'`, `instant_rag=false`, `expires_at=NULL` |

- **The net-new work is org-tier retrieval visibility** — the first time `org_slug` +
  membership is consulted at query time.

> **ARCHITECTURE DECISION (Ananth, 2026-07-09): physical store separation, not a filter.**
> Private + org docs live in a **separate namespace/DB**, physically isolated from the
> global authoritative corpus. Contamination becomes *structurally impossible* — a query
> against global cannot return a private/org row, with no reliance on a `visibility` filter
> being correct everywhere. It also contains the self-claimed-membership risk: a spoofed
> membership's blast radius is that org's namespace, never the authoritative corpus.
> - **The org/namespace DB houses BOTH private (user) and org docs.** private→org is a
>   metadata move *within* that DB; **org→global is the only physical crossing**, gated by
>   role + batch verification.
> - **Retrieval becomes a union across stores** — a normal chat query searches
>   `global corpus ∪ my private docs ∪ my orgs' docs` and merges, rather than filtering one
>   shared pool. This is the real cost of separation and is accepted.
> - Supersedes the earlier "chunk-metadata filter on the shared collection" (old §6 Q2).
> - **Scheduled for later** (after P0/P1) — flagged now so RAG/chat build toward it and
>   nothing new gets wired to deepen the shared-collection flag model.
- **Global** promotion does not let an "instant" tier doc silently join the
  authoritative payor corpus — it must pass through verification (batch pipeline),
  gated by `corpus_curator`/`rag_admin` in that org.
- Promotion clears the TTL and flips the catalog `status='promoted'`.

**Gate details (confirmed by user-manager agent 2026-07-09):**
- Roles are **per-org**, not global: the gate is "user holds `corpus_curator`|`rag_admin`
  **in the org that owns the doc**," not "holds it anywhere." Role grants are
  admin-scoped (internal-key API) — users cannot self-assign → the **global** gate is
  trustworthy.
- Membership lookup **already exists**: `GET /api/v1/users/by-identity?subject=<jwt-sub>`
  → `org_memberships: [{org_slug, display_name, roles}]` (auth `X-Internal-Key`, ~150ms).
  Cache per-user 5-min TTL. RAG's filter `visibility='org' AND org_slug ∈ memberships`
  maps directly onto this payload. **`org_slug` must match exactly, never translate** —
  customer/internal orgs are hyphenated (`david-lawrence-center`), payor orgs are
  underscored lexicon keys (`sunshine_health`).
- **⚠ Trust caveat — org membership is SELF-CLAIMED today** (preferences modal validates
  the org exists but has **no approval step**). So org-tier retrieval is **not safe for
  sensitive docs in prod** until a membership-approval flow exists (user-mgr has flagged
  it as pre-prod work). **Therefore org-tier v1 = discoverability of *non-sensitive*
  docs only**; sensitive docs stay private or go through the (trustworthy, role-gated)
  global path. P2 org-tier retrieval lands *after* membership approval, or ships gated
  to non-sensitive until then. The global gate is unaffected.

---

## 2.5 Promotion recommendation — content-eligibility (Ananth 2026-07-13)

Users won't reliably self-classify, and a wrong "public" on a PHI doc is a HIPAA breach.
So on **upload-complete** (and backfillable for prior docs) the system **auto-classifies
the content and recommends a visibility ceiling** — the highest tier the doc is *safe* for.
The user approves/overrides; the system does the classifying.

**Two layers gate a promotion** (both required):
- **Content-eligibility** (this recommendation) — the safe ceiling from content.
- **Authority** (§2.4) — role (`corpus_curator` for public) + the physically-separate store.
A doc promotes only when `target_tier ≤ recommended_ceiling` **and** user-approved **and**
(for public) role-authorized.

**Decisions:**
- **GATE, not advisory.** The promote UI disables tiers above the ceiling. Going above
  requires an explicit override + warning + audit (and public still needs the role). A
  distracted user cannot one-click a PHI doc to public.
- **PHI-first v1.** Ship the PHI/HIPAA detector first (highest-risk, most detectable).
  Default **private** unless clearly PHI-free. Confidential + org-specific are fast-follows.

**Model:**
- `recommended_ceiling`: PHI detected → **private**; PHI-free (v1) → **public-eligible**
  (confidential/org-specific fast-follows will lower this later).
- **Asymmetric risk → conservative:** high-recall PHI (catch it even with false positives);
  uncertain → assume PHI → private. **Only recommends, never auto-acts.**

**Mechanics:**
- Runs **async post-index** (doesn't slow the fast path) — same lane as deferred enrichment.
- PHI detector = the 18 HIPAA identifiers (names, DOB, SSN, MRN, dates-of-service, address,
  phone, …) via regex + NER + an LLM pass. Recall bar/test set anchored on
  `docs/hipaa-compliance-gap-analysis.md` + `docs/PHI_PATIENT_TEST_CASES.md`.
- Stored on `instant_rag_uploads` (new columns): `suggested_visibility` (private|org|public),
  `phi_flag`, `phi_evidence` (redacted reasons/spans), `classifier_confidence`, `classified_at`.
- **Surfaced at upload-complete:** "Recommended: keep private — contains patient info" /
  "Recommended: safe to share with your org" + [Approve] [Override…]. Backfill runs it over
  existing catalog rows.
- Can ship **ahead of the org-store (P2)** — the recommendation informs + pre-fills the
  eventual promote; it's useful even while promote is stubbed.

**Owner: a DEDICATED PHI-classifier SKILL** (Ananth 2026-07-13) — `mobius-skills/phi-classifier/`,
its own service. Not the feedback classifier, not a RAG pass — a focused, high-stakes,
**platform-reusable** component (instant-RAG is the *first* consumer; org-docs, Drive
doc-review, compliance also need it).
- **Interface:** `POST /classify {text, document_id?} → {phi_flag, phi_evidence[] (redacted
  spans/reasons), recommended_ceiling (private|org|public), confidence, identifiers_found[]}`.
- **Detection = layered, high-recall:** regex for structured identifiers (SSN, MRN, DOB,
  phone, email, dates-of-service, ZIP), NER for names/locations, an LLM pass for context +
  edge cases. Recall over precision — false positives are cheap, a missed PHI is a breach.
- **Recall bar (hard gate on the skill):** a test suite anchored on
  `docs/PHI_PATIENT_TEST_CASES.md` + `docs/hipaa-compliance-gap-analysis.md`; the skill must
  catch ~all PHI in it before it ships. This bar is the skill owner's contract.

**Finalized `/classify` contract (settled with PHI agent 2026-07-13):**
```
POST /classify {text: str, document_id?: str}
→ { phi_flag: bool,
    recommended_ceiling: "private"|"org"|"public",
    confidence: float 0-1,
    identifiers_found: [category strings],
    phi_evidence: [{category, redacted_span, offset}],
    classifier_version: str,     # detector version — for re-classify when recall bar improves
    layers_run: [str] }          # which of regex/ner/llm executed (degraded-mode visibility)
```
- `offset` = 0-indexed char offset into the **submitted** text (valid against the exact
  string POSTed; we store evidence, don't re-locate in the doc).
- `redacted_span` = fully masked, format-preserving where safe (`***-**-####`, `J•••• S••••`,
  `[DOB]`) — **never** raw PHI; the skill logs no raw text/spans.
- **Conservative default (skill guarantee):** any uncertainty, LLM-layer timeout, or failure
  → `phi_flag=true` / `recommended_ceiling="private"`. Fails toward private, never public.

**Consumer wiring (this agent):** async post-index → POST extracted text → store the verdict
on `instant_rag_uploads` → the Vault/promote UI reads it to gate tiers. Columns (migration):
`suggested_visibility`, `phi_flag`, `phi_evidence` (jsonb), `classifier_confidence`,
`identifiers_found` (jsonb), `classifier_version`, `layers_run` (jsonb), `classified_at`.
- **`classifier_version` stored** → when the skill bumps its recall bar, backfill re-classifies
  rows tagged with an older version.
- **`layers_run` stored** → verdicts produced in **degraded mode** (LLM skipped/timed out →
  defaulted private) are flagged for **re-classification when the LLM layer is healthy**, so a
  transient timeout never *permanently* under-promotes a doc that's actually shareable.
- Wire + live-test the moment the skill pings a dev `/classify` URL.
- **Consumers** call async post-index; instant-RAG stores the result on `instant_rag_uploads`
  and gates the promote UI on it. The skill is stateless (classify text → verdict).
The instant-RAG surface (recommendation display + `suggested_visibility` column + promote-UI
gating) stays chat/Vault-agent/mine; I'm the first consumer + wrote the contract.

## 3. Ownership & boundaries

**Instant RAG agent owns:** the `instant_rag` upload contract, the `instant_rag`
flag / `verification_tier` / `expires_at` / `visibility` semantics, the
`instant_rag_uploads` catalog contract, the TTL + promotion lifecycle, and the
(soon-archived) standalone skill's decommissioning.

**Not ours:** roster/credentialing (credentialing agent), the core RAG chunking/retrieval
internals (RAG agent — we specify the flags/filters we need), org identity & roles
(user/org-registry agent), lexicon tagging internals (lexicon agent).

---

## 4. Asks per collaborating agent

- **chat** — unify the two entry points onto `/chat/upload`; replace the poll-thread
  watcher with the SSE progress bridge; build the Vault view over `/chat/uploads`;
  render promotion controls + TTL countdowns.
- **UX** — the foreground progress affordance, the background "ready" notify pattern
  (system message + task badge), and the Vault surface layout + promotion consent copy.
- **RAG** — expose an SSE chunking-progress stream chat can subscribe to per
  `document_id`; add `visibility` + `org_slug` columns to the published chunk stores and
  filter retrieval by them; wire `/promote` → batch Path A for the global tier.
- **lexicon** — ✅ RESOLVED: P/D/J tagging already runs **inline** in Path B (the
  `lexicon` stage, in-memory Aho-Corasick, no LLM, ~ms — noise vs the ~15s budget; embed
  dominates). Nothing to add to the foreground. Read `document_tags` (p/d/j jsonb, keyed
  `document_id`) **as soon as the CHUNK stage completes** → that's the `suggested_*`
  source; `confirmed_*` stays a Vault-side user action. The `pipeline.py:74` TODO existed
  only because the standalone skill bypassed Path B — it evaporates on the canonical path.
  Ephemeral docs excluded from nightly retag churn (agreed).
- **user/org-registry** — confirm `roles` (`corpus_curator`/`rag_admin`) + `org_slug` as
  the promotion gate; provide the "which orgs is this user in" lookup for org-tier
  retrieval filtering.

---

## 5. Phased delivery

- **P0 — Unify & fix feedback.** One entry point; SSE progress bridge; foreground feel
  for fast docs; durable background notify. (chat + UX + RAG)
- **P1 — Vault v1.** Registry view over the catalog: list/extend/delete/re-use across
  threads; TTL countdowns; wire the app-tile. (chat + UX)
- **P2 — Promotion tiers.** `visibility` column + org-tier retrieval filter (self-serve
  org promotion); global promotion via role-gated batch verification. (RAG + user)
- **P3 — Retire standalone skill.** Migrate appeals-agent/doc-reader/finance to the
  canonical path; auto-tagging populates the tag columns; archive `mobius-skills/instant-rag/`.
  (instant-rag + lexicon)
- **Vault v2 (later)** — hard private-namespace isolation (HIPAA boundary).

---

## 6. Open questions for reviewers

1. **RAG:** cheapest way to expose per-`document_id` chunking progress as SSE to chat —
   reuse `ChunkingEvent` or a new lightweight status stream? *(open)*
2. **user:** ✅ RESOLVED — membership lookup exists (`/api/v1/users/by-identity`). Org-tier
   retrieval gated by the self-claimed-membership caveat (non-sensitive until approval lands).
   **Store shape DECIDED:** private + org docs move to a **separate namespace/DB**, physically
   isolated from the global corpus (see §2.4 architecture decision) — not a shared-collection
   filter. Retrieval unions across stores. Scheduled after P0/P1.
3. **lexicon:** ✅ RESOLVED — tagging is already inline in Path B; read `document_tags`
   post-chunk. No foreground-latency cost.
4. **chat/UX:** foreground cutoff — what wall-clock (e.g. 15 s) flips the UI from
   "stay and watch" to "you're free, we'll ping you"? *(open — chat + UX)*

---

## Appendix A — Standalone skill decommission (P3, inventory verified 2026-07-09)

**Finding: the skill has NO live runtime ingestion consumers.** Retiring it is low-risk.

| Suspected consumer | Reality | Action needed |
|---|---|---|
| **chat** | Resolution order is `MOBIUS_RAG_URL` → `CHAT_SKILLS_INSTANT_RAG_URL` (legacy fallback, `main.py:962`) → `:8001`. `MOBIUS_RAG_URL` is set in dev.env → skill already bypassed. | Remove the `CHAT_SKILLS_INSTANT_RAG_URL` fallback branch + env (chat agent). |
| **appeals-agent** | Uploads via `{CHAT_BASE}/chat/roster-upload` (`run_loop.py:170`) → chat proxy → canonical path. **Not** a direct consumer. | None (endpoint-rename alias covers it). |
| **doc-reader** | Only *copied* the envelope dataclass (`doc-reader/app/envelope.py:7` "Modeled on…"); builds its own transient envelopes, never calls the skill at runtime. | None (independent copy stays). |
| **finance** | Registered as a consumer *inside* the skill (`consumers/`); no external caller invokes the skill to trigger it. | Confirm w/ finance agent; migrate if any latent use. |
| **task-manager** | Defines the `instant_rag.lifecycle` contract (producer `instant-rag`). | Re-point producer to canonical path / this agent (task agent). |
| dev orchestration | `mstart:623`, `landing_server.py:253`, `.claude/launch.json:279` start it locally on `:8040`; `thread_corpus_search.py:8` has a **stale comment** describing the old flow. | Remove the 3 launch entries; fix the comment. |

**Decommission steps (P3):** (1) confirm zero prod traffic to the `mobius-instant-rag`
Cloud Run service via request logs; (2) drop chat's `CHAT_SKILLS_INSTANT_RAG_URL`
fallback; (3) re-point the task-manager `instant_rag.lifecycle` producer; (4) confirm
finance has no latent dependency; (5) remove dev-orchestration entries + the stale
`thread_corpus_search.py` comment; (6) archive `mobius-skills/instant-rag/`.
**Note:** `:8040` = instant-rag local port; `:8010` = lexicon/credentialing (do not conflate).

---

## Appendix B — Org doc-store registry (onboarding contract, with roster/credentialing)

Follows directly from §2.4's physical store separation: each customer/provider org's
private+org docs live in their own namespace/DB. Something must record **which store
holds org X's docs** and provision it at onboarding. The canonical org master is
**`org_profile` in provider-roster-credentialing** (migration 030: *"orgs are discovered
and set up here before users or providers are enrolled"*) — so the org→store mapping
lives there, alongside org identity.

**Division of labor:**
- **Roster/credentialing owns** storing, serving, and reporting the store descriptor
  (it's registry data on `org_profile`).
- **Doc-store side (this agent / RAG) owns** physically creating the namespace/DB — roster
  does not own doc-store infra. Roster *delegates* creation to a provisioner and records
  the result. This keeps store mechanics on our side and identity on theirs.

**Store descriptor** (new columns on `org_profile`, or a 1:1 `org_doc_store` table):

| field | meaning |
|---|---|
| `doc_store_status` | `none` \| `provisioning` \| `ready` \| `failed` |
| `doc_store_kind` | `shared_namespace` (v1 default) \| `dedicated_db` (HIPAA orgs, later) |
| `doc_store_ref` | namespace name or DB connection **secret ref** (never raw creds) |
| `doc_store_created_at` | when the store was first provisioned |

**Provision-or-get endpoint (idempotent), called during onboarding:**
```
POST /org/{org_slug}/doc-store/provision
→ 200 { org_slug, store: { kind, ref, status }, created: true|false }
```
- `created: true` iff this call actually created a new store; `false` if it already
  existed (idempotent re-onboarding is a no-op). **This is the "say if a new DB was
  created or not" requirement.**
- Internally: roster calls the doc-store provisioner (our side); provisioner is itself
  idempotent (create-if-absent) and returns `{ref, created}`; roster persists the
  descriptor and echoes `created`.

**Serve endpoint** (read path for retrieval + promotion):
```
GET /org/{org_slug}/doc-store  → { kind, ref, status }   (or fold into GET /org/{slug})
```
Consumers: retrieval (union across stores — needs the ref for each of a user's orgs),
and org→global promotion (reads the source org store).

**Descriptor home — `org_doc_store` sibling table (roster, migration 041; accepted 2026-07-09):**
1:1 to `org_profile` (not columns on it — doc-store is service-plumbing, not org identity;
sibling survives the 1:N `dedicated_db` future without another migration).
```sql
CREATE TABLE org_doc_store (
    org_slug         text PRIMARY KEY REFERENCES org_profile(org_slug),
    doc_store_status text NOT NULL DEFAULT 'none'
                     CHECK (doc_store_status IN ('none','provisioning','ready','failed')),
    doc_store_kind   text NOT NULL DEFAULT 'shared_namespace'
                     CHECK (doc_store_kind IN ('shared_namespace','dedicated_db')),
    doc_store_ref    text,          -- namespace name or SECRET ref (never raw creds)
    provisioned_by   text,          -- which provisioner call created it
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);
```

**Provision trigger — EXPLICIT, never automatic (accepted).** The onboarding workflow calls
`POST /org/{slug}/doc-store/provision` deliberately. Creating the `org_profile` row does NOT
auto-provision — regulatory/internal/system orgs must never get a doc-store. Only a customer
onboarding that's ready for docs triggers it.

**The provisioner leg (our side — the contract roster delegates to):**
```
POST {INSTANT_RAG_PROVISIONER_URL}/doc-store/provision
  body: { org_slug, kind }                       # kind defaults to shared_namespace
  → 200 { namespace_ref, created: true|false, status }
```
- **Idempotent, create-if-absent.** `created` is authoritative from the provisioner (it alone
  knows if physical storage already existed) — roster echoes it up to onboarding unchanged.
  This is the "new DB or not" signal end-to-end.
- Roster upserts its `org_doc_store` row from this response (`doc_store_ref=namespace_ref`,
  `status`, `provisioned_by`), then returns `{ store, created }` to onboarding.
- **Auth:** service-to-service via shared internal key (Secret Manager), same pattern as
  mobius-user's `X-Internal-Key`; can tighten to intra-VPC allowlist later.
- **Provisioner ownership (refined):** the **database agent** (`mobius-db-agent`) is the
  natural owner of the *infrastructure* half — physical create-if-absent of the
  namespace/DB, DDL + migrations of the org-docs chunk schema, connection/secret/pool
  management, and ongoing maintenance (backups, capacity, any BQ replica). **RAG** owns
  what lives *inside* each store (chunk/embedding write path, publish-into-store) and the
  cross-store retrieval union at query time — RAG *defines* the schema, db-agent
  *applies/maintains* it. So `provision` = db-agent creates the namespace + applies RAG's
  schema → returns `{namespace_ref, created}`. Endpoint stays at
  `INSTANT_RAG_PROVISIONER_URL` (name is just the pointer). **ACCEPTED by db-agent
  2026-07-10 — see acceptance block at end of this appendix.**

**Failure semantics.** Provisioner down → roster sets `doc_store_status='failed'`, does NOT
hard-fail the org create (fail-open, flag, retry). `status='provisioning'` while in flight.

**v1 = `shared_namespace`** — one org-docs DB, per-org namespace, `doc_store_ref` = namespace
name. `dedicated_db` per org deferred (HIPAA); descriptor already supports it.

**Contract ownership matrix (four parties):**
| responsibility | roster | database agent | RAG | instant-rag |
|---|---|---|---|---|
| org→store mapping (`org_doc_store`) | **own** | — | — | consume |
| provision trigger endpoint | **own** | — | — | — |
| physical namespace/DB create + maintenance | — | **own** | — | — |
| org-docs chunk schema (DDL) | — | apply/maintain | **define** | — |
| publish-into-store + retrieval union | — | — | **own** | — |
| doc lifecycle · promotion · Vault | — | — | — | **own** |

**Database-agent ACCEPTANCE (2026-07-10) — ownership confirmed, with the following
infra decisions and conditions:**

1. **Accepted scope:** physical create-if-absent, applying/maintaining RAG-defined DDL,
   connection/secret/pool management, backups/capacity, and the (roster-sourced)
   registry replica pattern. The provisioner endpoint is implemented **in
   `mobius-db-agent`** (the port-8008 service already owning governed DB access);
   `INSTANT_RAG_PROVISIONER_URL` stays as the pointer name.
2. **Q2 — v1 kind: `shared_namespace`, agreed.** Implemented as **one new database with
   a per-org Postgres schema**; `namespace_ref` = schema name. Rationale: `dedicated_db`
   per org multiplies migrations and connection slots (both already scarce on the shared
   instance) for no v1 gain; the opaque `namespace_ref` means a later org-level move to
   `dedicated_db` (HIPAA) changes no caller.
3. **Q3 — physical home: new DATABASE `mobius_org_docs` on the existing Cloud SQL
   instance** (`mobius-platform-dev-db`) — NOT a schema inside `mobius_rag`, NOT a new
   instance. Separate DB + disjoint role grants makes contamination structurally
   impossible at the permission layer too: the global-corpus service role gets **zero
   grants** on `mobius_org_docs`, and the org-docs role gets zero grants on `mobius_rag`.
   A new instance isn't justified at dozens of orgs (cost, second proxy, second slot
   budget); the `dedicated_db` HIPAA tier later likely lands on its own instance — decide
   then. Accepted trade-off: shared failure domain + shared connection-slot budget with
   the existing DBs (revisit at scale).
4. **Schema handshake condition (RAG):** the chunk/embedding schema arrives as
   **versioned migration files** (org-docs schema v1..vN) in an agreed location — no
   out-of-band DDL. Provisioner applies them per namespace, records `schema_version`
   per namespace, and returns it in the provision response. Re-provisioning an existing
   namespace applies pending versions (`created:false`, updated `schema_version`) — so
   `provision` doubles as the fleet-wide schema-upgrade mechanism.
5. **Pooling condition:** ONE shared pool to `mobius_org_docs` with per-request
   schema-qualified access — never per-org pools (slot exhaustion is a documented,
   recurring failure mode on this instance).
6. **Data-boundary note:** org-docs **content never replicates to BQ** (private data;
   same contamination principle). Only roster's `org_doc_store` registry rows ride the
   Layer-3 BQ replica pattern.

*(Matrix above is now fully ratified: four parties, no pending cells.)*
