# Change control: just-in-time write access

The agent manages the network, but it doesn't hold standing write access to the gateway. It reads all the time, and it writes only inside a short window opened for one approved change.

## Why

- **Blast radius.** One bad firewall or VLAN write can cut off the path the agent itself uses, so it can't undo its own mistake.
- **Prompt injection.** The agent reads data it doesn't control (client hostnames, device names, SSIDs, fetched docs). With standing write access, text in that data could end up as a config change.
- **Approval fatigue.** Per-call confirm prompts get rubber-stamped. A window ties every write to a reviewed entry in `changes.md`.

## Default state

- UniFi MCP `policy_create`, `policy_update` and `policy_delete` are all **off**.
- A `SessionStart` hook (`.claude/settings.json`) warns at the start of every session if a window was left open.

## Flow

1. **Propose.** The agent writes an entry in `docs/changes.md` with the diff, rollback and verification.
2. **Approve.** The owner approves it in chat. One approval covers one entry.
3. **Open.** `scripts/change-window.sh open "<exact entry title>"` refuses titles that aren't in `changes.md`. Then run `/reload-plugins`.
4. **Apply and verify.** The agent applies only that diff (the MCP still previews each mutation), then runs the entry's verification.
5. **Close.** Run `scripts/change-window.sh close`, then `/reload-plugins`. Update the entry's status, then commit `changes.md` and `change-windows.log` together.

`policy_delete` is never turned on by the script. Disable things instead of deleting them; a deletion is done by hand.

## Two accounts (recommended)

On its own, the script only flips the MCP's client-side flags, which are enforced by the MCP's own code. For a boundary the gateway enforces:

- **Read-only account:** UDM role *View Only* for Network. This is the default.
- **Write account:** a separate local UDM admin, used only during windows.

Put both in `private/change-window.conf` (gitignored, shell syntax; the values are commands that fetch secrets, not the secrets themselves):

```
RO_USERNAME=<read-only account>
RO_PASSWORD_COMMAND=<absolute argv that prints its password>
RW_USERNAME=<write account>
RW_PASSWORD_COMMAND=<absolute argv that prints its password>
```

With that file present, `open` switches the MCP to the write account and `close` switches it back.

## Audit trail

- `docs/change-windows.log`: one line per open/close (UTC), committed
- `docs/changes.md`: what was proposed, approved and applied
- UDM system log: what the write account actually did

## Limits

- The window is closed by a person or the agent, not by a timer. The session-start warning is the backstop.
- A plugin option change needs `/reload-plugins` or a new session, so a session that started during a window keeps write access until it reloads.
