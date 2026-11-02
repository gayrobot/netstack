#!/bin/sh
# The daily scope check: what changed in the documents that define the project's scope, and
# what's still open. The judgement (what to work on next) is the daily-check skill's job; this
# script only collects the facts and remembers when the check last ran.
#   daily-check.sh report          scope commits on origin/main since the last check, then the open backlog rows
#   daily-check.sh done            record that today's check ran, up to the current origin/main
#   daily-check.sh status [--hook] say when the check last ran; --hook prints only when it hasn't run today
#
# State lives in the git common dir (shared by every worktree, never tracked), because
# worktrees have no private/. With no state, report covers the last 7 days.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
state="$(git -C "$root" rev-parse --git-common-dir)/netstack-daily-check"
case "$state" in /*) ;; *) state="$root/$state" ;; esac

# The files that say what the project is, what it's for and what's next.
scope="CLAUDE.md AGENTS.md docs/spec.md docs/strategy.md docs/backlog.md docs/detectors.html
docs/change-control.md docs/exceptions.md docs/changes.md docs/vetting"

today() { date +%Y-%m-%d; }
last_date() { [ -f "$state" ] && cut -f1 "$state" || true; }
last_sha() { [ -f "$state" ] && cut -f2 "$state" || true; }

main_ref() {
  git -C "$root" fetch -q origin main 2>/dev/null || echo "(fetch failed; using the local origin/main)" >&2
  git -C "$root" rev-parse origin/main
}

report() {
  head=$(main_ref)
  since=$(last_sha)
  if [ -n "$since" ] && git -C "$root" cat-file -e "$since^{commit}" 2>/dev/null; then
    range="$since..$head"; echo "Scope changes since the last check ($(last_date), ${since%"${since#????????}"}):"
  else
    range="--since=7.days $head"; echo "Scope changes in the last 7 days (no earlier check recorded):"
  fi
  # shellcheck disable=SC2086
  log=$(git -C "$root" log --no-merges --date=short --format='%h %ad %s' $range -- $scope)
  if [ -n "$log" ]; then echo "$log"; else echo "  none"; fi
  echo
  echo "Files touched:"
  # shellcheck disable=SC2086
  files=$(git -C "$root" log --no-merges --format= --name-only $range -- $scope | sort | uniq -c | sort -rn)
  if [ -n "$files" ]; then echo "$files"; else echo "  none"; fi
  echo
  echo "Open backlog rows on origin/main (status not done, won't do, moved or superseded):"
  git -C "$root" show "$head:docs/backlog.md" |
    grep -E '^\| [A-Z][0-9]+ \|' |
    grep -viE '\| *(done|won.t do|moved|superseded)[^|]*\|$' |
    awk -F'|' '{ id=$2; item=$3; st=$(NF-1); gsub(/^ +| +$/, "", id); gsub(/\*\*/, "", item);
                 gsub(/^ +| +$/, "", st); if (tolower(st) ~ /on hold/) id = id " (on hold)";
                 if (length(item) > 90) item = substr(item, 1, 87) "...";
                 if (length(st) > 70) st = substr(st, 1, 67) "...";
                 printf "  %-4s %s\n       status: %s\n", id, item, st }'
}

case "${1:-status}" in
  report) report ;;
  done)
    head=$(main_ref)
    printf '%s\t%s\n' "$(today)" "$head" > "$state"
    echo "Daily check recorded for $(today) at ${head%"${head#????????}"}." ;;
  status)
    d=$(last_date)
    if [ "${2:-}" = "--hook" ]; then
      [ "$d" = "$(today)" ] && exit 0
      echo "Daily scope check hasn't run today (last: ${d:-never}). Run the daily-check skill before picking work."
    else
      echo "Daily scope check last ran: ${d:-never}."
    fi ;;
  *) sed -n '2,10p' "$0" >&2; exit 2 ;;
esac
