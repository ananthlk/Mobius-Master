# Tailored Welcome & Onboarding — contract spec v1

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
- **UX:** welcome card layout + tour-chip placement; skippability (never trap);
  RULING NEEDED on the direct fear question.
- **Task agent:** day-2/day-7 scheduled nudges ("you haven't tried X") via reminder
  kind + nudge machinery.
- **Chat (deferred):** render welcome card when `welcome.first_session` (or
  !is_onboarded per Ananth's pick); compose from the content pack.

## 6. Open items
- Ananth: fire once (first_session) vs until-completed (is_onboarded)? PA leans until-completed.
- Ananth: membership-approval flow green-light (unlocks org_status="pending" + approval-aware welcome copy).
- UX: fear-question ruling + card design.
- Exec persona gap (§3) — new activity or role.
