# Dev Chat Pipeline Report (9 Questions)

Flow: parse → retrieval (blend) → doc assembly (confidence, Google fallback).

RAG configured: True
Google search URL: set

---


## Summary: Factual vs Canonical + What Was Sent

| ID | Question | Canonical | Factual | n_h | n_f | Pre | Post | Google | Top Label |
|----|----------|-----------|---------|-----|-----|-----|------|--------|-----------|
| dev_001 | What is the prior authorization requiremen... | 0.10 | 0.90 | 0 | 9 | 9 | 9 | — | process_confident |
| dev_002 | What phone number do pharmacies call for E... | 0.10 | 0.90 | 0 | 9 | 9 | 9 | — | process_confident |
| dev_003 | Summarize the key guidance in the provider... | 0.90 | 0.10 | 4 | 1 | 4 | 4 | — | process_confident |
| dev_004 | What is the 72-hour emergency medication s... | 0.10 | 0.90 | 0 | 9 | 9 | 9 | — | process_confident |
| dev_005 | How can a provider determine whether a ser... | 0.70 | 0.30 | 4 | 3 | 4 | 4 | — | process_confident |
| dev_006 | What are the weekend and after-hours on-ca... | 0.10 | 0.90 | 0 | 9 | 9 | 9 | — | process_confident |
| dev_007 | Summarize the Secure Provider Portal regis... | 0.80 | 0.20 | 4 | 2 | 4 | 4 | — | process_confident |
| dev_008 | What is the process for claims reconsidera... | 0.90 | 0.10 | 4 | 1 | 4 | 4 | — | process_confident |
| dev_009 | What is the Medicare Part B prior authoriz... | 0.70 | 0.30 | 4 | 3 | 4 | 4 | — | process_confident |

*Canonical: 0=factual, 1=canonical. Factual: 0=canonical, 1=factual. Pre/Post = chunks before/after doc assembly.*

---

## dev_001

**Question:** What is the prior authorization requirement for physical therapy in Florida?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.10 |
| **factual_score**   | 0.90 |
| intent_score (from parser) | 0.9 |
| question_intent | factual |

### Retrieval Blend
n_hierarchical=0  n_factual=9  confidence_min=0.77


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 9 |
| Chunks after assembly (to LLM) | 9 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.894 | Florida Medicaid covers services that meet all ... |
| 2 | process_confident | 0.891 | 2 
2.0 Authorization Requirements 
2.1 
When to... |
| 3 | process_confident | 0.884 | Providers must report Florida licensure as requ... |
| 4 | process_confident | 0.881 | Providers should refer to the Pre-Auth Check To... |
| 5 | process_confident | 0.881 | Providers should refer to the Pre-Auth Check To... |

---

## dev_002

**Question:** What phone number do pharmacies call for Express Scripts help desk?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.10 |
| **factual_score**   | 0.90 |
| intent_score (from parser) | 0.9 |
| question_intent | factual |

### Retrieval Blend
n_hierarchical=0  n_factual=9  confidence_min=0.77


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 9 |
| Chunks after assembly (to LLM) | 9 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.893 | Pharmacy Benefit |
| 2 | process_confident | 0.893 | Pharmacy Benefit |
| 3 | process_confident | 0.893 | Pharmacy Benefit |
| 4 | process_confident | 0.890 | Non-Specialty/Retail Medications 
To efficientl... |
| 5 | process_confident | 0.890 | Non-Specialty/Retail Medications 
To efficientl... |

---

## dev_003

**Question:** Summarize the key guidance in the provider manual section "Medicaid in Florida".

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.90 |
| **factual_score**   | 0.10 |
| intent_score (from parser) | 0.1 |
| question_intent | canonical |

### Retrieval Blend
n_hierarchical=4  n_factual=1  confidence_min=0.53


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 4 |
| Chunks after assembly (to LLM) | 4 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.922 | Introduction ..................................... |
| 2 | process_confident | 0.919 | Providers must report or provide any certificat... |
| 3 | process_confident | 0.918 | Florida Medicaid covers services that meet all ... |
| 4 | process_confident | 0.910 | Medicaid |

---

## dev_004

**Question:** What is the 72-hour emergency medication supply policy?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.10 |
| **factual_score**   | 0.90 |
| intent_score (from parser) | 0.9 |
| question_intent | factual |

### Retrieval Blend
n_hierarchical=0  n_factual=9  confidence_min=0.77


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 9 |
| Chunks after assembly (to LLM) | 9 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.920 | 72-Hour Emergency Supply Policy 
State law requ... |
| 2 | process_confident | 0.920 | 72-Hour Emergency Supply Policy 
State law requ... |
| 3 | process_confident | 0.920 | 72-Hour Emergency Supply Policy 
State law requ... |
| 4 | process_confident | 0.917 | Drugs may be dispensed up to a 34-day supply on... |
| 5 | process_confident | 0.917 | Drugs may be dispensed up to a 34-day supply on... |

---

## dev_005

**Question:** How can a provider determine whether a service requires prior authorization?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.70 |
| **factual_score**   | 0.30 |
| intent_score (from parser) | 0.3 |
| question_intent | canonical |

### Retrieval Blend
n_hierarchical=4  n_factual=3  confidence_min=0.59


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 4 |
| Chunks after assembly (to LLM) | 4 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.933 | and Prior Authorization 
Utilization Management... |
| 2 | process_confident | 0.933 | and Prior Authorization 
Utilization Management... |
| 3 | process_confident | 0.927 | Prior authorization is required for all LTC ser... |
| 4 | process_confident | 0.927 | Prior authorization is required for all LTC ser... |

---

## dev_006

**Question:** What are the weekend and after-hours on-call phone numbers?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.10 |
| **factual_score**   | 0.90 |
| intent_score (from parser) | 0.9 |
| question_intent | factual |

### Retrieval Blend
n_hierarchical=0  n_factual=9  confidence_min=0.77


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 9 |
| Chunks after assembly (to LLM) | 9 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.899 | The utilization management department is staffe... |
| 2 | process_confident | 0.899 | The utilization management department is staffe... |
| 3 | process_confident | 0.897 | Phone |
| 4 | process_confident | 0.889 | PCP Access and Availability 
Each PCP is respon... |
| 5 | process_confident | 0.889 | PCP Access and Availability 
Each PCP is respon... |

---

## dev_007

**Question:** Summarize the Secure Provider Portal registration process.

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.80 |
| **factual_score**   | 0.20 |
| intent_score (from parser) | 0.2 |
| question_intent | canonical |

### Retrieval Blend
n_hierarchical=4  n_factual=2  confidence_min=0.56


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 4 |
| Chunks after assembly (to LLM) | 4 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.899 | Recredentialing 
Credentialing and Recredential... |
| 2 | process_confident | 0.899 | Recredentialing 
Credentialing and Recredential... |
| 3 | process_confident | 0.898 | Provider Enrollment Renewal ...................... |
| 4 | process_confident | 0.898 | Providers who have internet access and choose n... |

---

## dev_008

**Question:** What is the process for claims reconsiderations and disputes?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.90 |
| **factual_score**   | 0.10 |
| intent_score (from parser) | 0.1 |
| question_intent | canonical |

### Retrieval Blend
n_hierarchical=4  n_factual=1  confidence_min=0.53


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 4 |
| Chunks after assembly (to LLM) | 4 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.959 | ➢ See Process for Claims Reconsiderations and D... |
| 2 | process_confident | 0.959 | ➢ See Process for Claims Reconsiderations and D... |
| 3 | process_confident | 0.956 | Reconsiderations or Claim 
Dispute** |
| 4 | process_confident | 0.956 | Reconsiderations or Claim 
Dispute** |

---

## dev_009

**Question:** What is the Medicare Part B prior authorization process in California?

**expect_in_manual:** False

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.70 |
| **factual_score**   | 0.30 |
| intent_score (from parser) | 0.3 |
| question_intent | canonical |

### Retrieval Blend
n_hierarchical=4  n_factual=3  confidence_min=0.59


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 4 |
| Chunks after assembly (to LLM) | 4 |
| Google fallback used | no |

**Assembly messages:**
- Corpus confidence sufficient; using retrieved docs only.

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_confident | 0.896 | and Prior Authorization 
Utilization Management... |
| 2 | process_confident | 0.896 | and Prior Authorization 
Utilization Management... |
| 3 | process_confident | 0.889 | • 
Non-emergent/non-urgent pre-scheduled servic... |
| 4 | process_confident | 0.889 | • 
Non-emergent/non-urgent pre-scheduled servic... |

---
