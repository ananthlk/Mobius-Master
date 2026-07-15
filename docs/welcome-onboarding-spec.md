# Tailored Welcome & Onboarding — design spec (v0 draft)

**Directive (Ananth, 2026-07-15):** new users' first message is a product tour + summary;
ease their fears based on their profile; a tailored set-up module. PA agent owns the
spec + tour content; User Manager owns the profile contract; UX owns presentation;
chat wiring lands when the chat round opens.

**Status: DRAFT — blocked on User Manager's profile-model answers (5 questions sent 2026-07-15).**

## The shape

```
first session detected (User Manager: first_session / never_onboarded)
        │
        ▼
WELCOME CARD (chat, composed from welcome_profile)
  ├─ greeting by name (existing greeting contract)
  ├─ 3-sentence "what Mobius is for YOU" — persona-keyed (role)
  ├─ fear-easing line — posture-keyed (experience level)
  ├─ ▶ tour chips (1 primary + 1 alt) — role-mapped interact scripts
  └─ setup checklist: ① confirm preferences (tone/experience/autonomy)
                      ② confirm org  ③ try your first question (suggested per role)
```

## Personas × fears (draft — validate with UM data)

| Persona (role signal) | Likely fear | Reassurance (from verified docs) | First tour |
|---|---|---|---|
| Billing / claims staff | "AI will get it wrong and I'll be liable" | Citations on every answer; honesty critic; refuse-over-guess | check-provider-credentialing → tasks |
| Credentialing staff | "another system to learn" | Ask in plain words; chat is the front door; roster UI still there | credentialing card + Open Report chip tour |
| Clinician / clinical admin | "is patient data safe here" | PHI detection, visibility ceilings, private-by-default vault | upload-a-document (PHI card) tour |
| Ops / finance exec | "is this real or a demo" | Verified market numbers (26 analytics tools), benchmarks from claims data | analytics / strategy deck tour |
| Low AI-experience (any role) | "too complex for me" | Guided Show-me tours; preferences set the style; vibe | response-modes → update-preferences |
| High AI-experience | "is this just a chatbot wrapper" | Tool manifest, RECITAL/cards, corpus + registry architecture | operations-suite tour + schematic link |

## Assets already live (reuse, don't rebuild)
- 8 verified interact tours incl. update-preferences, sign-in, upload, ops-suite, response-modes.
- Greeting contract ({name, enabled}); onboarding nudge (`#onboardingNudge` → Preferences).
- Docs corpus answers "what is X" with honest planned/live gating; platform schematic at /schematic.
- Org invite flow carries role (org-agent → mobius-user, migration 005).

## To build
1. **welcome_profile contract** (UM): first_session flag + role + experience_level + org_status — extend greeting or dedicated endpoint (UM's call; question #4).
2. **Welcome tours**: 1–2 new persona scripts where the table's "first tour" doesn't exist yet (analytics tour is new; others exist).
3. **Welcome composition** (chat side, deferred): card template keyed by persona; UX designs it.
4. **Setup checklist state**: what marks "onboarded done" (UM's nudge state; question #2).
5. **Scheduled follow-up** (Ananth: "welcome / tailored set up schedule"): day-2/day-7 nudge —
   "you haven't tried X yet" via the tasks/nudge machinery (reminder kind exists). Needs UM + Task agent.

## Open questions
- UM's five (roles taxonomy, first-sign-in state, preferences shape, greeting extension, posture signals).
- UX: welcome card layout; where tour chips live; skippability (never trap the user).
- Ananth: should the welcome fire once (first session) or until dismissed/completed?
