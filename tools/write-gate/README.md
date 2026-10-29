# write-gate

Keeps each write connection (`unifi-write`, `synology-write`) off until a write is next, so sessions don't start them, or ask 1Password for their passwords, by default. Proposed in the 2026-10-29 entry "No 1Password prompts for read connections" in [changes.md](../../docs/changes.md), step 2.

```
write-gate on <connection> [minutes]    agent, when a write is next (default 60, max 240)
write-gate off [<connection>]           back off now (all if none given)
write-gate status
write-gate run --name <connection> -- <cmd> [args...]   the MCP config entry
```

## How a write goes

1. The agent says it's turning writes on for one connection, and that a 1Password prompt is coming.
2. It runs `write-gate on <connection>`. Within a second or two the gate starts the real server **in place**, which asks 1Password once. That's the owner's only sign-in.
3. Once the server is up, the gate tells the client its tool list changed, so the write tools appear with no reconnect. `write-gate status` shows `server ready`.
4. Each write call still needs the owner's click (`ask` rule). That's approval of the specific change, not a second sign-in.
5. When the window ends, the gate stops the real server once no call is in flight, and the tools go away.

## Behaviour

- **Off:** `run` answers as a stand-in MCP server with **no tools** and never starts `<cmd>`, so no password is read. The client sees a working connection, which avoids the failed-connection cache that skips a server for 15 minutes.
- **One session:** `on` records the session it was run from (the nearest `claude` process above it), and only that session's gate starts the real server. Other open sessions stay off, so there's one prompt, not one per session. Run from a terminal outside any session, `on` applies to every open session.
- **One connection:** windows are per connection, so turning on `unifi-write` doesn't start `synology-write`.
- **Failure:** if the real server exits or doesn't come up within 3 minutes (prompt ignored or denied), the status is `failed` and it isn't retried in that window. Running `on` again retries.
- **State:** `~/.config/netstack/write-gate/<connection>.on-until` (expiry and session) and `.status`. Turning writes on doesn't grant anything by itself: the real server still needs the owner's 1Password approval, and each call still needs a click.
- Why not the client's own per-project MCP disable: reports say it fails in the desktop app, isn't inherited by worktrees and hasn't always applied at startup.

Stdlib Python. Offline tests in `test_write_gate.py` run a fake server behind the gate (in CI).

## Install (owner, tier 3)

```
install -m 755 tools/write-gate/write_gate.py ~/.local/bin/write-gate
```

Each write connection's MCP entry becomes `python3 -I ~/.local/bin/write-gate run --name <connection> -- <original command and args>`.

## Couldn't verify

- **That this Claude Code version refreshes a local server's tools on `tools/list_changed`.** The docs say it does; several bug reports say it didn't for stdio servers, without saying which version fixed it. A headless test couldn't run (the CLI isn't signed in). The first real write is the test. If the tools don't appear after the 1Password approval, reconnecting the write connection in `/mcp` picks them up, since the real server is already running behind the gate
- That the real servers accept the client's `initialize` replayed by the gate (the fake server in the tests does)
- The session match on machines where the client process isn't named `claude`
