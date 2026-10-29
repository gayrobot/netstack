#!/usr/bin/env python3
"""write-gate: keeps a write connection off until writes are turned on for it.

  write-gate run --name <connection> -- <command> [args...]   MCP config entry for a write connection
  write-gate on <connection> [minutes]                        allow it to start (default 60, max 240)
  write-gate off [<connection>]                               back off now (all if none given)
  write-gate status

`run` is the MCP server the client talks to. While writes are off it answers as a stand-in
with no tools, so no password is read and there's no 1Password prompt. When `on` is run for
its connection, it starts the real server in place (which asks 1Password once), proxies to
it, and tells the client its tool list changed, so nobody has to reconnect anything. When
the window ends it stops the real server once no call is in flight, and the tools go away.

Turning writes on doesn't grant anything by itself: the real server still needs the owner's
1Password approval, and each call still needs the client's `ask` approval. The agent runs
`on` when a write is next and tells the owner to expect the 1Password prompt.

Stdlib only, stdio transport (newline-delimited JSON-RPC). Run with: python3 -I write_gate.py
"""
import json
import os
import re
import subprocess
import sys
import threading
import time

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_MINUTES = 60
MAX_MINUTES = 240
START_TIMEOUT_S = 180  # time for the owner to approve the 1Password prompt
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
HANDSHAKE_ID = "write-gate-handshake"


def state_dir():
    return os.environ.get("WRITE_GATE_DIR") or os.path.expanduser("~/.config/netstack/write-gate")


def poll_s():
    return float(os.environ.get("WRITE_GATE_POLL_S", "1"))


def check_name(name):
    if not NAME.match(name or ""):
        raise ValueError(f"bad connection name: {name!r}")
    return name


def path(name, kind):
    return os.path.join(state_dir(), f"{check_name(name)}.{kind}")


def session_pid():
    """PID of the nearest `claude` process above this one: the client session that ran us.

    Each session runs its own `claude` process, with its MCP servers and its shell below it,
    so this is how `on` (run from the agent's shell) and a gate (run by the client) agree on
    which session the window is for. None when run outside a session, e.g. from a terminal.
    """
    if os.environ.get("WRITE_GATE_SESSION"):
        return int(os.environ["WRITE_GATE_SESSION"])
    pid = os.getppid()
    while pid > 1:
        try:
            out = subprocess.run(["/bin/ps", "-o", "ppid=,comm=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=5).stdout.split(None, 1)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if len(out) < 2:
            return None
        if os.path.basename(out[1].strip()) == "claude":
            return pid
        pid = int(out[0])
    return None


def read_window(name, now=None):
    """(until, session) for this connection's window, or (None, None) if writes are off.

    session is the PID of the session the window is for, or None for every session."""
    try:
        with open(path(name, "on-until")) as f:
            fields = f.read().split()
        until = int(fields[0])
        session = int(fields[1]) if len(fields) > 1 else None
    except (OSError, ValueError, IndexError):
        return None, None
    return (until, session) if until > (now or time.time()) else (None, None)


def on_until(name, now=None):
    """Epoch seconds writes stay on until for this connection, or None if they're off."""
    return read_window(name, now)[0]


def turn_on(name, minutes, session=None):
    if not 1 <= minutes <= MAX_MINUTES:
        raise ValueError(f"minutes must be 1 to {MAX_MINUTES}")
    until = int(time.time()) + minutes * 60
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    with open(path(name, "on-until"), "w") as f:
        f.write(f"{until}" + (f" {session}" if session else "") + "\n")
    return until


def turn_off(name=None):
    names = [name] if name else known_names()
    for n in names:
        try:
            os.remove(path(n, "on-until"))
        except FileNotFoundError:
            pass


def known_names():
    try:
        files = os.listdir(state_dir())
    except FileNotFoundError:
        return []
    return sorted({f.rsplit(".", 1)[0] for f in files if f.endswith((".on-until", ".status"))})


def write_status(name, state):
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    with open(path(name, "status"), "w") as f:
        f.write(f"{state} {int(time.time())}\n")


def read_status(name):
    try:
        with open(path(name, "status")) as f:
            state, since = f.read().split()
        return state, int(since)
    except (OSError, ValueError):
        return "unknown", None


def stand_in(msg, starting=False):
    """Reply for the client while the real server isn't up."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None or method is None:
        return None  # notification, or a reply meant for a server that isn't running
    if method == "initialize":
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL_VERSION),
                  "capabilities": {"tools": {"listChanged": True}},
                  "serverInfo": {"name": "write-gate", "version": "0.2.0"},
                  "instructions": "This write connection is off, so it has no tools yet. When a write is next, "
                                  "the agent runs `write-gate on <connection>` and tells the owner to approve the "
                                  "1Password prompt; the tools then appear without a reconnect."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": []}
    else:
        why = "starting; waiting for the owner's 1Password approval" if starting else "writes are off"
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"{why}: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


class Gate:
    def __init__(self, name, command):
        self.name, self.command = check_name(name), command
        self.lock = threading.Lock()
        self.out_lock = threading.Lock()
        self.client_init = None   # the client's initialize params, replayed to the real server
        self.child = None
        self.ready = False
        self.started_at = None
        self.pending = set()      # client request ids forwarded to the real server
        self.closed = False

    def send(self, msg):
        with self.out_lock:
            sys.stdout.write(json.dumps(msg) + "\n")
            sys.stdout.flush()

    def tools_changed(self):
        self.send({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})

    # client -> gate
    def from_client(self, line):
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            self.send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            return
        with self.lock:
            if msg.get("method") == "initialize" and self.client_init is None:
                self.client_init = msg.get("params", {})
            if self.ready:
                if msg.get("method") and msg.get("id") is not None:
                    self.pending.add(msg["id"])
                self.child.stdin.write(line if line.endswith("\n") else line + "\n")
                self.child.stdin.flush()
                return
            starting = self.child is not None
        reply = stand_in(msg, starting)
        if reply is not None:
            self.send(reply)

    # real server -> gate
    def pump_child(self, child):
        for line in child.stdout:
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == HANDSHAKE_ID:
                with self.lock:
                    if child is not self.child:
                        return
                    if "error" in msg:
                        break
                    child.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
                    child.stdin.flush()
                    self.ready = True
                write_status(self.name, "ready")
                self.tools_changed()
                continue
            if msg.get("method") is None:
                with self.lock:
                    self.pending.discard(msg.get("id"))
            self.send(msg)
        self.child_gone(child)

    def child_gone(self, child):
        with self.lock:
            if child is not self.child:
                return
            was_ready = self.ready
            self.child, self.ready, self.pending = None, False, set()
        child.poll()
        write_status(self.name, "failed" if on_until(self.name) else "off")
        if was_ready:
            self.tools_changed()

    def start_child(self):
        child = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        with self.lock:
            self.child, self.ready, self.started_at = child, False, time.time()
            child.stdin.write(json.dumps({"jsonrpc": "2.0", "id": HANDSHAKE_ID, "method": "initialize",
                                          "params": self.client_init}) + "\n")
            child.stdin.flush()
        write_status(self.name, "starting")
        threading.Thread(target=self.pump_child, args=(child,), daemon=True).start()

    def stop_child(self):
        with self.lock:
            child = self.child
        if child is None:
            return
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
        self.child_gone(child)

    def watch(self):
        last_failed_window = None
        me = session_pid()
        while not self.closed:
            time.sleep(poll_s())
            until, session = read_window(self.name)
            if session is not None and session != me:
                until = None  # the window is for another session
            with self.lock:
                child, ready, busy = self.child, self.ready, bool(self.pending)
                have_init = self.client_init is not None
                started_at = self.started_at
            if until and child is None and have_init and until != last_failed_window:
                if read_status(self.name)[0] == "failed":
                    last_failed_window = until  # don't re-prompt in the same window; `on` again retries
                    continue
                self.start_child()
            elif child is not None and not ready and time.time() - started_at > START_TIMEOUT_S:
                self.stop_child()
                write_status(self.name, "failed")
            elif child is not None and not until and not busy:
                self.stop_child()
                write_status(self.name, "off")

    def serve(self):
        write_status(self.name, "off" if not on_until(self.name) else "waiting")
        threading.Thread(target=self.watch, daemon=True).start()
        for line in sys.stdin:
            if line.strip():
                self.from_client(line)
        self.closed = True
        self.stop_child()


def fmt(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "run":
        args = argv[2:]
        if len(args) < 4 or args[0] != "--name" or args[2] != "--":
            sys.exit("usage: write-gate run --name <connection> -- <command> [args...]")
        Gate(args[1], args[3:]).serve()
    elif cmd == "on":
        if len(argv) < 3:
            sys.exit("usage: write-gate on <connection> [minutes]")
        name = check_name(argv[2])
        session = session_pid()
        until = turn_on(name, int(argv[3]) if len(argv) > 3 else DEFAULT_MINUTES, session)
        write_status(name, "waiting")  # clears an earlier failure, so this window tries again
        who = f"session {session}" if session else "every open session"
        print(f"{name}: writes on until {fmt(until)} for {who}. It starts within a few seconds and asks "
              "1Password once; approve it and the tools appear.")
    elif cmd == "off":
        turn_off(check_name(argv[2]) if len(argv) > 2 else None)
        print("Writes off. A running write server stops once no call is in flight.")
    elif cmd == "status":
        names = known_names()
        if not names:
            print("No write connections seen yet.")
        for name in names:
            until = on_until(name)
            state, since = read_status(name)
            window = f"on until {fmt(until)}" if until else "off"
            print(f"{name}: writes {window}; server {state}" + (f" since {fmt(since)}" if since else ""))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
