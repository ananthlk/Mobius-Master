# Integration contract — appeals ↔ payor reference-data store

**Purpose:** pin the seam now so cutover is mechanical, not a negotiation, when the resolver lands.
**Status:** proposed by appeals · awaiting Payor Platform confirmation · **Step 0 is not complete until this is agreed and integrated.**

---

## 1. What appeals calls

```
resolve(
  payer_key,                   # canonical payer identity
  predicate,                   # appeal.deadline_days | appeal.levels | …
  product_line,                # medicaid_mco | marketplace_qhp | medicare_advantage | commercial | aso
  state,                       # FL
  network_status,              # contracted | non_contracted
  audience   = 'provider',     # DECLARED by appeals, never inferred
  party      = 'provider',     # DECLARED — filters ACTIONS, not just values
  appeal_level = <int|null>,
  as_of      = <denial_date>   # NEVER now()
) -> FactResolution
```

**Appeals always declares the full tuple.** An undeclared dimension must serve nothing — that is
the fail-closed rule generalised, and it is appeals' responsibility to declare, not the store's to
guess.

## 2. What appeals expects back

```jsonc
{
  "value":  <typed>,            // null when nothing resolves — never a guess, never a default
  "basis":  "regulatory|stated_policy|observed_claims|network_experience|stated_verbal|inferred|unverified",
  "citable": true|false,        // basis in (stated_policy, regulatory) — may be quoted IN an appeal letter
  "ref":    { "source": "...", "locator": "Provider Manual §8.4", "url": "...",
              "observed_on": "2026-01-01", "sample_n": null, "who": null },
  "effective_from": "2025-01-01", "effective_to": null,
  "resolved_by": { "specificity": [...bound dimensions...], "authority_rank": n,
                   "policy": "specificity_then_authority" },
  "conflict":  {                 // present ONLY when sourced values disagreed
      "candidates": [ {"value":90,"basis":"stated_policy","ref":{...}},
                      {"value":120,"basis":"regulatory","ref":{...}} ],
      "applied":   "shortest|longest|union|block",
      "floor_applied": true|false
  },
  "suppressed": null | "reason"  // e.g. "below citable bar for a filing-critical field"
}
```

**Three non-negotiables in the response shape:**
1. **`value: null` is a first-class answer.** Appeals renders an honest gap. It must never receive a
   default, a fallback, or a "best guess" — that is the failure class this store exists to end.
2. **`conflict` is surfaced, not resolved away.** Appeals shows the reviewer that three sourced
   values disagreed and which policy applied. A single number with the disagreement hidden is less
   trustworthy than the disagreement.
3. **`basis` + `citable` travel with every value.** Appeals decides render-vs-suppress from these,
   and the letter generator decides quote-vs-paraphrase. A value without its basis is unusable.

## 3. What appeals does with each result

| Store returns | Appeals behaviour |
|---|---|
| `citable: true` | render the value; **may be quoted inside the appeal letter** with its locator |
| `basis: observed_claims / network_experience` | render with provenance; **never quoted as policy** |
| `basis: stated_verbal` | usable to investigate and to **file early**; **never** establishes the outer bound of a deadline |
| `basis: unverified` or `value: null` on a **filing-critical** field | **suppress entirely** — removed, not labelled. A draft banner does not stop a coordinator acting on a number, and a wrong deadline loses the claim permanently |
| `conflict` present | render the resolved value **and** surface the conflict to the reviewer |
| party mismatch | action invisible, **unless** `requires_consent_artifact`, in which case it renders **with the artifact attached and never without it** |

Filing-critical set (as coded): `deadline_appeal_days`, `resubmit_deadline_days`,
`submission_channels`, `required_docs`, `levels`, plus `portal_url`/`fax`/`mail_address`.

## 4. Cutover — mechanical, one function

Appeals resolves every payor fact through **one seam**: `api/facts.py :: resolve_facts()`.
Cutover replaces that function body with a call to the store. Nothing else in appeals changes.

- [ ] Store exposes the resolver (any transport — HTTP is fine)
- [ ] Appeals swaps `resolve_facts()` internals
- [ ] Appeals retires `payor_playbooks` as a source of truth; it becomes a **cache or is dropped**
- [ ] The Postgres trigger guarantee moves to the store's table — **it must reject bad writes at
      YOUR table, from any endpoint**, because the legacy appeals write path is ratchet-locked in
      `app.py` and generation jobs bypass application code entirely
- [ ] Regression: the CARC 29 × Sunshine chat card renders identically, and the evidence audit
      reports the same or better

## 5. Acceptance — Step 0 is complete when
1. Resolver answers the §1 call with the §2 shape for **one payer × the appeal predicates**.
2. `03_fixture_wrong_party.json` passes at the store's table: (a) and (b) **rejected**, (c) the
   Medicare Advantage consent-artifact case **accepted**, (d) unsourced-duration **rejected**.
3. `02_fixture_divergence.json`: Sunshine's **14 fact signatures resolve to one**.
4. A fact sourced through the store's UI comes back `citable: true` with its locator, and appeals
   renders it — end to end, one predicate, one payer.
5. A fact with **no** source comes back `value: null` and appeals renders an honest gap.
6. Appeals' evidence audit reports `percent_citable > 0` for the first time.

## 6. Open — needs Payor Platform's answer
- Transport and auth for the resolver.
- Whether appeals keeps `payor_playbooks` as a read-through cache or drops it entirely.
- Who runs the migration of the 141 rows — and whether the 14 Sunshine variants are reconciled
  **by a human during sourcing** (my assumption) or programmatically.
- Batch shape: appeals needs ~6 predicates per card render; one call per predicate is chatty.
  A `resolve_many` taking a tuple + predicate list would be better.
