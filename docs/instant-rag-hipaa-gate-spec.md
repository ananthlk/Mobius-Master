# Instant-RAG HIPAA Gate — Implementation Spec

**Owner:** Instant RAG agent · **Status:** design locked, awaiting RAG staged endpoints
**Ananth ruling 2026-07-17:** PHI/HIPAA must be detected BEFORE it is embedded/stored, and
blocked (never ingested) when we are not in HIPAA-allowed mode. See
`project_instant_rag_hipaa_gate` memory.

## Principle: fail-closed. Embed/publish happens ONLY on confirmed-clean.

A blocking gate keyed on `phi_flag==true` alone FAILS OPEN: contextual-only PHI during an
LLM outage returns `phi_flag=false` and would sail through. So we branch on the explicit
`gate` tri-state and ingest ONLY on `gate=="clean"`. `phi` and `indeterminate` both block.

## Flow (staged)

```
1. chat: POST upload → RAG EXTRACT-ONLY  → document_id (NO embedding yet)
2. chat: GET /documents/{id}/pages       → extracted text (deterministic, exists)
3. chat: POST /classify {text}           → { gate, phi_flag, recommended_ceiling, ... }
4. branch on gate:
   • clean         → POST /documents/{id}/publish → embed+publish → CURRENT flow (card, retrieve)
   • phi + mode ON → POST /documents/{id}/publish as PRIVATE → "will be stored in private mode"
   • phi + mode OFF→ DELETE /documents/{id} → hard-stop "HIPAA found — cannot process"
   • indeterminate → DELETE /documents/{id} → hard-stop "couldn't verify — try again shortly"
```
`mode` = `GET /hipaa-mode.allowed`. Today = **false**, so all `phi` → block.

## Contracts

### PHI classifier — LIVE (rev 00011-cfx), verified 2026-07-17
- `GET /hipaa-mode` → `{allowed:false, reason, updated_at, updated_by}`. Default false;
  flipping = gated compliance action (BAA + sign-off), audit-logged, never agent-granted.
- `POST /classify {text, document_id?}` → adds `gate: "clean"|"phi"|"indeterminate"`.
  Verified: PHI→`phi`, clean→`clean`, LLM-down contextual→`indeterminate` (fail-closed).
- min-instances=1 set (warm — no cold-start on the ingest path).

### RAG — TO BUILD (the long pole)
1. **Extract-only upload** — flag/mode (e.g. `?stage=extract` or `publish=false`): extract
   text, return `document_id`, do NOT embed/publish. Text fetchable via existing
   `GET /documents/{id}/pages`.
2. **`POST /documents/{id}/publish`** — embed+publish a previously extract-only doc. Called
   only when `gate=="clean"` (or `phi`+mode ON, as private).
3. **`DELETE /documents/{id}` cascade fix** — currently FK-violates on `embeddable_units`.
   Must cascade-purge embeddings. The gate's block path depends on DELETE working.

### Chat — gate logic (upload handler, app/main.py ~1150–1300, inline attachment path,
before the SSE progress strip opens)
- Insert steps 1–4 above. Branch on `gate` (NOT phi_flag). Publish only on clean/allowed.
- On block: DELETE the extract-only doc, return a hard-stop result to the frontend (no
  progress strip, no card, no retrieval), and soft-discard the catalog row.

## UX states
- New progress stage **"Checking document safety…"** between upload and "Indexing"
  (classify + LLM ~1–3s is now on the critical path).
- Block (phi, mode off): 🔴 "This document contains PHI and can't be processed in the
  current mode. It was not stored." — no card, no retrieval.
- Block (indeterminate): 🟠 "We couldn't verify this document's safety right now. Please
  try again shortly. It was not stored."
- phi + mode ON: "PHI found — stored privately (not shared to the corpus)."
- clean: current flow (answer + card).

## Purge semantics
On any block, the extract-only doc is DELETEd (no embeddings exist yet in the staged flow,
so no FK issue on the normal path). PHI agent audit keeps only SHA-256 + masked evidence +
gate — zero raw text, purge-compatible, and a useful "blocked a PHI doc" record.

## Verification matrix (revised — supersedes the retrieval/duplicate PHI test)
| Case | Input | Mode | Expect |
|------|-------|------|--------|
| 1 | clean doc | off | publish; answer + safe-to-share card |
| 2 | PHI doc | off | BLOCK; hard-stop msg; NOT stored; NO card; NOT retrievable |
| 3 | contextual-PHI + LLM forced-down | off | `indeterminate` → BLOCK + try-again |
| 4 | PHI doc | on (test flip) | publish PRIVATE; "stored privately" |
| 5 | clean doc, >12s large | off | publish; progress incl. "Checking document safety…" |
Verify each: chat behavior + classifier logs (`gate`) + RAG has NO embeddings for blocked docs.

## HIPAA analysis audit + diagnostics (Ananth 2026-07-17)

EVERY upload transaction — regardless of outcome (clean / phi / indeterminate) — produces a
HIPAA-analysis record that is (a) stored durably in DB and (b) shown in the DIAGNOSTICS
section of the chat summary bubble. Every doc that touches the platform has an auditable
"was it screened, what was found, what did we do" trail.

**Record fields (masked — never raw PHI):**
`transaction_id/document_id, user_id, org, ts, gate (clean|phi|indeterminate), phi_flag,
ceiling, hipaa_mode_allowed (at decision time), action_taken (published | published_private
| blocked_phi | blocked_indeterminate), evidence_categories[] (e.g. ["SSN","DOB","MRN"] —
masked), classifier_version, layers_run[], confidence, reason.`

**Diagnostics categories — use PHI agent's fields (they own the vocabulary):**
`identifiers_found` (canonical, deduped, machine) for `evidence_categories[]`; `identifier_labels`
(human, e.g. ["SSN","Date of Birth","MRN"]) for the rendered "SSN, DOB, MRN detected" — chat
must NOT hardcode a category→label map (it would drift from the classifier). Categories only,
never values.

**content_sha256 recipe — FROZEN (PHI agent contract):**
`sha256( text.encode("utf-8") ).hexdigest()` where `text` = the EXACT, FULL, untruncated
decoded string chat sends in the /classify `{text}` body. NO normalization (no strip, collapse,
lowercase, NFC). Lowercase hex (64 chars), not base64. Hash the decoded string, not raw JSON
wire bytes. Test vectors: `""`→e3b0c442…b855; `"Patient John Smith DOB 01/02/1990"`→6ca5ff5f…39e1.
This makes chat's `content_sha256` == PHI agent's `phi_classification_audit.text_sha256` 1:1
(provable same-doc, zero raw text in either trail). Correlation grain: chat's row =
authoritative per-transaction decision; PHI audit = per-call operational record.

**Storage — LIVE (DB agent, mobius_chat migration 042):** `compliance.hipaa_analysis_log`.
Append-only enforced STRUCTURALLY (BEFORE trigger blocks UPDATE/DELETE + REVOKE from PUBLIC);
`document_id` is bare TEXT with NO FK, so document purge can never cascade the audit row.
Fields: id uuid PK, ts, transaction_id NOT NULL, document_id (null=blocked pre-registration),
content_sha256, user_id, org_slug, gate, phi_flag, ceiling, hipaa_mode_allowed, action_taken,
evidence_categories text[], classifier_version, layers_run text[], confidence, reason.
**Binding write-path contract (chat):** (1) audit INSERT in the SAME transaction as the gate
decision; a FAILED audit write FAILS THE GATE CLOSED (can't prove we screened → don't ingest).
(2) client-generated uuid4 id + ON CONFLICT (id) DO NOTHING (retry-idempotent). (3) stamp
`content_sha256` = the SAME hash the PHI agent uses in their audit, so the two trails correlate
without sharing content. PHI agent already keeps their own SHA-256/masked audit; this is the
platform-side compliance record AND the diagnostics source.

**Diagnostics display — UX DESIGN DONE (4 states, mockup delivered).** chat wires the payload.
- Clean: compact single line "✓ No PHI detected — added to session" (low visual weight).
- PHI blocked (mode OFF): NO card/retrieval; bubble leads red shield-x + title + next action,
  then full Diagnostics (gate badge, masked evidence pills, "HIPAA mode: OFF", reason, doc, txn id).
- Indeterminate (mode OFF): same as blocked but AMBER, "LLM timeout — fail-closed", NO evidence
  pills (we don't know contents).
- PHI + mode ON: answer renders; violet vault banner "stored in your private vault, not shared".
- Bubble border shifts to semantic color (danger/warning/pro); DIAGNOSTICS label = uppercase
  audit chrome; evidence as pills (masked feels intentional); txn id in mono for compliance query.
- Frontend wire contract (from chat): `{ gate, phi_flag, evidence_categories[], hipaa_mode_allowed,
  action_taken, reason, transaction_id, document_name }`.

**Category field split (reconcile):** the AUDIT row `hipaa_analysis_log.evidence_categories` stores
`identifiers_found` (machine/canonical, best for compliance query). The DIAGNOSTICS pills render
`identifier_labels` (human, e.g. "SSN","Date of Birth","MRN"). chat has both from /classify → route
machine→audit, human→display. (UX mockup abbreviated "DOB"; live labels are PHI-agent-owned strings —
render as-is to avoid drift, or abbreviate client-side deliberately.)

**Owners:** DB agent = `hipaa_analysis_log` schema + write path. PHI agent = emit the
analysis fields (mostly done; confirm `evidence_categories` masked + `gate` in payload). UX
= DIAGNOSTICS section design. Chat = write the record on every gate decision + include it in
the bubble's diagnostics payload. Instant RAG = contract + DoD + integration.

## Sequencing
RAG staged endpoints + DELETE cascade (long pole) → chat implements gate (1 pass) +
writes hipaa_analysis_log + diagnostics payload → Instant RAG integrates + runs the matrix.
PHI side done; DB agent (table) + UX (diagnostics layout) run in parallel with RAG's work.
