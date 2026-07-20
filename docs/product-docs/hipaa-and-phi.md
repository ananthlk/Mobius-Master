# Data privacy, PHI & HIPAA
> How Mobius protects patient information: what it does with PHI, why it sometimes blocks a document or message, and what "HIPAA mode" means for you.

## Is Mobius HIPAA compliant? Can I use it with patient information (PHI)?
Mobius is built to protect Protected Health Information (PHI), and today it runs in a mode that does **not** store PHI at all. The platform is not currently cleared to hold patient identifiers, so instead of storing PHI it is designed to keep PHI **out**: if you upload a document or type a message that contains patient identifiers, Mobius detects it and stops before anything is stored. Storing PHI would require a signed Business Associate Agreement (BAA) and explicit authorization; until that is in place, the safe default holds — PHI is not stored. Use Mobius for the operational and policy work behind care — payer rules, prior-auth, credentialing, benchmarking, provider lookups — rather than for entering patient identifiers.

This page describes how Mobius behaves today — it is not a claim of HIPAA certification (there is no such certification) or a legal compliance attestation, and it isn't legal advice. Using Mobius with PHI would require a signed BAA plus your organization's own compliance review.

## What happens if I upload a document that contains patient information?
Before anything is stored or indexed, Mobius scans the extracted text for PHI — the 18 HIPAA identifiers (names, date of birth, SSN, medical-record and member/beneficiary numbers, dates of service, addresses, phone/email, and more) plus contextual identifiers (a description specific enough to single out one person). In the current mode, if PHI is found, ingestion is **terminated**: the document is not stored, not embedded, and not retrievable, and the extracted text is purged. You will see a message along the lines of "HIPAA found — cannot process in current mode." This is intentional, and it protects you and your patients.

## Can I type patient details into the chat?
Mobius checks your message for PHI before it is processed. If it finds patient identifiers, it blocks that turn and asks you to remove them (or, if it is a false alarm, to attest that the text is not patient data). The conversation cannot move forward with unresolved PHI. The best practice is to keep patient identifiers out entirely and describe the situation in general terms — Mobius answers policy, billing, and operational questions, which rarely need a specific patient's identity.

## How does Mobius detect PHI, and is my text sent to outside AI?
Mobius uses a dedicated PHI classifier that combines pattern-matching for structured identifiers (like SSN, phone, and email), name detection, and an AI context check for subtler cases. That AI check runs on models within Mobius's own cloud infrastructure (Google Cloud Vertex — the same platform Mobius itself runs on), and your text is **not sent to any external or consumer AI service** (for example, public chatbots). It stays within Mobius's controlled cloud boundary. Any evidence the classifier surfaces is always **masked** (for example `J••• D••` or `***-**-****`) — never a raw identifier — and Mobius never logs the raw text of your queries, messages, or documents, only non-identifying categories and counts.

## Mobius flagged my document as PHI, but it isn't patient data — what do I do?
Mobius deliberately errs toward caution: a missed identifier is a breach, a false alarm is a minor annoyance. So it sometimes flags business or provider contact information — a clinician's name, a practice phone number printed in a public manual — as PHI. If you are authorized and certain the text is not patient PHI, you can **attest to override**. That override is one click when everything flagged is low-risk (such as a name, address, or phone number). Higher-risk identifiers (SSN, medical-record number, date of birth, dates of service) cannot be waved through with one click and follow a compliance path instead.

## Will Mobius ever store PHI? (HIPAA-allowed mode)
Yes — Mobius can operate in a **HIPAA-allowed** mode once the platform holds a signed BAA and has been formally authorized to store PHI. In that mode, PHI can be retained, but only **privately** — it is never shared to organization-wide or public spaces, following the minimum-necessary principle. Turning that mode on is a deliberate compliance decision (BAA plus sign-off, fully audit-logged); it is never flipped automatically, by a setting, or by anyone mid-conversation. Until it is turned on, the safe default stands: PHI stays out.

## Doc-readiness notes
- **Primary audience tag:** user (privacy/compliance questions — "is my data safe", "can I upload patient info", "why did it block my document", "is this HIPAA compliant").
- **Source:** user-facing synthesis of `docs/hipaa-phi-policy.md` (owned by the PHI Classifier agent). Reality-gated to the platform's current **HIPAA-NOT-allowed** default (PHI is not stored). If the global HIPAA mode ever flips to allowed, the "what happens" answers change from terminate/block to private-only storage — update this doc from the policy at that time.
- **Ownership:** the PHI agent owns the compliance facts; product-awareness owns this user-facing phrasing. Ratified by the PHI agent before publish.
