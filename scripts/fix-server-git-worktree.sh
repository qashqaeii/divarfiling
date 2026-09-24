#!/usr/bin/env bash
# Fix phantom "modified" on Linux production clones when:
#   git hash-object <file>              -> wrong id (e.g. 91697a7)
#   git hash-object --no-filters <file>   -> matches HEAD (e.g. 057e284)
# Bytes on disk are often already correct; Git's text/eol filters confuse status/checkout.
#
# Safe for server-only: writes .git/info/attributes (not committed).
# Usage: cd ~/DivarFiling && bash scripts/fix-server-git-worktree.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $ROOT" >&2
  exit 1
fi

mkdir -p .git/info
ATTR_FILE=".git/info/attributes"
MARKER="# server: disable text filters (phantom modified)"
if ! grep -qF "$MARKER" "$ATTR_FILE" 2>/dev/null; then
  {
    echo ""
    echo "$MARKER"
    echo "* -text"
  } >> "$ATTR_FILE"
  echo "Appended * -text to $ATTR_FILE (overrides repo eol filters for this clone)"
else
  echo "Server attribute override already present in $ATTR_FILE"
fi

git config --local core.autocrlf false
git config --local core.eol lf
git config --local --unset-all core.checkstat 2>/dev/null || true

echo "Fetching and resetting to origin/main..."
git fetch origin main
git reset --hard origin/main

echo "Rewriting tracked files from HEAD blobs (exact bytes)..."
while IFS= read -r -d '' path; do
  blob="$(git rev-parse "HEAD:$path" 2>/dev/null)" || continue
  mkdir -p "$(dirname "$path")"
  tmp="${path}.git-fix-tmp"
  git cat-file blob "$blob" > "$tmp"
  mv -f "$tmp" "$path"
done < <(git ls-files -z)

git update-index --refresh

SAMPLE="workspace/agency_space_api_views.py"
if [[ -f "$SAMPLE" ]]; then
  work="$(git hash-object "$SAMPLE")"
  head="$(git rev-parse "HEAD:$SAMPLE")"
  echo ""
  echo "Verify $SAMPLE:"
  echo "  hash-object (with filters disabled via * -text): $work"
  echo "  HEAD:                                          $head"
  if [[ "$work" != "$head" ]]; then
    echo "ERROR: hashes still differ after fix." >&2
    echo "Try: git hash-object --no-filters $SAMPLE" >&2
    exit 1
  fi
fi

dirty="$(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')"
if [[ "$dirty" != "0" ]]; then
  echo ""
  echo "WARNING: still $dirty tracked change(s) in git status:" >&2
  git status --short --untracked-files=no >&2
  exit 1
fi

echo ""
echo "OK: working tree clean (tracked files)."
echo "Next: bash scripts/deploy-server.sh   (migrate + collectstatic + restart)"
