# User-initiated page fetch — Crawler ⇄ Browser Extension pairing spec

**Status: DRAFT — Crawler's half committed first; Browser Extension owns §2 (capture side).**
**From:** Crawler Agent (owner: web-scraper + fleet robots/ToU compliance) · 2026-09-09
**Directive:** Ananth — pair on user-initiated web page fetch, where the user is actually on a
webpage and that context allows more freedom than a robot.

## 1 · The compliance frame (Crawler-owned, ratify before building)

### 1.1 What user-present legitimately relaxes

| Robot lane (web-scraper) | User lane (extension) | Why |
|---|---|---|
| robots.txt enforced pre-fetch | **no robots gate** | robots governs crawlers; a human on the page in their own browser is not one, and the extension acting on that page is the user's own access |
| `MobiusBot/1.0` honest UA | user's real browser | it genuinely IS their browser |
| no cookies / no auth | **user's session ok** | login-gated or paywalled content the user legitimately sees is their access, captured on their explicit action |
| 1.5s/host politeness, maxScale=1 | human pacing | the human IS the rate limit |

### 1.2 What does NOT relax — fetch path never changes content rules

1. **Licences attach to the data, not the fetch.** Live example: the AMA CPT End-User License
   permits personal viewing and prohibits transferring copies into a commercial corpus. A user
   VIEWING a fee schedule is licensed; our INGESTING it is not. The CPT screen
   (`web-scraper/app/services/cpt_screen.py` — fail-closed, fixture-tested against
   `docs/CPT_SCREEN_PREDICATE.md`) runs on this lane's ingest step too. One screen, not two:
   the extension calls the crawler's, so the predicate cannot drift.
2. **Content-Signals govern use, not access.** `ai-train=no` (AHCA serves it) rides into the
   corpus with the document; populate `documents.content_signals` exactly as the crawl lane does.
3. **PHI gates ingestion.** A user on a portal can capture PHI a crawler never sees. The
   extension's authorization log + PHI classifier sit IN FRONT of ingest (Instant RAG P0
   precedent: PHI GATES ingestion, fail-closed).
4. **The laundering boundary.** User-initiated = the page the user is on, per explicit action,
   human-paced. It never becomes tree-walking through the user's session:
   - a PDF the user CLICKS = user-initiated; a PDF merely LINKED = not;
   - no link-following of any kind on this lane;
   - anything beyond the visible page goes to the robot lane (robots + politeness).
   Holding this line is what makes everything in §1.1 defensible.

### 1.3 Provenance (verdict-provenance is this month's recurring lesson)

- New classification caller, minted once: **`browser-extension:user-fetch`** — these documents
  stay distinguishable from crawled ones forever (`payor_ingest_classification.caller`,
  `request_shape`, `initiated_by` already exist).
- Ingest doors already carry what's needed: `import-from-html` / `import-from-gcs` accept
  `source_run_id` + `source_page_url`. For this lane: `source_page_url` = the page the user was
  on; `source_run_id` = extension task/session id (correlates with the extension's
  authorization log's `task_id`).
- Dedup is free: content-identity 409s make a user re-fetch of a held page `already_held`.

## 2 · Capture side — BROWSER EXTENSION TO DRAFT

Open questions from Crawler:
- What is captured: rendered DOM, raw HTML, or both? (Main-content extraction differs; the CPT
  screen wants FULL html — licence notices live in footers that content extraction strips.)
- User/task provenance fields available at capture time?
- How does a user-clicked PDF flow — bytes through the extension, or URL handed to a fetcher?
  (If a URL is handed to a server-side fetcher, that fetch leaves the user's session and
  becomes robot-lane — needs care: prefer capturing the bytes the user's browser already has.)
- Consent surface: what does the user see/approve per capture?

## 3 · Sign-offs

- Crawler (compliance frame §1): ✍ DRAFTED, self-signed for the frame
- Browser Extension (§2 + accepts §1): ⬜
- Ananth: ⬜
