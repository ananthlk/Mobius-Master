# Mobius PHI / HIPAA Handling Policy

**Owner:** PHI Classifier agent (the platform's PHI/HIPAA authority)
**Status:** v1 — 2026-07-20. Living document; the PHI agent maintains it and broadcasts material changes.
**Applies to:** every agent and service that touches user text, documents, queries, messages, logs, or storage.

This is the single source of truth for how Mobius handles Protected Health
Information. If a design decision touches PHI and isn't covered here, **route it
to the PHI agent** before building.

---

## 1. Principle

- **PHI** = the 18 HIPAA Safe-Harbor identifiers (names, DOB, SSN, MRN,
  member/beneficiary IDs, dates of service, addresses, phone/email/fax, URLs,
  IPs, device/vehicle IDs, license/cert numbers, ages > 89, biometrics) **plus
  contextual quasi-identifiers** (e.g. "34-yo veteran, only one in the cohort").
- **Recall over precision.** When uncertain, treat text as PHI. A missed PHI is
  a HIPAA breach; a false positive is a shrug.
- **Fail closed.** If we cannot positively confirm text is clean (detector down,
  verdict indeterminate), we do NOT proceed as if it were clean.
- **Every surface is a PHI surface** — not just the database. Logs, traces,
  telemetry, cached responses, external API calls, and error payloads can all
  leak PHI and are all in scope.

---

## 2. HIPAA-allowed mode vs. HIPAA-NOT-allowed mode  ⭐ core policy

There is ONE global platform switch that governs whether PHI may be stored at
all. Check it at `GET {phi-url}/hipaa-mode → {allowed, reason, updated_at, updated_by}`.

### HIPAA-NOT-allowed (the DEFAULT and current platform state — `allowed:false`)
The platform is **not** cleared to store PHI. Therefore, when PHI is detected:
- **Ingestion (documents / org-docs):** TERMINATE. No ingest, no embed, no
  store, no retrieve. Purge the extracted text. Surface "HIPAA found — cannot
  process in current mode."
- **Chat messages (pre-farm gate):** BLOCK the turn. The user must edit the PHI
  out or explicitly override. The thread cannot move forward with PHI unresolved.
- **Traces / diagnostics:** persist only PHI-SCRUBBED content (masked or
  suppressed); never raw PHI.

### HIPAA-allowed (`allowed:true`)
The platform holds a signed BAA and is cleared to store PHI. When PHI is
detected:
- **Ingestion:** ingest but store **PRIVATE-only** ("will be stored in private
  mode"). Never auto-promote PHI to org/public.
- Everything else (scrubbing traces, blocking public exposure) still applies —
  PHI never goes to broadly-readable surfaces even in allowed mode
  (minimum-necessary).

### Who owns the switch, and how it flips
- The **PHI agent owns the MECHANISM** (the flag + its default `false`).
- The PHI agent does **NOT** own the AUTHORITY to flip it. Flipping to `true` is
  a **gated compliance action**: it requires a **signed BAA + Ananth/legal
  sign-off**, and is **audit-logged**.
- It is **never** granted by an agent, never by client input, and **never via a
  runtime endpoint** (no "test override" that flips PHI-storage on). Default
  stays `false` until PHI storage is genuinely authorized.

---

## 3. The PHI classifier — the shared primitive

One stateless service (`mobius-skills/phi-classifier`) is the platform's PHI
primitive. Do not build your own PHI detection — call it.

| Endpoint | Purpose |
|----------|---------|
| `POST /classify` | Document ingestion gate — full verdict + masked evidence |
| `POST /message-check` | Synchronous pre-farm gate on a chat message (regex+NER fast path) |
| `POST /redact` | PHI-scrubbing primitive (returns masked text or suppresses) |
| `GET /hipaa-mode` | The global allowed/not-allowed switch (§2) |

- **Detection layers:** regex (structured identifiers) + NER (Presidio **unioned
  with** a heuristic name pass — Presidio's name recall is context-inconsistent)
  + an LLM context pass for quasi-identifiers.
- **The LLM never leaves the network.** It routes through mobius-chat's bandit on
  a HIPAA-locked stage (Vertex/BAA models only). No third-party API ever sees PHI.
- **Evidence is always MASKED** (`***-**-****`, `J••• D••`). The service never
  returns or logs a raw PHI value.
- **Verdict is a fail-closed tri-state:** `clean` (safe), `phi` (block/gate),
  `indeterminate` (couldn't confirm → treat as unsafe).

---

## 4. PHI-in-logs standard  ⭐ (now enforced fleet-wide)

**Never log raw user-query / message / document text.** Log **categories +
counts + hashes** only — e.g. `phi_categories=['ssn','name']`, `token_count=12`,
`content_sha256=…`. Never `query=%r`, never `content[:80]`, never a token array.

- Cloud Logging is a PHI surface: broadly readable, retained, indexed.
- A regex scrub filter is **defense-in-depth only, not sufficient** — regex
  catches SSN/phone/email but **NOT names**. The real control is
  **don't-log-raw-text at the source.**
- Error payloads: log the error type/status, not the raw request body.

This standard is live: PHI-classifier, RAG, and Chat swept clean 2026-07-20.

### Acceptance criterion — WHOLE-BLOB leak check (not just named fields)

Scrubbing the fields you *named* is not sufficient. **Derived fields re-carry
source PHI** — a `semantic_core`, a token list, an embedding-input column, or a
telemetry summary built from the raw query will contain the PHI even after
`raw_query`/`answer` are scrubbed. (Real case, 2026-07-20: `raw_query` and
`llm_answer` were scrubbed, but `semantic_core` held the verbatim query and
`untagged_meaningful_tokens` held the SSN/MRN as tokens.)

**Acceptance gate for any table or log storing user-derived text:** grep the
ENTIRE stored blob (every column, the whole row/log line) for banned patterns
(SSN/phone/email/date/9-digit + a name spot-check) and treat any hit as a
FAIL — don't just confirm the named fields were scrubbed. Gate new
user-derived-text surfaces this way rather than re-discovering the leak
per-table.

---

## 5. Identifier risk tiering (for false-positive overrides)

When an authorized user attests "not patient PHI" to override a false positive,
the override is one-click **only when ALL detected categories are low-risk**.

- **HIGH-risk** (no easy override — compliance path): `ssn`,
  `medical_record_number`, `health_plan_beneficiary_number`, `account_number`,
  `date_of_birth`, `date_of_service`, `certificate_or_license_number`,
  `device_identifier`, `vehicle_identifier`, `contextual_identifier` (+ diagnosis,
  biometric if present — LLM-only, not structured).
- **LOW-risk** (attestation-overridable): `name` (highest-risk of the low set —
  never overridable alongside any high-risk category), `address`, `zip_code`,
  `phone`, `fax`, `email`, `url`, `ip_address`, `age_over_89`, generic `date`.

Enforce against the classifier's **canonical** category names (server-side).

---

## 6. Who works with the PHI agent, and how

| Agent / service | Their PHI responsibility | How they integrate |
|---|---|---|
| **Chat** | Pre-farm message gate | Call `/message-check` before farming. The **backend re-run is the authoritative gate** (client checks are bypassable) and must **fail CLOSED** on check-error. Write the envelope to `compliance.hipaa_message_check_log`. |
| **Instant RAG** | Upload ingestion gate | Classify extracted text before embed/store; branch on `gate`; gate promotion by ceiling; enforce §2 termination in not-allowed mode. |
| **RAG** | Org-docs ingestion + trace scrubbing | Ingestion gate for org-docs; scrub `raw_query` + `llm_answer` via `/redact` before persisting traces. |
| **DB agent** | Compliance persistence | Owns `compliance.hipaa_analysis_log` (append-only, ~6yr) + `hipaa_message_check_log`; schema, constraints, retention. |
| **Eval** | Trace-store + verification | Trace-store compliance rulings consume PHI-agent policy; verifies scrubbed rows. |
| **ORG** | False-positive override | Attestation UX enforces the §5 risk tiering server-side. |
| **Everyone** | The logging standard (§4) | Never log raw PHI. Route new PHI surfaces to the PHI agent for a gate contract first. |

**How to reach the PHI agent:** cross-session message to the PHI Classifier
agent. Before building any new surface that handles user text, **get the verdict
contract from the PHI agent first** — don't reinvent detection or gating.

---

## 7. Recall-over-precision consequences (expected, not bugs)

- The classifier **over-flags** business/provider contact info (names, phones,
  emails in public manuals) as PHI. This is by design (recall first). The
  **human attestation override (§5)** is the relief valve, not a looser detector.
- `/redact` **suppresses** (returns "[unavailable]") on full patient-identity
  combos and quasi-identifiers it can't mask cleanly — safe by design; single
  identifiers still mask. A suppressed field is a shrug, a leaked one is a breach.

---

## 8. Change control

The PHI agent maintains this policy, versions it, and broadcasts material
changes (new surfaces, mode-semantics changes, tiering changes, standard
changes) via the Broadcaster so it stays a fleet norm.
