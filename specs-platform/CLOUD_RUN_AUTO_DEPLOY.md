# Cloud Run Continuous Deployment (No Docker)

**Setup Cloud Run to auto-deploy from git — commit → live in seconds**

---

## Current State

Specs catalog running on Cloud Run:
- **Service:** specs-platform
- **Region:** us-central1
- **Image:** Container Registry (built via Cloud Build)

---

## New Approach: Auto-Deploy from Git

**No Docker build step, no Cloud Build, no Container Registry.**

Just: `git push` → Cloud Run detects → auto-deploys (instant)

---

## Setup Steps

### 1. Connect Cloud Run to Git Repository

```bash
# Delete old Cloud Build trigger (optional, keeps auto-build off)
gcloud builds triggers delete specs-platform-auto-build --region=us-central1

# Create new Cloud Run service with git source (use gcloud CLI)
gcloud run deploy specs-platform \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --runtime python311 \
  --entry-point "python specs-platform/server.py"
```

OR use Google Cloud Console:

1. Go to Cloud Run → Create Service
2. **Select "Continuously deploy from a repository"**
3. **Repository:** ananthlk/Mobius-Master
4. **Branch:** main
5. **Source type:** Python
6. **Runtime:** Python 3.11
7. **Entry point:** `python specs-platform/server.py`
8. **Deploy**

### 2. Verify Auto-Deploy is Enabled

In Cloud Run service settings:
- **Continuous deployment:** Enabled ✓
- **Repository:** ananthlk/Mobius-Master
- **Branch:** main
- **Directory:** `/specs-platform/`

### 3. Test Auto-Deployment

```bash
# Make a change to specs-platform/ or docs/
echo "# Updated" >> docs/README.md

# Commit and push
git add docs/README.md
git commit -m "test: verify auto-deploy"
git push origin main

# Watch Cloud Run logs
gcloud run logs read specs-platform --region us-central1 --limit 50

# Check service status
gcloud run services describe specs-platform --region us-central1
```

---

## How It Works

### Old Flow (Cloud Build + Docker)
```
git push
  ↓
Cloud Build trigger fires
  ↓
Build Docker image (2 min)
  ↓
Push to Container Registry
  ↓
Cloud Run deploys image
  ↓
Catalog live (5 min total)
```

### New Flow (Cloud Run Direct)
```
git push
  ↓
Cloud Run detects change
  ↓
Pulls source from git
  ↓
Runs Python buildpack
  ↓
Starts server (server.py)
  ↓
Catalog live (30 sec)
```

---

## What Happens on Deploy

1. Cloud Run pulls latest source from main branch
2. Detects Python (`specs-platform/server.py`)
3. Runs buildpack:
   - Installs Python 3.11
   - Reads `specs-platform/requirements.txt`
   - Installs dependencies (none in our case)
4. Starts process: `python specs-platform/server.py`
5. Server listens on `$PORT` (8080 by default)
6. Serves index.html + proxies /specs/* to GitHub

---

## Specs Update Flow

**Now:**
1. Update docs → `git add docs/`
2. Commit → `git commit -m "docs: update..."`
3. Push → `git push origin main`
4. Watch Cloud Run logs: `gcloud run logs read specs-platform --region us-central1 --tail -f`
5. Specs live (30 sec later)

**User experience:**
- Click link in catalog → sees spec
- Spec always current (fetched from git)
- No manual deployment needed

---

## Benefits

✅ **No Docker:** Python runs directly  
✅ **No Container Registry:** No images to manage  
✅ **No Cloud Build:** No build step  
✅ **Auto-Deploy:** Push → live in 30s  
✅ **Specs from Git:** Always current  
✅ **Instant Changes:** Commit message changes specs instantly  

---

## Disable Auto-Deploy (if needed)

```bash
# Revert to manual deployment
gcloud run deploy specs-platform \
  --source . \
  --region us-central1 \
  --no-gen2  # Disable Cloud Run Gen2 features if needed
```

Or use Cloud Console: Service → Settings → Disable continuous deployment

---

## Environment Variables (if needed)

If server.py needs env vars:

```bash
gcloud run deploy specs-platform \
  --set-env-vars PORT=8080,GITHUB_REPO=ananthlk/Mobius-Master \
  --region us-central1
```

---

## Logs & Monitoring

```bash
# Watch live logs
gcloud run logs read specs-platform --region us-central1 --tail -f

# See deployment history
gcloud run revisions list --service specs-platform --region us-central1

# Check service status
gcloud run services describe specs-platform --region us-central1
```

---

## FAQ

**Q: What if my commit has errors?**  
A: Cloud Run deployment fails, service stays on previous version. Fix commit, push again.

**Q: Can I rollback?**  
A: Yes. Cloud Run keeps revision history. `gcloud run revisions list` → pick old revision → set as traffic target.

**Q: What if GitHub is down?**  
A: Cloud Run can't pull source, deployment fails. Service stays on previous version. Retry when GitHub is back.

**Q: Can I still use Docker if I want?**  
A: Yes. Keep Dockerfile, use `--source .` with Docker option. But auto-deploy is faster without it.

**Q: Where does it pull from?**  
A: GitHub main branch, `/specs-platform/` directory. Ignores everything else.

---

## Cost

Cloud Run charges:
- **Memory:** 256MB (default)
- **CPU:** 1 vCPU (default, allocated when handling requests)
- **Requests:** $0.40 per million requests
- **Free tier:** 2M requests/month

Specs catalog typically: <100 req/day → **Well under free tier**

---

## Next Steps

1. **Setup:** Run `gcloud run deploy` command above with `--source .` flag
2. **Verify:** Check Cloud Run console → Continuous Deployment enabled
3. **Test:** Make a small commit, watch it deploy
4. **Done:** No more manual Docker builds

**From then on: Just `git push` and specs are live**

---

**Owner:** PA Architect  
**Setup Date:** 2026-08-11  
**Status:** Ready to configure
