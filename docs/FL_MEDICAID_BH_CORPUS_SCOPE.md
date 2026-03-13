# FL Medicaid BH: Corpus Scope, Metadata, and Sourcing Plan

> **Day 4–5 deliverable.** Minimal document set and metadata schema for a viable Florida Medicaid behavioral health RAG system. Policy vs contract vs reference namespace considerations.

---

## 1. Metadata Schema (Namespace Design)

RAG currently exposes `document_payer`, `document_state`, `document_program`, `document_authority_level` on published embeddings. To distinguish **policy** (operational rules) from **contract** (legal/network terms) and **reference** (external standards), we propose an expanded metadata model.

### Proposed document metadata (for ingestion + filterability)

| Field | Type | Values / notes | Purpose |
|-------|------|----------------|---------|
| **document_type** | VARCHAR(50) | See table below | What kind of document (RAG filter, JPD scope) |
| **authority_type** | VARCHAR(30) | `policy` \| `contract` \| `regulatory` \| `reference` | Policy = operational rules; contract = legal/network; regulatory = state/fed; reference = external guidance |
| **source_publisher** | VARCHAR(50) | `payor` \| `state_agency` \| `federal_agency` | Who publishes (for retrieval confidence) |
| **payer** | VARCHAR(100) | Sunshine Health, Molina, UnitedHealthcare, (empty) | Payor-specific docs |
| **state** | VARCHAR(2) | FL, (empty) | State scope |
| **program** | VARCHAR(100) | Medicaid, MMA, SMI, CWSP, HIV/AIDS, (empty) | Program scope |
| **authority_level** | VARCHAR(100) | *(existing)* | Legacy; can map to authority_type |
| **effective_date** | VARCHAR(20) | ISO date | Versioning |
| **url** | VARCHAR(500) | Source URL | Traceability, re-scrape |

### document_type values (map to lexicon `p`)

| document_type | authority_type | Description |
|---------------|----------------|-------------|
| provider_manual | policy | Payor provider operations (auth, billing, claims) |
| member_handbook | policy | Member benefits, rights, grievance/appeals |
| clinical_policy | policy | UM, PA, medical necessity criteria |
| payment_policy | policy | Fee schedules, modifiers, code edits |
| pa_lookup | policy | Prior auth rules, checklists |
| contract | contract | Network agreement, legal terms (distinct from policy) |
| regulatory | regulatory | AHCA, CMS, state plan provisions |
| code_reference | reference | CPT/HCPCS/ICD coverage tables |
| web_scrape | policy/reference | Scraped web pages (payor, AHCA, etc.) |

**Policy vs contract:** Policy = “how to do X” (auth, billing, appeals). Contract = “agreement terms” (network participation, liability). Separate `document_type` and `authority_type` so retrieval can prefer policy for operational questions and contract for legal questions.

---

## 2. Minimal Viable Document Set (FL Medicaid BH)

### Tier 1 — Must have (Day 5–6)

| Doc | document_type | authority_type | source_publisher | payer | Where to source |
|-----|---------------|----------------|------------------|-------|-----------------|
| Sunshine provider manual | provider_manual | policy | payor | Sunshine Health | Payor portal / existing PDF |
| Sunshine member handbook | member_handbook | policy | payor | Sunshine Health | Payor portal |
| Sunshine clinical policy (BH) | clinical_policy | policy | payor | Sunshine Health | Payor portal / clinical policy list |
| Sunshine payment policy | payment_policy | policy | payor | Sunshine Health | Payor portal |
| Molina provider manual | provider_manual | policy | payor | Molina | Payor portal |
| United provider manual | provider_manual | policy | payor | UnitedHealthcare | Payor portal |
| AHCA provider requirements | regulatory | regulatory | state_agency | (empty) | [AHCA Medicaid Provider](https://ahca.myflorida.com/medicaid/) |
| AHCA coverage / state plan summary | regulatory | regulatory | state_agency | (empty) | AHCA site, state plan documents |
| FL Medicaid BH coverage summary | regulatory | regulatory | state_agency | (empty) | AHCA, DCF |

### Tier 2 — Should have (Week 2)

| Doc | document_type | authority_type | source_publisher | payer | Where to source |
|-----|---------------|----------------|------------------|-------|-----------------|
| SAMHSA BH/SUD guidance | code_reference / regulatory | reference | federal_agency | (empty) | [SAMHSA.gov](https://www.samhsa.gov/) |
| CMS Medicaid parity | regulatory | regulatory | federal_agency | (empty) | [CMS.gov](https://www.cms.gov/) |
| DCF CWSP / child welfare | regulatory | regulatory | state_agency | (empty) | [DCF](https://www.myflfamilies.com/) |
| Payor PA lookup / checklists | pa_lookup | policy | payor | * | Payor portals, embedded in manuals |
| Payor + AHCA website scans | web_scrape | policy | payor / state_agency | * | Scraper (clinical policies, FAQs) |

### Tier 3 — Nice to have

| Doc | document_type | authority_type | source_publisher | payer | Where to source |
|-----|---------------|----------------|------------------|-------|-----------------|
| SSA eligibility (SSI/SSDI) | code_reference | reference | federal_agency | (empty) | [SSA.gov](https://www.ssa.gov/) |
| Medicaid enrollment rules | regulatory | regulatory | state_agency | (empty) | AHCA, DCF |
| Credentialing / enrollment FAQs | provider_manual | policy | payor | * | Payor portals |
| CPT/HCPCS BH code reference | code_reference | reference | payor / federal | * | CMS, AMA; payor fee schedules |

---

## 3. Concrete Sourcing Plan

### Step 1: Payor manuals (Tier 1)

| Payor | Document | URL pattern / source | Format | Process |
|-------|----------|----------------------|--------|---------|
| Sunshine Health | Provider manual | `sunshinehealth.com` provider section | PDF | Download PDF → upload to RAG → tag payer=Sunshine, document_type=provider_manual, authority_type=policy |
| Sunshine Health | Member handbook | Member materials section | PDF | Same |
| Sunshine Health | Clinical policy (BH) | Clinical policy / UM section | PDF or web | Download or scrape list + PDFs |
| Sunshine Health | Payment policy | Billing / payment section | PDF | Download |
| Molina | Provider manual | `molinahealthcare.com` Florida Medicaid | PDF | Same pattern |
| United | Provider manual | `uhcprovider.com` Florida Medicaid | PDF | Same pattern |

**Action:** Create a `sourcing/` folder or sheet: one row per doc, columns = document_type, authority_type, payer, url, status (pending/ingested/failed).

### Step 2: AHCA (Tier 1)

| Document | URL | Format | Process |
|----------|-----|--------|---------|
| Provider enrollment / requirements | https://ahca.myflorida.com/medicaid/Provider_Enrollment/ | Web + PDF | Scrape key pages; download linked PDFs |
| Medicaid coverage / state plan | https://ahca.myflorida.com/medicaid/state_plan/ | PDF | Download state plan summary, BH sections |
| BH program info | AHCA Medicaid BH pages | Web | Scrape |

**Action:** Add AHCA docs to sourcing sheet; tag source_publisher=state_agency, authority_type=regulatory.

### Step 3: Federal / reference (Tier 2)

| Document | URL | Format | Process |
|----------|-----|--------|---------|
| SAMHSA BH/SUD guidance | https://www.samhsa.gov/ | Web, PDF | Scrape key BH/SUD pages; download relevant guides |
| CMS Medicaid parity | https://www.cms.gov/medicaid/mental-health | PDF, Web | Download parity guidance |
| DCF CWSP | https://www.myflfamilies.com/ | Web, PDF | Scrape CWSP/child welfare BH pages |

### Step 4: Web scrape (Tier 2)

| Target | Pages | Process |
|--------|-------|---------|
| Payor clinical policy index | Sunshine, Molina, United clinical policy lists | Scrape index; optionally scrape or PDF individual policies |
| AHCA provider FAQs | AHCA Medicaid provider pages | Scrape |
| Payor contact / forms | Provider portals | Scrape key contact and form pages |

**Action:** Use mobius-skills web-scraper; store as document_type=web_scrape, include url in metadata.

### Step 5: Code coverage (Tier 2–3)

| Source | Content | Process |
|--------|---------|---------|
| Payor fee schedules / code lists | CPT/HCPCS BH codes | Extract from payment policy or separate PDF |
| CMS NCCI / code rules | Code bundling, modifiers | Download or reference CMS docs |
| Diagnosis / medical necessity | From clinical policies | Often embedded; tag extracted sections |

---

## 4. RAG Schema Changes (If Needed)

Current `documents` and `rag_published_embeddings` have `payer`, `state`, `program`, `authority_level`. To support the new namespace:

1. **Add columns** (or extend `authority_level`):
   - `document_type` — provider_manual, member_handbook, clinical_policy, payment_policy, pa_lookup, contract, regulatory, code_reference, web_scrape
   - `authority_type` — policy, contract, regulatory, reference
   - `source_publisher` — payor, state_agency, federal_agency
   - `source_url` — optional, for traceability

2. **Migration path:** Add columns as nullable; backfill from display_name/filename heuristics or manual tagging; update ingestion to set them.

3. **Lexicon sync:** Ensure `p` tags in lexicon match `document_type` values; JPD tagger can use them for retrieval scoping.

---

## 5. Benchmarking / Data (Not RAG Corpus)

Benchmarking (KPIs, outcomes, utilization) is typically:
- **Analytics / marts** (mobius-dbt) — aggregated data, not full-text retrieval
- **Reference summaries** — e.g. “typical IOP length of stay” from reports; could be ingested as `code_reference` or `regulatory` if we have written benchmarks

For Day 5–6, treat benchmarking as out of scope for RAG corpus; add as Tier 3 if we get benchmark reports as PDFs.

---

## 6. Checklist (Day 4–5 execution)

- [ ] Add `document_type`, `authority_type`, `source_publisher` to RAG schema (or document mapping in ingestion)
- [ ] Create sourcing spreadsheet/sheet: doc name, document_type, payer, url, status
- [ ] Source Tier 1: Sunshine provider manual, member handbook, clinical + payment policy; Molina + United provider manuals
- [ ] Source Tier 1: AHCA provider requirements, coverage/state plan summary
- [ ] Ingest with correct metadata; verify filterable by payer, document_type
- [ ] Run lexicon sync; verify JPD returns j_tags for sample questions
- [ ] Source Tier 2: SAMHSA, CMS parity, DCF; payor web scrapes

---

## 7. References

- `mobius-rag/docs/CONTRACT_DBT_RAG.md` — published embeddings schema
- `mobius-rag/app/models.py` — Document model
- `docs/LEXICON_AUDIT_CHECKLIST.md` — J/P/D tags and gaps
- V1 plan: Day 5 corpus + lexicon, Day 6 AHCA + 10 plans
