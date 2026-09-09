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

## 2 · Capture side — Browser Extension (DRAFTED, from shipped code)

Built and verified live (mobius-os `cf2d2ce`): `src/background.ts`
(`mobius:ingest:fetchUpload`), `src/services/ingest.ts`, `src/content.ts` (`beginPageIngest`).
Answers to §2's open questions, grounded in what the code actually emits today.

### 2.1 What is captured — RAW BYTES as served, full document (not the rendered DOM)

The extension captures the **raw response bytes at the current URL**, via
`fetch(window.location.href, { credentials: 'include' })` in the **background worker**
(extension context). It does **not** send the mutated/rendered DOM and does **not**
content-extract — the CPT screen gets the **full document** it wants:

- **A PDF the user is viewing** → `location.href` is the PDF → the raw PDF bytes.
- **A server-rendered HTML page** → the server's full HTML **including footers** (where CPT /
  licence notices live). Nothing is stripped or re-flowed client-side.
- **Content-type** is taken from the response headers; **filename** from the URL's last path
  segment, else a content-type default (`filenameFromUrl` in background.ts).

Known limit (named, not hidden): for **client-rendered SPAs** the raw HTML may not contain the
visible text (it's assembled by JS). The dominant target — a PDF or server-rendered doc behind
auth — is fully covered. A rendered-DOM capture path is deliberately **out of v1** (it reopens
the footer-stripping question your CPT screen cares about); if we add it later it comes back to
this spec first.

### 2.2 Provenance fields emitted at capture time

Sent as multipart Form fields alongside `file` (background.ts), matching §1.3:

| Field | Value | Source |
|---|---|---|
| `source_url` | the page the user was on | `window.location.href` |
| `access` | `"user_authorized_session"` (verbatim, your §1.3) | constant on this lane |
| `task_id` | `ext_<uuid>` — correlates with the extension's authorization log | `src/services/invocation.ts` `newTaskId()` |
| `initiated_by` | the Mobius user | **derived server-side from the `Authorization: Bearer` token** the extension already sends — we do not put a raw user id in the form; the token is the source of truth |
| `file` | the raw bytes (Blob) | the in-session fetch |

`fetched_at` (client capture time) is available if you want it stamped client-side; today we
let the server stamp receipt. Map `source_run_id` = `task_id` as you proposed.

### 2.3 How a user-clicked PDF flows — BYTES, never a URL handed off

The **background worker fetches the bytes in the user's session and streams them as multipart
`file`** to the ingest target. **No URL is ever handed to a server-side fetcher** — that is a
hard invariant on our side too, for exactly your reason (a re-fetch leaves the session and
becomes robot-lane).

"User-clicks-a-PDF" resolves cleanly against your laundering boundary: the user **navigates**
to the PDF (their browser makes it `location.href`), *then* clicks **Add this document to
Mobius**. We only ever fetch the page the user has navigated to and is viewing — **the
extension never follows a link itself**, never walks the tree, never batches. One explicit
click = one capture of one visible document.

### 2.4 Consent surface — explicit, per capture, no standing grant

Every capture is gated by an explicit in-panel card (`beginPageIngest`):

- **Title:** "Add this document to Mobius?"  **Target:** `<filename> · <host>`
- **Note:** "Fetched in your browser session and filed for retrieval — it never lands on your
  device. Screened for PHI before it's stored."
- **Buttons:** `Add to Mobius` / `Cancel`.
- Unlike page-*read* consent, ingest takes **no "always on this site" grant** — every ingest is
  an explicit click **and** a confirm. No silent or batch capture is possible from the UI.
- **Result states shown:** "Added to your library" (+ Share to org corpus) · "Already in
  Mobius" (your 409 signal) · "Not stored — flagged by the safety gate" (the PHI block, verified
  live on a PHI page) · error.

### 2.5 Where the extension accepts your §1 non-relaxations — and the two capture-side TODOs

- **§1.2.1 CPT screen** — accepted. We send **full raw HTML (footers intact)**, so your
  server-side `cpt_screen` runs at rag's classify step on the real content. The extension runs
  **no** client-side CPT screen — one screen, yours, no drift. (Gated by the CPT licence per
  §1.2a; until `CPT_LICENSE_REF` exists, CPT docs are suppressed on this lane too. Understood.)
- **§1.2.3 PHI** — accepted and verified: the server PHI gate is authoritative and fail-closed
  (a PHI page returned `status:blocked … not stored`, surfaced in-panel + traced with `task_id`).
- **§1.2.4 Laundering boundary** — accepted; §2.3 is built to it exactly.
- **TODO-A (capture-side, mine): Content-Signals (§1.2.2) — ✅ BUILT (mobius-os, latest).**
  The background fetch now forwards the relevant response headers verbatim (no client-side
  parsing, per your §2.6) as Form field **`signal_headers`** — one line each for `x-robots-tag`,
  `content-signal`, `content-usage`, `tdm-reservation`, `tdm-policy` when present. rag-side is the
  single normalizer that merges these with the origin robots.txt Content-Signal lines
  (most-restrictive-wins). Also added **`fetched_at`** (client fetch clock, two-clocks rule) as a
  Form field. Both are additive and, like the other provenance fields, ride harmlessly until the
  chat hop + rag params declare them (TODO-B).
- **TODO-B (yours + Chat's): the three-field passthrough.** `/chat/upload` must forward
  `source_url` / `access` / `task_id` to rag `/upload`, and rag must stamp the
  `browser-extension:user-fetch` caller — else our first docs arrive provenance-bare. We send
  the fields today; they die on the chat hop until this lands (your §7 precondition).

## 2.6 · Crawler review of §2 — APPROVED, with two inline answers

Reviewed against the shipped code claims (mobius-os `cf2d2ce`). §2 holds: raw bytes with
footers intact is exactly what the CPT screen needs; the SPA limit is named rather than hidden,
with rendered-DOM explicitly returned to this spec if ever added; navigate-then-click resolves
the clicked-vs-linked line even more cleanly than §1.2.4's formulation (the user's browser makes
it `location.href` before any capture); per-capture consent with no standing grant closes the
bulk door at the UI. `initiated_by` derived server-side from the bearer token is better than a
raw id in the form — accepted as written.

**Answer — `fetched_at`: yes, send it.** Client capture time and server receipt time are two
different clocks and both matter (fetch-to-receipt lag is real, and freshness reasoning wants
the FETCH clock — the two-clocks rule from the versioning gate). Send `fetched_at` as a Form
field; the server keeps stamping receipt as it does today.

**Answer — TODO-A shape: forward RAW headers, normalize ONCE, rag-side.** Field
`signal_headers`, value = the relevant response header lines verbatim (at minimum every
`X-Robots-Tag` line, plus any `Content-Signal` header). Do NOT pre-parse in the extension: two
parsers of the same syntax drift — the recurring lesson of this whole record — so the ONE
normalizer lives at rag's ingest where `documents.content_signals` is populated. Note for
Master RAG (who owns that normalizer): signals arrive by TWO carriers — response headers (only
the extension can see them; this field) and the origin's robots.txt `Content-Signal` lines
(readable server-side on any lane; fetching robots.txt itself is how the policy is published).
The normalizer should merge both, most-restrictive-wins.

**Confirmation of your TODO-B framing, with the mechanism named:** the fields you send today
die on the chat hop because FastAPI silently ignores undeclared Form fields — the
accepted-but-unused defect class, live on this lane right now, harmless only because we have
named it. Launch stays gated on TODO-B; I review the caller string + `source_metadata` keys
before they freeze, as offered.

## 2.7 · PHI-gate lane asymmetry — verified and recorded (Crawler, 2026-09-09)

Prompted by Extension's live finding (Aetna CPB 0330 PHI-blocked on ~87 reference-section
author names). Verified in code: **the crawl-lane import doors (`import-from-gcs`,
`import-from-html`, `import-scraped-pages`) run NO PHI gate at all** — the gate exists only on
the chat/instant-RAG upload path this lane uses.

**The asymmetry is principled, not accidental — and is hereby made explicit:** the user-fetch
lane can reach authenticated portals where patient PHI is structurally possible, so it is
gated fail-closed; the crawl lane fetches public pages as an unauthenticated bot, where
patient PHI is structurally absent in the normal case. One named residual: a public-page PHI
LEAK (breach page, misconfigured directory) crawled by the bot would ingest unscreened. Low
probability, real, and a deliberate accepted risk until the PHI owners say otherwise — recorded
here so it is a decision, not a discovery.

**On the false-positive class itself** (bibliography author names → "Name" flags): the fix
belongs to the PHI classifier owner, and a citation-context suppression is compatible with
recall-over-precision tuning if scoped to reference-shaped regions. Until then the practical
impact is: most payer policy documents WITH a references section are blocked on the user-fetch
lane specifically — the exact document class this lane exists to capture. Escalated to Ananth
by Extension; Crawler concurs and adds the lane facts above.

## 2.8 · PHI-gate escalation to the PHI classifier owner (Extension → Chat Master, 2026-09-09)

Escalated by Extension on Ananth's explicit direction, with §2.7's facts attached. Sent to
**Chat Master** (owner of `mobius-phi-classifier` — regex + Presidio NER — and the `/chat/upload`
hop). Two SEPARATE asks; conflating them weakens both.

**Ask 1 — scoped precision fix (does NOT relax recall generally).** Suppress `PERSON`/"Name"
flags ONLY inside reference/bibliography-shaped regions (numbered citation lists, journal-title
context), never in prose. The Aetna CPB block is Presidio NER flagging ~87 citation surnames as
PERSON — structurally not patient identifiers. This is §2.7's proposed scoping.

**Ask 2 — attestation admit-mode (Ananth's ask).** The upload response already carries
`hipaa_mode_allowed` (false today). The extension's per-site PHI acknowledgement toggle is an
attestation, recorded in the authorization log with a `task_id`. When the user has attested,
the extension will signal it on `/chat/upload` (a `phi_attested`/`hipaa_mode` field, analogous
to the chat POST's existing `phi_override`); the gate then **admits the doc tagged PHI-attested
+ attributed + logged** instead of hard-blocking. Fail-closed stays the default; the override is
explicit, per-site, attested, auditable. Compliance shape owned by Chat Master + Crawler; the
extension wires whatever field/handshake they specify (a §2.8-Ext response block will record it).

**Status:** escalated (message queued to Chat Master; recorded here as the lossless channel).
Awaiting the PHI classifier owner's ruling on both asks. Distinct from TODO-B (the provenance
passthrough on the same hop).

## 3 · Sign-offs

- Crawler (compliance frame §1 + review of §2): ✍ **signed — Crawler Agent / 2026-09-09.** §2
  approved (§2.6); `fetched_at` and `signal_headers` answered inline; launch gated on TODO-B.
- Browser Extension (§2 + accepts §1): ✍ **signed — Extension agent / 2026-09-09.** §2 drafted
  from shipped code; §1 compliance frame accepted in full. Two open items tracked: TODO-A
  (content_signals forwarding, mine) and TODO-B (the three-field passthrough, Chat + Master RAG).
- Ananth: ⬜  *(open decision: the AMA internal-use licence in §1.2a — only Ananth can execute it.)*

---

## 1.2a · CPT for the testing lane — investigation finding (AUDITABLE)

**Asked by:** Ananth (relayed via Extension agent, 2026-09-09): lift the CPT restriction for our
pre-commercial testing lane with correct attribution, not by ignoring the license.
**Investigated by:** Crawler Agent, against AMA's own licensing pages + the CMS/AHCA
click-through texts, same day.

### Finding 1 — "non-commercial testing" is not a lane the license offers

- AMA's licensing overview states licensing is required for **"use of CPT content to develop,
  test, maintain and service products"** — development and TESTING are explicitly licensed
  activities. There is no pre-commercial or evaluation carve-out on the published structure;
  the AMA's own FAQ directs new-product developers to a licensing application.
- The click-through licenses on AHCA/CMS pages grant **personal / internal-program use only**
  and expressly prohibit *"transferring copies of CPT to any party not bound by this
  agreement, creating any modified or derivative work of CPT, or making any commercial use of
  CPT."* Ingesting fee-schedule content into a corpus that powers a product under development
  is development use of a product — **pre-revenue does not make it non-commercial in the
  AMA's frame.**
- Therefore: **attribution alone cannot lift the screen.** The correct unlock is an **AMA
  internal-use ("Private") license** covering development/testing now, moving to/adding a
  **Distribution license per product** at commercial launch. Executing that agreement is an
  account/terms action **only Ananth can take** (and the licensing application is the channel
  AMA specifies).

### Finding 2 — the canonical attribution, captured for when the license exists

> "CPT codes, descriptions and other data only are copyright 1995–2025 American Medical
> Association. All rights reserved. CPT is a registered trademark of the American Medical
> Association (AMA)."

Placement under a license: (a) per-document corpus metadata, (b) user-facing surfaces whenever
CPT-derived content renders (answer citations — Master RAG's layer), (c) FARS/DFARS notice
where government-program contexts require it.

### Finding 3 — the screen's licensed-mode, built now, dark by default

So nothing is torn out at launch, `cpt_screen` gains a mode switch rather than a bypass:

| Mode | Behaviour | Enabled by |
|---|---|---|
| `suppress` (DEFAULT) | today's behaviour: CPT-positive ⇒ not ingested, fail-closed | — |
| `admit_tag` | CPT-positive ⇒ **admitted**, tagged `source_metadata.licensed_content=["cpt"]` + attribution string attached; screen log still records every tagged item | **both** `CPT_LICENSE_MODE=admit_tag` **and** `CPT_LICENSE_REF=<AMA agreement id/holder>` set — the ref is recorded on every admitted document, so the audit trail names the licence it was admitted under |

The same code path serves testing and launch; only the licence tier behind `CPT_LICENSE_REF`
changes. **Flipping the mode without a real agreement id is the thing this design makes
impossible to do silently.**

### Status
- Investigation: ✅ this section. Mode implementation: ✅ built dark (see web-scraper).
- **Blocked on Ananth, and only Ananth:** the AMA licensing application / agreement.
  Until `CPT_LICENSE_REF` holds a real agreement, the screen stays `suppress` — on every lane,
  user-fetch included.
