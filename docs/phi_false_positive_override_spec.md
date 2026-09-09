# PHI Gate — False-Positive Override (attestation model)

Status: DRAFT for circulation · Owner: Org/Providr agent (serene-mendeleev) · 2026-07-19

## Problem
The pre-embed PHI gate (`mobius-rag /upload` Path B → `phi-classifier@0.1.0`,
recall-over-precision) hard-blocks docs when `gate ∈ {phi, indeterminate}` and the
org isn't HIPAA-configured. Public payer/provider manuals are the predictable
false-positive class: they trip `name/address/phone/email/url/fax/zip` (business
contact info), never the patient-specific identifiers. Real example —
`abhfl_provider_resource_guide.pdf` for `lifestream-behavioral-center`, txn
`25a8ae93`, conf 0.97, categories `{address,email,name,phone,url}`. No real PHI.

## What this IS and ISN'T
- **IS (build):** a *false-positive attestation*. An authorized human asserts
  "this document does NOT contain patient PHI." On attestation the doc is
  re-ingested down the **normal clean-doc path** (chunk → embed → index into the
  standard store). Same outcome as a doc the classifier had scored clean.
- **IS NOT (refuse):** a "store real PHI in a non-HIPAA store anyway" bypass.
  Storing genuine PHI in non-compliant storage is the exact thing the gate
  prevents; logging does not make it acceptable. The override never enables PHI
  storage — it asserts the doc is *not* PHI.

## Guardrail — risk tiering
Override eligibility depends on **what was detected** (`evidence_categories`):
- **Low-risk (overridable):** name, address, phone, email, url, fax, zip_code,
  date, age — the "every business doc has these" set.
- **High-risk (NOT one-click overridable):** ssn, mrn / medical_record_number,
  member_id, account_number, dob, health_plan_beneficiary_number, diagnosis,
  certificate/license, biometric, device_id.
  → Attesting "not PHI" against an MRN/SSN hit is a red flag. For any high-risk
  category present: hide the one-click override; show a heavier "contact
  compliance" path (out of scope for v1 — just block the easy path).
- Canonical high-risk list to be **confirmed by the PHI-classifier agent** (they
  own the vocabulary).

## Authorization — profile capability (User agent owns)
- Not any member, and NOT a hardcoded role. Gated by a real, revocable
  **`override_authority`** capability on the user's **Mobius-user profile**
  (owned by the User Manager agent). Grantable/revocable per user; auditable.
- Providr resolves the **acting user's** profile → checks `override_authority`
  → shows/hides the affordance. RAG **re-fetches the profile capability
  server-side** before honoring the override (client gating not trusted).
- Override is a named, accountable action: capture `overridden_by` (the resolved
  user id), timestamp, and a **required** free-text justification.
- **Defense in depth:** capability + risk-tier both re-validated server-side.

### Identity dependency (blocks the above)
Providr currently hardcodes `uploaded_by='admin'` (`documents.html:373`) — no
real acting-user identity. To resolve a real profile we need the platform's
acting-user id reaching the skill (platform JWT / `X-User` header via SSO). Until
that's wired, the capability check has no real subject. Confirm what identity the
platform passes to the Providr skill.

## Audit (append-only)
Reuse `compliance.hipaa_analysis_log` (RAG DB). The original block row stays
**immutable**; the override is its **own new event row**:
- new `transaction_id`; `action_taken = 'override_ingested'`
- `overridden_from_txn` → original block txn
- `overridden_by`, `override_justification`
- gate/categories/confidence still recorded (from re-classify) for the record
Surfaces in the pending compliance/telemetry log on the Documents page.

## Flow
1. Upload → gate → `blocked_phi` (409, `transaction_id`). Blocked receipt already
   shown (built).
2. If detected categories are **all low-risk** AND viewer is admin → show
   "Override — attest not PHI" on the blocked receipt. Else no override affordance.
3. Modal: shows detected categories; required attestation checkbox ("I attest this
   document does not contain patient PHI"); required justification; confirm.
4. Re-submit the **file bytes** with `override_transaction_id` + `attestation` +
   `justification`. (Blocked bytes are never persisted, so override = re-send. If
   the page still holds the File object, no re-pick needed; after reload, re-pick.)
5. RAG: still classifies (for the record), but with a valid override on a low-risk
   tier + authorized role → `action_taken='override_ingested'`, ingest via clean
   path, write override audit row linked to the original txn. High-risk or
   unauthorized → reject 403 server-side.

## Per-agent pieces
- **Org/Providr (me):** blocked-receipt override affordance (admin + low-risk
  only), attestation modal, proxy endpoint, telemetry surfacing, e2e verify.
  Owns DoD + integration.
- **RAG agent:** `/upload` override branch — accept `override_transaction_id` +
  attestation + justification; server-side role + risk-tier re-check; clean-path
  ingest; override audit-row write.
- **DB agent:** `compliance.hipaa_analysis_log` — extend `action_taken` CHECK to
  include `override_ingested`; add `overridden_from_txn`, `overridden_by`,
  `override_justification`. Migration on the RAG DB.
- **User Manager agent:** add `override_authority` capability to the Mobius-user
  profile (schema + set/revoke + expose in profile-read API so Providr/RAG can
  check it). **Blocking dependency.**
- **PHI-classifier agent:** confirm canonical high-risk identifier list; (separate,
  the real fix) precision so provider manuals stop tripping business-contact PHI.
- **HIPAA agent:** policy nod — attestation-as-not-PHI ingests as clean and does
  NOT require global HIPAA-allowed mode; confirm audit fields meet requirements.
- **Platform/SSO:** deliver the acting-user identity to the Providr skill (see
  Identity dependency).

## DoD
- [ ] Blocked receipt shows override only for admin + all-low-risk categories.
- [ ] Modal enforces attestation checkbox + non-empty justification.
- [ ] Endpoint re-ingests via clean path; immutable override row links to original.
- [ ] Server-side re-validation of role + tier (client gating not trusted).
- [ ] High-risk categories → override disabled, guidance shown.
- [ ] Override events visible in compliance/telemetry log.
- [ ] E2E: re-run lifestream provider guide → override → indexed; audit row present.

## Open dependency
- **Admin identity source in Providr** — need the role/identity claim the app
  already has for `uploaded_by`; confirm how "org admin" is determined. Blocks the
  authorization piece.
