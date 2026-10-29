#!/usr/bin/env python3
"""op-rotate: renews the read-only 1Password service-account token before it expires.

  op-rotate check                   daily (launchd): rotate if within warn_days of expiry
  op-rotate rotate                  rotate now
  op-rotate status [--hook]         when it expires; --hook prints only when it needs attention
  op-rotate seed <name> <YYYY-MM-DD>  record the current service account and its expiry (install)
  op-rotate plist                   print the launchd agent for this install

A rotation creates a new service account with read access to the read-only vault only,
checks the new token can read one read-only item, and only then writes it to the Keychain
item that op-ro-read uses. The token is never printed, logged or put in argv. Creating a
service account needs the owner's 1Password sign-in, so each rotation shows one 1Password
prompt; a macOS notification says it's coming. A missed or failed rotation keeps the current
token and is tried again the next day. The old service account keeps working until its own
expiry; delete it in the 1Password web app (the CLI can't).

Config (non-secret, private names): ~/.config/netstack/op-rotate/config, key=value lines:
  base_name, vault, keychain_service, verify_ref (op://...), account (optional),
  warn_days (default 14), expires_days (default 90)

Stdlib only. Run with: python3 -I op_rotate.py
"""
import datetime
import fcntl
import os
import re
import subprocess
import sys

TOKEN = re.compile(r"^ops_[A-Za-z0-9+/=_.-]{20,}$")
SAFE = re.compile(r"^[A-Za-z0-9_.:/@-]+$")  # names that go into op argv or `security -i`
CREATE_TIMEOUT_S = 300  # time for the owner to approve the 1Password prompt
LABEL = "local.netstack.op-rotate"


def state_dir():
    return os.environ.get("OP_ROTATE_DIR") or os.path.expanduser("~/.config/netstack/op-rotate")


def op_bin():
    return os.environ.get("OP_ROTATE_OP", "/opt/homebrew/bin/op")


def security_bin():
    return os.environ.get("OP_ROTATE_SECURITY", "/usr/bin/security")


def today():
    fixed = os.environ.get("OP_ROTATE_TODAY")
    return datetime.date.fromisoformat(fixed) if fixed else datetime.date.today()


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_kv(name):
    out = {}
    try:
        with open(os.path.join(state_dir(), name)) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return out


def write_kv(name, data):
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    p = os.path.join(state_dir(), name)
    with open(p + ".tmp", "w") as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")
    os.replace(p + ".tmp", p)


def load_config():
    cfg = read_kv("config")
    missing = [k for k in ("base_name", "vault", "keychain_service", "verify_ref") if not cfg.get(k)]
    if missing:
        raise SystemExit(f"op-rotate: config is missing {', '.join(missing)} ({state_dir()}/config)")
    for k in ("base_name", "vault", "keychain_service", "verify_ref", "account"):
        if cfg.get(k) and not SAFE.match(cfg[k]):
            raise SystemExit(f"op-rotate: config {k} has unexpected characters")
    if not cfg["verify_ref"].startswith("op://"):
        raise SystemExit("op-rotate: verify_ref is not an op:// reference")
    cfg["warn_days"] = int(cfg.get("warn_days", 14))
    cfg["expires_days"] = int(cfg.get("expires_days", 90))
    return cfg


def log(msg):
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    with open(os.path.join(state_dir(), "rotate.log"), "a") as f:
        f.write(f"{now()} {msg}\n")


def notify(msg):
    cmd = os.environ.get("OP_ROTATE_NOTIFY")
    if cmd == "":
        return
    argv = [cmd, msg] if cmd else [
        "/usr/bin/osascript", "-e", "on run argv", "-e",
        'display notification (item 1 of argv) with title "netstack"', "-e", "end run", msg]
    try:
        subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


def days_left(state):
    try:
        return (datetime.date.fromisoformat(state["expires"]) - today()).days
    except (KeyError, ValueError):
        return None


def last_line(text):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1][:200] if lines else ""


def keychain_user():
    import pwd
    return pwd.getpwuid(os.getuid()).pw_name


def keychain_read(service):
    r = subprocess.run([security_bin(), "find-generic-password", "-a", keychain_user(), "-s", service, "-w"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    return r.stdout.strip() if r.returncode == 0 else None


def keychain_write(service, token):
    # `security -i` reads the command from stdin, so the token never appears in argv.
    cmd = f'add-generic-password -U -a "{keychain_user()}" -s "{service}" -w "{token}"\n'
    r = subprocess.run([security_bin(), "-i"], input=cmd, capture_output=True, text=True, timeout=30)
    return r.returncode == 0


def failed(state, reason, note=""):
    state.update(last_run=now(), last_result=f"failed: {reason}")
    write_kv("state", state)
    log(f"rotation failed: {reason}{' ' + note if note else ''}")
    notify(f"Read-only token renewal failed: {reason}. The current token still works; it tries again tomorrow.")
    return 1


def rotate(cfg):
    state = read_kv("state")
    old = state.get("name", "")
    name = f"{cfg['base_name']}-{today():%Y%m%d}"
    if name == old:
        name += datetime.datetime.now().strftime("-%H%M")
    log(f"rotating: creating {name} (read_items on the read-only vault, {cfg['expires_days']}d); asking 1Password")
    notify("Renewing the read-only 1Password token: approve the 1Password prompt.")

    argv = [op_bin()] + (["--account", cfg["account"]] if cfg.get("account") else []) + [
        "service-account", "create", name, "--vault", f"{cfg['vault']}:read_items",
        "--expires-in", f"{cfg['expires_days']}d", "--raw"]
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=CREATE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return failed(state, "1Password prompt not approved in time")
    token = r.stdout.strip()
    del r.stdout
    if r.returncode != 0 or not TOKEN.match(token):
        return failed(state, "could not create the service account", last_line(r.stderr))

    # The new token must read a read-only item before it replaces the current one.
    env = {k: v for k, v in os.environ.items() if not k.startswith("OP_")}
    env["OP_SERVICE_ACCOUNT_TOKEN"] = token
    try:
        v = subprocess.run([op_bin(), "read", "--no-newline", cfg["verify_ref"]], env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        ok = v.returncode == 0 and bool(v.stdout)
        del v
    except subprocess.TimeoutExpired:
        ok = False
    if not ok:
        return failed(state, f"new service account {name} could not read the check item",
                      "Delete it in the 1Password web app.")

    if not keychain_write(cfg["keychain_service"], token) or keychain_read(cfg["keychain_service"]) != token:
        return failed(state, "could not save the new token to the Keychain",
                      f"Service account {name} was created; delete it in the 1Password web app.")
    token = None

    expires = today() + datetime.timedelta(days=cfg["expires_days"])
    state = {"name": name, "expires": expires.isoformat(), "previous": old,
             "last_run": now(), "last_result": "ok"}
    write_kv("state", state)
    try:
        os.remove(os.path.join(state_dir(), "rotate-now"))
    except FileNotFoundError:
        pass
    log(f"rotated: {name} saved, expires {expires}; previous {old or '(none)'} still valid until its own expiry")
    notify(f"Read-only token renewed; good until {expires}."
           + (f" You can delete the old service account {old} in the 1Password web app." if old else ""))
    return 0


def locked(fn):
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    with open(os.path.join(state_dir(), "lock"), "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("op-rotate: another rotation is running", file=sys.stderr)
            return 1
        return fn()


def due(cfg, state):
    if os.path.exists(os.path.join(state_dir(), "rotate-now")):
        return True
    left = days_left(state)
    return left is None or left <= cfg["warn_days"]


def cmd_check():
    cfg = load_config()
    if not due(cfg, read_kv("state")):
        return 0
    return locked(lambda: rotate(cfg))


def cmd_status(hook):
    state = read_kv("state")
    if not state:
        if not hook:
            print("op-rotate: not set up (no state file)")
        return 0
    cfg = read_kv("config")
    warn = int(cfg.get("warn_days", 14))
    left = days_left(state)
    result = state.get("last_result", "")
    if hook:
        if left is not None and left < 0:
            print(f"op-rotate: the read-only 1Password token EXPIRED on {state['expires']}; read connections "
                  "can't start. Tell the owner to run `op-rotate rotate` and approve the 1Password prompt.")
        elif left is not None and left <= warn:
            print(f"op-rotate: the read-only 1Password token expires in {left} days ({state['expires']}). "
                  "The daily job asks the owner for one 1Password approval; or they can run `op-rotate rotate`."
                  + (f" Last attempt: {result}." if result.startswith("failed") else ""))
        elif result.startswith("failed"):
            print(f"op-rotate: last token renewal {result}.")
        return 0
    print(f"service account: {state.get('name', '?')}")
    print(f"expires:         {state.get('expires', '?')} ({left} days)")
    print(f"renews from:     {warn} days before")
    print(f"last run:        {state.get('last_run', 'never')} {result}")
    return 0


def cmd_seed(name, expires):
    if not SAFE.match(name):
        raise SystemExit("op-rotate: bad name")
    datetime.date.fromisoformat(expires)
    state = read_kv("state")
    state.update(name=name, expires=expires)
    write_kv("state", state)
    log(f"seeded: {name} expires {expires}")
    return 0


def cmd_plist():
    script = os.path.expanduser("~/.local/bin/op-rotate")
    print(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array><string>{sys.executable}</string><string>-I</string><string>{script}</string><string>check</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{state_dir()}/launchd.log</string>
  <key>StandardErrorPath</key><string>{state_dir()}/launchd.log</string>
</dict>
</plist>""")
    return 0


def main(argv):
    if argv[:1] == ["check"] and len(argv) == 1:
        return cmd_check()
    if argv[:1] == ["rotate"] and len(argv) == 1:
        cfg = load_config()
        return locked(lambda: rotate(cfg))
    if argv[:1] == ["status"] and argv[1:] in ([], ["--hook"]):
        return cmd_status(argv[1:] == ["--hook"])
    if argv[:1] == ["seed"] and len(argv) == 3:
        return cmd_seed(argv[1], argv[2])
    if argv == ["plist"]:
        return cmd_plist()
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
