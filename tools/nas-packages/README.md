# nas-packages

A two-tool MCP server for DSM Package Center, used to apply vendor security updates (for example Synology-SA-26:14) without giving the agent a shell on the NAS.

| Tool | Does | Never does |
|---|---|---|
| `package_list` | lists installed packages, their versions, and whether Synology's package server offers a newer one | change anything |
| `package_upgrade(package_id, dry_run=true)` | upgrades one installed package to the version Synology's package server offers | install, uninstall, downgrade, upload a `.spk`, download from anywhere but `*.synology.com` |

- **One file, stdlib only** ([server.py](server.py)), so there are no dependencies to lock or vet. Requests go through `curl` with `--pinnedpubkey`, the same TLS pin as `scripts/change-window.sh`.
- **One NAS**, set by the environment. No tool takes a host or URL.
- **The password** comes from `NAS_PASSWORD_COMMAND` (run without a shell), is sent on curl's stdin, and never appears in argv, tool arguments or output.
- **Both tools need an administrator**: DSM returns error 105 for package calls from a non-admin account. How the list tool is gated is the owner's decision; see `docs/changes.md`.
- `package_upgrade` is a dry run unless the call passes `"dry_run": false`, so the approval prompt shows that explicitly.

Setup is in [mcp.example.json](mcp.example.json). Registering the server, its credential and its permission rules is a tier 3 step for the owner.

Tests (offline, DSM is faked):

```bash
python3 -I tools/nas-packages/test_server.py
```

## Couldn't verify

- **The DSM request parameters.** Synology doesn't document the Package Center API. The method names and keys come from the community `synology-api` wrapper and haven't been run against this NAS yet: `SYNO.Core.Package` `list`, `SYNO.Core.Package.Server` `list`, and `SYNO.Core.Package.Installation` `install` / `status` / `upgrade`, plus `.Download` `check`. The first real run should be `package_list`, then a dry run, then one upgrade of a low-risk package with the owner watching Package Center.
- That `SYNO.Core.Package.Server` `list` returns `link`, `md5` and `size` for packages in the official Synology channel. If it doesn't, the tool refuses to upgrade; it doesn't guess.
- Accounts with 2-step verification: login doesn't send an OTP, so the account has to be one without 2FA, like the existing agent write account.
- Whether DSM restarts a package after the upgrade the same way the UI does (`installrunpackage=true` is meant to).
