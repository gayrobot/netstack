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
