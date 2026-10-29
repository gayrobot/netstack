# Vetting: synology-extras (first-party, gaps in the Synology MCP)

**Reviewed:** 2026-10-28, against the [checklist](README.md). The author is the agent, so the owner's PR review is the independent review.
**Verdict:** **OK with conditions** (below). Not registered yet.

## Identity and provenance

- [x] Source: this repo, [`tools/synology-extras/server.py`](../../tools/synology-extras/server.py), one file, first-party. License: the repo's.
- [x] What gets installed: nothing. The client runs the file from a checkout of `main` with the system `python3 -I`.
- [x] Artifact traced to source: the source is the artifact. Run it from a checkout of a merged commit, not from a branch.
- [x] Installed files match: n/a (no package).

## Dependencies

- [x] Python standard library only, plus the system `curl` (for `--pinnedpubkey`). No third-party packages.
- [x] Security logic in a dependency: TLS pinning is curl's, the same as `scripts/change-window.sh`.
- [x] Hash lock: n/a, nothing to lock. If a dependency is ever added, it needs a lock under `locks/` and an addendum here.

## Behavior

- [x] Outbound: only `NAS_URL` from the environment. No tool takes a host, so a prompt injection can't point it elsewhere. Upgrade downloads are made by the NAS, and the tool refuses any `link` that isn't `https` on `synology.com` or a subdomain of it (tested, including a lookalike host).
- [x] Processes: `curl` and the password command, both as argv lists with no shell. No `eval`, `exec` or `pickle`. No file reads or writes; it doesn't load `.env` or anything from the working directory.
- [x] Startup hooks: none. `python3 -I` ignores `PYTHON*` variables and the script's directory on import paths.
- [x] Credentials: password from `NAS_PASSWORD_COMMAND`, sent only on curl's stdin (never in argv, so `ps` can't see it). The session ID is sent the same way. Errors report the DSM error code, never the request.

## Authority

- [x] Actions, as the code declares them:
  - read: `package_list` (`SYNO.Core.Package` list, `SYNO.Core.Package.Server` list)
  - update: `package_upgrade` (download from Synology, check, upgrade one installed package; the version must be strictly newer)
  - create / delete: none. It doesn't install, uninstall, upload `.spk` files, change Package Center settings or trust sources.
- [x] Its own controls are enforced at call time, in code: package ID regex, installed-only check, newer-only check, download-host check. `dry_run` defaults to true.
- [x] "Confirmation": `dry_run` is a model-passed flag, not a human. The human control is the client's `ask` rule, and the prompt shows `"dry_run": false`.
- [x] Account: DSM requires an administrator for every package call (error 105 for the non-admin read account, observed 2026-10-28). There's no lower role in DSM for Package Center.

## Risks that stay

- An administrator credential sits behind a tool surface we wrote, and `package_list` uses it with no approval click (only while write-gate has it on). A bug, or a later edit that adds a tool, widens it. Mitigation: `ask` on every tool that changes anything, any change to `server.py` means a new review (rule 3 in the README), and the agent never sees the password.
- A package upgrade can't be rolled back from DSM. Synology's package server and code signing (`check_codesign=true`) are the supply-chain trust here, the same as clicking Update in Package Center.

## Conditions

1. Register it with `allow` on `package_list` and `ask` on `package_upgrade` (owner's choice, 2026-10-28). Every tool added later is `ask` unless it's read-only and the owner approves it as `allow`. Register it at local scope for this repo, behind `write-gate run --name synology-extras` (owner's choice, 2026-10-29), so no session has its tools until the agent turns it on.
2. Use the existing NAS write account. Don't create a new admin.
3. Run from a checkout of merged `main`.
4. First live use runs in this order, with the owner watching: `package_list`, a dry run, then one real upgrade of a low-risk package. Record the result here as an addendum.

## Couldn't verify

- Live test of every DSM call (the parameters come from a community wrapper; see the tool's README)
- Behavior with 2FA accounts (unsupported by design)
