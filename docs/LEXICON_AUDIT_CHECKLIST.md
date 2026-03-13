# Lexicon Audit Checklist (V1 Day 4)

Use this checklist to audit the lexicon for RAG/Chat: entries, J/P/D tags, and gaps. Deliverable: list of terms to add/fix and missing payers, doc types, AHCA coverage.

---

## 1. Current lexicon structure

- **Source:** `mobius-qa/lexicon-maintenance` — API, DB, `app/scripts/reload_clean_lexicon.py`
- **Kinds:** `j` (jurisdiction), `d` (domain), `p` (document/policy type)
- **Format:** Domain (e.g. `payor`) → Tag (e.g. `payor.sunshine_health`); tags have `strong_phrases`, `aliases`, `refuted_words`, etc.

### J (Jurisdiction) — WHO/WHERE

| Domain / tag | Purpose |
|--------------|---------|
| `state`, `state.florida` | State scope |
| `payor`, `payor.molina_healthcare`, `payor.sunshine_health`, `payor.unitedhealthcare` | Payers (3 plans) |
| `program`, `program.medicaid`, `program.mma`, `program.smi`, etc. | Programs (MMA, SMI, LTC, CWSP, HIV/AIDS) |
| `provider`, `provider.child_welfare` | Provider type |
| `regulatory_authority`, `regulatory_authority.ahca`, `.cms`, `.dcf`, `.fbha`, `.gsa`, `.hhs`, `.oig`, `.ssa` | Agencies (AHCA, CMS, DCF, etc.) |

### D (Domain) — topic

- **Claims:** general, submission, denial, timely_filing, clean_claim, corrected_claims, electronic/paper, billing_forms, COB, appeals_grievances, payer_id
- **Eligibility:** general, enrollment, verification, member_status, plan_assignment
- **Pharmacy:** general, PDL, specialty_pharmacy, controlled_substances, DUR, pharmacy_benefit
- **Compliance:** general, HIPAA, FWA, audits, confidentiality, nondiscrimination
- (Additional domains in `reload_clean_lexicon.py`)

### P (Document / policy type)

- Defined in same script; used for document_type tagging.

---

## 2. Gaps to document

- [ ] **Payers:** Current: Sunshine, Molina, UnitedHealthcare. Missing for 10-plan target? (List plans to add.)
- [ ] **Doc types:** V1 expects 6: provider_manual, member_manual, clinical_policy, payment_policy, pa_lookup, web_scrape. Map to lexicon `p` codes; note any missing.
- [ ] **AHCA:** `regulatory_authority.ahca` exists. Confirm strong_phrases/aliases cover AHCA docs and FL regulatory questions.
- [ ] **State/region:** Only `state.florida`; add others if scope expands.
- [ ] **New programs or agencies:** Any programs/agencies in new docs not yet in lexicon.

---

## 3. Terms to add/fix (running list)

| Term or phrase | Kind | Action (add / fix / alias) | Notes |
|----------------|------|----------------------------|--------|
| _(add rows as audit finds gaps)_ | j/d/p | | |

---

## 4. Sync and verification

- [ ] Run `reload_clean_lexicon.py` (or API equivalent) after edits.
- [ ] Sync QA → RAG → Chat per project docs (`sync_qa_lexicon_to_rag`, `sync_rag_lexicon_to_chat`).
- [ ] **Gate:** JPD tagger returns `j_tags` for sample questions on new plans (Day 5/8).

---

## 5. References

- `mobius-qa/lexicon-maintenance/app/scripts/reload_clean_lexicon.py` — canonical entry list
- `mobius-retriever` jpd_tagger — consumes lexicon for retrieval scoping
- [FL_MEDICAID_BH_CORPUS_SCOPE.md](FL_MEDICAID_BH_CORPUS_SCOPE.md) — corpus scope, metadata schema (policy vs contract), sourcing plan
- V1 plan: Day 6 audit, Day 8 updates, Day 11 retagging, Day 22 staging sync
