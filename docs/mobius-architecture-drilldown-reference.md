# Mobius Architecture Drilldown Reference
## Complete resource mapping: each component links to UIs, specs, schemas, and code

---

## **PRE-LAYER 0: SOURCING & INGESTION PIPELINE**
### Foundation: How knowledge gets into the system

Raw documents → Indexed Intelligence. This pipeline FEEDS INTO Layer 6 (Intelligence).

### Sourcing Agent
- **What it is** — Web scraping, document classification, corpus building
- **Status** — ✅ Live
- **Owner** — Sourcing Agent (me, Retriever Agent)
- **Links to:**
  - **Code** → `mobius-rag/src/sourcing/`
  - **Spec** → `docs/sourcing-agent-spec.md`
  - **Output** → `mobius_rag.raw_documents` (PG) + `mobius_rag.extraction_jobs`
- **Schema:**
  ```
  raw_documents (PG)
  ├── id (UUID)
  ├── source_url (TEXT)
  ├── payor_id (FK)
  ├── doc_type (fee_schedule|policy|manual|addendum)
  ├── title (TEXT)
  ├── content (TEXT)
  ├── hash (md5)
  ├── status (raw|extracted|classified|chunked|published)
  ├── scraped_at
  
  extraction_jobs (PG)
  ├── id (UUID)
  ├── document_id (FK)
  ├── status (queued|processing|completed|failed)
  ├── extracted_tables (INT)
  ├── extracted_sections (INT)
  ├── completed_at
  ```
- **Known Issues** → Web scrape verification brittle; robots.txt compliance gap
- **Roadmap** → Distributed scraper, JavaScript-heavy site support

---

### Extraction Service
- **What it is** — Table capture and section parsing from PDFs
- **Status** — ✅ Live (embedded in Curation Agent)
- **Owner** — Curation Agent
- **Links to:**
  - **Code** → `mobius-rag/src/curation/extraction.py`
  - **Spec** → `docs/table-extraction-spec.md`
- **Capabilities:**
  - Table identification + structure extraction
  - Section boundary detection (policy sections, definitions, precedent)
  - OCR fallback for image-based content
- **Schema:** Outputs to `extraction_jobs` (see Sourcing Agent)
- **Known Issues** → Complex table layouts sometimes misdetected; images without OCR lost
- **Roadmap** → Improved layout detection, OCR speed optimization

---

### Curation & Lexicon Module
- **What it is** — Chunking, tagging with controlled vocabulary, metadata enrichment
- **Status** — ✅ Live
- **Owner** — Curation Agent (me, Retriever Agent)
- **Links to:**
  - **Code** → `mobius-rag/src/curation/`
  - **Spec** → `docs/curation-agent-spec.md`
  - **Lexicon** → `docs/lexicon/` (service-line taxonomy, tag vocabulary)
- **Lexicon Module Details:**
  ```
  Service-Line Taxonomy:
  ├── BH (Behavioral Health)
  ├── Integrated Care
  └── RCM (Revenue Cycle Management)
  
  Tag Vocabulary:
  ├── d (document type: policy, fee_schedule, manual)
  ├── p (coverage: covered, non_covered, requires_auth)
  ├── j (service_line: BH, integrated, rcm)
  ├── c (temporal: effective_date, expiry, precedence)
  └── [custom per payor]
  
  Tag-Selectivity Loop:
  ├── Per tag, target pool size (e.g., 1000 chunks)
  ├── Monitor tagging quality (precision/recall per tag)
  ├── Rebalance if tag pool too large/small
  └── Metric: coverage_per_tag (prevent tag explosion)
  ```
- **Schema:**
  ```
  chunks (PG)
  ├── id (UUID)
  ├── document_id (FK)
  ├── sequence_num (INT)
  ├── content (TEXT)
  ├── metadata (JSONB): {payor_id, service_line, doc_type}
  ├── created_at
  
  chunk_tags (PG)
  ├── chunk_id (FK)
  ├── tag_name (TEXT)
  ├── confidence (FLOAT)
  ├── assigned_by (LLM|human)
  ├── created_at
  
  tag_selectivity (PG)
  ├── tag_name
  ├── total_chunks (INT)
  ├── pool_size (INT) [target]
  ├── tagging_quality (FLOAT)
  └── recall (FLOAT)
  ```
- **Known Issues** → Tagging quality varies by tag; chunk size inconsistent; tag-selectivity loop not fully tuned
- **Roadmap** → Per-payor chunk strategies, improved tagging quality, tag balance automation

---

### Publishing & Indexing
- **What it is** — Embedding chunks, indexing vectors, publishing to RAG corpus
- **Status** — ✅ Live
- **Owner** — Curation Agent (embedding + indexing) + Payor Platform Agent (Fact Store publishing)
- **Links to:**
  - **Code** → `mobius-rag/src/curation/publish.py`
  - **Embedding Model** → text-embedding-004 (768-dim, OpenAI)
- **Schema:**
  ```
  chunk_embeddings (pgvector)
  ├── chunk_id (FK)
  ├── embedding (vector(768))
  ├── model_name (text-embedding-004)
  ├── created_at
  
  rag_corpus_published (BQ)
  ├── chunk_id
  ├── document_id
  ├── payor_id
  ├── service_line
  ├── content
  ├── embedding (768-dim)
  ├── published_at
  └── [denormalized for fast retrieval]
  ```
- **Known Issues** → Overlap between 22q chunks (deduplication needed); re-ranking not yet live
- **Roadmap** → Deduplication via content-digest, re-ranking model, batch publishing optimization

---

## **LAYER 1: SURFACES**

### Chat Interface
- **What it is** — Conversational interface for operators
- **Status** — ✅ Live
- **Owner** — Chat Frontend/UX Agent
- **Links to:**
  - **UI** → `https://mobius-chat-ortabkknqa-uc.a.run.app/` (production)
  - **Code** → `mobius-chat/frontend/` (React)
  - **Spec** → `docs/product-docs/mobius-chat.md`
  - **Schema** → See Database section below
- **Schema:**
  ```
  threads (PG)
  ├── id (UUID)
  ├── org_id (UUID)
  ├── user_id (UUID)
  ├── created_at
  ├── updated_at
  ├── metadata (JSONB)
  
  messages (PG)
  ├── id (UUID)
  ├── thread_id (FK threads)
  ├── role (user|assistant)
  ├── content (TEXT)
  ├── sources (JSONB) [citations]
  ├── metadata (JSONB)
  ```
- **Known Issues** → BUG_LOG.md: "lv.submission.trim is not a function"
- **Roadmap** → Chat v2 FE refactor, think-mode UI improvements

---

### API Endpoints
- **What it is** — RESTful + WebSocket access to Mobius
- **Status** — ✅ Live
- **Owner** — Chat Backend Team
- **Links to:**
  - **Code** → `mobius-chat/app/api/`
  - **Spec** → `docs/mobius-api.md` (or auto-generated from FastAPI docs at `/docs`)
  - **Production** → `https://mobius-chat-ortabkknqa-uc.a.run.app/docs`
- **Endpoints:**
  - `POST /chat/message` — Send query, get response
  - `GET /chat/thread/{id}` — Fetch thread history
  - `POST /chat/skills/{skill}/invoke` — Call a skill
  - `GET /api/platform/definition` — Fetch architecture (local API)
- **Known Issues** → Rate limiting not documented
- **Roadmap** → GraphQL layer, event-driven webhooks

---

### Chrome Extension
- **What it is** — Inline help while operators work in EHR
- **Status** — 📋 Planned
- **Owner** — Chat Frontend/UX Agent
- **Links to:**
  - **Code** → `mobius-chat-extension/` (not yet created)
  - **Spec** → `docs/chrome-extension-spec.md` (draft)
- **Schema:** (TBD)
- **Known Issues** → Not built yet
- **Roadmap** → Q4 2026 target

---

### Interact (Web-Interaction Engine & Demos)
- **What it is** — Reusable instruction schema for guided demos (show-me walkthroughs) + RPA on external sites (future)
- **Status** — 🔨 BUILDING (P1 complete, P2-P4 awaiting implementation)
- **Owner** — Interact Agent (design complete, implementation in progress)
- **Links to:**
  - **Spec** → `docs/interact-agent-spec.md` (complete design, P1-P4 phases)
  - **Code** → `mobius-interact/` (12 commits, 24 files: schema.py, validator.py, tests)
- **What It Does:**
  - **Guided demos (P1-P3)** — Product-awareness feeds show-me-how scripts → Interact runs them step-by-step (find → highlight → click → type → wait → read)
  - **Modes:** `guide` (user performs actions), `narrate` (engine performs with captions), `auto` (full speed, returns data)
  - **RPA on external sites (P4, gated)** — Same schema, executed on payor portals (e.g., check prior-auth on Sunshine)
- **Schema (interact.v1):**
  ```yaml
  script:
    schema: interact.v1
    id: chat:upload-a-document          # namespace:slug
    title: Upload a document to chat
    mode: guide                         # guide | narrate | auto
    surface: mobius-chat                # target app
    permissions: []                     # empty for guide; required for auto+external
    preconditions:
      - selector: "[data-tour-id=composer-input]"
    steps:
      - find: "[data-tour-id=composer-attach]"    # anchor via data-tour-id first
        action: highlight
        caption: "This paperclip attaches a document"
      - find: "[data-tour-id=composer-attach]"
        action: click
        wait_for: "[data-tour-id=composer-attachment-chip]"
  
  interact_runs (PG):
  ├── id (UUID)
  ├── script_id
  ├── mode (guide|narrate|auto)
  ├── surface
  ├── status (completed|failed|aborted)
  ├── per_step_outcomes (JSONB)
  ├── duration_ms
  ├── run_at
  
  scripts (PG):
  ├── id (namespace:slug)
  ├── title
  ├── schema_version (interact.v1)
  ├── mode
  ├── surface
  ├── steps (JSONB)
  ├── permissions (ARRAY)
  ├── published_by
  ├── published_at
  ├── updated_at
  ```
- **API:**
  ```
  GET /scripts/{id}              → fetch validated script
  POST /scripts                  → publish script (product-awareness, later payor-registry)
  POST /validate                 → validate schema
  Runtimes:
    - In-page runner (interact-runner.js, <10KB, no deps)
    - External driver (Playwright, later, P4 gated)
  ```
- **Why It's Frozen:**
  - Design phase only (P1-P3 stable, P4 awaiting PHI gate contract)
  - Awaiting Interact Agent kickoff (not yet started)
  - Depends on Chat v2 refactor for full integration
- **Phases to Ship:**
  - **P1:** Validator + schema tests → done
  - **P2:** In-page runner + first demo (upload-a-document) → chat integration
  - **P3:** Five demand-ranked demos + narrate mode → anchor audit
  - **P4 (gated):** auto mode + external driver → Sunshine prior-auth (requires PHI gate)
- **Known Issues:**
  - No code yet (design-only)
  - External RPA hard-disabled until enablement
  - P4 requires PHI gate contract before build
- **Roadmap:**
  - P2 implementation: in-page runner + first demo
  - P3: Five demand-ranked demos + narrate mode
  - P4 (gated): auto mode + external driver (Sunshine prior-auth pilot)

---

### instant-rag (Deprecated)
- **What it is** — Upload → Vault → promotion (instant RAG ingest for user documents)
- **Status** — ⏸️ DEPRECATED (2026-07-09, decommissioning in progress)
- **Owner** — (Archived)
- **Why deprecated:**
  - Zero ingest/POST traffic for 30 days (as of 2026-07-09)
  - Replaced by Vault carve-out with better architecture
  - Still referenced in code but no longer active
- **Links to:**
  - **Deprecation notice** → `DEPRECATED.md` (in instant-rag/)
  - **Decommissioning plan** → 6 stages outlined; 2 complete
- **Status:**
  - Phase 1-2: ✅ Complete (customer notification, endpoint sunset)
  - Phase 3-6: 🔨 In progress (data migration, service cleanup)
- **Known Issues** → Still appears in environment configs and skill references (causing confusion)
- **Roadmap** → Full decommissioning by Q4 2026; use Vault instead

---

## **LAYER 2: ROUTER & OPTIMIZER**

### Prompt Composer
- **What it is** — Modular prompt assembly from reusable blocks
- **Status** — ✅ Live
- **Owner** — ReAct Agent
- **Links to:**
  - **Code** → `mobius-rag/src/router/prompt_composer.py`
  - **Spec** → `docs/prompts/prompt-composition-studio.md`
  - **Block Library** → `mobius-rag/prompts/blocks/` (system, context, examples, constraints)
- **Schema:**
  ```
  prompt_blocks (PG)
  ├── id (UUID)
  ├── name (TEXT)
  ├── category (system|context|examples|constraints)
  ├── content (TEXT)
  ├── version (INT)
  ├── created_by (user_id)
  ├── updated_at
  
  composed_prompts (BQ)
  ├── run_id
  ├── blocks_used (ARRAY<block_id>)
  ├── final_prompt (TEXT)
  ├── model_response (TEXT)
  ├── grading (STRUCT<accuracy, clarity, latency>)
  ```
- **Known Issues** → Block composition not versioned per run
- **Roadmap** → UI for prompt builders to edit blocks

---

### Mode Selector (Reasoning Modes)
- **What it is** — Chooses reasoning approach: direct, few-shot, chain-of-thought, debate
- **Status** — ✅ Live
- **Owner** — Router Agent
- **Links to:**
  - **Code** → `mobius-rag/src/router/mode_selector.py`
  - **Spec** → `docs/reasoning-modes.md`
- **Modes:**
  - **Direct** — Single-shot answer (fee lookups)
  - **Few-shot** — Show 2-3 examples then answer (policy interpretation)
  - **Chain-of-thought** — Break into steps (multi-step logic)
  - **Debate** — Conservative vs aggressive readings then synthesis (conflicting rules)
- **Schema:**
  ```
  reasoning_modes (PG)
  ├── mode_name (direct|few_shot|cot|debate)
  ├── prompt_template (TEXT)
  ├── max_tokens (INT)
  ├── temperature (FLOAT)
  ├── success_rate (FLOAT) [from Eval feedback]
  
  mode_performance (BQ)
  ├── run_id
  ├── mode_used
  ├── latency_ms
  ├── accuracy_score
  ├── chosen_by (Router decision log)
  ```
- **Known Issues** → Debate mode not used enough; underinvested
- **Roadmap** → Mode-specific fine-tuning, auto-mode selection

---

### Strategy Selector
- **What it is** — Picks retrieval strategy: Facts → RAG → Web → Reasoning
- **Status** — ✅ Live
- **Owner** — Router Agent
- **Links to:**
  - **Code** → `mobius-rag/src/router/allocator.py`
  - **Spec** → `docs/router-reasoning-strategy.md`
  - **Coverage Map** → `docs/fact-store-coverage-map.json`
- **Strategies:**
  - **A (Facts)** — Instant, deterministic, pre-cited
  - **B (RAG)** — Rich, searchable, with citations
  - **C (Web)** — Fallback for obscure/new questions
  - **D (Reasoning)** — Multi-step ReAct chains
- **Schema:**
  ```
  strategy_coverage (PG)
  ├── payor_id
  ├── predicate (TEXT) [e.g. "fee_schedule", "timely_filing"]
  ├── strategy_a_available (BOOL)
  ├── strategy_b_available (BOOL)
  ├── strategy_c_available (BOOL)
  ├── strategy_d_available (BOOL)
  
  strategy_performance (BQ)
  ├── run_id
  ├── strategy_used (a|b|c|d)
  ├── accuracy_score
  ├── latency_ms
  ├── cost_tokens
  ├── bandit_reward
  ```
- **Known Issues** → Strategy D underutilized; web fallback (C) has high false-positive rate
- **Roadmap** → Bandit optimization tuning, cascading strategies

---

### Bandit Optimizer
- **What it is** — Multi-armed bandit: learns which strategy wins
- **Status** — ✅ Live
- **Owner** — Router Agent
- **Links to:**
  - **Code** → `mobius-rag/src/router/bandit.py`
  - **Spec** → `docs/bandit-reward-attribution.md`
  - **Live Dashboard** → `https://mobius-chat-ortabkknqa-uc.a.run.app/platform` (Status tab)
- **Reward Function:**
  - `reward = accuracy * (1 - latency_penalty) * (1 - cost_penalty)`
  - Accuracy from Eval grading
  - Latency penalty: >5s = 0.5x multiplier
  - Cost penalty: expensive strategies discounted
- **Schema:**
  ```
  bandit_state (PG)
  ├── arm (a|b|c|d)
  ├── n_pulls (INT)
  ├── total_reward (FLOAT)
  ├── avg_reward (FLOAT)
  ├── ucb_bound (FLOAT) [upper confidence bound]
  ├── updated_at
  
  arm_performance (BQ)
  ├── date
  ├── arm
  ├── pulls (INT)
  ├── avg_accuracy
  ├── avg_latency_ms
  ├── avg_cost_tokens
  ├── avg_reward
  ```
- **Known Issues** → Reward attribution lag (3-hour delay from Eval)
- **Roadmap** → Real-time feedback loop, per-domain bandit tuning

---

## **LAYER 3: PLATFORM AGENTS**

### Product Awareness Agent
- **What it is** — Keeps documentation fresh, up-to-date, discoverable
- **Status** — ✅ Live
- **Owner** — Product Awareness Agent (locked, governance role)
- **Links to:**
  - **Spec** → `docs/product-docs/product-awareness-agent-spec.md`
  - **Docs Repo** → `docs/product-docs/`
  - **Demo Tours** → `docs/demo-tours/` (interactive walkthroughs)
  - **Onboarding** → Platform → Learn tab
- **Responsibilities:**
  - Documentation governance (specs, essays, architecture)
  - Demo tour creation and maintenance
  - Onboarding materials for new team members
  - FAQ and learning resources
- **Schema:**
  ```
  documentation_assets (PG)
  ├── id (UUID)
  ├── title (TEXT)
  ├── path (TEXT)
  ├── type (spec|essay|demo|faq)
  ├── owner_agent
  ├── last_updated
  ├── freshness_score (FLOAT)
  
  doc_freshness_signals (BQ)
  ├── doc_id
  ├── area_tag (e.g. "router", "appeals")
  ├── signal_type (spec_change|code_change|gate_update)
  ├── flagged_at
  ├── status (open|in_progress|done)
  ```
- **Known Issues** → Docs lag code changes by 1-2 weeks
- **Roadmap** → Auto-generate API docs, spec versioning

---

### Eval Command Center
- **What it is** — QA cockpit: grades answers, identifies gaps, trains Router
- **Status** — ✅ Live
- **Owner** — Eval Agent (self-owned)
- **Links to:**
  - **UI** → `https://mobius-chat-ortabkknqa-uc.a.run.app/platform` (Eval/QA tab)
  - **Code** → `mobius-rag/src/eval/` + `mobius-chat/app/eval/`
  - **Spec** → `docs/eval-command-center.md`
  - **Question Bank** → `docs/eval-question-bank.json` (1000+ questions)
- **Grading Dimensions:**
  - Accuracy (correctness of answer)
  - Coverage (did we have the knowledge?)
  - Latency (speed)
  - Clarity (understandability)
  - Citation (provenance correctness)
- **Schema:**
  ```
  evaluation_results (BQ)
  ├── run_id (UUID)
  ├── query (TEXT)
  ├── answer (TEXT)
  ├── strategy_used (a|b|c|d)
  ├── accuracy_score (0-1)
  ├── coverage_score (0-1)
  ├── latency_ms (INT)
  ├── clarity_score (0-1)
  ├── citation_score (0-1)
  ├── graded_at
  ├── grader_model
  
  run_calibration (BQ)
  ├── run_id
  ├── date
  ├── avg_accuracy
  ├── avg_latency_ms
  ├── avg_cost_tokens
  ├── gates_passed (ARRAY<gate_name>)
  ├── coverage_gaps (ARRAY<gap_topic>)
  
  coverage_gaps (PG)
  ├── id
  ├── topic (TEXT)
  ├── count (INT) [how many times this gap appeared]
  ├── priority (INT)
  ├── assigned_to (deep_research_queue)
  ├── status (open|in_progress|resolved)
  ```
- **Known Issues** → Grader model lag (3-hour batch), real-time grading needed
- **Roadmap** → Real-time online grading, per-domain eval

---

### Observer Agent
- **What it is** — Per-slot verdicts: tracks what each query slot (Facts/RAG/Web/Reasoning) returned, confidence, and accuracy
- **Status** — ✅ Live (running since 2026-07-26, NOT blocked as previously stated)
- **Owner** — Observer Agent
- **Links to:**
  - **Code** → `mobius-rag/src/eval/observer.py`
  - **Spec** → `docs/observer-agent-spec.md`
- **What it tracks:**
  - Per-slot verdict (did this slot return correct answer?)
  - Confidence scores from each strategy
  - Ranking of strategies by accuracy
  - Slot interactions (when one slot triggers another)
- **Schema:**
  ```
  slot_verdicts (BQ)
  ├── run_id (UUID)
  ├── slot (a|b|c|d) [Facts|RAG|Web|Reasoning]
  ├── returned_answer (TEXT)
  ├── verdict (correct|partial|wrong|abstained)
  ├── confidence (FLOAT)
  ├── latency_ms (INT)
  ├── executed_at
  
  slot_performance (BQ)
  ├── date
  ├── slot
  ├── accuracy (FLOAT)
  ├── avg_latency_ms
  ├── abstention_rate (FLOAT)
  └── cost_tokens (INT)
  ```
- **Known Issues** — None currently known; running reliably in production
- **Roadmap** → Calibration model refinement, per-payor slot tuning

---

## **LAYER 4: DOMAIN AGENTS**

### Credentialing Agent
- **What it is** — Provider enrollment, license tracking, taxonomy management
- **Status** — ✅ Live
- **Owner** — Credentialing Agent
- **Links to:**
  - **UI** → `https://mobius-chat-ortabkknqa-uc.a.run.app/` (Credentialing workspace)
  - **Spec** → `docs/credentialing-agent-spec.md`
  - **API** → `/chat/skills/credentialing/` endpoints
- **Schema:**
  ```
  providers (PG)
  ├── npi (VARCHAR(10))
  ├── org_id (FK)
  ├── first_name
  ├── last_name
  ├── specialty_code (NPPES taxonomy)
  ├── license_state
  ├── license_number
  ├── license_expiry
  ├── credentialing_status (active|pending|expired|revoked)
  ├── last_verified_at
  
  enrollments (PG)
  ├── provider_npi (FK)
  ├── payor_id
  ├── product_id
  ├── enrollment_date
  ├── termination_date
  ├── status (active|pending|terminated)
  
  licenses (PG)
  ├── provider_npi (FK)
  ├── state
  ├── license_number
  ├── issue_date
  ├── expiry_date
  ├── verification_source (NPI+state board)
  ├── last_verified_at
  ```
- **Known Issues** → License verification lag (14-day batch update)
- **Roadmap** → Real-time license API integration

---

### Appeals Agent
- **What it is** — Appeal workflows, letter generation, regulatory compliance
- **Status** — 🔨 Building
- **Owner** — Appeals Agent
- **Links to:**
  - **Spec** → `docs/appeals-agent-spec.md`
  - **Playbook Card** → Chat UI (Appeals tab)
  - **Decision Engine** → `mobius-contracts/appeals/` (logic)
- **Schema:**
  ```
  appeals (PG)
  ├── id (UUID)
  ├── org_id (FK)
  ├── claim_id (FK)
  ├── denial_reason
  ├── appeal_level (1|2|3)
  ├── filing_date
  ├── deadline_date
  ├── status (pending|approved|denied|withdrawn)
  ├── decision_date
  ├── decision_reason (TEXT)
  
  appeal_letters (PG)
  ├── appeal_id (FK)
  ├── template_used
  ├── generated_at
  ├── content (TEXT)
  ├── attachments (ARRAY<file_id>)
  ├── sent_date
  ```
- **Known Issues** → Decision engine needs M6 judge calibration, L3 promotion rules undefined
- **Roadmap** → M6 judge + L3 promotion (Wilson-LB), §11 Bayes flip-gate

---

### Sourcing Agent
- **What it is** — Web scraping, document classification, corpus building
- **Status** — ✅ Live
- **Owner** — Sourcing Agent (owned by me, Retriever Agent)
- **Links to:**
  - **Code** → `mobius-rag/src/sourcing/`
  - **Spec** → `docs/sourcing-agent-spec.md`
  - **Classifier** → Payor Classification (owned by Payor Platform Agent)
  - **Chunking Jobs Queue** → `mobius_rag.chunking_jobs` (PG)
- **Schema:**
  ```
  raw_documents (PG)
  ├── id (UUID)
  ├── source_url (TEXT)
  ├── payor_id (FK)
  ├── doc_type (fee_schedule|policy|manual|addendum)
  ├── title (TEXT)
  ├── content (TEXT)
  ├── scraped_at
  ├── hash (md5)
  ├── status (raw|extracted|classified|chunked|published)
  
  extraction_jobs (PG)
  ├── id
  ├── document_id (FK)
  ├── status (queued|processing|completed|failed)
  ├── extracted_tables (INT)
  ├── extracted_sections (INT)
  ├── created_at
  ├── completed_at
  
  chunking_jobs (PG)
  ├── id
  ├── document_id (FK)
  ├── chunks_count (INT)
  ├── avg_chunk_length (INT)
  ├── created_at
  ├── status (queued|processing|completed)
  ```
- **Known Issues** → Web scrape verification brittle, robots.txt compliance gap
- **Roadmap** → Distributed scraper, JavaScript-heavy site support

---

### Curation Agent
- **What it is** — Chunking, embedding, tagging, metadata enrichment
- **Status** — ✅ Live
- **Owner** — Curation Agent (owned by me, Retriever Agent)
- **Links to:**
  - **Code** → `mobius-rag/src/curation/`
  - **Spec** → `docs/curation-agent-spec.md`
  - **Lexicon** → `docs/lexicon/` (tag schema)
- **Schema:**
  ```
  chunks (PG)
  ├── id (UUID)
  ├── document_id (FK)
  ├── sequence_num (INT)
  ├── content (TEXT)
  ├── start_offset (INT)
  ├── end_offset (INT)
  ├── metadata (JSONB)
  │   ├── payor_id
  │   ├── service_line
  │   ├── doc_type
  │   ├── extracted_from_table (BOOL)
  ├── created_at
  
  chunk_embeddings (pgvector)
  ├── chunk_id (FK)
  ├── embedding (vector(768))
  ├── model_name
  ├── model_version
  ├── created_at
  
  chunk_tags (PG)
  ├── id
  ├── chunk_id (FK)
  ├── tag_name (TEXT)
  ├── confidence (FLOAT)
  ├── assigned_by (LLM|human)
  ├── created_at
  
  tag_selectivity (PG)
  ├── tag_name
  ├── total_chunks (INT)
  ├── pool_size (INT) [target for balancing]
  ├── tagging_quality (FLOAT)
  ├── recall (FLOAT)
  ```
- **Known Issues** → Tagging quality varies by tag; chunk size inconsistent
- **Roadmap** → Tag-selectivity loop tuning, per-payor chunk strategies

---

### Deep Research Agent
- **What it is** — Researches gaps, verifies, feeds Fact Store
- **Status** — 🔨 Building (~70% complete)
- **Owner** — Deep Research Agent (actually a Skill, not an Agent)
- **Links to:**
  - **Code** → `mobius-rag/src/deep_research/`
  - **Spec** → `docs/deep-research-spec.md`
  - **Use Cases** → `docs/deep-research-use-cases.md` (6 scenarios)
- **Use Cases:**
  - UC-1: Batch sourcing new payor
  - UC-2: Standing audit (continuous freshness)
  - UC-3: Appeals runtime pack (ad-hoc fact assembly)
  - UC-4: Reverify diff (check if fact is still valid)
  - UC-5: Divergence probe (payor A says X, B says Y; research)
  - UC-6: New-payor coverage sweep (find gaps on launch)
- **Schema:**
  ```
  research_jobs (PG)
  ├── id (UUID)
  ├── use_case (UC-1|UC-2|UC-3|UC-4|UC-5|UC-6)
  ├── gap_topic (TEXT)
  ├── status (open|in_progress|completed)
  ├── created_by (eval_system|operator)
  ├── priority (INT)
  
  research_findings (PG)
  ├── job_id (FK)
  ├── finding (TEXT)
  ├── source_doc_id (FK)
  ├── confidence (FLOAT)
  ├── verified_by (human|critic_model)
  ├── verification_status (unverified|pending|verified|rejected)
  
  fact_candidates (PG)
  ├── id
  ├── finding_id (FK)
  ├── fact_text (TEXT)
  ├── payor_id
  ├── predicate
  ├── status (candidate|accepted|rejected)
  ├── ingestion_date
  ```
- **Known Issues** → Critic verification has high false-positive rate; document_id propagation incomplete
- **Roadmap** → UC-1 batch sourcing when DR carries document_id

---

## **LAYER 6: INTELLIGENCE**

### Fact Store (Certified Facts)
- **What it is** — Instant, deterministic facts with provenance
- **Status** — ✅ Live
- **Owner** — Payor Platform Agent + Master RAG (Payor Fact Store Persistence owned by me, Retriever Agent)
- **Links to:**
  - **Code** → `mobius-rag/src/facts/`
  - **Spec** → `docs/payor-fact-store-api.md`
  - **Coverage Map** → `docs/fact-store-coverage-map.json`
- **Schema:**
  ```
  facts (PG)
  ├── id (UUID)
  ├── payor_id (FK)
  ├── predicate (TEXT) [e.g. "fee_schedule_code_90834"]
  ├── answer (TEXT)
  ├── source_doc_id (FK)
  ├── source_page
  ├── source_section
  ├── confidence (HIGH|MEDIUM|LOW)
  ├── verification_status (ACCEPTED|PENDING|REJECTED)
  ├── accepted_date
  ├── expiry_date
  ├── created_by (deep_research|operator)
  ├── created_at
  ├── updated_at
  
  coverage_map (PG)
  ├── payor_id
  ├── predicate
  ├── available (BOOL)
  ├── last_updated
  ```
- **Contract:** Answer-or-abstain. No guessing.
- **Known Issues** → Coverage too thin to matter; 65 facts total across all payors
- **Roadmap** → Deep Research UC-1 batch sourcing to grow coverage

---

### RAG Corpus (Rich Documents)
- **What it is** — Searchable policy documents with embeddings
- **Status** — ✅ Live
- **Owner** — Master RAG Agent (owned by me, Retriever Agent)
- **Links to:**
  - **Code** → `mobius-rag/src/retrieval/`
  - **Spec** → `docs/rag-backend.md`
  - **Embedding Model** → text-embedding-004 (768-dim, OpenAI)
- **Schema:**
  ```
  chunks (see Curation section above)
  
  chunk_embeddings (pgvector)
  ├── chunk_id (FK)
  ├── embedding (vector(768))
  ├── model (text-embedding-004)
  
  retrieval_logs (BQ)
  ├── run_id
  ├── query (TEXT)
  ├── chunks_retrieved (ARRAY<chunk_id>)
  ├── ranking_scores (ARRAY<FLOAT>)
  ├── latency_ms
  ├── accuracy_score (from Eval)
  ```
- **Known Issues** → Overlap between 22q chunks causes redundant retrieval
- **Roadmap** → Deduplication via content-digest, re-ranking model

---

## **LAYER 7: EVALUATION & FEEDBACK**

### Accuracy Grading
- **What it is** — Grade answer correctness via judge model + human spot-checks
- **Status** — ✅ Live
- **Owner** — Eval Command Center
- **Links to:**
  - **Code** → `mobius-rag/src/eval/graders/accuracy.py`
  - **Judge Model** → Claude 3.5 Sonnet (M6 tier)
  - **Rubric** → `docs/eval-rubric-accuracy.md`
- **Rubric:**
  - 1.0 = Perfectly correct, well-cited
  - 0.75 = Correct, minor citation gaps
  - 0.5 = Partially correct or speculative
  - 0.0 = Wrong or hallucinated
- **Schema:**
  ```
  accuracy_grades (BQ)
  ├── run_id
  ├── query
  ├── answer
  ├── score (0-1)
  ├── reasoning (TEXT)
  ├── grader_model
  ├── graded_at
  ```
- **Known Issues** → Judge model sometimes too lenient; human review gap
- **Roadmap** → M6 judge + L3 promotion (Wilson-LB)

---

### Coverage Analysis
- **What it is** — Identify gaps (topics we couldn't answer)
- **Status** — ✅ Live
- **Owner** — Eval Command Center
- **Links to:**
  - **Code** → `mobius-rag/src/eval/coverage.py`
  - **Gap Queue** → `mobius_rag.coverage_gaps` (PG)
- **Schema:**
  ```
  coverage_gaps (PG)
  ├── id
  ├── topic (TEXT)
  ├── count (INT)
  ├── first_seen_at
  ├── last_seen_at
  ├── priority (INT) [high = more frequently missed]
  ├── assigned_to_deep_research (BOOL)
  ├── status (open|in_progress|resolved)
  ```
- **Known Issues** → Gap deduplication weak; lots of near-duplicates
- **Roadmap** → Semantic deduplication, auto-route to Deep Research

---

## **DEEP RESEARCH (PARALLEL SYSTEM)**

### Deep Research System
- **What it is** — Continuous learning loop: identify gaps → research → verify → ingest
- **Status** — 🔨 Building (~70% complete)
- **Owner** — Deep Research Skill (called by Domain Agents)
- **Links to:**
  - **Code** → `mobius-rag/src/deep_research/`
  - **Spec** → `docs/deep-research-spec.md`
  - **Use Cases** → `docs/deep-research-use-cases.md`
- **Data Flow:**
  ```
  Eval Gap Signals
       ↓
  Deep Research Queue
       ↓
  Research Job (UC-1 through UC-6)
       ↓
  Critic Verification
       ↓
  Fact Store (if certified) or RAG Corpus (if documentation)
       ↓
  Next operator gets better knowledge
  ```
- **Schema:**
  ```
  research_pipeline (BQ)
  ├── phase (gap_signal|research|verification|ingestion)
  ├── job_id
  ├── status
  ├── throughput (jobs/day)
  ├── quality_score (verified/total)
  
  deep_research_findings (PG)
  ├── id (UUID)
  ├── job_id (FK)
  ├── finding (TEXT)
  ├── source_doc_id (FK)
  ├── confidence (FLOAT)
  ├── verified_at
  ├── fact_id_ingested (FK facts table)
  ```
- **Known Issues** → 70% complete; document_id propagation blocking UC-1
- **Roadmap** → Unblock UC-1, scale verification, continuous loop

---

## **KEY SCHEMA NOTES**

### Cross-layer Keys
- `org_id` — Shared across all tables (multi-tenant isolation)
- `payor_id` — Payor context for Intelligence + Sourcing
- `run_id` (BQ logs) — Ties together: query, strategy, latency, grading, bandit reward
- `document_id` (PG raw_documents) — Provenance chain: raw → extracted → chunked → embedded → tagged → cited

### Status Enums
- Surfaces: live|building|planned
- Agents: live|building|blocked
- Components: queued|processing|completed|failed

### Performance Tables (BQ)
- Centralized in BigQuery for OLAP (analysis)
- Denormalized from PG for fast queries
- 3-hour lag from transaction to BQ
- Feed Eval scores and bandit rewards

---

## **NAVIGATION RULES**

When clicking a component in the platform:
1. **Expand** → See What/Status/Owner/Links/Schema
2. **Click "Spec"** → Navigate to detailed spec document
3. **Click "UI"** → Open in new tab (if exists)
4. **Click "Code"** → Jump to source repo (if exists)
5. **Click "Schema"** → Scroll to schema details below
6. **Click "Issues"** → Jump to BUG_LOG.md
7. **Click "Roadmap"** → Show next 3 milestones

---

*Last Updated: 2026-09-07*
