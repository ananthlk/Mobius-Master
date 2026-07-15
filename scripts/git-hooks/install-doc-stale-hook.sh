#!/bin/sh
# Install (or refresh) the doc_stale post-commit hook in every module checkout.
# Idempotent; safe to re-run (the weekly product-docs sweep re-runs it so new
# worktree/submodule checkouts get covered). Chains after any existing hook.
set -u
HOOK_SRC="$(cd "$(dirname "$0")" && pwd)/post-commit-doc-stale.sh"
MARKER="post-commit-doc-stale.sh"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

install_into() {
  repo_dir="$1"
  [ -e "$repo_dir/.git" ] || return 0
  hooks_dir=$(git -C "$repo_dir" rev-parse --git-path hooks 2>/dev/null) || return 0
  case "$hooks_dir" in /*) : ;; *) hooks_dir="$repo_dir/$hooks_dir" ;; esac
  mkdir -p "$hooks_dir"
  hook="$hooks_dir/post-commit"
  if [ -f "$hook" ] && grep -q "$MARKER" "$hook"; then
    echo "ok (already installed): $repo_dir"
    return 0
  fi
  if [ ! -f "$hook" ]; then
    printf '#!/bin/sh\n' > "$hook"
  fi
  printf '\n# doc_stale auto-file (product-awareness; Ananth-approved 2026-07-15)\n"%s" || true\n' "$HOOK_SRC" >> "$hook"
  chmod +x "$hook"
  echo "installed: $repo_dir"
}

# Primary module checkouts (repo->module mapping lives in the hook itself).
for r in mobius-chat mobius-rag mobius-skills mobius-skills-core mobius-auth mobius-story-ui; do
  install_into "$ROOT/$r"
done

# Agent worktrees: cover module checkouts inside .claude/worktrees/*/
for wt in "$ROOT"/.claude/worktrees/*/; do
  [ -d "$wt" ] || continue
  for r in mobius-chat mobius-rag mobius-skills mobius-skills-core mobius-auth mobius-story-ui; do
    install_into "$wt$r"
  done
done
