# Dev Retrieval Report

JPD + BM25 + Vector retrieval on eval_questions_dev.yaml.

**Note on sentence vs paragraph BM25:** Sentence-level BM25 tends to outperform paragraph-level for fact-based queries.

---

## Summary: Golden Answer in Top 1 / Top 3

| ID | Question | Golden | BM25 Sent Top1 | In1 | In3 | BM25 Para Top1 | In1 | In3 | Vec Para Top1 | In1 | In3 |
|----|----------|--------|----------------|-----|-----|----------------|-----|-----|---------------|-----|-----|
| dev_001 | What is the prior authorization requirement for... | — | Prior authorization is required for voluntary... | — | — | 72-Hour Emergency Supply Policy  State law... | — | — | Providers should refer to the Pre-Auth Check... | — | — |
| dev_002 | What phone number do pharmacies call for Express.. | — | Pharmacies may call the Express Scripts help... | — | — | Sunshine Health covers prescription drugs and... | — | — | Non-Specialty/Retail Medications  To... | — | — |
| dev_003 | Summarize the key guidance in the provider manual. | — | The Florida Medicaid provider requirements for... | — | — | The table listed in this section includes all... | — | — | Provider Demographic Updates... | — | — |
| dev_004 | What is the 72-hour emergency medication supply po | — | 111 72-Hour Emergency Supply Policy... | — | — | 72-Hour Emergency Supply Policy  State law... | — | — | 72-Hour Emergency Supply Policy  State law... | — | — |
| dev_005 | How can a provider determine whether a service... | — | Providers should use the Pre-Auth Check Tool... | — | — | 72-Hour Emergency Supply Policy  State law... | — | — | and Prior Authorization  Utilization... | — | — |
| dev_006 | What are the weekend and after-hours on-call phone | — | Weekend and After-Hours on Call-Number (for... | — | — | The utilization management department is... | — | — | The utilization management department is... | — | — |
| dev_007 | Summarize the Secure Provider Portal registration. | — | 15 Secure Provider Portal... | — | — | Providers who have internet access and choose... | — | — | guidelines on general outreach and enrollment,... | — | — |
| dev_008 | What is the process for claims reconsiderations an | — | ➢ See Process for Claims Reconsiderations and... | — | — | ➢ See Process for Claims Reconsiderations and... | — | — | ➢ See Process for Claims Reconsiderations and... | — | — |
| dev_009 | What is the Medicare Part B prior authorization... | — | Bill Medicare for Medicare-allowable Part B... | — | — | (a) Medicare Part A Premium. Florida Medicaid... | — | — | and Prior Authorization  Utilization... | — | — |

*In1 = golden answer in top 1; In3 = golden answer in top 3. ✓/✗ when gold_ids provided; — when no gold labels.*

---

## Summary: Top 3 by rerank (raw | normalized | final)

### dev_001
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.8813 | 0.1410 | 0.7502 | Providers should refer to the... |
| 2 | 0.8813 | 0.1410 | 0.7502 | Providers should refer to the... |
| 3 | 0.8804 | 0.0739 | 0.7499 | and Prior Authorization  Utilization... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.5204 | 0.0000 | 0.4279 | Prior authorization is required for... |
| 2 | 0.5942 | 1.0000 | 0.3306 | Physical therapy in an office setting. |
| 3 | 0.5645 | 0.5976 | 0.3283 | Physical therapy |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9271 | 1.0000 | 0.5799 | 72-Hour Emergency Supply Policy... |
| 2 | 0.8923 | 0.8712 | 0.5668 | Sunshine Health will complete a... |
| 3 | 0.8903 | 0.8638 | 0.5661 | •  Medical equipment and supplies  •... |

### dev_002
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.8845 | 0.6928 | 0.8212 | Non-Specialty/Retail Medications  To... |
| 2 | 0.8845 | 0.6928 | 0.8212 | Non-Specialty/Retail Medications  To... |
| 3 | 0.8845 | 0.6928 | 0.8212 | Non-Specialty/Retail Medications  To... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 1.0000 | 1.0000 | 0.6770 | Pharmacies may call the Express... |
| 2 | 0.7219 | 0.2843 | 0.5729 | Call 711 and give them our Member... |
| 3 | 0.6351 | 0.0610 | 0.5403 | Call Member Services at... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9997 | 1.0000 | 0.6769 | Sunshine Health covers prescription... |
| 2 | 0.9351 | 0.8706 | 0.6528 | Questions? Call Member Services at... |
| 3 | 0.8917 | 0.7837 | 0.6366 | Questions? Call Member Services at... |

### dev_003
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9129 | 0.3770 | 0.7625 | Provider Demographic Updates... |
| 2 | 0.9129 | 0.3770 | 0.7625 | Provider Demographic Updates... |
| 3 | 0.9068 | 0.0000 | 0.7602 | Chapter 1: Welcome to Sunshine... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.7781 | 1.0000 | 0.4192 | The Florida Medicaid provider... |
| 2 | 0.6400 | 0.4616 | 0.3675 | The table listed in this section... |
| 3 | 0.5216 | 0.0000 | 0.3231 | 1.2.5 Crossover-Only Provider... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9562 | 1.0000 | 0.4860 | The table listed in this section... |
| 2 | 0.9431 | 0.8376 | 0.4845 | 2  1.4.6  Provider  The term used to... |
| 3 | 0.9396 | 0.7945 | 0.4798 | Providers must report the provider’s... |

### dev_004
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9198 | 1.0000 | 0.6574 | 72-Hour Emergency Supply Policy... |
| 2 | 0.9198 | 1.0000 | 0.6574 | 72-Hour Emergency Supply Policy... |
| 3 | 0.9198 | 1.0000 | 0.6574 | 72-Hour Emergency Supply Policy... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 1.0000 | 1.0000 | 0.5000 | 111 Exclusions to the 72-Hour... |
| 2 | 0.9987 | 0.8679 | 0.4995 | 111 Exclusions to the 72-Hour... |
| 3 | 0.9970 | 0.6973 | 0.4989 | 72-Hour Emergency Supply Policy... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 1.0000 | 1.0000 | 0.5000 | 72-Hour Emergency Supply Policy... |
| 2 | 0.9959 | 0.7831 | 0.4984 | The following drug categories are... |
| 3 | 0.9917 | 0.5646 | 0.4969 | Over-the-Counter (OTC)... |

### dev_005
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9331 | 1.0000 | 0.7692 | and Prior Authorization  Utilization... |
| 2 | 0.9331 | 1.0000 | 0.7692 | and Prior Authorization  Utilization... |
| 3 | 0.9275 | 0.6004 | 0.7671 | Prior authorization is required for... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.7230 | 1.0000 | 0.5029 | Providers should use the Pre-Auth... |
| 2 | 0.7030 | 0.8835 | 0.4954 | Be told prior to getting a service... |
| 3 | 0.6908 | 0.8126 | 0.4908 | Providers should refer to the... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9681 | 1.0000 | 0.5948 | 72-Hour Emergency Supply Policy... |
| 2 | 0.9508 | 0.9128 | 0.5883 | Sunshine Health provides a 24-hour... |
| 3 | 0.9507 | 0.9126 | 0.5883 | Providers should refer to the... |

### dev_006
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9062 | 1.0000 | 0.8293 | The utilization management... |
| 2 | 0.9062 | 1.0000 | 0.8293 | The utilization management... |
| 3 | 0.8944 | 0.3556 | 0.8249 | PCP Access and Availability  Each... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9976 | 1.0000 | 0.6761 | Weekend and After-Hours on... |
| 2 | 0.8119 | 0.3333 | 0.6064 | PCPs are encouraged to offer... |
| 3 | 0.7190 | 0.0000 | 0.5716 | 9 Key Contacts and Important Phone... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9995 | 1.0000 | 0.6768 | The utilization management... |
| 2 | 0.9482 | 0.7413 | 0.6575 | In-office waiting times for visits... |
| 3 | 0.9403 | 0.7018 | 0.6546 | PCP Access and Availability  Each... |

### dev_007
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9029 | 0.9803 | 0.7579 | guidelines on general outreach and... |
| 2 | 0.9029 | 0.9803 | 0.7579 | guidelines on general outreach and... |
| 3 | 0.9029 | 0.9803 | 0.7579 | guidelines on general outreach and... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.8224 | 1.0000 | 0.5402 | 15 Secure Provider Portal... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.8548 | 1.0000 | 0.5523 | Providers who have internet access... |
| 2 | 0.7106 | 0.3108 | 0.4983 | Preferred Method  Providers are... |
| 3 | 0.6901 | 0.2131 | 0.4906 | Medical practitioners and providers... |

### dev_008
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9740 | 1.0000 | 0.8478 | ➢ See Process for Claims... |
| 2 | 0.9740 | 1.0000 | 0.8478 | ➢ See Process for Claims... |
| 3 | 0.9410 | 0.1162 | 0.7730 | Reconsideration/Claim Disputes... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9975 | 1.0000 | 0.6690 | ➢ See Process for Claims... |
| 2 | 0.9975 | 1.0000 | 0.6067 | 125 Process for Claims... |
| 3 | 0.8910 | 0.0000 | 0.5667 | Providers must include the original... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9993 | 0.9897 | 0.6697 | ➢ See Process for Claims... |
| 2 | 0.9995 | 1.0000 | 0.6075 | Providers must include the original... |
| 3 | 0.9876 | 0.3581 | 0.6030 | All requests for corrected claims or... |

### dev_009
**Vector:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.8960 | 1.0000 | 0.7553 | and Prior Authorization  Utilization... |
| 2 | 0.8960 | 1.0000 | 0.7553 | and Prior Authorization  Utilization... |
| 3 | 0.8892 | 0.5684 | 0.7527 | •  Non-emergent/non-urgent... |

**BM25 Sentence:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.8979 | 0.8368 | 0.5697 | Florida Medicaid will pay the Part A... |
| 2 | 0.9420 | 1.0000 | 0.5415 | Drugs covered under Medicare Part B... |
| 3 | 0.8080 | 0.5033 | 0.5348 | During this period, access to these... |

**BM25 Paragraph:**
| Rank | Raw | Norm | Final | Snippet |
|------|-----|------|-------|---------|
| 1 | 0.9852 | 1.0000 | 0.6025 | (a) Medicare Part A Premium. Florida... |
| 2 | 0.9177 | 0.6851 | 0.5759 | resort. If an authorization is... |
| 3 | 0.8368 | 0.3074 | 0.5456 | The following drug categories are... |

---

## dev_001

**Question:** What is the prior authorization requirement for physical therapy in Florida?

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: ['health_care_services.physical_therapy', 'utilization_management.prior_authorization']
- j_tags: ['state.florida']
- document_ids resolved: 21 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=17.432 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `2d2c5ff6-da5b-47ea-aa5c-f7f166810e07` | raw_score=16.644 Sunshine Provider Manual | Sunshine Health will complete a retrospective medical necessity review if...
  3. `8f17c077-6b24-47f7-8259-9e381c3893ad` | raw_score=16.606 Sunshine Provider Manual | • 
Medical equipment and supplies 
• 
Medication administration 
•...
  4. `43a29e63-85c8-43dd-9ee3-8e50b3c073e6` | raw_score=15.550 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  5. `1bb998c3-3f24-477e-a6f7-f240c9d232eb` | raw_score=14.096 document | 2 
2.0 Authorization Requirements 
2.1 
When to Request Authorization...
  6. `d04785de-207b-4c37-b4ce-afcb22fce928` | raw_score=13.948 document | 59G-1.040 Preadmission Screening and Resident Review. 
(1) Purpose. This...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `078780e4-1c4e-45ed-894e-40888fa22a60` | raw_score=14.619 Sunshine Member Handbook | Physical therapy in an office setting.
  2. `8f17c077-6b24-47f7-8259-9e381c3893ad` | raw_score=14.351 Sunshine Provider Manual | Physical therapy
  3. `2056c9e6-f9de-421c-b479-d8d209316bee` | raw_score=14.153 Sunshine Provider Manual | Authorization requirement and submission
  4. `5c8167d6-84c1-4b47-9fb9-b54f53e47e8b` | raw_score=13.961 Sunshine Member Handbook | Prior authorization is required for voluntary admissions.

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `5c8167d6-84c...` | 0.5204 | 0.0000 | 0.4279 | Prior authorization is required for voluntary... |
| 2 | `078780e4-1c4...` | 0.5942 | 1.0000 | 0.3306 | Physical therapy in an office setting. |
| 3 | `8f17c077-6b2...` | 0.5645 | 0.5976 | 0.3283 | Physical therapy |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=5c8167d6-84c1-4b47-9fb9-... rerank_score=0.4279
    score: raw=0.5204 norm=0.0 weight=0.3
    tag_match: raw=0.3449 norm=0.0597 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] contrib=[0.55, 0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=078780e4-1c4e-45ed-894e-... rerank_score=0.3306
    score: raw=0.5942 norm=1.0 weight=0.3
    tag_match: raw=0.3449 norm=0.0597 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] contrib=[0.55, 0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1
  id=8f17c077-6b24-47f7-8259-... rerank_score=0.3283
    score: raw=0.5645 norm=0.5976 weight=0.3
    tag_match: raw=0.3732 norm=1.0 weight=0.25
      tag_source=line
      overlap d: {'count_norm': 0.5, 'intensity_norm': 0.275} tags=['health_care_services.physical_therapy'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1
  id=2056c9e6-f9de-421c-b479-... rerank_score=0.3105
    score: raw=0.5422 norm=0.2952 weight=0.3
    tag_match: raw=0.3431 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] contrib=[0.55, 0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `4f4a79c5-2f9...` | 0.9271 | 1.0000 | 0.5799 | 72-Hour Emergency Supply Policy  State law... |
| 2 | `2d2c5ff6-da5...` | 0.8923 | 0.8712 | 0.5668 | Sunshine Health will complete a retrospective... |
| 3 | `8f17c077-6b2...` | 0.8903 | 0.8638 | 0.5661 | •  Medical equipment and supplies  •... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=4f4a79c5-2f96-405b-9d1e-... rerank_score=0.5799
    score: raw=0.9271 norm=1.0 weight=0.3
    tag_match: raw=0.3431 norm=0.9947 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] contrib=[0.55, 0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=2d2c5ff6-da5b-47ea-aa5c-... rerank_score=0.5668
    score: raw=0.8923 norm=0.8712 weight=0.3
    tag_match: raw=0.3431 norm=0.9947 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] contrib=[0.55, 0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=8f17c077-6b24-47f7-8259-... rerank_score=0.5661
    score: raw=0.8903 norm=0.8638 weight=0.3
    tag_match: raw=0.3431 norm=0.9947 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] contrib=[0.55, 0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=43a29e63-85c8-43dd-9ee3-... rerank_score=0.5405
    score: raw=0.8205 norm=0.6057 weight=0.3
    tag_match: raw=0.3449 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] contrib=[0.55, 0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1bb998c3-3f24-477e-a6f7-... rerank_score=0.4362
    score: raw=0.6746 norm=0.066 weight=0.3
    tag_match: raw=0.1862 norm=0.5293 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 0.5, 'intensity_norm': 0.275} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['state.florida'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `1eb4490c-5482-43a6-ab10-112dd92921bf` | sim=0.881 rerank=0.750 dist=0.237 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...
  2. `72c1b99b-0756-438b-b223-5e3736ed7ee6` | sim=0.880 rerank=0.750 dist=0.239 Sunshine Provider Manual | and Prior Authorization 
Utilization Management Program Overview
  3. `909f4f6b-c89f-488d-935f-6aef26327ed3` | sim=0.879 rerank=0.749 dist=0.241 Sunshine Provider Manual | the member’s PCP, except in a true emergency. All non-emergency inpatient...
  4. `1bb998c3-3f24-477e-a6f7-f240c9d232eb` | sim=0.891 rerank=0.517 dist=0.219 59G_1053_Authorization_Requirements_Cove | 2 
2.0 Authorization Requirements 
2.1 
When to Request Authorization...
  5. `d3a90a42-b3a9-4418-8e22-acd931ff1fa6` | sim=0.881 rerank=0.513 dist=0.238 59G_1053_Authorization_Requirements_Cove | 1 
1.0 
Introduction 
1.1 
Description 
This policy contains general...
  6. `b7554fa1-f552-4c7a-9765-c81ff06c1962` | sim=0.884 rerank=0.511 dist=0.232 59G-1.060_Enrollment.pdf | Providers must report Florida licensure as required for the scope of...
  7. `aceee138-a249-4559-af73-be75b73812a7` | sim=0.881 rerank=0.510 dist=0.238 59G-1.060_Enrollment.pdf | *Home health providers must be either Medicare certified or meet the...
  8. `2e7b42ef-d461-49d2-8c9d-1a912fd75ace` | sim=0.894 rerank=0.462 dist=0.213 59G-4.028.pdf | Florida Medicaid covers services that meet all of the following: 
 
Are...

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=2e7b42ef-d46... sim=0.894 doc=59G-4.028.pdf
  2. id=1bb998c3-3f2... sim=0.891 doc=59G_1053_Authorization_Require
  3. id=b7554fa1-f55... sim=0.884 doc=59G-1.060_Enrollment.pdf
  4. id=1eb4490c-548... sim=0.881 doc=Sunshine Provider Manual
  5. id=f52b484c-a9a... sim=0.881 doc=Sunshine Provider Manual
  6. id=aceee138-a24... sim=0.881 doc=59G-1.060_Enrollment.pdf
  7. id=d3a90a42-b3a... sim=0.881 doc=59G_1053_Authorization_Require
  8. id=72c1b99b-075... sim=0.880 doc=Sunshine Provider Manual
  9. id=6ad1a510-c6b... sim=0.880 doc=Sunshine Provider Manual
  10. id=909f4f6b-c89... sim=0.879 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=1eb4490c-548... rerank=0.750 sim=0.881
  2. id=f52b484c-a9a... rerank=0.750 sim=0.881
  3. id=72c1b99b-075... rerank=0.750 sim=0.880
  4. id=6ad1a510-c6b... rerank=0.750 sim=0.880
  5. id=909f4f6b-c89... rerank=0.749 sim=0.879
  6. id=1bb998c3-3f2... rerank=0.517 sim=0.891
  7. id=d3a90a42-b3a... rerank=0.513 sim=0.881
  8. id=b7554fa1-f55... rerank=0.511 sim=0.884
  9. id=aceee138-a24... rerank=0.510 sim=0.881
  10. id=2e7b42ef-d46... rerank=0.462 sim=0.894

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `1eb4490c-548...` | 0.8813 | 0.1410 | 0.7502 | Providers should refer to the Pre-Auth Check... |
| 2 | `f52b484c-a9a...` | 0.8813 | 0.1410 | 0.7502 | Providers should refer to the Pre-Auth Check... |
| 3 | `72c1b99b-075...` | 0.8804 | 0.0739 | 0.7499 | and Prior Authorization  Utilization... |

**Per-chunk signals (raw, norm, weight):**
  id=1eb4490c-5482-43a6-a... rerank_score=0.750
    score: raw=0.8813 norm=0.141 weight=0.3
    tag_match: raw=0.3431 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('health_care_services.physical_therapy', 1.0, 0.1, 0.55), ('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=f52b484c-a9a9-4428-9... rerank_score=0.750
    score: raw=0.8813 norm=0.141 weight=0.3
    tag_match: raw=0.3431 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('health_care_services.physical_therapy', 1.0, 0.1, 0.55), ('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=72c1b99b-0756-438b-b... rerank_score=0.750
    score: raw=0.8804 norm=0.0739 weight=0.3
    tag_match: raw=0.3431 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('health_care_services.physical_therapy', 1.0, 0.1, 0.55), ('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=6ad1a510-c6b7-4579-b... rerank_score=0.750
    score: raw=0.8804 norm=0.0739 weight=0.3
    tag_match: raw=0.3431 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('health_care_services.physical_therapy', 1.0, 0.1, 0.55), ('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=909f4f6b-c89f-488d-9... rerank_score=0.749
    score: raw=0.8793 norm=0.0 weight=0.3
    tag_match: raw=0.3431 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('health_care_services.physical_therapy', 1.0, 0.1, 0.55), ('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1bb998c3-3f24-477e-a... rerank_score=0.517
    score: raw=0.8907 norm=0.7909 weight=0.3
    tag_match: raw=0.1862 norm=0.5341 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'claims.reimbursement', 'eligibility.enrollment', 'contact_information.fax', 'contact_information.website'] j=['state', 'provider', 'state.florida', 'program.medicaid', 'payor.unitedhealthcare', 'regulatory_authority.dcf', 'regulatory_authority.ahca']
      overlap d: {'count_norm': 0.5, 'intensity_norm': 0.275} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=d3a90a42-b3a9-4418-8... rerank_score=0.513
    score: raw=0.8808 norm=0.1074 weight=0.3
    tag_match: raw=0.1862 norm=0.5341 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'claims.reimbursement', 'eligibility.enrollment', 'contact_information.fax', 'contact_information.website'] j=['state', 'provider', 'state.florida', 'program.medicaid', 'payor.unitedhealthcare', 'regulatory_authority.dcf', 'regulatory_authority.ahca']
      overlap d: {'count_norm': 0.5, 'intensity_norm': 0.275} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=b7554fa1-f552-4c7a-9... rerank_score=0.511
    score: raw=0.8841 norm=0.3316 weight=0.3
    tag_match: raw=0.1748 norm=0.5003 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap d: {'count_norm': 0.5, 'intensity_norm': 0.275} — tags: ['health_care_services.physical_therapy'] (q_score, doc_decayed, contrib): [('health_care_services.physical_therapy', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=aceee138-a249-4559-a... rerank_score=0.510
    score: raw=0.8811 norm=0.1226 weight=0.3
    tag_match: raw=0.1748 norm=0.5003 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap d: {'count_norm': 0.5, 'intensity_norm': 0.275} — tags: ['health_care_services.physical_therapy'] (q_score, doc_decayed, contrib): [('health_care_services.physical_therapy', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=2e7b42ef-d461-49d2-8... rerank_score=0.462
    score: raw=0.8937 norm=1.0 weight=0.3
    tag_match: raw=0.0063 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['health_care_services.physical_therapy', 'utilization_management.prior_authorization'] j=['state.florida']
      doc_tags (this chunk): p=['communication', 'review.review', 'submission.submit', 'compliance_action.required', 'compliance_action.prohibited'] d=['tools.general', 'claims.general', 'eligibility.general', 'claims.billing_forms', 'claims.reimbursement', 'care_management.general', 'responsibilities.training', 'place_of_service.inpatient'] j=['state', 'program', 'provider', 'state.florida', 'program.medicaid', 'payor.unitedhealthcare', 'regulatory_authority.cms', 'regulatory_authority.dcf']
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['state.florida'] (q_score, doc_decayed, contrib): [('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | doc: Sunshine Provider Manual | raw_score=17.432 rerank=0.580
- text: 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to dispense a 72-hour (three-day) supply of certain 
medications to a member awaiting a prior authorization determination. The purpose is to avoid 
interruption of current therapy or delay in the initiation of therapy. All...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `5c8167d6-84c1-4b47-9fb9-b54f53e47e8b` | doc: Sunshine Member Handbook | raw_score=13.961 rerank=0.428
- text: Prior authorization is required for voluntary admissions.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `1eb4490c-5482-43a6-ab10-112dd92921bf` | doc: Sunshine Provider Manual | sim=0.881 rerank=0.750 dist=0.237
- text: Providers should refer to the Pre-Auth Check Tool to look up a service code to determine if prior 
authorization is needed. To view those codes, select the Pre-Auth Check Tool link followed by the 
product in which the Sunshine Health member is enrolled. Under the Provider Resources section 
of...

**In syllabus** (expect_in_manual=true)

---

## dev_002

**Question:** What phone number do pharmacies call for Express Scripts help desk?

**Tags from question (J/P/D):**
- p_tags: ['communication.call']
- d_tags: ['contact_information.phone']
- j_tags: (none)
- document_ids resolved: 9 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `3b543bcb-8074-4934-a277-15bb4d366a12` | raw_score=27.588 Sunshine Provider Manual | Sunshine Health covers prescription drugs and certain over-the-counter (OTC)...
  2. `47ad14cd-d4dd-48ec-8410-09e3363e5648` | raw_score=17.662 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  3. `47c6c40a-eeb7-4945-a7f6-7f2761cbcd57` | raw_score=16.633 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  4. `ec2977a4-25aa-4500-9d24-a65503107f19` | raw_score=15.737 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  5. `5bd77e37-4864-4bb1-98f5-24235c54e61c` | raw_score=15.549 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  6. `f2a7a941-23bb-4530-a91b-452e72141718` | raw_score=14.036 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  7. `2c51497c-5786-4420-9384-b5749e56d46c` | raw_score=12.757 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `3b543bcb-8074-4934-a277-15bb4d366a12` | raw_score=40.068 Sunshine Provider Manual | Pharmacies may call the Express Scripts help desk at 1-833-750-4392.
  2. `3b543bcb-8074-4934-a277-15bb4d366a12` | raw_score=17.295 Sunshine Provider Manual | Pharmacy claims are processed by Express Scripts.
  3. `ec2977a4-25aa-4500-9d24-a65503107f19` | raw_score=15.876 Sunshine Member Handbook | Call 711 and give them our Member Services phone number.
  4. `cebfece2-5d2e-4e9c-8e6f-7d7653706322` | raw_score=15.175 Sunshine Member Handbook | What Do I Have To Pay For?
  5. `47ad14cd-d4dd-48ec-8410-09e3363e5648` | raw_score=14.999 Sunshine Member Handbook | Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770 77 What You...
  6. `5bd77e37-4864-4bb1-98f5-24235c54e61c` | raw_score=14.777 Sunshine Member Handbook | What You Can Do: What We Will Do: If you are not happy with us or our...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `3b543bcb-807...` | 1.0000 | 1.0000 | 0.6770 | Pharmacies may call the Express Scripts help... |
| 2 | `ec2977a4-25a...` | 0.7219 | 0.2843 | 0.5729 | Call 711 and give them our Member Services... |
| 3 | `47ad14cd-d4d...` | 0.6351 | 0.0610 | 0.5403 | Call Member Services at 1-866-796-0530 or TTY... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=3b543bcb-8074-4934-a277-... rerank_score=0.6770
    score: raw=1.0 norm=1.0 weight=0.3
    tag_match: raw=0.5664 norm=0.9989 weight=0.25
      tag_source=line
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=ec2977a4-25aa-4500-9d24-... rerank_score=0.5729
    score: raw=0.7219 norm=0.2843 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=47ad14cd-d4dd-48ec-8410-... rerank_score=0.5403
    score: raw=0.6351 norm=0.061 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=5bd77e37-4864-4bb1-98f5-... rerank_score=0.5314
    score: raw=0.6114 norm=0.0 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=3b543bcb-8074-4934-a277-... rerank_score=0.3127
    score: raw=0.8319 norm=0.5675 weight=0.3
    tag_match: raw=0.0025 norm=0.0 weight=0.25
      tag_source=line
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `3b543bcb-807...` | 0.9997 | 1.0000 | 0.6769 | Sunshine Health covers prescription drugs and... |
| 2 | `47ad14cd-d4d...` | 0.9351 | 0.8706 | 0.6528 | Questions? Call Member Services at... |
| 3 | `47c6c40a-eeb...` | 0.8917 | 0.7837 | 0.6366 | Questions? Call Member Services at... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=3b543bcb-8074-4934-a277-... rerank_score=0.6769
    score: raw=0.9997 norm=1.0 weight=0.3
    tag_match: raw=0.5664 norm=0.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=47ad14cd-d4dd-48ec-8410-... rerank_score=0.6528
    score: raw=0.9351 norm=0.8706 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=47c6c40a-eeb7-4945-a7f6-... rerank_score=0.6366
    score: raw=0.8917 norm=0.7837 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=ec2977a4-25aa-4500-9d24-... rerank_score=0.6153
    score: raw=0.835 norm=0.6702 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=5bd77e37-4864-4bb1-98f5-... rerank_score=0.6098
    score: raw=0.8204 norm=0.641 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `1c912807-a31c-4a35-9003-8b40989f137a` | sim=0.885 rerank=0.821 dist=0.231 Sunshine Provider Manual | Non-Specialty/Retail Medications 
To efficiently process prior authorization...
  2. `696f17fe-94ad-41ba-bcf0-ae182a1dd04c` | sim=0.874 rerank=0.817 dist=0.251 Sunshine Provider Manual | Phone Number 
Provider Services 
1-844-477-8313 
Medical or behavioral...
  3. `bdca20a8-a22b-49e4-a858-1b844ab41dbb` | sim=0.874 rerank=0.817 dist=0.252 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  4. `d5f2d290-339a-4195-b975-4ee4289a49e4` | sim=0.889 rerank=0.522 dist=0.222 Sunshine Provider Manual | Pharmacy Benefit

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=d5f2d290-339... sim=0.889 doc=Sunshine Provider Manual
  2. id=45eb21f6-969... sim=0.889 doc=Sunshine Provider Manual
  3. id=a2c00b22-38c... sim=0.889 doc=Sunshine Provider Manual
  4. id=1c912807-a31... sim=0.885 doc=Sunshine Provider Manual
  5. id=f5867631-9a2... sim=0.885 doc=Sunshine Provider Manual
  6. id=38e3feb2-ac3... sim=0.885 doc=Sunshine Provider Manual
  7. id=696f17fe-94a... sim=0.874 doc=Sunshine Provider Manual
  8. id=273adfd3-7ee... sim=0.874 doc=Sunshine Provider Manual
  9. id=bdca20a8-a22... sim=0.874 doc=Sunshine Provider Manual
  10. id=e966e52d-90c... sim=0.874 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=1c912807-a31... rerank=0.821 sim=0.885
  2. id=f5867631-9a2... rerank=0.821 sim=0.885
  3. id=38e3feb2-ac3... rerank=0.821 sim=0.885
  4. id=696f17fe-94a... rerank=0.817 sim=0.874
  5. id=273adfd3-7ee... rerank=0.817 sim=0.874
  6. id=bdca20a8-a22... rerank=0.817 sim=0.874
  7. id=e966e52d-90c... rerank=0.817 sim=0.874
  8. id=d5f2d290-339... rerank=0.522 sim=0.889
  9. id=45eb21f6-969... rerank=0.522 sim=0.889
  10. id=a2c00b22-38c... rerank=0.522 sim=0.889

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `1c912807-a31...` | 0.8845 | 0.6928 | 0.8212 | Non-Specialty/Retail Medications  To... |
| 2 | `f5867631-9a2...` | 0.8845 | 0.6928 | 0.8212 | Non-Specialty/Retail Medications  To... |
| 3 | `38e3feb2-ac3...` | 0.8845 | 0.6928 | 0.8212 | Non-Specialty/Retail Medications  To... |

**Per-chunk signals (raw, norm, weight):**
  id=1c912807-a31c-4a35-9... rerank_score=0.821
    score: raw=0.8845 norm=0.6928 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=f5867631-9a2a-40bb-a... rerank_score=0.821
    score: raw=0.8845 norm=0.6928 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=38e3feb2-ac3f-427a-8... rerank_score=0.821
    score: raw=0.8845 norm=0.6928 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=696f17fe-94ad-41ba-b... rerank_score=0.817
    score: raw=0.8743 norm=0.0082 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=273adfd3-7ee9-412c-b... rerank_score=0.817
    score: raw=0.8743 norm=0.0082 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=bdca20a8-a22b-49e4-a... rerank_score=0.817
    score: raw=0.8742 norm=0.0 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=e966e52d-90c3-4a6d-9... rerank_score=0.817
    score: raw=0.8742 norm=0.0 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=d5f2d290-339a-4195-b... rerank_score=0.522
    score: raw=0.8891 norm=1.0 weight=0.3
    tag_match: raw=0.0025 norm=0.0 weight=0.25
      tag_source=line
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=[] d=['pharmacy.general', 'pharmacy.pharmacy_benefit'] j=[]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1
  id=45eb21f6-9698-41b2-9... rerank_score=0.522
    score: raw=0.8891 norm=1.0 weight=0.3
    tag_match: raw=0.0025 norm=0.0 weight=0.25
      tag_source=line
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=[] d=['pharmacy.general', 'pharmacy.pharmacy_benefit'] j=[]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1
  id=a2c00b22-38c4-4388-a... rerank_score=0.522
    score: raw=0.8891 norm=1.0 weight=0.3
    tag_match: raw=0.0025 norm=0.0 weight=0.25
      tag_source=line
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=[] d=['pharmacy.general', 'pharmacy.pharmacy_benefit'] j=[]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `3b543bcb-8074-4934-a277-15bb4d366a12` | doc: Sunshine Provider Manual | raw_score=27.588 rerank=0.677
- text: Sunshine Health covers prescription drugs and certain over-the-counter (OTC) drugs ordered by 
Sunshine Health providers. Some medications require prior authorization or have limitations on 
dosage, maximum quantities or the member’s age. Sunshine Health follows AHCA’s preferred drug 
list...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `3b543bcb-8074-4934-a277-15bb4d366a12` | doc: Sunshine Provider Manual | raw_score=40.068 rerank=0.677
- text: Pharmacies may call the Express Scripts help desk at 1-833-750-4392.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `1c912807-a31c-4a35-9003-8b40989f137a` | doc: Sunshine Provider Manual | sim=0.885 rerank=0.821 dist=0.231
- text: Non-Specialty/Retail Medications 
To efficiently process prior authorization requests for non-specialty/retail medications, providers 
should follow these steps: 
• 
Submit requests electronically through CoverMyMeds (preferred method) 
• 
Send a fax to 1-833-546-1507 
• 
Call 1-866-399-0928, 8...

**In syllabus** (expect_in_manual=true)

---

## dev_003

**Question:** Summarize the key guidance in the provider manual section "Medicaid in Florida".

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: ['provider.manual']
- j_tags: ['provider', 'program.medicaid', 'state.florida']
- document_ids resolved: 23 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `961a8e58-b137-4d01-a59c-c3ac1f5a3302` | raw_score=18.426 document | The table listed in this section includes all general documents required to...
  2. `2697aae3-0bce-40f4-b09e-16a758cf52a6` | raw_score=17.920 document | 2 
1.4.6 
Provider 
The term used to describe any entity, facility, person,...
  3. `acacb3ba-eb4a-4a26-a2d9-3ddd1f808721` | raw_score=17.804 document | Providers must report the provider’s Internal Revenue Service assigned TIN...
  4. `8a823e98-8e82-4ddf-876c-eaf5a2d445b4` | raw_score=17.639 document | Florida Medicaid assigns one provider ID number per TIN and type of service...
  5. `06218880-5f65-4107-8237-bcbd1d46533f` | raw_score=17.428 document | 15 
5.10 Change in Enrollment Status/Exclusion Occurrence 
Providers must...
  6. `ea67cb8d-90e3-41dd-b582-d7cc99636e1d` | raw_score=17.371 document | 8 
 
Currently sanctioned by Medicare or Medicaid in any state 
...
  7. `e9ea1bbc-358a-4ea2-ab5c-a200217d7dca` | raw_score=16.856 document | (a) Medicare Part A Premium. Florida Medicaid will pay the Part A premium...
  8. `00aeafdd-1167-4d4f-9982-3f018bb31a4f` | raw_score=16.798 document | 5 
Providers deemed ineligible during the application process will be...
  9. `386bae4a-f19c-4f6b-a06f-bec6ddb02856` | raw_score=16.434 document | 16 
 
The provider is required to be licensed, certified, accredited,...
  10. `396b836b-e60a-46fe-945a-0e97ceff230e` | raw_score=16.344 document | 14 
5.4 
Change of Ownership 
Providers must report a change of ownership in...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `b637cc3f-f855-46af-8ac9-f4b1fec2fd19` | raw_score=16.537 document | The Florida Medicaid provider requirements for a change of ownership are...
  2. `961a8e58-b137-4d01-a59c-c3ac1f5a3302` | raw_score=15.045 document | The table listed in this section includes all general documents required to...
  3. `e7c1702d-d5be-46d8-8e04-0388c6243c65` | raw_score=13.971 document | 1.2.5 Crossover-Only Provider Eligible Medicare provider enrolled in Florida...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `b637cc3f-f85...` | 0.7781 | 1.0000 | 0.4192 | The Florida Medicaid provider requirements for... |
| 2 | `961a8e58-b13...` | 0.6400 | 0.4616 | 0.3675 | The table listed in this section includes all... |
| 3 | `e7c1702d-d5b...` | 0.5216 | 0.0000 | 0.3231 | 1.2.5 Crossover-Only Provider Eligible... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=b637cc3f-f855-46af-8ac9-... rerank_score=0.4192
    score: raw=0.7781 norm=1.0 weight=0.3
    tag_match: raw=0.0079 norm=1.0 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=961a8e58-b137-4d01-a59c-... rerank_score=0.3675
    score: raw=0.64 norm=0.4616 weight=0.3
    tag_match: raw=0.0079 norm=1.0 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=e7c1702d-d5be-46d8-8e04-... rerank_score=0.3231
    score: raw=0.5216 norm=0.0 weight=0.3
    tag_match: raw=0.0079 norm=1.0 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `961a8e58-b13...` | 0.9562 | 1.0000 | 0.4860 | The table listed in this section includes all... |
| 2 | `2697aae3-0bc...` | 0.9431 | 0.8376 | 0.4845 | 2  1.4.6  Provider  The term used to describe... |
| 3 | `acacb3ba-eb4...` | 0.9396 | 0.7945 | 0.4798 | Providers must report the provider’s Internal... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=961a8e58-b137-4d01-a59c-... rerank_score=0.4860
    score: raw=0.9562 norm=1.0 weight=0.3
    tag_match: raw=0.0079 norm=0.0 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=2697aae3-0bce-40f4-b09e-... rerank_score=0.4845
    score: raw=0.9431 norm=0.8376 weight=0.3
    tag_match: raw=0.0188 norm=0.8967 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=acacb3ba-eb4a-4a26-a2d9-... rerank_score=0.4798
    score: raw=0.9396 norm=0.7945 weight=0.3
    tag_match: raw=0.0079 norm=0.0 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=8a823e98-8e82-4ddf-876c-... rerank_score=0.4778
    score: raw=0.9343 norm=0.7288 weight=0.3
    tag_match: raw=0.0079 norm=0.0 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=06218880-5f65-4107-8237-... rerank_score=0.4751
    score: raw=0.9269 norm=0.6372 weight=0.3
    tag_match: raw=0.0079 norm=0.0 weight=0.25
      tag_source=document
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider', 'program.medicaid', 'state.florida'] contrib=[0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `c2ef0450-cd4d-40fe-81dc-686acaaebc2d` | sim=0.913 rerank=0.762 dist=0.174 Sunshine Provider Manual | Provider Demographic Updates...
  2. `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | sim=0.907 rerank=0.760 dist=0.186 Sunshine Provider Manual | Chapter 1: Welcome to Sunshine Health...
  3. `2e7b42ef-d461-49d2-8c9d-1a912fd75ace` | sim=0.916 rerank=0.474 dist=0.167 59G-4.028.pdf | Florida Medicaid covers services that meet all of the following: 
 
Are...
  4. `147d428e-ecee-4327-98da-4e73e9e052d8` | sim=0.923 rerank=0.474 dist=0.154 59G-1.060_Enrollment.pdf | Introduction...
  5. `0814955b-6ac2-469d-84c7-c1565cdeccee` | sim=0.919 rerank=0.472 dist=0.161 59G-1.060_Enrollment.pdf | Providers must report or provide any certification as required in accordance...
  6. `b7554fa1-f552-4c7a-9765-c81ff06c1962` | sim=0.907 rerank=0.468 dist=0.186 59G-1.060_Enrollment.pdf | Providers must report Florida licensure as required for the scope of...

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=147d428e-ece... sim=0.923 doc=59G-1.060_Enrollment.pdf
  2. id=0814955b-6ac... sim=0.919 doc=59G-1.060_Enrollment.pdf
  3. id=2e7b42ef-d46... sim=0.916 doc=59G-4.028.pdf
  4. id=c2ef0450-cd4... sim=0.913 doc=Sunshine Provider Manual
  5. id=d307c991-dbf... sim=0.913 doc=Sunshine Provider Manual
  6. id=95fdb0bd-dcf... sim=0.908 doc=59G-4.028.pdf
  7. id=e469e26f-d20... sim=0.908 doc=59G-1.010 Definitions Policy.p
  8. id=18f54f90-d6b... sim=0.908 doc=59G_1053_Authorization_Require
  9. id=b7554fa1-f55... sim=0.907 doc=59G-1.060_Enrollment.pdf
  10. id=1ce2b150-00b... sim=0.907 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=c2ef0450-cd4... rerank=0.762 sim=0.913
  2. id=d307c991-dbf... rerank=0.762 sim=0.913
  3. id=1ce2b150-00b... rerank=0.760 sim=0.907
  4. id=2e7b42ef-d46... rerank=0.474 sim=0.916
  5. id=147d428e-ece... rerank=0.474 sim=0.923
  6. id=0814955b-6ac... rerank=0.472 sim=0.919
  7. id=b7554fa1-f55... rerank=0.468 sim=0.907

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `c2ef0450-cd4...` | 0.9129 | 0.3770 | 0.7625 | Provider Demographic Updates... |
| 2 | `d307c991-dbf...` | 0.9129 | 0.3770 | 0.7625 | Provider Demographic Updates... |
| 3 | `1ce2b150-00b...` | 0.9068 | 0.0000 | 0.7602 | Chapter 1: Welcome to Sunshine Health... |

**Per-chunk signals (raw, norm, weight):**
  id=c2ef0450-cd4d-40fe-8... rerank_score=0.762
    score: raw=0.9129 norm=0.377 weight=0.3
    tag_match: raw=0.3444 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['provider.manual'] j=['provider', 'program.medicaid', 'state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider.manual'] (q_score, doc_decayed, contrib): [('provider.manual', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider', 'program.medicaid', 'state.florida'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55), ('program.medicaid', 1.0, 0.1, 0.55), ('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=d307c991-dbf5-4760-b... rerank_score=0.762
    score: raw=0.9129 norm=0.377 weight=0.3
    tag_match: raw=0.3444 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['provider.manual'] j=['provider', 'program.medicaid', 'state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider.manual'] (q_score, doc_decayed, contrib): [('provider.manual', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider', 'program.medicaid', 'state.florida'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55), ('program.medicaid', 1.0, 0.1, 0.55), ('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1ce2b150-00bd-4a56-9... rerank_score=0.760
    score: raw=0.9068 norm=0.0 weight=0.3
    tag_match: raw=0.3444 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['provider.manual'] j=['provider', 'program.medicaid', 'state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider.manual'] (q_score, doc_decayed, contrib): [('provider.manual', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider', 'program.medicaid', 'state.florida'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55), ('program.medicaid', 1.0, 0.1, 0.55), ('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=2e7b42ef-d461-49d2-8... rerank_score=0.474
    score: raw=0.9163 norm=0.5865 weight=0.3
    tag_match: raw=0.0188 norm=0.0323 weight=0.25
      tag_source=document
      question_tags: p=[] d=['provider.manual'] j=['provider', 'program.medicaid', 'state.florida']
      doc_tags (this chunk): p=['communication', 'review.review', 'submission.submit', 'compliance_action.required', 'compliance_action.prohibited'] d=['tools.general', 'claims.general', 'eligibility.general', 'claims.billing_forms', 'claims.reimbursement', 'care_management.general', 'responsibilities.training', 'place_of_service.inpatient'] j=['state', 'program', 'provider', 'state.florida', 'program.medicaid', 'payor.unitedhealthcare', 'regulatory_authority.cms', 'regulatory_authority.dcf']
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider', 'program.medicaid', 'state.florida'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55), ('program.medicaid', 1.0, 0.1, 0.55), ('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=147d428e-ecee-4327-9... rerank_score=0.474
    score: raw=0.9231 norm=1.0 weight=0.3
    tag_match: raw=0.0079 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['provider.manual'] j=['provider', 'program.medicaid', 'state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider', 'program.medicaid', 'state.florida'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55), ('program.medicaid', 1.0, 0.1, 0.55), ('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=0814955b-6ac2-469d-8... rerank_score=0.472
    score: raw=0.9193 norm=0.7674 weight=0.3
    tag_match: raw=0.0079 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['provider.manual'] j=['provider', 'program.medicaid', 'state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider', 'program.medicaid', 'state.florida'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55), ('program.medicaid', 1.0, 0.1, 0.55), ('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=b7554fa1-f552-4c7a-9... rerank_score=0.468
    score: raw=0.9072 norm=0.0246 weight=0.3
    tag_match: raw=0.0079 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['provider.manual'] j=['provider', 'program.medicaid', 'state.florida']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider', 'program.medicaid', 'state.florida'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55), ('program.medicaid', 1.0, 0.1, 0.55), ('state.florida', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `961a8e58-b137-4d01-a59c-c3ac1f5a3302` | doc: document | raw_score=18.426 rerank=0.486
- text: The table listed in this section includes all general documents required to be submitted with a Florida 
Medicaid provider application. Florida Medicaid Provider Enrollment Agreements and Forms are located 
at http://portal.flmmis.com under Provider Services.
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `b637cc3f-f855-46af-8ac9-f4b1fec2fd19` | doc: document | raw_score=16.537 rerank=0.419
- text: The Florida Medicaid provider requirements for a change of ownership are specified in section 5.3.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `c2ef0450-cd4d-40fe-81dc-686acaaebc2d` | doc: Sunshine Provider Manual | sim=0.913 rerank=0.762 dist=0.174
- text: Provider Demographic Updates ........................................................................................................................ 28 
Chapter 4: Utilization Management...

**In syllabus** (expect_in_manual=true)

---

## dev_004

**Question:** What is the 72-hour emergency medication supply policy?

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: (none)
- j_tags: (none)
- document_ids resolved: 0 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=35.460 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `49e59ab8-e5f8-4aaf-be6a-7c36dcd3452f` | raw_score=22.838 Sunshine Provider Manual | The following drug categories are not part of the Sunshine Health PDL and...
  3. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=21.549 Sunshine Provider Manual | Over-the-Counter (OTC)...
  4. `7f6838ec-10b4-4a86-9e58-f767507af3e7` | raw_score=19.999 Sunshine Provider Manual | • 
Drugs used to treat infertility 
• 
Experimental/investigational...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=36.140 Sunshine Provider Manual | 111 72-Hour Emergency Supply Policy...
  2. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=28.333 Sunshine Provider Manual | 111 Exclusions to the 72-Hour Emergency Supply...
  3. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=26.544 Sunshine Provider Manual | 72-Hour Emergency Supply Policy State law requires that a pharmacy offer to...
  4. `7f6838ec-10b4-4a86-9e58-f767507af3e7` | raw_score=23.923 Sunshine Provider Manual | Prostheses, appliances and devices (except products for diabetics and...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `6b9bd6ea-bda...` | 1.0000 | 1.0000 | 0.5000 | 111 72-Hour Emergency Supply Policy... |
| 2 | `6b9bd6ea-bda...` | 0.9987 | 0.8679 | 0.4995 | 111 72-Hour Emergency Supply Policy... |
| 3 | `4f4a79c5-2f9...` | 0.9970 | 0.6973 | 0.4989 | 72-Hour Emergency Supply Policy State law... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=6b9bd6ea-bda6-44fe-99f1-... rerank_score=0.5000
    score: raw=1.0 norm=1.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=6b9bd6ea-bda6-44fe-99f1-... rerank_score=0.4995
    score: raw=0.9987 norm=0.8679 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=4f4a79c5-2f96-405b-9d1e-... rerank_score=0.4989
    score: raw=0.997 norm=0.6973 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=7f6838ec-10b4-4a86-9e58-... rerank_score=0.4963
    score: raw=0.9902 norm=0.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `4f4a79c5-2f9...` | 1.0000 | 1.0000 | 0.5000 | 72-Hour Emergency Supply Policy  State law... |
| 2 | `49e59ab8-e5f...` | 0.9959 | 0.7831 | 0.4984 | The following drug categories are not part of... |
| 3 | `6b9bd6ea-bda...` | 0.9917 | 0.5646 | 0.4969 | Over-the-Counter (OTC)... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=4f4a79c5-2f96-405b-9d1e-... rerank_score=0.5000
    score: raw=1.0 norm=1.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=49e59ab8-e5f8-4aaf-be6a-... rerank_score=0.4984
    score: raw=0.9959 norm=0.7831 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=6b9bd6ea-bda6-44fe-99f1-... rerank_score=0.4969
    score: raw=0.9917 norm=0.5646 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=7f6838ec-10b4-4a86-9e58-... rerank_score=0.4928
    score: raw=0.9809 norm=0.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `bdca20a8-a22b-49e4-a858-1b844ab41dbb` | sim=0.920 rerank=0.657 dist=0.160 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `8436c85b-64d8-4960-80a9-2fef4150196d` | sim=0.917 rerank=0.656 dist=0.166 Sunshine Provider Manual | Drugs may be dispensed up to a 34-day supply on most medications and up to a...
  3. `88ffa0c2-28d1-4048-a91e-aa569dba1f99` | sim=0.909 rerank=0.653 dist=0.182 Sunshine Provider Manual | • 
Drugs used to treat infertility 
• 
Experimental/investigational...
  4. `beae8b4c-5e70-4f1d-aef5-26176f530ff8` | sim=0.894 rerank=0.648 dist=0.212 Sunshine Provider Manual | The following drug categories are not part of the Sunshine Health PDL and...

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=bdca20a8-a22... sim=0.920 doc=Sunshine Provider Manual
  2. id=e966e52d-90c... sim=0.920 doc=Sunshine Provider Manual
  3. id=4f4a79c5-2f9... sim=0.920 doc=Sunshine Provider Manual
  4. id=8436c85b-64d... sim=0.917 doc=Sunshine Provider Manual
  5. id=f3cabd77-da5... sim=0.917 doc=Sunshine Provider Manual
  6. id=5d8bfc2f-e6a... sim=0.917 doc=Sunshine Provider Manual
  7. id=88ffa0c2-28d... sim=0.909 doc=Sunshine Provider Manual
  8. id=cda5ec66-bf8... sim=0.909 doc=Sunshine Provider Manual
  9. id=7f6838ec-10b... sim=0.909 doc=Sunshine Provider Manual
  10. id=beae8b4c-5e7... sim=0.894 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=bdca20a8-a22... rerank=0.657 sim=0.920
  2. id=e966e52d-90c... rerank=0.657 sim=0.920
  3. id=4f4a79c5-2f9... rerank=0.657 sim=0.920
  4. id=8436c85b-64d... rerank=0.656 sim=0.917
  5. id=f3cabd77-da5... rerank=0.656 sim=0.917
  6. id=5d8bfc2f-e6a... rerank=0.656 sim=0.917
  7. id=88ffa0c2-28d... rerank=0.653 sim=0.909
  8. id=cda5ec66-bf8... rerank=0.653 sim=0.909
  9. id=7f6838ec-10b... rerank=0.653 sim=0.909
  10. id=beae8b4c-5e7... rerank=0.648 sim=0.894

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `bdca20a8-a22...` | 0.9198 | 1.0000 | 0.6574 | 72-Hour Emergency Supply Policy  State law... |
| 2 | `e966e52d-90c...` | 0.9198 | 1.0000 | 0.6574 | 72-Hour Emergency Supply Policy  State law... |
| 3 | `4f4a79c5-2f9...` | 0.9198 | 1.0000 | 0.6574 | 72-Hour Emergency Supply Policy  State law... |

**Per-chunk signals (raw, norm, weight):**
  id=bdca20a8-a22b-49e4-a... rerank_score=0.657
    score: raw=0.9198 norm=1.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=e966e52d-90c3-4a6d-9... rerank_score=0.657
    score: raw=0.9198 norm=1.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=4f4a79c5-2f96-405b-9... rerank_score=0.657
    score: raw=0.9198 norm=1.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=8436c85b-64d8-4960-8... rerank_score=0.656
    score: raw=0.9169 norm=0.887 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=f3cabd77-da5b-4449-9... rerank_score=0.656
    score: raw=0.9169 norm=0.887 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=5d8bfc2f-e6a9-47bc-b... rerank_score=0.656
    score: raw=0.9169 norm=0.887 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=88ffa0c2-28d1-4048-a... rerank_score=0.653
    score: raw=0.9089 norm=0.5725 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=cda5ec66-bf82-4da0-8... rerank_score=0.653
    score: raw=0.9089 norm=0.5725 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=7f6838ec-10b4-4a86-9... rerank_score=0.653
    score: raw=0.9089 norm=0.5725 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=beae8b4c-5e70-4f1d-a... rerank_score=0.648
    score: raw=0.8942 norm=0.0 weight=0.3
    tag_match: raw=0.0 norm=1.0 weight=0.25
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | doc: Sunshine Provider Manual | raw_score=35.460 rerank=0.500
- text: 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to dispense a 72-hour (three-day) supply of certain 
medications to a member awaiting a prior authorization determination. The purpose is to avoid 
interruption of current therapy or delay in the initiation of therapy. All...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | doc: Sunshine Provider Manual | raw_score=36.140 rerank=0.500
- text: 111 72-Hour Emergency Supply Policy ...................................................................................................................
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `bdca20a8-a22b-49e4-a858-1b844ab41dbb` | doc: Sunshine Provider Manual | sim=0.920 rerank=0.657 dist=0.160
- text: 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to dispense a 72-hour (three-day) supply of certain 
medications to a member awaiting a prior authorization determination. The purpose is to avoid 
interruption of current therapy or delay in the initiation of therapy. All...

**In syllabus** (expect_in_manual=true)

---

## dev_005

**Question:** How can a provider determine whether a service requires prior authorization?

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: ['utilization_management.prior_authorization']
- j_tags: ['provider']
- document_ids resolved: 18 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=19.033 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `220be833-d68d-481c-8d3a-91ac6cbf2dce` | raw_score=18.201 Sunshine Provider Manual | Sunshine Health provides a 24-hour help line to respond to requests for...
  3. `1eb4490c-5482-43a6-ab10-112dd92921bf` | raw_score=18.200 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...
  4. `ce5f30c3-1174-4180-abfa-1304b880ad86` | raw_score=15.899 document | 3 
• 
Service delivery address 
• 
Unit(s) of service requested  
• 
Dates...
  5. `9a5265c3-480b-4ceb-ad83-fa1d5dcc65b0` | raw_score=15.753 document | 2 
provider’s Florida Medicaid claims during a period of time, to determine...
  6. `0e57e17a-4abb-4308-b2c0-962d84f376ab` | raw_score=14.970 Sunshine Provider Manual | Every new prescription for the members noted above requires a new informed...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `bef681ed-0bbd-42de-ac0c-632f80ca11e9` | raw_score=15.889 Sunshine Provider Manual | Providers should use the Pre-Auth Check Tool to look up a service code to...
  2. `420953df-857c-4c08-8f08-0ad073132cca` | raw_score=15.674 Sunshine Provider Manual | Be told prior to getting a service how much it may cost them
  3. `1eb4490c-5482-43a6-ab10-112dd92921bf` | raw_score=15.547 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...
  4. `1d2d80cc-4d58-41da-9ebf-c727d8607fde` | raw_score=15.267 Sunshine Member Handbook | To be told prior to getting a service how much it may cost you
  5. `9a5265c3-480b-4ceb-ad83-fa1d5dcc65b0` | raw_score=14.240 document | 2 provider’s Florida Medicaid claims during a period of time, to determine...
  6. `49be0e82-6b23-4fc9-a276-8d29c1fe1926` | raw_score=14.232 Sunshine Provider Manual | During an episode of emergency care, Sunshine Health does not require prior...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `bef681ed-0bb...` | 0.7230 | 1.0000 | 0.5029 | Providers should use the Pre-Auth Check Tool... |
| 2 | `420953df-857...` | 0.7030 | 0.8835 | 0.4954 | Be told prior to getting a service how much it... |
| 3 | `1eb4490c-548...` | 0.6908 | 0.8126 | 0.4908 | Providers should refer to the Pre-Auth Check... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=bef681ed-0bbd-42de-ac0c-... rerank_score=0.5029
    score: raw=0.723 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=420953df-857c-4c08-8f08-... rerank_score=0.4954
    score: raw=0.703 norm=0.8835 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1eb4490c-5482-43a6-ab10-... rerank_score=0.4908
    score: raw=0.6908 norm=0.8126 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=49be0e82-6b23-4fc9-a276-... rerank_score=0.4384
    score: raw=0.5511 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1d2d80cc-4d58-41da-9ebf-... rerank_score=0.4372
    score: raw=0.6629 norm=0.6502 weight=0.3
    tag_match: raw=0.2036 norm=0.5916 weight=0.25
      tag_source=line
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `4f4a79c5-2f9...` | 0.9681 | 1.0000 | 0.5948 | 72-Hour Emergency Supply Policy  State law... |
| 2 | `220be833-d68...` | 0.9508 | 0.9128 | 0.5883 | Sunshine Health provides a 24-hour help line... |
| 3 | `1eb4490c-548...` | 0.9507 | 0.9126 | 0.5883 | Providers should refer to the Pre-Auth Check... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=4f4a79c5-2f96-405b-9d1e-... rerank_score=0.5948
    score: raw=0.9681 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=0.9604 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=220be833-d68d-481c-8d3a-... rerank_score=0.5883
    score: raw=0.9508 norm=0.9128 weight=0.3
    tag_match: raw=0.3417 norm=0.9604 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1eb4490c-5482-43a6-ab10-... rerank_score=0.5883
    score: raw=0.9507 norm=0.9126 weight=0.3
    tag_match: raw=0.3417 norm=0.9604 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=ce5f30c3-1174-4180-abfa-... rerank_score=0.5537
    score: raw=0.8468 norm=0.3897 weight=0.3
    tag_match: raw=0.3557 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=0e57e17a-4abb-4308-b2c0-... rerank_score=0.5203
    score: raw=0.7693 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=0.9604 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `72c1b99b-0756-438b-b223-5e3736ed7ee6` | sim=0.933 rerank=0.769 dist=0.134 Sunshine Provider Manual | and Prior Authorization 
Utilization Management Program Overview
  2. `8c753010-57ae-42db-b2dc-7c07284d5494` | sim=0.928 rerank=0.767 dist=0.145 Sunshine Provider Manual | Prior authorization is required for all LTC services except custodial...
  3. `47ae9843-2ce3-45d1-bb56-bd4452ccf579` | sim=0.926 rerank=0.766 dist=0.149 Sunshine Provider Manual | • 
Non-emergent/non-urgent pre-scheduled services requiring prior...
  4. `1eb4490c-5482-43a6-ab10-112dd92921bf` | sim=0.919 rerank=0.764 dist=0.162 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...
  5. `e26ee630-cf35-40bf-b6cf-582688dc419d` | sim=0.923 rerank=0.659 dist=0.154 Sunshine Provider Manual | verify eligibility on the same day services are rendered.

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=72c1b99b-075... sim=0.933 doc=Sunshine Provider Manual
  2. id=6ad1a510-c6b... sim=0.933 doc=Sunshine Provider Manual
  3. id=8c753010-57a... sim=0.928 doc=Sunshine Provider Manual
  4. id=307d55d3-37e... sim=0.928 doc=Sunshine Provider Manual
  5. id=47ae9843-2ce... sim=0.926 doc=Sunshine Provider Manual
  6. id=61383785-afd... sim=0.926 doc=Sunshine Provider Manual
  7. id=e26ee630-cf3... sim=0.923 doc=Sunshine Provider Manual
  8. id=2b061175-0c6... sim=0.923 doc=Sunshine Provider Manual
  9. id=1eb4490c-548... sim=0.919 doc=Sunshine Provider Manual
  10. id=f52b484c-a9a... sim=0.919 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=72c1b99b-075... rerank=0.769 sim=0.933
  2. id=6ad1a510-c6b... rerank=0.769 sim=0.933
  3. id=8c753010-57a... rerank=0.767 sim=0.928
  4. id=307d55d3-37e... rerank=0.767 sim=0.928
  5. id=47ae9843-2ce... rerank=0.766 sim=0.926
  6. id=61383785-afd... rerank=0.766 sim=0.926
  7. id=1eb4490c-548... rerank=0.764 sim=0.919
  8. id=f52b484c-a9a... rerank=0.764 sim=0.919
  9. id=e26ee630-cf3... rerank=0.659 sim=0.923
  10. id=2b061175-0c6... rerank=0.659 sim=0.923

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `72c1b99b-075...` | 0.9331 | 1.0000 | 0.7692 | and Prior Authorization  Utilization... |
| 2 | `6ad1a510-c6b...` | 0.9331 | 1.0000 | 0.7692 | and Prior Authorization  Utilization... |
| 3 | `8c753010-57a...` | 0.9275 | 0.6004 | 0.7671 | Prior authorization is required for all LTC... |

**Per-chunk signals (raw, norm, weight):**
  id=72c1b99b-0756-438b-b... rerank_score=0.769
    score: raw=0.9331 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=6ad1a510-c6b7-4579-b... rerank_score=0.769
    score: raw=0.9331 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=8c753010-57ae-42db-b... rerank_score=0.767
    score: raw=0.9275 norm=0.6004 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=307d55d3-37ee-485f-8... rerank_score=0.767
    score: raw=0.9275 norm=0.6004 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=47ae9843-2ce3-45d1-b... rerank_score=0.766
    score: raw=0.9256 norm=0.4606 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=61383785-afdd-4434-8... rerank_score=0.766
    score: raw=0.9256 norm=0.4606 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1eb4490c-5482-43a6-a... rerank_score=0.764
    score: raw=0.9192 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=f52b484c-a9a9-4428-9... rerank_score=0.764
    score: raw=0.9192 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=e26ee630-cf35-40bf-b... rerank_score=0.659
    score: raw=0.9229 norm=0.2664 weight=0.3
    tag_match: raw=0.0025 norm=0.0 weight=0.25
      tag_source=line
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['verification.verify'] d=['eligibility.general'] j=[]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=2b061175-0c67-41da-a... rerank_score=0.659
    score: raw=0.9229 norm=0.2664 weight=0.3
    tag_match: raw=0.0025 norm=0.0 weight=0.25
      tag_source=line
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['provider']
      doc_tags (this chunk): p=['verification.verify'] d=['eligibility.general'] j=[]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | doc: Sunshine Provider Manual | raw_score=19.033 rerank=0.595
- text: 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to dispense a 72-hour (three-day) supply of certain 
medications to a member awaiting a prior authorization determination. The purpose is to avoid 
interruption of current therapy or delay in the initiation of therapy. All...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `bef681ed-0bbd-42de-ac0c-632f80ca11e9` | doc: Sunshine Provider Manual | raw_score=15.889 rerank=0.503
- text: Providers should use the Pre-Auth Check Tool to look up a service code to determine if prior authorization is needed.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `72c1b99b-0756-438b-b223-5e3736ed7ee6` | doc: Sunshine Provider Manual | sim=0.933 rerank=0.769 dist=0.134
- text: and Prior Authorization 
Utilization Management Program Overview

**In syllabus** (expect_in_manual=true)

---

## dev_006

**Question:** What are the weekend and after-hours on-call phone numbers?

**Tags from question (J/P/D):**
- p_tags: ['communication.call']
- d_tags: ['contact_information.phone']
- j_tags: (none)
- document_ids resolved: 9 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | raw_score=26.731 Sunshine Provider Manual | The utilization management department is staffed Monday through Friday from...
  2. `591744db-245e-4c41-82ff-14e9f82eddaf` | raw_score=18.101 Sunshine Provider Manual | In-office waiting times for visits shall not exceed 30 minutes. 
PCPs are...
  3. `48111001-ac56-422a-ae00-44a86bf5c743` | raw_score=17.827 Sunshine Provider Manual | PCP Access and Availability 
Each PCP is responsible for maintaining...
  4. `0bc13f48-0d92-4ac1-b8a1-aaf994321044` | raw_score=16.585 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  5. `7a520d6e-8357-49e9-82d0-cb2dedf14c87` | raw_score=15.317 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | raw_score=27.059 Sunshine Provider Manual | Weekend and After-Hours on Call-Number (for all products): 1-844-477-8313.
  2. `591744db-245e-4c41-82ff-14e9f82eddaf` | raw_score=16.993 Sunshine Provider Manual | PCPs are encouraged to offer after-hours appointments after 5 p.m. on office...
  3. `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | raw_score=15.845 Sunshine Provider Manual | 9 Key Contacts and Important Phone Numbers...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `0d9f9c4a-48c...` | 0.9976 | 1.0000 | 0.6761 | Weekend and After-Hours on Call-Number (for... |
| 2 | `591744db-245...` | 0.8119 | 0.3333 | 0.6064 | PCPs are encouraged to offer after-hours... |
| 3 | `1ce2b150-00b...` | 0.7190 | 0.0000 | 0.5716 | 9 Key Contacts and Important Phone Numbers... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=0d9f9c4a-48c2-475a-a1d2-... rerank_score=0.6761
    score: raw=0.9976 norm=1.0 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=591744db-245e-4c41-82ff-... rerank_score=0.6064
    score: raw=0.8119 norm=0.3333 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1ce2b150-00bd-4a56-9dbb-... rerank_score=0.5716
    score: raw=0.719 norm=0.0 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `0d9f9c4a-48c...` | 0.9995 | 1.0000 | 0.6768 | The utilization management department is... |
| 2 | `591744db-245...` | 0.9482 | 0.7413 | 0.6575 | In-office waiting times for visits shall not... |
| 3 | `48111001-ac5...` | 0.9403 | 0.7018 | 0.6546 | PCP Access and Availability  Each PCP is... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=0d9f9c4a-48c2-475a-a1d2-... rerank_score=0.6768
    score: raw=0.9995 norm=1.0 weight=0.3
    tag_match: raw=0.5664 norm=0.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=591744db-245e-4c41-82ff-... rerank_score=0.6575
    score: raw=0.9482 norm=0.7413 weight=0.3
    tag_match: raw=0.5664 norm=0.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=48111001-ac56-422a-ae00-... rerank_score=0.6546
    score: raw=0.9403 norm=0.7018 weight=0.3
    tag_match: raw=0.5664 norm=0.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=0bc13f48-0d92-4ac1-b8a1-... rerank_score=0.6356
    score: raw=0.8892 norm=0.4441 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=7a520d6e-8357-49e9-82d0-... rerank_score=0.6026
    score: raw=0.801 norm=0.0 weight=0.3
    tag_match: raw=0.567 norm=1.0 weight=0.25
      tag_source=document
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['communication.call'] contrib=[0.55]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.phone'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `1fd0dbe8-660a-4422-af45-88f61b6d0fd5` | sim=0.906 rerank=0.829 dist=0.188 Sunshine Provider Manual | The utilization management department is staffed Monday through Friday from...
  2. `a638f008-9f54-49b8-845c-5a0595c617e9` | sim=0.894 rerank=0.825 dist=0.211 Sunshine Provider Manual | PCP Access and Availability 
Each PCP is responsible for maintaining...
  3. `591744db-245e-4c41-82ff-14e9f82eddaf` | sim=0.890 rerank=0.823 dist=0.220 Sunshine Provider Manual | In-office waiting times for visits shall not exceed 30 minutes. 
PCPs are...
  4. `c7d685be-df5a-40e8-8e21-af3e25f789ed` | sim=0.895 rerank=0.507 dist=0.210 Preadmission_Screen_and_Resident_Review_ | Phone

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=1fd0dbe8-660... sim=0.906 doc=Sunshine Provider Manual
  2. id=0d9f9c4a-48c... sim=0.906 doc=Sunshine Provider Manual
  3. id=c7d685be-df5... sim=0.895 doc=Preadmission_Screen_and_Reside
  4. id=a638f008-9f5... sim=0.894 doc=Sunshine Provider Manual
  5. id=48111001-ac5... sim=0.894 doc=Sunshine Provider Manual
  6. id=aa5ea259-22c... sim=0.894 doc=Sunshine Provider Manual
  7. id=591744db-245... sim=0.890 doc=Sunshine Provider Manual
  8. id=988e9c00-ef0... sim=0.890 doc=Sunshine Provider Manual
  9. id=732cb8f0-579... sim=0.890 doc=Sunshine Provider Manual
  10. id=2af2789e-61f... sim=0.888 doc=Preadmission_Screen_and_Reside

**Ranks AFTER rerank (by rerank_score):**
  1. id=1fd0dbe8-660... rerank=0.829 sim=0.906
  2. id=0d9f9c4a-48c... rerank=0.829 sim=0.906
  3. id=a638f008-9f5... rerank=0.825 sim=0.894
  4. id=48111001-ac5... rerank=0.825 sim=0.894
  5. id=aa5ea259-22c... rerank=0.825 sim=0.894
  6. id=591744db-245... rerank=0.823 sim=0.890
  7. id=988e9c00-ef0... rerank=0.823 sim=0.890
  8. id=732cb8f0-579... rerank=0.823 sim=0.890
  9. id=c7d685be-df5... rerank=0.507 sim=0.895

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `1fd0dbe8-660...` | 0.9062 | 1.0000 | 0.8293 | The utilization management department is... |
| 2 | `0d9f9c4a-48c...` | 0.9062 | 1.0000 | 0.8293 | The utilization management department is... |
| 3 | `a638f008-9f5...` | 0.8944 | 0.3556 | 0.8249 | PCP Access and Availability  Each PCP is... |

**Per-chunk signals (raw, norm, weight):**
  id=1fd0dbe8-660a-4422-a... rerank_score=0.829
    score: raw=0.9062 norm=1.0 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=0d9f9c4a-48c2-475a-a... rerank_score=0.829
    score: raw=0.9062 norm=1.0 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=a638f008-9f54-49b8-8... rerank_score=0.825
    score: raw=0.8944 norm=0.3556 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=48111001-ac56-422a-a... rerank_score=0.825
    score: raw=0.8944 norm=0.3556 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=aa5ea259-22c7-42bb-b... rerank_score=0.825
    score: raw=0.8944 norm=0.3556 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=591744db-245e-4c41-8... rerank_score=0.823
    score: raw=0.8899 norm=0.1084 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=988e9c00-ef04-4785-9... rerank_score=0.823
    score: raw=0.8899 norm=0.1084 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=732cb8f0-5794-4e92-9... rerank_score=0.823
    score: raw=0.8899 norm=0.1084 weight=0.3
    tag_match: raw=0.5664 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap p: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['communication.call'] (q_score, doc_decayed, contrib): [('communication.call', 1.0, 0.1, 0.55)]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=c7d685be-df5a-40e8-8... rerank_score=0.507
    score: raw=0.8948 norm=0.3724 weight=0.3
    tag_match: raw=0.5473 norm=0.912 weight=0.25
      tag_source=line
      question_tags: p=['communication.call'] d=['contact_information.phone'] j=[]
      doc_tags (this chunk): p=[] d=['contact_information.phone'] j=[]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.phone'] (q_score, doc_decayed, contrib): [('contact_information.phone', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | doc: Sunshine Provider Manual | raw_score=26.731 rerank=0.677
- text: The utilization management department is staffed Monday through Friday from 8 a.m. to 8 p.m. 
Eastern. Providers should call Provider Services at 1-844-477-8313 and select the prompt for 
authorization. Weekend and After-Hours on Call-Number (for all products): 1-844-477-8313.
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | doc: Sunshine Provider Manual | raw_score=27.059 rerank=0.676
- text: Weekend and After-Hours on Call-Number (for all products): 1-844-477-8313.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `1fd0dbe8-660a-4422-af45-88f61b6d0fd5` | doc: Sunshine Provider Manual | sim=0.906 rerank=0.829 dist=0.188
- text: The utilization management department is staffed Monday through Friday from 8 a.m. to 8 p.m. 
Eastern. Providers should call Provider Services at 1-844-477-8313 and select the prompt for 
authorization. Weekend and After-Hours on Call-Number (for all products): 1-844-477-8313.

**In syllabus** (expect_in_manual=true)

---

## dev_007

**Question:** Summarize the Secure Provider Portal registration process.

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: ['contact_information.portal']
- j_tags: ['provider']
- document_ids resolved: 18 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `0ca7b77c-1c5f-48c3-8867-aa96ffd0f4e3` | raw_score=16.016 Sunshine Provider Manual | Providers who have internet access and choose not to submit claims via EDI...
  2. `05665c2d-3616-48d1-9518-21dbc1a0677e` | raw_score=14.406 Sunshine Provider Manual | Preferred Method 
Providers are asked to verify member eligibility by using...
  3. `bef681ed-0bbd-42de-ac0c-632f80ca11e9` | raw_score=14.227 Sunshine Provider Manual | Medical practitioners and providers are to submit requests for inpatient or...
  4. `5a1469db-d577-4515-9664-9f7566342cfa` | raw_score=13.870 Sunshine Provider Manual | Practitioners must submit a notice of pregnancy (NOP) form to Sunshine...
  5. `b637cc3f-f855-46af-8ac9-f4b1fec2fd19` | raw_score=13.857 document | An exception to the requirement to notify the Agency of changes within 30...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | raw_score=17.149 Sunshine Provider Manual | 15 Secure Provider Portal...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `1ce2b150-00b...` | 0.8224 | 1.0000 | 0.5402 | 15 Secure Provider Portal... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=1ce2b150-00bd-4a56-9dbb-... rerank_score=0.5402
    score: raw=0.8224 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.portal'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `0ca7b77c-1c5...` | 0.8548 | 1.0000 | 0.5523 | Providers who have internet access and choose... |
| 2 | `05665c2d-361...` | 0.7106 | 0.3108 | 0.4983 | Preferred Method  Providers are asked to... |
| 3 | `bef681ed-0bb...` | 0.6901 | 0.2131 | 0.4906 | Medical practitioners and providers are to... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=0ca7b77c-1c5f-48c3-8867-... rerank_score=0.5523
    score: raw=0.8548 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.portal'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=05665c2d-3616-48d1-9518-... rerank_score=0.4983
    score: raw=0.7106 norm=0.3108 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.portal'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=bef681ed-0bbd-42de-ac0c-... rerank_score=0.4906
    score: raw=0.6901 norm=0.2131 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.portal'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=b637cc3f-f855-46af-8ac9-... rerank_score=0.4747
    score: raw=0.6455 norm=0.0 weight=0.3
    tag_match: raw=0.3443 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.portal'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=5a1469db-d577-4515-9664-... rerank_score=0.4745
    score: raw=0.6472 norm=0.0079 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['contact_information.portal'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['provider'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `0edf2010-cc25-4e16-b9f8-29946f89eae4` | sim=0.903 rerank=0.758 dist=0.194 Sunshine Provider Manual | guidelines on general outreach and enrollment, claims processing and systems...
  2. `0716b163-1779-4d27-a883-d3c1464de9d2` | sim=0.901 rerank=0.757 dist=0.198 Sunshine Provider Manual | Recredentialing 
Credentialing and Recredentialing Overview
  3. `6a31adf1-34ba-4f06-a901-de2b4705368e` | sim=0.894 rerank=0.755 dist=0.211 Sunshine Provider Manual | Providers who have internet access and choose not to submit claims via EDI...
  4. `0208178e-3606-4558-b426-71f5cc9c6964` | sim=0.903 rerank=0.571 dist=0.194 59G-1.060_Enrollment.pdf | Provider Enrollment Renewal...
  5. `3700e5c5-a7ee-4632-a7fd-10e86778246d` | sim=0.898 rerank=0.569 dist=0.204 59G-1.060_Enrollment.pdf | Provider Screening...
  6. `93d6faf2-232a-40c7-9f7e-e6ed63b8eee5` | sim=0.897 rerank=0.569 dist=0.205 59G-1.060_Enrollment.pdf | Providers who prescribe, order, or administer medications and who are...

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=0208178e-360... sim=0.903 doc=59G-1.060_Enrollment.pdf
  2. id=0edf2010-cc2... sim=0.903 doc=Sunshine Provider Manual
  3. id=215ea3f0-12d... sim=0.903 doc=Sunshine Provider Manual
  4. id=b2ebfd7a-ef6... sim=0.903 doc=Sunshine Provider Manual
  5. id=0716b163-177... sim=0.901 doc=Sunshine Provider Manual
  6. id=836363d1-d58... sim=0.901 doc=Sunshine Provider Manual
  7. id=3700e5c5-a7e... sim=0.898 doc=59G-1.060_Enrollment.pdf
  8. id=93d6faf2-232... sim=0.897 doc=59G-1.060_Enrollment.pdf
  9. id=6a31adf1-34b... sim=0.894 doc=Sunshine Provider Manual
  10. id=3c20e18b-4ee... sim=0.894 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=0edf2010-cc2... rerank=0.758 sim=0.903
  2. id=215ea3f0-12d... rerank=0.758 sim=0.903
  3. id=b2ebfd7a-ef6... rerank=0.758 sim=0.903
  4. id=0716b163-177... rerank=0.757 sim=0.901
  5. id=836363d1-d58... rerank=0.757 sim=0.901
  6. id=6a31adf1-34b... rerank=0.755 sim=0.894
  7. id=3c20e18b-4ee... rerank=0.755 sim=0.894
  8. id=0208178e-360... rerank=0.571 sim=0.903
  9. id=3700e5c5-a7e... rerank=0.569 sim=0.898
  10. id=93d6faf2-232... rerank=0.569 sim=0.897

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `0edf2010-cc2...` | 0.9029 | 0.9803 | 0.7579 | guidelines on general outreach and enrollment,... |
| 2 | `215ea3f0-12d...` | 0.9029 | 0.9803 | 0.7579 | guidelines on general outreach and enrollment,... |
| 3 | `b2ebfd7a-ef6...` | 0.9029 | 0.9803 | 0.7579 | guidelines on general outreach and enrollment,... |

**Per-chunk signals (raw, norm, weight):**
  id=0edf2010-cc25-4e16-b... rerank_score=0.758
    score: raw=0.9029 norm=0.9803 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=215ea3f0-12dc-4649-a... rerank_score=0.758
    score: raw=0.9029 norm=0.9803 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=b2ebfd7a-ef6c-4e07-a... rerank_score=0.758
    score: raw=0.9029 norm=0.9803 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=0716b163-1779-4d27-a... rerank_score=0.757
    score: raw=0.9008 norm=0.7398 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=836363d1-d585-4ebe-b... rerank_score=0.757
    score: raw=0.9008 norm=0.7398 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=6a31adf1-34ba-4f06-a... rerank_score=0.755
    score: raw=0.8944 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=3c20e18b-4ee2-4258-b... rerank_score=0.755
    score: raw=0.8944 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=0208178e-3606-4558-b... rerank_score=0.571
    score: raw=0.9031 norm=1.0 weight=0.3
    tag_match: raw=0.3443 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=3700e5c5-a7ee-4632-a... rerank_score=0.569
    score: raw=0.8982 norm=0.4406 weight=0.3
    tag_match: raw=0.3443 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=93d6faf2-232a-40c7-9... rerank_score=0.569
    score: raw=0.8974 norm=0.342 weight=0.3
    tag_match: raw=0.3443 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['contact_information.portal'] j=['provider']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'submission.submit', 'communication.contact', 'compliance_action.required', 'compliance_action.prohibited'] d=['benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'disputes.appeal', 'compliance.hipaa', 'pharmacy.general', 'provider.services'] j=['state', 'program', 'provider', 'state.florida', 'program.hiv_aids', 'program.medicaid', 'provider.general', 'payor.unitedhealthcare']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['contact_information.portal'] (q_score, doc_decayed, contrib): [('contact_information.portal', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['provider'] (q_score, doc_decayed, contrib): [('provider', 1.0, 0.1, 0.55)]
    authority_level: raw=0.0 norm=0.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `0ca7b77c-1c5f-48c3-8867-aa96ffd0f4e3` | doc: Sunshine Provider Manual | raw_score=16.016 rerank=0.552
- text: Providers who have internet access and choose not to submit claims via EDI or on paper may 
submit claims directly to Sunshine Health by using the Secure Provider Portal. Providers must 
request access to the secure site by registering for a username and password. 
Providers then may file...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | doc: Sunshine Provider Manual | raw_score=17.149 rerank=0.540
- text: 15 Secure Provider Portal ...........................................................................................................................
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `0edf2010-cc25-4e16-b9f8-29946f89eae4` | doc: Sunshine Provider Manual | sim=0.903 rerank=0.758 dist=0.194
- text: guidelines on general outreach and enrollment, claims processing and systems technologies; and 
an overview of resources and tools available to them. Providers must complete this training 
within 30 days of becoming participating in the network.

**In syllabus** (expect_in_manual=true)

---

## dev_008

**Question:** What is the process for claims reconsiderations and disputes?

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: ['claims.general', 'disputes', 'disputes.appeal', 'disputes.general']
- j_tags: (none)
- document_ids resolved: 14 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `4335c5e8-619a-42ef-a658-1af27078d636` | raw_score=26.770 Sunshine Provider Manual | Providers must include the original claim number on the complaint and...
  2. `2368270f-2be4-4d00-946a-0cd07dd07784` | raw_score=26.164 Sunshine Provider Manual | ➢ See Process for Claims Reconsiderations and Disputes
  3. `571bda6e-8536-4b59-99b0-d95336a61641` | raw_score=20.803 Sunshine Provider Manual | All requests for corrected claims or reconsiderations/claim disputes must be...
  4. `66b378b8-a1d5-47e7-b017-e5d6e4593dc3` | raw_score=20.001 Sunshine Provider Manual | Reconsideration/Claim Disputes...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `66b378b8-a1d5-47e7-b017-e5d6e4593dc3` | raw_score=26.912 Sunshine Provider Manual | 125 Process for Claims Reconsiderations and Disputes...
  2. `2368270f-2be4-4d00-946a-0cd07dd07784` | raw_score=26.912 Sunshine Provider Manual | ➢ See Process for Claims Reconsiderations and Disputes
  3. `4335c5e8-619a-42ef-a658-1af27078d636` | raw_score=18.396 Sunshine Provider Manual | Providers must include the original claim number on the complaint and...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `2368270f-2be...` | 0.9975 | 1.0000 | 0.6690 | ➢ See Process for Claims Reconsiderations and... |
| 2 | `66b378b8-a1d...` | 0.9975 | 1.0000 | 0.6067 | 125 Process for Claims Reconsiderations and... |
| 3 | `4335c5e8-619...` | 0.8910 | 0.0000 | 0.5667 | Providers must include the original claim... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=2368270f-2be4-4d00-946a-... rerank_score=0.6690
    score: raw=0.9975 norm=1.0 weight=0.3
    tag_match: raw=0.544 norm=1.0 weight=0.25
      tag_source=line
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] contrib=[0.55, 0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=66b378b8-a1d5-47e7-b017-... rerank_score=0.6067
    score: raw=0.9975 norm=1.0 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] contrib=[0.55, 0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=4335c5e8-619a-42ef-a658-... rerank_score=0.5667
    score: raw=0.891 norm=0.0 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] contrib=[0.55, 0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `2368270f-2be...` | 0.9993 | 0.9897 | 0.6697 | ➢ See Process for Claims Reconsiderations and... |
| 2 | `4335c5e8-619...` | 0.9995 | 1.0000 | 0.6075 | Providers must include the original claim... |
| 3 | `571bda6e-853...` | 0.9876 | 0.3581 | 0.6030 | All requests for corrected claims or... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=2368270f-2be4-4d00-946a-... rerank_score=0.6697
    score: raw=0.9993 norm=0.9897 weight=0.3
    tag_match: raw=0.544 norm=1.0 weight=0.25
      tag_source=line
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] contrib=[0.55, 0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=4335c5e8-619a-42ef-a658-... rerank_score=0.6075
    score: raw=0.9995 norm=1.0 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] contrib=[0.55, 0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=571bda6e-8536-4b59-99b0-... rerank_score=0.6030
    score: raw=0.9876 norm=0.3581 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] contrib=[0.55, 0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=66b378b8-a1d5-47e7-b017-... rerank_score=0.6005
    score: raw=0.9809 norm=0.0 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] contrib=[0.55, 0.55, 0.55, 0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `c56a3461-2085-4859-a105-141d0663aad1` | sim=0.974 rerank=0.848 dist=0.052 Sunshine Provider Manual | ➢ See Process for Claims Reconsiderations and Disputes
  2. `71df57ef-27e6-443e-bdc7-735e5d7eecd8` | sim=0.941 rerank=0.773 dist=0.118 Sunshine Provider Manual | Reconsideration/Claim Disputes 
Definitions 
The definition of a corrected...
  3. `51f9d9fb-67b0-42b2-8c9e-6aec2956e361` | sim=0.937 rerank=0.771 dist=0.127 Sunshine Provider Manual | Providers must include the original claim number on the complaint and...
  4. `5238e05f-9774-4c3f-a2b3-014fa6086d66` | sim=0.967 rerank=0.658 dist=0.067 Sunshine Provider Manual | Reconsiderations or Claim 
Dispute**

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=c56a3461-208... sim=0.974 doc=Sunshine Provider Manual
  2. id=2368270f-2be... sim=0.974 doc=Sunshine Provider Manual
  3. id=5238e05f-977... sim=0.967 doc=Sunshine Provider Manual
  4. id=df92bf77-023... sim=0.967 doc=Sunshine Provider Manual
  5. id=f6cfedc0-012... sim=0.967 doc=Sunshine Provider Manual
  6. id=71df57ef-27e... sim=0.941 doc=Sunshine Provider Manual
  7. id=7f12aeb6-43a... sim=0.941 doc=Sunshine Provider Manual
  8. id=fe442d75-0d4... sim=0.941 doc=Sunshine Provider Manual
  9. id=51f9d9fb-67b... sim=0.937 doc=Sunshine Provider Manual
  10. id=4335c5e8-619... sim=0.937 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=c56a3461-208... rerank=0.848 sim=0.974
  2. id=2368270f-2be... rerank=0.848 sim=0.974
  3. id=71df57ef-27e... rerank=0.773 sim=0.941
  4. id=7f12aeb6-43a... rerank=0.773 sim=0.941
  5. id=fe442d75-0d4... rerank=0.773 sim=0.941
  6. id=51f9d9fb-67b... rerank=0.771 sim=0.937
  7. id=4335c5e8-619... rerank=0.771 sim=0.937
  8. id=5238e05f-977... rerank=0.658 sim=0.967
  9. id=df92bf77-023... rerank=0.658 sim=0.967
  10. id=f6cfedc0-012... rerank=0.658 sim=0.967

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `c56a3461-208...` | 0.9740 | 1.0000 | 0.8478 | ➢ See Process for Claims Reconsiderations and... |
| 2 | `2368270f-2be...` | 0.9740 | 1.0000 | 0.8478 | ➢ See Process for Claims Reconsiderations and... |
| 3 | `71df57ef-27e...` | 0.9410 | 0.1162 | 0.7730 | Reconsideration/Claim Disputes  Definitions... |

**Per-chunk signals (raw, norm, weight):**
  id=c56a3461-2085-4859-a... rerank_score=0.848
    score: raw=0.974 norm=1.0 weight=0.3
    tag_match: raw=0.544 norm=1.0 weight=0.25
      tag_source=line
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=[] d=['disputes', 'claims.general', 'disputes.appeal', 'disputes.general'] j=[]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=2368270f-2be4-4d00-9... rerank_score=0.848
    score: raw=0.974 norm=1.0 weight=0.3
    tag_match: raw=0.544 norm=1.0 weight=0.25
      tag_source=line
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=[] d=['disputes', 'claims.general', 'disputes.appeal', 'disputes.general'] j=[]
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=71df57ef-27e6-443e-b... rerank_score=0.773
    score: raw=0.941 norm=0.1162 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=7f12aeb6-43a5-442d-8... rerank_score=0.773
    score: raw=0.941 norm=0.1162 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=fe442d75-0d43-4abe-a... rerank_score=0.773
    score: raw=0.941 norm=0.1162 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=51f9d9fb-67b0-42b2-8... rerank_score=0.771
    score: raw=0.9366 norm=0.0 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=4335c5e8-619a-42ef-a... rerank_score=0.771
    score: raw=0.9366 norm=0.0 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=5238e05f-9774-4c3f-a... rerank_score=0.658
    score: raw=0.9666 norm=0.8021 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1
  id=df92bf77-023b-4a7e-8... rerank_score=0.658
    score: raw=0.9666 norm=0.8021 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1
  id=f6cfedc0-0122-479e-8... rerank_score=0.658
    score: raw=0.9666 norm=0.8021 weight=0.3
    tag_match: raw=0.3444 norm=0.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['claims.general', 'disputes', 'disputes.appeal', 'disputes.general'] j=[]
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['disputes.appeal', 'disputes.general', 'disputes', 'claims.general'] (q_score, doc_decayed, contrib): [('disputes.appeal', 1.0, 0.1, 0.55), ('disputes.general', 1.0, 0.1, 0.55), ('disputes', 1.0, 0.1, 0.55), ('claims.general', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=0.0 norm=0.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `2368270f-2be4-4d00-946a-0cd07dd07784` | doc: Sunshine Provider Manual | raw_score=26.164 rerank=0.670
- text: ➢ See Process for Claims Reconsiderations and Disputes
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `2368270f-2be4-4d00-946a-0cd07dd07784` | doc: Sunshine Provider Manual | raw_score=26.912 rerank=0.669
- text: ➢ See Process for Claims Reconsiderations and Disputes
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `c56a3461-2085-4859-a105-141d0663aad1` | doc: Sunshine Provider Manual | sim=0.974 rerank=0.848 dist=0.052
- text: ➢ See Process for Claims Reconsiderations and Disputes

**In syllabus** (expect_in_manual=true)

---

## dev_009

**Question:** What is the Medicare Part B prior authorization process in California?

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: ['utilization_management.prior_authorization']
- j_tags: ['regulatory_authority.cms']
- document_ids resolved: 11 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `e9ea1bbc-358a-4ea2-ab5c-a200217d7dca` | raw_score=20.475 document | (a) Medicare Part A Premium. Florida Medicaid will pay the Part A premium...
  2. `105fb1a2-ebdb-44ab-814e-21887d9183c7` | raw_score=17.191 Sunshine Provider Manual | resort. If an authorization is required, the providers still must obtain...
  3. `49e59ab8-e5f8-4aaf-be6a-7c36dcd3452f` | raw_score=15.762 Sunshine Provider Manual | The following drug categories are not part of the Sunshine Health PDL and...
  4. `40e99cf1-6358-4de3-a2f5-27a076b18d3f` | raw_score=14.987 Sunshine Provider Manual | Newly approved drug products are not normally placed on the preferred drug...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `49e59ab8-e5f8-4aaf-be6a-7c36dcd3452f` | raw_score=19.903 Sunshine Provider Manual | Drugs covered under Medicare Part B and/or Medicare Part D
  2. `e9ea1bbc-358a-4ea2-ab5c-a200217d7dca` | raw_score=18.558 document | Bill Medicare for Medicare-allowable Part B inpatient ancillary services.
  3. `40e99cf1-6358-4de3-a2f5-27a076b18d3f` | raw_score=16.938 Sunshine Provider Manual | During this period, access to these medications is considered through the...
  4. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=15.428 Sunshine Provider Manual | 110 Prior Authorization Process for Medications...
  5. `e9ea1bbc-358a-4ea2-ab5c-a200217d7dca` | raw_score=15.360 document | Florida Medicaid will pay the Part A premium for dually eligible recipients...

**BM25 Sentence Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `e9ea1bbc-358...` | 0.8979 | 0.8368 | 0.5697 | Bill Medicare for Medicare-allowable Part B... |
| 2 | `49e59ab8-e5f...` | 0.9420 | 1.0000 | 0.5415 | Drugs covered under Medicare Part B and/or... |
| 3 | `40e99cf1-635...` | 0.8080 | 0.5033 | 0.5348 | During this period, access to these... |

**BM25 Sentence per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=e9ea1bbc-358a-4ea2-ab5c-... rerank_score=0.5697
    score: raw=0.8979 norm=0.8368 weight=0.3
    tag_match: raw=0.3457 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=49e59ab8-e5f8-4aaf-be6a-... rerank_score=0.5415
    score: raw=0.942 norm=1.0 weight=0.3
    tag_match: raw=0.2025 norm=0.0 weight=0.25
      tag_source=line
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=40e99cf1-6358-4de3-a2f5-... rerank_score=0.5348
    score: raw=0.808 norm=0.5033 weight=0.3
    tag_match: raw=0.3417 norm=0.9724 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['regulatory_authority.cms'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=6b9bd6ea-bda6-44fe-99f1-... rerank_score=0.4865
    score: raw=0.6791 norm=0.0253 weight=0.3
    tag_match: raw=0.3417 norm=0.9724 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['regulatory_authority.cms'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=e9ea1bbc-358a-4ea2-ab5c-... rerank_score=0.4851
    score: raw=0.6723 norm=0.0 weight=0.3
    tag_match: raw=0.3457 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**BM25 Paragraph Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (norm BM25) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------------|--------------|----------------|---------|
| 1 | `e9ea1bbc-358...` | 0.9852 | 1.0000 | 0.6025 | (a) Medicare Part A Premium. Florida Medicaid... |
| 2 | `105fb1a2-ebd...` | 0.9177 | 0.6851 | 0.5759 | resort. If an authorization is required, the... |
| 3 | `49e59ab8-e5f...` | 0.8368 | 0.3074 | 0.5456 | The following drug categories are not part of... |

**BM25 Paragraph per-chunk signals (raw, norm, weight) — Top 5:**
  Weights: score=0.3  tag_match=0.25  authority_level=0.15  length=0.1
  id=e9ea1bbc-358a-4ea2-ab5c-... rerank_score=0.6025
    score: raw=0.9852 norm=1.0 weight=0.3
    tag_match: raw=0.3457 norm=1.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=105fb1a2-ebdb-44ab-814e-... rerank_score=0.5759
    score: raw=0.9177 norm=0.6851 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['regulatory_authority.cms'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=49e59ab8-e5f8-4aaf-be6a-... rerank_score=0.5456
    score: raw=0.8368 norm=0.3074 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['regulatory_authority.cms'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=40e99cf1-6358-4de3-a2f5-... rerank_score=0.5209
    score: raw=0.771 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=0.0 weight=0.25
      tag_source=document
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['utilization_management.prior_authorization'] contrib=[0.55]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} tags=['regulatory_authority.cms'] contrib=[0.55]
    authority_level: raw=0.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Vector Retrieved (similarity, rerank_score) [deduped by text, top 10]:**
  1. `72c1b99b-0756-438b-b223-5e3736ed7ee6` | sim=0.896 rerank=0.755 dist=0.208 Sunshine Provider Manual | and Prior Authorization 
Utilization Management Program Overview
  2. `47ae9843-2ce3-45d1-bb56-bd4452ccf579` | sim=0.889 rerank=0.753 dist=0.222 Sunshine Provider Manual | • 
Non-emergent/non-urgent pre-scheduled services requiring prior...
  3. `8c753010-57ae-42db-b2dc-7c07284d5494` | sim=0.887 rerank=0.752 dist=0.227 Sunshine Provider Manual | Prior authorization is required for all LTC services except custodial...
  4. `b04b30b3-559c-434d-a169-cf04e2f3bd0a` | sim=0.886 rerank=0.752 dist=0.227 Sunshine Provider Manual | In general, prior authorization for MMA, CWSP, SMI and HIV/AIDS members is...
  5. `1c912807-a31c-4a35-9003-8b40989f137a` | sim=0.880 rerank=0.749 dist=0.239 Sunshine Provider Manual | Non-Specialty/Retail Medications 
To efficiently process prior authorization...

**Reranker config (emits):**
- combination: additive
- score: weight=0.3 formula=direct params={}
- tag_match: weight=0.25 formula=direct_context params={'j_weight': 0.4, 'd_weight': 0.4, 'p_weight': 0.2, 'p_count_weight': 0.4, 'd_count_weight': 0.6, 'count_scale': 0.4, 'intensity_scale': 0.3, 'homogeneity_scale': 0.2, 'context_weight': 0.2, 'doc_decay_factor': 0.1}
- authority_level: weight=0.15 formula=rank params={'contract_source_of_truth': 1.0, 'operational_suggested': 0.65, 'fyi_not_citable': 0.35, 'unknown': 0.0}
- length: weight=0.1 formula=floor params={'min_chars': 50}

**Ranks BEFORE rerank (by similarity):**
  1. id=72c1b99b-075... sim=0.896 doc=Sunshine Provider Manual
  2. id=6ad1a510-c6b... sim=0.896 doc=Sunshine Provider Manual
  3. id=47ae9843-2ce... sim=0.889 doc=Sunshine Provider Manual
  4. id=61383785-afd... sim=0.889 doc=Sunshine Provider Manual
  5. id=8c753010-57a... sim=0.887 doc=Sunshine Provider Manual
  6. id=307d55d3-37e... sim=0.887 doc=Sunshine Provider Manual
  7. id=b04b30b3-559... sim=0.886 doc=Sunshine Provider Manual
  8. id=69198ac1-9b1... sim=0.886 doc=Sunshine Provider Manual
  9. id=1c912807-a31... sim=0.880 doc=Sunshine Provider Manual
  10. id=f5867631-9a2... sim=0.880 doc=Sunshine Provider Manual

**Ranks AFTER rerank (by rerank_score):**
  1. id=72c1b99b-075... rerank=0.755 sim=0.896
  2. id=6ad1a510-c6b... rerank=0.755 sim=0.896
  3. id=47ae9843-2ce... rerank=0.753 sim=0.889
  4. id=61383785-afd... rerank=0.753 sim=0.889
  5. id=8c753010-57a... rerank=0.752 sim=0.887
  6. id=307d55d3-37e... rerank=0.752 sim=0.887
  7. id=b04b30b3-559... rerank=0.752 sim=0.886
  8. id=69198ac1-9b1... rerank=0.752 sim=0.886
  9. id=1c912807-a31... rerank=0.749 sim=0.880
  10. id=f5867631-9a2... rerank=0.749 sim=0.880

**Top 3 by rerank (raw | normalized | final):**
| Rank | Chunk | Raw (sim) | Norm (score) | Final (rerank) | Snippet |
|------|-------|-----------|--------------|----------------|---------|
| 1 | `72c1b99b-075...` | 0.8960 | 1.0000 | 0.7553 | and Prior Authorization  Utilization... |
| 2 | `6ad1a510-c6b...` | 0.8960 | 1.0000 | 0.7553 | and Prior Authorization  Utilization... |
| 3 | `47ae9843-2ce...` | 0.8892 | 0.5684 | 0.7527 | •  Non-emergent/non-urgent pre-scheduled... |

**Per-chunk signals (raw, norm, weight):**
  id=72c1b99b-0756-438b-b... rerank_score=0.755
    score: raw=0.896 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=6ad1a510-c6b7-4579-b... rerank_score=0.755
    score: raw=0.896 norm=1.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=47ae9843-2ce3-45d1-b... rerank_score=0.753
    score: raw=0.8892 norm=0.5684 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=61383785-afdd-4434-8... rerank_score=0.753
    score: raw=0.8892 norm=0.5684 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=8c753010-57ae-42db-b... rerank_score=0.752
    score: raw=0.8865 norm=0.3993 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=307d55d3-37ee-485f-8... rerank_score=0.752
    score: raw=0.8865 norm=0.3993 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=b04b30b3-559c-434d-a... rerank_score=0.752
    score: raw=0.8864 norm=0.3883 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=69198ac1-9b15-4b0f-8... rerank_score=0.752
    score: raw=0.8864 norm=0.3883 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=1c912807-a31c-4a35-9... rerank_score=0.749
    score: raw=0.8803 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1
  id=f5867631-9a2a-40bb-a... rerank_score=0.749
    score: raw=0.8803 norm=0.0 weight=0.3
    tag_match: raw=0.3417 norm=1.0 weight=0.25
      tag_source=document
      question_tags: p=[] d=['utilization_management.prior_authorization'] j=['regulatory_authority.cms']
      doc_tags (this chunk): p=['submission', 'verification', 'communication', 'review.review', 'dispute.appeal', 'submission.submit', 'communication.call', 'communication.email'] d=['disputes', 'benefits.dme', 'claims.denial', 'tools.general', 'claims.general', 'claims.payer_id', 'disputes.appeal', 'provider.manual'] j=['payor', 'state', 'program', 'provider', 'program.mma', 'program.smi', 'program.cwsp', 'state.florida']
      overlap d: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['utilization_management.prior_authorization'] (q_score, doc_decayed, contrib): [('utilization_management.prior_authorization', 1.0, 0.1, 0.55)]
      overlap j: {'count_norm': 1.0, 'intensity_norm': 0.55} — tags: ['regulatory_authority.cms'] (q_score, doc_decayed, contrib): [('regulatory_authority.cms', 1.0, 0.1, 0.55)]
    authority_level: raw=1.0 norm=1.0 weight=0.15
    length: raw=1.0 norm=1.0 weight=0.1

**Top paragraph with answer:**
- paragraph_id: `e9ea1bbc-358a-4ea2-ab5c-a200217d7dca` | doc: document | raw_score=20.475 rerank=0.602
- text: (a) Medicare Part A Premium. Florida Medicaid will pay the Part A premium for dually eligible recipients with full Florida 
Medicaid, Qualified Medicare Beneficiaries (QMB), Supplemental Security Income (SSI), or Medically Needy with QMB. 
(b) Medicare Part B Premium. Florida Medicaid will pay...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `e9ea1bbc-358a-4ea2-ab5c-a200217d7dca` | doc: document | raw_score=18.558 rerank=0.570
- text: Bill Medicare for Medicare-allowable Part B inpatient ancillary services.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `72c1b99b-0756-438b-b223-5e3736ed7ee6` | doc: Sunshine Provider Manual | sim=0.896 rerank=0.755 dist=0.208
- text: and Prior Authorization 
Utilization Management Program Overview

**OUT OF SYLLABUS** (expect_in_manual=false)

---
