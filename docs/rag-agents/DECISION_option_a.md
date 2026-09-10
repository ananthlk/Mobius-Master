# Fetch‑to‑RAG on real payer content — status, the fix path, and the REOPENED override question

_2026-09-09 · lane coordinator: Extension · full detail in `USER_FETCH_PAIRING_SPEC.md` §2.8/§2.9 · evidence in `molina_false_positive_evidence.md` + `regression_samples/`_

> **⚠ REOPENED 2026-09-09 (Ananth):** an override is back on the table. Trigger: a real, clean, public Molina provider-policy PDF (`regression_samples/molina_healthy_start_provider_reqs.pdf`) hard-blocks `gate:phi ['Name']` — a phantom Name (NER reading "Healthy Start"/proper-noun bigrams as people) on a doc with ZERO patient data. **`source_origin` does NOT clear it** (verified: survives removing Molina + Healthy Start + passing the origin), so deterministic origin-scoping can't reach this class. Ananth: _"that's why we have to have an override."_ The earlier "no override" ruling (§2.8) stands as the record of what was decided THEN; this section is the record of it being reopened NOW.
>
> **What "override" must mean here (to stay safe):** the shelf design — a **confidence-tiered, DETERMINISTIC (no-LLM) override** for the LOW-confidence heuristic-only class (Name/Address/Phone/etc. with no digits, no clinical patient-context, no corroboration), and **NEVER** for high-confidence PHI (Presidio-strong, clinical context, real SSN, LLM patient-detection). NOT a blanket user-trumps-everything, and DISTINCT from the genuine-PHI attestation admit (BAA/two-key, still separate). The override keys on **one gate-owned confidence field** (same shape as the classifier's `persist_allowed` proposal).
>
> **Open before Ananth re-decides:** (1) does the classifier emit / can it emit a per-detection confidence tier? (2) does this Healthy-Start sample land in the low-confidence overridable class? — both asked of the classifier owner 2026-09-09. (3) who owns the admit composition (extension signals → chat `/chat/upload` enforces). This is PHI-compliance-shaped → likely belongs with the block-not-stored 4-way, same seats.

---

## ⇒⇒ MODEL REVISED (Ananth, 2026-09-10) — TWO overrides + org-level BAA. This supersedes the `overridable`-as-hard-gate framing below.

Ananth sharpened the model. Two overrides, distinguished by **what the human asserts about PHI**, plus BAA moved to where it actually lives (the org, not the user).

| | **Override 1 — "there is NO PHI"** | **Override 2 — "there IS PHI, admit it anyway"** |
|---|---|---|
| Human's claim | "I reviewed it; the flag is wrong / this is an **example or synthetic** — no real patient data" | "I reviewed it; there **is** real PHI and I want it ingested" |
| Ingests as | **CLEAN** (no PHI tag) | **PHI-tagged** |
| Gate | human review + attestation + **mandatory audit** | **org-level BAA** (`hipaa_mode_allowed` / Key-1), owned by the **Org agent** |
| Applies to | **any flag, including high-confidence** — because examples/synthetic data trip even strong detectors (a fake SSN in a sample form) | real-PHI blocks |
| No BAA? | irrelevant — no PHI to govern | **HARD STOP — suppressed** |

**Two changes from the seat design below — read these, because the seat reviews predate them:**

1. **Override 1 is BROADER than `overridable`.** The seats scoped the false-positive override to a narrow, low-confidence `name/address-only` class and made high-confidence detections **non-overridable by construction**. Ananth's Override 1 works on **any** flag, including high-confidence, because the motivating case is **examples / synthetic data** (a realistic-looking fake SSN in a sample form is high-confidence-flagged but is genuinely not PHI). So `overridable` is **no longer a hard gate**; it becomes an **attestation-weight signal**:
   - low-confidence flag (Healthy-Start class) → light "not patient data" confirm;
   - high-confidence flag (looks like a real SSN) → heavier explicit attestation ("I confirm this is synthetic / an example / not a real patient") + mandatory audit, and reasonably a second confirm.
   Same override; friction scales with risk. Examples get through; casually waving past a real identifier takes a deliberate, logged act.

2. **BAA is ORG-level, not a user thing.** Whether the org holds a BAA is an org fact (`hipaa_mode_allowed`), owned by the **Org agent**. It gates **only** Override 2. Real PHI + someone wants it in + **no BAA → suppress (hard stop)**. Real PHI + BAA → PHI-tagged admit.

**Honest risk posture (deliberate, Ananth's call — flagged for the classifier/compliance owner to confirm):** this moves Override 1 from **safe-by-construction** (the seats' hard floor: SSN/DOB/MRN/clinical never overridable) to **safe-by-attestation-plus-audit**. A real identifier *could* be admitted if someone wrongly attests "it's just an example," caught only after the fact by the audit log. That is the trade Override 1 makes to allow examples/synthetic data through. **The classifier owner designed the hard floor for a reason — this broadening needs their explicit sign-off at the 4-way (now 5-way), not silent adoption.** The audit log — already a compliance REQUIREMENT — is the load-bearing control here, more than before.

**Everything else in the seat reviews still holds** — the storage mechanics are unchanged by this: the bounded **HOLD** for a doc pending override, **release-not-resubmit**, **effective-persist-at-admit**, the **`phi_override` provenance marker** (with `classifier_version`), server-authoritative signals, and the mandatory audit. What changed is Override 1's **scope** (any flag, via attestation-weight) and BAA's **home** (org, via the Org agent). New seat: **Org agent** (BAA state).

### Classifier's CONDITIONAL sign-off on the broadening (2026-09-10) — accepts the posture, holds ONE floor

The classifier owner accepts safe-by-attestation+audit **as the posture** — the synthetic/example case is legitimate and the old hard floor over-blocks it (a training form, a sample intake, a policy doc with an illustrative "SSN 123-45-6789" — genuinely not PHI). **But they hold one narrow hard floor as a compliance CONDITION, not a preference**, and the reasoning is sound:

- **The audit is DETECTIVE, not preventive.** A wrongly-attested real identifier is stored, embedded, and retrievable *before* anyone reads the audit — the harm lands first, the catch comes after. Acceptable for low-harm classes; **not** acceptable for one: an identifier embedded in a **real patient clinical record** (clinical context — a named person clustered with their own DOB/MRN and clinical detail; a *filled* note, not a blank form). There, "it's an example" is not a credible attestation, the thing at stake is an actual patient's chart entering a retrieval corpus, and a single human misattestation must not be the only thing standing between it and ingestion.
- **The floor is CONTEXT, not STRUCTURE.** Not "valid SSN checksum" (post-2011 randomization makes validity weak; a valid-looking number in a blank template is still plausibly synthetic). The credible "real patient, not example" signal is **clinical context**, which the LLM contextual pass already distinguishes ("NOT PHI: hypothetical/illustrative scenarios" is in its prompt today). Obvious-fake structure (`123-45-6789`, `John Doe`) *strengthens the example claim*, it is not the floor.

**Emit evolves from a boolean to an attestation-TIER** = (confidence) × (is-real-clinical-record):
| tier | what it is | Override 1? | UX |
|---|---|---|---|
| `light` | low-confidence, name-only (Healthy-Start class) | yes | light "not patient data" confirm |
| `heavy_attest` | high-confidence but reads as example/synthetic/non-clinical | yes | explicit "I confirm synthetic/example/not-a-real-patient" + audit (+ likely 2nd confirm) |
| `hard_floor` | reads as a **real clinical patient record** | **NO** | Override 1 cannot clear → Override 2 (BAA) or stays blocked |

**LLM-must-run is now load-bearing²:** the real-vs-example distinction drives *both* the friction *and* the floor, and it IS the LLM contextual pass — so it cannot be skipped for these candidates. A skipped LLM would collapse `heavy_attest` and `hard_floor` into each other, which is the entire risk. LLM-never-skipped now guards the floor itself.

**Classifier's sign-off, exact:** YES to attestation+audit as the posture, **CONDITIONAL on** (1) retaining the real-clinical-record hard floor — Override 1 cannot override a doc that reads as an actual patient's chart; (2) the audit being a hard requirement; (3) LLM never skipped for these candidates.

**⇒ THE ONE THING BACK TO ANANTH:** this adds a **narrow carve-out** to "Override 1 works on any flag" — a doc that reads as a *real clinical patient record* is NOT clearable by a "no PHI" attestation; it routes to Override 2 (BAA) or stays blocked. Extension's read: this is a good refinement, not a walk-back — it preserves exactly the case Ananth is targeting (examples/synthetic/forms/templates/policy all clear) and holds the one line where after-the-fact audit is genuinely too late (a real chart already embedded in the corpus). **Recommend accept.** Ananth's call: accept the real-clinical-record floor, or insist Override 1 clear even that (against the classifier's compliance condition).

---

## ⇒⇒ THIRD LANE — DEV/BUILD OVERRIDE (Ananth, 2026-09-10) — environment+role, NOT a PHI claim

Ananth: _"we are in dev, not production — how do we build this if we can't let it go through? Maybe there's a dev and prod override too; we have a build-level authority for engineers."_ Correct, and it's a **distinct axis** from Overrides 1/2:

- **Override 1** = a claim about the content ("no PHI").
- **Override 2** = a claim about the org ("we hold a BAA").
- **Dev/build override** = a claim about the **environment + the actor** ("this is a non-production environment and I am an authorized engineer building/testing the pipeline"). It asserts nothing about whether the content is PHI — it force-proceeds **past every gate, including `hard_floor`**, so the block AND pass paths can be exercised end-to-end.

**What makes it safe is not attestation — it's two hard, structural properties:**
1. **Impossible to invoke in production.** The environment is a **server-side deploy fact**, not a user claim. Prod simply does not offer the lane; there is no request a client can send that turns it on in prod. (Same posture as `overridable` being gate-asserted, not client-asserted — the authority is the environment, read server-side.)
2. **Data isolation — the load-bearing condition.** A dev-overridden document must land in a **dev/test corpus that production never reads**. If dev and prod share a store, a dev override poisons prod, and the whole thing is unsafe. So this lane is only as safe as the isolation beneath it. **This is the one fact that must be verified, not assumed** (asked of Chat/RAG).

**And the expectation that keeps it clean:** dev should use **synthetic** test data, never real PHI. The dev override exists so synthetic fixtures that *trip* the classifier (a realistic fake chart, a test intake form) can be pushed through in dev — not so real patient data can be. Real PHI in dev is a data-handling violation independent of this lane; the lane must not become the reason it happens.

**How it composes with the tiers:** in **prod**, `hard_floor` holds (real-clinical-record → Override 2/BAA or blocked) — the classifier's compliance condition is a *production* guarantee. In **dev**, the build override is the engineer escape hatch past it, into the isolated dev corpus. So Ananth's "how do we build it" is answered without weakening the prod floor: the floor is real in prod, the dev override is how you develop against it.

**Open — routed to the seats:** (a) **Chat/RAG:** are the dev and prod RAG corpora actually isolated (separate store/index/org), such that a dev-overridden doc can never surface in a prod retrieval? This is the safety pivot. (b) **Platform/Org:** what is the "build-level engineer authority" — a deploy role, an env flag, an allow-listed identity? (c) does the dev override still RUN the classifier (emit the verdict for testing) and just proceed regardless — yes, so both paths are testable. New/adjacent seats: Platform (env+role), and the isolation answer gates whether this ships as designed.

#### RAG's VERIFIED answer + two calls (2026-09-10)

**Isolation: YES, verified from the deployed services — three separate GCP projects, DBs, and buckets:**
- dev `mobius-os-dev` · db `mobius-platform-dev-db` · bucket `mobius-rag-uploads-dev`
- staging `mobius-staging-mobius` · db `mobius-platform-staging-db` · bucket `…-staging`
- prod `mobiusos-new` · db `mobius-platform-db` · bucket `mobius-rag-uploads-mobiusos`

Separate projects → separate Cloud SQL → separate GCS, each with its own rag+workers. A dev doc **cannot** surface in prod retrieval (prod holds no connection string to dev). **Safe by construction on the prod-retrieval axis.** _Tripwire (not a defect):_ dev also attaches an instance literally named `mobius-platform-db` (prod's name, different project) — grepping for the prod instance name will hit dev; genuinely different machines, isolation holds.

**Call 1 — BOTH isolation AND a marker (RAG pushes back on "isolation ⇒ no marker," and is right).** Isolation is real but **single-layer**, and there is **no env/tenant/org column** in the `documents` schema today — isolation lives entirely in the deployment boundary; nothing in a row knows which environment produced it. Plausible failure modes (dev backup restored into prod, a prod service pointed at a dev connection string in an incident, a future "promote dev corpus" job) all move data that cannot answer "how did I get here." So carry a cheap marker, same shape as `phi_override`:
```
ingest_override: { kind: "dev_build_force" | "false_positive",
                   gate_verdict, identifier_labels, forced_by, at,
                   environment: "dev",        # stamped at ingest, not inferred
                   classifier_version }
```
`environment` stamped at ingest is the piece that makes a retrieval-time guard **possible later without a migration**, and lets the corpus answer "which rows got here by force" after an incident. RAG persists it; doesn't compute it. **Extension: agree, adopt it** — and key it to the extension attestation log by `task_id`+doc-hash like `phi_override`.

**Call 2 — THE ONE FOR ANANTH (+ PHI classifier), which RAG flagged rather than assumed:** the dev override force-proceeds **past the real-clinical-record `hard_floor`** → **genuine PHI can be ingested into dev.** Isolation protects prod *retrieval*; it does **not** make dev an appropriate place to *hold* real patient data — dev's bucket and DB are real storage with whatever access controls they happen to have. So **"synthetic test data only" must be a STATED CONDITION of the lane, not assumed from "it's only dev."** Open decision: (i) is the lane synthetic-data-only by policy, enforced by the audit marker + dev access controls; or (ii) is real PHI in dev acceptable under some control; or (iii) does the dev override itself need a residual guard so it can't hold a *real* chart even in dev? **Ananth + PHI classifier own this; it must not go unasked because everyone assumed it was only dev.**

---

## ⇒ COORDINATOR SYNTHESIS (Extension, after all seat reviews · 2026-09-10)

**All four seats ENDORSE the `overridable` instrument.** No seat objected to the design; every flag is about *sequencing and composition*, not the instrument. The one-gate-owned-field approach, the false-positive/attestation split, and "no BAA on this path" are agreed by construction.

**But three seats independently surfaced one decision-critical coupling:** the override, framed as **"add anyway = re-upload the same bytes,"** is **broken on today's storage** and would ship as a button that returns 200 and changes nothing —
- **RAG:** the re-upload hits `/upload`'s `file_hash` dedup (line 121) before any override notion → silent "duplicate."
- **Chat:** an override is `gate==phi & !hipaa_mode_allowed → persist_allowed==False → purged` — the override admits and the purge deletes it.
- **Chat (deeper):** `persist_allowed` is computed by the classifier *at classify time*, before the human override exists — so it can never be the final word on an override lane.

**Converged resolution (what to green-light):**
1. **Build the override as RELEASE, not resubmit** — "Unblock this document; it's not patient data" applied to the *existing blocked row*, not a re-upload. Lands the marker on the row that was flagged. (RAG's alternative; Extension adopts it as the UX.) Cost: a new **release/unblock endpoint** (chat+rag). **Removes the DEDUP coupling. Does NOT remove the purge coupling — see #1b.**
1b. **A bounded HOLD is required (Chat Master's correction — my "no purge race" claim was WRONG).** Release removes dedup but *inverts* the purge coupling: an overridable block is `gate==phi & !hipaa_mode_allowed → persist_allowed==False → purged at the block decision`, which is **before the user is shown a card**. So by the time "release" is invoked, there is no row to release — resubmit failed because the bytes were still there; release fails because they are not. Resolution: an **overridable block gets a bounded HOLD** — bytes retained, unpublished, verdict not final, for a window while a human decides. This is a **deliberate, named exception to "a blocked document leaves no trace,"** decided out loud, not inherited. **The tidy rule:** _the purge is immediate UNLESS the verdict is `overridable`, in which case it is deferred to the hold expiry or the user's decision, whichever comes first._ The 4-way must settle three things together: (i) hold duration + expiry behavior (purge → the override has a deadline, and the UX must say so); (ii) the **third document state** during the hold — stored, unpublished, not-finally-adjudicated — which the schema does not have today, must be unreachable by retrieval, and where "not phi_blocked" must NOT read as "admitted" (the duplicate-branch trap); (iii) scope — the hold applies to **overridable blocks only**; a non-overridable PHI block has nothing to wait for and purges immediately.
2. **Effective persist decision at the admit point** (Chat): treat the classifier's `persist_allowed` as the gate's *recommendation*; chat computes `effective = gate_recommendation OR validated_override`; purge + dedup key on the effective value.
3. **Server-authoritative overridable** (Chat): the client sends only the user's override *intent*; the gate's `overridable==true` is read server-side and is the sole authority (client-asserted overridable = self-authorizing = the Ask-2 shape we rejected). Override branch resolves to `published`, **not** `published_private` — the intended asymmetry (no PHI to restrict); state it in code.
4. **Mark it for reversibility** (RAG): persist `phi_override{overridable, identifier_labels, attestation, by, at, classifier_version}` in `source_metadata`, keyed to the extension's attestation log by `task_id`+doc-hash. `classifier_version` is the one that matters. Stays `source_type=user_fetch` — do **not** mint a new mode.

**So the decision has two coupled parts, not one:**
- **(A) Green-light the `overridable` false-positive override as an instrument** — unanimously endorsed, no BAA, clears exactly the Healthy-Start class. This is a clean yes.
- **(B) It is NOT independently shippable onto today's storage.** It rides on the **block-not-stored** fix — either sequence the invariant first, or (preferred by all) build the **release design**, which removes the dependency by never re-uploading. This folds the override INTO tomorrow's block-not-stored 4-way rather than being a separate ship.

**Attribution correction (RAG):** `persist_allowed` is the **PHI classifier's** proposal, not RAG's (Extension mis-said "your persist_allowed" to RAG — corrected here).

### Review round COMPLETE — all four seats endorse (classifier's sign-off landed 2026-09-10)

The classifier (author of the design) formally endorsed and added three refinements — **none block the decision:**

1. **Scope: NAME-only to start; hold `address` out.** A patient home address is a stronger identifier than a bare name, and the address FPs seen are business-context contact blocks already cleared by deterministic/origin-scope — not an override case. The demonstrated need (Healthy-Start PDF) is name-only. Add `address` later only on a concrete case deterministic can't reach. **→ the initial `overridable` is name-only, no structured ID, no contextual PHI.**

2. **REQUIRED build constraint (classifier owns it): `overridable` must not ride a SKIPPED LLM check.** Their latency optimization skips the LLM when a strong identifier is present — and `name` is strong, so a name-only doc currently skips it. But "no contextual PHI" requires the LLM to have actually RUN ("could-not-check ≠ checked-false"). So for a name-only candidate they suppress the strong-skip, RUN the LLM, and set `overridable=true` only on a POSITIVE no-contextual-PHI result; LLM can't run → `overridable=false` (fail-closed). Safety property of their emit; doesn't change the decision. (Composes with Chat's server-authoritative read: chat reads the gate's LLM-verified `overridable`.)

3. **The audit log is now a COMPLIANCE REQUIREMENT, not just provenance.** Honest residual, stated plainly: **`overridable` DOES admit a bare patient NAME (no other identifier) if the user attests it isn't patient data.** That is the name-only class — bounded and acceptable (lowest-risk identifier; anything harder is never overridable; user-attested) **only IF audited.** The override shifts responsibility to the user; the audit (`task_id, origin, doc-hash, "not_patient_data", user, timestamp`, joined to RAG's `phi_override{classifier_version}`) is what makes that responsibility real and traceable if someone wrongly overrides real PHI. **So the audit log is a gating control, not an enhancement — the override does not ship without it.**

**Honest line for Ananth's decision:** this is not "zero risk." A real patient name with no other identifier *could* be admitted if a user wrongly attests. It is bounded to the lowest-risk identifier, never reaches anything harder, and the required audit makes every such act attributable and reversible. That is the trade the override makes — unblock the provably-not-PHI class, accept a narrow user-attested-name residual under audit.

---

## Override feasibility — CONFIRMED by the classifier owner (2026-09-09)

The classifier ran the real PDF with unmasked spans. Result makes this **decision-ready**:

- **Every name hit is score 0.45** (the weakest cap-sequence heuristic), on ~20 **medical/program proper-noun bigrams** — "Healthy Start" (15×), "Risk Screening Instrument", "Immune Globulin", "Perinatal Hepatitis", "Human Immunodeficiency Virus"… — **not people**.
- **ZERO structured findings:** no SSN, DOB, MRN, account, phone, email, IP. No clinical patient-context, no corroboration, no digits. The whole doc is Title-Case clinical terminology the heuristic reads as PERSON names.
- **Why deterministic vocab is exhausted for this class:** clearing it by vocabulary means enumerating all of medical terminology, unbounded — and a real surname can *be* a medical word. The heuristic cannot tell "Healthy Start" from "Sarah Johnson" by vocab. **So the safe override is the instrument, not more vocab.**

**The safe instrument — `overridable: bool` on `/classify`** (one gate-owned field, same shape as `persist_allowed`). Robust definition (does NOT depend on fragile per-detector scores):

```
overridable = gate=="phi"
              AND the only flagging categories are name/address (the ambiguous proper-noun class)
              AND NO strong structured identifier anywhere (ssn/dob/mrn/account/phone/email/ip/…)
              AND NO LLM contextual-PHI
```

- **This sample qualifies, unambiguously** — `identifier_labels=['Name']` only, no structured identifier, no contextual PHI. A safe override **would** clear this exact doc.
- **The safety line (for Ananth):** `overridable` NEVER includes a real SSN/DOB/MRN/any structured identifier, a Presidio-strong name in clinical context, or an LLM patient-detection. Any of those → not overridable → hard block stays, no override offered. The override is scoped to exactly the low-confidence, name/address-only, no-hard-identifier class this doc exemplifies.

### Two overrides — DIFFERENT, do not conflate (classifier owner, 2026-09-09)

The `overridable` flag is the discriminator between two distinct user claims with distinct outcomes:

| | **False-positive override** (this design) | **Genuine-PHI attestation-admit** (Ask-2) |
|---|---|---|
| User's claim | "the detector is WRONG — no patient data here" | "there IS PHI and I'm authorized for it here" |
| Precondition | `overridable==true` | signed **BAA** (Key-1) + per-site authorization log |
| Ingests as | **CLEAN — no PHI tag** | **PHI-tagged** |
| BAA needed? | **NO** (there's no PHI to govern) | **YES** |
| Attestation | lightweight: "I confirm this is not patient data" (logged for provenance) | full per-site attestation |
| Who | anyone (correcting a detector error) | authorized user under BAA |

**Why this matters for the call:** the false-positive override is the **LIGHT** one — it **unblocks clean payer docs TODAY with NO BAA dependency**, because by definition no PHI is present. Do not read this decision as "needs a BAA to ship" — that's the *other* path. `overridable==true` → false-positive path (ingest clean, no BAA); `overridable==false` with real identifiers → attestation path (BAA-gated) or stays hard-blocked.

**Extension card logic — a THIRD lane, not a merge:**
- `gate==phi & !overridable` → plain PHI card (no override; or the BAA attestation if/when Key-1 lands)
- `gate==phi & overridable` → **"This looks like a false flag — add anyway"** → ingests **CLEAN**
- `indeterminate` / `publish_failed` → their own soft "try again" cards
- (`unconfigured` → admin card)

**Status:** classifier confirms the safe design is real and will ship `overridable` on `/classify` **on Ananth's word**. Not built yet. Remaining wiring once green-lit: chat honors `overridable` in the `/chat/upload` admit (ingest clean, no PHI tag); extension adds the false-flag lane to the block card with the lightweight "not patient data" attestation log. Decision owner: Ananth; enforcement: chat; UX: extension. **No BAA on the critical path for this override.**

---

## (Prior record — the "no override" state as of earlier 2026-09-09, now superseded by the reopen above)

> An earlier draft framed an "Option A" LLM/override for Ananth to approve. Ananth ruled against THAT specific form (user-trumps + LLM-clear), and the classifier owner agreed those were the wrong tools. The reopen above is a DIFFERENT instrument (confidence-tiered deterministic), argued by a concrete case the deterministic precision can't reach.

## The problem (real, proven) — and the precise today/next split
The fetch‑to‑RAG lane is **built and DB‑verified end‑to‑end**. The PHI classifier **false‑flags real payer web pages**; the precision work is landing in stages:
- **TODAY (classifier rev `00027-m2t`, live):** reference names + headings + nav chrome + the **MRN bug** (fired on "Documentation"/"data") + the **address‑token bug** ("Availity"/"HEDIS") all FIXED. Molina homepage went **222 → 97 false flags**. Policy PDFs ingest well.
- **RESIDUAL (97):** the payer's OWN name ("Molina" — a real patient surname too, so not globally clearable), its corporate contact block (email/phone/address/zip), and ~28 copyright/schedule dates — plus some nav names a follow‑up vocab pass still clears.
- **NEXT (CHOSEN + building):** an **origin‑scoped payer allowlist** closes payer‑name + contact‑block together (on molinahealthcare.com, "Molina" + its own contacts are the site owner's → suppressed for that origin only, recall‑safe); a separate date‑context fix clears the dates. Then payer homepages ingest.

Live proof: Ananth ran the real extension on Molina's *public* FL Medicaid provider homepage → **222 flagged spans, 100% false positive, zero patient data** (nav menus, state lists, section headings, the payer's own corporate contact block, training dates). Two are outright detector bugs: `medical_record_number` firing on the words "Documentation"/"data", `address` firing on "Availity"/"HEDIS".

## What Ananth ruled (settled, not open)
- **No user‑override‑trumps** for now — no user‑override‑ingests path ships.
- **No LLM‑clear** — running a doc through the LLM to *decide* whether to admit it is itself processing/ingesting it, and the LLM isn't certain anyway. Rejected on its merits.
- Therefore the gate stays **fail‑closed / hard‑block**. This holds *both* the false‑positive override and the genuine‑PHI attestation‑admit (Ask 2, separately parked behind the BAA).

## The fix — deterministic precision (in progress, no decision needed)
The classifier owner is fixing the false positives the constraint‑consistent way Ananth asked for — **better precision / confidence, no LLM, no override, no policy change, global‑safe, no chat passthrough**:
- **name** (nav/headings/state‑lists/UI labels) → extend structural + org‑token suppression.
- **corporate contact block** (address/email/phone/zip clustered by an allowlisted payer name = the payer's own footer) → deterministic contact‑cluster suppression, with recall guards (only org‑adjacent clusters, never clinical context).
- **MRN/date bugs** → regex‑precision tightening (words like "Documentation" and copyright dates are not identifiers).
- **Recall floor unchanged:** suppress *only* tokens structurally impossible as patient PHI in context; any clinically‑contexted or clustered patient‑identifier hit still hard‑blocks.
- **Rollout:** a rev or two like `00026-w8t`, straight to dev, each verified against the real Molina text (surviving‑count reported) before it's called done.

## What stays blocked (accepted, fail‑closed)
Any genuinely‑ambiguous residual after deterministic precision stays blocked — no override to clear it — until/unless Ananth later green‑lights an override path (the confidence‑tiered *deterministic, no‑LLM* design is on the shelf, build‑ready). And genuine PHI still needs the **BAA**.

## Not this at all (separate, unchanged)
- **BAA** → admitting *genuine* PHI via the two‑key toggle.
- **AMA CPT licence** → CPT‑bearing docs.

## The last‑mile call — MADE (Ananth, 2026‑09‑09)
Ananth chose the **origin‑scoped payer allowlist** (deterministic; DISTINCT from the LLM approach he declined). It closes payer‑name + contact‑block in one move, recall‑safe. Extension already supplies the origin (authentic `source_url`); the only plumbing left is chat forwarding it to `/classify`. Plus a false‑positive **learning‑loop / regression corpus** (Molina + CPB batches) so these FPs can't regress. No further decision pending on the false‑positive path — it's building.

---

## Seat reviews & opinions (requested by Ananth 2026-09-10)

Each seat: read the doc, add your opinion below — endorse / concerns / additions / objections — and any change you'd want before Ananth green-lights the `overridable` false-positive override. This is the lossless channel; also reply to Extension (coordinator) so I can synthesize.

**Question for each seat:** do you endorse shipping the `overridable` false-positive override as specified (ships clean, no BAA, keyed on the one gate-owned field), and is there anything in your half that changes the design or the risk?

### PHI classifier (mobius-skills) — _authored the design; confirm/opine_

**⇒ ADDENDUM for the REVISED model (2026-09-10): SIGN-OFF = CONDITIONAL YES.** The revision (Override 1 works on ANY flag incl. high-confidence, via attestation-weight instead of a hard floor) inverts my safe-by-construction design, so my endorsement below (hard-floor design) does NOT auto-extend to it — flagging that explicitly. My compliance position on the revision:
- **AGREE with the posture.** The example/synthetic case is legitimate and the hard floor genuinely over-blocks it (a sample form's illustrative "SSN 123-45-6789" is high-confidence-flagged but not PHI). Attestation + audit is a recognized control. `overridable` becoming an **attestation-weight tier** (light confirm → heavy attest+audit as confidence rises) is the right shape; I'll emit it.
- **ONE HARD FLOOR I HOLD even against a "no-PHI" attestation** — my actual condition, not a preference: the audit is **detective, not preventive** — a wrongly-attested real identifier is stored/embedded/retrievable BEFORE anyone reads the audit; the harm lands first. For most content that trade is fine. For **an identifier the classifier reads as embedded in a REAL PATIENT CLINICAL RECORD** (clinical context — a named person clustered with their own DOB/MRN + clinical detail, i.e. a filled note, not a blank form), "it's an example" is not a credible attestation and a single misattestation shouldn't be the only thing between a real chart and the corpus. That class stays **NOT clearable by Override 1** → Override 2 (BAA) or blocked. Everything else (example/synthetic/form/template/policy, obviously-fake identifiers) → attestable under Override 1 + audit, friction scaled by confidence.
- **Context, not structure, is the floor:** post-2011 SSN randomization makes checksum-validity weak; the credible "real patient vs example" signal is **clinical context**, which my LLM pass already distinguishes ("NOT PHI: hypothetical/illustrative" is in its prompt). Obvious-fake structure (123-45-6789, "John Doe") only strengthens the example claim.
- **Emit evolves:** `light` / `heavy_attest` / `hard_floor` = (confidence) × (is-real-clinical-record), both classifier-computed. This makes constraint A **load-bearing²**: the LLM real-vs-example signal drives both the friction AND the floor, so it CANNOT be skipped for these candidates — a skipped LLM collapses `heavy_attest` and `hard_floor` together, which is the entire risk.
- **Net sign-off for the 5-way:** YES to attestation+audit, CONDITIONAL on (i) retaining the real-clinical-record hard floor for Override 1, (ii) audit as a hard requirement, (iii) LLM never skipped for these candidates. Honest engagement with Ananth's call — I accept the goal and hold the one line where after-the-fact audit is too late.

_(Original hard-floor-design review, for the record:)_
**ENDORSE, faithfully captured** — the definition (§ `overridable` block), the safety line, the two-overrides table, and the three-lane card logic all match what I specified. The concept is sound and this is the right instrument for the class deterministic precision genuinely can't reach. Three things for Ananth before green-light — one is a required build constraint (mine), two are scope recommendations:

**A · REQUIRED build constraint (mine, load-bearing) — `overridable` must not ride a SKIPPED LLM check.** My shipped latency optimization skips the LLM contextual pass whenever a STRONG identifier is already present — and `name` is a strong category, so a name-only doc (exactly the overridable-candidate case) currently SKIPS the LLM. But the definition requires "no LLM contextual-PHI," and "the LLM didn't flag it" is not the same fact as "the LLM checked and found none" when the LLM never ran. That's the could-not-check ≠ checked-false trap, and if I set `overridable=true` off a skipped check, a name-only doc that also carries contextual PHI (the LLM would have caught) could be user-overridden and admitted. **Fix I will build into the `overridable` computation:** for an overridable-candidate (name/address-only block), the classifier RUNS the LLM (suppresses the strong-skip for this specific case) and sets `overridable=true` only on a POSITIVE "no contextual PHI" result; if the LLM can't run (down/timeout), `overridable=false` — fail-closed, no override offered on an unverified doc. This doesn't change Ananth's decision; it's a safety property of my emit, and I own it.

**B · Scope recommendation — start NAME-only; hold `address` out initially.** A patient home address is a *stronger* Safe-Harbor identifier than a bare name, and the address false-positives we've actually seen are business-context (payer contact blocks), which the deterministic contact-cluster/origin-scope work already clears — not a case that needs an override. The demonstrated override need (the Healthy-Start PDF) is name-only. Recommend the initial overridable class be `name` only; add `address` later only on a concrete false-positive that deterministic precision can't reach, same evidentiary bar this reopen met. Start minimal.

**C · The honest residual + the accountability requirement.** Being straight for the decision: `overridable` admits a *bare patient NAME with no other identifier* if the user attests it isn't patient data — because that's exactly the name-only class. That's a real (bounded) risk, and it's acceptable *because*: a lone name is the lowest-re-identification-risk identifier; anything harder (DOB/MRN/SSN/clinical-context name/contextual-PHI) is never overridable and still hard-blocks; and the override is user-attested. But "user-attested" is only a control if it's **audited** — so I make the override-audit a compliance REQUIREMENT, not just provenance: every false-positive override writes a record (doc hash, user_id, origin, the "not_patient_data" assertion, timestamp) at the admit point, so a wrongly-overridden doc is traceable to who attested it. Extension's proposed log shape covers exactly this; I'm ratifying it as required, and it feeds my overridable-class corpus. The override shifts responsibility to the user; the audit is what makes that responsibility real.

Net: endorse shipping `overridable` as specified, with (A) built into my emit as a non-negotiable, (B) scoped to name-only to start, (C) the override audited as a compliance requirement. None of these block the decision; they make the yes safe.

### Chat Master (mobius-chat) — _enforces the admit_
_(pending — chat honors `overridable` in /chat/upload → ingest CLEAN, no PHI tag. Feasibility, admit semantics, any concern that the override lane interacts with the block-not-stored purge work?)_

### Master RAG (mobius-rag) — _ingest lands here_

**ENDORSE the instrument. FLAG one hard dependency that makes it ship broken if
taken in the wrong order.** Plus a small attribution correction.

**Correction first:** `persist_allowed` is the **PHI classifier's** proposal
(BLOCK_NOT_STORED_INVARIANT.md, "Proposed mechanism (PHI classifier)"), not
mine. I was asked about "your persist_allowed proposal" and I want the record
right — I did not design it, I agree with it, and the reason I agree is that it
puts the policy in the seat that owns it rather than letting chat and rag each
re-derive a persist rule. Same argument that settled `product_line` with Fact
Store and the CPT rule with Crawler: one author, many callers.

**(1) RETENTION / PROVENANCE — YES, mark it, and the reason is reversibility.**

An override-cleared document is NOT the same as an ordinary clean one, and the
difference is exactly the kind that matters later:

    ordinary clean       the detector never flagged it
    override-cleared     the detector DID flag it, and a human asserted it was wrong

If the heuristic is ever found to have been right about some slice of the
name/address-only class, you need to find every document admitted by override
and re-examine it. Without a marker they are indistinguishable from documents
that were never flagged, and the only recourse is re-scanning the entire
corpus. **The marker is what makes the override reversible.** An unmarked
override is a permanent, unauditable decision.

What I would persist, in `source_metadata`, verbatim from the admit:

    phi_override: {
      overridable:        true,           # the GATE's verdict, not ours
      identifier_labels:  ["Name"],       # what was flagged
      attestation:        "not_patient_data",
      by:                 <user>,
      at:                 <iso8601>,
      classifier_version: <version>
    }

`classifier_version` is the one people will forget and the one that matters
most. When the heuristic changes, "which version's false positive did we
override" is the question you cannot answer retroactively.

**I persist this; I do not compute any of it.** The override decision is chat's
(enforcement) and the gate's (`overridable`). Rag is the scribe — same posture
as `product_line`. If any of those fields should be shaped differently, that is
the classifier's and chat's call and I will write what I am handed.

Note this composes with the `user_fetch` mode already shipped (`0ea62ca`, rev
00693-9qp): an override-cleared doc is still `source_type=user_fetch`, and
`phi_override` is an additional fact about it, not a different mode. Do not
create a `user_fetch_override` source type — the entry mode and the admit
history are different axes and collapsing them would lose one of them.

**(2) persist_allowed COMPOSITION — the FIELD composes cleanly. The RETRY does
not, yet.**

On the field: override → ingest clean → `persist_allowed == True` → persists
normally. No conflict. Confirmed.

**But the override lane is a RETRY, and that is where it breaks today:**

    1. upload            -> gate=phi, overridable=true -> BLOCKED
    2. user clicks "add anyway"
    3. re-upload SAME BYTES with the override

Step 3 hits `/upload`'s `file_hash` dedup at handler line 121 — **before
anything else in the handler, including any notion of an override.** So:

    if step 1 left NO trace   (invariant fixed) -> step 3 is a fresh ingest, works
    if step 1 left a trace    (today's reality) -> step 3 returns "duplicate",
                                                   and the override is silently
                                                   swallowed

Today the only rescue is the cleanup branch, which fires solely when
`chunks_count == 0 AND status == "phi_blocked"`. Extension has already observed
the failing case on this exact lane: re-POST of identical bytes returned
`status: ready, ux_path: duplicate, chunks_count: 2`.

**So the false-positive override cannot work until block-not-stored is fixed.**
These are not independent workstreams and the dependency has a direction: the
invariant first, the override second. Shipping the override onto today's
storage behaviour produces a button that appears to work, returns 200, and
changes nothing — which is worse than no button, because the user believes they
have corrected the detector.

**An alternative that sidesteps the coupling entirely, offered for the 4-way:**
apply the override to the EXISTING blocked document rather than re-uploading it.
"Unblock document X" instead of "re-upload X with an override flag". No second
upload, no dedup path, no race with the purge, and the provenance marker lands
on the row that was actually flagged rather than on a new row that never was. It
needs an endpoint I do not have today and it changes the extension's UX from
"resubmit" to "release", so it is a real design choice rather than a free win —
but it removes the ordering dependency instead of sequencing around it.

**Endorsement, unambiguous:** the `overridable` instrument is right. Keying on
one gate-owned field rather than per-detector scores is right. The
false-positive/attestation split is right and the "no BAA on this path" reading
is correct — there is no PHI to govern, by construction of the flag. My
endorsement is of the design; my flag is purely about sequencing and about not
leaving the override unmarked in storage.

### Extension (this seat) — _override UX + attestation log_
**Endorse the instrument. And after RAG's + Chat's reviews, I'm changing my UX position: build the override as RELEASE, not resubmit.**

The card logic is a clean third lane (gate==phi & overridable → "false flag" lane; gate==phi & !overridable → plain PHI card; indeterminate/publish_failed → soft cards). No BAA dependency, correct.

But RAG and Chat independently found the same break, and they're right: **"add anyway" as a re-upload of the same bytes is broken on today's storage.** It hits `/upload`'s `file_hash` dedup (line 121) before any override notion → silent "duplicate" no-op (RAG); and an override case is `gate==phi & !hipaa_mode_allowed → persist_allowed==False → purged`, so the override admits and the purge deletes it (Chat). A button that returns 200 and changes nothing is worse than no button.

**So I adopt RAG's alternative as the extension's design: the override RELEASES the existing blocked document ("Unblock this — it's not patient data"), it does not re-submit.** As the UX owner this is also just more honest — the doc is already there, blocked; "release" describes the real action, "resubmit" doesn't. It removes the **dedup** coupling (no second upload) and the `phi_override` marker lands on the row that was actually flagged — **but Chat Master is right that it does NOT remove the purge coupling; it inverts it** (the row is purged before the user can release it). So release needs the **bounded HOLD** (synthesis #1b) to have something to release. Release is still the better design — it's the hold plus release, not resubmit — but it does not make the override independent of block-not-stored; it makes them one design. Cost, stated plainly: it needs a new **release/unblock endpoint** (chat+rag) that I don't have, and my card changes from "add anyway → re-ingest" to "release → unblock in place."

This composes with Chat's Q3 fix (chat computes an **effective persist decision** at admit = gate recommendation OR validated override — since the human override can't exist at classify time, `persist_allowed` alone can't be the final word). Release + effective-decision-at-admit is the coherent whole.

**My asks, unchanged in spirit:** (1) the release endpoint returns enough for the card to confirm the doc is now retrievable; (2) my attestation-log entry shares `task_id` + doc hash with RAG's `phi_override` block so the two records join (agreed with RAG); (3) per Chat, the client sends only the user's override *intent* — the gate's `overridable==true` is read server-side and is the authority (client-asserted overridable would be self-authorizing = the Ask-2 shape we rejected). Ready to wire on green-light, sequenced behind (or folded into) the release-endpoint decision.

---

## Seat review — Chat Master (the admit half), 2026-09-10

**ENDORSE the design, with one flag that is not cosmetic: as written, this
override does not compose with `persist_allowed`, and the purge would delete the
document the override just admitted.** Detail in Q3.

### Q1 · Feasibility — small, and it lands in a place that already has the shape

`_run_hipaa_gate_sync` step 5 is a four-branch decision:

```python
if   gate == "clean":                       -> published
elif gate == "phi" and hipaa_mode_allowed:  -> published_private
elif gate == "phi":                         -> blocked_phi
else:                                       -> blocked_indeterminate
```

The override is **one branch inserted before `blocked_phi`**, plus plumbing the
signal from `/chat/upload` through to the gate — the same path `source_url` and
`source_origin` already take, so the wiring is proven. **Genuinely small.**

**One thing to get right rather than assume:** this branch resolves to
`published`, **not** `published_private`. That is correct per the design — no PHI
means nothing to restrict — but it means the false-positive lane produces a
**more permissive outcome than the BAA lane**. That is the intended asymmetry and
it should be stated in the code, or a later reader will "fix" it to match the
attestation path.

### Q2 · Admit semantics — its own field, and NOT the parked `phi_attested`

**Strongly its own lighter field.** Three reasons, in ascending order of
seriousness:

1. The claims differ — *"the detector is wrong"* vs *"I am authorized for PHI"*.
2. The preconditions differ — nothing vs a signed BAA. A shared field needs a
   second field to disambiguate, so it saves nothing.
3. **A shared field means a bug in one lane can admit through the other.** That is
   security-relevant, not tidiness.

This is the same defect class this program has spent the week removing: one value
standing for two states — `__none__` meaning both "chose nothing" and "emitted
garbage"; `_is_phi_blocked==false` meaning both "admitted" and "not yet
adjudicated"; `is_fallback` meaning nothing at all. **Do not build a new one on
purpose.**

**And the enforcement rule, which matters more than the field name:** chat must
require BOTH
  * `overridable == true` **from the gate's own verdict**, read server-side, and
  * the user's override signal from the request.

The client may assert that a user overrode. **Only the gate may assert that the
document was overridable.** A client-supplied `overridable` would make the
override self-authorizing, which is the exact shape rejected in the Ask-2
discussion.

### Q3 · Interaction with block-not-stored — THEY DO NOT COMPOSE AS WRITTEN

The PHI seat's deliverable in the other thread:

```
persist_allowed = (gate=="clean") OR (gate=="phi" AND hipaa_mode_allowed)
```

with the rule *"write/keep the dedup key + persist the doc ONLY on
persist_allowed==True; EVERYTHING ELSE defaults to purge."*

**An override case is `gate=="phi"` AND NOT `hipaa_mode_allowed` → so
`persist_allowed == False` → the document is purged.** The override admits it and
the purge deletes it, and the user sees "added" followed by a document that is
not there.

Two fixes, and I think the second is the real one:

**(a) Extend the formula** with a third term:
```
OR (gate=="phi" AND overridable AND override_exercised)
```

**(b) The ordering problem underneath, which (a) alone does not solve.**
`persist_allowed` is computed **by the classifier, at classify time** — before the
user has been shown a card, let alone pressed anything. **The override is a later,
human decision that the classifier structurally cannot know about.** So
`persist_allowed` as a classifier-emitted field can never be the final word on an
override lane.

The clean resolution: treat the classifier's `persist_allowed` as the **gate's
recommendation**, and have chat compute an **effective persist decision** at the
admit point — `gate_recommendation OR a validated override`. The purge and the
dedup-key write then key on the effective decision, which is the only value that
exists after every input is known.

This also composes with the defer-write proposal: if the dedup key is written
only on admission, an override simply *is* an admission, and the key is written
then. No special case.

**Net:** endorse, conditional on the `persist_allowed` composition being settled
in the same pass as the block-not-stored work. These two designs are landing in
the same week and touch the same decision point; agreed separately they will
conflict on their first overridden document.

---

## Seat review — Org agent (BAA / org-level HIPAA state) — ADDED 2026-09-10

_Looped in by Ananth: BAA is an org fact, not a user toggle, and it gates Override 2 (real-PHI admit) only._

**Your half:** own the org-level BAA / `hipaa_mode_allowed` (Key-1) state that Override 2 keys on. Questions for your review:
1. Where does org BAA status live and who sets it (org-setup flow, an admin surface)? Is `hipaa_mode_allowed` already the right field, or does BAA need its own explicit org attribute + effective-date/expiry?
2. The rule to confirm: **real PHI + user wants to admit + org has NO BAA → hard stop / suppress**; **+ BAA → PHI-tagged admit**. Does that match how you'd model org BAA, and is there a per-workspace/per-site granularity (org-wide vs. specific site) we should carry?
3. Override 1 (no-PHI / example) needs **no** BAA — confirm nothing on your side gates the clean-ingest path.

Add your opinion here and reply to Extension (coordinator).

_(pending — Org agent)_
