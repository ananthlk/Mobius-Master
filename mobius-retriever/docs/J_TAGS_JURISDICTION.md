# J Tags and Jurisdiction Alignment

The `j_tags` in the lexicon align with the multi-dimensional jurisdiction model used by mobius-chat. Use these codes to scope retrieval when documents or questions are tagged with jurisdiction.

## Jurisdiction j_tag Code Convention

| Dimension   | Code Format      | Examples                                   |
|------------|------------------|--------------------------------------------|
| State      | `state.{abbrev}` | `state.FL`, `state.TX`, `state.CA`         |
| Payor      | `payor.{name}`   | `payor.sunshine`, `payor.uhc`, `payor.molina` |
| Program    | `program.{name}` | `program.medicaid`, `program.medicare`     |
| Perspective| `provider`, `patient` | `provider`, `patient`                 |

## Lexicon Entries

Add j_tags to `policy_lexicon_entries` (kind='j') with `phrases`, `aliases`, or `description` that map to jurisdiction codes. Example structure:

```yaml
j_tags:
  state.FL:
    description: "Florida"
    phrases: ["Florida", "FL", "in Florida", "for Florida"]
  payor.sunshine:
    description: "Sunshine Health"
    aliases: ["Sunshine Health", "Sunshine", "Sunshine Health Plan"]
  program.medicaid:
    description: "Medicaid"
    phrases: ["Medicaid", "Medicaid managed care", "MCO"]
  provider:
    description: "Provider-office perspective"
    phrases: ["as a provider", "our clinic", "provider office"]
  patient:
    description: "Patient perspective"
    phrases: ["as a member", "as a patient", "member"]
```

## Document Tags

Documents should have `j_tags` in `document_tags` and `policy_line_tags` populated from policy extraction or manual tagging. The JPD tagger matches the question against the lexicon, resolves overlapping document_ids, and scopes BM25 retrieval accordingly.

## Relationship to State-Based Filters

- **RAG filter overrides** (from mobius-chat state): `filter_payer`, `filter_state`, `filter_program` are applied at retrieval time when the user has established jurisdiction in conversation. These come from `rag_filters_from_active(active)`.
- **J_tags**: Provide additional scoping when the question text matches lexicon phrases (e.g. "Sunshine Health prior auth"). Both paths can be active; document_ids from JPD and tag_filters from state work together to narrow the corpus.
