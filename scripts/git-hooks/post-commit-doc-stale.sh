#!/bin/sh
# post-commit → auto-file a doc_stale signal (Ananth-approved 2026-07-15).
#
# Files ONE signal per user-facing commit in a module repo so the product-docs
# weekly sweep sees "this module changed since its doc was built" without any
# agent remembering to file. Fire-and-forget: NEVER blocks or fails the commit.
#
# Skips: docs-only commits, chunk regen, commits whose subject contains [no-doc],
# and anything when DOC_STALE_HOOK_DISABLE=1.
# Dry-run: DOC_STALE_HOOK_DRY_RUN=1 prints the payload instead of posting.

FEEDBACK_URL="${DOC_STALE_HOOK_URL:-https://mobius-chat-ortabkknqa-uc.a.run.app/chat/product-feedback}"

[ "$DOC_STALE_HOOK_DISABLE" = "1" ] && exit 0

main() {
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  repo_name=$(basename "$repo_root")
  subject=$(git log -1 --format=%s 2>/dev/null) || return 0
  case "$subject" in *"[no-doc]"*) return 0 ;; esac
  sha=$(git rev-parse --short HEAD 2>/dev/null)
  files=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null)
  [ -n "$files" ] || return 0

  # Docs-only / chunk-regen commits are the FIX, not new staleness.
  non_doc=$(printf '%s\n' "$files" | grep -vE '\.md$|^docs/|^corpus/chunks/|^product-awareness/corpus/')
  [ -n "$non_doc" ] || return 0

  # repo (+ paths) → area_tag; unknown repos are silently out of scope.
  module=""
  case "$repo_name" in
    mobius-chat)      module="chat" ;;
    mobius-rag)
      module="rag"
      printf '%s\n' "$non_doc" | grep -qiE 'lexicon' && module="lexicon" ;;
    mobius-skills)
      module="skills"
      printf '%s\n' "$non_doc" | grep -qE '^provider-roster-credentialing/' && module="credentialing" ;;
    mobius-skills-core) module="skills" ;;
    mobius-auth)      module="auth" ;;
    mobius-user)      module="auth" ;;   # enrollment/invite/set-password → user-and-auth.md
    mobius-story-ui)  module="strategy" ;;
    *) return 0 ;;
  esac

  n_files=$(printf '%s\n' "$non_doc" | grep -c .)
  # JSON-escape the subject minimally (quotes + backslashes).
  esc_subject=$(printf '%s' "$subject" | sed 's/\\/\\\\/g; s/"/\\"/g' | cut -c1-160)
  payload=$(printf '{"category":"doc_stale","verbatim":"git-hook: %s@%s %s (%s files)","area_tags":["%s"],"source":"git-hook","trigger":"agent_signal"}' \
    "$repo_name" "$sha" "$esc_subject" "$n_files" "$module")

  if [ "$DOC_STALE_HOOK_DRY_RUN" = "1" ]; then
    echo "[doc-stale-hook dry-run] POST $FEEDBACK_URL"
    echo "$payload"
    return 0
  fi
  curl -s -m 5 -X POST "$FEEDBACK_URL" \
    -H "Content-Type: application/json" -d "$payload" >/dev/null 2>&1 || true
}

if [ "$DOC_STALE_HOOK_DRY_RUN" = "1" ]; then
  main
else
  main >/dev/null 2>&1 &
fi
exit 0
