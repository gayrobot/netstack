# Vetting: atom2ueki/mcp-server-synology (Synology NAS MCP)

**Reviewed:** 2026-10-26, read-only, using the [checklist](README.md)
**Verdict:** **Not OK as currently configured.** The code and its provenance are reasonable. The problem is authority: 43 write tools with no gating of any kind, running as a NAS **administrator**, behind an agent client that doesn't prompt per call. OK only once the conditions under "Verdict" are met.

This one was connected on 2026-10-16, before any review, so this review is retroactive.

## Identity and provenance

| | |
|---|---|
| Upstream | `atom2ueki/mcp-server-synology` on GitHub, MIT license, created May 2025, 237 stars, 47 forks |
| Maintainers | one primary author (251 commits); 6 others with 2–8 commits each; Dependabot |
| PyPI | `mcp-server-synology`, 3 releases (first 2026-09-22); this install pins `==1.8.0` (2026-09-29) |
| Security history | no published advisories; no open issues. Closed issues show security work (stored-password alternatives, hardened deployment defaults, Windows ACL checks) and one correctness bug where group writes reported success without being applied |
| How it runs here | user-level MCP server; a local wrapper script reads the password from the macOS Keychain and runs `uvx mcp-server-synology==1.8.0` |
| Provenance | **Trusted Publishing** attestation: `atom2ueki/mcp-server-synology` / `pypi-publish.yml`, for both wheel and sdist |
| Artifact vs. source | the wheel matches PyPI's sha256; all **21/21 files are identical** to tag `1.8.0` |
| Installed vs. artifact | 30 installed files match the wheel's `RECORD` |

## Dependencies

- Declared with ranges only (`requests`, `pycryptodome`, `websockets>=17.0.1`, `filelock>=3.12`, `mcp>=2.2.0`, `python-dotenv`).
- **They float in practice.** Across 9 cached environments for the same `==1.8.0` pin there are 4 versions of `pycryptodome` (its crypto library), 4 of `filelock`, `httpx2` and `certifi`, and 3 of `starlette`, among others.
- **Hygiene problem:** the wheel installs generic top-level modules (`auth`, `config`, `utils`, `health`, `container`), which can collide with or be shadowed by other packages in the same environment.
- **Hash lock:** [`locks/mcp-server-synology-1.8.0.txt`](locks/mcp-server-synology-1.8.0.txt) pins 39 packages. Tested 2026-10-26: installs cleanly with `--require-hashes --no-deps --no-build`; fails with `Hash mismatch` when the package's hashes are altered. Only the top-level package was reviewed.

## Behavior

- **Outbound hosts:** only the configured NAS, plus an optional remote bridge to `wss://api.xiaozhi.me/mcp/` (a third-party voice-assistant service). The bridge is **off by default** and stays off unless a `settings.json` enables it. None exists here. While off, it's an unused remote-control channel; if enabled, a third party could drive every tool.
- **Process execution:** no `subprocess`, `eval`, `exec` or `pickle` outside tests.
- **Login:** a `POST` to `auth.cgi`, so the password isn't in a query string. Redirects are explicitly refused, so a forged redirect can't replay credentials elsewhere. No logging of passwords, SIDs or OTPs found.
- **Credentials:** the password reaches the server as an environment variable from the Keychain wrapper. That's good. The `synology_login` tool takes a password as a tool argument, which would put it in the agent transcript; with auto-login on, it isn't needed.
- **Target host:** a caller-supplied `base_url` isn't logged in to automatically. Only configured NAS entries are, so a call aimed at another host gets no session and no credentials. (I read the resolver, not every handler.)
- **⚠ TLS verification is off** (`VERIFY_SSL=false`, the default). Anyone who can intercept LAN traffic to the NAS can present a fake certificate and capture the **admin password** at login.
- **⚠ It loads `./.env` from the working directory** (legacy support, `config.py`). The working directory is wherever the agent client runs, so in this project that's the gateway `.env` the rules say no agent may read. It doesn't override variables already set, but it reads the file.

## Authority

- **94 tools: 49 read, 43 write, plus login/logout.** The writes include file create/move/rename/copy/**delete**, NAS **user creation, deletion and permission changes, and group membership** (including `administrators`), share creation, NFS enable and export permissions, iSCSI LUN/target create/delete/map, container start/stop/delete, compose project create/build/start (a container is effectively **root on the NAS**), image pull and prune, and download-task creation.
- **No permission controls of any kind:** no read-only mode, no per-tool switches, no MCP read-only or destructive annotations. Every tool is always live.
- **The account is an administrator.** It's in the NAS `administrators` group, so every write tool works, including granting itself or anyone else anything.
- **No human in the loop.** With the agent client in an auto-approve mode and no `ask`/`deny` rules for these tools, nothing stops a write except the model's judgement. A prompt injection in any file name or log line the agent reads could become `create_user` + `add_user_to_group administrators`.
- **Interaction with the backup design:** immutable snapshots survive this account (that's their job), but the account can disable the snapshot schedule or read the backup share while it's unlocked. That's why backups are also encrypted to an offline key.

## Verdict and conditions

**Not OK as configured.** OK with all of these:

1. **Deny the write tools in the agent client** (all 43, plus `synology_login`), and deny agent writes to the server's config directory so the remote bridge can't be enabled. This is the fastest real control.
2. **Run from the hash lock, from a fixed working directory**, so no project `.env` gets loaded: the wrapper does `cd` into its own directory before starting.
3. **Turn TLS verification on** with the NAS certificate as the trusted CA, or move to a hostname with a proper certificate.
4. **Stop using an administrator for everyday reads.** Either a non-admin account for daily reads, with admin only inside a change window, or a filtering MCP proxy that exposes an allowlist of read tools and logs every call. The proxy would also be a reusable artifact for other MCP servers.

## Not yet done

- Whether File Station `delete` through the API bypasses the recycle bin
- Which read tools still work for a non-admin account (decides condition 4)
- Review of `pypi-publish.yml` and recent commit history
- Handler-by-handler check of `base_url` use
