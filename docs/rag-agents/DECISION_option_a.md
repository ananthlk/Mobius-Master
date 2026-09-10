# Fetch‑to‑RAG on real payer content — status & the fix path (NOT a pending override decision)

_2026-09-09 · lane coordinator: Extension · full detail in `USER_FETCH_PAIRING_SPEC.md` §2.8/§2.9 · evidence in `molina_false_positive_evidence.md`_

> **Read this first:** an earlier draft framed an "Option A" LLM/override for Ananth to approve. **Ananth already ruled against that**, and the classifier owner agrees it's the wrong tool. This page is now the accurate record. **No decision is required here** — the fix is a build already underway.

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
