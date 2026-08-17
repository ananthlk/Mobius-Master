# Crawler — decision log, 2026-08-12 → 08-15

Every commit, and every **judgment call** behind them. Written because Ananth
asked for the calls to be flagged and persisted, not just reported in chat.

**Scope:** Crawler = sub-scope of the Sourcing agent. Owns
`mobius-skills/web-scraper` + `mobius-payor/app/robots.py` + no-crawl
compliance fleet-wide (Ananth, 2026-08-12).

Related: [`crawler-sub-scope.md`](crawler-sub-scope.md) ·
[`crawler-signoff/`](crawler-signoff/README.md) · [`../../ownership.yaml`](../../ownership.yaml)

---

## 1. Commits

### `mobius-skills` (branch `main`) — the crawler service

| Commit | What |
|---|---|
| `06e540e` | Exhaustive capture: honour crawl params, HTML as first-class content, classify after discovery |
| `f851657` | Two defects found by live-testing the real site (nested-chrome crash, path_prefix killing file capture) |
| `3c2f8cc` | Section-first frontier — bounded crawls spend budget on the section, not site furniture |
| `435646b` | Time-aware crawl: caller declares a budget, we return best-effort within it |
| `2d5422d` | Ranked link manifest + honest 404 — stop making the caller guess URLs |
| `7459e1a` | `POST /fetch/batch` — the fleet's single compliant web-egress path |
| `0d3c1b9` | Silent Brotli corruption in the shared fetch headers |
| `b53290c` | Robots must follow the redirect |
| `4c86089` | Resolve citation wrappers **before** the robots gate — ordering was the bug |

### Superrepo (`main`) — skills-core + governance

| Commit | What |
|---|---|
| `274bca2` | Callers declare a latency budget on `web_scrape` (quick 10s / medium 18s / detailed 24s) |
| `112d1d1` | Hand ReAct the site's links instead of letting it guess |
| `cd03b88` | Commit the sign-off ledger + ownership rows so seats can actually read them |

### `mobius-rag` (`main`)

| Commit | What |
|---|---|
| `0479f2f` | Per-attempt fetch audit trail (`source_fetch_attempts`) |
| `a3c88bf` | The source-registry curator UI at `GET /curator` |

*(Both originated on `retriever-answer-engine` as `60b7135` / `b808f2d` and were
moved to `main` deliberately — see call **J**.)*

---

## 2. Judgment calls — ROBOTS / COMPLIANCE

These are the ones to scrutinise. Ananth made me responsible for "everything we
scrape related honoring the no crawl rules", so each is recorded with its
reasoning and its risk.

### A. Robots is checked BEFORE any content request — and reported, not just acted on
A disallowed URL costs zero content requests; enforcement that still fetches is
not enforcement. Every result row carries `robots_decision` and the batch
carries `robots_blocked_count`, so a caller measuring a recall drop can
**attribute** it to robots instead of reading it as a quality problem.
*Risk accepted:* none material.

### B. Robots failure FAILS CLOSED
A `robots.txt` that errors is not permission. Failing open would silently
restore the behaviour being fixed.
*Risk accepted:* transient robots outages cost us content. Correct trade.

### C. ⚠️ Citation wrappers are resolved BEFORE the gate — the call to challenge
Vertex grounding hands out `vertexaisearch.cloud.google.com/grounding-api-redirect/…`
wrappers. Google disallows that path (reasonably — it stops bots mining their
redirector). Gating the wrapper rejected **5/5** real hits in ~100ms each,
whatever the publisher's own policy said.

**My reasoning:** robots governs crawling a site's *content*. A redirector is
not content, and these links reached us because we called an **authorised API**
that handed them over as citations — we did not discover them by crawling.
Resolution reads only the `Location` header (`follow_redirects=False`), no body.

**What is unchanged:** the DESTINATION is robots-gated before a single byte of
its body is read; a disallowed publisher yields nothing. The exception is a
**narrow named allowlist** (`vertexaisearch.cloud.google.com`, `google.com`,
`duckduckgo.com`), with a test pinning that ordinary hosts are still gated
before any request, so it cannot widen by accident.

**This is the call most worth a second opinion.** If you or Technical Review
read it differently, it reverts to a one-line allowlist change.

### D. Robots re-checked after a cross-origin redirect
Checking only the requested URL is a false guarantee once redirects are in play.
If the final origin differs, we re-gate on where we landed and **discard the
body** if disallowed. The request is already spent; the content is what robots
governs, and we do not use it.

### E. filler_d's un-gated fetch — found, escalated, NOT silently fixed
`filler_d` fetched arbitrary third-party URLs with a **spoofed Chrome-120 UA and
zero robots consultation**, live, on the strongest retrieval arm (~0.67).
`payer_context.py` and `corpus_search_strategy_d.py` both *do* check; filler_d
was the outlier.

**I did not quietly gate it.** Gating will likely *cost recall*, and
compliance-vs-recall on our best arm is Ananth's call, not an engineering trade
to make in a commit. Escalated to Retriever + Eval with a baseline-first
sequence. Retriever has since migrated onto `/fetch/batch` (`494fbef`, 75 tests).

### F. Politeness bounds
Crawl concurrency is capped at 6 (waves) / 8 (batch), matching the httpx
connection limit — we never open more sockets to a host than that, however wide
a caller fans out. We are a guest on someone's site.

---

## 3. Judgment calls — LOGGING / AUDITABILITY

### G. `source_fetch_attempts` — history, because latest-state erases its own evidence
`discovered_sources` keeps only the newest verdict, so a bug that corrupts the
verdict also destroys the proof. `[403, 200, 200]` and `[403, 403, 403]` collapse
to the same column depending only on when you look. Append-only, one row per
attempt, with `robots_decision` and `content_hash_before/after`.

**DDL divergence flagged, not silently resolved:** the DB seat's prose asked for
monthly partitions but their DDL declared `PRIMARY KEY (attempt_id)` alone, which
Postgres cannot partition on `attempted_at`. Built the valid version
(unpartitioned + index) and raised it back rather than quietly diverging.

### H. Honest status vocabulary
Every failure names its real condition rather than a vague one:
`robots_disallowed`, `skipped_budget`, `not_pdf`, `error:UnresolvedRedirect`,
`http_{code}`, `timeout`. A vague `extract_failed` is what disguised the Brotli
bug as a parser problem for hours. Every input URL gets a row — misses are never
silent.

### I. `curated_by` is REQUIRED in the curator UI
"Who called this canonical" is the audit question those columns exist to answer,
so the UI refuses to write rather than record an anonymous decision.

---

## 4. Judgment calls — PROCESS / SCOPE

### J. Branch discipline in a shared checkout
`mobius-rag`'s shared checkout sits on `retriever-answer-engine`, **56 commits
ahead of main**, almost all other agents' in-flight work. Moving my two commits
to `main` was done by **cherry-pick into a temporary worktree** so the shared
checkout's branch never moved. Two conflicts were resolved by *narrowing*:
- the audit-trail test hunk carried another agent's provenance test whose code is
  not on main — dropped it rather than import a test that would fail;
- the curator route's `main.py` conflict spanned ~1900 lines of unrelated
  divergence — applied the 24-line route by hand instead.

### K. Built ahead of sign-off — but not on contested ground
Ananth authorised build-before-signoff. I built the audit trail, exhaustive
capture, `/fetch/batch` and the curator UI. I did **not** build
`freshness_worker.py`, because C3 is a live dispute with Maintaining whose
charter claims "freshness" by name — building it would have settled a contested
boundary in my own favour while the other party was offline.

### L. I edited `ownership.yaml` myself
Normally Technical Review's file. Ananth instructed it directly. Both rows carry
his verbatim instruction in `notes`, `ratified:` was left untouched, and both
Technical Review and Payor Platform were told to **verify rather than trust**.

### M. The delivery failure I caused
Four of five ledger files and `ownership.yaml` sat **untracked** for a day. Agents
in the main checkout could read them; **UX runs in a worktree** and could not —
their ask file did not exist from where they stood. I read that as
non-response for a full day. It was my failure to deliver, not their silence.
Fixed in `cd03b88`. **Check `git ls-files`, not `ls`.**

---

## 5. Still open

| Item | Owner |
|---|---|
| `min-instances=1` on the scraper (~12s cold start distorts Eval latency) | **Ananth** — spend call |
| Hardcoded dev URL at `filler_d.py:496` | Retriever |
| C3 freshness boundary | Maintaining (silent) |
| Q1 representation, Q3 structure | Technical Review |
| Curator UI ownership | UX (never ruled; Ananth assigned to me) |
| §4 acceptance tests 2 & 3 | Fact Store |
| chat rebuild to pick up `274bca2` + `112d1d1` | Chat |
