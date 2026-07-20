#!/usr/bin/env bash
#
# mobius-cloud.sh — park / wake the GCP dev environment to stop idle billing.
#
#   ./mobius-cloud.sh down     # park: snapshot + scale all warm services to 0, stop Cloud SQL
#   ./mobius-cloud.sh up       # wake: start Cloud SQL, restore services from the snapshot
#   ./mobius-cloud.sh status   # show current SQL policy + service min-instances
#
# Only touches resources that COST MONEY WHILE IDLE:
#   - Cloud SQL instance (does not scale to zero)
#   - Cloud Run services pinned to min-instances > 0 (kept warm 24/7)
# Everything already at min=0 scales to zero and is left untouched.
#
# `down` SNAPSHOTS the current min-instances of every warm service to a state
# file, then zeroes them. `up` restores each service to exactly its snapshotted
# value. This means the script never fights whatever set those values (e.g. the
# nightly pipeline, which scales the rag workers up for a run and back to 0) —
# it faithfully restores whatever reality was at park time. Nothing is deleted.
#
# IMPORTANT: this is a SHARED dev environment. Running `down` stops Cloud SQL and
# zeroes services other live agent sessions may be using — only park when the
# fleet is idle (end of day), not mid-work.

set -euo pipefail

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
PROJECT="mobius-os-dev"
REGION="us-central1"
SQL_INSTANCE="mobius-platform-dev-db"
STATE_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.mobius-cloud-parked.state"

GC="gcloud --project=${PROJECT} --quiet"

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
_min_of() {  # print current minScale (0 if unset) for a service
  local v
  v="$($GC run services describe "$1" --region="$REGION" \
      --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>/dev/null)"
  echo "${v:-0}"
}

# All Cloud Run services with their current min, one "name min" per line.
_all_service_mins() {
  $GC run services list --platform=managed --region="$REGION" \
    --format="value(metadata.name, spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>/dev/null \
    | awk '{print $1, ($2==""?0:$2)}'
}

_set_min() {  # svc min  — updates in background; caller collects $!
  echo "   -> ${1}: min-instances=${2}"
  $GC run services update "$1" --region="$REGION" --min-instances="$2" \
    >/dev/null 2>"/tmp/mobius-cloud.${1}.err" &
}

_wait_all() {
  local failed=0 pid
  for pid in "$@"; do wait "$pid" || failed=1; done
  [[ "$failed" == "1" ]] && { echo "!! a Cloud Run update failed — see /tmp/mobius-cloud.*.err"; return 1; }
  return 0
}

# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------
cmd_down() {
  echo "== Parking Mobius dev environment ($PROJECT) =="
  echo "   NOTE: shared env — this disrupts any live session using the DB/services."

  # Snapshot every warm service (min>0) before we zero anything.
  local warm; warm="$(_all_service_mins | awk '$2+0 > 0')"
  if [[ -z "$warm" ]]; then
    echo "-> No warm services (all already min=0)."
  else
    echo "$warm" > "$STATE_FILE"
    echo "-> Snapshotted $(echo "$warm" | wc -l | tr -d ' ') warm service(s) to ${STATE_FILE##*/}:"
    echo "$warm" | sed 's/^/     /'
    # Guard: flag a likely leaked nightly run rather than baking it into the snapshot silently.
    echo "$warm" | awk '$1=="mobius-rag-chunking-worker" && $2+0 > 2 {
      print "   !! chunking-worker min="$2" looks like a leaked nightly run (idle should be 0)."
      print "      up will restore "$2"; fix it to 0 first if that is not intended." }'
    local pids=() svc min
    while read -r svc min; do [[ -z "$svc" ]] && continue; _set_min "$svc" 0; pids+=("$!"); done <<< "$warm"
    _wait_all "${pids[@]}"
  fi

  echo "-> Stopping Cloud SQL: $SQL_INSTANCE (activation-policy=NEVER)"
  $GC sql instances patch "$SQL_INSTANCE" --activation-policy=NEVER >/dev/null

  echo "== Parked. Services scaled to zero; SQL compute billing stopped."
  echo "   (Storage still bills. './mobius-cloud.sh up' to resume.) =="
}

cmd_up() {
  echo "== Waking Mobius dev environment ($PROJECT) =="

  echo "-> Starting Cloud SQL: $SQL_INSTANCE (activation-policy=ALWAYS)"
  $GC sql instances patch "$SQL_INSTANCE" --activation-policy=ALWAYS >/dev/null

  if [[ ! -f "$STATE_FILE" ]]; then
    echo "!! No snapshot ($STATE_FILE) — services left as-is. Nothing to restore."
  else
    echo "-> Restoring services from snapshot:"
    local pids=() svc min
    while read -r svc min; do [[ -z "$svc" ]] && continue; _set_min "$svc" "$min"; pids+=("$!"); done < "$STATE_FILE"
    _wait_all "${pids[@]}" && { rm -f "$STATE_FILE"; echo "-> Snapshot consumed."; }
  fi

  echo "== Awake. Cloud SQL ~1-2 min to accept connections; Cloud Run cold-starts on first hit. =="
}

cmd_status() {
  echo "== Mobius dev environment status ($PROJECT) =="
  echo
  echo -n "Cloud SQL: $SQL_INSTANCE — "
  $GC sql instances describe "$SQL_INSTANCE" --format="value(settings.activationPolicy, state)"
  echo
  echo "Cloud Run services with min-instances > 0 (idle cost):"
  _all_service_mins | awk '$2+0 > 0 {printf "   %-32s min=%s\n", $1, $2}'
  echo
  [[ -f "$STATE_FILE" ]] && echo "(parked snapshot present: ${STATE_FILE})" || echo "(no parked snapshot — env is not parked by this script)"
}

# ----------------------------------------------------------------------------
case "${1:-}" in
  down)   cmd_down ;;
  up)     cmd_up ;;
  status) cmd_status ;;
  *) echo "Usage: $0 {up|down|status}"; exit 1 ;;
esac
