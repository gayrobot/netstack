# netstack

A home network (UniFi Dream Machine Pro, a Mac Pro VM host and the VMs on it) run as a governed, Claude Code-managed project. This is a public repo, so treat everything you commit here as published.

## Phase

**Phase 1: read-only.** Inventory the network and write docs. Change no config on any device.

Later phases (not active yet):
2. Drift detection and scheduled config backups
3. Writes, only as proposed diffs that the owner approves, logged in git

## Rules

1. **No firewall, VLAN, DHCP, port-forward, WLAN or routing changes** unless there is a written diff in `docs/changes.md` and the owner has explicitly approved it in chat. An approval covers that one change only.
2. **Don't SSH into the UDM.** Use the UniFi API through the MCP, which is a narrower surface and easier to audit.
3. **Don't read, print or `cat` `.env`** or any other credential file. Use `.env.example` to see which variables exist.
4. **Log every proposed change in `docs/changes.md`**, including ones that get rejected.
5. Use **read-only MCP tools only** (`list_*`, `get_*`, `lookup_*`). If a task seems to need a mutating tool, stop and propose it as a diff.
6. **Public vs. private.** Real hostnames, account names, service and container names, and the exact inventory go in `private/` (gitignored). Tracked files use role names only. See `docs/redaction.md`. No MACs, public IPs or IPv6 prefixes, passphrases, keys or serials anywhere tracked.
7. **Never bypass the hooks** (`--no-verify`). If `scripts/check-public.sh` blocks a commit, fix the content.
8. **Separate verified from inferred.** Every doc ends with a "Couldn't verify" list.

## Layout

- `docs/network.md`: VLANs, zones, inbound exposure (role names)
- `docs/hosts/`: one page per host role
- `docs/changes.md`: change log (proposed, approved, applied, rejected)
- `docs/vetting/`: supply-chain reviews of every MCP server and skill before it's used
- `docs/redaction.md`: how the public/private split is enforced
- `private/`: real specifics, raw dumps, the denylist (never committed)
- `.env.example`: variable names only, never values

## Environment notes

- Claude Code runs on an admin laptop and reaches hosts over SSH.
- The VM host runs no containers itself. Containers run in a Linux VM attached to a VLAN through macvlan, so the UDM's zone firewall decides who can reach them, not Docker port mappings.
