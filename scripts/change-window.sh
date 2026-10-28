#!/bin/sh
# Just-in-time write access for the UniFi MCP.
#   change-window.sh open "<change title>"   enable create/update for one approved change
#   change-window.sh close                   back to read-only (safe to run anytime)
#   change-window.sh status [--hook]         show state; --hook prints only when a window is open
#   change-window.sh backup <file.unf>       record an off-box gateway backup (path, time, sha256)
#
# open refuses to run without a restore point younger than BACKUP_MAX_AGE_DAYS (default 3, set
# in private/change-window.conf). Two sources qualify, checked in this order:
#   1. The NAS job's manifest.json, fetched over the DSM API when BACKUP_NAS_URL is set (no mount
#      needed), or read from a read-only mount at BACKUP_MANIFEST. Age is the gateway's
#      backup creation time; the encrypted file must exist next to it, match its sha256 and
#      have passed the job's archive check.
#   2. The manual record (backup <file.unf>): still at its path with the same sha256. Age is the
#      file's modification time, i.e. when it was downloaded.
#
# Flips policy_create / policy_update in the plugin options in ~/.claude/settings.json.
# policy_delete is never turned on. If private/change-window.conf defines RW_USERNAME and
# RW_PASSWORD_COMMAND, the window also switches the MCP to that write-capable UDM account,
# and close switches back to RO_USERNAME / RO_PASSWORD_COMMAND, so the UDM role (not just
# the MCP's own flags) is the boundary. Every open/close is appended to docs/change-windows.log.
# Plugin option changes apply after /reload-plugins or a new session.
#
# WINDOW_MODE=gate (set in the conf) is for setups with a separate write connection that asks the
# owner on every call: open and close then only check the restore point and log, and never touch
# the read connection's settings. The default, flags, keeps the behaviour described above.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
settings="$HOME/.claude/settings.json"
log="$root/docs/change-windows.log"
conf="$root/private/change-window.conf"
plugin="unifi-network@unifi-plugins"

backups="$root/private/backup-record.tsv"

RO_USERNAME= RO_PASSWORD_COMMAND= RW_USERNAME= RW_PASSWORD_COMMAND=
BACKUP_MAX_AGE_DAYS=3 BACKUP_MANIFEST=
WINDOW_MODE=flags
BACKUP_NAS_URL= BACKUP_NAS_PIN= BACKUP_NAS_USER= BACKUP_NAS_PASSWORD_COMMAND= BACKUP_NAS_DIR=
# shellcheck disable=SC1090
[ -f "$conf" ] && . "$conf"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

# Print "<source> <sha12> <age_hours>" for a qualifying restore point, or explain why none qualifies and fail.
check_backup() {
  if [ -n "$BACKUP_NAS_URL" ]; then
    nas_tmp=$(mktemp -d)
    if r=$(fetch_nas "$nas_tmp" 2>&1) && r=$(BACKUP_MANIFEST="$nas_tmp/manifest.json" check_manifest 2>&1); then
      rm -rf "$nas_tmp"; echo "nas $r"; return 0
    fi
    rm -rf "$nas_tmp"
    echo "NAS: $r" >&2
  elif [ -n "$BACKUP_MANIFEST" ]; then
    if r=$(check_manifest 2>&1); then echo "nas $r"; return 0; fi
    echo "NAS manifest: $r" >&2
  fi
  r=$(check_record) || return 1
  echo "manual $r"
}

# fetch_nas <dir>: download manifest.json and the backup it names from the NAS over the DSM File Station
# API, as a read-only account, so no share has to be mounted. TLS is pinned to the NAS's public key.
# The password comes from BACKUP_NAS_PASSWORD_COMMAND (an argv, run without a shell) and only travels on stdin.
fetch_nas() {
  python3 -I - "$1" "$BACKUP_NAS_URL" "$BACKUP_NAS_PIN" "$BACKUP_NAS_USER" "$BACKUP_NAS_PASSWORD_COMMAND" "$BACKUP_NAS_DIR" <<'EOF'
import json, os, shlex, subprocess, sys, urllib.parse
out, url, pin, user, pwcmd, share = sys.argv[1:]
if not (pin.startswith("sha256//") and user and pwcmd and share.startswith("/")):
    sys.exit("BACKUP_NAS_PIN, BACKUP_NAS_USER, BACKUP_NAS_PASSWORD_COMMAND and BACKUP_NAS_DIR are required")
api = url.rstrip("/") + "/webapi/entry.cgi"
curl = ["curl", "-sS", "--fail", "--max-time", "60", "--insecure", "--pinnedpubkey", pin, api, "--data-binary", "@-"]

def call(params, dest=None):
    r = subprocess.run(curl + (["-o", dest] if dest else []), input=urllib.parse.urlencode(params).encode(),
                       capture_output=True)
    if r.returncode:
        sys.exit("NAS request failed: " + r.stderr.decode(errors="replace").strip()[:200])
    return r.stdout

pw = subprocess.run(shlex.split(pwcmd), capture_output=True, text=True, timeout=60)
if pw.returncode or not pw.stdout.strip():
    sys.exit("password command failed")
login = json.loads(call({"api": "SYNO.API.Auth", "version": "6", "method": "login", "account": user,
                         "passwd": pw.stdout.rstrip("\n"), "session": "FileStation", "format": "sid"}))
if not login.get("success"):
    sys.exit(f"NAS login failed: {login.get('error')}")
sid = login["data"]["sid"]

def download(name):
    dest = os.path.join(out, name)
    call({"api": "SYNO.FileStation.Download", "version": "2", "method": "download",
          "path": json.dumps([share.rstrip("/") + "/" + name]), "mode": "download", "_sid": sid}, dest)
    with open(dest, "rb") as f:
        if f.read(10).startswith(b'{"error"'):
            sys.exit(f"NAS refused to send {name}")

try:
    download("manifest.json")
    name = os.path.basename(json.load(open(os.path.join(out, "manifest.json")))["latest"]["file"])
    if not name.endswith(".unf.cms"):
        sys.exit("manifest names an unexpected file")
    download(name)
finally:
    call({"api": "SYNO.API.Auth", "version": "6", "method": "logout", "session": "FileStation", "_sid": sid})
EOF
}

check_manifest() {
  [ -f "$BACKUP_MANIFEST" ] || { echo "not reachable at $BACKUP_MANIFEST (is the share mounted?)"; return 1; }
  python3 -I - "$BACKUP_MANIFEST" "$BACKUP_MAX_AGE_DAYS" <<'EOF'
import calendar, hashlib, json, os, sys, time
path, max_days = sys.argv[1], int(sys.argv[2])
try:
    m = json.load(open(path))["latest"]
    created = calendar.timegm(time.strptime(m["source_created"], "%Y-%m-%dT%H:%M:%SZ"))
except (OSError, ValueError, KeyError, TypeError) as e:
    sys.exit(f"unreadable or incomplete ({type(e).__name__})")
if m.get("archive_check") != "ok":
    sys.exit("latest backup did not pass the archive check")
f = os.path.join(os.path.dirname(path), os.path.basename(m.get("file", "")))
if not os.path.isfile(f):
    sys.exit(f"backup file {os.path.basename(f)} is missing from the share")
h = hashlib.sha256()
with open(f, "rb") as fh:
    for chunk in iter(lambda: fh.read(1 << 20), b""):
        h.update(chunk)
if h.hexdigest() != m.get("sha256"):
    sys.exit("backup file does not match the manifest's sha256")
age = int(time.time()) - created
if age > max_days * 86400:
    sys.exit(f"latest backup is {age // 86400} days old; the limit is {max_days}")
print(m["sha256"][:12], age // 3600)
EOF
}

check_record() {
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
    set -- $b
    restore="$1 backup sha256:$2 (${3}h old)"
    if [ "$WINDOW_MODE" = gate ]; then
      printf '%s OPEN  %s | gate only | %s\n' "$(stamp)" "$title" "$restore" >> "$log"
      echo "Gate passed for: $title (restore point: $restore). Apply it through the write connection, verify, then: $0 close"
      exit 0
    fi
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
    if [ "$WINDOW_MODE" = gate ]; then printf '%s CLOSE\n' "$(stamp)" >> "$log"; echo "Closed and logged."; exit 0; fi
    set_options false "$RO_USERNAME" "$RO_PASSWORD_COMMAND"
    printf '%s CLOSE\n' "$(stamp)" >> "$log"
    echo "Window closed: MCP is read-only. Run /reload-plugins (or start a new session) to apply." ;;
  status)
    set -- "${2:-}" $(state)
    if [ "$2" = open ]; then
      echo "WARNING: UniFi MCP change window is OPEN (account: $3). Last entry: $(tail -n1 "$log" 2>/dev/null). Close it with scripts/change-window.sh close once the approved change is applied and verified."
    elif [ "$1" != --hook ]; then
      echo "Closed: UniFi MCP is read-only (account: $3, delete enabled: $4)."
      if b=$(check_backup 2>/dev/null); then
        set -- $b; echo "Restore point: $1 backup sha256:$2, ${3}h old (limit ${BACKUP_MAX_AGE_DAYS}d)."
      else
        echo "Restore point: none usable."; check_backup 2>&1 >/dev/null | sed 's/^/  /' || true
      fi
    fi ;;
  *) echo "usage: $0 open \"<title>\" | close | status | backup <file.unf>" >&2; exit 2 ;;
esac
