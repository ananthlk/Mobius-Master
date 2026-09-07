#!/usr/bin/env bash
# tag_module.sh <module> <version>
#
# Creates an annotated semver tag in a module's own repo, using that version's
# release notes as the tag message. Refuses to tag a dirty tree or reuse a
# version — a tag is permanent, so the guards are not optional.
#
#   scripts/release/tag_module.sh mobius-chat v1.1.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODULE="${1:?usage: tag_module.sh <module> <version>}"
VERSION="${2:?usage: tag_module.sh <module> <version>}"

[[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] \
  || { echo "✗ version must be vMAJOR.MINOR.PATCH, got '$VERSION'" >&2; exit 1; }

DIR="$ROOT/$MODULE"
[ -e "$DIR/.git" ] || { echo "✗ $MODULE is not a git repo" >&2; exit 1; }

NOTES="$ROOT/docs/releases/modules/$MODULE/$VERSION.md"
[ -f "$NOTES" ] || { echo "✗ no release notes at docs/releases/modules/$MODULE/$VERSION.md" >&2; exit 1; }

if git -C "$DIR" rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  echo "✗ $MODULE already has $VERSION (tags are permanent — pick the next version)" >&2
  exit 1
fi

DIRTY_N="$(git -C "$DIR" status --porcelain | wc -l | tr -d ' ')"
if [ "$DIRTY_N" != "0" ] && [ "${3:-}" != "--allow-dirty" ]; then
  echo "✗ $MODULE has $DIRTY_N uncommitted file(s)." >&2
  git -C "$DIR" status --short | sed 's/^/    /' >&2
  echo "  A tag points at a COMMIT, so this work would not be in the release." >&2
  echo "  Commit it first, or re-run with --allow-dirty to tag HEAD and record" >&2
  echo "  the exclusion in the manifest." >&2
  exit 1
fi

BRANCH="$(git -C "$DIR" rev-parse --abbrev-ref HEAD)"
SHA="$(git -C "$DIR" rev-parse --short HEAD)"

git -C "$DIR" tag -a "$VERSION" -F "$NOTES"
echo "✓ $MODULE $VERSION → $SHA (branch: $BRANCH)"
[ "$BRANCH" = "main" ] || echo "  note: tagged from '$BRANCH', not main — recorded in the manifest"
[ "$DIRTY_N" = "0" ] || echo "  note: $DIRTY_N uncommitted file(s) NOT in this release — recorded in the manifest"
