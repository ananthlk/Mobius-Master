# PHI gate & override — the build contract

**Status:** BUILD (Ananth green-lit 2026-09-10) · **Rules owner: PHI classifier (mobius-skills)** · Enforcers: Chat (admit) · RAG (persist) · Extension (UX) · Org (BAA) · Platform (env/role)
**Rationale + full history:** `DECISION_option_a.md`. This page is the contract to build against — the rules, the emitted fields, and each seat's enforcement. It is deliberately short.

> **The principle Ananth set:** **PHI owns these rules.** The classifier emits ONE authoritative verdict; every other seat READS it server-side and enforces — nobody re-derives the policy. A decision is a contract, not a UI. If a rule needs to change, it changes here first, in the PHI seat, and the enforcers follow.

---

## 1 · What PHI emits (the contract every enforcer reads)

Per-document verdict from `/classify` (server-side, authoritative — never client-asserted):

| field | values | meaning |
|---|---|---|
| `gate` | `clean` \| `phi` \| `indeterminate` | existing verdict |
| `attestation_tier` | `light` \| `heavy_attest` \| `hard_floor` | = (confidence) × (is-real-clinical-record). The override authority. **Requires the LLM contextual pass — never skipped for candidates.** |
| `persist_allowed` | bool | the gate's *recommendation*: `(gate==clean) OR (gate==phi AND hipaa_mode_allowed)`. NOT the final word on an override lane (see §3). |
| `identifier_labels` | \[…] | what flagged (may be masked) |
| `classifier_version` | string | stamped into every override marker |

`hipaa_mode_allowed` (org BAA / Key-1) is an **Org**-owned fact the verdict reads; it is not PHI's to set.

`attestation_tier` decode:
- `light` — low-confidence, name-only (Healthy-Start class).
- `heavy_attest` — high-confidence but reads as example/synthetic/non-clinical (a fake SSN in a blank form).
- `hard_floor` — reads as a **real clinical patient record** (named person + own DOB/MRN + clinical context; a *filled* chart). The compliance floor.

---

## 2 · The three override lanes (the rules PHI owns)

| lane | claim | clears | ingests as | gate |
|---|---|---|---|---|
| **1 · False-positive** | "no PHI — it's an example/synthetic" | `light`, `heavy_attest` — **NOT `hard_floor`** | **clean** (no PHI tag) | human review + attestation + **audit** (friction scales: light confirm → heavy attest) |
| **2 · PHI admit** | "there IS PHI, admit it" | real PHI | **PHI-tagged** | **org BAA** (`hipaa_mode_allowed`). No BAA → **hard stop** |
| **3 · Dev/build** | "non-prod env, authorized engineer" | **everything incl `hard_floor`** | into **isolated dev corpus** only | **server-side** env + engineer role. Impossible in prod. |

- Override 1 never clears `hard_floor` → a real chart routes to Override 2 (BAA) or stays blocked.
- Override 3 is a claim about **environment + actor**, not PHI; it still RUNS the classifier (emits the verdict for testing) and proceeds regardless.

---

## 3 · Per-seat enforcement (how each reads the one authority)

- **PHI classifier — OWNER.** Emits the verdict above; runs the LLM contextual pass (never skipped for candidates — it drives *both* the friction and the `hard_floor`, so a skip collapses `heavy_attest`/`hard_floor`). Owns every definition here. **Closes the one open policy decision (§4).**
- **Chat — admit.** Reads `attestation_tier`/`gate` **server-side** as the authority; client sends only the user's *intent*. Computes the **effective persist decision** at admit = `persist_allowed OR validated_override` (because a human override cannot exist at classify time). Enforces the §2 table: Override 1 clears light/heavy_attest→`published` (NOT `published_private` — no PHI to restrict, intended asymmetry, state in code); Override 2 needs org BAA; Override 3 needs server-side env+role.
- **RAG — persist (scribe).** Keys purge/dedup on the **effective** decision. Bounded **HOLD** for an override-pending doc (a named third state: stored/unpublished/not-adjudicated, unreachable by retrieval, "not phi_blocked" ≠ "admitted"); **release-not-resubmit** (unblock the existing row, no re-upload). Persists markers verbatim, computes none: `phi_override{…, classifier_version}` and `ingest_override{kind, environment stamped-at-ingest, forced_by, classifier_version, …}`. Rule: **purge immediate UNLESS `attestation_tier` is overridable and within the hold, then deferred to hold expiry or the user's decision.**
- **Extension — UX.** Renders the tier: `light`→light "not patient data" confirm; `heavy_attest`→explicit "I confirm synthetic/example" + audit (+2nd confirm); `hard_floor`→no Override 1, offer Override 2 (BAA) or stays blocked. Dev-override affordance shown **only in dev**. Sends the user's **intent** only (never a client-asserted tier). Writes the attestation log keyed to RAG's markers by `task_id`+doc-hash.
- **Org — BAA.** Owns `hipaa_mode_allowed` / org BAA state that Override 2 gates on. Real PHI + no BAA → suppress.
- **Platform — env/role.** Defines the "build-level engineer authority" (deploy role / env flag / allow-listed identity) that Override 3 reads server-side.

**The audit log is a compliance REQUIREMENT** (not provenance): the override shifts responsibility to a human; the audit makes it real and traceable. No override ships without it.

---

## 4 · The one open policy decision — PHI to CLOSE (as rules owner)

Override 3 proceeds past `hard_floor`, so **genuine PHI can land in dev storage** (isolation protects prod *retrieval*, not whether dev is an appropriate place to *hold* a real chart). PHI decides, as rules owner:
- (i) **synthetic-only by policy**, enforced by the `ingest_override` audit marker + dev access controls; or
- (ii) real PHI in dev acceptable under a stated control; or
- (iii) a residual guard so Override 3 can't hold a *real* chart even in dev.

_(Extension's read: (i) is the normal engineering answer — build with synthetic data, marker makes any violation traceable — but it must be a STATED condition, not "it's only dev." PHI's call.)_

---

## 5 · Build sequencing (one coupled thread, not independent ships)

The override is **coupled to block-not-stored** and ships with it:
1. **PHI:** emit `attestation_tier` (LLM-verified, never skipped); close §4.
2. **RAG + Chat:** the storage spine — bounded HOLD, release/unblock endpoint, effective-persist-at-admit, `phi_override`/`ingest_override` markers with `environment`. (This is the block-not-stored fix; the override rides it.)
3. **Extension:** the three-tier card + dev-only affordance + attestation log, on the release endpoint.
4. **Org:** BAA state for Override 2.

Isolation is **verified** (dev/staging/prod = separate GCP projects/DBs/buckets; prod holds no dev connection string). The `environment`-stamped marker adds the second layer + makes a retrieval guard possible later without a migration.
