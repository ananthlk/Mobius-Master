# Overridable-class exemplars

Clean documents that hard-block `gate:phi` on **low-confidence, name/address-only,
no-structured-identifier** detections — the class a safe **override** targets, NOT
a must-suppress regression set.

**Do not** treat these as "the classifier should learn to suppress them by vocab."
Per the classifier owner: deterministic vocab is exhausted for this class — the
cap-sequence heuristic (score 0.45) cannot tell a medical/program proper-noun
bigram ("Healthy Start", "Immune Globulin") from a real surname ("Sarah Johnson")
by vocabulary, and enumerating all of medical terminology is unbounded. The safe
instrument is the `overridable` verdict tier (see `../DECISION_option_a.md`), not
suppression.

These belong in tests that assert **`overridable == true`** (name/address only,
zero structured identifiers, no contextual PHI), not tests that assert `gate==clean`.

## Samples
- `molina_healthy_start_provider_reqs.pdf` / `.txt` — Molina FL "Healthy Start
  Provider Requirements", public provider policy, zero patient data. Live verdict:
  `gate:phi`, `identifier_labels:['Name']` only, ~20 name hits all score 0.45 on
  medical/program bigrams. Textbook overridable.
