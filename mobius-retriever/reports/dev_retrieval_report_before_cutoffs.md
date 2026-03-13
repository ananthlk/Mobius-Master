# Dev Retrieval Report

JPD + BM25 + Vector retrieval on eval_questions_dev.yaml.

**Note on sentence vs paragraph BM25:** Sentence-level BM25 tends to outperform paragraph-level for fact-based queries (phone numbers, dates, specific entities) because (a) facts typically appear in a single sentence, (b) BM25 scores each sentence independently so the exact-matching sentence ranks higher, and (c) paragraphs dilute the signal by mixing many sentences. Paragraph-level can be better for conceptual/summary questions. Raw scores show the distance between top hits and the rest.

---

## dev_001

**Question:** What is the prior authorization requirement for physical therapy in Florida?

**Tags from question (J/P/D):**
- p_tags: (none)
- d_tags: ['health_care_services.physical_therapy', 'utilization_management.prior_authorization']
- j_tags: ['state.florida']
- document_ids resolved: 21 doc(s)

**BM25 Retrieved (paragraphs, raw_score) [deduped by text, top 20]:**
  1. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=16.522 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `8f17c077-6b24-47f7-8259-9e381c3893ad` | raw_score=16.293 Sunshine Provider Manual | • 
Medical equipment and supplies 
• 
Medication administration 
•...
  3. `2d2c5ff6-da5b-47ea-aa5c-f7f166810e07` | raw_score=15.772 Sunshine Provider Manual | Sunshine Health will complete a retrospective medical necessity review if...
  4. `43a29e63-85c8-43dd-9ee3-8e50b3c073e6` | raw_score=14.850 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  5. `21c76cea-ddf5-461f-981a-d7d1d4219011` | raw_score=13.203 Sunshine Provider Manual | • 
Tuberculin skin testing as appropriate to age and risk 
• 
Vision...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `2056c9e6-f9de-421c-b479-d8d209316bee` | raw_score=14.763 Sunshine Provider Manual | Authorization requirement and submission
  2. `21c76cea-ddf5-461f-981a-d7d1d4219011` | raw_score=14.513 Sunshine Provider Manual | The requirement is not in compliance with Florida law, including laws...
  3. `078780e4-1c4e-45ed-894e-40888fa22a60` | raw_score=14.401 Sunshine Member Handbook | Physical therapy in an office setting.
  4. `8f17c077-6b24-47f7-8259-9e381c3893ad` | raw_score=14.051 Sunshine Provider Manual | Physical therapy

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `1eb4490c-5482-43a6-ab10-112dd92921bf` | sim=0.881 dist=0.237 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...
  2. `72c1b99b-0756-438b-b223-5e3736ed7ee6` | sim=0.881 dist=0.239 Sunshine Provider Manual | and Prior Authorization 
Utilization Management Program Overview
  3. `909f4f6b-c89f-488d-935f-6aef26327ed3` | sim=0.879 dist=0.241 Sunshine Provider Manual | the member’s PCP, except in a true emergency. All non-emergency inpatient...
  4. `f8651178-e694-4050-bb78-b36c75ab2d0a` | sim=0.879 dist=0.242 Sunshine Provider Manual | Medical practitioners and providers are to submit requests for inpatient or...
  5. `8c753010-57ae-42db-b2dc-7c07284d5494` | sim=0.878 dist=0.243 Sunshine Provider Manual | Prior authorization is required for all LTC services except custodial...

**Top paragraph with answer:**
- paragraph_id: `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | doc: Sunshine Provider Manual | raw_score=16.522
- text: 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to dispense a 72-hour (three-day) supply of certain 
medications to a member awaiting a prior authorization determination. The purpose is to avoid 
interruption of current therapy or delay in the initiation of therapy. All...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `2056c9e6-f9de-421c-b479-d8d209316bee` | doc: Sunshine Provider Manual | raw_score=14.763
- text: Authorization requirement and submission
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `1eb4490c-5482-43a6-ab10-112dd92921bf` | doc: Sunshine Provider Manual | sim=0.881 dist=0.237
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
  1. `3b543bcb-8074-4934-a277-15bb4d366a12` | raw_score=26.955 Sunshine Provider Manual | Sunshine Health covers prescription drugs and certain over-the-counter (OTC)...
  2. `47ad14cd-d4dd-48ec-8410-09e3363e5648` | raw_score=16.995 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  3. `47c6c40a-eeb7-4945-a7f6-7f2761cbcd57` | raw_score=15.889 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  4. `ec2977a4-25aa-4500-9d24-a65503107f19` | raw_score=15.035 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  5. `5bd77e37-4864-4bb1-98f5-24235c54e61c` | raw_score=14.819 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  6. `f2a7a941-23bb-4530-a91b-452e72141718` | raw_score=13.384 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  7. `2c51497c-5786-4420-9384-b5749e56d46c` | raw_score=12.182 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  8. `0bc13f48-0d92-4ac1-b8a1-aaf994321044` | raw_score=11.524 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `3b543bcb-8074-4934-a277-15bb4d366a12` | raw_score=38.940 Sunshine Provider Manual | Pharmacies may call the Express Scripts help desk at 1-833-750-4392.
  2. `3b543bcb-8074-4934-a277-15bb4d366a12` | raw_score=16.775 Sunshine Provider Manual | Pharmacy claims are processed by Express Scripts.
  3. `ec2977a4-25aa-4500-9d24-a65503107f19` | raw_score=15.443 Sunshine Member Handbook | Call 711 and give them our Member Services phone number.
  4. `cebfece2-5d2e-4e9c-8e6f-7d7653706322` | raw_score=14.765 Sunshine Member Handbook | What Do I Have To Pay For?
  5. `47ad14cd-d4dd-48ec-8410-09e3363e5648` | raw_score=14.308 Sunshine Member Handbook | Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770 77 What You...
  6. `360df18e-7a09-416a-bf47-d606912a33a3` | raw_score=14.288 Sunshine Member Handbook | 25 What Do I Have To Pay For?...

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `d5f2d290-339a-4195-b975-4ee4289a49e4` | sim=0.889 dist=0.222 Sunshine Provider Manual | Pharmacy Benefit
  2. `1c912807-a31c-4a35-9003-8b40989f137a` | sim=0.884 dist=0.232 Sunshine Provider Manual | Non-Specialty/Retail Medications 
To efficiently process prior authorization...
  3. `696f17fe-94ad-41ba-bcf0-ae182a1dd04c` | sim=0.874 dist=0.252 Sunshine Provider Manual | Phone Number 
Provider Services 
1-844-477-8313 
Medical or behavioral...
  4. `bdca20a8-a22b-49e4-a858-1b844ab41dbb` | sim=0.874 dist=0.252 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...

**Top paragraph with answer:**
- paragraph_id: `3b543bcb-8074-4934-a277-15bb4d366a12` | doc: Sunshine Provider Manual | raw_score=26.955
- text: Sunshine Health covers prescription drugs and certain over-the-counter (OTC) drugs ordered by 
Sunshine Health providers. Some medications require prior authorization or have limitations on 
dosage, maximum quantities or the member’s age. Sunshine Health follows AHCA’s preferred drug 
list...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `3b543bcb-8074-4934-a277-15bb4d366a12` | doc: Sunshine Provider Manual | raw_score=38.940
- text: Pharmacies may call the Express Scripts help desk at 1-833-750-4392.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `d5f2d290-339a-4195-b975-4ee4289a49e4` | doc: Sunshine Provider Manual | sim=0.889 dist=0.222
- text: Pharmacy Benefit

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
  1. `15dc978a-f75f-40c7-bd09-b07bfe326582` | raw_score=14.319 Sunshine Provider Manual | Sunshine Health follows the Section 1557 nondiscrimination provision of the...
  2. `7c1b6a09-9b06-4c1e-a5af-c22957caf38a` | raw_score=13.778 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  3. `261b93b2-a657-4df8-8a5e-511d61f4495a` | raw_score=13.761 Sunshine Provider Manual | Funded by both the state and federal governments, Medicaid provides health...
  4. `34d6d014-e4d0-4d68-83e8-3bd7e207d1c5` | raw_score=13.569 Sunshine Provider Manual | The Early and Periodic Screening, Diagnosis and Treatment (EPSDT) program...
  5. `47c00089-aade-49cb-935b-fa57562a6ac2` | raw_score=13.249 Sunshine Provider Manual | The Florida Legislature did not provide any funding for this program except...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | raw_score=16.045 Sunshine Provider Manual | 9 Medicaid in Florida...
  2. `261b93b2-a657-4df8-8a5e-511d61f4495a` | raw_score=13.831 Sunshine Provider Manual | Most Florida Medicaid recipients are enrolled in the SMMC program.
  3. `6d592940-9cc5-44c7-ae32-3fad6cf862f0` | raw_score=11.566 Sunshine Member Handbook | 18 Section 7: Your Medicaid Eligibility...
  4. `261b93b2-a657-4df8-8a5e-511d61f4495a` | raw_score=11.369 Sunshine Provider Manual | In 2011, the Florida Legislature established the Florida Medicaid program as...
  5. `6d592940-9cc5-44c7-ae32-3fad6cf862f0` | raw_score=11.005 Sunshine Member Handbook | 19 Section 8: Enrollment in Our Plan...
  6. `4dd8e8eb-6560-4eab-b2c3-46c020af1bf8` | raw_score=10.966 Sunshine Provider Manual | Health education, including anticipatory guidance

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `c2ef0450-cd4d-40fe-81dc-686acaaebc2d` | sim=0.913 dist=0.174 Sunshine Provider Manual | Provider Demographic Updates...
  2. `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | sim=0.907 dist=0.186 Sunshine Provider Manual | Chapter 1: Welcome to Sunshine Health...
  3. `9c3dd0f7-9a15-415f-84dc-abb91f5c2802` | sim=0.903 dist=0.194 Sunshine Provider Manual | Eligibility Determination 
Medicaid eligibility in Florida is determined by...
  4. `e4f5fc27-8ad8-4338-9c9f-30e35af59821` | sim=0.898 dist=0.205 Sunshine Provider Manual | Specialty Plan in all regions of the state. 
Medicaid recipients who qualify...
  5. `9103d54e-55dc-4414-880a-0b856b2b8890` | sim=0.896 dist=0.208 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  6. `51ff319d-9b9b-4527-95e8-4b55d818f937` | sim=0.896 dist=0.208 Sunshine Provider Manual | Medicaid fair hearings may be requested any time up to 120 days following...

**Top paragraph with answer:**
- paragraph_id: `15dc978a-f75f-40c7-bd09-b07bfe326582` | doc: Sunshine Provider Manual | raw_score=14.319
- text: Sunshine Health follows the Section 1557 nondiscrimination provision of the federal Affordable 
Care Act (ACA). Section 1557 prohibits discrimination on the grounds of race, color, national 
origin, sex, age, or disability in certain health programs and activities. The Section 1557 final 
rule...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | doc: Sunshine Provider Manual | raw_score=16.045
- text: 9 Medicaid in Florida ............................................................................................................................................
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `c2ef0450-cd4d-40fe-81dc-686acaaebc2d` | doc: Sunshine Provider Manual | sim=0.913 dist=0.174
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
  1. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=34.788 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `49e59ab8-e5f8-4aaf-be6a-7c36dcd3452f` | raw_score=22.719 Sunshine Provider Manual | The following drug categories are not part of the Sunshine Health PDL and...
  3. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=21.131 Sunshine Provider Manual | Over-the-Counter (OTC)...
  4. `7f6838ec-10b4-4a86-9e58-f767507af3e7` | raw_score=19.735 Sunshine Provider Manual | • 
Drugs used to treat infertility 
• 
Experimental/investigational...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=36.652 Sunshine Provider Manual | 111 72-Hour Emergency Supply Policy...
  2. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=27.671 Sunshine Provider Manual | 111 Exclusions to the 72-Hour Emergency Supply...
  3. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=26.253 Sunshine Provider Manual | 72-Hour Emergency Supply Policy State law requires that a pharmacy offer to...
  4. `7f6838ec-10b4-4a86-9e58-f767507af3e7` | raw_score=23.858 Sunshine Provider Manual | Prostheses, appliances and devices (except products for diabetics and...

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `bdca20a8-a22b-49e4-a858-1b844ab41dbb` | sim=0.920 dist=0.160 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `8436c85b-64d8-4960-80a9-2fef4150196d` | sim=0.918 dist=0.165 Sunshine Provider Manual | Drugs may be dispensed up to a 34-day supply on most medications and up to a...
  3. `88ffa0c2-28d1-4048-a91e-aa569dba1f99` | sim=0.909 dist=0.182 Sunshine Provider Manual | • 
Drugs used to treat infertility 
• 
Experimental/investigational...
  4. `beae8b4c-5e70-4f1d-aef5-26176f530ff8` | sim=0.895 dist=0.211 Sunshine Provider Manual | The following drug categories are not part of the Sunshine Health PDL and...

**Top paragraph with answer:**
- paragraph_id: `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | doc: Sunshine Provider Manual | raw_score=34.788
- text: 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to dispense a 72-hour (three-day) supply of certain 
medications to a member awaiting a prior authorization determination. The purpose is to avoid 
interruption of current therapy or delay in the initiation of therapy. All...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | doc: Sunshine Provider Manual | raw_score=36.652
- text: 111 72-Hour Emergency Supply Policy ...................................................................................................................
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `bdca20a8-a22b-49e4-a858-1b844ab41dbb` | doc: Sunshine Provider Manual | sim=0.920 dist=0.160
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
  1. `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | raw_score=18.335 Sunshine Provider Manual | 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to...
  2. `1eb4490c-5482-43a6-ab10-112dd92921bf` | raw_score=17.302 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...
  3. `220be833-d68d-481c-8d3a-91ac6cbf2dce` | raw_score=17.213 Sunshine Provider Manual | Sunshine Health provides a 24-hour help line to respond to requests for...
  4. `0c692dfc-0aff-4993-9018-5ea3aed71d91` | raw_score=14.391 Sunshine Provider Manual | Clinical validation is intended to identify coding scenarios that...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `bef681ed-0bbd-42de-ac0c-632f80ca11e9` | raw_score=15.603 Sunshine Provider Manual | Providers should use the Pre-Auth Check Tool to look up a service code to...
  2. `420953df-857c-4c08-8f08-0ad073132cca` | raw_score=15.432 Sunshine Provider Manual | Be told prior to getting a service how much it may cost them
  3. `1eb4490c-5482-43a6-ab10-112dd92921bf` | raw_score=15.256 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...
  4. `1d2d80cc-4d58-41da-9ebf-c727d8607fde` | raw_score=15.015 Sunshine Member Handbook | To be told prior to getting a service how much it may cost you
  5. `49be0e82-6b23-4fc9-a276-8d29c1fe1926` | raw_score=13.952 Sunshine Provider Manual | During an episode of emergency care, Sunshine Health does not require prior...

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `72c1b99b-0756-438b-b223-5e3736ed7ee6` | sim=0.933 dist=0.134 Sunshine Provider Manual | and Prior Authorization 
Utilization Management Program Overview
  2. `8c753010-57ae-42db-b2dc-7c07284d5494` | sim=0.927 dist=0.145 Sunshine Provider Manual | Prior authorization is required for all LTC services except custodial...
  3. `47ae9843-2ce3-45d1-bb56-bd4452ccf579` | sim=0.925 dist=0.149 Sunshine Provider Manual | • 
Non-emergent/non-urgent pre-scheduled services requiring prior...
  4. `e26ee630-cf35-40bf-b6cf-582688dc419d` | sim=0.923 dist=0.154 Sunshine Provider Manual | verify eligibility on the same day services are rendered.
  5. `1eb4490c-5482-43a6-ab10-112dd92921bf` | sim=0.919 dist=0.162 Sunshine Provider Manual | Providers should refer to the Pre-Auth Check Tool to look up a service code...

**Top paragraph with answer:**
- paragraph_id: `4f4a79c5-2f96-405b-9d1e-441b669a06fe` | doc: Sunshine Provider Manual | raw_score=18.335
- text: 72-Hour Emergency Supply Policy 
State law requires that a pharmacy offer to dispense a 72-hour (three-day) supply of certain 
medications to a member awaiting a prior authorization determination. The purpose is to avoid 
interruption of current therapy or delay in the initiation of therapy. All...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `bef681ed-0bbd-42de-ac0c-632f80ca11e9` | doc: Sunshine Provider Manual | raw_score=15.603
- text: Providers should use the Pre-Auth Check Tool to look up a service code to determine if prior authorization is needed.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `72c1b99b-0756-438b-b223-5e3736ed7ee6` | doc: Sunshine Provider Manual | sim=0.933 dist=0.134
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
  1. `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | raw_score=25.566 Sunshine Provider Manual | The utilization management department is staffed Monday through Friday from...
  2. `591744db-245e-4c41-82ff-14e9f82eddaf` | raw_score=17.052 Sunshine Provider Manual | In-office waiting times for visits shall not exceed 30 minutes. 
PCPs are...
  3. `48111001-ac56-422a-ae00-44a86bf5c743` | raw_score=16.783 Sunshine Provider Manual | PCP Access and Availability 
Each PCP is responsible for maintaining...
  4. `0bc13f48-0d92-4ac1-b8a1-aaf994321044` | raw_score=15.621 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...
  5. `7a520d6e-8357-49e9-82d0-cb2dedf14c87` | raw_score=14.512 Sunshine Member Handbook | Questions? Call Member Services at 1-866-796-0530 or TTY at 1-800-955-8770...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | raw_score=26.101 Sunshine Provider Manual | Weekend and After-Hours on Call-Number (for all products): 1-844-477-8313.
  2. `591744db-245e-4c41-82ff-14e9f82eddaf` | raw_score=16.458 Sunshine Provider Manual | PCPs are encouraged to offer after-hours appointments after 5 p.m. on office...
  3. `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | raw_score=15.484 Sunshine Provider Manual | 9 Key Contacts and Important Phone Numbers...
  4. `6d592940-9cc5-44c7-ae32-3fad6cf862f0` | raw_score=12.331 Sunshine Member Handbook | 17 Contacting Member Services after Hours...
  5. `ec2977a4-25aa-4500-9d24-a65503107f19` | raw_score=11.155 Sunshine Member Handbook | Call 711 and give them our Member Services phone number.
  6. `aaeac914-5247-4bd7-b8ea-c25626318ea8` | raw_score=11.042 Sunshine Member Handbook | You can call the numbers at the beginning of this handbook for a ride.

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `1fd0dbe8-660a-4422-af45-88f61b6d0fd5` | sim=0.906 dist=0.187 Sunshine Provider Manual | The utilization management department is staffed Monday through Friday from...
  2. `a638f008-9f54-49b8-845c-5a0595c617e9` | sim=0.895 dist=0.211 Sunshine Provider Manual | PCP Access and Availability 
Each PCP is responsible for maintaining...
  3. `591744db-245e-4c41-82ff-14e9f82eddaf` | sim=0.890 dist=0.220 Sunshine Provider Manual | In-office waiting times for visits shall not exceed 30 minutes. 
PCPs are...
  4. `5238e05f-9774-4c3f-a2b3-014fa6086d66` | sim=0.879 dist=0.243 Sunshine Provider Manual | Reconsiderations or Claim 
Dispute**

**Top paragraph with answer:**
- paragraph_id: `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | doc: Sunshine Provider Manual | raw_score=25.566
- text: The utilization management department is staffed Monday through Friday from 8 a.m. to 8 p.m. 
Eastern. Providers should call Provider Services at 1-844-477-8313 and select the prompt for 
authorization. Weekend and After-Hours on Call-Number (for all products): 1-844-477-8313.
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `0d9f9c4a-48c2-475a-a1d2-cfcc0e08fb59` | doc: Sunshine Provider Manual | raw_score=26.101
- text: Weekend and After-Hours on Call-Number (for all products): 1-844-477-8313.
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `1fd0dbe8-660a-4422-af45-88f61b6d0fd5` | doc: Sunshine Provider Manual | sim=0.906 dist=0.187
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
  1. `0ca7b77c-1c5f-48c3-8867-aa96ffd0f4e3` | raw_score=15.296 Sunshine Provider Manual | Providers who have internet access and choose not to submit claims via EDI...
  2. `05665c2d-3616-48d1-9518-21dbc1a0677e` | raw_score=13.823 Sunshine Provider Manual | Preferred Method 
Providers are asked to verify member eligibility by using...
  3. `bef681ed-0bbd-42de-ac0c-632f80ca11e9` | raw_score=13.484 Sunshine Provider Manual | Medical practitioners and providers are to submit requests for inpatient or...
  4. `5a1469db-d577-4515-9664-9f7566342cfa` | raw_score=13.177 Sunshine Provider Manual | Practitioners must submit a notice of pregnancy (NOP) form to Sunshine...
  5. `ac22a9b0-3002-4093-ba23-0e440df8ddcf` | raw_score=12.620 Sunshine Provider Manual | Providers can submit health risk assessments for their patients (Sunshine...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | raw_score=16.772 Sunshine Provider Manual | 15 Secure Provider Portal...
  2. `3693e38f-664a-4d36-b56c-0c6058f3cbb3` | raw_score=13.311 Sunshine Provider Manual | Secure Provider Portal to verify member eligibility, manage claims and...
  3. `5a1469db-d577-4515-9664-9f7566342cfa` | raw_score=13.015 Sunshine Provider Manual | The form may be accessed and submitted electronically via the Secure...
  4. `2cd187f8-2e45-49b6-b33b-32cac07fb3ca` | raw_score=12.872 Sunshine Provider Manual | Submit a corrected claim via the Secure Provider Portal and follow...
  5. `b823f838-7251-4c81-8996-ba49b84cbea8` | raw_score=12.570 Sunshine Provider Manual | Register to access Sunshine Health’s Secure Provider Portal at...

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `0edf2010-cc25-4e16-b9f8-29946f89eae4` | sim=0.903 dist=0.195 Sunshine Provider Manual | guidelines on general outreach and enrollment, claims processing and systems...
  2. `0716b163-1779-4d27-a883-d3c1464de9d2` | sim=0.900 dist=0.199 Sunshine Provider Manual | Recredentialing 
Credentialing and Recredentialing Overview
  3. `6a31adf1-34ba-4f06-a901-de2b4705368e` | sim=0.894 dist=0.211 Sunshine Provider Manual | Providers who have internet access and choose not to submit claims via EDI...
  4. `72c1b99b-0756-438b-b223-5e3736ed7ee6` | sim=0.892 dist=0.216 Sunshine Provider Manual | and Prior Authorization 
Utilization Management Program Overview

**Top paragraph with answer:**
- paragraph_id: `0ca7b77c-1c5f-48c3-8867-aa96ffd0f4e3` | doc: Sunshine Provider Manual | raw_score=15.296
- text: Providers who have internet access and choose not to submit claims via EDI or on paper may 
submit claims directly to Sunshine Health by using the Secure Provider Portal. Providers must 
request access to the secure site by registering for a username and password. 
Providers then may file...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `1ce2b150-00bd-4a56-9dbb-1dae917d982d` | doc: Sunshine Provider Manual | raw_score=16.772
- text: 15 Secure Provider Portal ...........................................................................................................................
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `0edf2010-cc25-4e16-b9f8-29946f89eae4` | doc: Sunshine Provider Manual | sim=0.903 dist=0.195
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
  1. `4335c5e8-619a-42ef-a658-1af27078d636` | raw_score=25.554 Sunshine Provider Manual | Providers must include the original claim number on the complaint and...
  2. `2368270f-2be4-4d00-946a-0cd07dd07784` | raw_score=25.112 Sunshine Provider Manual | ➢ See Process for Claims Reconsiderations and Disputes
  3. `571bda6e-8536-4b59-99b0-d95336a61641` | raw_score=19.584 Sunshine Provider Manual | All requests for corrected claims or reconsiderations/claim disputes must be...
  4. `66b378b8-a1d5-47e7-b017-e5d6e4593dc3` | raw_score=18.843 Sunshine Provider Manual | Reconsideration/Claim Disputes...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `66b378b8-a1d5-47e7-b017-e5d6e4593dc3` | raw_score=25.983 Sunshine Provider Manual | 125 Process for Claims Reconsiderations and Disputes...
  2. `2368270f-2be4-4d00-946a-0cd07dd07784` | raw_score=25.983 Sunshine Provider Manual | ➢ See Process for Claims Reconsiderations and Disputes
  3. `4335c5e8-619a-42ef-a658-1af27078d636` | raw_score=17.501 Sunshine Provider Manual | Providers must include the original claim number on the complaint and...
  4. `4563bc72-feb9-4c2a-abfe-e40ad2ffb40b` | raw_score=12.684 Sunshine Provider Manual | Submit attachments for claims and resubmitted claims for payment...
  5. `571bda6e-8536-4b59-99b0-d95336a61641` | raw_score=12.624 Sunshine Provider Manual | All requests for corrected claims or reconsiderations/claim disputes must be...

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `c56a3461-2085-4859-a105-141d0663aad1` | sim=0.974 dist=0.052 Sunshine Provider Manual | ➢ See Process for Claims Reconsiderations and Disputes
  2. `5238e05f-9774-4c3f-a2b3-014fa6086d66` | sim=0.967 dist=0.066 Sunshine Provider Manual | Reconsiderations or Claim 
Dispute**
  3. `71df57ef-27e6-443e-bdc7-735e5d7eecd8` | sim=0.941 dist=0.118 Sunshine Provider Manual | Reconsideration/Claim Disputes 
Definitions 
The definition of a corrected...
  4. `51f9d9fb-67b0-42b2-8c9e-6aec2956e361` | sim=0.937 dist=0.127 Sunshine Provider Manual | Providers must include the original claim number on the complaint and...

**Top paragraph with answer:**
- paragraph_id: `4335c5e8-619a-42ef-a658-1af27078d636` | doc: Sunshine Provider Manual | raw_score=25.554
- text: Providers must include the original claim number on the complaint and include any relevant 
supporting documentation. 
➢ See Process for Claims Reconsiderations and Disputes
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `66b378b8-a1d5-47e7-b017-e5d6e4593dc3` | doc: Sunshine Provider Manual | raw_score=25.983
- text: 125 Process for Claims Reconsiderations and Disputes .............................................................................
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `c56a3461-2085-4859-a105-141d0663aad1` | doc: Sunshine Provider Manual | sim=0.974 dist=0.052
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
  1. `105fb1a2-ebdb-44ab-814e-21887d9183c7` | raw_score=17.381 Sunshine Provider Manual | resort. If an authorization is required, the providers still must obtain...
  2. `49e59ab8-e5f8-4aaf-be6a-7c36dcd3452f` | raw_score=17.283 Sunshine Provider Manual | The following drug categories are not part of the Sunshine Health PDL and...
  3. `40e99cf1-6358-4de3-a2f5-27a076b18d3f` | raw_score=14.528 Sunshine Provider Manual | Newly approved drug products are not normally placed on the preferred drug...
  4. `7fe6f591-3469-4126-8bed-5ae9102986ba` | raw_score=14.153 Sunshine Provider Manual | • 
Sunshine Health may not deny medically necessary treatment to a child...

**BM25 Retrieved (sentences, raw_score) [deduped by text, top 20]:**
  1. `49e59ab8-e5f8-4aaf-be6a-7c36dcd3452f` | raw_score=22.019 Sunshine Provider Manual | Drugs covered under Medicare Part B and/or Medicare Part D
  2. `40e99cf1-6358-4de3-a2f5-27a076b18d3f` | raw_score=16.642 Sunshine Provider Manual | During this period, access to these medications is considered through the...
  3. `6b9bd6ea-bda6-44fe-99f1-4c6631c837c7` | raw_score=15.257 Sunshine Provider Manual | 110 Prior Authorization Process for Medications...
  4. `105fb1a2-ebdb-44ab-814e-21887d9183c7` | raw_score=13.448 Sunshine Provider Manual | If Medicare covers the needed service, the provider must first process the...

**Vector Retrieved (similarity, distance) [deduped by text, top 10]:**
  1. `72c1b99b-0756-438b-b223-5e3736ed7ee6` | sim=0.896 dist=0.208 Sunshine Provider Manual | and Prior Authorization 
Utilization Management Program Overview
  2. `47ae9843-2ce3-45d1-bb56-bd4452ccf579` | sim=0.889 dist=0.222 Sunshine Provider Manual | • 
Non-emergent/non-urgent pre-scheduled services requiring prior...
  3. `8c753010-57ae-42db-b2dc-7c07284d5494` | sim=0.887 dist=0.227 Sunshine Provider Manual | Prior authorization is required for all LTC services except custodial...
  4. `b04b30b3-559c-434d-a169-cf04e2f3bd0a` | sim=0.886 dist=0.227 Sunshine Provider Manual | In general, prior authorization for MMA, CWSP, SMI and HIV/AIDS members is...
  5. `1c912807-a31c-4a35-9003-8b40989f137a` | sim=0.880 dist=0.239 Sunshine Provider Manual | Non-Specialty/Retail Medications 
To efficiently process prior authorization...

**Top paragraph with answer:**
- paragraph_id: `105fb1a2-ebdb-44ab-814e-21887d9183c7` | doc: Sunshine Provider Manual | raw_score=17.381
- text: resort. If an authorization is required, the providers still must obtain Sunshine Health 
authorization for the Medicaid portion of the bill. 
Providers may check eligibility and identify if a member has other insurance through the Sunshine 
Health secure provider portal. This is particularly...
- likely_has_answer: True

**Top sentence with answer:**
- paragraph_id: `49e59ab8-e5f8-4aaf-be6a-7c36dcd3452f` | doc: Sunshine Provider Manual | raw_score=22.019
- text: Drugs covered under Medicare Part B and/or Medicare Part D
- likely_has_answer: True

**Top vector result:**
- paragraph_id: `72c1b99b-0756-438b-b223-5e3736ed7ee6` | doc: Sunshine Provider Manual | sim=0.896 dist=0.208
- text: and Prior Authorization 
Utilization Management Program Overview

**OUT OF SYLLABUS** (expect_in_manual=false)

---
