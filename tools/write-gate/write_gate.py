#!/usr/bin/env python3
"""write-gate: keeps a write connection off until the owner turns writes on.

  write-gate run -- <command> [args...]   MCP config entry for a write connection
  write-gate on [minutes]                 owner: allow write connections to start (default 60, max 240)
  write-gate off                          owner: back off now
  write-gate status

`run` starts the real server only while writes are on. Otherwise it serves a stand-in MCP
server with no tools, so the connection succeeds without reading a password (no 1Password
prompt, and no failed connection for the client to cache). Turning writes on only lets the
real server start; it still needs the owner's 1Password approval, and each call still needs
the client's `ask` approval. A server that's already running keeps running after the window
ends; the window decides the next start.

Stdlib only, stdio transport (newline-delimited JSON-RPC). Run with: python3 -I write_gate.py
"""
import json
import os
import sys
import time

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_MINUTES = 60
MAX_MINUTES = 240
INSTRUCTIONS = ("This write connection is off, so it has no tools. To make a write, the owner runs "
                "`write-gate on`, then reconnects this server in /mcp or starts a new session. "
                "The agent doesn't turn writes on itself.")


def state_file():
    return os.environ.get("WRITE_GATE_FILE") or os.path.expanduser("~/.config/netstack/writes-on-until")


def on_until(now=None):
    """Epoch seconds writes stay on until, or None if they're off."""
    try:
        with open(state_file()) as f:
            until = int(f.read().strip())
    except (OSError, ValueError):
        return None
    return until if until > (now or time.time()) else None


def turn_on(minutes):
    if not 1 <= minutes <= MAX_MINUTES:
        raise ValueError(f"minutes must be 1 to {MAX_MINUTES}")
    until = int(time.time()) + minutes * 60
    path = state_file()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w") as f:
        f.write(f"{until}\n")
    return until


def turn_off():
    try:
        os.remove(state_file())
    except FileNotFoundError:
        pass


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None  # notification
    if method == "initialize":
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL_VERSION),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "write-gate (writes off)", "version": "0.1.0"},
                  "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": []}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"writes are off: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve_stand_in():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


def fmt(until):
    return time.strftime("%H:%M", time.localtime(until))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "run":
        real = argv[3:] if argv[2:3] == ["--"] else argv[2:]
        if not real:
            sys.exit("write-gate run: no command given")
        if on_until():
            os.execv(real[0], real)
        print("write-gate: writes are off; serving a stand-in with no tools", file=sys.stderr)
        serve_stand_in()
    elif cmd == "on":
        until = turn_on(int(argv[2]) if len(argv) > 2 else DEFAULT_MINUTES)
        print(f"Writes on until {fmt(until)}. Reconnect unifi-write / synology-write in /mcp, "
              "or start a new session; each asks 1Password once.")
    elif cmd == "off":
        turn_off()
        print("Writes off. Running write connections stay up until the session ends or they're reconnected.")
    elif cmd == "status":
        until = on_until()
        print(f"Writes on until {fmt(until)}." if until else "Writes off.")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
