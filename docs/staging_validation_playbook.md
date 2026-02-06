# Staging Validation Playbook

Run this checklist after deploying all services to the staging project. It reuses the dry-run workflow in [docs/dev_release_dry_run.md](dev_release_dry_run.md) with staging-specific URLs and manifests.

---

## 1. Prepare Environment Variables

```bash
export STAGING_PROJECT_ID=mobius-staging
export REGION=us-central1

export STAGING_OS_URL=https://mobius-os-backend-<hash>-uc.a.run.app
export STAGING_RAG_URL=https://mobius-rag-<hash>-uc.a.run.app
export STAGING_CHAT_URL=https://mobius-chat-api-<hash>-uc.a.run.app
export STAGING_SCRAPER_URL=https://mobius-skills-scraper-<hash>-uc.a.run.app
export STAGING_DBT_URL=https://mobius-dbt-ui-<hash>-uc.a.run.app
export STAGING_MODULE_HUB_URL=https://module-hub-<hash>-uc.a.run.app
```

Record these in `docs/release_logs/YYYY-MM-staging.md`.

---

## 2. Smoke Tests (`verify_production.sh`)

Parameterize the verification script for staging endpoints:

```bash
./verify_production.sh \
  --env staging \
  --os-url "$STAGING_OS_URL" \
  --rag-url "$STAGING_RAG_URL" \
  --chat-url "$STAGING_CHAT_URL" \
  --scraper-url "$STAGING_SCRAPER_URL" \
  --dbt-url "$STAGING_DBT_URL"
```

If the script lacks flags, temporarily export environment variables inside the script or run the listed commands manually.

Capture output (pass/fail) and attach to the staging release log.

---

## 3. Mobius QA Regression

```bash
cd mobius-qa/mobius-chat-qa
python chat_bot.py \
  --config chat_bot_config.staging.yaml \
  --limit 15 \
  --report reports/staging-smoke-$(date +%Y%m%d).md
```

Ensure the config points to `STAGING_CHAT_URL` and uses staging auth tokens/secrets if required.

---

## 4. dbt Validation

Run the pipeline in staging mode:

```bash
cd mobius-dbt
./scripts/land_and_dbt_run.sh
```

Confirm:
- BigQuery landing/mart tables updated in the staging dataset.
- `dbt test` passes.
- Optional: run `python scripts/sync_mart_to_chat.py` against staging `CHAT_DATABASE_URL` and Vertex IDs.

---

## 5. Module Hub Status

Open the staging Module Hub and verify:
- All services show **green**.
- Redis status is OK (staging Memorystore).
- Links navigate to staging URLs only.

Take a screenshot for the release log.

---

## 6. Checklist Updates

1. Update `docs/production_build_checklist.md` with any new steps discovered during staging validation (e.g., additional secrets, migrations).
2. Update staging-specific documentation (e.g., `mobius-config/.env.staging`) if values changed.
3. File issues for any failing checks and block production promotion until resolved.

---

## 7. Sign-off

- Add a summary to `docs/release_logs/YYYY-MM-staging.md`: manifest, build trigger URL, QA report path, verify script output.
- Have the release commander confirm staging success before copying the manifest to production.
- Schedule production release window once staging is green.
