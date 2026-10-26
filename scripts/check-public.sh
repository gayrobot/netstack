#!/bin/sh
# Block commits that would publish private specifics.
#   check-public.sh staged       -> scan staged file contents and paths
#   check-public.sh msg <file>   -> scan a commit message
#   check-public.sh tree         -> scan every tracked file and the full history
# Private terms live in private/denylist.txt (gitignored). Generic patterns live here.
set -u
root=$(git rev-parse --show-toplevel) || exit 1
deny="$root/private/denylist.txt"

if [ ! -f "$deny" ]; then
  echo "check-public: $deny is missing; refusing to commit (fail closed)." >&2
  exit 1
fi

patterns=$(mktemp)
trap 'rm -f "$patterns"' EXIT
grep -vE '^\s*(#|$)' "$deny" > "$patterns"
# Generic: MAC addresses and globally routable IPv6 (2000::/3)
printf '%s\n' '([0-9a-f]{2}[:-]){5}[0-9a-f]{2}' '\b[23][0-9a-f]{3}:[0-9a-f]{1,4}:[0-9a-f]{1,4}:' >> "$patterns"

scan() { grep -inE -f "$patterns"; }
fail=0
report() { echo "check-public: private term found in $1:" >&2; printf '%s\n' "$2" | sed 's/^/  /' >&2; fail=1; }

case "${1:-staged}" in
  staged)
    hits=$(git diff --cached --name-only --diff-filter=ACMR | scan) && report "file paths" "$hits"
    for f in $(git diff --cached --name-only --diff-filter=ACMR); do
      hits=$(git show ":$f" | scan) && report "$f" "$hits"
    done ;;
  msg)
    hits=$(grep -v '^#' "$2" | scan) && report "commit message" "$hits" ;;
  tree)
    hits=$(git log --all --format='%H %an %ae %s%n%b' | scan) && report "commit metadata" "$hits"
    hits=$(git log --all --name-only --format= | sort -u | scan) && report "paths in history" "$hits"
    for c in $(git rev-list --all); do
      hits=$(git grep -inE -f "$patterns" "$c" 2>/dev/null) && report "commit $(git rev-parse --short "$c")" "$hits"
    done ;;
esac

[ "$fail" -eq 0 ] || echo "check-public: move specifics to private/ or use role names (see docs/redaction.md)." >&2
exit "$fail"
