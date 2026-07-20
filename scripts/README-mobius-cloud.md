# Mobius dev cost parking

Stop paying for the GCP dev environment when you're not building.

## What it does

`mobius-cloud.sh` flips exactly the resources that cost money while idle:

- **Cloud SQL** (`mobius-platform-dev-db`) — stops it (`activation-policy=NEVER`),
  which halts compute billing (~$99/mo). Storage still bills (~$30/mo).
- **Every Cloud Run service with `min-instances > 0`** — `down` snapshots each
  one's current min to `.mobius-cloud-parked.state`, then sets it to 0 (scale to
  zero, free at idle). `up` restores each service to exactly its snapshotted
  value, then deletes the snapshot.

Services are **discovered dynamically** — no hardcoded list to drift. Because
`up` restores the snapshot, the script never fights whatever set those values
(e.g. the nightly pipeline, which scales the rag workers up for a run and back
to 0). Everything already at min=0 is left untouched. **Nothing is deleted**;
`down` is fully reversible via `up`.

> ⚠️ **Shared environment.** `down` stops Cloud SQL and zeroes services other
> live agent sessions may be using — only park when the fleet is idle (end of
> day), not mid-work.

## Usage

```bash
cd /Users/ananth/Mobius
./scripts/mobius-cloud.sh down     # done for the day — stop the meter
./scripts/mobius-cloud.sh up       # about to build — wake it up
./scripts/mobius-cloud.sh status   # what's the current state?
```

- `up` takes ~1–2 min for Cloud SQL to accept connections; Cloud Run services
  cold-start (a few seconds) on first request.
- The service-update calls run in parallel, so `down`/`up` finish in well under
  a minute.

## One-click surface

**Shell aliases (simplest — works now).** Add to `~/.zshrc`:

```bash
alias mup='/Users/ananth/Mobius/scripts/mobius-cloud.sh up'
alias mdown='/Users/ananth/Mobius/scripts/mobius-cloud.sh down'
alias mstat='/Users/ananth/Mobius/scripts/mobius-cloud.sh status'
```

**macOS Shortcuts button (true one-click, pin to menu bar).**
Shortcuts.app → new shortcut → "Run Shell Script" action:
```
/Users/ananth/Mobius/scripts/mobius-cloud.sh down
```
Set shell to `zsh`, "Pass input: to stdin". Name it "Mobius Down", make a second
one for "up", then Menu Bar / Dock pin. Click = park/wake.

**Raycast.** Add the two aliases as Script Commands, or point a Raycast Script
Command at the script with an `up`/`down` argument.

## Config notes (in the script)

- **`mobius-rag-chunking-worker` at `min=12` is a leaked nightly run, not config.**
  The nightly pipeline (`mobius-rag/scripts/run_nightly_pipeline.sh`) scales it
  **up to `$CHUNK_WORKERS` (12)** at the start of a run and back to **0** on
  teardown. A standing `min=12` means a run scaled up but its teardown never
  fired — the correct idle value is **0**. `down` warns if it snapshots
  chunking-worker at min>2 so a leak isn't silently baked into the snapshot; fix
  it to 0 (`gcloud run services update mobius-rag-chunking-worker
  --region=us-central1 --min-instances=0`) before parking. This is the RAG /
  nightly-pipeline domain — coordinate with that owner rather than pinning it
  here.
- **`mobius-rag`** carries a `max=1` correctness pin (in-process job state breaks
  at max>1). The script only ever changes `min`, never `max`, so that pin is safe.
- Only `SQL_INSTANCE` / `PROJECT` / `REGION` are configurable at the top; the
  service set is discovered at runtime, so there's no list to maintain.

## What this does NOT reduce

Storage costs persist regardless: the 179GB Cloud SQL disk, GCS buckets, and
Artifact Registry images. Idle floor is ~$40–60/mo. Going lower means deleting
data, which this script never does.
