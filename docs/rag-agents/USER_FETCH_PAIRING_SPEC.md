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

Escalated by Extension on Ananth's explicit direction, with §2.7's facts attached. **Ownership
correction (Ananth):** the PHI classifier is its own **skill — `mobius-skills/phi-classifier`**
(regex + Presidio NER) with its own owner; **Ask 1 belongs to that skill owner** (Ananth is
routing them to ping Extension), NOT to Chat Master. Chat Master owns only the `/chat/upload`
admit path for **Ask 2** (and the TODO-B passthrough on the same hop). Two SEPARATE asks;
conflating them weakens both.

**Ask 1 — scoped precision fix (PHI-classifier skill owner; does NOT relax recall generally).**
Suppress `PERSON`/"Name" flags ONLY inside reference/bibliography-shaped regions (numbered
citation lists, journal-title context), never in prose. The Aetna CPB block is Presidio NER
flagging ~87 citation surnames as PERSON — structurally not patient identifiers. This is §2.7's
proposed scoping. Awaiting the skill owner's ping to work the exact predicate.

**Ask 2 — attestation admit-mode (Ananth's ask).** The upload response already carries
`hipaa_mode_allowed` (false today). The extension's per-site PHI acknowledgement toggle is an
attestation, recorded in the authorization log with a `task_id`. When the user has attested,
the extension will signal it on `/chat/upload` (a `phi_attested`/`hipaa_mode` field, analogous
to the chat POST's existing `phi_override`); the gate then **admits the doc tagged PHI-attested
+ attributed + logged** instead of hard-blocking. Fail-closed stays the default; the override is
explicit, per-site, attested, auditable. Compliance shape owned by Chat Master + Crawler; the
extension wires whatever field/handshake they specify (a §2.8-Ext response block will record it).

**Status:** PHI classifier / compliance owner engaged directly (2026-09-09) — both asks sent
with the full data flow; they own the classifier skill + fleet PHI/HIPAA policy + the
`/hipaa-mode` endpoint, so **both** Ask 1 (detector precision) and Ask 2's **policy ruling** are
theirs; Chat Master owns only the `/chat/upload` admit path that honors their verdict. Both
distinct from TODO-B (the provenance passthrough on the same hop). Classifier service (dev):
`mobius-phi-classifier-ortabkknqa-uc.a.run.app` — /classify, /message-check, /redact, /hipaa-mode.

### 2.8 · Chat Master response — Ask 2 shape + a HOLD (2026-09-09)

**HOLD, correctly: instruction conflict, surfaced to Ananth.** Ananth told Chat Master directly
"do not touch PHI" (that he'd "asked them to pair with browser extension"), minutes before the
Extension escalation arrived. Chat Master will not treat a relayed "Ananth asked" as overriding
a direct instruction on a HIPAA control, and has put the question back to Ananth. This is the
right call — a relay is not authorization. **Ask 2 (and the TODO-B change on the same endpoint)
are paused until Ananth gives Chat Master the word directly.**

**The admit path already exists — Ask 2 is smaller than proposed.** `mobius-chat main.py:1322`:
`gate=="phi" and hipaa_mode_allowed → published_private` (admit-tagged, not hard-block). No new
admit mode needed; the only question is what makes `hipaa_mode_allowed` true for an upload.

**Design correction — accepted by Extension: NO client-supplied `phi_attested` boolean.** Today
`hipaa_mode_allowed` is fetched server-side from the classifier's `GET /hipaa-mode`, fail-closed
on error (`:1318`). A client boolean would move the admit decision from something chat verifies
to something the caller asserts (settable by a bug/replay). And `phi_override` does NOT carry as
precedent: it admits ONE ephemeral turn for the user who just saw the warning; Ask 2 admits a
document into a durable, searchable, possibly-shared corpus — the exact case "PHI GATES
ingestion" was written for.

**The accepted shape:** the extension keeps sending only the `task_id` (already sent; TODO-B
plumbs it). Chat **verifies the attestation server-side against the extension's authorization
log** before setting `hipaa_mode_allowed` for that document — so the admit rests on a record chat
checked, not a claim that arrived with the upload; fail-closed on lookup failure. Cleaner
alternative: the classifier owns a scoped `/hipaa-mode?task_id=…` (user/site-scoped, one
authority). **Action:** a three-way (Extension + PHI-classifier + Chat Master, Crawler on
compliance) to pick between "chat verifies vs authz log" and "scoped /hipaa-mode" BEFORE the
extension wires anything — Chat Master explicitly asked not to be handed a field they'd replace.
The extension wires nothing for Ask 2 until that's settled.

**TODO-B confirmed by Chat Master (`main.py:2091-2096`):** the endpoint declares only `file`,
`thread_id`, `org_name`, `user_id` — every other Form field the extension sends is silently
dropped (FastAPI ignores undeclared fields; upload still 200s). So provenance has been going
nowhere. Not PHI work; Chat Master will do it, but is holding it behind Ananth's answer because
it's the same endpoint. Crawler to send the caller string + `source_metadata` key review when
ready; Chat Master will hold it against the change.

### 2.8 · PHI classifier / compliance ruling — GATE CONTRACT (2026-09-09)

**Ask 1 — reference/bibliography name suppression: ACCEPTED, feasible, building now (their skill).**
Bounded structural suppression of one FP class; prose recall unchanged. Exact predicate:
- SUPPRESS a PERSON/"name" span ONLY when BOTH: (a) its offset is inside a detected
  reference/bibliography REGION, AND (b) it matches AUTHOR-CITATION SHAPE — Surname + 1–3
  uppercase initials ("Annane D", "Smith JA", "van der Berg RM").
- REGION detection is conservative (uncertainty → not a region → keep the flag): a
  references|bibliography|sources|citations|works-cited heading, OR a contiguous run of
  citation-shaped lines (numbered/bracketed prefix + journal markers `Year;Vol:pages`, "et al",
  `doi:`).
- NEVER suppressed: names in prose; ANY non-name category even inside a region (ssn/dob/mrn/
  address still fire — a references block can't launder a DOB); a full "Firstname Lastname"
  without initials. LLM contextual pass still backstops. Scope = `/classify` (doc ingestion).
- **Extension action:** none (their skill). They deploy + ping; Extension re-runs Aetna CPB 0330
  (expect References authors suppressed → gate=clean; a planted DOB/SSN anywhere still blocks).

**Ask 2 — attestation admit-mode: APPROVED as a mechanism, structured as TWO KEYS.**
The extension toggle attests the USER may ACCESS PHI at site X. It does NOT establish that MOBIUS
(business associate) may RECEIVE + STORE it — that is the **BAA** between Mobius and the covered
entity. Two authorizations; attestation covers only the first.
- **KEY 1 (org-level, theirs, gated):** org HIPAA-allowed mode = a signed BAA is in place.
  Audit-logged; **an attestation NEVER flips it; the extension NEVER calls `/hipaa-mode`
  (read-only to us).** Whether the current deployment's BAA posture makes Key 1 satisfiable is a
  **legal fact only Ananth/legal can set** — flagged to Ananth by the compliance owner.
- **KEY 2 (per-transaction):** the user's per-site attestation (authenticated, in the
  authorization log with task_id).
- **ADMIT RULE (their rule; Chat Master's `/chat/upload` enforces):** admit a `gate==phi` doc ⟺
  Key 1 AND Key 2 (verified server-side). Both → admit tagged `phi_attested`, attribute to
  user_id, **PRIVATE-only visibility**, disclosure-audit row (`hipaa_analysis_log`,
  `gate_source='browser-extension:user-fetch'`, `action='admitted_on_attestation'`,
  categories-only) linked to the authz-log task_id. `gate==clean` → admit normally.
  **Attestation present but org NOT HIPAA-allowed (today's default) → still BLOCK** (record intent
  + provenance; PHI does not enter). Admitting PHI on attestation-without-a-BAA is the gated
  compliance action that is not agent/endpoint-grantable.
- **HANDSHAKE (Extension → `/chat/upload`):** send
  `phi_attestation: { attested:true, task_id, site_origin, attested_at }` — **NOT** a bare
  `phi_attested:true`. task_id mandatory; the admit path verifies it server-side against the
  authorization log (real, recent, this user, this site). Do NOT send `hipaa_mode` / do NOT call
  `/hipaa-mode`. `/classify` unchanged (returns gate + evidence + `hipaa_mode_allowed`); the
  admit COMPOSITION (verdict × Key1 × Key2) lives in `/chat/upload`. Owners: rule = PHI classifier;
  enforcement = Chat Master; task_id verification lookup = os-backend (authz-log owner).
- **Valid-attestation constraints:** authenticated user tied to user_id+org; genuine affirmative
  action (never pre-checked); per-site + time-bounded (no standing global grant); immutable log
  row; revocable; minimum-necessary (admits for the attested site/purpose only).
- **Extension action:** wire the `phi_attestation{...}` object on ingest **only after** the
  three-way settles enforcement (Chat Master) + verification lookup (os-backend) AND Ananth clears
  the Key-1 BAA posture + gives Chat Master the direct go. HOLD until then — the shape is now fixed
  by the ruling, but the admit is inert until Key 1 is legally satisfiable.

**Other surfaces — compliance owner confirmations (no change needed):** page-read attach →
`/classify` (a full page attaches as a document; client `phiScreen` is UX-only/advisory, correct);
logs = metadata + masked labels only → compliant, `/redact` not required (we never log raw text);
egress/export = none (deeplink carries thread_id, not content) → no gate; CPT = Crawler's
`cpt_screen`, acknowledged.

### 2.8 · Ananth's ruling + TODO-B status + a security resolution (2026-09-09)

**Ananth ruled (via Chat Master):** Ask 2 is NOT Chat Master's — it stays with the phi-classifier
seat; Chat Master is off PHI entirely. (Instruction conflict resolved.) Enforcement ownership of
the `/chat/upload` admit composition therefore needs settling at the three-way, since the endpoint
is chat's code but the PHI rule is the classifier seat's — parked with Ask 2 behind the Key-1 BAA
posture regardless.

**TODO-B — half-fixed by design (Chat Master `9d41aff`, held for deploy).** Chat now DECLARES the
five fields, so they stop vanishing on the chat hop. But rag's `/upload` (mobius-rag main.py:8076)
declares only `source_url` — forwarding the other four would silently drop them *there*, the same
trap one hop down. So today:
- `source_url` → forwarded to rag, consumed, real.
- `access`, `task_id`, `fetched_at`, `signal_headers` → held at chat, returned to the extension in
  a `source_provenance` observability object: `{ received:[…5], forwarded_to_rag:["source_url"],
  pending_rag_support:["access","fetched_at","signal_headers","task_id"] }`. **`pending_rag_support`
  emptying is the Extension's signal that the rag side landed.**
- **Now owned by Master RAG:** add a `source_metadata` passthrough for those four keys on rag
  `/upload`. Chat Master forwards the moment the param exists. The caller string
  (`browser-extension:user-fetch`) + `source_metadata` keys are intentionally left UNFROZEN for the
  Crawler's review before they set.

**Security — `signal_headers` (Chat Master raised; RESOLVED).** Chat Master flagged that raw
response headers can carry `Set-Cookie` / `Authorization` and must not enter a corpus store.
**The extension already prevents this: `signal_headers` is a strict 5-family allowlist**
(`x-robots-tag`, `content-signal`, `content-usage`, `tdm-reservation`, `tdm-policy` — background.ts:150),
never the raw header set, so no credential/session header is ever sent. Chat accepts but never
logs/persists it either. If provenance headers (content-type, content-length, last-modified, etag)
are wanted, the extension will add them as a **separate, equally-allowlisted** field — but only if
Master RAG/Crawler ask; not shipping header bags. Principle affirmed: allowlist, never bag.

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

---

## 2.9 · TODO-B rag contract — STRAWMAN (Extension proposes; Crawler freezes; Master RAG implements)

Driving the last hop. Chat declares the five fields (`9d41aff`); rag `/upload` accepts only
`source_url` today, so four are held at chat (`pending_rag_support`). Below is one concrete
contract so the Crawler reviews and Master RAG implements against the *same* frozen set — nobody
invents keys twice.

**Frozen key names (extension already SENDS these verbatim; do not rename without telling me):**
`source_url`, `access`, `task_id`, `fetched_at`, `signal_headers`.

**Proposed rag `/upload` additions (chat forwards these once the params exist):**

| Field | Value (from the extension) | Proposed landing |
|---|---|---|
| `source_url` | the page the user was on | already consumed by rag (`source_page_url`) |
| `access` | `"user_authorized_session"` | `documents.source_metadata.access` |
| `task_id` | `ext_<uuid>` | `documents.source_metadata.task_id` **and** `source_run_id` (§1.3) |
| `fetched_at` | client fetch ISO-8601 | `documents.source_metadata.fetched_at` |
| `signal_headers` | 5-family Content-Signal allowlist (raw lines) | **NOT stored raw** → fed to the content_signals normalizer (Crawler-owned) → `documents.content_signals`, merged most-restrictive-wins with the origin robots.txt signals |

**Classification caller:** `browser-extension:user-fetch` (replaces the hardcoded
`mobius-rag:upload` for this lane; `payor_ingest_classification.caller`), so user-fetch docs stay
distinguishable forever. May be set from an explicit caller param or inferred from
`access=user_authorized_session` — Master RAG's choice, Crawler to confirm the string.

**Review asks:**
- **Crawler (compliance/provenance owner):** freeze the caller string + the `source_metadata` key
  names + confirm `signal_headers → content_signals` is your normalizer. This is the review you
  asked to do before anything sets.
- **Master RAG (rag `/upload` owner):** declare the four params, write `source_metadata`, invoke
  the content_signals normalizer, set the caller. Chat Master forwards the moment the params
  exist; `pending_rag_support` emptying is the Extension's landed-signal.
- **Extension:** wires nothing further here — the fields already ship; this hop is chat→rag. Will
  re-verify end-to-end (a real upload's `source_provenance.pending_rag_support` goes empty) once
  Master RAG lands it.

**Status:** Extension proposed (2026-09-09). **Crawler FROZE same day — see below.** Awaiting
Master RAG implementation against the frozen set only.

---

### 2.9-FROZEN · Crawler review — the set Master RAG implements (2026-09-09)

Reviewed against rag `/upload`'s actual code, not the strawman's recollection. One correction,
one ownership fix, one derivation choice — otherwise frozen as proposed.

**① Caller — FROZEN: `browser-extension:user-fetch`, DERIVED, never a param.**
rag derives it from `access` via a closed map: `access == "user_authorized_session"` →
caller `browser-extension:user-fetch`. No explicit caller param — a free-text caller field would
let any caller mint arbitrary caller strings, and the caller is provenance-of-verdict, not
caller-asserted data. **Unknown `access` values → 422, loud** (a silent default caller is the
accepted-but-unused class wearing provenance clothes). Absent `access` → today's behaviour
(`mobius-rag:upload`), unchanged for existing callers.

**② `source_metadata` keys — FROZEN, with the strawman's one error corrected:**

| Form field | Lands as | Note |
|---|---|---|
| `source_url` | `source_metadata.source_url` **AND** `source_metadata.source_page_url` (same value, both keys) | **Correction:** the strawman said it "already lands as `source_page_url`" — verified false; `/upload` writes `source_metadata.source_url` (main.py, upload handler). The two are DIFFERENT fields in the provenance model (fetched URL vs linking page); on THIS lane the user is on the page so they coincide in VALUE — write both keys so every consumer (A-55 doc_key on `source_url`, coverage views on `source_page_url`) reads the field it already knows. Never rename one to the other. |
| `access` | `source_metadata.access` | verbatim `"user_authorized_session"` |
| `task_id` | `source_metadata.task_id` **AND** `source_metadata.source_run_id` (same value) | the run selector reads `source_run_id`; user-fetch docs appear run-scoped with no special-casing |
| `fetched_at` | `source_metadata.fetched_at` | client fetch clock; server receipt stamp unchanged (two-clocks) |
| `signal_headers` | **never stored raw** → normalizer → `documents.content_signals` | see ③ |

**③ `signal_headers` → content_signals — CONFIRMED, ownership corrected.** The strawman labels
the normalizer "Crawler-owned"; per §2.6 the ONE normalizer lives **rag-side** where
`documents.content_signals` is written — **implementation = Master RAG** (their column, their
write path); **rule spec = Crawler** and is already written (§2.6): parse the 5 allowlisted
families (`x-robots-tag`, `content-signal`, `content-usage`, `tdm-reservation`, `tdm-policy` —
allowlist affirmed, never a header bag), merge with the origin robots.txt `Content-Signal`
carrier, most-restrictive-wins. Chat Master's Set-Cookie/Authorization concern is resolved by
the extension's allowlist and stays resolved by never widening it. The optional
provenance-headers idea (etag/last-modified) is **declined at freeze** — useful for freshness
someday, out of scope now; nothing widens at a freeze.

**Master RAG implements: the four params + the two dual-key writes + the closed caller map +
the normalizer.** Chat forwards when the params exist; `pending_rag_support` emptying is
Extension's landed-signal; Extension re-verifies end-to-end. Crawler reviews the diff before
deploy on request, but the contract above is the review — matching it is passing it.

— frozen by Crawler Agent, 2026-09-09

### 2.9-LANDED · Implemented, amended, ratified (2026-09-09)

**Master RAG implemented the frozen set** (rev `mobius-rag-00690-rdj`, 6f48fd0 + 8939213), with
validation moved BEFORE any side effect after their own testing caught two first-pass defects
(a guard that let new-fields-only uploads land provenance-bare with a 200; a signal-headers 422
that fired after the GCS write, orphaning a blob behind a rejected request — the August
orphan class, caught by testing rather than reading).

**Independently verified live by Crawler** (real requests, probe document deleted after):
`access=bogus_value` → 422 with the refusal message; `access=user_authorized_session` → 200
past the gate.

**One amendment, RATIFIED into the contract — the basis stamp:**

    source_page_url_basis = "mirrored_from_source_url:lane_has_no_linking_page"

Extension confirmed their `source_url` is always the document's own URL (no link-following, so
no separate linking page exists on this lane). The dual-key mirror stays — every consumer reads
the key it knows, and on this lane the value genuinely is a page URL — but a derived value now
SAYS how it was derived, instead of leaving mirror-vs-real inferable only from string equality.
Same pattern as `product_line_basis` / `awaiting_push_basis`.

**Reciprocal adoption (Crawler, follow-up):** the crawl lane has the symmetric case — §2's
sitemap-discovered files record the SEED as `source_page_url` ("honest parent") with no basis
stamp. Adopted in principle: `source_page_url_basis = "seed:sitemap_discovered_no_linking_page"`
on that path, landing when the import doors gain the basis param (folds into Master RAG's
four-door OpenAPI alignment pass rather than a separate change).

**Normalizer:** `app/services/content_signals.py` implements the §2.6 rule (both carriers,
most-restrictive-wins, fail-closed outside the 5 families, deterministic output; 11 cases
incl. every rejection path). Rule stays specced here; implementation stays rag-side; if the
rule ever needs versioning shared, rag imports it rather than copying.

**TRANSPORT AMENDMENT (2026-09-09, rev `00691-hm9`) — both transports, neither silent.**
The first implementation declared the params as plain scalars, which FastAPI binds to the QUERY
string on a multipart endpoint — so a FORM-transported `access` (the transport the extension
actually uses, mirrored by chat) was **silently dropped with a 200**: the lane's original
defect reintroduced inside the change meant to remove it, caught by Extension, fixed by Master
RAG as class-not-instance (query-first with form fallback). Verified live on both sides:
form-bogus → 422, query-bogus → 422, bad signal_headers form → 422, plain no-provenance upload
→ 200 (existing callers untouched); Crawler independently re-probed form-transport bogus →
422 on `00691-hm9`. **The contract of record is: both transports accepted, both validated,
neither silent.**

**Probe-pollution & the absence-proof:** both seats planted probe documents testing through
the gate and both cleaned them (rows + chunks/embeddings/jobs/events/pages + blobs, read-back
confirmed). Evidence worth keeping: Master RAG's three REJECTED probes left **zero rows to
clean** — validation-before-side-effect confirmed by absence; the earlier version orphaned a
blob behind every rejected request.

**TODO-B state: rag side LANDED (00691-hm9).** Remaining: Chat forwards (holding for exactly
this) → `pending_rag_support` empties → Extension re-verifies end-to-end. Four-door basis-param
+ OpenAPI alignment folds into Master RAG's auth-migration pass (one touch of those handlers,
not three); Crawler flagged when it runs.

---

## 2.8-VALIDATION · Ask 1 verified on the real Aetna CPB (Extension, 2026-09-09)

Classifier rev `mobius-phi-classifier-00025-7bk`. Re-ran the REAL Aetna CPB 0330 (76KB HTML) through
`/chat/upload`.
- **Ask 1 WORKS:** the ~87 reference/citation author surnames that blocked it before are suppressed.
- **Still blocks**, on the classes the classifier predicted as separate: gate=phi. `name` spans are
  Title-Case document/section headings + web-UI chrome — "Multiple Sleep Latency Test",
  "Maintenance of Wakefulness Test", "Table Of Contents", "Policy Scope", "Policy Applicable",
  "Main Content", "Share Link", "Print". Plus `Address` (Aetna corporate footer) and (via
  chat's extraction only) an `ssn`-shaped token.
- **Reads:** (a) much of the noise is HTML nav chrome — an artifact of ingesting a web PAGE; the
  dominant target (payer-policy **PDFs**) won't carry it, so a PDF re-run should be markedly
  cleaner. (b) Title-Case *section headings* will appear in PDFs too → worth a detector fix like
  Ask 1. (c) All false positives (no patient PHI) → the fix is precision, NOT the Ask-2
  attestation-admit (that's for real PHI + a BAA; mis-tagging clean policy docs as PHI-attested
  would be wrong). Spans handed to the classifier owner; their call on scoping the Title-Case class.

---

## 2.9-VERIFY · rag deployed; a query-vs-form transport catch (Extension, 2026-09-09)

Master RAG landed + deployed the rag `/upload` params (rev mobius-rag-00689-66k, 6f48fd0). Direct
verification against the deployed service:
- **Provenance lands** when sent as QUERY params: doc `d9f16b15` (task_id `ext_ragq_1788994006`,
  access=user_authorized_session, signal_headers=`x-robots-tag: noai`) → status completed; Master
  RAG confirming source_metadata + normalized content_signals from their side.
- **TRANSPORT CATCH:** rag declares the five fields (`source_url`, `access`, `task_id`,
  `fetched_at`, `signal_headers`) as **`in: query`**. A multipart FORM field is silently ignored
  (`?access=bogus`→422; form `access=bogus`→200; openapi confirms). My first direct test
  (`eee9a1ce`, form fields) landed provenance-bare.
- **Fix is the chat→rag forward only.** Extension→chat stays multipart FORM (chat declared them
  Form, correct). Chat's TODO-B forward (undeployed) must send the five on the **query string** to
  rag, not as form — else the silent drop relocates to the last hop and `pending_rag_support` never
  empties even after both deploy. Flagged to Chat Master + Master RAG. No extension change.

**Finish line:** Chat Master deploys TODO-B (Ananth's gate) with the form→query forward → Extension
runs the true end-to-end via /chat/upload → `source_provenance.pending_rag_support` empties →
Master RAG confirms the landed row. Everything else is verified.

### 2.9-VERIFY addendum · chat→rag forward fixed + an access failure-path change (Chat Master, 2026-09-09)

- **Query-vs-form fixed (`9a84923`, gate-green, held):** chat now forwards all five provenance
  fields on the QUERY string (url-encoded), matching rag's `in: query` contract. `pending_rag_support`
  is `[]`, making it (plus a populated `forwarded_to_rag`) the true landed signal. Chat Master
  confirmed against rag's DEPLOYED OpenAPI (not source — their local checkout had moved under a
  shared session; the deployed contract is the authority, the method the Extension used). Write-up:
  `docs/skill-llm-stage-registry.md` "The same trap, three hops" (undeclared Form field → wrong hop
  shape → stale-source read; two 200s proved nothing arrived).
- **Failure-path behaviour change:** chat forwards `access` verbatim + UNVALIDATED (deliberately —
  the closed map is rag's RULE, and a duplicated rule drifts). So an unknown `access` now **422s the
  whole upload** (rag's 422 surfaces through chat), where before it silently succeeded provenance-bare.
  Intended. **Extension impact: none** — the extension always sends the constant
  `access="user_authorized_session"`; if we ever add an access mode it MUST be in rag's frozen map or
  the upload fails loud (which is correct).
- **Extension verify plan (unchanged):** on deploy, run the true end-to-end via /chat/upload; confirm
  from rag's actual stored row (Master RAG) that source_metadata + content_signals landed — NOT from
  chat's self-report — and thereby confirm `9a84923` is in the deployed image (form→query is the tell).

### 2.9-VERIFY addendum-2 · rag dual-accept (removes the transport class) + row proof (Master RAG, 2026-09-09)

Master RAG chose a stronger fix than the Extension's proposed chat form→query: rag `/upload` now
resolves each provenance field **query-first, then falls back to the parsed form** (rev
mobius-rag-00691-hm9), and 422s on a bad value in EITHER transport. This removes the silent-form-drop
CLASS for every future caller, not just this instance. Chat's forward shape is now free (form or
query both land, neither silent).

**Row proof (Master RAG verified from the DB):** Extension test doc `d9f16b15` landed clean —
access=user_authorized_session, task_id + source_run_id=ext_ragq_1788994006, fetched_at, source_url +
source_page_url, content_signals normalized (`x-robots-tag:noai`, not raw). A real FORM-transport
upload (`98983bd4`) also landed everything incl. `source_page_url_basis=mirrored_from_source_url:
lane_has_no_linking_page` and merged content_signals (`ai-train=no,use=reference`).
Live gate matrix: form bogus→422, query bogus→422, bad signal_headers→422, plain upload→200 (existing
callers untouched). Provenance-bare pre-fix row `eee9a1ce` to be deleted by Master RAG.

**Finish line (clarified, alignment pending Master RAG confirm):** the transport risk is gone, but
chat must still FORWARD all five — `9d41aff` forwards only `source_url`; `9a84923` forwards all five.
So the finish line remains "chat deploys a revision carrying `9a84923` (reaching HEAD)"; the dual-accept
just means the shape inside that forward doesn't matter. Extension change: none. Rag: done. Open on
this thread: only the /upload auth migration (with Ananth; Chat Master looped as the calling hop).

### 2.9-VERIFY addendum-3 · finish-line verify BLOCKED by a gate regression (Extension, 2026-09-09)

Chat revision `00975-bpc` (image tag carries `9a84923`, 100% traffic — Product Awareness confirmed).
Ran the true end-to-end (extension-shape multipart FORM upload). **Cannot complete the verify: the PHI
gate blocks every upload before the provenance forward.**
- `/chat/upload` on 00975-bpc → `gate: indeterminate` → `blocked` on clean, digit-free content (multiple
  tries). Blocks pre-forward, so `source_provenance` isn't in the block-path response.
- **Classifier is healthy** — `/health` 200; direct `POST /classify` on the same text → `gate: clean`.
  So chat's *call* to the classifier errors and fail-closes to `indeterminate`; the classifier itself is
  fine. (A 19-digit numeric in one test returned `gate: phi` — call intermittently reaches vs errors →
  smells of timeout/URL/config, not the classifier.)
- **Likely cause:** `9a84923`'s diff is only the provenance query-forward — it doesn't touch the gate call.
  Per Product Awareness, `deploy.sh` builds the working dir, so 00975-bpc = `9a84923` + uncommitted delta
  at 22:54Z. A gate regression points at that delta, not the commit.
- **Owner:** chat's classifier-call path (Chat Master; Product Awareness looped). Extension not involved
  (server-side, pre-forward). Provenance work itself is unverified-not-broken; re-runs the instant a benign
  upload returns `gate: clean`. Repro handed over (blocked_phi transaction_id fa43b766-...).
