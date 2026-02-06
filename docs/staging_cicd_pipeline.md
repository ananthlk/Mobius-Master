# Staging CI/CD Pipeline

Goal: automatically build and deploy every Mobius service to the staging project before changes reach production. The pipeline mirrors production releases but targets `mobius-staging`.

---

## 1. Release Manifest

Create manifests under `release-manifests/` using the staging template (`release-manifests/staging-release-template.yaml`). Each release should capture:

- Repo SHAs / tags per module
- Container image tags (optional if built inline)
- Database migration identifiers
- Feature flags and env overrides

Store manifests in git for traceability and promotion to production.

---

## 2. Cloud Build Configuration

Add a new build config at the repo root (example: `cloudbuild.staging.yaml`):

```yaml
steps:
  - id: "Checkout umbrella repo"
    name: gcr.io/cloud-builders/git
    args: ["clone", "https://source.of.truth/Mobius.git", "."]

  - id: "Load release manifest"
    name: gcr.io/cloud-builders/gcloud
    entrypoint: "bash"
    args:
      - "-c"
      - |
        MANIFEST_PATH=${_RELEASE_MANIFEST}
        echo "Using manifest: $MANIFEST_PATH"
        cat "$MANIFEST_PATH"

  - id: "Build & deploy mobius-os"
    name: gcr.io/$PROJECT_ID/cloud-builders/gcloud
    entrypoint: bash
    args:
      - "-c"
      - |
        ./mobius-os/scripts/build_and_deploy_staging.sh "$MANIFEST_PATH"

  # Repeat for mobius-rag, mobius-chat, mobius-dbt, mobius-skills, module hub...

options:
  logging: CLOUD_LOGGING_ONLY

substitutions:
  _RELEASE_MANIFEST: release-manifests/2026-02-staging.yaml
```

> Prefer dedicated helper scripts per module to keep the Cloud Build YAML concise.

---

## 3. Triggers

Create Cloud Build triggers (one-time setup):

```bash
gcloud beta builds triggers create webhook \
  --project="$STAGING_PROJECT_ID" \
  --name="mobius-staging-release" \
  --inline-config=cloudbuild.staging.yaml \
  --substitutions=_RELEASE_MANIFEST=release-manifests/2026-02-staging.yaml \
  --description="Deploy Mobius services to staging with manifest"
```

Alternatively, use a **manual trigger** (UI or CLI) that accepts `_RELEASE_MANIFEST` so you can deploy any manifest file.

---

## 4. Credentials & Identities

- **Build Identity:** set trigger to run as `mobius-cicd-staging@` (see `[docs/staging_iam_and_secrets.md](staging_iam_and_secrets.md)`).
- **Secret Access:** ensure the CI/CD service account has `roles/secretmanager.secretAccessor` and `roles/cloudsql.client`.
- **Cloud Run Deploy:** use `--service-account=mobius-platform-staging@...` or ensure each deploy command passes it.

---

## 5. Artifact Handling

You can either:
- Build images inside Cloud Build and push to `gcr.io/mobius-staging/...`, or
- Promote pre-built artifacts referenced in the manifest.

Example build step:

```bash
gcloud builds submit mobius-chat \
  --tag gcr.io/$STAGING_PROJECT_ID/mobius-chat-api:${COMMIT_SHA}
```

Store `COMMIT_SHA` or tag in the manifest for reproducibility.

---

## 6. Promotion Flow

1. Merge feature branches to `main`.
2. Create/update staging manifest.
3. Kick off staging trigger with `_RELEASE_MANIFEST`.
4. Validate staging (Section 6 below).
5. Once verified, copy manifest to `release-manifests/<date>-prod.yaml` (adjust project IDs) and run production pipeline.

---

## 7. Monitoring & Notifications

- Enable Cloud Build notifications (Pub/Sub → Slack/email) for staging trigger success/failure.
- Keep Cloud Run metrics dashboards (latency, error rate) filtered to staging project.

---

## 8. Documentation

Log each staging release:

- `docs/release_logs/YYYY-MM-staging.md` containing manifest filename, trigger ID, build log URL, deploy URLs, and verification status.
- Update `docs/production_build_checklist.md` to reference the staging pipeline as a prerequisite.

---

## 9. Future Enhancements

- Parameterize `cloudbuild.staging.yaml` to accept `_GIT_REF` for branch-specific deployments.
- Introduce automated canary checks (smoke tests) as additional Cloud Build steps.
- Integrate Terraform or Deployment Manager for infrastructure drift detection prior to deploy.
