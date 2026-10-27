# Change log

Log every proposed change here, whether it's approved or not. Newest entries go at the top. Entries use role names; exact object names and IDs are in `private/changes.md` under the same date and title.

Template:

```
## YYYY-MM-DD: <short title>
- Status: proposed | approved | applied | rejected
- Target: <device / object>
- Why:
- Diff:
- Rollback:
- Approved by / when:
```

## 2026-10-26: Synology MCP: deny write tools in the agent client
- Status: proposed
- Target: agent client user settings (permission deny rules)
- Why: 43 write tools with no gating, running as a NAS administrator, no per-call prompt ([vetting](vetting/synology-mcp.md))
- Diff: add `deny` rules for the 43 write tools and `synology_login`, plus deny writes/edits to the server's config directory (so the remote bridge can't be enabled)
- Rollback: remove the rules
- Approved by / when: pending

## 2026-10-26: Synology MCP: hash lock, fixed working directory, TLS verification
- Status: proposed
- Target: the local wrapper script that starts the Synology MCP
- Why: floating dependencies; `./.env` gets loaded from the agent's working directory; TLS verification off while sending an admin password
- Diff: `cd` into the wrapper's own directory before starting; run from a venv built from `docs/vetting/locks/mcp-server-synology-1.8.0.txt`; `VERIFY_SSL=true` with `REQUESTS_CA_BUNDLE` set to the NAS certificate (requires a cert valid for the address used)
- Rollback: restore the previous wrapper
- Approved by / when: pending

## 2026-10-26: Synology MCP: non-admin account for everyday reads
- Status: proposed (needs testing which read tools work without admin)
- Target: NAS accounts; Synology MCP config
- Why: the agent's NAS account is in `administrators`
- Diff: create a non-admin read account for daily use; keep admin credentials for change windows only, or put a filtering MCP proxy in front with a read-tool allowlist and a call log
- Rollback: switch the MCP back to the current account
- Approved by / when: pending

## 2026-10-26: Run the UniFi MCP from the hash-locked environment
- Status: proposed
- Target: agent machine; the UniFi MCP server launch command
- Why: `uvx unifi-network-mcp==0.38.3` re-resolves the libraries that hold the permission gate on every run ([vetting](vetting/unifi-mcp.md), Finding 3)
- Diff: create a venv from `docs/vetting/locks/unifi-network-mcp-0.38.3.txt` with `--require-hashes --no-deps --no-build`; point the MCP server command at that venv's `unifi-network-mcp` instead of `uvx`; disable the plugin's own server entry
- Rollback: re-enable the plugin's server entry
- Approved by / when: pending

## 2026-10-26: Category-scoped change windows
- Status: proposed
- Target: `scripts/change-window.sh`
- Why: server-wide `update` also enables reboot, firmware upgrade, port power-cycle and permanent client deletion ([vetting](vetting/unifi-mcp.md), Finding 5)
- Diff: `open` takes the categories the change needs and enables only `UNIFI_POLICY_NETWORK_<CATEGORY>_<ACTION>` for those, leaving server-wide create/update off. First check how the client passes extra env vars to the MCP process
- Rollback: revert the script
- Approved by / when: pending

## 2026-10-26: Daily gateway backups to the NAS
- Status: approved 2026-10-26 (design in [gateway-backups.md](gateway-backups.md)); building
- Target: gateway (new backup account; auto-backup weekly → daily), NAS (share, two users, immutable snapshots, scheduled job)
- Why: the only gateway backups are stored on the gateway itself; change windows need a verified off-box restore point
- Diff: see the build order in gateway-backups.md; the gateway auto-backup schedule `30 0 * * 0` → `30 0 * * *`, max files unchanged
- Rollback: disable the NAS task; set the auto-backup schedule back to weekly; the share and snapshots can stay
- Approved by / when: owner, in chat, 2026-10-26 (design; each device step still runs as its own step)

## 2026-10-26: Disable stale WAN port forwards to the NAS
- Status: proposed
- Target: gateway, two port-forward rules to the NAS
- Why: they expose the NAS to the internet on two ports; the service they were for now runs behind a VPN tunnel in the app VM
- Diff: `enabled: true -> false` on both (toggle, not delete)
- Rollback: toggle both back on
- Check first: whether anything on the NAS still uses those ports
- Approved by / when: pending

## 2026-10-26: Disable rpcbind on the app VM
- Status: proposed
- Target: app VM, systemd `rpcbind.service` / `rpcbind.socket`
- Why: listening on `0.0.0.0:111` and `[::]:111`; NFSv4.1 (the only NFS use) doesn't need it
- Diff: `sudo systemctl disable --now rpcbind.socket rpcbind.service` and `sudo systemctl mask rpcbind`
- Rollback: `sudo systemctl unmask rpcbind && sudo systemctl enable --now rpcbind.socket`
- Verify: the NFS mount is still mounted and writable; `ss -tln` shows no :111
- Approved by / when: pending

## 2026-10-26: Turn UniFi MCP create/update policies off
- Status: applied 2026-10-26 via `scripts/change-window.sh close` (takes effect after `/reload-plugins`); read-only is now the default, and writes go through change windows (see [change-control.md](change-control.md))
- Target: Claude Code user settings, `pluginConfigs["unifi-network@unifi-plugins"]`
- Why: Phase 1 is read-only, but `policy_create` and `policy_update` are both `true`, so the MCP can create and modify objects (the confirm prompt is the only remaining guard).
- Diff: `policy_create: true -> false`, `policy_update: true -> false` (`policy_delete` is already off)
- Rollback: set them back to `true`, then `/reload-plugins`
- Approved by / when: owner, in chat, 2026-10-26
