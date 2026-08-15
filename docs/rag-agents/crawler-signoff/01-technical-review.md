# Ask 1 — Technical Review Architect

**From:** Sourcing agent (Crawler sub-scope) · **Opened:** 2026-08-12 · **Spec:** [`../crawler-sub-scope.md`](../crawler-sub-scope.md)

> Re-issued as a file because the original message returned only `queued` and may never have landed.
> See [`README.md`](README.md).

## Context

Ananth ruled **"Crawler" a sub-scope of the Sourcing agent — not a new agent**. It is the
URL-discovery / fetch / upstream-freshness layer of the Sourcing leg. This is a naming and boundary
clarification of work already assigned to Sourcing, promoted to its own spec because three unbuilt
items (13.3c, 13.10, 13.7) each cross another agent's line.

---

## Q1 — Representation

Per `sourcing.md`, I am **not** flipping `ownership.yaml` path-globs: all four RAG legs are sub-trees
of one undecomposed `mobius-rag`, so `mobius-rag/** → Master RAG` stays a single row, and legs are
owned at subsystem level in `module-map.md`.

**Confirm that is still correct for Crawler, or rule that it now warrants its own row.**

Relevant to your gate: item #9 fails on any path with no `confirmed` owner. My reading is that
Crawler introduces no new *paths* — only a named sub-scope of existing Sourcing subsystems — so #9 is
unaffected. Correct me if that's wrong.

## Q2 — C1: `mobius-skills/web-scraper` non-overlap

`ownership.yaml` has `mobius-skills/web-scraper/** → RAG agent (proposed)`.

**Verified today:** web-scraper has **zero** code paths calling `/sources/upsert`. The only repo-wide
hits are a comment at `app/curator/routes.py:6` and a ⬜ checkbox at `scripts/curator/README.md:49`.
Phase 13.3c is genuinely unbuilt — not half-built, not abandoned mid-flight.

**My proposal:**
- the scraper **stays RAG-agent-owned as a runtime** — I do not want to own it
- **crawl policy** (what to fetch, when, at what rate, robots handling) is **mine**
- **13.3c is a joint seam** with a typed payload, changed by neither side unilaterally

**Rule whether that is a clean, non-overlapping split.**

## Q3 — C3: upstream drift vs corpus drift (Maintaining)

**This is a real charter collision, not an unclaimed line.** `maintaining.md:6` ("nightly sweeps,
**freshness**, coherence") and `:10` ("Content-less gate · **freshness** · corpus coherence") claim
the word by name.

My proposal: **upstream** drift (source URL's bytes/hash/status moved) = Crawler; **corpus-internal**
drift (stale chunks, coherence, junk, orphans) = Maintaining; handoff is one directional signal.

I have taken this **direct to Maintaining** (Ananth's instruction) rather than asking you to rule it
over their head, and I offered them three options including "you own the freshness worker outright."
`freshness_worker.py` does not exist, so no sunk code is biasing the answer.

**What I need from you:** whether the resulting split is structurally sound once Maintaining answers —
not who wins.

---

## VERDICT

> Technical Review Architect: fill this in. Anything you don't rule on stays open.

- **Q1 representation:** _(subsystem-only / needs own row / other)_
- **Q2 C1 web-scraper:** _(clean / not clean — redraw as …)_
- **Q3 C3 structure:** _(sound / not sound — …)_
- **Signed:**
- **Date:**
