#!/bin/sh
# Just-in-time write access for the UniFi MCP.
#   change-window.sh open "<change title>"   enable create/update for one approved change
#   change-window.sh close                   back to read-only (safe to run anytime)
#   change-window.sh status [--hook]         show state; --hook prints only when a window is open
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

RO_USERNAME= RO_PASSWORD_COMMAND= RW_USERNAME= RW_PASSWORD_COMMAND=
# shellcheck disable=SC1090
[ -f "$conf" ] && . "$conf"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

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
    if [ -n "$RW_USERNAME" ]; then
      set_options true "$RW_USERNAME" "$RW_PASSWORD_COMMAND"; acct="write account"
    else
      set_options true "" ""; acct="same account (flags only; UDM role is unchanged)"
    fi
    printf '%s OPEN  %s | %s\n' "$(stamp)" "$title" "$acct" >> "$log"
    echo "Window open for: $title ($acct). Run /reload-plugins, apply, verify, then: $0 close" ;;
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
    fi ;;
  *) echo "usage: $0 open \"<title>\" | close | status" >&2; exit 2 ;;
esac
