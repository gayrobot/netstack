#!/bin/sh
# Get a gateway network backup onto the NAS, verify it, encrypt it, record it.
# Runs from DSM Task Scheduler as a dedicated non-admin user. See docs/gateway-backups.md.
#
#   pull-gateway-backup.sh <config>                  pull from the gateway
#   pull-gateway-backup.sh <config> --file <x.unf>   import a local backup instead (bootstrap/test)
#
# Config (shell syntax, mode 600, owned by the job user):
#   GW_HOST=<gateway IP>          GW_SITE=default
#   GW_USER=<backup account>      GW_PASSWORD_FILE=<path, mode 600>
#   GW_PUBKEY_PIN=sha256//<base64>   pinned TLS public key of the gateway (required)
#   DEST=<share path>             CERT=<public X.509 cert to encrypt to>
#   KEEP=30                       encrypted files kept in DEST (snapshots keep history)
#   GW_MODE=ondemand              ondemand: ask the gateway for a fresh backup each run (needs
#                                 Network Full Management); auto: pull the newest weekly auto-backup
#
# Exits non-zero on any failure so DSM's "email on abnormal termination" fires.
# The plaintext backup only ever exists in a mode-700 temp dir that is removed on exit.
set -eu
umask 027   # stored files group-readable for the read-only reader; the temp dir is 700 regardless

conf=${1:?usage: pull-gateway-backup.sh <config> [--file <x.unf>]}
[ -f "$conf" ] || { echo "config not found: $conf" >&2; exit 1; }
GW_SITE=default KEEP=30 GW_MODE=ondemand GW_HOST= GW_USER= GW_PASSWORD_FILE= GW_PUBKEY_PIN= DEST= CERT=
# shellcheck disable=SC1090
. "$conf"
[ -n "$DEST" ] && [ -d "$DEST" ] || { echo "DEST is not a directory: $DEST" >&2; exit 1; }
[ -f "$CERT" ] || { echo "CERT not found: $CERT" >&2; exit 1; }
for bin in curl openssl python3; do command -v "$bin" >/dev/null || { echo "missing $bin" >&2; exit 1; }; done

# UniFi .unf files use a fixed, widely published AES-128-CBC key and IV. This is not secrecy,
# only the container format; it's why the file is re-encrypted to our own key below.
UNF_KEY=626379616e676b6d6c756f686d617273
UNF_IV=75626e74656e74657270726973656170

tmp=$(mktemp -d)
jar="$tmp/cookies"
trap 'rm -rf "$tmp"' EXIT INT TERM

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

gw() { # gw <curl args...>: HTTPS to the gateway with the pinned key; never prints the body on error
  curl -sS --fail --max-time 60 --insecure --pinnedpubkey "$GW_PUBKEY_PIN" \
       -b "$jar" -c "$jar" "$@"
}

pull() {
  [ -n "$GW_HOST" ] && [ -n "$GW_USER" ] && [ -f "$GW_PASSWORD_FILE" ] || { echo "GW_HOST, GW_USER and GW_PASSWORD_FILE are required" >&2; exit 1; }
  case "$GW_PUBKEY_PIN" in sha256//?*) ;; *) echo "GW_PUBKEY_PIN is required (sha256//...)" >&2; exit 1 ;; esac
  base="https://$GW_HOST"

  # Login body is built from the password file and piped in, so the password never appears in argv.
  python3 -I -c 'import json,sys; print(json.dumps({"username": sys.argv[1], "password": open(sys.argv[2]).read().rstrip("\n")}))' \
    "$GW_USER" "$GW_PASSWORD_FILE" |
    gw -D "$tmp/login.hdr" -H 'Content-Type: application/json' --data-binary @- "$base/api/auth/login" -o /dev/null
  csrf=$(tr -d '\r' < "$tmp/login.hdr" | awk -F': ' 'tolower($1)=="x-csrf-token"{print $2}' | tail -n1)
  [ -n "$csrf" ] || { echo "login returned no CSRF token" >&2; exit 1; }

  if [ "$GW_MODE" = ondemand ]; then
    # Ask the gateway for a fresh network backup. It returns a download URL; the file is
    # overwritten on the next request, so nothing builds up on the gateway.
    gw -H "X-CSRF-Token: $csrf" -H 'Content-Type: application/json' --data '{"cmd":"backup","days":0}' \
       "$base/proxy/network/api/s/$GW_SITE/cmd/backup" -o "$tmp/create.json"
    url=$(python3 -I -c '
import json, sys
d = json.load(open(sys.argv[1]))
if (d.get("meta") or {}).get("rc") != "ok": sys.exit("backup request failed")
print(d["data"][0]["url"])
' "$tmp/create.json") || exit 1
    case "$url" in /dl/backup/*.unf) ;; *) echo "unexpected backup URL" >&2; exit 1 ;; esac
    case "$url" in *[!A-Za-z0-9/._-]*) echo "unexpected backup URL" >&2; exit 1 ;; esac
    created=$(date +%s)
    version=$(basename "$url" .unf)
    gw -H "X-CSRF-Token: $csrf" "$base/proxy/network$url" -o "$tmp/backup.unf"
    gw -H "X-CSRF-Token: $csrf" -X POST "$base/api/auth/logout" -o /dev/null || true
    return
  fi

  # "list-backups" is a read-only command; it still needs POST and the CSRF token.
  gw -H "X-CSRF-Token: $csrf" -H 'Content-Type: application/json' --data '{"cmd":"list-backups"}' \
     "$base/proxy/network/api/s/$GW_SITE/cmd/backup" -o "$tmp/list.json"
  info=$(python3 -I -c '
import json, sys
d = json.load(open(sys.argv[1])).get("data", [])
d = [b for b in d if str(b.get("filename", "")).startswith("autobackup_") and b.get("time")]
if not d: sys.exit("no auto-backups listed")
b = max(d, key=lambda b: b["time"])
print(b["filename"], int(b["time"]) // 1000, b.get("version", "unknown"))
' "$tmp/list.json") || exit 1
  set -- $info
  name=$1 created=$2 version=$3
  case "$name" in *[!A-Za-z0-9._-]*) echo "unexpected backup filename" >&2; exit 1 ;; esac

  gw -H "X-CSRF-Token: $csrf" "$base/proxy/network/dl/autobackup/$name" -o "$tmp/backup.unf"
  gw -H "X-CSRF-Token: $csrf" -X POST "$base/api/auth/logout" -o /dev/null || true
}

import_file() {
  [ -s "$1" ] || { echo "not found or empty: $1" >&2; exit 1; }
  cp "$1" "$tmp/backup.unf"
  created=$(python3 -I -c 'import os,sys; print(int(os.stat(sys.argv[1]).st_mtime))' "$1")
  version=unknown
}

if [ "${2:-}" = --file ]; then import_file "${3:?--file needs a path}"; else pull; fi

# Verify: decrypt the .unf container and check it's a zip that contains the controller database.
size=$(wc -c < "$tmp/backup.unf" | tr -d ' ')
[ "$size" -ge 1024 ] && [ $((size % 16)) -eq 0 ] || { echo "backup has an invalid size ($size bytes)" >&2; exit 1; }
openssl enc -d -aes-128-cbc -nopad -K "$UNF_KEY" -iv "$UNF_IV" -in "$tmp/backup.unf" -out "$tmp/backup.zip"
python3 -I -c '
import sys
b = open(sys.argv[1], "rb").read()
if not b.startswith(b"PK\x03\x04"): sys.exit("decrypted backup is not a zip archive")
if b"db.gz" not in b: sys.exit("archive does not contain db.gz")
' "$tmp/backup.zip"
plain=$(sha256 "$tmp/backup.unf")

# Skip if this exact backup is already stored, or if it's older than the one already recorded
# (latest must never move backwards).
if [ -f "$DEST/manifest.json" ] && python3 -I -c '
import calendar, json, sys, time
m = json.load(open(sys.argv[1])).get("latest") or {}
if m.get("plain_sha256") == sys.argv[2]: sys.exit(0)
prev = calendar.timegm(time.strptime(m["source_created"], "%Y-%m-%dT%H:%M:%SZ")) if m.get("source_created") else 0
sys.exit(0 if int(sys.argv[3]) <= prev else 1)
' "$DEST/manifest.json" "$plain" "$created"; then
  log "unchanged: this backup is already stored or older than the latest recorded one"
  exit 0
fi

stamp=$(python3 -I -c 'import sys,time; print(time.strftime("%Y%m%d-%H%M", time.gmtime(int(sys.argv[1]))))' "$created")
out="gateway-$stamp.unf.cms"
openssl cms -encrypt -binary -aes-256-cbc -outform DER -in "$tmp/backup.unf" -out "$tmp/$out" "$CERT"
enc=$(sha256 "$tmp/$out")

# Write the file, then the manifest, each atomically (temp name in DEST + rename).
cp "$tmp/$out" "$DEST/.$out.part" && mv "$DEST/.$out.part" "$DEST/$out"
python3 -I - "$DEST/manifest.json" "$out" "$created" "$enc" "$plain" "$version" <<'EOF'
import json, os, sys, time
path, out, created, enc, plain, version = sys.argv[1:]
iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
try:
    m = json.load(open(path))
except (OSError, ValueError):
    m = {"last_restore_test": None}
m["latest"] = {"file": out, "source_created": iso(int(created)), "pulled": iso(time.time()),
               "sha256": enc, "plain_sha256": plain, "archive_check": "ok", "controller_version": version}
tmp = os.path.join(os.path.dirname(path), ".manifest.json.part")
with open(tmp, "w") as f:
    json.dump(m, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
EOF

# Retention inside the share; immutable snapshots keep the longer history.
ls -1t "$DEST"/gateway-*.unf.cms 2>/dev/null | tail -n +"$((KEEP + 1))" | while IFS= read -r old; do rm -f "$old"; done

log "stored $out (sha256 ${enc%"${enc#????????????}"}, source $stamp UTC, controller $version)"
