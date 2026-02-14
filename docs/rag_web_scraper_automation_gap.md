# RAG Web-Scraper: Automation and URL Retention

**Goal:** Automatically run **scrape → extract → chunk → embed** (and optionally publish) for all pages/docs from a website, with clear inputs, a report for fixing errors, and URL retention for refreshes.

---

## URL retention for refreshes

When we import scraped web pages, we **already store the URL** so you can go back and refresh (re-scrape) later:

- **Per page:** `document_pages.source_url` – the original URL for that page (null for PDF pages). Set in `import-scraped-pages` for every page.
- **Per document:** `documents.source_metadata` (JSONB) includes:
  - `source_type`: `"scraped"`
  - `scraped_seed_url`: first/seed URL
  - `scraped_page_count`: number of pages
  - `scraped_page_urls`: list of all page URLs

**What to do next:**

- **Expose in UI/APIs:** Ensure document detail and reader APIs return `source_url` per page and `source_metadata` on the document, so the UI can show “Source: https://…” and support “Refresh from URL” later.
- **Refresh workflow (future):** Use stored URLs to re-scrape the same page(s), then either update the existing document or create a new version; dedup can use `scraped_page_urls` or a dedicated “last_refreshed_at” + URL table if we want versioning.

No schema change is required for retention; only exposure and optional refresh features.

---

## Full E2E automation: inputs and report

To run **full end-to-end automation** (scrape → extract → chunk → embed) with a **report for fixing errors**, the following inputs and report shape are needed.

### Inputs

| Input | Description | Where it lives today |
|-------|-------------|----------------------|
| **Website / seed URL** | Starting URL (e.g. `https://example.com/providers.html`). | Scraper: job seed URL. |
| **Scrape approach** | Mode (e.g. tree vs list), depth, path scope, content type (HTML/text/both). | Scraper job config (RAG frontend or scraper API). |
| **Doc metadata** | Payer, state, program, authority_level, effective_date, termination_date, display_name. | RAG import payload; could be set once per automation run. |
| **Chunking method** | Path A (LLM facts) vs Path B (policy NLP), threshold, critique on/off, max_retries, extraction on/off. | RAG `POST /documents/{id}/chunking/start` body; today per-doc, could be defaulted for auto-chunk. |
| **Report generation** | Where to write report (GCS path, or return in API response), format (JSON/HTML), and what to include. | New: automation run result. |

### Report (for fixing errors)

The report should be produced at the end of an automation run so you can fix errors. Suggested contents:

- **Run id** (e.g. automation job id or scrape job id).
- **Seed URL / website name** and scrape approach used.
- **Per document:** document_id, filename/display_name, status per stage:
  - Scrape: included in job (yes/no), URL list.
  - Import: success / duplicate / error (message).
  - Chunk: pending / in_progress / completed / failed (error_message).
  - Embed: pending / in_progress / completed / failed.
- **Per-page URLs** for each document (from `source_metadata.scraped_page_urls` and `document_pages.source_url`) so you can re-scrape or refresh specific URLs.
- **Errors and warnings:** aggregation of processing_errors, chunking/embedding failures, so you can fix and re-run.

Report format could be JSON (for tooling) and/or a human-readable summary (HTML or markdown). Optionally store in GCS under a path like `reports/automation/{run_id}.json`.

### Implementation direction

1. **Orchestrator or “automation run” API** that accepts: seed URL, scrape config, doc metadata, chunking options, report path/format. It then:
   - Starts the scrape (or waits for an existing scrape job).
   - When scrape completes, calls RAG import (all pages or per-doc) with metadata.
   - RAG import creates document(s) and auto-creates ChunkingJob(s) (see “Minimal changes” below).
   - Tracks document ids and status through chunking/embedding (poll or events).
   - Writes the report (GCS or response) with the above fields and URLs.
2. **RAG:** Auto-chunk on import (and optionally accept chunking options in import body). Expose `source_url` and `source_metadata` in document/detail and pages APIs so the report and UI can show URLs for refreshes.

---

## What’s Stopping Full Automation (current gaps)

### Current pipeline (what exists today)

| Step | What happens | Automated? |
|------|----------------|------------|
| **Scrape** | User starts scrape in RAG Document Input; web-scraper runs and stores pages (and optionally PDFs) in GCS or returns page content. | Manual start only. |
| **Extract** | For **scraped pages**: text/html is already available at import time (no separate extraction). For **GCS PDFs**: extraction runs **during** `import-from-gcs` (inline). | Yes for both once import runs. |
| **Import** | User clicks “Add to RAG” / “Add selected” → `import-scraped-pages` or `import-from-gcs` creates a Document + DocumentPages. | **Manual.** |
| **Chunk** | User goes to Document Status and clicks “Chunk” (or bulk “Chunk”) → `POST /documents/{id}/chunking/start` creates a ChunkingJob; chunking worker processes it. | **Manual.** |
| **Embed** | When chunking **completes**, the chunking worker **automatically** enqueues an EmbeddingJob; embedding worker picks it up and runs. | **Yes** (once chunking is started). |
| **Publish** | User clicks Publish in Document Detail / Status. | Manual by design (review before publish). |

So today: **chunk → embed is already automatic**. The gaps are **import** and **chunk**.

---

## What’s Stopping Full Automation

### 1. Import is manual after scrape completes

- When the scrape job finishes, the UI shows the list of scraped pages/docs.
- Nothing automatically calls RAG’s `import-scraped-pages` or `import-from-gcs`.
- The user must click “Add to RAG” or “Add selected” (and may need to set metadata).

**To automate:** Either:

- **Frontend:** When scrape status becomes `completed`, optionally auto-call import for all displayed pages (or all selected), with a checkbox like “Auto-add to RAG when scrape completes,” or
- **Backend/event:** Scraper (or a small orchestrator) calls RAG’s import API when the job completes (e.g. webhook or job-complete handler). RAG would need an endpoint that accepts “import everything from job X” or the scraper would push page list + metadata.

### 2. Chunking is manual after import (and after upload)

- `import-scraped-pages` and `import-from-gcs` only create the Document and DocumentPages; they do **not** create a ChunkingJob.
- `POST /upload` (file upload) also does not create a ChunkingJob.
- So every new document (from scrape import or upload) sits in “Store/MD done” until the user goes to Document Status and clicks “Chunk.”

**To automate:** When a document is created in a “ready for chunking” state, auto-queue chunking:

- **Option A – RAG backend:** In `import-scraped-pages` and `import-from-gcs` (and optionally in `POST /upload` after successful extraction), after creating the document and pages, create a `ChunkingJob` for that document (same defaults as `POST /documents/{id}/chunking/start`). Chunking worker then runs; on completion it already enqueues embedding.
- **Option B – Config flag:** Add a query/body flag like `auto_chunk=true` so auto-chunk only runs when requested (e.g. for scrape flow only).

Result with Option A (and auto-import): **scrape → [auto-import] → import creates doc + auto ChunkingJob → chunk → auto embed**. Only Publish stays manual.

---

## Summary: Minimal Changes for “Scrape → Extract → Chunk → Embed”

| Gap | Change |
|-----|--------|
| **Auto-import when scrape completes** | Frontend: when `scrapeStatus === 'completed'`, optionally call import for all pages (or add “Auto-add to RAG when complete” and use that), **or** scraper/orchestrator calls RAG import API on job complete. |
| **Auto-chunk after import** | RAG backend: in `import-scraped-pages` and `import-from-gcs` (and optionally upload), after creating the document, create a `ChunkingJob` for that document (status `pending`, same generator/threshold defaults as start endpoint). |

No change needed for **chunk → embed**; it’s already automatic. **Publish** can remain manual so users can review before publishing to the vector index.

---

## Files Involved (for implementation)

- **RAG backend – auto-chunk after import:**  
  - [mobius-rag/app/main.py](mobius-rag/app/main.py): in `import_scraped_pages` and `import_document_from_gcs`, after `db.commit()` and returning the document, create and add a `ChunkingJob` for the new document (and optionally same in the upload success path if you want upload → chunk → embed as well).
- **RAG frontend – auto-import when scrape completes:**  
  - [mobius-rag/frontend/src/components/tabs/DocumentInputTab.tsx](mobius-rag/frontend/src/components/tabs/DocumentInputTab.tsx): when `scrapeStatus` becomes `'completed'`, optionally call `addSelectedToRag()` for all displayed pages (or all docs), or add a checkbox “Auto-add to RAG when complete” and trigger import when it’s checked and status flips to completed.
- **Chunking job creation:** Same pattern as [mobius-rag/app/main.py](mobius-rag/app/main.py) `start_chunking` (create `ChunkingJob` with `document_id`, `generator_id`, `threshold`, `status="pending"`). Worker and embedding worker require no change.

---

## Quick test: one-page site (Path B)

Automation uses **Path B** (deterministic policy spans, no LLM) for chunking and embedding on import.

**Example: [Florida Behavioral Health Association](https://floridabha.org/) (single page)**

1. Start RAG backend, chunking worker, embedding worker, and web scraper.
2. Open RAG UI → **Document Input** → **Scrape from URL**.
3. Enter: `https://floridabha.org/`
4. Leave mode as **Regular scan (single page)**.
5. Check **"Auto-add to RAG when scrape completes (import + chunk + embed)"**.
6. Click **Start scrape**.
7. When the job completes, the UI auto-imports the page; RAG creates one document and queues a **Path B** chunking job; the worker runs chunking then enqueues embedding. Check **Document Status** for the new doc and Chunk/Embedding columns moving to completed.
8. Optional: open **Details** and confirm **source_metadata** (e.g. `scraped_seed_url`, `scraped_page_urls`) and that the pages API shows **source_url** for the page (for refreshes).
