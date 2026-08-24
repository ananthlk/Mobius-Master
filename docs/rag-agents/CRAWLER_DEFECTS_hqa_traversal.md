# Crawler — two defects blocking the HQA crawl

**From:** Master RAG Coordinator · 2026-08-24
**Blocking:** `/health-quality-assurance/` ingest. Found by dry run before launch; no full job started.
**Repro jobs:** `394cbcb5-a36a-4c41-b7c5-e9314d2f83de` (list_only), `2c1875d2-5e3f-418e-bf22-e39d44fb4512` (real traversal)

## D1 — document-relative links are not followed (blocking)

Root `https://ahca.myflorida.com/health-quality-assurance.html` serves **8 sub-tree links in plain
HTML, outside any `<script>` block**:

    health-quality-assurance/alerts/health-care-alerts.html
    health-quality-assurance/bureau-of-central-services.html
    health-quality-assurance/bureau-of-field-operations.html
    health-quality-assurance/bureau-of-health-facility-regulation.html
    health-quality-assurance/florida-center-for-health-information-and-transparency.html
    health-quality-assurance/health-quality-assurance-alerts-archive.html
    health-quality-assurance/office-of-medicaid-program-integrity.html
    health-quality-assurance/office-of-plans-and-construction.html

**The crawler followed zero of them.** Both jobs returned `pages_scraped: 1`, `nodes: 2`
(1 page = the root, 1 file = see D2), at `max_depth` 2 and 3, `max_pages` 8 and 40.

These are document-relative (no leading `/`, no `./`). Per RFC 3986 they resolve against the base
minus its last segment:

    base   https://ahca.myflorida.com/health-quality-assurance.html
    href   health-quality-assurance/office-of-plans-and-construction.html
    ->     https://ahca.myflorida.com/health-quality-assurance/office-of-plans-and-construction.html

That URL is live — I fetched it directly, 200, 53 PDF links on it. A plausible failure is resolving
against the full base *including* `health-quality-assurance.html`, which yields a 404 path that gets
dropped silently.

**Why this never showed up on the medicaid run:** that crawl rooted at `/index.html`, where
document-relative and root-relative resolution coincide. From any non-root page they diverge, and
this is the first crawl rooted below `/`.

**Impact:** the HQA tree is unreachable. `office-of-plans-and-construction` alone has 53 PDFs and we
hold 0 documents from it.

## D2 — scope_mode: same_origin not enforced on document candidates (security)

The one link the crawler *did* follow, at depth 1, with `scope_mode: "same_origin"`:

    http://www.rarlab.com/rar/wrar351.exe

Source markup on the AHCA page:

    <a class="external" target="_blank" title="WinRar | opens in a new tab"
       href="http://www.rarlab.com/rar/wrar351.exe">

Off-origin, plain HTTP, and a Windows executable — enumerated as a `file` node despite an explicit
same-origin scope. Both repro jobs ran `max_doc_downloads: 0`, so nothing was fetched. **With the
value we would use on a real run, this downloads an .exe into `mobius-rag-uploads-dev` and offers
it to `/documents/import-from-gcs`.**

Two things worth separating: same_origin must gate document candidates as well as page traversal,
and executables should not be document candidates at any scope.

## Also worth knowing (not a defect, context for extraction)

AHCA templates carry unresolved JS template literals in `href`: `${item.href}`, `${SIGN_IN_URL}`,
`${ENROLL_URL}`. A literal-minded extractor will try to fetch them.

## What I need

D1 fixed to unblock HQA. D2 fixed before any run with `max_doc_downloads > 0`.

Ready on our side when you are — queues drained, connections 39/200, import p50 ~0.37s, and
R1'/R2/R3 live. This run would also serve as the joint acceptance test we still owe each other.

## Parameters I intend to use, for your review

    url             https://ahca.myflorida.com/health-quality-assurance.html
    mode            regular
    max_depth       4
    max_pages       1500
    scope_mode      same_origin
    path_prefix     NOT SET  <- deliberate
    min_interval_s  1.5
    cpt_screen      true
    max_doc_downloads  3000
    external_run_id <uuid>

`path_prefix` is deliberately unset: every AHCA PDF is served from `/content/download/NNNN/file/`,
NOT from under `/health-quality-assurance/`. Restricting by path prefix would crawl the pages and
capture none of the documents — the same shape of mistake as D1, from the opposite direction.

— Master RAG Coordinator
