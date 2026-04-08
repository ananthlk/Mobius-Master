# Document Reader Skill — Architecture Schematic

> **Status**: Design (not code). Chat is the reference client.
> **Aligns with**: task-manager signal contract, db-agent MCP pattern, assistant envelope v1.

---

## 1. System Context — Where It Sits

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CONSUMERS                                   │
│                                                                     │
│   ┌──────────┐   ┌───────────┐   ┌──────────────┐   ┌──────────┐  │
│   │  Chat    │   │  Lexicon  │   │  Financial   │   │ Instant  │  │
│   │ Pipeline │   │  Manager  │   │ Benchmarking │   │   RAG    │  │
│   └────┬─────┘   └─────┬─────┘   └──────┬───────┘   └────┬─────┘  │
│        │               │                │                 │        │
│        └───────────────┼────────────────┼─────────────────┘        │
│                        │                │                          │
│                   ┌────▼────────────────▼────┐                     │
│                   │   doc_reader_client.py   │  ← thin HTTP client │
│                   │   (copied into each svc) │    like db_client   │
│                   └────────────┬─────────────┘                     │
└────────────────────────────────┼───────────────────────────────────┘
                                 │ HTTP POST
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│              DOCUMENT READER SKILL  (port 8018)                   │
│                                                                    │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│   │  /read       │  │  /summarize  │  │  /extract              │  │
│   │  (full doc)  │  │  (abstract)  │  │  (targeted query)      │  │
│   └──────┬───────┘  └──────┬───────┘  └──────────┬─────────────┘  │
│          └─────────────────┼─────────────────────┘                │
│                            ▼                                       │
│                   ┌─────────────────┐                              │
│                   │  ReadEnvelope   │  ← standard output contract  │
│                   │  Builder        │                              │
│                   └────────┬────────┘                              │
│                            │                                       │
│          ┌─────────────────┼─────────────────┐                    │
│          ▼                 ▼                  ▼                    │
│   ┌─────────────┐  ┌─────────────┐  ┌──────────────┐             │
│   │ db_client   │  │ emit_signal │  │ cache (7d)   │             │
│   │ → db-agent  │  │ → task-mgr  │  │ (envelope    │             │
│   │   (8008)    │  │   (8015)    │  │  by doc+view)│             │
│   └─────────────┘  └─────────────┘  └──────────────┘             │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. ReadEnvelope — The Output Contract

Every call to the Document Reader Skill returns a `ReadEnvelope`:

```python
@dataclass
class ReadEnvelope:
    # ── Identity ──────────────────────────────────────
    envelope_id:    str              # uuid
    document_id:    str              # from published_rag_metadata or upload
    view:           str              # "full" | "summary" | "section" | "tagged" | "extract"

    # ── Document metadata ─────────────────────────────
    display_name:   str              # "Sunshine Provider Manual"
    payer:          str | None
    authority_level: str | None      # "payor_policy" | "regulatory" | ...
    provenance:     Provenance       # source_type, source_url, effective_date, verification_tier

    # ── Structure ─────────────────────────────────────
    toc:            list[TocEntry]   # [{heading, depth, page_range, section_id}]
    sections:       list[Section]    # see below
    summary:        str | None       # 2-3 sentence abstract (populated for summary/full views)

    # ── Tagging ───────────────────────────────────────
    tags:           JpdTags          # {j_tags, p_tags, d_tags} — from lexicon
    tag_coverage:   float            # 0.0-1.0 — how well tagged

    # ── Cache ─────────────────────────────────────────
    cached_at:      str | None       # ISO timestamp; None = fresh
    expires_at:     str | None       # TTL (default 7d)

@dataclass
class Section:
    section_id:     str              # stable reference
    heading:        str
    depth:          int              # 1=H1, 2=H2, etc.
    page_start:     int | None
    page_end:       int | None
    markdown_body:  str              # reassembled from chunks, formatted markdown
    citations:      list[Citation]   # every claim traceable
    tags:           JpdTags | None   # section-level tags (for lexicon consumer)

@dataclass
class Citation:
    citation_id:    str              # "doc:abc:p12:¶5"
    chunk_id:       str              # from published_rag_metadata
    document_id:    str
    page:           int | None
    paragraph_index: int | None
    display:        str              # "[Sunshine Manual, p.12 §3]"

@dataclass
class TocEntry:
    heading:        str
    depth:          int
    page_range:     str              # "pp. 12-15"
    section_id:     str              # links to Section.section_id
```

---

## 3. Input Contract — Three Endpoints

### 3a. `POST /read` — Full or section-level read

```python
{
    "document_id":   str,            # required (from published_rag_metadata)
    "view":          str,            # "full" | "section" | "tagged"
    "section_filter": str | None,    # section heading or section_id (for view=section)
    "caller_id":     str,            # "chat" | "lexicon" | "financial" | "instant-rag"
    "include_tags":  bool,           # default false; true adds per-section JPD tags
    "run_id":        str | None,     # for task-manager correlation
    "org":           str | None,     # for task-manager org scoping
}
```

### 3b. `POST /summarize` — Abstract only

```python
{
    "document_id":   str,
    "caller_id":     str,
    "max_sentences":  int,           # default 3
}
```

Returns ReadEnvelope with `view="summary"`, `sections=[]`, `summary` populated.

### 3c. `POST /extract` — Query-targeted extraction

```python
{
    "document_id":   str,
    "query":         str,            # "rate tables for H0031"
    "caller_id":     str,
    "max_sections":  int,            # default 5
    "run_id":        str | None,
    "org":           str | None,
}
```

Returns ReadEnvelope with only the sections relevant to the query, plus citations.

---

## 4. Chat as Client — End-to-End Flow

This is the most complex consumer. Walk through a user asking: **"What does the Sunshine manual say about prior authorization?"**

### Step 1: Chat Pipeline — Plan Stage

```
User message: "What does the Sunshine manual say about prior authorization?"
                                    │
                                    ▼
                         ┌────────────────────┐
                         │  Plan Stage        │
                         │  classify → plan   │
                         │                    │
                         │  Subquestions:      │
                         │  SQ1: "What are    │
                         │   Sunshine's PA    │
                         │   requirements?"   │
                         └────────┬───────────┘
                                  │
                                  ▼
                         ┌────────────────────┐
                         │  Blueprint Stage   │
                         │  route: RAG agent  │
                         │  + doc_reader      │
                         │  (document cited   │
                         │   in corpus)       │
                         └────────┬───────────┘
                                  │
```

### Step 2: Resolve Stage — RAG + Doc Reader

```
                         ┌────────────────────────────────────────┐
                         │  Resolve Stage                         │
                         │                                        │
                         │  1. search_corpus("prior auth          │
                         │     Sunshine") → chunk hits            │
                         │     with document_id + page refs       │
                         │                                        │
                         │  2. doc_reader_client.extract(          │
                         │       document_id = "sunshine-manual", │
                         │       query = "prior authorization     │
                         │               requirements",           │
                         │       caller_id = "chat"               │
                         │     )                                  │
                         │     → ReadEnvelope                     │
                         │       .sections[0].markdown_body       │
                         │       .sections[0].citations           │
                         │       .summary                         │
                         │                                        │
                         │  3. Merge: RAG chunks provide          │
                         │     relevance ranking; ReadEnvelope    │
                         │     provides structure + citations     │
                         └────────────────┬───────────────────────┘
                                          │
```

### Step 3: Responder Stage — ReadEnvelope → Assistant Envelope

```
                         ┌────────────────────────────────────────┐
                         │  Responder Stage                       │
                         │                                        │
                         │  ReadEnvelope.sections[]               │
                         │       ↓ maps to                        │
                         │  AssistantEnvelope.blocks[]            │
                         │                                        │
                         │  ┌──────────────────────────────────┐  │
                         │  │ Block Mapping:                    │  │
                         │  │                                   │  │
                         │  │ ReadEnvelope        Asst Envelope │  │
                         │  │ ─────────────       ───────────── │  │
                         │  │ .summary          → direct_answer │  │
                         │  │ .sections[].md    → detail block  │  │
                         │  │ .sections[].md    → markdown_rpt  │  │
                         │  │ .citations[]      → sources block │  │
                         │  │ .toc              → (nav sidebar) │  │
                         │  │ .tags             → tool_attrib   │  │
                         │  └──────────────────────────────────┘  │
                         └────────────────┬───────────────────────┘
                                          │
                                          ▼
                         ┌────────────────────────────────────────┐
                         │  Assistant Envelope v1 (to frontend)   │
                         │                                        │
                         │  {                                     │
                         │    "version": 1,                       │
                         │    "blocks": [                         │
                         │      {                                 │
                         │        "type": "tool_attribution",     │
                         │        "icon": "doc",                  │
                         │        "label": "Sunshine Manual"      │
                         │      },                                │
                         │      {                                 │
                         │        "type": "direct_answer",        │
                         │        "markdown": "Sunshine requires  │
                         │         prior auth for H0031, H2017…"  │
                         │      },                                │
                         │      {                                 │
                         │        "type": "detail",               │
                         │        "markdown": "## Prior Auth\n…", │
                         │        "collapsed_default": true       │
                         │      },                                │
                         │      {                                 │
                         │        "type": "sources",              │
                         │        "refs": [                       │
                         │          {                             │
                         │            "index": 0,                 │
                         │            "title": "Sunshine Manual,  │
                         │                     p.47 §3",          │
                         │            "open": {                   │
                         │              "kind": "document_viewer",│
                         │              "document_id": "abc-123", │
                         │              "page": 47,               │
                         │              "highlight": "¶5"         │
                         │            }                           │
                         │          }                             │
                         │        ]                               │
                         │      }                                 │
                         │    ]                                   │
                         │  }                                     │
                         └────────────────────────────────────────┘
```

---

## 5. Financial Benchmarking — Same Skill, Different View

Today the financial report cites numbers without source links. With the doc reader:

```
┌──────────────────────────────────────────────────────────────────┐
│  Financial Strategy Pipeline (report_pipeline.py)               │
│                                                                  │
│  Phase 0 (NEW): Source Hydration                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  fee_schedule_env = doc_reader_client.extract(             │  │
│  │      document_id = "ahca-59g-4-002",                      │  │
│  │      query = "fee schedule rates H0031 H0032 H2017 ...",  │  │
│  │      caller_id = "financial"                               │  │
│  │  )                                                         │  │
│  │  → ReadEnvelope with rate table sections + citations       │  │
│  │                                                            │  │
│  │  provider_manual_env = doc_reader_client.extract(          │  │
│  │      document_id = "sunshine-provider-manual",             │  │
│  │      query = "reimbursement rates billing guidelines",     │  │
│  │      caller_id = "financial"                               │  │
│  │  )                                                         │  │
│  │  → ReadEnvelope with billing sections + citations          │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  Phase 1: Draft (existing — but now receives citations)         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  LLM prompt now includes:                                  │  │
│  │  - fee_schedule_env.sections[].markdown_body               │  │
│  │  - fee_schedule_env.citations[] (for inline refs)          │  │
│  │  - provider_manual_env.sections[].markdown_body            │  │
│  │                                                            │  │
│  │  Draft output: markdown with citation markers              │  │
│  │  e.g. "H0031 rate of $26.61 [AHCA 59G, p.3 §2]"          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  Phase 2-3: Validate + Compose (existing)                       │
│                          │                                       │
│                          ▼                                       │
│  OUTPUT: Report as AssistantEnvelope blocks                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  {                                                         │  │
│  │    "blocks": [                                             │  │
│  │      {"type": "tool_attribution", "label": "Financial…"},  │  │
│  │      {"type": "direct_answer", "markdown": "Executive…"},  │  │
│  │      {"type": "table", "headers": ["Code","Rate",…], …},  │  │
│  │      {"type": "chart", "image_base64": "…"},               │  │
│  │      {"type": "callout", "variant": "warning", …},         │  │
│  │      {"type": "detail", "markdown": "## Risk…"},           │  │
│  │      {"type": "task_list", "tasks": [priorities…]},        │  │
│  │      {"type": "sources", "refs": [                         │  │
│  │        {"title": "AHCA 59G-4.002, p.3", …},               │  │
│  │        {"title": "Sunshine Manual, p.47", …}               │  │
│  │      ]},                                                   │  │
│  │      {"type": "next_steps", "items": [30/60/90 day…]}      │  │
│  │    ]                                                       │  │
│  │  }                                                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  RESULT: Same report, but now with:                             │
│  ✓ Clickable citations to source documents                      │
│  ✓ Rendered via shared envelope renderer (not bespoke SPA)      │
│  ✓ PDF-exportable via existing report_pdf.py                    │
│  ✓ Quotable in chat ("how is my H0031 rate?" pulls blocks)      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Task-Manager Integration — Signal Contract for Doc Reader

The doc reader emits signals using the **same pattern** as credentialing and instant-rag:

```python
# ── Step Config (added to contract.py) ─────────────────────

"doc_reader": {
    "reassemble_doc": {
        "title_running": "Reading document…",
        "title_done":    "Document ready",
        "title_failed":  "Failed to read document",
        "expected_outcome": "ReadEnvelope with sections and citations",
        "roles": ["analyst", "coordinator"],
    },
    "extract_sections": {
        "title_running": "Extracting relevant sections…",
        "title_done":    "Sections extracted",
        "title_failed":  "Extraction failed",
        "expected_outcome": "Targeted sections matching query",
        "roles": ["analyst"],
    },
    "generate_summary": {
        "title_running": "Summarizing document…",
        "title_done":    "Summary ready",
        "title_failed":  "Summary failed",
        "expected_outcome": "2-3 sentence abstract",
        "roles": ["analyst"],
    },
}

# ── Blocker Config ─────────────────────────────────────────

"doc_not_published": {
    "title": "Document not in published corpus",
    "body":  "This document hasn't been chunked and published yet.",
    "actions": [
        {"id": "trigger_ingest", "label": "Ingest now",   "style": "primary"},
        {"id": "dismiss",        "label": "Dismiss",      "style": "ghost"},
    ],
},
"chunks_missing_pages": {
    "title": "Page references unavailable",
    "body":  "Chunks exist but page numbers were not preserved during ingestion.",
    "actions": [
        {"id": "proceed_without", "label": "Proceed without page refs", "style": "secondary"},
        {"id": "re_ingest",       "label": "Re-ingest with pages",     "style": "primary"},
    ],
},
```

### Signal Emission Timeline (chat /extract call)

```
T+0s    emit_signal("step_start", step_id="extract_sections",
            workflow="doc_reader", org=caller_org, run_id=envelope_id)
        → TaskCard: status=running, title="Extracting relevant sections…"

T+0.1s  db_client.db_query(
            "SELECT * FROM published_rag_metadata WHERE document_id = :id
             ORDER BY paragraph_index",
            "chat", params={"id": document_id}
        )
        → chunks retrieved via db-agent

T+0.5s  [if no chunks found]
        emit_signal("blocker", step_id="extract_sections",
            workflow="doc_reader", issue_code="doc_not_published",
            data={"document_id": document_id})
        → TaskCard: status=open, type=blocker

T+0.5s  [if chunks found — reassemble + LLM summarize sections]

T+2s    emit_signal("step_done", step_id="extract_sections",
            workflow="doc_reader", org=caller_org, run_id=envelope_id,
            data={"sections_found": 3, "citations": 7})
        → TaskCard: status=resolved

        return ReadEnvelope(...)
```

---

## 7. DB-Agent Integration — Manifest + Queries

### Manifest: `doc-reader.yml`

```yaml
service: doc-reader
permissions:
  chat:
    read:
      - published_rag_metadata    # chunks, embeddings, document metadata
      - document_tags             # JPD tags per document
      - policy_line_tags          # line-level tags
      - policy_lexicon_entries    # lexicon for tag enrichment
    write: []                     # read-only service
  rag:
    read:
      - documents                 # document metadata (display_name, payer, etc.)
      - document_pages            # raw pages (for unpublished doc fallback)
      - hierarchical_chunks       # pre-publish chunks
    write: []
limits:
  max_rows: 5000
  timeout_seconds: 30
```

### Key Queries

```sql
-- 1. Fetch all chunks for a document (ordered for reassembly)
SELECT chunk_id, chunk_text, page_number, paragraph_index,
       document_display_name, document_payer, document_authority_level,
       source_type
FROM published_rag_metadata
WHERE document_id = :doc_id
ORDER BY paragraph_index ASC;

-- 2. Fetch JPD tags for section-level tagging
SELECT chunk_id, j_tags, p_tags, d_tags
FROM policy_line_tags
WHERE document_id = :doc_id;

-- 3. Fetch document-level metadata (from rag DB)
SELECT id, display_name, payer, state, program,
       authority_level, source_type, source_metadata
FROM documents
WHERE id = :doc_id;

-- 4. Query-targeted extraction (BM25 pre-filter)
SELECT chunk_id, chunk_text, page_number, paragraph_index
FROM published_rag_metadata
WHERE document_id = :doc_id
  AND chunk_text ILIKE '%' || :keyword || '%'
ORDER BY paragraph_index ASC;
```

---

## 8. Alignment Summary — Three Pillars

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    DOCUMENT READER SKILL                        │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │  db-agent   │    │ task-manager │    │ assistant envelope  │ │
│  │  (data)     │    │ (lifecycle)  │    │ (presentation)      │ │
│  ├─────────────┤    ├─────────────┤    ├─────────────────────┤ │
│  │ db_client   │    │ emit_signal │    │ ReadEnvelope maps   │ │
│  │ manifests   │    │ step config │    │ to envelope blocks  │ │
│  │ read-only   │    │ blocker cfg │    │                     │ │
│  │ chat + rag  │    │ dedup by    │    │ .summary → direct   │ │
│  │ databases   │    │ envelope_id │    │ .sections → detail  │ │
│  │             │    │             │    │ .citations → sources│ │
│  │ SAME        │    │ SAME        │    │ .toc → navigation   │ │
│  │ PATTERN AS  │    │ PATTERN AS  │    │ .tags → attribution │ │
│  │ credntling  │    │ credntling  │    │                     │ │
│  │ & instant   │    │ & instant   │    │ SAME RENDERER as    │ │
│  │   RAG       │    │   RAG       │    │ chat + credntling   │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│                                                                 │
│  No new patterns. No new infrastructure.                       │
│  Just a new skill that composes the three existing pillars.    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Consumer Matrix — Who Uses What View

| Consumer | Endpoint | View | Key Fields Used | Emits Signals? |
|----------|----------|------|-----------------|----------------|
| **Chat (Q&A)** | `/extract` | `extract` | `.sections[].markdown_body`, `.citations[]`, `.summary` | Yes (via chat's run_id) |
| **Chat (browse doc)** | `/read` | `full` | `.toc`, `.sections[]`, all fields | Yes |
| **Lexicon audit** | `/read` | `tagged` | `.sections[].tags`, `.tag_coverage` | No (batch job) |
| **Financial benchmarking** | `/extract` | `extract` | `.sections[].markdown_body`, `.citations[]` | Yes (via pipeline run_id) |
| **Instant RAG QA** | `/read` | `full` | `.toc`, `.sections[]`, `.summary` | Yes (existing workflow) |
| **Report PDF export** | `/read` | `full` | `.sections[].markdown_body` → weasyprint | No |

---

## 10. Thread-Attached Files — Bridging the Gap

Today: user uploads a file in chat → goes to tool agent as opaque blob.
With doc reader: uploaded file gets a **transient ReadEnvelope** (not published to RAG):

```
User uploads "rates_2026.pdf" in chat thread
        │
        ▼
┌─────────────────────────────────────────────────┐
│  document_upload_skill (existing)               │
│  stores file with thread_id + purpose           │
│        │                                        │
│        ▼                                        │
│  doc_reader_client.read(                        │
│      raw_file = file_bytes,                     │
│      file_type = "pdf",                         │
│      caller_id = "chat",                        │
│      transient = True    ← not published to RAG │
│  )                                              │
│        │                                        │
│        ▼                                        │
│  ReadEnvelope (cached per thread, 24h TTL)      │
│  - .toc shows what the PDF contains             │
│  - .sections have markdown + citations          │
│  - .citations point to page/paragraph           │
│  - LLM can now cite "rates_2026.pdf, p.3 §2"   │
│    instead of summarizing from raw text         │
└─────────────────────────────────────────────────┘
```

For transient files, the skill uses **its own PDF/DOCX parser** (not the RAG pipeline) to produce chunks locally, then assembles the ReadEnvelope. This is the one place it needs parsing logic — for published docs it reads from `published_rag_metadata` via db-agent.

---

## 11. Cache Strategy

```
Cache Key:  hash(document_id + view + section_filter + query)
TTL:        7 days (published docs) | 24 hours (transient uploads)
Storage:    In-memory dict (MVP) → Redis (later)
Invalidation:
  - Re-chunking event from RAG → bust all envelopes for that document_id
  - Re-tagging event from lexicon → bust "tagged" view envelopes
  - Manual: DELETE /cache/{document_id}
```

---

## 12. What This Does NOT Replace

| Existing System | Stays As-Is | Why |
|----------------|-------------|-----|
| mobius-rag ingestion | Yes | Doc reader is read-side; RAG handles write-side (parse, chunk, embed, publish) |
| Vertex AI vector search | Yes | Doc reader augments search results with structure; doesn't replace retrieval |
| InstantRagEnvelope | Yes | InstantRag = write envelope (ingest); ReadEnvelope = read envelope (present). Complementary. |
| JPD tagger | Yes | Doc reader consumes tags from `policy_line_tags`; tagger produces them |
| AnswerCard JSON | Evolves | Responder maps ReadEnvelope → AssistantEnvelope blocks instead of free-form AnswerCard |

---

## 13. Open Design Decisions

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Section reassembly from chunks | (a) Simple `paragraph_index` ordering (b) LLM-assisted section detection | Start with (a); add (b) for `/extract` view only |
| 2 | Transient file parsing | (a) Embed parser in doc-reader skill (b) Call RAG's existing extraction endpoints | (a) — keeps doc-reader self-contained for uploads |
| 3 | Financial report rendering | (a) Envelope blocks replace SPA entirely (b) SPA uses envelope renderer as component | (b) first — SPA keeps its nav sidebar; swap renderer |
| 4 | Citation format | (a) `[DocName, p.12 §3]` (b) `[1]` footnotes (c) Configurable | (c) — `rendering_hints.citation_style` in ReadEnvelope |
| 5 | Streaming for large docs | (a) Full envelope in one response (b) SSE section-by-section | (a) with `max_sections` param; (b) later if needed |
