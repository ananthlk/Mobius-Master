# Fetch‑to‑RAG on real payer content — status, the fix path, and the REOPENED override question

_2026-09-09 · lane coordinator: Extension · full detail in `USER_FETCH_PAIRING_SPEC.md` §2.8/§2.9 · evidence in `molina_false_positive_evidence.md` + `regression_samples/`_

> **⚠ REOPENED 2026-09-09 (Ananth):** an override is back on the table. Trigger: a real, clean, public Molina provider-policy PDF (`regression_samples/molina_healthy_start_provider_reqs.pdf`) hard-blocks `gate:phi ['Name']` — a phantom Name (NER reading "Healthy Start"/proper-noun bigrams as people) on a doc with ZERO patient data. **`source_origin` does NOT clear it** (verified: survives removing Molina + Healthy Start + passing the origin), so deterministic origin-scoping can't reach this class. Ananth: _"that's why we have to have an override."_ The earlier "no override" ruling (§2.8) stands as the record of what was decided THEN; this section is the record of it being reopened NOW.
>
> **What "override" must mean here (to stay safe):** the shelf design — a **confidence-tiered, DETERMINISTIC (no-LLM) override** for the LOW-confidence heuristic-only class (Name/Address/Phone/etc. with no digits, no clinical patient-context, no corroboration), and **NEVER** for high-confidence PHI (Presidio-strong, clinical context, real SSN, LLM patient-detection). NOT a blanket user-trumps-everything, and DISTINCT from the genuine-PHI attestation admit (BAA/two-key, still separate). The override keys on **one gate-owned confidence field** (same shape as the classifier's `persist_allowed` proposal).
>
> **Open before Ananth re-decides:** (1) does the classifier emit / can it emit a per-detection confidence tier? (2) does this Healthy-Start sample land in the low-confidence overridable class? — both asked of the classifier owner 2026-09-09. (3) who owns the admit composition (extension signals → chat `/chat/upload` enforces). This is PHI-compliance-shaped → likely belongs with the block-not-stored 4-way, same seats.

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
_(pending — you defined `overridable`; confirm the doc captures it faithfully + any final caveat)_

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
Endorse. The card logic is a clean third lane over what already shipped (gate==phi & overridable → "false flag — add anyway" + lightweight "not patient data" log; gate==phi & !overridable → plain PHI card). No BAA dependency for this path. My only ask: the attestation log entry needs a stable shape (task_id, origin, doc hash, "not_patient_data" assertion, user) so the false-positive-override actions are auditable and can feed the classifier's overridable-class corpus. Ready to wire on green-light.

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
