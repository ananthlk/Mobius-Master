# Deploying the Module Hub to GCP

The **Module Hub** is the landing/dashboard server that shows status of Mobius processes (OS, Chat, RAG, DBT), workers (Chat worker, Scraper, RAG chunking/embedding), and dependencies (Redis). It probes health endpoints and provides links to each module. In production on GCP, modules run as separate services (e.g. Cloud Run) with public or internal URLs. The same dashboard works in both dev and production by using **configurable URLs** and **feature flags** so control actions (Stop/Restart/Start all, Logs, Start Redis) are disabled in production.

---

## Environment variables

Set these when running the landing server (or in Cloud Run env vars when deployed).

| Variable | Default (dev) | Description |
|----------|----------------|-------------|
| `ENV` | `dev` | Set to `prod` for production: binds `0.0.0.0`, uses `PORT`, disables control actions and log streaming. |
| `PORT` | `3999` (dev) / `8080` (prod) | HTTP port. Cloud Run sets `PORT` (e.g. 8080). |
| `MOBIUS_OS_URL` | `http://127.0.0.1:5001` | OS backend probe and dashboard link. |
| `MOBIUS_CHAT_URL` | `http://127.0.0.1:8000` | Chat API probe and link. |
| `MOBIUS_RAG_BACKEND_URL` | `http://127.0.0.1:8001` | RAG backend health probe. |
| `MOBIUS_RAG_FRONTEND_URL` | `http://127.0.0.1:5173` | RAG frontend (dashboard card link). |
| `MOBIUS_DBT_URL` | `http://127.0.0.1:6500` | DBT API probe and link. |
| `MOBIUS_SCRAPER_URL` | `http://127.0.0.1:8002` | Scraper API probe and link. |
| `MOBIUS_REDIS_HOST` | `127.0.0.1` | Redis host for status check (e.g. Cloud Memorystore IP in prod). |
| `MOBIUS_REDIS_PORT` | `6379` | Redis port. |

If a variable is unset, dev defaults keep the current localhost behavior. In production, set all `MOBIUS_*_URL` (and Redis host/port if you check Redis) so the dashboard probes and card links point to your GCP service URLs.

---

## Production behavior

When `ENV=prod`:

- **Bind:** Server listens on `0.0.0.0` and `PORT` (e.g. 8080) for Cloud Run.
- **Controls disabled:** Stop all, Start all, and per-card Stop/Restart are hidden in the UI and return 404 if called.
- **Logs disabled:** `/api/logs` and `/api/logs/stream` return 404; "Logs" is hidden in the dashboard.
- **Start Redis disabled:** "Start Redis" is hidden (managed Redis in prod).
- **Status and links:** Probes and card links use the configured `MOBIUS_*_URL` and Redis host/port.

---

## Deploy to Cloud Run

### Prerequisites

- `gcloud` CLI installed and authenticated.
- GCP project with Cloud Run and Container Registry (or Artifact Registry) enabled.

### Option 1: Deploy script (recommended)

From the repo root:

```bash
./scripts/deploy_module_hub_cloudrun.sh
```

Optional: set service URLs (and Redis) before running so the deployed dashboard points to your GCP services:

```bash
MOBIUS_OS_URL=https://os-xxx.run.app \
MOBIUS_CHAT_URL=https://chat-xxx.run.app \
MOBIUS_RAG_BACKEND_URL=https://rag-xxx.run.app \
MOBIUS_RAG_FRONTEND_URL=https://rag-fe-xxx.run.app \
MOBIUS_DBT_URL=https://dbt-xxx.run.app \
MOBIUS_SCRAPER_URL=https://scraper-xxx.run.app \
MOBIUS_REDIS_HOST=10.x.x.x \
MOBIUS_REDIS_PORT=6379 \
./scripts/deploy_module_hub_cloudrun.sh
```

Script defaults: `GCP_PROJECT_ID=mobiusos-new`, `GCP_REGION=us-central1`. Override with env vars if needed.

### Option 2: Manual build and deploy

1. **Build the image** (from repo root):

   ```bash
   docker build -f Dockerfile.module-hub -t gcr.io/YOUR_PROJECT_ID/module-hub:latest .
   docker push gcr.io/YOUR_PROJECT_ID/module-hub:latest
   ```

   Or with Cloud Build:

   ```bash
   gcloud builds submit --config=cloudbuild.module-hub.yaml --project=YOUR_PROJECT_ID .
   ```

2. **Deploy to Cloud Run:**

   ```bash
   gcloud run deploy module-hub \
     --image=gcr.io/YOUR_PROJECT_ID/module-hub:latest \
     --region=us-central1 \
     --platform=managed \
     --allow-unauthenticated \
     --memory=256Mi \
     --set-env-vars="ENV=prod,PORT=8080" \
     --set-env-vars="MOBIUS_OS_URL=...,MOBIUS_CHAT_URL=...,..." \
     --project=YOUR_PROJECT_ID
   ```

Set all `MOBIUS_*_URL` (and Redis host/port if applicable) in `--set-env-vars` so the dashboard works correctly in production.

---

## Files

- **Landing server:** `landing_server.py` — serves dashboard, `/api/status`, `/api/config`, and (in dev) control and log endpoints.
- **Dashboard UI:** `landing/index.html` — fetches `/api/config` on load, sets card hrefs from config, hides controls when `controls_enabled` is false.
- **Image:** `Dockerfile.module-hub` — minimal Python image; copies `landing_server.py` and `landing/`.
- **Build:** `cloudbuild.module-hub.yaml` — Cloud Build config to build with `Dockerfile.module-hub`.
- **Deploy:** `scripts/deploy_module_hub_cloudrun.sh` — build and deploy to Cloud Run with optional env vars.

After deployment, open the Module Hub URL to see status and links for all GCP-deployed modules from one place.
