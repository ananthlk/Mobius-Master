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
