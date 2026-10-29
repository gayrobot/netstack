# Change control: just-in-time write access

The agent manages the network, but it doesn't hold standing write access to the gateway. It reads all the time, and it writes only inside a short window opened for one approved change.

This is step 1. Where it's headed (a broker that holds credentials, self-expiring grants, risk tiers) is in [jit-design.md](jit-design.md).

## Current setup: write connections with per-call approval (since 2026-10-28)

Each device has two MCP connections:

| Connection | Account | Prompts |
|---|---|---|
| Gateway read (the UniFi plugin) | View Only | none |
| Gateway write (`unifi-write`, hash-locked environment) | Network Site Admin; create and update on, delete off | the owner approves **every call** (an `ask` rule in the client) |
| NAS read (`synology`) | non-admin | none; write tools denied |
| NAS write (`synology-write`) | administrator | the owner approves **every call**; `synology_login` denied |
| NAS extras (`synology-extras`, first-party, gaps in the Synology MCP only; **proposed, not registered**) | administrator (the NAS write account) | per tool: read-only tools (`package_list`) need no prompt; anything that changes the NAS (`package_upgrade`) needs the owner's approval on **every call**. Exception EX-1 in [exceptions.md](exceptions.md): these reads need admin |

What each tier needs:

- **Tier 1** (small, reversible: names, labels, a port forward toggle, a DHCP reservation, restarting one device): one click on the call, then a log entry.
- **Tier 2** (firewall, VLAN, DHCP scopes, WAN, VPN, WLAN, routing, NAS share permissions): a `changes.md` entry, chat approval, then `change-window.sh open`. With `WINDOW_MODE=gate` the script only checks for a fresh off-box restore point and logs; the write itself is still one click per call.
- **Tier 3** (accounts, authentication, backups, snapshots, these controls): never through the agent.

The approval prompt shows the exact tool and arguments, so approving it is the change control. The risk is rubber-stamping; tier 2 keeps the restore-point gate for the changes that can cut off the network.

The sections below describe the original flag-flipping windows (`WINDOW_MODE=flags`), kept for setups with a single connection.

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
3. **Open.** `scripts/change-window.sh open "<exact entry title>"` refuses titles that aren't in `changes.md`, and refuses to open without a usable restore point (below). Then run `/reload-plugins`.
4. **Apply and verify.** The agent applies only that diff (the MCP still previews each mutation), then runs the entry's verification.
5. **Close.** Run `scripts/change-window.sh close`, then `/reload-plugins`. Update the entry's status, then commit `changes.md` and `change-windows.log` together.

`policy_delete` is never turned on by the script. Disable things instead of deleting them; a deletion is done by hand.

## Restore point required

A window that can write to the gateway won't open without a recent off-box backup of it.

- **NAS (normal case):** the NAS job stores a fresh, encrypted gateway backup every night. `open` fetches the job's manifest and that backup over the DSM API as a read-only NAS account (TLS pinned), then checks age, the archive check and the sha256. Nothing to do by hand. See [gateway-backups.md](gateway-backups.md).
- **Manual fallback, record a backup:** download one from UniFi OS (Settings → System → Backups → Download), store it off the gateway, then run `scripts/change-window.sh backup <file.unf>`. This records the path, the file's modification time and its sha256 in `private/backup-record.tsv`, plus a sha256 prefix in `change-windows.log`.
- **Gate:** `open` refuses unless the latest recorded backup is younger than `BACKUP_MAX_AGE_DAYS` (default 3, set in `private/change-window.conf`), still exists at its path, and still matches its sha256. The `OPEN` log line names the restore point it relied on.
- **Why off-box:** the gateway's own weekly auto-backups live on the gateway, and cloud backup is off. If the gateway is what breaks, those copies go with it.
- **Handle the file as a secret.** A `.unf` contains Wi-Fi passphrases, VPN keys and admin hashes, and its encryption uses a well-known static key, so treat it as plaintext. It's gitignored (`*.unf`, `private/`).

Limits: age comes from the file's modification time, so this guards against forgetting, not against someone deliberately faking it. It also checks that a backup exists, not that it restores. A periodic test restore (for example to a spare controller) would close that gap.

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
