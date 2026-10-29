# netstack

A home network (UniFi Dream Machine Pro, a Mac Pro VM host and the VMs on it) run as a governed, Claude Code-managed project. This is a public repo, so treat everything you commit here as published.

## Phase

1. Read-only inventory and docs: **done**.
2. Scheduled config backups: **done** (nightly, off-box, encrypted). Drift detection: not started.
3. Writes: **active since 2026-10-28**, through write connections where the owner approves every call (rule 5).

## Rules

1. **No firewall, VLAN, DHCP, port-forward, WLAN or routing changes** unless there is a written diff in `docs/changes.md` and the owner has explicitly approved it in chat. An approval covers that one change only.
2. **Don't SSH into the UDM.** Use the UniFi API through the MCP, which is a narrower surface and easier to audit.
3. **Don't read, print or `cat` `.env`** or any other credential file. Use `.env.example` to see which variables exist.
4. **Log every proposed change in `docs/changes.md`**, including ones that get rejected.
5. **Read with the read connections, write with the write connections.** Each device has a read connection (read-only account, no prompts) and a write connection (write account; the owner approves every call in the client). Never use a write connection for reads. Write connections are off until a write is next: tell the owner a 1Password prompt is coming, then run `write-gate on <connection>` yourself and wait for the tools to appear (`write-gate status`). Tiers (`docs/change-control.md`):
   - **Tier 1** (names, labels, a port forward toggle, a DHCP reservation, restarting one device): propose the call, the owner approves it, then log it in `docs/changes.md`.
   - **Tier 2** (everything in rule 1, plus NAS share permissions): a `changes.md` entry and chat approval first, then `scripts/change-window.sh open "<title>"` (checks for a fresh restore point and logs), apply, verify, `close`.
   - **Tier 3** (accounts, authentication, backups, snapshots, these controls themselves): never through the agent. Propose; the owner does it.
6. **Public vs. private.** Real hostnames, account names, service and container names, and the exact inventory go in `private/` (gitignored). Tracked files use role names only. See `docs/redaction.md`. No MACs, public IPs or IPv6 prefixes, passphrases, keys or serials anywhere tracked.
7. **Never bypass the hooks** (`--no-verify`). If `scripts/check-public.sh` blocks a commit, fix the content.
8. **Separate verified from inferred.** Every doc ends with a "Couldn't verify" list.
9. **Every repo change goes through a pull request.** Work on a branch, run `scripts/check-public.sh tree`, push the branch and open a PR. Never commit or push to `main` directly. The owner reviews and merges; the `check-public` and `tests` CI jobs must pass first.
10. **Exceptions and new capabilities follow the rubrics.** An exception to these rules goes through `docs/exceptions.md` (check its register before relying on one). A new agent capability goes through `docs/vetting/build-or-adopt.md`.

## Layout

- `docs/strategy.md` + `docs/backlog.md`: what we're protecting, from what, in what order; the ordered list of work. Start here
- `docs/network.md`: VLANs, zones, inbound exposure (role names)
- `docs/hosts/`: one page per host role
- `docs/changes.md`: change log (proposed, approved, applied, rejected)
- `docs/change-control.md` + `scripts/change-window.sh`: write tiers and the restore-point gate; `docs/change-windows.log` is its audit log
- `docs/vetting/`: supply-chain reviews of every MCP server and skill before it's used
- `tools/`: first-party code
- `docs/redaction.md`: how the public/private split is enforced
- `private/`: real specifics, raw dumps, the denylist (never committed)
- `.github/workflows/check-public.yml`: the same scan in CI, with the denylist from the `DENYLIST` secret
- `.env.example`: variable names only, never values

## Environment notes

- Claude Code runs on an admin laptop and reaches hosts over SSH.
- The VM host runs no containers itself. Containers run in a Linux VM attached to a VLAN through macvlan, so the UDM's zone firewall decides who can reach them, not Docker port mappings.
