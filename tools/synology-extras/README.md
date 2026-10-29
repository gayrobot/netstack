# synology-extras

A first-party MCP server for the DSM features the third-party Synology MCP (`mcp-server-synology`, connectors `synology` and `synology-write`) doesn't cover. It's one connector, next to those two.

**Scope rule: gaps only** ([build-or-adopt.md](../../docs/vetting/build-or-adopt.md), step 4). A tool goes here only if the third-party MCP has nothing equivalent. If a later upstream release adds one, the upgrade PR settles it: one path per action, the safer one ([synology-mcp-upgrades.md](../../docs/vetting/synology-mcp-upgrades.md)). `CHECKED_AGAINST` in `server.py` records the upstream version each tool was last checked against, and a test fails until an upgrade PR rechecks them. Every new tool is a PR with a vetting addendum, because each one widens what the admin login can do.

Tools today (Package Center, for vendor security updates such as Synology-SA-26:14):

| Tool | Does | Never does |
|---|---|---|
| `package_list` | lists installed packages, their versions, and whether Synology's package server offers a newer one | change anything |
| `package_upgrade(package_id, dry_run=true)` | upgrades one installed package to the version Synology's package server offers | install, uninstall, downgrade, upload a `.spk`, download from anywhere but `*.synology.com` |

- **One file, stdlib only** ([server.py](server.py)), so there are no dependencies to lock or vet. Requests go through `curl` with `--pinnedpubkey`, the same TLS pin as `scripts/change-window.sh`.
- **One NAS**, set by the environment. No tool takes a host or URL.
- **The password** comes from `NAS_PASSWORD_COMMAND` (run without a shell), is sent on curl's stdin, and never appears in argv, tool arguments or output.
- **Every tool here needs an administrator**, because that's usually why the read connector can't do it (DSM error 105). So there's no read/write pair: one connector, and a permission rule per tool. Read-only tools are `allow`; anything that changes the NAS is `ask`. That's exception EX-1 in [docs/exceptions.md](../../docs/exceptions.md), approved by the owner 2026-10-28.
- **Off until needed.** Because it holds the admin login, it runs behind [write-gate](../write-gate/README.md) like the write connections (owner's choice, 2026-10-29). Sessions start it as a stand-in with no tools. When a package check or upgrade is next, the agent tells the owner and runs `write-gate on synology-extras`; the tools then appear for that session only, until the window ends. Starting it reads no password: `NAS_PASSWORD_COMMAND` runs on each tool call, so the 1Password prompt comes with the call, not with `on`.
- `package_upgrade` is a dry run unless the call passes `"dry_run": false`, so the approval prompt shows that explicitly.

Setup is in [mcp.example.json](mcp.example.json): local scope for this repo, wrapped in `write-gate run --name synology-extras`. Registering the server, its credential and its permission rules is a tier 3 step for the owner.

Tests (offline, DSM is faked):

```bash
python3 -I tools/synology-extras/test_server.py
```

## Couldn't verify

- **The DSM request parameters.** Synology doesn't document the Package Center API. The method names and keys come from the community `synology-api` wrapper and haven't been run against this NAS yet: `SYNO.Core.Package` `list`, `SYNO.Core.Package.Server` `list`, and `SYNO.Core.Package.Installation` `install` / `status` / `upgrade`, plus `.Download` `check`. The first real run should be `package_list`, then a dry run, then one upgrade of a low-risk package with the owner watching Package Center.
- That `SYNO.Core.Package.Server` `list` returns `link`, `md5` and `size` for packages in the official Synology channel. If it doesn't, the tool refuses to upgrade; it doesn't guess.
- Accounts with 2-step verification: login doesn't send an OTP, so the account has to be one without 2FA, like the existing agent write account.
- Whether DSM restarts a package after the upgrade the same way the UI does (`installrunpackage=true` is meant to).
- How often 1Password asks again when the password is read on each call (once per call, or once for a while after an approval).
- That this server works behind write-gate: the gate is tested with a fake server, and live with `unifi-write` only.
