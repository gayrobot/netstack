#!/bin/sh
# Just-in-time write access for the UniFi MCP.
#   change-window.sh open "<change title>"   enable create/update for one approved change
#   change-window.sh close                   back to read-only (safe to run anytime)
#   change-window.sh status [--hook]         show state; --hook prints only when a window is open
#   change-window.sh backup <file.unf>       record an off-box gateway backup (path, time, sha256)
#
# open refuses to run unless the latest recorded backup is newer than BACKUP_MAX_AGE_DAYS
# (default 3, set in private/change-window.conf) and is still at its recorded path with the
# same sha256. The backup's age is its file modification time, i.e. when it was downloaded.
#
# Flips policy_create / policy_update in the plugin options in ~/.claude/settings.json.
# policy_delete is never turned on. If private/change-window.conf defines RW_USERNAME and
# RW_PASSWORD_COMMAND, the window also switches the MCP to that write-capable UDM account,
# and close switches back to RO_USERNAME / RO_PASSWORD_COMMAND, so the UDM role (not just
# the MCP's own flags) is the boundary. Every open/close is appended to docs/change-windows.log.
# Plugin option changes apply after /reload-plugins or a new session.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
settings="$HOME/.claude/settings.json"
log="$root/docs/change-windows.log"
conf="$root/private/change-window.conf"
plugin="unifi-network@unifi-plugins"

backups="$root/private/backup-record.tsv"

RO_USERNAME= RO_PASSWORD_COMMAND= RW_USERNAME= RW_PASSWORD_COMMAND=
BACKUP_MAX_AGE_DAYS=3
# shellcheck disable=SC1090
[ -f "$conf" ] && . "$conf"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

# Print "<sha12> <age_hours>" for the latest recorded backup, or explain why it doesn't qualify and fail.
check_backup() {
  [ -s "$backups" ] || { echo "No off-box gateway backup on record. Download one, then: $0 backup <file.unf>" >&2; return 1; }
  IFS='	' read -r _ mtime hash _ path <<EOF
$(tail -n1 "$backups")
EOF
  [ -f "$path" ] || { echo "Recorded backup is not reachable at its path (is the volume mounted?). Record a new one." >&2; return 1; }
  [ "$(sha "$path")" = "$hash" ] || { echo "Recorded backup has changed since it was recorded (sha256 mismatch). Record a new one." >&2; return 1; }
  age=$(( $(date +%s) - mtime ))
  max=$(( BACKUP_MAX_AGE_DAYS * 86400 ))
  [ "$age" -le "$max" ] || { echo "Latest backup is $(( age / 86400 )) days old; the limit is $BACKUP_MAX_AGE_DAYS. Download a fresh one, then: $0 backup <file.unf>" >&2; return 1; }
  echo "$(printf '%s' "$hash" | cut -c1-12) $(( age / 3600 ))"
}

# set_options <write:true|false> <username> <password_command>; empty account fields are left as is
set_options() {
  cp "$settings" "$settings.bak-change-window"
  python3 -I - "$settings" "$plugin" "$1" "$2" "$3" <<'EOF'
import json, sys
path, plugin, write, user, pwcmd = sys.argv[1:]
with open(path) as f:
    s = json.load(f)
opts = s.setdefault("pluginConfigs", {}).setdefault(plugin, {}).setdefault("options", {})
opts["policy_create"] = opts["policy_update"] = (write == "true")
opts["policy_delete"] = False
if user:
    opts["username"] = user
if pwcmd:
    opts["password_command"] = pwcmd
with open(path, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
EOF
}

state() {
  python3 -I - "$settings" "$plugin" <<'EOF'
import json, sys
o = json.load(open(sys.argv[1])).get("pluginConfigs", {}).get(sys.argv[2], {}).get("options", {})
print("open" if o.get("policy_create") or o.get("policy_update") else "closed",
      o.get("username", "?"), bool(o.get("policy_delete")))
EOF
}

case "${1:-status}" in
  open)
    title=${2:?usage: change-window.sh open "<change title from docs/changes.md>"}
    grep -qF "$title" "$root/docs/changes.md" || { echo "No entry titled \"$title\" in docs/changes.md." >&2; exit 1; }
    b=$(check_backup) || exit 1
    restore="backup sha256:${b% *} (${b#* }h old)"
    if [ -n "$RW_USERNAME" ]; then
      set_options true "$RW_USERNAME" "$RW_PASSWORD_COMMAND"; acct="write account"
    else
      set_options true "" ""; acct="same account (flags only; UDM role is unchanged)"
    fi
    printf '%s OPEN  %s | %s | %s\n' "$(stamp)" "$title" "$acct" "$restore" >> "$log"
    echo "Window open for: $title ($acct, restore point: $restore). Run /reload-plugins, apply, verify, then: $0 close" ;;
  backup)
    f=${2:?usage: change-window.sh backup <file.unf>}
    case "$f" in *.unf|*.unifi) ;; *) echo "Expected a UniFi backup (.unf or .unifi): $f" >&2; exit 1 ;; esac
    [ -s "$f" ] || { echo "Not found or empty: $f" >&2; exit 1; }
    f=$(cd "$(dirname "$f")" && pwd)/$(basename "$f")
    case "$f" in *'	'*) echo "Path contains a tab; rename the file." >&2; exit 1 ;; esac
    mtime=$(stat -f %m "$f"); hash=$(sha "$f"); size=$(stat -f %z "$f")
    mkdir -p "$(dirname "$backups")"
    printf '%s\t%s\t%s\t%s\t%s\n' "$(stamp)" "$mtime" "$hash" "$size" "$f" >> "$backups"
    printf '%s BACKUP recorded sha256:%s (%s bytes)\n' "$(stamp)" "$(printf '%s' "$hash" | cut -c1-12)" "$size" >> "$log"
    echo "Recorded backup sha256:$(printf '%s' "$hash" | cut -c1-12), $size bytes. Keep it at: $f" ;;
  close)
    set_options false "$RO_USERNAME" "$RO_PASSWORD_COMMAND"
    printf '%s CLOSE\n' "$(stamp)" >> "$log"
    echo "Window closed: MCP is read-only. Run /reload-plugins (or start a new session) to apply." ;;
  status)
    set -- "${2:-}" $(state)
    if [ "$2" = open ]; then
      echo "WARNING: UniFi MCP change window is OPEN (account: $3). Last entry: $(tail -n1 "$log" 2>/dev/null). Close it with scripts/change-window.sh close once the approved change is applied and verified."
    elif [ "$1" != --hook ]; then
      echo "Closed: UniFi MCP is read-only (account: $3, delete enabled: $4)."
      if b=$(check_backup 2>&1); then echo "Restore point: sha256:${b% *}, ${b#* }h old (limit ${BACKUP_MAX_AGE_DAYS}d)."; else echo "Restore point: none usable. $b"; fi
    fi ;;
  *) echo "usage: $0 open \"<title>\" | close | status | backup <file.unf>" >&2; exit 2 ;;
esac
