# BM25 Pipeline Report (9 Questions) — Detailed

Flow: Pre-ranking (BM25) → Rerank (by component) → Assembly (confidence, Google).

---


## Summary

| ID | Question | Pre (BM25) | Post rerank | Kept | Final | best | Decision |
|----|----------|------------|-------------|------|-------|------|----------|
| dev_001 | What is the prior authorization requiremen... | 0 | 0 | 0 | 5 | 0.000 | Google only |
| dev_002 | What phone number do pharmacies call for E... | 6 | 6 | 6 | 6 | 0.865 | corpus only |
| dev_003 | Summarize the key guidance in the provider... | 0 | 0 | 0 | 5 | 0.000 | Google only |
| dev_004 | What is the 72-hour emergency medication s... | 24 | 24 | 24 | 29 | 0.687 | corpus + Google |
| dev_005 | How can a provider determine whether a ser... | 0 | 0 | 0 | 5 | 0.000 | Google only |
| dev_006 | What are the weekend and after-hours on-ca... | 4 | 4 | 4 | 4 | 0.854 | corpus only |
| dev_007 | Summarize the Secure Provider Portal regis... | 0 | 0 | 0 | 5 | 0.000 | Google only |
| dev_008 | What is the process for claims reconsidera... | 14 | 14 | 14 | 19 | 0.846 | corpus + Google |
| dev_009 | What is the Medicare Part B prior authoriz... | 1 | 1 | 0 | 5 | 0.443 | Google only |

---

## dev_001: What is the prior authorization requirement for physical therapy in...

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| *(none)* | | | | | |

### 2. Rerank: effect by component

*(Reranker not run; using BM25 order)*

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|

**Assembly decision:**
  best_score=0.000 → low confidence → Google only
  filter_abstain: 0 → 0 kept

  Google fallback: 5 external results added
    1. Florida Medicaid - The Agency for Health Care A...
    2. Habilitation and Rehabilitation Therapy (Occupa...
    3. Florida Physical Therapy Laws and Regulations -...

**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | abstain | 0.000 | Medicaid Prior Authorization Form for Phys... |
| 2 | abstain | 0.000 | Prior authorization for outpatient therapy... |
| 3 | abstain | 0.000 | Florida Board of Physical Therapy » Practi... |
| 4 | abstain | 0.000 | Do You Need a Referral for Physical Therap... |
| 5 | abstain | 0.000 | License Requirements - May 1, 2025 - BACKG... |

---

## dev_002: What phone number do pharmacies call for Express Scripts help desk?

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| 1 | `3b543bcb-8074-49...` | Sunshine Provider Manual | 27.588 | 0.978 | paragraph |
| 2 | `8c267e1c-7719-4a...` | Sunshine Provider Manual | 27.588 | 0.978 | paragraph |
| 3 | `d05bfd4f-43e7-4c...` | Sunshine Provider Manual | 27.588 | 0.978 | paragraph |
| 4 | `3b543bcb-8074-49...` | Sunshine Provider Manual | 40.068 | 1.000 | sentence |
| 5 | `8c267e1c-7719-4a...` | Sunshine Provider Manual | 40.068 | 1.000 | sentence |
| 6 | `d05bfd4f-43e7-4c...` | Sunshine Provider Manual | 40.068 | 1.000 | sentence |

### 2. Rerank: effect by component

**Before rerank (id, similarity):**
  1. id=3b543bcb-8074-49... sim=0.978 doc=Sunshine Provider Manual
  2. id=8c267e1c-7719-4a... sim=0.978 doc=Sunshine Provider Manual
  3. id=d05bfd4f-43e7-4c... sim=0.978 doc=Sunshine Provider Manual
  4. id=3b543bcb-8074-49... sim=1.000 doc=Sunshine Provider Manual
  5. id=8c267e1c-7719-4a... sim=1.000 doc=Sunshine Provider Manual
  6. id=d05bfd4f-43e7-4c... sim=1.000 doc=Sunshine Provider Manual

**After rerank (new order, rerank_score):**
  1. id=3b543bcb-8074-49... rerank=0.864
  2. id=8c267e1c-7719-4a... rerank=0.864
  3. id=d05bfd4f-43e7-4c... rerank=0.864
  4. id=3b543bcb-8074-49... rerank=0.856
  5. id=8c267e1c-7719-4a... rerank=0.856
  6. id=d05bfd4f-43e7-4c... rerank=0.856

**Per-chunk signal contribution (top 5):**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  - id=3b543bcb-8074-49... **rerank_score=0.8645**
      score: raw=1.0 norm=1.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=8c267e1c-7719-4a... **rerank_score=0.8645**
      score: raw=1.0 norm=1.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=d05bfd4f-43e7-4c... **rerank_score=0.8645**
      score: raw=1.0 norm=1.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=3b543bcb-8074-49... **rerank_score=0.8562**
      score: raw=0.978 norm=0.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=8c267e1c-7719-4a... **rerank_score=0.8562**
      score: raw=0.978 norm=0.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|
| `3b543bcb-8074-49...` | Sunshine Provider Manual | 0.865 | process_confident | Likely correct; verify no c... |
| `8c267e1c-7719-4a...` | Sunshine Provider Manual | 0.865 | process_confident | Likely correct; verify no c... |
| `d05bfd4f-43e7-4c...` | Sunshine Provider Manual | 0.865 | process_confident | Likely correct; verify no c... |
| `3b543bcb-8074-49...` | Sunshine Provider Manual | 0.856 | process_confident | Likely correct; verify no c... |
| `8c267e1c-7719-4a...` | Sunshine Provider Manual | 0.856 | process_confident | Likely correct; verify no c... |
| `d05bfd4f-43e7-4c...` | Sunshine Provider Manual | 0.856 | process_confident | Likely correct; verify no c... |

**Assembly decision:**
  best_score=0.865 → corpus only (no Google)
  filter_abstain: 6 → 6 kept


**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.865 | Pharmacies may call the Express Scripts he... |
| 2 | process_confident | 0.865 | Pharmacies may call the Express Scripts he... |
| 3 | process_confident | 0.865 | Pharmacies may call the Express Scripts he... |
| 4 | process_confident | 0.856 | Sunshine Health covers prescription drugs ... |
| 5 | process_confident | 0.856 | Sunshine Health covers prescription drugs ... |
| 6 | process_confident | 0.856 | Sunshine Health covers prescription drugs ... |

---

## dev_003: Summarize the key guidance in the provider manual section "Medicaid...

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| *(none)* | | | | | |

### 2. Rerank: effect by component

*(Reranker not run; using BM25 order)*

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|

**Assembly decision:**
  best_score=0.000 → low confidence → Google only
  filter_abstain: 0 → 0 kept

  Google fallback: 5 external results added
    1. 2026 Care Provider Manual for Florida Statewide...
    2. Information for Providers - The Agency for Heal...
    3. Provider Manual (Provider Handbook) - Molina He...

**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | abstain | 0.000 | PDF Provider Manual - Sunshine Health Medi... |
| 2 | abstain | 0.000 | [PDF] CCP-Medicaid-and-SMI-Provider ... Me... |
| 3 | abstain | 0.000 | [PDF] Medicaid Eligibility, Enrollment, an... |
| 4 | abstain | 0.000 | [PDF] Medicaid Provider Rate Setting Study... |
| 5 | abstain | 0.000 | [PDF] Medicaid Managed Long-Term Care in F... |

---

## dev_004: What is the 72-hour emergency medication supply policy?

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| 1 | `4f4a79c5-2f96-40...` | Sunshine Provider Manual | 35.460 | 1.000 | paragraph |
| 2 | `bdca20a8-a22b-49...` | Sunshine Provider Manual | 35.460 | 1.000 | paragraph |
| 3 | `e966e52d-90c3-4a...` | Sunshine Provider Manual | 35.460 | 1.000 | paragraph |
| 4 | `49e59ab8-e5f8-4a...` | Sunshine Provider Manual | 22.838 | 0.805 | paragraph |
| 5 | `beae8b4c-5e70-4f...` | Sunshine Provider Manual | 22.838 | 0.805 | paragraph |
| 6 | `ed80a444-97dc-47...` | Sunshine Provider Manual | 22.838 | 0.805 | paragraph |
| 7 | `6b9bd6ea-bda6-44...` | Sunshine Provider Manual | 21.549 | 0.684 | paragraph |
| 8 | `ff434374-0947-40...` | Sunshine Provider Manual | 21.549 | 0.684 | paragraph |
| 9 | `6b9bd6ea-bda6-44...` | Sunshine Provider Manual | 36.140 | 1.000 | sentence |
| 10 | `ff434374-0947-40...` | Sunshine Provider Manual | 36.140 | 1.000 | sentence |
| 11 | `6b9bd6ea-bda6-44...` | Sunshine Provider Manual | 28.333 | 0.985 | sentence |
| 12 | `ff434374-0947-40...` | Sunshine Provider Manual | 28.333 | 0.985 | sentence |
| 13 | `4f4a79c5-2f96-40...` | Sunshine Provider Manual | 26.544 | 0.963 | sentence |
| 14 | `bdca20a8-a22b-49...` | Sunshine Provider Manual | 26.544 | 0.963 | sentence |
| 15 | `e966e52d-90c3-4a...` | Sunshine Provider Manual | 26.544 | 0.963 | sentence |

### 2. Rerank: effect by component

**Before rerank (id, similarity):**
  1. id=4f4a79c5-2f96-40... sim=1.000 doc=Sunshine Provider Manual
  2. id=bdca20a8-a22b-49... sim=1.000 doc=Sunshine Provider Manual
  3. id=e966e52d-90c3-4a... sim=1.000 doc=Sunshine Provider Manual
  4. id=49e59ab8-e5f8-4a... sim=0.805 doc=Sunshine Provider Manual
  5. id=beae8b4c-5e70-4f... sim=0.805 doc=Sunshine Provider Manual
  6. id=ed80a444-97dc-47... sim=0.805 doc=Sunshine Provider Manual
  7. id=6b9bd6ea-bda6-44... sim=0.684 doc=Sunshine Provider Manual
  8. id=ff434374-0947-40... sim=0.684 doc=Sunshine Provider Manual
  9. id=6b9bd6ea-bda6-44... sim=1.000 doc=Sunshine Provider Manual
  10. id=ff434374-0947-40... sim=1.000 doc=Sunshine Provider Manual

**After rerank (new order, rerank_score):**
  1. id=6b9bd6ea-bda6-44... rerank=0.687
  2. id=ff434374-0947-40... rerank=0.687
  3. id=4f4a79c5-2f96-40... rerank=0.687
  4. id=bdca20a8-a22b-49... rerank=0.687
  5. id=e966e52d-90c3-4a... rerank=0.687
  6. id=6b9bd6ea-bda6-44... rerank=0.682
  7. id=ff434374-0947-40... rerank=0.682
  8. id=4f4a79c5-2f96-40... rerank=0.674
  9. id=bdca20a8-a22b-49... rerank=0.674
  10. id=e966e52d-90c3-4a... rerank=0.674

**Per-chunk signal contribution (top 5):**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  - id=6b9bd6ea-bda6-44... **rerank_score=0.6874**
      score: raw=0.9997 norm=1.0 weight=0.3
      tag_match: raw=0.0 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=ff434374-0947-40... **rerank_score=0.6874**
      score: raw=0.9997 norm=1.0 weight=0.3
      tag_match: raw=0.0 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=4f4a79c5-2f96-40... **rerank_score=0.6873**
      score: raw=0.9996 norm=0.9996 weight=0.3
      tag_match: raw=0.0 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=bdca20a8-a22b-49... **rerank_score=0.6873**
      score: raw=0.9996 norm=0.9996 weight=0.3
      tag_match: raw=0.0 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=e966e52d-90c3-4a... **rerank_score=0.6873**
      score: raw=0.9996 norm=0.9996 weight=0.3
      tag_match: raw=0.0 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|
| `6b9bd6ea-bda6-44...` | Sunshine Provider Manual | 0.687 | process_with_caution | Use but reconcile across docs |
| `ff434374-0947-40...` | Sunshine Provider Manual | 0.687 | process_with_caution | Use but reconcile across docs |
| `4f4a79c5-2f96-40...` | Sunshine Provider Manual | 0.687 | process_with_caution | Use but reconcile across docs |
| `bdca20a8-a22b-49...` | Sunshine Provider Manual | 0.687 | process_with_caution | Use but reconcile across docs |
| `e966e52d-90c3-4a...` | Sunshine Provider Manual | 0.687 | process_with_caution | Use but reconcile across docs |
| `6b9bd6ea-bda6-44...` | Sunshine Provider Manual | 0.682 | process_with_caution | Use but reconcile across docs |
| `ff434374-0947-40...` | Sunshine Provider Manual | 0.682 | process_with_caution | Use but reconcile across docs |
| `4f4a79c5-2f96-40...` | Sunshine Provider Manual | 0.674 | process_with_caution | Use but reconcile across docs |
| `bdca20a8-a22b-49...` | Sunshine Provider Manual | 0.674 | process_with_caution | Use but reconcile across docs |
| `e966e52d-90c3-4a...` | Sunshine Provider Manual | 0.674 | process_with_caution | Use but reconcile across docs |

**Assembly decision:**
  best_score=0.687 → corpus + Google complement
  filter_abstain: 24 → 24 kept

  Google complement: 5 external results appended

**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.687 | 111 72-Hour Emergency Supply Policy ......... |
| 2 | process_with_caution | 0.687 | 111 72-Hour Emergency Supply Policy ......... |
| 3 | process_with_caution | 0.687 | 72-Hour Emergency Supply Policy  State law... |
| 4 | process_with_caution | 0.687 | 72-Hour Emergency Supply Policy  State law... |
| 5 | process_with_caution | 0.687 | 72-Hour Emergency Supply Policy  State law... |
| 6 | process_with_caution | 0.682 | 111 Exclusions to the 72-Hour Emergency Su... |
| 7 | process_with_caution | 0.682 | 111 Exclusions to the 72-Hour Emergency Su... |
| 8 | process_with_caution | 0.674 | 72-Hour Emergency Supply Policy State law ... |

---

## dev_005: How can a provider determine whether a service requires prior autho...

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| *(none)* | | | | | |

### 2. Rerank: effect by component

*(Reranker not run; using BM25 order)*

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|

**Assembly decision:**
  best_score=0.000 → low confidence → Google only
  filter_abstain: 0 → 0 kept

  Google fallback: 5 external results added
    1. The When and How of Prior Authorization
    2. Prior Authorization and Pre-Claim Review Initia...
    3. Fixing prior auth: Clear up what's required and...

**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | abstain | 0.000 | Prior Authorization and Pre-Claim Review I... |
| 2 | abstain | 0.000 | The When and How of Prior Authorization - ... |
| 3 | abstain | 0.000 | Prior Authorization Workflow: A Step-by-St... |
| 4 | abstain | 0.000 | 2024 Prior Authorization (PA) State Law Ch... |
| 5 | abstain | 0.000 | Prior authorization: What is it, when migh... |

---

## dev_006: What are the weekend and after-hours on-call phone numbers?

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| 1 | `0d9f9c4a-48c2-47...` | Sunshine Provider Manual | 26.731 | 0.967 | paragraph |
| 2 | `1fd0dbe8-660a-44...` | Sunshine Provider Manual | 26.731 | 0.967 | paragraph |
| 3 | `0d9f9c4a-48c2-47...` | Sunshine Provider Manual | 27.059 | 0.972 | sentence |
| 4 | `1fd0dbe8-660a-44...` | Sunshine Provider Manual | 27.059 | 0.972 | sentence |

### 2. Rerank: effect by component

**Before rerank (id, similarity):**
  1. id=0d9f9c4a-48c2-47... sim=0.967 doc=Sunshine Provider Manual
  2. id=1fd0dbe8-660a-44... sim=0.967 doc=Sunshine Provider Manual
  3. id=0d9f9c4a-48c2-47... sim=0.972 doc=Sunshine Provider Manual
  4. id=1fd0dbe8-660a-44... sim=0.972 doc=Sunshine Provider Manual

**After rerank (new order, rerank_score):**
  1. id=0d9f9c4a-48c2-47... rerank=0.854
  2. id=1fd0dbe8-660a-44... rerank=0.854
  3. id=0d9f9c4a-48c2-47... rerank=0.852
  4. id=1fd0dbe8-660a-44... rerank=0.852

**Per-chunk signal contribution (top 5):**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  - id=0d9f9c4a-48c2-47... **rerank_score=0.8538**
      score: raw=0.9715 norm=1.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=1fd0dbe8-660a-44... **rerank_score=0.8538**
      score: raw=0.9715 norm=1.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=0d9f9c4a-48c2-47... **rerank_score=0.8520**
      score: raw=0.9666 norm=0.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=1fd0dbe8-660a-44... **rerank_score=0.8520**
      score: raw=0.9666 norm=0.0 weight=0.3
      tag_match: raw=0.5664 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|
| `0d9f9c4a-48c2-47...` | Sunshine Provider Manual | 0.854 | process_confident | Likely correct; verify no c... |
| `1fd0dbe8-660a-44...` | Sunshine Provider Manual | 0.854 | process_confident | Likely correct; verify no c... |
| `0d9f9c4a-48c2-47...` | Sunshine Provider Manual | 0.852 | process_confident | Likely correct; verify no c... |
| `1fd0dbe8-660a-44...` | Sunshine Provider Manual | 0.852 | process_confident | Likely correct; verify no c... |

**Assembly decision:**
  best_score=0.854 → corpus only (no Google)
  filter_abstain: 4 → 4 kept


**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.854 | Weekend and After-Hours on Call-Number (fo... |
| 2 | process_confident | 0.854 | Weekend and After-Hours on Call-Number (fo... |
| 3 | process_confident | 0.852 | The utilization management department is s... |
| 4 | process_confident | 0.852 | The utilization management department is s... |

---

## dev_007: Summarize the Secure Provider Portal registration process.

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| *(none)* | | | | | |

### 2. Rerank: effect by component

*(Reranker not run; using BM25 order)*

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|

**Assembly decision:**
  best_score=0.000 → low confidence → Google only
  filter_abstain: 0 → 0 kept

  Google fallback: 5 external results added
    1. User Guide_Provider Portal: Registration User G...
    2. Provider Resources - securhealthplan.com
    3. Provider portal registration | UHCprovider.com

**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | abstain | 0.000 | 5 Key Characteristics of a Successful Deal... |
| 2 | abstain | 0.000 | 5 Best Mental Health Software: The Definit... |
| 3 | abstain | 0.000 | Build an event registration portal with Po... |
| 4 | abstain | 0.000 | 8 Starz — Official 888Starz Portal for Cas... |
| 5 | abstain | 0.000 | Accounts Payable: Process more efficiently... |

---

## dev_008: What is the process for claims reconsiderations and disputes?

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| 1 | `4335c5e8-619a-42...` | Sunshine Provider Manual | 26.770 | 0.967 | paragraph |
| 2 | `51f9d9fb-67b0-42...` | Sunshine Provider Manual | 26.770 | 0.967 | paragraph |
| 3 | `a690fcc0-0aa6-47...` | Sunshine Provider Manual | 26.770 | 0.967 | paragraph |
| 4 | `2368270f-2be4-4d...` | Sunshine Provider Manual | 26.164 | 0.956 | paragraph |
| 5 | `c56a3461-2085-48...` | Sunshine Provider Manual | 26.164 | 0.956 | paragraph |
| 6 | `571bda6e-8536-4b...` | Sunshine Provider Manual | 20.803 | 0.599 | paragraph |
| 7 | `9ae8997d-69d7-43...` | Sunshine Provider Manual | 20.803 | 0.599 | paragraph |
| 8 | `9e3c9408-28bb-40...` | Sunshine Provider Manual | 20.803 | 0.599 | paragraph |
| 9 | `66b378b8-a1d5-47...` | Sunshine Provider Manual | 20.001 | 0.500 | paragraph |
| 10 | `e6f59c42-251e-47...` | Sunshine Provider Manual | 20.001 | 0.500 | paragraph |
| 11 | `66b378b8-a1d5-47...` | Sunshine Provider Manual | 26.912 | 0.969 | sentence |
| 12 | `e6f59c42-251e-47...` | Sunshine Provider Manual | 26.912 | 0.969 | sentence |
| 13 | `2368270f-2be4-4d...` | Sunshine Provider Manual | 26.912 | 0.969 | sentence |
| 14 | `c56a3461-2085-48...` | Sunshine Provider Manual | 26.912 | 0.969 | sentence |

### 2. Rerank: effect by component

**Before rerank (id, similarity):**
  1. id=4335c5e8-619a-42... sim=0.967 doc=Sunshine Provider Manual
  2. id=51f9d9fb-67b0-42... sim=0.967 doc=Sunshine Provider Manual
  3. id=a690fcc0-0aa6-47... sim=0.967 doc=Sunshine Provider Manual
  4. id=2368270f-2be4-4d... sim=0.956 doc=Sunshine Provider Manual
  5. id=c56a3461-2085-48... sim=0.956 doc=Sunshine Provider Manual
  6. id=571bda6e-8536-4b... sim=0.599 doc=Sunshine Provider Manual
  7. id=9ae8997d-69d7-43... sim=0.599 doc=Sunshine Provider Manual
  8. id=9e3c9408-28bb-40... sim=0.599 doc=Sunshine Provider Manual
  9. id=66b378b8-a1d5-47... sim=0.500 doc=Sunshine Provider Manual
  10. id=e6f59c42-251e-47... sim=0.500 doc=Sunshine Provider Manual

**After rerank (new order, rerank_score):**
  1. id=2368270f-2be4-4d... rerank=0.846
  2. id=c56a3461-2085-48... rerank=0.846
  3. id=2368270f-2be4-4d... rerank=0.841
  4. id=c56a3461-2085-48... rerank=0.841
  5. id=66b378b8-a1d5-47... rerank=0.784
  6. id=e6f59c42-251e-47... rerank=0.784
  7. id=4335c5e8-619a-42... rerank=0.783
  8. id=51f9d9fb-67b0-42... rerank=0.783
  9. id=a690fcc0-0aa6-47... rerank=0.783
  10. id=571bda6e-8536-4b... rerank=0.645

**Per-chunk signal contribution (top 5):**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  - id=2368270f-2be4-4d... **rerank_score=0.8460**
      score: raw=0.9694 norm=1.0 weight=0.3
      tag_match: raw=0.544 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=c56a3461-2085-48... **rerank_score=0.8460**
      score: raw=0.9694 norm=1.0 weight=0.3
      tag_match: raw=0.544 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=2368270f-2be4-4d... **rerank_score=0.8410**
      score: raw=0.9561 norm=0.9717 weight=0.3
      tag_match: raw=0.544 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=c56a3461-2085-48... **rerank_score=0.8410**
      score: raw=0.9561 norm=0.9717 weight=0.3
      tag_match: raw=0.544 norm=1.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1
  - id=66b378b8-a1d5-47... **rerank_score=0.7837**
      score: raw=0.9694 norm=1.0 weight=0.3
      tag_match: raw=0.3444 norm=0.0 weight=0.25
      authority_level: raw=1.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|
| `2368270f-2be4-4d...` | Sunshine Provider Manual | 0.846 | process_with_caution | Use but reconcile across docs |
| `c56a3461-2085-48...` | Sunshine Provider Manual | 0.846 | process_with_caution | Use but reconcile across docs |
| `2368270f-2be4-4d...` | Sunshine Provider Manual | 0.841 | process_with_caution | Use but reconcile across docs |
| `c56a3461-2085-48...` | Sunshine Provider Manual | 0.841 | process_with_caution | Use but reconcile across docs |
| `66b378b8-a1d5-47...` | Sunshine Provider Manual | 0.784 | process_with_caution | Use but reconcile across docs |
| `e6f59c42-251e-47...` | Sunshine Provider Manual | 0.784 | process_with_caution | Use but reconcile across docs |
| `4335c5e8-619a-42...` | Sunshine Provider Manual | 0.783 | process_with_caution | Use but reconcile across docs |
| `51f9d9fb-67b0-42...` | Sunshine Provider Manual | 0.783 | process_with_caution | Use but reconcile across docs |
| `a690fcc0-0aa6-47...` | Sunshine Provider Manual | 0.783 | process_with_caution | Use but reconcile across docs |
| `571bda6e-8536-4b...` | Sunshine Provider Manual | 0.645 | process_with_caution | Use but reconcile across docs |

**Assembly decision:**
  best_score=0.846 → corpus + Google complement
  filter_abstain: 14 → 14 kept

  Google complement: 5 external results appended

**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.846 | ➢ See Process for Claims Reconsiderations ... |
| 2 | process_with_caution | 0.846 | ➢ See Process for Claims Reconsiderations ... |
| 3 | process_with_caution | 0.841 | ➢ See Process for Claims Reconsiderations ... |
| 4 | process_with_caution | 0.841 | ➢ See Process for Claims Reconsiderations ... |
| 5 | process_with_caution | 0.784 | 125 Process for Claims Reconsiderations an... |
| 6 | process_with_caution | 0.784 | 125 Process for Claims Reconsiderations an... |
| 7 | process_with_caution | 0.783 | Providers must include the original claim ... |
| 8 | process_with_caution | 0.783 | Providers must include the original claim ... |

---

## dev_009: What is the Medicare Part B prior authorization process in California?

### 1. Pre-ranking (BM25 retrieved)

| Rank | Chunk ID | Doc | raw_score | match_score | provision |
|------|----------|-----|-----------|-------------|-----------|
| 1 | `e9ea1bbc-358a-4e...` | document | 20.475 | 0.559 | paragraph |

### 2. Rerank: effect by component

**Before rerank (id, similarity):**
  1. id=e9ea1bbc-358a-4e... sim=0.559 doc=document

**After rerank (new order, rerank_score):**
  1. id=e9ea1bbc-358a-4e... rerank=0.443

**Per-chunk signal contribution (top 5):**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  - id=e9ea1bbc-358a-4e... **rerank_score=0.4427**
      score: raw=0.559 norm=1.0 weight=0.3
      tag_match: raw=0.3457 norm=1.0 weight=0.25
      authority_level: raw=0.0 norm=1.0 weight=0.15
      length: raw=1.0 norm=1.0 weight=0.1

### 3. Assembly

**assign_confidence (rerank_score → label):**
| Chunk ID | Doc | rerank_score | confidence_label | llm_guidance |
|----------|-----|--------------|------------------|--------------|
| `e9ea1bbc-358a-4e...` | document | 0.443 | abstain | Do not send |

**Assembly decision:**
  best_score=0.443 → low confidence → Google only
  filter_abstain: 1 → 0 kept

  Google fallback: 5 external results added
    1. Prior Authorizations (Part B) - Portal Guide - ...
    2. PDF Analysis Prior Authorization in California ...
    3. Prior Authorization and Pre-Claim Review Initia...

**Final sent to LLM:**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | abstain | 0.000 | Signs Medicare Advantage Isn't Working for... |
| 2 | abstain | 0.000 | Medicare Advantage + prior authorizations ... |
| 3 | abstain | 0.000 | AI reviews rolling out for Medicare in Was... |
| 4 | abstain | 0.000 | How to Do Prior Authorization Cover My Med... |
| 5 | abstain | 0.000 | MGMA Statement on Proposed Prior Authoriza... |
