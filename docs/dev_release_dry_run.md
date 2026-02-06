# Dev Dry-Run Playbook

Purpose: rehearse the production build end-to-end against the development (or staging) environment so scripts, infrastructure, and checklist coverage are battle-tested before the first production release.

> Run this document together with `docs/production_build_checklist.md`. Treat the dry-run as a gated rehearsal—if a step fails in dev, fix it here before scheduling the production window.

---

## 1. Establish Dev ↔ Prod Parity

| Step | Owner | Action | Notes |
| --- | --- | --- | --- |
| 1.1 | Dev Infra | Clone `mobius-config/.env.example` to `.env` with **dev values that mirror prod variable names** (Vertex, GCS, Cloud SQL, Redis, JWT). | Use `mobius-config/env_helper.py` to inject shared env across repos. |
| 1.2 | Dev Infra | Provision dev Cloud SQL databases matching prod (`mobius`, `mobius_rag`, `mobius_chat`, `mobius_user`). | Follow [`mobius-rag/docs/GCP_DEPLOYMENT.md`](mobius-rag/docs/GCP_DEPLOYMENT.md) steps; enable `pgvector` where required. |
| 1.3 | Dev Infra | Ensure dev service account permissions ⟶ `roles/cloudsql.client`, `roles/aiplatform.user`, `roles/storage.objectAdmin`. | Reuse the shared SA model from production; separate key if needed. |
| 1.4 | Dev Infra | Mirror storage + Vertex resources (GCS bucket, Vertex Vector Search index, Vertex model). | Populate with non-prod data so RAG/chat flows can execute. |
| 1.5 | Dev Leads | Confirm each repo has a dev branch/tag that tracks the intended production commit candidate. | Document SHAs for manifest in Section 3. |

---

## 2. Run Production Checklist Against Dev Targets

1. Open `docs/production_build_checklist.md`.
2. For each row, substitute dev infrastructure (e.g., Cloud SQL dev instance, dev GCS bucket) and execute the same command.
3. Capture evidence (command output, screenshots) in a shared Dry-Run log (e.g., `docs/release_logs/2026-02-dev.md`).
4. Record any failures or manual workarounds; they feed into Section 5.

---

## 3. Build the Dev Release Manifest

1. Create `release-manifests/<date>-dev.yaml` using the template below.
2. Populate with:
   - Git commit SHAs or annotated tags per repo (`mobius-os`, `mobius-rag`, `mobius-chat`, `mobius-dbt`, `mobius-auth`, `mobius-skills`, `mobius-user`, `mobius-qa`).
   - Target container image tags (if pre-built) or let Cloud Build derive from SHA.
   - Database migration revisions (Alembic revision IDs, SQL script names).
   - Feature flags / configuration toggles required for the release.
3. Store the manifest in git for traceability; Cloud Build (or other orchestrator) should read this file to determine deploy inputs.

**Template (`release-manifests/dev-release-template.yaml`):**

```yaml
release_id: YYYY-MM-DD-dev
description: Dry-run rehearsal for first production build

commits:
  mobius-os: <git-sha-or-tag>
  mobius-rag: <git-sha-or-tag>
  mobius-chat: <git-sha-or-tag>
  mobius-dbt: <git-sha-or-tag>
  mobius-auth: <git-sha-or-tag>
  mobius-skills: <git-sha-or-tag>
  mobius-user: <git-sha-or-tag>
  mobius-qa: <git-sha-or-tag>

images:
  mobius-os-backend: gcr.io/<project>/mobius-os-backend:<tag>
  mobius-rag-backend: gcr.io/<project>/mobius-rag-backend:<tag>
  mobius-rag-worker: gcr.io/<project>/mobius-rag-worker:<tag>
  mobius-chat-api: gcr.io/<project>/mobius-chat-api:<tag>
  mobius-chat-worker: gcr.io/<project>/mobius-chat-worker:<tag>
  mobius-skills-scraper: gcr.io/<project>/mobius-skills-scraper:<tag>

migrations:
  mobius-os: <alembic_revision_id>
  mobius-rag: [python:add_publish_tables, sql:add_error_tracking.sql]
  mobius-user: <alembic_revision_id>
  mobius-chat: db/schema/002_published_rag_metadata.sql

feature_flags:
  chat_live_stream: true
  rag_publish_gate: true
```

---

## 4. Execute the Orchestrated Pipeline in Dev

1. **Prepare the release orchestrator** (e.g., `cloudbuild-release.yaml` in the umbrella repo):
   - Step 1: fetch manifest + checkout each repo at the manifest SHAs.
   - Step 2: build container images or run existing `deploy.sh` scripts with dev substitutions.
   - Step 3: run database migrations against dev Cloud SQL instances.
   - Step 4: redeploy supporting services (workers, dbt jobs, scraper) using dev configs.
2. **Trigger the pipeline** with the dev manifest:
   ```bash
   gcloud builds submit . \
     --config cloudbuild-release.yaml \
     --substitutions=_RELEASE_MANIFEST=release-manifests/2026-02-dev.yaml
   ```
3. Monitor Cloud Build (or equivalent) logs; collect the final status URL for the dry-run report.

---

## 5. Validate End-to-End Behaviour

1. Export dev endpoints (e.g., `DEV_OS_URL`, `DEV_RAG_URL`, `DEV_CHAT_URL`).
2. Run the verification script (update prod URLs → dev URLs):
   ```bash
   ./verify_production.sh \
     --os-url "$DEV_OS_URL" \
     --rag-url "$DEV_RAG_URL" \
     --chat-url "$DEV_CHAT_URL" \
     --scraper-url "$DEV_SCRAPER_URL"
   ```
   > If you haven’t parameterised the script yet, run the commands inline replacing the curl targets manually.
3. Execute a limited `mobius-qa` test sweep:
   ```bash
   cd mobius-qa/mobius-chat-qa
   python chat_bot.py --config chat_bot_config.dev.yaml --limit 15 --report reports/dev-dry-run.md
   ```
4. Review dbt run results (`target/run_results.json`, BigQuery job history) to confirm RAG → Chat sync works end-to-end.

---

## 6. Capture Learnings & Update Artifacts

1. Summarise incidents, manual patches, and missing automation in a retrospective doc (e.g., `docs/release_logs/2026-02-dev.md`).
2. Update:
   - `docs/production_build_checklist.md` (add new checks uncovered by the dry-run).
   - Deployment scripts (e.g., make `mobius-os/deploy.sh` non-interactive if Cloud Build needs env vars).
   - Release manifest template (add/remove fields based on actual needs).
3. Log outstanding gaps with owners and due dates before approving the production window.

---

## 7. Exit Criteria

- All sections above completed without manual hotfixes.
- Verification + QA suites pass and evidence stored.
- Updated checklist + scripts committed.
- Release commander signs off dev dry-run report and schedules the production build rehearsal.
