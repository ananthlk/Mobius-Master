# Interact agent — design spec

Status: design only (no code yet). Authored 2026-07-06 by the product-awareness agent
on Ananth's direction; ownership transfers to the **Interact Agent** on kickoff.

**Mission:** a reusable web-interaction engine — the "hands" that can operate a webpage
from a declarative instruction set: *find → highlight → click → type → wait → read →
assert*. It knows nothing about Mobius features, demos, or payors. Content ("what to
do") always comes from a **feeder**; the engine only executes.

Two consumer classes, one engine:
1. **Guided demos** (first, in-scope now) — animated "show me how" walkthroughs on
   Mobius's own UI, fed by the product-awareness agent from the product docs.
2. **RPA on external sites** (later, design-for now) — e.g. check prior-authorization
   status on Sunshine Health's provider portal, fed by the payor registry agent.

The reusable asset is the **instruction schema** even more than the code: one step
format that multiple runtimes execute.

---

## 1. What it is NOT

- Not a screen recorder. No videos/GIFs — recordings rot; scripts on the live UI don't.
- Not a content owner. The engine never hardcodes flows; feeders own scripts.
- Not a crawler/scraper. `mobius-skills/web-scraper` reads pages; interact *operates* them.
- Not (initially) a general agentic browser. v1 executes declarative scripts only —
  no LLM-in-the-loop decisions mid-run. (That's a possible v3; see §9.)

## 2. Packaging & ownership

- **Module:** new top-level submodule `mobius-interact/` (own repo/deploy like
  mobius-email / product-awareness — the platform norm).
- **Owner:** the Interact Agent (new session). Owns: engine code, the step schema +
  its versioning, both runtimes, the validator, tests, this spec's evolution.
- **Not owned by interact:** demo content (product-awareness), portal knowledge
  (payor registry agent), chat frontend integration (Chat Agent), `data-tour-id`
  anchor placement (each UI's owner).

| Concern | Owner |
|---|---|
| Step schema, schema versioning, validator | **Interact** |
| In-page runner lib + external driver backend | **Interact** |
| Demo scripts (tour content), demo registry, freshness/drift sweep, demand ranking | **Product-awareness** |
| Portal/RPA scripts (later) | **Payor registry agent** |
| `data-tour-id` anchors in chat UI; "▶ Show me" chip; runner `<script>` include | **Chat Agent** |
| Permission gates for auto-mode on external sites | **Interact** (mechanism) + Ananth (policy) |

## 3. The instruction schema (the contract)

A **script** is YAML/JSON: metadata + ordered steps. Versioned (`schema: interact.v1`).

```yaml
schema: interact.v1
id: chat:upload-a-document          # <feeder-namespace>:<slug>
title: Upload a document to chat
mode: guide                          # guide | auto | narrate  (see §4)
surface: mobius-chat                 # which app/site this targets
permissions: []                      # [] for guide-on-own-UI; see §5 for auto/external
preconditions:                       # engine checks before starting; abort politely if unmet
  - selector: "[data-tour-id=composer-input]"   # "the composer exists" = user is in chat
steps:
  - find: "[data-tour-id=composer-attach]"      # anchor-first (see resolution order)
    action: highlight
    caption: "This paperclip attaches a document — PDF, DOCX, HTML, or TXT."
  - find: "[data-tour-id=composer-attach]"
    action: click                    # in guide mode: waits for the USER to click
    caption: "Click it and pick your file."
    wait_for: "[data-tour-id=composer-attachment-chip]"   # advance when this appears
  - find: "[data-tour-id=composer-attachment-chip]"
    action: highlight
    caption: "Your file is staged here — it uploads when you hit Send."
  - find: "[data-tour-id=composer-send]"
    action: highlight
    caption: "Send your question — the answer will use your document."
    end: true
```

**Step fields:** `find` (element ref) · `action` (`highlight | click | type | read |
wait | assert | navigate`) · `value` (for `type`; supports `{{inputs.*}}` templating —
never literals for secrets, see §5) · `caption` (user-visible in guide/narrate) ·
`wait_for` (selector or `{ms}`) · `optional` (skip if not found) · `end`.

**Element resolution order (normative):**
1. `data-tour-id` attribute — the stable anchor convention. Always preferred.
2. CSS selector — allowed on external sites where we can't add anchors.
3. Text match (`text:"Prior Authorization"`) — last resort, locale-fragile.

A script that uses tier 2/3 on a Mobius-owned surface fails validation — own surfaces
must use anchors (that's what keeps demos from rotting).

**RPA example (later, same schema — this is the point):**

```yaml
schema: interact.v1
id: payor:sunshine-prior-auth-status
mode: auto
surface: https://provider.sunshinehealth.com
permissions: [external_site, form_input, read_data]
inputs: [member_id, auth_number]       # supplied at run time by the caller, never stored
steps:
  - find: "text:Prior Authorization"
    action: click
  - find: "#authNumber"
    action: type
    value: "{{inputs.auth_number}}"
  - find: "#searchBtn"
    action: click
    wait_for: ".auth-status-row"
  - find: ".auth-status-row .status"
    action: read
    into: auth_status                  # returned in the run result envelope
```

## 4. Modes

| mode | what the engine does | v1? |
|---|---|---|
| `guide` | Spotlight + caption; **the user performs each action**; engine advances on `wait_for`. The demo experience. | ✅ |
| `narrate` | Engine performs the actions itself, slowly, with captions — "watch me do it." | ✅ (cheap once guide works) |
| `auto` | Engine performs actions at full speed, no UI chrome; returns a result envelope (`read` values, per-step status). The RPA mode. | design-for, build later |

## 5. Permissions & safety (design in now, enforce simply)

- Scripts declare `permissions`. The engine refuses to run a script whose permissions
  exceed what the runtime context grants.
- **Guide/narrate on Mobius-owned surfaces:** `[]` — always allowed. `type` is allowed
  only into Mobius inputs and only with user-visible captions.
- **`auto` + `external_site`:** gated. v1 ships with this HARD-DISABLED in config;
  enabling it (for the Sunshine case) requires: an allowlisted `surface`, `inputs`
  supplied per-run by the caller (never persisted in scripts), a full per-step audit
  log, and Ananth's explicit enablement. Credentials handling is OUT of scope until a
  design addendum — do not build credential storage.
- Every run (any mode) emits a run record: script id, mode, surface, per-step outcome,
  duration. (Interact owns where these persist; a `interact_runs` table mirroring
  `email_messages`' pattern is the suggested shape.)

## 6. The two runtimes

**A. In-page runner (v1).** A small dependency-free JS lib (`interact-runner.js`,
target <10 KB; vendoring driver.js is acceptable if it stays under ~20 KB) that chat
imports. Renders spotlight/tooltip/next-prev, executes guide/narrate. API:

```js
MobiusInteract.run(script, {onStep, onDone, onAbort})
```

**B. External driver (later).** Same schema, executed by either the mobius-os
extension's content script (it already injects overlays into host pages — natural fit)
or server-side Playwright for headless RPA. Building B must require **zero schema
changes** — that's the acceptance test for having designed A honestly.

## 7. Serving & the feeder interface

- **Engine service** (`mobius-interact` on Cloud Run, platform deploy pattern):
  - `GET /scripts/{id}` → validated script (engine serves; feeders publish).
  - `POST /scripts` (feeder publish; validates schema + anchors) · `POST /validate`.
  - `GET /health`.
- **Feeder contract:** a feeder owns a namespace (`chat:*` = product-awareness,
  `payor:*` = payor registry). Publish = POST a script; the engine validates and
  stores. Feeders re-publish on content change; the engine keeps `schema`-version and
  `updated_at`.
- **Consumer flow (demos):** `product_help_search` answers already carry structured
  `extra`; product-awareness adds `demo: {script_id, title}` when the matched doc
  section has one. Chat renders a "▶ Show me" chip → runner fetches `GET /scripts/{id}`
  → runs in guide mode. (Chat-side: one chip renderer + the runner include; the same
  pattern as capture_card.)

## 8. Freshness (rides the existing engine)

- **Anchor audit:** product-awareness's weekly sweep fetches the served chat bundle
  and verifies every `data-tour-id` referenced by published `chat:*` scripts still
  exists; missing anchors file a `doc_stale`-style signal (`category=doc_stale`,
  verbatim="demo <id> anchor <x> missing") via the existing feedback bus.
- **Demand ranking:** which demos to author next = the `docs_backlog` verbatims
  (users' actual "how do I…" questions). Already flowing.
- **`demo_gap` (optional later):** if a user asks "show me" where no script exists,
  product_help_search files it — same mechanics as docs_gap, no new infra.

## 9. Build phases & acceptance

- **P1 — Contract + validator.** Schema finalized (this doc §3–5), `POST /validate`
  works, 10+ schema tests. *Accept:* product-awareness can validate a hand-written
  script.
- **P2 — In-page runner + first demo.** Runner lib; Chat Agent lands ~30
  `data-tour-id` anchors (product-awareness supplies the element inventory from the
  button-level chat doc) + the chip; `chat:upload-a-document` runs in guide mode
  end-to-end in deployed chat. *Accept:* a real user clicks "▶ Show me" and completes
  an upload guided.
- **P3 — Five demand-ranked demos + narrate mode.** upload-a-document, response-modes,
  email-a-thread, open-a-source, give-feedback (order re-ranked by docs_backlog at
  build time). Anchor audit wired into the weekly sweep. *Accept:* all five verified
  in deployed chat; sweep catches a deliberately broken anchor.
- **P4 (gated, later) — auto mode + external driver.** Playwright or extension
  backend; permission gates + audit; the Sunshine prior-auth script as the pilot,
  fed by the payor registry agent. *Accept:* zero schema changes from P1–P3.

Testing note (per the fleet's consolidated-harness push): schema/validator tests are
plain pytest; runner gets a DOM-fixture test page; deployed-smoke = run one guide
script against the live chat bundle headlessly and assert step resolution.

## 10. Open questions (for kickoff)

1. Runner build: vendor driver.js vs hand-roll (~200 lines)? Lean hand-roll — zero
   deps, brandable (mobius-design tokens), and the overlay is the easy part.
2. Script storage: engine-local Postgres table vs files-in-repo published at deploy?
   Lean table (feeders publish over HTTP, no engine redeploy per content change).
3. Where do run records live — engine DB (suggested) or the chat telemetry DB?
4. Does `narrate` mode need a global kill-switch chip ("stop driving") — probably yes.

---

*Cross-references: docs/product-awareness-feedback-contract.md (the seam pattern this
follows), docs/product-docs/mobius-chat.md (the complete anchor-able element
inventory), memory note project_product_awareness_agent (freshness engine the demo
feeder plugs into).*
