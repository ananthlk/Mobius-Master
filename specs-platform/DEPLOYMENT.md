# Mobius Specs Catalog — Deployment Guide

**This is the persistent, team-owned source of truth for all product specs, governance, and acceptance criteria.**

---

## What This Is

A **Cloud Run web application** that serves an interactive specs catalog. Team members can:
- Browse all product specs by category (Governance, Surfaces, RAG, Agents, Design)
- Review acceptance criteria before shipping features
- Track sign-offs and blockers
- Use it as the onboarding checklist for new team members

**URL:** `https://mobius-specs.example.com` (or your GCP project URL)

---

## Architecture

```
specs-platform/
├── index.html              # Interactive HTML dashboard
├── Dockerfile              # Cloud Run container definition
├── cloudbuild.yaml         # CI/CD pipeline configuration
├── DEPLOYMENT.md           # This file
└── specs/                  # Symbolic links to /docs specs (Git maintains these)
    ├── mobius-model.md
    ├── mobius-thesis.md
    ├── rag-backend.md
    ├── appeals-agent-spec.md
    └── ...
```

**Data flow:**
1. Specs are authored in `/docs` and version-controlled in Git
2. `specs-platform/specs/` is a **symbolic link** to `/docs` (so specs auto-update)
3. On `git push` to `main`, Cloud Build triggers automatically
4. Dockerfile packages everything into a container
5. Cloud Run deploys the container (publicly accessible)
6. Users visit the URL to browse specs (always latest)

---

## Setup (One-Time)

### 1. Create Cloud Run Service

```bash
gcloud run create mobius-specs \
  --image=gcr.io/YOUR_PROJECT_ID/mobius-specs:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1
```

### 2. Set Up Cloud Build Trigger

In the [Cloud Console](https://console.cloud.google.com/cloud-build/triggers):

1. **New Trigger**
2. Name: `mobius-specs-deploy`
3. Event: `Push to branch`
4. Repository: `Mobius-Master` (your GitHub repo)
5. Branch: `^main$`
6. Build configuration: `Cloud Build configuration file (yaml)`
7. Location: `specs-platform/cloudbuild.yaml`
8. Included files filter: `specs-platform/**`

### 3. Link Specs

Create a symbolic link so specs auto-update:

```bash
cd specs-platform
ln -s ../docs specs
git add specs
git commit -m "chore: link specs directory"
git push
```

---

## Deployment

### Automatic (Every Commit to main)

1. Push to `main` → Cloud Build triggers automatically
2. Build → Push to Container Registry → Deploy to Cloud Run
3. Live in ~2 minutes

### Manual Deploy

```bash
gcloud run deploy mobius-specs \
  --image=gcr.io/YOUR_PROJECT_ID/mobius-specs:latest \
  --region=us-central1 \
  --allow-unauthenticated
```

---

## Adding New Specs

1. **Author the spec** in `/docs/product-docs/` or `/docs/rag-agents/` (or root `/docs/`)
2. **Commit & push** to `main`
3. **Cloud Build redeploys automatically** → New spec is live

The symlink means specs are **always current** without extra steps.

---

## Linking from Chat & Other Systems

### In Product Docs

Reference the catalog:
```markdown
See the [Specs Catalog](https://mobius-specs.example.com) for the authoritative sign-off status on all features.
```

### In Chat Help

When a user asks "what specs are there?", point them to:
```
https://mobius-specs.example.com
```

### For Onboarding

Share the **Onboarding** tab directly:
```
https://mobius-specs.example.com#onboarding
```

---

## Versioning & Git Integration

Each deployed version is tagged with the Git commit SHA:

```bash
# View deployed version
gcloud run describe mobius-specs --region=us-central1 --format='value(status.image)'

# Shows: gcr.io/PROJECT_ID/mobius-specs:abc1234 (commit SHA)
```

This means:
- **Every deployment is traceable** to a git commit
- **Rollback is one command** (re-deploy an old SHA)
- **No manual upload needed** — Git is the source of truth

---

## Maintenance

### Update Product Docs

1. Edit `/docs/product-docs/mobius-chat.md`, `/docs/rag-backend.md`, etc.
2. Commit and push → Specs catalog updates automatically

### Update Catalog Index

The `index.html` file is the catalog dashboard. Edit it to:
- Add new sections
- Adjust categories
- Update acceptance criteria checklists
- Change navigation structure

On next push to `main`, changes go live.

### Monitor Deployment

```bash
# View recent deployments
gcloud run revisions list --service=mobius-specs --region=us-central1

# View logs
gcloud run logs read mobius-specs --region=us-central1 --limit=50
```

---

## Troubleshooting

### Cloud Build Fails

Check the build logs:
```bash
gcloud builds list --filter='name:mobius-specs' --limit=5
gcloud builds log BUILD_ID  # Replace BUILD_ID from above
```

Common issues:
- **`specs/` symlink broken** → Fix: `cd specs-platform && ln -s ../docs specs`
- **Dockerfile path wrong** → Check: cloudbuild.yaml has `-f specs-platform/Dockerfile`
- **GCP permissions** → Ensure Cloud Build has permission to deploy to Cloud Run

### Specs Not Updating

1. Check that specs are committed to `/docs/`
2. Verify symlink exists: `ls -la specs-platform/specs/`
3. Wait 2 minutes for Cloud Build to complete
4. Refresh browser (Ctrl+Shift+R to clear cache)

### Need to Rollback

```bash
# Get old SHA
gcloud builds list --filter='name:mobius-specs' --limit=10

# Re-deploy old version
gcloud run deploy mobius-specs \
  --image=gcr.io/YOUR_PROJECT_ID/mobius-specs:OLD_SHA \
  --region=us-central1
```

---

## Access Control (Optional)

By default, the specs catalog is **public and unauthenticated**. To restrict access:

```bash
gcloud run deploy mobius-specs \
  --no-allow-unauthenticated \
  --region=us-central1

# Share the link only with your team
# Access is gated by Google Cloud Identity (your company Google account)
```

---

## Custom Domain (Optional)

To serve at `https://specs.mobius.company.com`:

1. Set up a Cloud Load Balancer (or use Cloud Run domain mapping)
2. Point DNS to the load balancer
3. Configure SSL certificate

See [Cloud Run Custom Domains](https://cloud.google.com/run/docs/mapping-custom-domains).

---

## Backup & Compliance

- **Git is the source of truth** — all specs are version-controlled
- **Cloud Build logs** are archived (searchable audit trail)
- **Container Registry** keeps all image versions (cheap to store)
- **No data loss** — specs live in Git, not on a server

---

## Questions?

For deployment issues or feature requests:
1. File an issue in the repo: `mobius/specs-platform/issues`
2. Or ask the PA Architect

---

**Status:** ✅ Ready for deployment  
**Last updated:** 2026-08-11
