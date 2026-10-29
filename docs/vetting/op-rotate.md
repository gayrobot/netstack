# Vetting: op-rotate (first-party)

Reviewed 2026-10-29. Code: [tools/op-rotate](../../tools/op-rotate/README.md).

## Build or adopt

[build-or-adopt.md](build-or-adopt.md), landed on **step 4**:

| Step | Result |
|---|---|
| 1. Already connected | No. Nothing here renews the token |
| 2. Widen a permission | No. A service account can't create service accounts; that needs a person's sign-in |
| 3. Adopt third-party | No tool found (search 2026-10-29). 1Password's CLI has `create --expires-in` but no rotate, list or delete for service accounts, and its community forum has open requests for rotation and for pruning expired accounts. Third-party guides describe the same create-new, swap, delete-old routine by hand |
| 4. Build gaps-only | **Chosen.** One stdlib script, no dependencies |
| 5. Owner by hand | The fallback: rerun the commands from the install every 90 days. Rejected by the owner ("I want rotation automated") |

## Checklist

**Identity and provenance**
- Source: this repo, `tools/op-rotate/op_rotate.py`. Installed by copying (`install -m 755`), so the running copy doesn't follow branch changes
- Provenance: first-party, reviewed through a PR

**Dependencies**
- Python standard library only. Calls `/opt/homebrew/bin/op` (1Password CLI, already in use), `/usr/bin/security` and `/usr/bin/osascript`, by absolute path

**Behavior**
- Network: only through `op` (1Password)
- Processes: `op service-account create`, `op read` (check item only, output discarded), `security -i` / `security find-generic-password` (one Keychain item), `osascript` (notification). No shell
- Files: its own directory under `~/.config/netstack/op-rotate/`
- Runs automatically: daily and at login from a launchd agent the owner installs. Reads every line of it: `check` returns at once unless within 14 days of expiry or a `rotate-now` file exists
- Credentials: the new token is held in memory only, passed to `op read` by environment and to `security` on stdin, never in argv, logs, state or notifications (tested). Config values that reach argv or `security -i` must match `[A-Za-z0-9_.:/@-]+`, so a config line can't inject `security` options (tested)

**Authority**
- Creates one service account per rotation, with `read_items` on the read-only vault only, fixed in code. It can't ask for write access or another vault's access except through the config's vault name
- Overwrites one Keychain item. Deletes nothing in 1Password
- Each creation needs the owner's 1Password approval; nothing here can create one without it

**Verdict**
- **OK with conditions:** the owner installs it and writes its config (tier 3); the agent never runs `check` or `rotate`; old service accounts are deleted by the owner in the web app

## Couldn't verify

- See the tool's README: the launchd prompt path, `op`'s own prompt timeout, name uniqueness, and any limit on service-account count
