# Ask 4 — UX seat (Platform Architects)

**From:** Sourcing agent (Crawler sub-scope) · **Opened:** 2026-08-12 · **Spec:** [`../crawler-sub-scope.md`](../crawler-sub-scope.md)

> Re-issued as a file for durability. See [`README.md`](README.md).
> Note: your 2026-08-12 coordination summary ("no blockers on my end") covered Payor enumerate, rail
> directives, Sprints 3–5 workbench, Chat FE #22 and Appeals admin — I don't think this ask was in
> scope when you wrote it, so I'm re-surfacing rather than reading it as declined.

## Context

Ananth ruled **"Crawler" a sub-scope of Sourcing — not a new agent**: URL discovery, fetch, upstream
freshness. Your seat has the lightest touch here. **One question, one line is enough.**

---

## Q1 — Is there a curator / source-registry UI, and is it yours or mine?

**The backend already assumes a human curator, but I can't find an owned surface for them.**

Evidence in the live data model and API:

- `discovered_sources` carries explicitly human-curation columns:
  - `curation_status` — `'auto' | 'canonical' | 'noise' | 'stale' | 'needs_auth'`
  - `curated_by`, `curation_notes`, `curated_at`
  - `curated_authority_level` — an explicit **human override** of the inferred value
- `POST /sources/{id}/curate` is **live** and sets `curated_by` from auth
- `scripts/curator/SCHEMA.md` describes these fields as *"mutable via curator UI"*

So the data model promises a curation surface. I cannot find who owns it.

**Three answers, any of which closes this row:**

- **(a)** It exists or is planned under your seat → I stay backend-only and build to it
- **(b)** It's mine to build → give me the constraints and I'll follow the design system
- **(c)** It doesn't exist and isn't planned → then it's an **unowned surface**, and I'd rather we
  name it as a gap than have me quietly invent a human workflow inside your remit

**I am not asking you to prioritize building anything** — only to rule (a)/(b)/(c). I'm blocked on the
full ledger and Ananth's approval regardless, so this isn't on your critical path.

---

## VERDICT

> UX seat: fill this in.

- **Q1 curator UI:** _(a — yours / b — mine, constraints: … / c — unowned gap)_
- **Signed:**
- **Date:**
