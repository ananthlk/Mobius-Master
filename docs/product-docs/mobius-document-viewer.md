# Mobius Document Viewer
> The in-app reader that lets you open a source document, jump straight to a cited passage, and inspect or curate the facts and tags Mobius has pulled from it.

## Purpose
The Mobius Document Viewer is the shared reading surface for corpus documents (payer manuals, policy PDFs, scraped pages, and uploads). It renders a document page-by-page in a clean "Mobius" text view, or — when the original file is stored — switches to the actual source PDF. On top of the text it overlays Mobius-generated highlights: extracted **facts** and applied **tags**, each with a hover tooltip. When you follow a citation from a chat answer or a retrieved source, the viewer opens to the right page and scrolls to (and highlights) the exact quoted text, so you can verify an answer against its source in one click.

Technically it is a shared React component library (`@mobius/document-viewer`) rather than a standalone app. It ships the reader UI (toolbar, sections sidebar, page navigation, highlight/annotation layer, tooltips, context menus) and is embedded by host modules — today primarily the RAG frontend's "Read" tab — which supply the document pages, highlights, and the interaction behavior.

## Audience
- **End users / operators** verifying where an answer came from: following citations, reading the underlying policy passage, downloading the source.
- **Corpus curators / knowledge editors** who review and correct what Mobius extracted: approving, rejecting, or deleting facts, and adding or removing tags directly on the document text.
- **Developers** integrating the reader into a new module (they provide pages, highlights, and an interaction config).

## Capabilities
- **Two view modes:**
  - *Mobius Renderer* — an enriched, readable text view (Markdown or normalized plain text) with Mobius highlights and annotations.
  - *Original Document* — the actual source PDF, rendered via PDF.js, shown only when the original file exists in storage. A toolbar toggle switches between the two; if there's no original file, only the Mobius view is available.
- **Supported content:** Markdown pages (headings, tables, ordered/unordered lists rendered with GFM), plain extracted text, and original PDF files. The "Original Document" pane uses react-pdf and expects a PDF; the RAG wrapper only offers the Original toggle when the document's stored path starts with `gs://` (a GCS original). [UNVERIFIED: whether non-PDF originals (e.g. DOCX) are converted to PDF upstream before storage is a RAG-API/ingestion concern, not determined from viewer or wrapper code.]
- **Sections sidebar:** a left panel listing every page, labeled by page number plus an auto-detected first section header. Click a section to jump to it. The sidebar can be collapsed/expanded via a chevron. Pages with a non-`success` extraction status show a small status badge.
- **Page navigation:** floating left/right chevrons, a bottom "Previous / Page X of Y / Next" bar, and section clicks in the sidebar.
- **Zoom:** zoom in/out (50%–300%, 25% steps), a percentage readout, and Reset. Keyboard shortcuts Ctrl/Cmd `+`, `-`, and `0` are supported.
- **Highlights on text:** facts and tags extracted by Mobius are highlighted inline in the Mobius view (and matched onto the PDF text layer in Original view). Highlight styling and content are driven by the host module.
- **Hover tooltips:** hovering a highlight shows a tooltip. In the RAG integration these render fact details, tag details, or policy-line tag details.
- **Citation jumping / scroll-to-text:** the viewer can be told to open a specific page and either scroll to a specific highlight by ID (fact navigation) or find and highlight a quoted passage by its text (`scrollToText` / "Quoted in chat"), smoothly scrolling it into view. Fact-ID navigation takes precedence over text matching. Text matching is whitespace-normalized with a case-insensitive fallback.
- **Right-click context menus (host-defined):**
  - On a highlighted fact: *Approve fact*, *Reject fact*, *Delete fact* (options shown depend on current verification status).
  - On a highlighted tag: *Remove tag*.
  - On selected text: *Mark as fact*, plus *Add tag →* a taxonomy of domains/leaf tags (claims, eligibility, utilization management, credentialing, compliance, provider, health care services, etc.).
- **Text selection:** users can select text to drive the selection menu above; this can be disabled per host module (e.g. Chat disables it).
- **Download:** a Download button opens the best available source — the original file if present, otherwise a server-generated PDF built from the page text/markdown, otherwise a Markdown export.
- **Document selector:** in the RAG integration, a dropdown lets you pick which document to view (and switch between documents).

## Navigation & Access
The viewer is **embedded, not standalone**. It has no route of its own; host modules mount the `DocumentViewer` React component.

- **Primary entry point — RAG "Read" tab:** the RAG frontend's `DocumentReaderTab` wraps the shared viewer. It is reachable via a deep-link URL of the form:
  `<RAG_APP_BASE>?tab=read&documentId=<id>&pageNumber=<n>&citeText=<quoted text>`
  (`pageNumber` and `citeText` are optional; `citeText` drives the scroll-to-highlight behavior).
- **From chat citations / sources:** chat answer citations and retrieved sources build that RAG deep-link (`getRagDocumentUrl`) and open it in a new tab, landing you on the cited page with the quote highlighted. Chat also has its own in-page "Doc Reader Panel" slideout — a vanilla-JS DOM component in `mobius-chat/frontend/src/app.ts` that calls `/chat/doc-reader/read` (proxying `mobius-doc-reader`) and renders sections as cards, with an "Open in RAG ↗" header link back to the deep-link. This slideout is a **separate reader from `@mobius/document-viewer`, not the shared React component** — confirmed in code. (A code comment above it references an earlier RAG-iframe approach that embedded `@mobius/document-viewer`, but that was reverted in favor of the current inline reader.)
- **Document selector:** within the Read tab, when no document is chosen the viewer shows a "Select Document" dropdown; once selected it renders pages.

## Key User Workflows
1. **Verify a chat answer against its source.**
   1. In chat, click a citation / source link on an answer.
   2. A new tab opens the RAG Read tab at the cited document and page.
   3. The quoted passage is highlighted and scrolled into view; read the surrounding text to confirm the claim.
   4. Optionally toggle to *Original Document* to see the exact source PDF, or Download the source.

2. **Read a document end-to-end.**
   1. Open the Read tab and pick a document from the selector.
   2. Use the Sections sidebar to jump between headed sections, or the Previous/Next controls to page through.
   3. Zoom in/out for readability; collapse the sidebar for a wider reading pane.

3. **Curate extracted facts.**
   1. Open a document; extracted facts appear as highlights (hover to read details).
   2. Right-click a fact highlight and choose *Approve*, *Reject*, or *Delete* to correct Mobius's extraction.

4. **Tag a passage.**
   1. Select a span of text in the Mobius view.
   2. Right-click and either *Mark as fact* or *Add tag →* pick a domain and leaf tag.
   3. To remove a tag later, right-click the tag highlight and choose *Remove tag*.

## Integrations
- **mobius-rag (frontend):** the main consumer. `DocumentReaderTab.tsx` fetches pages, facts, and tags from the RAG API, maps them to the viewer's generic `Highlight[]`, supplies the fact/tag tooltips and approve/reject/tag context menus, and wires original-file / PDF-download / markdown-download URLs (`/documents/{id}/file`, `/documents/{id}/download/pdf`, `/documents/{id}/download/markdown`).
- **mobius-chat (frontend):** feeds the viewer indirectly — chat answer citations and retrieved sources deep-link into the RAG Read tab (with page + cite text) so answers are traceable to source. Chat's own inline "Doc Reader Panel" is a distinct component (`mobius-doc-reader`-backed, not `@mobius/document-viewer`); see the note under Navigation & Access.
- **Extensibility:** the component is provider-agnostic via its `InteractionConfig` (tooltips, highlight menus, selection menus, and a `textSelectionEnabled` flag). The type comments cite RAG, Lexicon, and Chat as intended hosts, but a full-repo search shows **only mobius-rag actually imports `@mobius/document-viewer`** today. Lexicon does not embed it, and Chat only builds the RAG deep-link (its own panel uses a different reader — see above). The Lexicon/Chat mentions in the type comments are aspirational, not shipped integrations.

## Doc-readiness notes
- **Primary audience tag:** mixed (user-facing reader + curator actions; the module itself is a developer-facing component library).
- **What's solid:** view modes, zoom, sections sidebar, page navigation, download fallbacks, highlight overlay, hover tooltips, citation/scroll-to-text jumping, and the fact/tag curation menus are all directly grounded in the component source and the RAG integration.
- **Resolved during verification:**
  - The chat "Doc Reader Panel" is confirmed **separate** from `@mobius/document-viewer` (vanilla-JS, `mobius-doc-reader`-backed). Docs must not conflate them.
  - Only **mobius-rag** embeds `@mobius/document-viewer` today; Lexicon does not.
- **Ambiguous / gaps a human must fill:**
  - Supported *original* file formats beyond PDF: the viewer's Original pane assumes PDF, and the RAG wrapper only enables it for `gs://` originals. Whether non-PDF sources are converted upstream is a RAG-ingestion question, not answerable from this module.
  - Auth/permissions and which document sets a given user can open (not covered by viewer code).
  - Exact backend contract for facts/tags and the effect of Approve/Reject/Delete (handled by RAG API, not this module).
  - No screenshots or exact UI labels verified against a running instance.
