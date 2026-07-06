# Mobius HIPAA Compliance Gap Analysis

**Date:** 2026-06-30
**Scope:** Full codebase review across mobius-chat, mobius-rag, mobius-os, mobius-skills (incl. instant-rag, doc-reader, email, roster/credentialing), mobius-answer-cache, mobius-auth.
**Method:** 5 parallel audits (access control, PHI storage/encryption, audit logging, transmission/secrets, third-party data flows), key findings adversarially verified against source.

---

## Bottom line

Mobius has **real HIPAA foundations** — a `phi_audit_log` table with a PHI detector, BAA-tracking flags, GCP Secret Manager for secrets, Cloud Run TLS, multi-tier rate limiting and fail-closed CORS in chat, non-root containers, and IAM DB auth. This is well ahead of a typical pre-compliance codebase.

But the platform is **not yet defensibly HIPAA-compliant**, for one structural reason: **the safeguards detect and log, but do not enforce or fully cover.** PHI flows to external LLMs and email without de-identification or BAA-gating; audit logging covers only 2 of ~10 PHI-touching paths and can't attribute access to a user or org; uploaded documents are never deleted from object storage; encryption-at-rest is assumed (Google default) rather than verified/controlled.

**Recommendation:** Do not process real client PHI until the Critical items below are closed. Most are days-to-weeks of work, not months.

---

## What's already in good shape (keep / verify)

- **Secrets management** — `mobius-chat/app/secrets_loader.py`: env-override → GCP Secret Manager → default. Service-account JSON keys are gitignored. *(Corrects an earlier "secrets committed" finding — the live keys are in local gitignored `.env`, not in git.)*
- **TLS in transit (external)** — all services on Cloud Run, HTTPS enforced/terminated by the platform.
- **CORS + rate limiting (chat)** — `mobius-chat/app/api/front_door.py`: dev permissive, staging/prod fail-closed; 3-tier rate limiting (per-IP/thread/user). **Note: `mobius-os/backend/server.py` is the opposite — wildcard CORS, no rate limiting.**
- **PHI detector exists and is shared** — `mobius-skills-core/.../skills/phi_audit.py` (SSN, member ID, name, DOB, MRN, 9-digit).
- **BAA tracking scaffold** — `phi_audit_log.py` records `baa_available` per vendor via `CHAT_BAA_*` env vars.
- **Audit table is append-only in practice** — no UPDATE/DELETE against `phi_audit_log` anywhere in code.
- **Containers run non-root**, multi-stage builds, IAM DB auth path for Cloud SQL.

---

## CRITICAL — close before touching real PHI

### C1. PHI sent to external LLMs/email without de-identification or BAA enforcement
- BAA flags are **audit-only** — `_baa_available_for()` is logged *after* the call, never blocks it. Default is `False`, so prod without the env var sends PHI to a vendor and merely records "baa_available=False."
- No de-identification/redaction layer. `action_taken="redacted"` is defined but **never exercised** (`resolve.py` comment: "future policy").
- Affects: chat RAG (`gemini-2.5-flash` via Vertex / Claude), instant-rag embeddings (Vertex), email skill (OpenAI/Vertex), vibe & org-intelligence skills (direct Anthropic).
- **HIPAA:** §164.502(e)/§164.504(e) BAAs, §164.514 de-identification.
- **Fix:** (a) Sign BAAs with Anthropic + Google Cloud (and OpenAI or drop it); (b) make the BAA flag *block* calls when PHI is detected and no BAA is set; (c) build a real redaction pass before any external call.

### C2. Audit logging does not cover most PHI paths, and can't say *who* or *which org*
- Only `resolve` (user msg) and `integrate` (LLM response) write audit rows. **Not** instrumented: RAG document retrieval/download/`vector_search` (`mobius-rag/app/main.py:3110-3300`), doc-reader read/extract/summarize, corpus search, instant-rag upload retrieval, credentialing, roster, email.
- `phi_audit_log` has **no `user_id`** and **no `org_id`/`org_slug`** column. Cannot answer "who accessed this PHI?" or "did org B see org A's data?" — the core HIPAA audit question.
- **HIPAA:** §164.312(b) Audit Controls, §164.308(a)(1)(ii)(D) Activity Review.
- **Fix:** Add `user_id` + `org_slug` to `phi_audit_log`; emit access events from every PHI-touching endpoint (a shared middleware/decorator); build a `/admin/phi-audit-query` interface.

### C3. Uploaded documents (PHI) are never deleted from GCS
- **Verified:** `cleanup_expired_documents` → `_cascade_delete_document` deletes DB rows (`main.py:660-671`) and the vector store (`734-735`), but **never calls `blob.delete()`**. Files with PHI persist in the bucket indefinitely past their TTL.
- Answer cache (`chat_answer_cache`) has **no `expires_at`** and only soft-deletes (`invalidated_at`) — PHI questions/answers live forever, unencrypted.
- **HIPAA:** §164.502(b) minimum necessary, §164.310(d) media disposal.
- **Fix:** Delete the GCS object in the cleanup cron; add hard-delete + TTL to the answer cache.

### C4. Committed dev database credential
- **Verified:** `mobius-chat/.env.example` is git-tracked and contains a real Cloud SQL host (`34.135.72.145`) + password in history.
- **HIPAA:** §164.312(a)(2)(i), §164.308(a)(3).
- **Fix:** Rotate that DB password now; replace the value in `.env.example` with `${...}` placeholders; confirm that instance has no production PHI.

### C5. Encryption at rest is assumed, not controlled
- No CMEK/KMS key specified for Cloud SQL or GCS (relies on Google-managed default). No application/field-level encryption on NPI/name/address columns. Self-hosted **Chroma VM** (`34.170.243.161:8000`) has no documented encryption or auth.
- **HIPAA:** §164.312(a)(2)(iv) Encryption.
- **Fix:** Confirm/enable CMEK on Cloud SQL + GCS; retire the Chroma VM in favor of pgvector on Cloud SQL (already planned) or lock it down (TLS + token + disk encryption); consider field encryption for the most sensitive columns.

---

## HIGH — close during initial client onboarding

| # | Finding | HIPAA | Where |
|---|---------|-------|-------|
| H1 | **No `correlation_id` FK on `phi_audit_log`** → audit rows orphan if a turn is deleted | §164.312(b) integrity | `020_llm_analytics.sql` |
| H2 | **No audit-log retention policy** (rule: 6 yrs / §164.316(b)). No documented SLA, no archive job | §164.316(b)(2) | n/a |
| H3 | **No MFA** anywhere | §164.312(d) | mobius-os/auth |
| H4 | **RBAC not enforced** — `Role` table exists but no endpoint checks it; all users in a tenant see all tenant data | §164.308(a)(4) | mobius-os |
| H5 | **No automatic logoff** — refresh tokens last 7 days, no idle timeout | §164.312(a)(2)(iii) | `auth_service.py` |
| H6 | **Postgres connections don't force TLS** (`sslmode=require` absent) | §164.312(e)(1) | task-manager/db.py, rag/database.py, roster migrations |
| H7 | **`mobius-os/backend` wildcard CORS + no rate limiting** (unlike chat) | §164.312(a)(1) | `mobius-os/backend/server.py` |
| H8 | **Email can send PHI with no audit trail and no recipient controls** (Gmail SMTP) — email is a classic breach vector | §164.312(b), §164.504(e) | mobius-skills/email |
| H9 | **No data-access audit** distinct from PHI-detection (reads of PHI aren't logged as access events) | §164.312(b) | platform-wide |

---

## MEDIUM — hardening

- **M1.** Weak password policy (8 chars, no complexity, no breach check), no account lockout/brute-force protection — `mobius-os/auth.py`.
- **M2.** Tenant isolation is app-layer `WHERE tenant_id=` only; no Postgres Row-Level Security as defense-in-depth.
- **M3.** Unauthenticated `/auth/check-email` (user enumeration) and `/auth/activities` endpoints — `mobius-os`.
- **M4.** Audit writes are fire-and-forget with no retry and no alerting on failure → silent audit gaps.
- **M5.** No DB-level immutability on `phi_audit_log` (trigger to reject UPDATE/DELETE; SELECT-only audit role).
- **M6.** Over-collection: `roster_upload_members.source_row` stores raw CSV; full prompts stored regardless of PHI.
- **M7.** `org_id` missing from `chat_turns` → per-org compliance reporting impossible.
- **M8.** Vertex region not validated (`assert_hosted_config` doesn't reject non-US locations) → data-residency risk if misconfigured.
- **M9.** Chroma SSL is opt-in (`CHROMA_SSL`), defaults off — enforce in hosted envs.

---

## Beyond code — HIPAA is also process (clients will ask for these)

Technical safeguards are necessary but not sufficient. To actually sign healthcare clients you will need:

1. **Signed BAAs** — with you *from* each client (you're their Business Associate), and *from* each subprocessor: Anthropic, Google Cloud, and any other vendor that can see PHI. **Build a subprocessor register** (`SUBPROCESSORS.md`).
2. **Security Risk Assessment (SRA)** — §164.308(a)(1)(ii)(A). A documented, periodic risk analysis. This report is a starting input, not a substitute.
3. **Written policies & procedures** — access management, incident response / breach notification (§164.404), sanction policy, contingency/backup, media disposal.
4. **Workforce training** + access provisioning/de-provisioning records.
5. **Audit-log review cadence** — someone actually reviews `phi_audit_log` on a schedule (§164.308(a)(1)(ii)(D)).

---

## Suggested sequencing

**Phase 0 (this week):** C4 rotate credential; turn on a global "HIPAA mode" that blocks external LLM/email calls on PHI when no BAA is set (C1 enforcement half); wire GCS blob deletion (C3).

**Phase 1 (BAA + audit, ~2-4 wks):** Sign Anthropic + GCP BAAs; add `user_id`/`org_slug`/FK + retention to `phi_audit_log`; instrument the uncovered PHI endpoints (C2, H1, H2); confirm CMEK (C5).

**Phase 2 (access control, ~4-6 wks):** MFA, RBAC enforcement, auto-logoff, lockout, RLS, fix mobius-os CORS/rate-limit (H3-H5, H7, M1-M3).

**Phase 3 (de-id + process):** Real redaction layer (C1 second half), SRA, policies, training, subprocessor register.
