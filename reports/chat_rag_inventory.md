# Chat/RAG State Inventory

**Generated:** 2026-02-20T18:07:51.446677+00:00
**Source:** Chat Postgres (mobius_chat)

---

## 1. Documents Available to Chat

| Metric | Value |
|--------|-------|
| Rows (chunks/facts) | 1,914 |
| Distinct documents | 20 |

### By source_type

| source_type | Count |
|-------------|-------|
| hierarchical | 1,914 |

### Top documents (by chunk count)

| Document | document_id | Chunks |
|----------|-------------|--------|
| Sunshine Provider Manual | d9721756-d1b1-4cf4-845b-f44652c5fcf9 | 1,434 |
| — | ee3cb924-247f-4684-8714-6bf930a0771c | 157 |
| — | c4297605-92cd-432c-9044-bc8eec7f1722 | 108 |
| Sunshine Member Handbook | ed99a1d4-4c07-4b33-901f-fc45d503eaba | 106 |
| — | f6edfdaa-81d3-44ba-be80-20527018437b | 26 |
| — | bb843014-3d3c-450c-887a-b98491b6b234 | 23 |
| — | 1d609fda-7ace-4516-bca0-f659dd9fd39e | 17 |
| — | a12a8e12-040e-422c-8741-3c0e656752ce | 10 |
| — | 37ea30b1-65b4-4aba-90f5-62b931f58cc1 | 8 |
| — | 957f74b8-786e-4a7b-b47c-58d0b6163216 | 6 |
| — | ba233e8e-c7ea-4ae3-9447-12da0367612a | 6 |
| — | 9fdb3ebc-255f-4e37-b0dd-a1fc59278838 | 4 |
| — | 873e2bfd-566b-49b3-b588-2390f4e5294b | 2 |
| — | ccd5ad00-39c1-43ee-ab9e-0a3d07bc7f92 | 1 |
| — | 14828dc7-0232-4907-8f2a-25c03f63dcc0 | 1 |
| — | 88e28899-a18a-4f73-ad0c-d42ca0150c25 | 1 |
| — | a6f0f070-1c35-4970-9462-ada26fddc265 | 1 |
| — | 6f1113fc-803b-489f-9dfd-d670fdb0a619 | 1 |
| — | a5c4c13f-42c9-411e-bd80-c4705092b2e7 | 1 |
| — | c7198def-2819-4dc7-b5ca-ed608a0f5c10 | 1 |

---

## 2. Tags Available

| Table | Rows | Distinct documents |
|-------|------|-------------------|
| policy_lexicon_meta | 1 | — |
| policy_lexicon_entries (active) | 231 | — |
| document_tags | 23 | 23 |
| policy_line_tags | 19,013 | 24 |

### Lexicon by kind

| kind | Count |
|------|-------|
| j | 30 |
| p | 15 |
| d | 186 |

---

## 3. Vertex AI Vector Search (from sync_runs)

| Run | Started | vector_rows_upserted | postgres_rows_written | status |
|-----|---------|----------------------|------------------------|--------|
| 366f3dbc... | 2026-02-19 13:57:31 | 1914 | 1914 | success |
| bba6b067... | 2026-02-18 19:58:20 | 1914 | 1914 | success |
| 647d8d1a... | 2026-02-18 16:27:53 | — | 1914 | failure |
| 5bad5958... | 2026-02-18 16:21:07 | — | — | success |

---

## Summary

- **Published chunks/facts:** 1,914
- **Documents with published content:** 20
- **Documents with document_tags:** 23
- **Documents with policy_line_tags:** 24
- **Line-level tag rows:** 19,013

- **Last Vertex upsert:** 1,914 vectors