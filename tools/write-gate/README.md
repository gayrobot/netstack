# write-gate

Keeps the write connections (`unifi-write`, `synology-write`) off until the owner turns writes on, so sessions don't start them, or ask 1Password for their passwords, by default. Proposed in the 2026-10-29 entry "No 1Password prompts for read connections" in [changes.md](../../docs/changes.md), step 2.

```
write-gate on [minutes]    allow write connections to start (default 60, max 240)
write-gate off             back off now
write-gate status
write-gate run -- <cmd>    the MCP config entry for a write connection
```

- While writes are off, `run` serves a stand-in MCP server with **no tools** and never starts `<cmd>`, so no password is read. The client sees a working connection, which avoids the failed-connection cache that skips a server for 15 minutes.
- While writes are on, `run` replaces itself with `<cmd>`, which reads its password with the owner's 1Password approval as before. Per-call `ask` rules still apply.
- The state is one file, `~/.config/netstack/writes-on-until`, holding an expiry time. Turning writes on doesn't grant anything by itself, so the agent could flip it but still couldn't write without the owner's 1Password approval and a click per call. The agent doesn't do it anyway (see [change-control.md](../../docs/change-control.md)).
- Why not the client's own per-project MCP disable: reports say it fails in the desktop app, isn't inherited by worktrees and hasn't always applied at startup.

Stdlib Python, offline tests in `test_write_gate.py` (run in CI).

## Install (owner, tier 3)

```
install -m 755 tools/write-gate/write_gate.py ~/.local/bin/write-gate
```

Then each write connection's MCP entry becomes `python3 -I ~/.local/bin/write-gate run -- <original command and args>`.

## Couldn't verify

- That `/mcp` reconnect in the desktop app restarts a write connection after `write-gate on` (expected; a new session does)
- How the client behaves if a write connection's tools appear partway through a session that started with the stand-in (expected: a reconnect lists them)
