# Mobius Specs Catalog — Team Guide

**Live at:** https://mobius-specs-1032922478554.us-central1.run.app

---

## What Is This?

This is the **single source of truth** for:
- ✅ What's shipped (live in production)
- 🔨 What's being built (with delivery dates)
- 🗺️ What's planned (design ready, awaiting resources)
- ⏸️ What's blocked (built but waiting on something upstream)
- 🔍 What needs sign-off before shipping

---

## Using It

### For Onboarding (New Team Members)

1. Open the catalog
2. Click the **Onboarding** tab
3. Find your role (Chat Owner, RAG Owner, Appeals Owner, etc.)
4. Read every document listed
5. ✓ Check the box when you've read it

### For Shipping Features

Before you ship anything:
1. Find your feature in the catalog
2. Review the **Acceptance Criteria** checklist
3. ✓ Make sure all criteria are met
4. Get sign-offs from the owners listed
5. Ship it

### For Understanding Blockers

If something isn't shipping:
1. Find it in the catalog
2. Look for the ⏸️ Blocked badge
3. Read the **Blocker** column — it explains why
4. See who owns that blocker

Example:
- **Observer** is ⏸️ Blocked because it's "Awaiting Eval's calibration plan"
- Contact the Eval Agent owner to unblock it

### For Status Updates

Check once a week:
1. Open the catalog
2. Scan the status badges
3. If something looks stale (marked Live but you know it's still being built), ask the owner

---

## Status Badge Legend

| Badge | Meaning | Example |
|-------|---------|---------|
| ✅ Live | Deployed, verified, in production | Chat is live for policy questions |
| 🔨 In Progress | Being built right now | Answer Cache service being wired to Chat |
| 🗺️ Planned | Design done, waiting to build | Gate 7 (Coding) is on the roadmap |
| ⏸️ Blocked | Built but can't ship yet | Observer built but awaiting calibration plan |
| 🔍 Under Review | Awaiting sign-off | Chat v2 FE sign-off awaiting PA review |

---

## Roles & Responsibilities

### Chat Owner
- Keep Chat status in the catalog up to date
- Review and update acceptance criteria when they change
- Signal when you're blocked and why

### RAG / Retriever Owner
- Track all 5 RAG steps (Shape, Pool, Fillers, Router, Observer/Synthesis)
- Update status badges as work progresses
- Document blockers (e.g., "Awaiting Eval calibration")

### Appeals Owner
- Maintain Appeals roadmap (W1, W7, Post-M1 milestones)
- Update sign-off status for 3 locked gates
- Signal when you need chat integration or product-help filing

### Payor Platform Owner
- Maintain Platform substrate status
- Document contract policy updates
- Track Technical Day items

### Eval Owner
- Drive calibration plans (Observer, Synthesis)
- Update sign-off status as work completes
- Signal when blockers are resolved

### UX / Design Lead
- Govern design system adoption
- Review Governance Surface pattern usage
- Update Figma component status

---

## How to Update the Catalog

### If You're the Owner of Something

1. When status changes (now Live, now Blocked, new blocker), update the catalog
2. Edit the relevant section in `specs-platform/index.html`
3. Commit and push: `git add specs-platform/index.html && git commit -m "update: Gate X status" && git push`
4. **Done** — site redeploys automatically in ~2 minutes

### If You're Updating Product Docs

1. Edit `/docs/product-docs/mobius-chat.md` or `/docs/rag-backend.md`, etc.
2. Commit and push
3. **Done** — specs catalog auto-syncs (symlink) and redeploys

### Don't Do This

❌ Edit the website directly (it's read-only)  
❌ Upload files to the server (it auto-deploys from git)  
❌ Bypass git to make changes (git is the source of truth)  

---

## Questions to Ask Using the Catalog

**Is X shipped?**
→ Open the catalog, search for X, check the status badge

**When is X shipping?**
→ Open the catalog, find X, read the acceptance criteria checklist (that tells you what's left)

**Who owns X?**
→ Open the catalog, look at the "Owner" column for that feature

**Why is X blocked?**
→ Open the catalog, find the ⏸️ Blocked badge, read the blocker note

**Can I ship now?**
→ Open the catalog, find your feature, check if all acceptance criteria are met

---

## If Something Looks Wrong

1. **The site is down** → Tell PA Architect (usually a deployment issue, fixed in 2-5 min)
2. **A status looks stale** → Ask the owner to update it
3. **Missing a feature** → Tell PA Architect to add it to the index
4. **Acceptance criteria are wrong** → Tell the owner to update them

---

## Quarterly Reviews

**Every October 1–7:**
- Gate owners fill out the Q4 Quarterly Alignment form
- PA Architect updates the catalog with new status
- Everyone reviews and approves

This is how you know the catalog stays honest and current.

---

**Remember:** This catalog exists so you never have to ask "what's shipped?" or "where's the spec?" 

It's always here. It's always current (because it's tied to git). It's always honest (because gate owners update it quarterly).

Use it.

---

**Questions?** Contact the PA Architect.
