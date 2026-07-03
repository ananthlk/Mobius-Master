# Mobius Product Documentation

User-facing and technical documentation for every Mobius module, written for both
human readers and (eventually) RAG ingestion + a chat-invokable "product help" skill.

Each module doc follows the same template: **Purpose · Audience · Capabilities ·
Navigation & Access · Key User Workflows · Integrations · Doc-readiness notes**.

## Status legend

- ✅ **Verified** — every claim checked against live code in a second pass.
- Each doc has a **`## Not yet available (planned)`** section. Anything there renders
  in the UI but is stubbed / mocked / not wired. **Never document these as working.**
- `[UNVERIFIED: …]` inline = genuinely not determinable from code (a product/GTM
  decision or an untraced cross-module path). Needs a human, not more grepping.

## Scope

**Active focus = the 5 deployed core areas:** chat, rag, lexicon, skills, strategy.
Everything else is documented but **out of active scope** — either not deployed yet
(Mobius OS) or peripheral to the current product-awareness effort.

## Coverage map — in scope

| Module | Doc | Audience | What it actually is | Biggest "not yet available" |
|---|---|---|---|---|
| **Chat** | [mobius-chat.md](mobius-chat.md) | user | Flagship conversational assistant; sourced answers + `/pipeline` (8 steps) | ⋯ upload purpose-picker, email-a-thread UI, MS/Enterprise SSO |
| **RAG & Retrieval** | [rag-backend.md](rag-backend.md) | dev | rag (service) / retriever (library) / rag-api (HTTP wrapper) | Strategy (d) external escalation unwired |
| **Lexicon** | [lexicon.md](lexicon.md) | dev | Versioned p/d/j tagging vocabulary + 3-stage candidate pipeline; filters corpus + drives strategy | `mobius-config/lexicons/` unwired (empty) |
| **Skills** | [skills.md](skills.md) | mixed | 13 chat builtins + 21 MCP tools | Analytics/market-data tools (prose-only), appeals (not wired by default) |
| **Strategy** (story-ui) | [story-ui-and-landing.md](story-ui-and-landing.md) | mixed | The "Mobius story" — 31-slide market-intelligence strategy deck (+ internal launcher) | Modular per-slide deck (preview-only); `briefing.modules` live path |

## Coverage map — out of scope (documented, not active focus)

| Module | Doc | Why out of scope |
|---|---|---|
| Mobius OS | [mobius-os.md](mobius-os.md) | **Not deployed yet** (only Chat mode wired; rest are mockups) |
| Credentialing & Roster | [credentialing-and-roster.md](credentialing-and-roster.md) | Peripheral to current effort |
| User & Auth | [user-and-auth.md](user-and-auth.md) | Peripheral; most features unbuilt |
| Document Viewer | [mobius-document-viewer.md](mobius-document-viewer.md) | Shared component, folded into rag/chat |
| Supporting Infra | [infrastructure.md](infrastructure.md) | Dev plumbing (design, config, dbt, qa, cache, contracts, db-agent, migrations, meval) |

## Cross-cutting reality notes

**Module names mislead — document behavior, not names.**
- `mobius-os` is a browser extension, not the platform shell.
- `mobius-story-ui` is a slide deck app, not a Storybook/component library.
- `mobius-document-viewer` is a React component, not a standalone viewer app.
- `landing` is an internal launcher dashboard, not a marketing site.

**Several headline capabilities are aspirational.** No team management, SSO stubbed,
answer-cache undeployed, most OS workflow modes are mocks, modular deck preview-only.
User docs must lead with what works today and cordon off the rest.

**Known duplication / cleanup (internal, not user-facing):**
- Credentialing / org / roster pages exist **three times**: `mobius-story-ui/public/`,
  `landing/`, and the `:8011` roster-ui skill server's `static/` (some are symlinks
  into a git worktree). Slated for de-dup.

**Stale docs discovered:**
- `mobius-rag/…/PATH_B_STATUS.md` says the lexicon/tag pipeline is broken — it isn't;
  the doc predates the code that landed it. (Good example of why the freshness signal
  in a product-awareness agent matters.)

## Next steps (ingestion phase)

1. **Metadata schema** — product docs need new facets (`audience`, `doc_type`,
   `module`, `doc_class`). Today the corpus only filters on payer/state/program/
   authority_level, so these must be **promoted to real columns** (following the
   `authority_level → document_authority_level` pattern) to be filterable — JSONB
   alone won't power the retrieval skills. Note the two-path table subtlety:
   mobius-rag reads `rag_published_embeddings`, the retriever library reads
   `published_rag_metadata`.
2. **Two retrieval skills** — a user-help and a dev-help skill, both filtering the
   *same* corpus by tag (follow the existing `search_corpus` builtin pattern). Add a
   `doc_class:product` facet so product docs don't pollute policy search.
3. **Freshness tracking** — flag docs stale relative to their source commit
   (reuse the retag/lexicon-revision staleness machinery).
