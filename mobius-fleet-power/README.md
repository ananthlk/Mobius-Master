# mobius-fleet-power

Cloud Run fleet power manager. Keeps the fleet's **pinned capacity** (min/max
instances) matching a desired-state manifest, and audits spend.

Born from the Sep 2026 cost audit: two RAG workers were silently pinned at
8 and 6 instances of 4vCPU/8Gi always-allocated CPU (~$3,200/mo, 83% of the
bill) by a **service-level** `run.googleapis.com/minScale` annotation that
`gcloud run services update --min=8` sets and later deploys never clear.
Unused services were not the problem — anything at min=0 with no traffic
costs ~$0. The money is always in pinned instances and always-allocated CPU.

## Usage

```bash
python3 fleetpower.py status            # manifest vs live + live instance counts; exit 1 on drift
python3 fleetpower.py apply --dry-run   # show what would change
python3 fleetpower.py apply             # enforce fleet.yaml (service-level --min/--max, no redeploys)
python3 fleetpower.py audit --days 7    # billable hrs vs requests, est. $/mo, waste flags
python3 fleetpower.py boost mobius-rag-chunking-worker --min 8   # ingest sprint; revert = apply
```

Requires: gcloud authed to the project, python3 + pyyaml.

## The manifest (fleet.yaml)

Each service gets a `mode` (`off` / `standby` / `active` / `pinned`, defined at
the top) and optional explicit `min`/`max` overrides. Services not listed are
reported UNMANAGED and never touched. To change fleet scaling, edit fleet.yaml
and run `apply` — don't run raw gcloud, or status will (correctly) nag about drift.

## Sharp edges learned the hard way

- **Two scaling layers.** Revision-level `autoscaling.knative.dev/minScale`
  (set by `--min-instances` at deploy) and service-level
  `run.googleapis.com/minScale` (set by `--min`) pin instances independently;
  the effective floor is the max of both. fleetpower reads both. Lowering a
  revision-level min requires a new revision → gated behind `--allow-redeploy`.
- **Poll-loop workers must not hit min=0.** mobius-rag-{chunking,embedding}-worker
  process their queue from a background thread; min=0 stops all queue polling.
  min=1 is the floor until event-driven wake exists.
- **audit flags, not verdicts.** `WASTE?` = instance-hours far beyond both the
  pin and the traffic; `PINNED-IDLE` = warm floor with almost no requests.
  Both are prompts to reconsider the manifest entry, not automatic actions.
- **A service whose image tag was pruned** (e.g. mobius-specs, `:latest` gone
  from GCR) fails *any* update with "image not found". Redeploy the image first.
- **Cost model** is us-central1 tier-1 list price; throttled services' idle
  min instances bill below the request rate, so estimates are an upper bound.

## Wishlist / next steps

- Nightly `audit` + `status` via Cloud Scheduler or the standup routine, so a
  re-pinned worker gets caught in a day, not a month.
- Event-driven wake for the RAG workers (enqueue → POST → drain → scale to 0)
  to reclaim the last ~$460/mo of standby cost.
