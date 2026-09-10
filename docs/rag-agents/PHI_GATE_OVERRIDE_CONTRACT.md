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

## 4 · CLOSED — PHI ruling (rules owner, 2026-09-10): **(i), synthetic-only by policy, as a STATED CONDITION**

**Decision: Override 3 is for SYNTHETIC / test / example data ONLY. Real PHI in dev is a stated policy VIOLATION, not a sanctioned use.** Enforced by the `ingest_override` audit marker (environment-stamped) carrying an explicit engineer attestation ("synthetic/test data, no real patient"), plus dev access controls. NOT (ii) — real PHI in dev is never a normal, sanctioned use.

**Why not (iii) — the structural guard — even though I held exactly that floor for Override 1:** the classifier CANNOT structurally distinguish a *realistic synthetic* clinical chart from a real one — a fake "John Doe, DOB 01/01/80, MRN 12345, dx: hypertension" reads as `hard_floor`, same as a real chart. That's the whole reason the tier exists. So a structural guard on `hard_floor` in dev would block the *legitimate* case (testing the pipeline with realistic synthetic clinical data), which is Override 3's entire purpose. A guard that blocks the intended use to stop the unintended one, when it can't tell them apart, is self-defeating. The only thing that distinguishes synthetic-clinical from real-clinical is the **human attestation + the environment** — so that's what the control keys on.

**Why this stays CONSISTENT with the Override-1 hard floor (not a reversal):** the floor exists where the *harm* is — Override 1 admits into the **prod retrieval corpus** (a real chart served to users on a misattestation; detective audit too late; high harm). Override 3 admits into an **isolated dev corpus** — verified separate GCP project/DB/bucket, prod holds no dev connection string — so a wrongly-attested real chart **cannot reach prod retrieval**. The harm is contained by isolation; the residual (a real chart at rest in dev) is bounded by isolation + policy + an **attributed** audit marker (who attested what, environment-stamped) + dev access controls. So: preventive structural floor where it matters (prod retrieval, Override 1); layered proportionate controls where the harm is isolated (dev, Override 3). Same principle, applied to the actual harm surface.

**Conditions of Override 3 (the stated policy):**
1. **Synthetic/test data only.** The engineer attests "no real patient data." Using it on real PHI is a policy violation, not a sanctioned path.
2. **Attributed, environment-stamped audit is mandatory** — the `ingest_override` marker records `forced_by` (engineer identity), `environment`, the attestation, `classifier_version`, doc-hash. A violation is traceable to who committed it.
3. **Dev access controls apply** — who can read the dev corpus is limited (Platform's env/role authority).
4. **Genuine real-PHI-in-dev needs do NOT use this override** — they go through a deliberate controlled path (de-identification, or a BAA-covered controlled-data process). Override 3 is not that door.
5. **Forward hook:** the `environment`-stamped marker already makes a **retrieval guard** addable later without a migration (§5) — if we ever want a structural "dev-marked docs never served in prod retrieval" belt, the data supports it. Recommended as a fast-follow, not a blocker.

That closes §4. The floor I hold in prod (Override 1 can't clear `hard_floor`) is unchanged; Override 3's isolation is what lets the dev override proceed under policy+audit instead of a structural guard that can't work.

---

## 5 · Build sequencing (one coupled thread, not independent ships)

The override is **coupled to block-not-stored** and ships with it:
1. **PHI:** emit `attestation_tier` (LLM-verified, never skipped); close §4.
2. **RAG + Chat:** the storage spine — bounded HOLD, release/unblock endpoint, effective-persist-at-admit, `phi_override`/`ingest_override` markers with `environment`. (This is the block-not-stored fix; the override rides it.)
3. **Extension:** the three-tier card + dev-only affordance + attestation log, on the release endpoint.
4. **Org:** BAA state for Override 2.

Isolation is **verified** (dev/staging/prod = separate GCP projects/DBs/buckets; prod holds no dev connection string). The `environment`-stamped marker adds the second layer + makes a retrieval guard possible later without a migration.

---

## Chat seat — §3 admit row confirmed, with three flags

**The §3 Chat row matches how I would build it.** Server-side authority, effective
persist at admit, `published` not `published_private` with the asymmetry stated
in code, Override 1 never clearing `hard_floor`. No changes requested to that row.

Three things I would want settled before the build, all inside my enforcement.

### 1 · Override 1's justification changed and its outcome did not

As reviewed, Override 1's claim was *"the detector is WRONG — no patient data
here"*, and "no PHI to govern, therefore no BAA" held **by construction**:
`overridable` certified name/address-only with **zero structured identifiers**.

§2 now has Override 1 clearing **`light` AND `heavy_attest`**, on the claim *"no
PHI — it's an example/synthetic"*. If `heavy_attest` can carry structured
identifiers, the no-BAA justification stops being structural and becomes **the
user's word** — while the outcome stays identical: `published`, clean, no PHI
tag, no BAA.

Both tiers reaching the same outcome is defensible. Reaching it on two different
kinds of guarantee, without that being visible in the emitted verdict, is the
part I would not want to discover later. **Request:** the persisted marker
records the tier that was cleared, so "admitted because provably not PHI" and
"admitted because a human said it was synthetic" are distinguishable forever
after. Same rule as `blocked_indeterminate` vs `blocked_publish_failed` — one
value must not stand for two situations.

### 2 · For `heavy_attest` the audit IS the control, so admit must fail closed on it

A synthetic-data claim is **unfalsifiable at admit time**. Nothing can check it;
only the audit makes it attributable afterwards. The contract already says the
audit is a compliance requirement rather than provenance — which means, for this
tier, **the audit is the only control that exists.**

So the ordering matters and is not stated: **if the audit write fails, the admit
must fail.** Not "log and continue". A failure between admit and audit leaves an
unattributable admission of possibly-real PHI, which is the exact state the
audit exists to make impossible. I will build it that way unless PHI rules
otherwise — flagging because it is a rule, not an implementation detail.

### 3 · Override 3 reads the environment — which way does it fail?

"Impossible in prod" rests on a server-side env + role check. We closed a
fail-open of exactly this shape hours ago: `PHI_CLASSIFIER_URL` unset meant the
gate was skipped and the document published unscreened.

An env check answering "am I in dev?" must **fail closed — absent, empty or
unrecognised means PROD**, and Override 3 is unavailable. Not "not dev, so
presumably dev". Cheap to state now; expensive to discover from a misconfigured
deploy that quietly enabled a `hard_floor` bypass.

**Otherwise confirmed. Not starting the build until Ananth clears it directly —
this is PHI enforcement and it is coupled to the block-not-stored spine, so it
is his call and not a relay's.**

---

## RAG seat — §3 persist row confirmed, with five things to change or state

**The §3 RAG row is my build.** HOLD as a named third state, release-not-resubmit,
markers persisted verbatim and computed by nobody here, purge keyed on the
effective decision — all of it matches what I spec'd and I am not asking to
change the shape. Five things below are gaps between the row as written and what
the deployed code actually does. The first is load-bearing; the rest are
statements the contract currently leaves to the implementer.

### 1 · "Unreachable by retrieval" is true today only because nothing publishes it — verified, and it needs a guard

I checked rather than assumed. Retrieval reads **only** `rag_published_embeddings`
(`corpus_search.py`, every query; no join to `documents`). `publish.py:302` copies
`doc.status` into the published row as `document_status`, and the only consumer of
that column is `synthesis.py:385`, which uses it to label `"planned"`. **There is
no WHERE clause on it anywhere.**

So HOLD's unreachability rests entirely on "a held document is never published,"
and **`publish.py` has no status guard** — it will publish whatever it is handed.
That is fine while `/upload` is the only path, and not fine given the
Republishing agent runs corpus-wide coherence sweeps that call publish on
documents it did not ingest. A held row that a sweep picks up lands in the index,
and nothing downstream would catch it.

**Change:** an explicit refusal in `publish.py` for `status == "hold"` (and
`phi_blocked`), at the top of the publish call, not in its callers. One author,
many callers — the same rule the product_line mapping is under. Without it, HOLD
is `review_status` again: a label in a column that no query reads.

### 2 · The effective decision has no transport

Chat computes the effective persist decision at admit. RAG's only inbound channel
for it today is `PATCH /documents/{id}` with `status: "phi_blocked"`
(`main.py:6964`) — a status setter that carries no tier, no `classifier_version`,
no override record. If purge/dedup keys on the effective decision, that PATCH
becomes the transport for a compliance decision with no schema behind it.

**Change:** the effective decision arrives on the **same endpoint as
release/unblock**, carrying the verdict fields and the override, and the status is
*derived* from it here rather than asserted by the caller. Same anti-spoof shape
as `_upload_classify_caller` — the caller states intent and evidence; this seat
derives the state. I will build it that way; flagging because §3 reads as though
the decision simply arrives.

### 3 · "Purge" is not specified as bytes-only or bytes-plus-row, and it matters in both directions

The dedup key (`file_hash`) lives **on the document row**. So:

- **Purge the row too** → the "previously blocked, cannot be ingested" 409
  (`main.py:8283`) disappears with it. The same real chart becomes re-uploadable
  without limit, and every re-upload re-forwards the bytes to the classifier.
  The purge would defeat the block.
- **Purge bytes, keep the row** → dedup survives and the block is durable. What
  is retained is a SHA-256 of the content and the verdict, which is not PHI.

**I read the second as correct and will build it**, but it is a compliance
statement and should be in the contract rather than inferred from my choice:
*purge means the GCS object and the extracted text; the row, its hash, and its
verdict survive as the record that this content was refused.*

(Adjacent, same area: the zombie branch at `main.py:8296` does `db.delete(
existing_doc)` and does not touch the blob. That orphans GCS bytes today, on a
non-PHI path. Mine, and I will fix it with this work.)

### 4 · "Bounded" has no clock

A hold expires "at hold expiry or the user's decision." No component expires
anything today. A hold whose only exit is someone asking about it is not bounded
— it is the classifier-hold defect again, where a document sat `completed`,
unchunked, and invisible on every dashboard.

**Change:** name the owner and the TTL in the contract. My proposal — RAG owns
the sweeper (it is my table), default TTL 7 days, expiry resolves to **purge**,
not admit, and the expiry is written to the marker so "expired unadjudicated" and
"purged on verdict" are never the same value. Fail-closed: a hold that nobody
adjudicated is a refusal, not a grant.

### 5 · Chat's flag #2 has a hole on exactly the tier it protects

Chat's rule — *audit write fails ⟹ admit fails* — is right, and the org-docs lane
already implements that shape (`main.py:19477` raises `phi_blocked /
audit_write_failed`). But it fails closed **only when `_blocked` is true**; on a
clean gate it logs and continues (`main.py:19487`).

An Override-1 clearance on `heavy_attest` produces a document whose post-override
gate reads **clean**. It would take the best-effort branch — the one tier where,
by Chat's own argument, the audit is the *only* control that exists.

**Change:** the fail-closed condition is not "was it blocked," it is "was this
admission attributable to a human." Any document carrying a `phi_override` marker
fails closed on the audit write regardless of its resulting gate. I will state it
that way in the persist path.

### Confirmed without change

- `phi_override{cleared_tier, attestation_tier, identifier_labels, attestation,
  by, at, classifier_version}` — **Chat's flag #1 is granted**: `cleared_tier` is
  persisted, so "admitted because provably not PHI" and "admitted because a human
  said it was synthetic" stay distinguishable forever. Same rule that put
  `caller` in the classification blob after it was computed and discarded.
- `ingest_override{kind, gate_verdict, environment, forced_by, at,
  classifier_version}` — `environment` stamped at ingest from the server-side
  value, never caller-asserted, and **fail-closed the way Chat's flag #3 asks**:
  absent, empty or unrecognised resolves to `prod`.
- Both persisted **verbatim**. This seat computes no field in either marker.
- `ON CONFLICT (id) DO UPDATE` on the `rag_published_embeddings` insert
  (`publish.py:349`), matching `publish_sync.py:352`. It composes here: a publish
  that dies on the pkey today leaves a state chat labels
  `blocked_indeterminate`, which means some population currently counted as a PHI
  refusal was never a PHI decision at all. Worth fixing before the HOLD counts
  are read as compliance numbers.

**Sequencing:** items 1–3 and the pkey fix are the storage spine and are mine to
build in one change. Item 4's TTL and item 5's rule are decisions I have proposed
rather than taken — PHI closes them as rules owner, same as §4.
