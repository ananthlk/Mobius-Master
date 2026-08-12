# Specs Catalog Setup & Maintenance Process
**Purpose:** Complete end-to-end process for managing the Specs Catalog as source of truth

---

## What Is the Specs Catalog?

**URL:** https://mobius-specs-1032922478554.us-central1.run.app

**Purpose:** Single source of truth for all Mobius product specifications, gates, agent status, and acceptance criteria

**Ownership:** PA Architect (maintains), All agents (sign off on status)

**Architecture:**
- **Frontend:** Static HTML (specs-platform/index.html)
- **Server:** Python http.server in Cloud Run
- **Hosting:** Google Cloud Run (Container Registry)
- **Deployment:** Automatic (Cloud Build on git push)
- **Status Links:** GitHub (https://github.com/ananthlk/Mobius-Master/blob/main/docs/*)

---

## How It Works

### 1. Agent Submits Status
Agent (e.g., Retriever, Master RAG) fills out **AGENT_STATUS_UPDATE.md** form with verified status:
- What's LIVE
- What's IN PROGRESS  
- What's BLOCKED
- What's PLANNED
- Open bugs
- Dependencies

### 2. PA Verifies Status
PA Architect reviews submission against **AGENT_STATUS_SPEC.md** acceptance criteria:
- ✓ Status reflects TODAY's reality (not aspirations)
- ✓ Dates are realistic (not best-case)
- ✓ Blockers are real (not theoretical)
- ✓ Bugs listed are unfixed

Logs verification in **AGENT_STATUS_COLLECTION_LOG.md** and **AGENT_STATUS_SIGNOFF_TRACKER.md**

### 3. PA Updates Catalog
Edits `specs-platform/index.html` with agent-verified status:
- Updates status badges (✅ LIVE, 🔨 IN PROGRESS, ⏸️ BLOCKED, 🗺️ PLANNED)
- Adds blocker reasons and ETAs
- Updates cross-agent dependency table
- Commits with agent co-authored signature

### 4. Cloud Build Auto-Deploys
Git push triggers Cloud Build:
1. Build Docker image (Dockerfile)
2. Push to Container Registry
3. Deploy to Cloud Run
4. Live in ~2 minutes

### 5. Team Sees Live Status
Specs catalog updates automatically with:
- Verified agent status (not interpretations)
- Cross-agent blockers identified
- ETAs and dependencies visible
- Links to spec documents (GitHub)

---

## File Structure

### Core Specs Catalog
```
specs-platform/
  ├─ index.html          ← Main catalog (auto-deployed to Cloud Run)
  ├─ Dockerfile          ← Container definition for Cloud Run
  ├─ cloudbuild.yaml     ← CI/CD trigger config
  ├─ DEPLOYMENT.md       ← Setup/troubleshooting guide
  └─ status.sh           ← Script to check deployment status
```

### Agent Status Collection
```
Mobius-Master/
  ├─ AGENT_STATUS_SPEC.md                  ← Framework (what status means)
  ├─ AGENT_STATUS_UPDATE.md                ← Form template (agents fill out)
  ├─ AGENT_STATUS_UPDATE_REQUEST.md        ← Request document
  ├─ AGENT_STATUS_BROADCAST.md             ← Message sent to all agents
  ├─ AGENT_STATUS_COLLECTION_WORKFLOW.md   ← End-to-end process
  ├─ AGENT_STATUS_EXECUTION_CHECKLIST.md   ← Daily execution checklist
  ├─ AGENT_STATUS_COLLECTION_LOG.md        ← Tracking log (which agents submitted)
  ├─ AGENT_STATUS_SIGNOFF_TRACKER.md       ← Sign-off checklist
  ├─ AGENT_STATUS_UPDATE_RAG.md            ← Example: RAG agent submission
  └─ SPECS_CATALOG_VERIFICATION_REPORT.md  ← Deployment verification
```

---

## Deployment Process

### Auto-Deployment (Happens Automatically)
```
1. Developer commits to main branch
   $ git add specs-platform/index.html
   $ git commit -m "feat(specs): update agent status"
   $ git push origin main

2. Cloud Build detects push
   → Runs cloudbuild.yaml pipeline
   → Builds Docker image from Dockerfile
   → Pushes to Container Registry
   → Deploys to Cloud Run

3. Cloud Run serves the catalog
   → http.server from Python
   → Serves specs-platform/index.html
   → Static files (CSS, JS) included

4. Live on the web (~2 minutes)
   → https://mobius-specs-1032922478554.us-central1.run.app
   → All changes automatically reflected
```

### Check Deployment Status
```bash
# View recent builds
gcloud builds list --limit=5

# View logs of last build
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)')

# Check Cloud Run service
gcloud run services describe specs-platform --region=us-central1

# Verify catalog is live
curl -s https://mobius-specs-1032922478554.us-central1.run.app | grep "Last updated"
```

---

## How to Update the Catalog

### Step 1: Collect Agent Status
Send **AGENT_STATUS_BROADCAST.md** to agent owner with deadline (EOW Friday)

Include:
- AGENT_STATUS_UPDATE.md form
- AGENT_STATUS_SPEC.md framework
- AGENT_STATUS_CURRENT_SNAPSHOT.md (what catalog currently says)

### Step 2: Verify Submission
When agent submits, check against **AGENT_STATUS_SPEC.md** criteria:
```markdown
**Acceptance Criteria:**
- [ ] Status reflects TODAY's reality (not wishes)
- [ ] Dates are realistic (not best-case)
- [ ] Blockers actually exist
- [ ] Bugs listed are unfixed right now
```

If verification passes:
- Log in AGENT_STATUS_COLLECTION_LOG.md
- Mark as verified with date + confidence level
- Proceed to edit catalog

### Step 3: Edit specs-platform/index.html
Find the agent's section and update:

**Example: RAG Agent**
```html
<!-- BEFORE -->
<tr>
  <td><strong>5</strong></td>
  <td>Synthesis (compilation)</td>
  <td><span class="badge blocked">⏸️ v1 Built</span></td>
  <td>Awaiting AsyncSession threading</td>
</tr>

<!-- AFTER (from Retriever submission) -->
<tr>
  <td><strong>5</strong></td>
  <td>Synthesis (compilation)</td>
  <td><span class="badge live">✅ Live</span></td>
  <td>—</td>
</tr>
```

### Step 4: Commit with Agent Co-Author
```bash
git add specs-platform/index.html AGENT_STATUS_COLLECTION_LOG.md

git commit -m "feat(specs): update RAG agent status from verified sign-off

LIVE (verified 2026-08-11):
- Synthesis: live since 2026-07-24 (confirmed in every trace)
- Observer: live since 2026-07-26 (drives multi-turn decisions)
- Portfolio allocator: new, validated against greedy

BLOCKED:
- Observer wiring (awaiting Eval calibration plan)
- Filler d (DB url field missing)

Open bugs: P1 corpus gap (FL Medicaid), pytest-asyncio flakiness

Co-Authored-By: Retriever Agent <noreply@anthropic.com>"
```

### Step 5: Push to Deploy
```bash
git push origin main
# → Cloud Build auto-triggers (~2 min deploy time)
```

### Step 6: Verify Live
```bash
# Wait 2 minutes, then verify
curl -s https://mobius-specs-1032922478554.us-central1.run.app | grep "Last updated"
# Should show current date/time
```

---

## Current Status (2026-08-11)

### Deployed ✅
- Specs Catalog infrastructure live (Cloud Run)
- Git integration + auto-deploy working
- HTML structure for all 7 tabs (Overview, Governance, Surfaces, RAG Pipeline, Agents, Design, Onboarding)
- Agent status collection framework complete

### In Progress 🔨
- RAG agent status collected (Retriever + Master RAG verified)
- Cloud Build deploying latest changes (~2 min)
- Links refreshing from `/specs/` → GitHub URLs

### Tracking Documents Created
- ✅ AGENT_STATUS_SPEC.md (framework)
- ✅ AGENT_STATUS_UPDATE.md (form)
- ✅ AGENT_STATUS_BROADCAST.md (message to agents)
- ✅ AGENT_STATUS_COLLECTION_LOG.md (tracking)
- ✅ AGENT_STATUS_SIGNOFF_TRACKER.md (sign-offs)
- ✅ AGENT_STATUS_UPDATE_RAG.md (first agent submission)
- ✅ SPECS_CATALOG_VERIFICATION_REPORT.md (deployment health)

---

## Quarterly Update Schedule

**Standing Process:** Every 3 months (Oct 1–7, Jan 1–7, Apr 1–7, Jul 1–7)

### Timeline per Update Cycle
- **Day 1 (Monday):** PA sends AGENT_STATUS_BROADCAST to Phase 1 agents (gate owners)
- **Days 2–5:** Agents fill out forms, submit via GitHub issue or direct message
- **Day 5 (Friday EOW):** Deadline for Phase 1 submissions
- **Day 6–7 (Weekend):** PA verifies all submissions
- **Monday Week 2:** PA updates specs catalog, pushes to deploy
- **Monday Week 2 (AM):** Team sees live, updated status

**Process Repeats:** Same cadence every quarter

---

## Maintenance Checklist

### Weekly
- [ ] Spot-check catalog loads without errors
- [ ] Verify timestamp is current
- [ ] Check that any recent agent submissions are reflected

### Monthly
- [ ] Review all spec links for broken references
- [ ] Audit any "stale" status flags in tabs
- [ ] Confirm gate statuses match code reality

### Quarterly
- [ ] Send status update broadcast to all agents (Phase 1, 2, 3)
- [ ] Collect submissions following AGENT_STATUS_COLLECTION_WORKFLOW
- [ ] Verify all submissions
- [ ] Update catalog with new data
- [ ] Review for missing agents or incomplete sections

---

## Troubleshooting

### Links Return 404
**Problem:** Clicking spec links shows "File not found"

**Cause:** `/specs/` symlink not working in Cloud Run (symlinks don't resolve in container)

**Solution:** All links should point to GitHub URLs:
```html
<!-- ✅ Correct -->
<a href="https://github.com/ananthlk/Mobius-Master/blob/main/docs/observer-spec.md">

<!-- ❌ Wrong -->
<a href="/specs/observer-spec.md">
```

**Verify:** `curl https://mobius-specs-1032922478554.us-central1.run.app | grep "href=" | grep "github.com"`

### Status Not Updated After Commit
**Problem:** Made changes to index.html, pushed, but catalog still shows old status

**Cause:** Cloud Build hasn't completed deployment yet (takes ~2 min)

**Solution:** Wait 2–3 minutes, then refresh browser (Ctrl+R)

**Verify:** Check Cloud Build logs:
```bash
gcloud builds list --limit=5
gcloud builds log <BUILD_ID>
```

### Cloud Run Service Down
**Problem:** https://mobius-specs-1032922478554.us-central1.run.app returns error

**Cause:** Service crashed or quota exceeded

**Solution:** Restart Cloud Run service:
```bash
gcloud run deploy specs-platform \
  --image gcr.io/mobius-os-dev/specs-platform \
  --region us-central1 \
  --platform managed
```

---

## Key Contacts

- **PA Architect (Catalog Owner):** Ananth (ananth.lalithakumar@gmail.com)
- **Cloud Infrastructure:** GCP Project: mobius-os-dev
- **Git Repository:** https://github.com/ananthlk/Mobius-Master
- **Cloud Build:** Automated on push to main

---

## Document Versions

| Document | Version | Status | Last Updated |
|----------|---------|--------|--------------|
| AGENT_STATUS_SPEC.md | 1.0 | LIVE | 2026-08-11 |
| AGENT_STATUS_UPDATE.md | 1.0 | LIVE | 2026-08-11 |
| AGENT_STATUS_BROADCAST.md | 1.0 | LIVE | 2026-08-11 |
| AGENT_STATUS_COLLECTION_WORKFLOW.md | 1.0 | LIVE | 2026-08-11 |
| AGENT_STATUS_COLLECTION_LOG.md | 1.0 | LIVE | 2026-08-11 |
| SPECS_CATALOG_VERIFICATION_REPORT.md | 1.0 | LIVE | 2026-08-11 |
| SPECS_CATALOG_SETUP_PROCESS.md | 1.0 | LIVE | 2026-08-11 |

---

**Owner:** PA Architect  
**Last Updated:** 2026-08-11  
**Next Quarterly Review:** 2026-10-01
