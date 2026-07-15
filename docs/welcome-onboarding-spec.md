# Training Mode (Welcome & Onboarding) — contract spec v2

**v2 pivot (Ananth, 2026-07-15): this is a MODE, not a card — "TRAINING MODE", owned by
the Product-Awareness agent.** Interaction IS the profiling: users click and respond,
and each response BUILDS their profile (the baseline for all tailoring). Engagement-first
— "have them click, have them respond." The tailored welcome card (v1 below) becomes the
GRADUATION artifact at the end of training, not the entry point.

## Training sequence (v2 — each step teaches the product AND learns the user)
| # | Step | Mechanic | Writes (UM preference) |
|---|---|---|---|
| 1 | "90 seconds — I learn you, you learn me" | consent + skip always visible | — |
| 2 | Pick your week | activity cards, multi-select, primary first | `activities` |
| 3 | Same answer, three ways | ONE real question rendered three ways, **UNLABELED** — "no labels, no right answer, tap the reply you'd rather read." The pick DEDUCES `tone`; the deduction is revealed only on the graduation chip (Ananth: labels bias the pick — deduce from answers, don't ask them to self-identify as 'friendly') | `tone` |
| 4 | "A denial needs reworking. Should I…?" | scenario: Just do it / Show me first / Walk me through | `autonomy` (+ experience-level inference) |
| 5 | "Anything make you hesitant?" | optional chips (wrong answers / patient data / too complex / nothing) — the UX-approved deferred fear question, now placed AFTER engagement | `hesitation` (new field, UM) |
| 6 | Graduation | profile summary ("here's what I learned — edit anytime in Preferences") + the tailored fun card + confetti; card retires when checklist completes | `onboarding_completed_at` |

Principles carried from v1: promise-what-the-profile-guarantees; three honesty pillars
(Today / Coming — really not built / You steer it, with a working make-a-wish);
skippable at every step, never trapped; picks demonstrate their effect INSTANTLY
(pick concise → the sample re-renders concise).

## Success criteria (Ananth, 2026-07-15): "truly capturing the user intents and
## experience so that they are set up and will come back"
The mode is measured on OUTCOMES, not completion theater:
1. **Intent capture** — the graduation first-question is USER-AUTHORED (chips are
   starters, not scripts — "user select… as against saying it for them"). The typed/chosen
   question is stored as an intent signal; if Mobius can't answer it, it AUTO-FILES into
   the demand loop (docs_gap / feature_request) — a new user's unmet first intent is the
   highest-value gap signal we can collect.
2. **Setup fidelity** — % of training picks later EDITED in Preferences is the
   mis-capture metric (low churn = we understood them). Per-step completion + skip rates.
   **MEASURABLE (UM migration 008, live + smoke-verified 2026-07-15):** user_preference_audit
   (user_id, field, old_value, new_value, source, changed_at). CONTRACT: every training-mode
   write includes `"source": "training_mode"` in the PUT /preferences body; churn = rows where
   source != 'training_mode' AND the field was previously written by training_mode. No-op
   saves don't audit (metric stays clean); initial onboarding capture deliberately unaudited
   (first writes aren't churn). Bonus: unexplained modal-source rows expose the
   silent-default-flip bug class in data.
3. **Return** — D1/D7 return rate of trained vs skipped users; first-question fire rate
   from the graduation card; second-session first-action.
Owner: PA agent tracks these once chat wiring lands (needs skill_invocations-style
telemetry — flagged as a dependency; the analytics gap is a known skills-node item).

## v2.1 corrections (User Manager, preference owner, 2026-07-15 — accepted)
- **Step 4 writes `autonomy_sensitive`, NOT routine** — a denial-rework scenario is the
  preference model's literal definition of sensitive. (Optionally routine = one notch
  more autonomous than the pick; v1 writes sensitive only.)
- **Experience level is SELF-DECLARED, never inferred** — independent axis (the
  counterexample: an expert who wants confirm-first on sensitive work). The autonomy pick
  may PRE-SELECT a suggestion in a visible control the user confirms — never a silent write.
  Training adds a micro-chip confirm ("How much AI have you used?") on the same screen.
- **`hesitations` = text[] multi-select** (UM migration 007, `hesitations` field on the
  preferences API, returned in /me; empty = skipped). Welcome block unchanged for now;
  can ride it additively if graduation ever re-renders server-side.
- Per-step writes confirmed: existing PUT /api/v1/auth/preferences (all-optional body);
  graduation = PUT /api/v1/auth/onboarding; /me lazily re-renders the profile prompt, so
  a step-3 tone pick shapes answers immediately.

**Ownership:** PA agent OWNS training mode (sequence, content, mechanics, prototype).
UM owns the write path (each step → preference field; `hesitation` is a new field).
UX polishes presentation. Chat hosts the mode (deferred round) — triggers: first
session / !is_onboarded, cheat codes `/welcome`, `/training`, `?welcome=1`.
**Prototype live at product-awareness `/welcome-preview` (training flow + graduation card).**

---
# v1 spec below (welcome block contract §2 unchanged — UM's build stands)



**Directive (Ananth, 2026-07-15):** new users' first message is a product tour + summary;
ease their fears based on their profile; a tailored set-up module, with a scheduled follow-up.

**Co-owners:** PA agent (spec, persona content, tours) · User Manager (profile contract,
`welcome` block) · UX (card presentation, fear-question ruling) · Task agent (scheduled
nudges) · Chat (composition — deferred until Ananth opens the chat round).

**v1 status: CONTRACT FIXED — UM implementing the `welcome` block against §2.**

## 1. The shape

```
whoami/by-identity returns `welcome` (always present; chat decides when to render)
        │
        ▼
WELCOME CARD (first_session=true, or until is_onboarded — Ananth to pick)
  ├─ greeting by preferred name (existing greeting contract)
  ├─ arrival-keyed opening:
  │    invited    → "Your org already set you up — here's what you can do."
  │    self_serve → orientation ("what Mobius is" in 3 sentences)
  ├─ persona paragraph: activities × experience_level (see §3)
  ├─ fear-easing line: PROMISE WHAT THE PROFILE GUARANTEES (see §4)
  ├─ ▶ tour chips: 1 primary + 1 alt, persona-mapped interact scripts (§3)
  └─ setup checklist: ① preferences (tone/experience/autonomy — all revisable)
                      ② org (confirm membership / self-claim)  ③ suggested first question (persona-keyed)
```

## 2. The `welcome` block — CONTRACT (UM builds; PA + chat consume)

Extends by-identity/whoami (UM's call: one fetch, one cache, one auth path — no new endpoint):

```json
"welcome": {
  "first_session": true,            // derived server-side (last_login_at null at token issue)
  "is_onboarded": false,            // onboarding_completed_at null — nudge state
  "arrival": "invited",             // "invited" | "self_serve"
  "org_status": "member",           // "member" | "none" (| "pending" when approval flow lands)
  "roles": ["credentialing_coordinator"],   // operational grants (per-org, open set)
  "activities": ["rework_denials", "submit_claims"],  // user-picked, ordered, primary first
  "experience_level": "beginner",   // beginner | regular | expert
  "tone": "professional"            // professional | friendly | concise
}
```

Notes: computed server-side, present on every response (cheap); chat-side 5-min cache rides
the existing whoami path. `org_status:"pending"` semantics arrive with the membership-approval
flow (pending Ananth green-light). Welcome content must NOT duplicate rendered_prompt
instructions (the profile already steers 5 LLM stages) — welcome REFERENCES behavior, prompt ENFORCES it.

## 3. Personas — keyed activities × roles × experience × arrival

| Persona key (priority order) | Fear (proxy-derived) | Reassurance (all live, verified) | Primary tour | Alt tour |
|---|---|---|---|---|
| activities ∋ rework_denials / submit_claims | "wrong answer = my liability" | Citations on every answer; honesty critic; refuses over guessing | credentialing card (check-provider) | complete-a-task |
| roles ∋ credentialing_coordinator | "another system to learn" | Ask in plain words; chat is the front door; roster UI still there | ops-suite | check-provider |
| activities ∋ schedule/check-in/outreach (front-desk) | "too complex / not for me" | Show-me tours; plain-words answers; preferences set the style | response-modes | update-preferences |
| PHI-adjacent activities (outreach, clinical) | "is patient data safe" | PHI detection on uploads; private-by-default; visibility ceilings | upload-a-document | sign-in |
| roles ∋ rag_admin / corpus_curator / eval_owner | "is the corpus trustworthy" | Publish pipeline, lexicon QA, eval baselines | ops-suite (library leg) | give-feedback |
| experience_level=expert (any) | "just a chatbot wrapper?" | Tool manifest (45), cards/RECITAL, registry architecture, /schematic | ops-suite | email-a-thread |
| DEFAULT (no signals — self-serve day one) | general orientation | 3-sentence what-is-Mobius (about module, verified) | response-modes | update-preferences |
| **GAP** exec/analytics persona | "is this real or a demo" | verified claims-data numbers | **analytics tour — TO AUTHOR** | strategy deck |

Resolution: first matching row wins by priority; experience_level=beginner ADDS the
hand-holding line to any persona (see §4). Exec gap: no exec activity exists in the
catalog — either UM adds one (e.g. financial_strategy — deferred entity from task-v2
backlog!) or we key off future role; parked.

## 4. Promise-what-the-profile-guarantees (fear-easing lines)

- experience beginner → "Mobius explains itself and asks before acting" — GUARANTEED by
  rendered_prompt (beginner behavior) + autonomy confirm_first defaults.
- autonomy manual/confirm_first on sensitive → "nothing sensitive happens without your
  say-so" — GUARANTEED by hard sensitive-tool gating (shipped).
- accuracy fear → "every answer shows its sources — click any citation" — GUARANTEED
  by citations + honesty critic.
- data safety → "uploads are checked for patient info and kept private by default" —
  GUARANTEED by PHI classifier (live) + visibility ceilings (promote gate planned —
  say "private by default" only, until promote ships).

## 5. Build items
- **UM:** `welcome` block per §2; optional `hesitation` preference IF UX approves the
  direct question ("what's your biggest hesitation?" at onboarding).
- **PA (me):** persona content pack (per-row: opening, fear line, suggested first
  question) as versioned content UM/chat can consume; author the analytics tour;
  re-verify the 6 mapped tours against current anchors.
- **UX: DELIVERED 2026-07-15.** Card design: inline soft card at thread top ("a colleague
  left a note on your desk"), border-left 3px violet, surface-2 bg, no shadow, max 640px;
  greeting + one-sentence fear-ease (no bullets) + 2 ghost-style tour chips + compact
  3-step checklist ("A few things to get started") + "Skip for now" plain link. REPLACES
  the onboarding nudge when a welcome payload is present; falls back to nudge otherwise.
  Dismiss semantics (reconciled with Ananth's until-completed ruling): "Skip for now" =
  per-session hide; "×" = permanent opt-out (the "explicitly turned off" path); checklist
  completion = permanent auto-hide.
- **Fear question RULED (UX):** NO on cold arrival (survey-before-trust). DEFERRED version
  approved: if the user skips the tour chips or disengages in the first 3–5 turns, surface
  an optional "help us tailor your experience" prompt; UM stores the answer as a preference
  then. New build item (chat round): disengagement detection + deferred prompt.
- **Task agent:** day-2/day-7 scheduled nudges ("you haven't tried X") via reminder
  kind + nudge machinery.
- **Chat (deferred):** render welcome card when `welcome.first_session` (or
  !is_onboarded per Ananth's pick); compose from the content pack.

## 6. Decisions & principles (Ananth, 2026-07-15)
- **DECIDED: welcome persists until-completed** (renders while `!is_onboarded`; dismissible
  per session, returns until the checklist is done or explicitly turned off).
- **CONTENT PRINCIPLE — three pillars, in order:**
  1. **True today** — only verified live capabilities (reality-gated, same as the docs).
  2. **Evolving** — where the product is going, shown honestly as planned/coming.
  3. **You shape it** — users steer the roadmap, and the loop is REAL: feedback files
     backlog items, "no docs yet" auto-files gaps, asking for a planned feature tallies
     demand (capability_demand), page-worthy feedback becomes tasks. The welcome says
     this explicitly and invites it.

## 7. Cheat code (testing + power users)
- **In chat (when wired):** message exactly `/welcome` → deterministic pre-router trigger
  (NOT planner-routed — planner paraphrase drops intent; same lesson as recite). Renders
  the welcome card regardless of first_session/is_onboarded, using the caller's live profile.
- **Client param:** `?welcome=1` on the chat URL forces the card client-side (same data).
- **TODAY, before chat wiring:** GET /welcome-preview on the product-awareness service —
  interactive harness with persona / arrival / experience / name toggles rendering the
  exact card content per profile. Ananth-testable immediately.

## 8. Open items
- ~~Ananth: membership-approval flow green-light~~ **GREEN-LIT 2026-07-15** — User Manager
  builds the flow (self-claim → pending → approve; org side ready per Org agent; instant-RAG
  is the named consumer). `org_status:"pending"` joins the welcome block when it ships;
  welcome copy for pending users: "your org membership is awaiting approval — here's what
  you can do meanwhile."
- UX: fear-question ruling + card design (three-pillar content structure per §6).
- Exec persona gap (§3) — new activity or role.
