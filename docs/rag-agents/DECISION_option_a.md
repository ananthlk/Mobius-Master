# Decision — Option A: make fetch‑to‑RAG usable on real payer content

**One decision, two coupled parts. Owner of the ask: Extension (lane coordinator).**
_2026-09-09 · full detail in `USER_FETCH_PAIRING_SPEC.md` §2.8 / §2.9_

> ## ⛔ OUTCOME — DEFERRED (Ananth's directive, relayed via PHI/compliance seat 2026‑09‑09; Extension to confirm in‑session)
> **"No user override trumps for now."** No user‑override‑ingests path ships — the gate stays **fail‑closed / hard‑block**. This holds BOTH overrides: the false‑positive override (Option A below) **and** the genuine‑PHI attestation‑admit (Ask 2, already parked behind the BAA).
> - **What this changes:** the deterministic precision fixes already shipped **stand** (references, Title‑Case headings, web‑nav chrome — those doc classes now ingest). What **still blocks**: docs whose remaining flags are a medical‑TITLE fragment or a corporate‑footer address/contact block (i.e. most real payer homepages). No override to clear those until Ananth green‑lights an override path (and the chat‑side admit infra / BAA exist).
> - **The override design is specced and build‑ready** (confidence‑tiered, deterministic, no LLM) — parked, not abandoned; the classifier pings when/if it's green‑lit.
> - The rest of this brief is retained as the record of what the decision was and why.

---

---

## The situation (3 lines)
- The browser‑extension "Add this document to Mobius" lane is **built and verified end‑to‑end** — capture → consent → PHI gate → provenance → corpus, confirmed from the DB.
- But the PHI classifier **false‑flags essentially every real payer web page.** Live proof: Ananth ran it on Molina's *public* FL Medicaid provider homepage → blocked on **7 categories** (Name, Address, Email, Phone, ZIP, Date, MRN) — all the site's own nav headings + corporate contact block, **zero patient data**.
- So the lane is **inert on real content** until this is fixed. This is the line between "demos" and "usable."

## The decision — bundled, one call
1. **Approve the caller‑scoped recall carve‑out** (Option A, below). It's a scoped exception to the fleet "names always flag" policy, so it needs your explicit nod.
2. **Name who writes chat's PHI‑adjacent code** while Chat Master is parked off PHI. Three items all need it and are otherwise blocked: (a) Option A's one‑field caller passthrough (chat gate → `/classify`); (b) the Ask‑2 two‑key admit path; (c) the HTML→text digit‑boundary fix (phantom SSN/MRN). One owner unblocks all three.

## What Option A is
`/classify` takes a **caller** hint. For `caller = browser-extension:user-fetch`, **low‑confidence, uncorroborated, heuristic‑only** findings (Name, Address, Email, Phone, ZIP, Date, MRN) become **LLM‑overridable** — the LLM pass that already runs clears them when it confirms the page is public provider/nav/contact content with no patient PHI. **Global default unchanged** (any other caller: names always flag).

## Why it's safe — the recall floor is preserved
Even on this caller, these **still hard‑block** (never overridable): Presidio‑detected names, clinical‑context names, all regex identifiers, real `XXX‑XX‑XXXX` SSNs, and the LLM's own patient‑detection. A real patient document mis‑routed to this lane still blocks on any of them; only a public page's own furniture gets cleared. No per‑document medical dictionary — it scales to every payer site.

## What "yes" unblocks (and who does it)
- **Classifier owner:** ready to build the caller‑scoped arbitration **the moment the caller field arrives** (their side is done pending it).
- **Chat‑side (the named owner):** one‑field caller passthrough — small.
- Same owner then also clears (b) Ask‑2 admit and (c) the extraction fix on their own tracks.
- **Extension:** nothing further — we already send the fields; verified.

## What "no / defer" means
The lane stays **demo‑only**: it cannot ingest real payer policy pages, because they all carry contact blocks and nav that trip the gate. The plumbing sits complete but unused.

## NOT this decision (separate gates, don't conflate)
- **BAA** → admitting *genuine* PHI via the two‑key toggle. Option A is for *false positives on public content*, not real PHI.
- **AMA CPT licence** → CPT‑bearing docs.
Both are additional gates; **Option A is the one that makes the feature work on ordinary public payer content**, which is the dominant case.

---

**Ask:** ☐ Approve Option A carve‑out ☐ Name the chat‑PHI owner → _______________  ·  Ananth / date: ________
