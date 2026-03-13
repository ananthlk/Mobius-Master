# Dev Chat Pipeline Report (9 Questions)

Flow: parse → retrieval (BM25, retrieve → rerank → assemble) → doc assembly (confidence, Google fallback).

RAG configured: True
Retrieval backend: BM25 (retrieve→rerank→assemble)
Google search URL: set

---


## Summary: Factual vs Canonical + What Was Sent

| ID | Question | Canonical | Factual | n_h | n_f | Pre | Post | Google | Top Label |
|----|----------|-----------|---------|-----|-----|-----|------|--------|-----------|
| dev_001 | What is the prior authorization requiremen... | 0.10 | 0.90 | 0 | 9 | 9 | 14 | ✓ | process_with_caution |
| dev_002 | What phone number do pharmacies call for E... | 0.05 | 0.95 | 0 | 10 | 10 | 15 | ✓ | process_with_caution |
| dev_003 | Summarize the key guidance in the provider... | 0.70 | 0.30 | 4 | 3 | 2 | 7 | ✓ | process_with_caution |
| dev_004 | What is the 72-hour emergency medication s... | 0.20 | 0.80 | 1 | 8 | 7 | 12 | ✓ | process_with_caution |
| dev_005 | How can a provider determine whether a ser... | 0.70 | 0.30 | 4 | 3 | 3 | 8 | ✓ | process_with_caution |
| dev_006 | What are the weekend and after-hours on-ca... | 0.10 | 0.90 | 0 | 9 | 9 | 14 | ✓ | process_with_caution |
| dev_007 | Summarize the Secure Provider Portal regis... | 0.80 | 0.20 | 4 | 2 | 2 | 7 | ✓ | process_with_caution |
| dev_008 | What is the process for claims reconsidera... | 0.90 | 0.10 | 4 | 1 | 1 | 6 | ✓ | process_with_caution |
| dev_009 | What is the Medicare Part B prior authoriz... | 0.80 | 0.20 | 4 | 2 | 2 | 7 | ✓ | process_with_caution |

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
| Chunks after assembly (to LLM) | 14 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.750 | Providers should refer to the Pre-Auth Check To... |
| 2 | process_with_caution | 0.750 | Providers should refer to the Pre-Auth Check To... |
| 3 | process_with_caution | 0.750 | and Prior Authorization 
Utilization Management... |
| 4 | process_with_caution | 0.750 | and Prior Authorization 
Utilization Management... |
| 5 | process_with_caution | 0.749 | the member’s PCP, except in a true emergency. A... |

---

## dev_002

**Question:** What phone number do pharmacies call for Express Scripts help desk?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.05 |
| **factual_score**   | 0.95 |
| intent_score (from parser) | 0.95 |
| question_intent | factual |

### Retrieval Blend
n_hierarchical=0  n_factual=10  confidence_min=0.78


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 10 |
| Chunks after assembly (to LLM) | 15 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.823 | Non-Specialty/Retail Medications 
To efficientl... |
| 2 | process_with_caution | 0.823 | Non-Specialty/Retail Medications 
To efficientl... |
| 3 | process_with_caution | 0.823 | Non-Specialty/Retail Medications 
To efficientl... |
| 4 | process_with_caution | 0.820 | 72-Hour Emergency Supply Policy 
State law requ... |
| 5 | process_with_caution | 0.820 | 72-Hour Emergency Supply Policy 
State law requ... |

---

## dev_003

**Question:** Summarize the key guidance in the provider manual section "Medicaid in Florida".

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
| Chunks before assembly | 2 |
| Chunks after assembly (to LLM) | 7 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.761 | Provider Demographic Updates ..................... |
| 2 | process_with_caution | 0.761 | Provider Demographic Updates ..................... |
| 3 | abstain | 0.000 | Medicaid Lawyer \| Serving Florida \| Elder Needs... |
| 4 | abstain | 0.000 | Advancing Access to Contraception Through Secti... |
| 5 | abstain | 0.000 | Provider Manual
Provider Manual PROVIDER MANUAL... |

---

## dev_004

**Question:** What is the 72-hour emergency medication supply policy?

**expect_in_manual:** True

### Factual vs Canonical
| Score | Value |
|-------|-------|
| **canonical_score** | 0.20 |
| **factual_score**   | 0.80 |
| intent_score (from parser) | 0.8 |
| question_intent | factual |

### Retrieval Blend
n_hierarchical=1  n_factual=8  confidence_min=0.74


### What Was Sent
| Metric | Value |
|--------|-------|
| Chunks before assembly | 7 |
| Chunks after assembly (to LLM) | 12 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.656 | Drugs may be dispensed up to a 34-day supply on... |
| 2 | process_with_caution | 0.656 | Drugs may be dispensed up to a 34-day supply on... |
| 3 | process_with_caution | 0.656 | Drugs may be dispensed up to a 34-day supply on... |
| 4 | process_with_caution | 0.641 | Prostheses, appliances and devices (except prod... |
| 5 | process_with_caution | 0.641 | Prostheses, appliances and devices (except prod... |

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
| Chunks before assembly | 3 |
| Chunks after assembly (to LLM) | 8 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.769 | and Prior Authorization 
Utilization Management... |
| 2 | process_with_caution | 0.769 | and Prior Authorization 
Utilization Management... |
| 3 | process_with_caution | 0.767 | Prior authorization is required for all LTC ser... |
| 4 | abstain | 0.000 | Prior Authorization – HUMAN RESOURCES FOR ME
As... |
| 5 | abstain | 0.000 | Healthcare & Medical Prior Authorization Servic... |

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
| Chunks after assembly (to LLM) | 14 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.827 | The utilization management department is staffe... |
| 2 | process_with_caution | 0.827 | The utilization management department is staffe... |
| 3 | process_with_caution | 0.823 | PCP Access and Availability 
Each PCP is respon... |
| 4 | process_with_caution | 0.823 | PCP Access and Availability 
Each PCP is respon... |
| 5 | process_with_caution | 0.823 | PCP Access and Availability 
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
| Chunks before assembly | 2 |
| Chunks after assembly (to LLM) | 7 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.757 | Recredentialing 
Credentialing and Recredential... |
| 2 | process_with_caution | 0.757 | Recredentialing 
Credentialing and Recredential... |
| 3 | abstain | 0.000 | Provider portal registration \| UHCprovider.com
... |
| 4 | abstain | 0.000 | Multi-Payer Portal Registration - Availity
Elec... |
| 5 | abstain | 0.000 | Secure Provider Portal - TRICARE West - TriWest... |

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
| Chunks before assembly | 1 |
| Chunks after assembly (to LLM) | 6 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.810 | ➢ See Process for Claims Reconsiderations and D... |
| 2 | abstain | 0.000 | SSA - POMS: DI 27001.001 - Introduction to the ... |
| 3 | abstain | 0.000 | Reconsiderations and appeals \| Provider \| Human... |
| 4 | abstain | 0.000 | Provider Claims Reconsideration - TriWest
To di... |
| 5 | abstain | 0.000 | Pre- and post-service appeals and reconsiderati... |

---

## dev_009

**Question:** What is the Medicare Part B prior authorization process in California?

**expect_in_manual:** False

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
| Chunks before assembly | 2 |
| Chunks after assembly (to LLM) | 7 |
| Google fallback used | yes |

**Assembly messages:**
- Adding external search to complement corpus...

**Top chunks sent (with confidence_label):**
| # | confidence_label | rerank_score | Snippet |
|---|------------------|--------------|---------|
| 1 | process_with_caution | 0.755 | and Prior Authorization 
Utilization Management... |
| 2 | process_with_caution | 0.755 | and Prior Authorization 
Utilization Management... |
| 3 | abstain | 0.000 | Medicare Program; Update to the Required Prior ... |
| 4 | abstain | 0.000 | Medicare Program; Update to the Required Prior ... |
| 5 | abstain | 0.000 | Medicare Program; Updates to the Master List of... |

---
