# Mobius product-v1.0.0

**Cut:** 2026-09-07 · **Modules:** 14 tagged, 8 pre-release, 1 deprecated
**Manifest:** [product-v1.0.0.lock.json](product-v1.0.0.lock.json)

---

## What this release is

This is **not a feature release. It is a baseline.**

Fourteen modules have been shipping continuously since January without a
version between them. "What is in production?" has been a question you could
only answer by reading a deploy log. From this tag forward it is a question with
an exact answer: a module name, a semver, and a commit SHA.

Nothing in this release is new. Everything in it is now *named*.

## What a user can do at v1.0.0

- **Ask a payor-policy question and get a cited answer.** Chat runs a ReAct loop
  over a declared 23-tool manifest, retrieves from a pgvector corpus, and returns
  an answer card with citations a reviewer can follow back to a document page.
- **Ask about Mobius itself.** `product-awareness` answers "how do I use this?"
  from the product docs, and files every miss as tracked documentation debt.
- **Work inside their own tools.** The `mobius-os` browser extension puts chat
  beside the EHR, with a local zero-egress PHI screen before anything leaves the
  page.
- **Keep a personal workspace.** `mobius-vault` holds recent and liked answers,
  uploads, and tasks in a 7-section panel that docks into chat.
- **Be shown, not told.** `mobius-interact` executes published guide scripts, so
  an answer can carry a "Show me" chip that drives the actual UI.
- **Have answers graded.** `mobius-qa` runs the eval harness and the lexicon
  maintenance loop that feeds retrieval quality.

## The state this release is honest about

A baseline is only worth cutting if it records the real condition. These are the
material findings from writing the fourteen module notes — every one verified
against the repository, not inferred.

### Two modules are tagged from feature branches, not `main`

`mobius-rag` is tagged from `retriever-answer-engine` (**+201 commits** over
`main`) and `mobius-payor` from `claude/sources-module-canonical-payor-enumerate`
(**+227**). Both branches are *strictly ahead* — the branch is the live product
and `main` is the stale ref. The manifest names the branch it tagged rather than
quietly tagging a `main` that nobody is running.

**This should not survive to v1.1.** Two of the highest-traffic modules in the
product have no releasable `main`.

### `mobius-os` shows why per-module versioning was necessary

It already carried a `v1.0.0` tag — pointing at a January commit, roughly sixty
commits behind its own HEAD. Rather than move a published tag, it is assigned
**v1.1.0**. One module's clock had already run ahead of the rest, which is
precisely the situation a single global version number cannot express.

### Correctness issues carried into v1.0.0

| Module | Issue |
|---|---|
| `mobius-payor` | **Duplicate migration numbers** — two different `047_*.sql` and two `050_*.sql`. Migration ordering is ambiguous. |
| `mobius-interact` | **Write auth is designed but unenforced.** Any caller can publish or delete any namespace. A production script was clobbered by a smoke test on 2026-07-08 and caught only because someone was watching. |
| `product-awareness` | **`τ_gap` has two contradictory values.** The calibration was actually performed (0.544, two-sided on live Vertex+pgvector) but the code default was never updated from the uncalibrated 0.35 — so every deployment except one dev env abstains far too eagerly. |
| `mobius-skills` | The web-scraper's **robots default-deny bug ran undetected March→August**. Any coverage or compliance figure measured before that fix reflects the bug, not the sites' policies. |
| `mobius-chat` | Open `thread_id` write-path bug (#108). Structured output is Vertex-only. |

### Maturity gaps

- **`mobius-auth` has no tests at all**, and ships a committed `dist/` with no
  version pinning — it is consumed by file path.
- **`mobius-answer-cache` is tagged but not deployed.** Its README still says so,
  and Chroma remains the default backend despite the platform's pgvector cutover.
- **`mobius-dbt`'s expensive marts are excluded from CI**, so the most
  operationally significant models are the least tested.
- **`mobius-rag/STATUS.md` is months stale**, describing Step 6 PDF extraction as
  current work. Anyone using it to orient themselves is being misled.
- **`mobius-story-ui`'s per-slide refactor is half-done** — 34 slide directories
  coexist with a still-monolithic `story.html`.

## Module versions

| Module | Version | Commit | Branch |
|---|---|---|---|
| mobius-chat | v1.0.0 | `3fa105d` | main |
| mobius-rag | v1.0.0 | `53f6178` | ⚠ retriever-answer-engine |
| mobius-payor | v1.0.0 | `ee05685` | ⚠ claude/sources-module-canonical-payor-enumerate |
| mobius-skills | v1.0.0 | `5adc343` | main |
| mobius-skills-mcp | v1.0.0 | `0a5f558` | main |
| mobius-os | v1.1.0 | `a5696f4` | main |
| mobius-story-ui | v1.0.0 | `7da229a` | main |
| mobius-qa | v1.0.0 | `7fe4ae2` | main |
| mobius-interact | v1.0.0 | `aa6767d` | main |
| mobius-dbt | v1.0.0 | `400b166` | main |
| mobius-auth | v1.0.0 | `852f4f4` | main |
| mobius-answer-cache | v1.0.0 | `73bf7e3` | main |
| mobius-vault | v1.0.0 | `a434e85` | main |
| product-awareness | v1.0.0 | `44d14cd` | main |

Uncommitted work at cut time was **not** included — a tag points at a commit.
The manifest records the excluded file count per module (29 files across 8
modules: payor 11, rag 7, chat 3, qa 3, dbt 2, and one each in skills-mcp,
story-ui and interact).

### Not in the release set

**Pre-release** (carried in the manifest, untagged — too early to claim a
version): `mobius-config`, `mobius-contracts`, `mobius-db-agent`,
`mobius-design`, `mobius-document-viewer`, `mobius-migrations`,
`mobius-qa-modules`, `mobius-rag-api`.

**Deprecated:** `mobius-retriever` — superseded by the RAG module's own
retrieval path.

## What v1.1.0 should require

1. `mobius-rag` and `mobius-payor` merged to `main`, so the product can be built
   from default branches.
2. The `payor` duplicate migration numbers resolved.
3. `product-awareness` `τ_gap` set to its calibrated value in code.
4. `mobius-interact` namespace write-auth enforced.
5. A doc-ingestion surface, so product knowledge stops being a hardcoded dict.
