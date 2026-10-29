# netstack

A home network run by an AI agent **under governance**: the agent reads freely, writes through separate connections where a person approves every call, needs a fresh off-box backup before risky changes, and logs every change in git.

It's built around a UniFi gateway and a Synology NAS, managed through MCP servers. The controls are plain shell scripts and git hooks, so they work with whichever agent you use: Claude Code, Codex, Cursor, Aider, or anything else that can read files and run commands.

## What you get

| Control | What it does | Where |
|---|---|---|
| **Rules file** | Read-only phase, no SSH to the gateway, no reading `.env`, log every change, verified vs. inferred | [`CLAUDE.md`](CLAUDE.md) (also read via [`AGENTS.md`](AGENTS.md)) |
| **Read/write split** | Read connections use read-only accounts and never prompt. Write connections use separate accounts, and the owner approves every call. Changes are tiered by risk | [`docs/change-control.md`](docs/change-control.md) |
| **Restore point gate** | Risky (tier 2) changes need a fresh, hash-verified, off-box gateway backup first | same script; [`docs/gateway-backups.md`](docs/gateway-backups.md) |
| **Automated backups** | The NAS pulls the gateway's auto-backup daily over a pinned TLS key, checks that it's a valid archive, encrypts it to an offline key, and stores it under immutable snapshots | [`scripts/nas/pull-gateway-backup.sh`](scripts/nas/pull-gateway-backup.sh), [`docs/gateway-backups-setup.md`](docs/gateway-backups-setup.md) |
| **Change log** | Every proposal with diff, rollback, verification and approval | [`docs/changes.md`](docs/changes.md) |
| **Public/private split** | Real hostnames and inventory live in a gitignored `private/`; hooks block commits that leak them, and they fail closed | [`scripts/check-public.sh`](scripts/check-public.sh), [`docs/redaction.md`](docs/redaction.md) |
| **Supply-chain vetting** | Every MCP server is reviewed and pinned before use | [`docs/vetting/`](docs/vetting/) |

## Quick start

### 0. Prerequisites

- A UniFi gateway (built on a UDM Pro; other UniFi OS consoles should work)
- An MCP server for it. This repo uses [sirkirby/unifi-mcp](https://github.com/sirkirby/unifi-mcp); read [the vetting notes](docs/vetting/unifi-mcp.md) first
- `git`, `python3`, `openssl` and `curl` on the machine running the agent
- Optional: a Synology NAS (DSM 7.2+, Btrfs) for automated backups

### 1. Clone and turn on the guardrails

```bash
git clone https://github.com/<you>/netstack && cd netstack
git config core.hooksPath .githooks
mkdir -p private
```

Create `private/denylist.txt` with one regex per line: your hostnames, account names, service names, anything you don't want published. The hooks refuse every commit until this file exists.

```bash
printf '# one extended regex per line, case-insensitive\nmy-gateway-hostname\nmy-nas-name\n' > private/denylist.txt
scripts/check-public.sh tree; echo "exit=$?"
```

### 2. Configure access (read-only)

- On the gateway, create a **local** account with a **View Only** Network role for the agent.
- Copy `.env.example` to `.env` and fill it in, or set the same values in your MCP client's config. Keep `CREATE`, `UPDATE` and `DELETE` set to `false`.
- Prefer a password *command* (for example a Keychain lookup) over a plaintext password.

### 3. Point your agent at the rules

| Agent | Reads |
|---|---|
| Claude Code | `CLAUDE.md` automatically; `.claude/settings.json` adds deny rules and a session-start warning |
| Codex, Cursor, Aider and others | `AGENTS.md`, which points to `CLAUDE.md`. Add your tool's equivalent of the deny rules if it has them |

Whatever the agent, the scripts and git hooks enforce the same controls.

### 4. First prompt

```
Read-only: inventory my network and container hosts, then draft docs/network.md
(VLANs, subnets, zones, DHCP, inbound exposure) and one page per host under docs/hosts/.
Put real hostnames and raw output in private/; public docs use role names.
Change no config. End every doc with a "Couldn't verify" list.
Flag anything exposed to the internet or bound to 0.0.0.0.
```

### 5. Making a change

```
small fix (tier 1):  agent proposes the call → you approve the prompt → agent logs it in docs/changes.md
risky (tier 2):      agent writes a docs/changes.md entry → you approve in chat
                     scripts/change-window.sh open "<exact entry title>"   # refuses without a fresh backup
                     agent applies through the write connection (you approve each call), verifies
                     scripts/change-window.sh close
```

`scripts/change-window.sh status` shows the current state and restore point at any time.

## Adapting to your setup

- **Different agent:** `change-window.sh` flips the plugin options in `~/.claude/settings.json`. For another client, change `set_options()` to edit that client's MCP config, or keep two MCP profiles (read-only and write) and switch between them.
- **No NAS:** download a backup by hand and run `scripts/change-window.sh backup <file.unf>`. The gate accepts that too.
- **Different hardware:** the change-window, change-log and redaction patterns don't depend on UniFi. Only the backup job does.
- **Two gateway accounts:** for a boundary the gateway enforces itself, not only the MCP's own flags, put a read-only and a write account in `private/change-window.conf` ([details](docs/change-control.md#two-accounts-recommended)).

## Repo layout

```
CLAUDE.md / AGENTS.md     rules for the agent
docs/
  network.md              VLANs, zones, exposure (role names)
  hosts/                  one page per host role
  changes.md              change log
  change-control.md       just-in-time write access
  change-windows.log      audit log of windows and backups
  gateway-backups*.md     backup design and owner checklist
  redaction.md            what stays out of the repo and how
  vetting/                MCP supply-chain reviews
scripts/
  change-window.sh        open / close / status / backup
  check-public.sh         denylist scan (staged, message, full history)
  nas/pull-gateway-backup.sh
.githooks/                pre-commit + commit-msg → check-public.sh
.github/workflows/        check-public in CI (denylist from a secret, output suppressed)
private/                  gitignored: real names, raw dumps, denylist, configs
```

## Status

- **Phase 1 (read-only inventory):** done for the gateway, VM host and app VM.
- **Phase 2 (backups and drift detection):** nightly off-box gateway backups run on the NAS, and a test decrypt has succeeded. Drift detection isn't started.
- **Phase 3 (approved writes):** live since 2026-10-28 through per-call-approved write connections; tier 2 changes also need a fresh restore point. The longer-term design (broker, self-expiring grants, risk tiers) is in [docs/jit-design.md](docs/jit-design.md).

## Known limits

- Git hooks run locally and can be skipped with `--no-verify`. The `check-public` CI job repeats the scan on every PR and push to `main`, but it runs after the branch is pushed, so it keeps a leak out of `main`, not off GitHub.
- The MCP's permission flags are enforced by the MCP's own code; only a separate gateway account makes the gateway enforce them.
- The backup gate proves a backup exists and matches its hash, not that it restores. Test a restore periodically.
- A denylist only catches the terms it lists.

## Contributing

Issues and PRs are welcome, especially adaptations for other agents and other gateway vendors. Run `scripts/check-public.sh tree` before opening a PR. For security problems, see [SECURITY.md](SECURITY.md).

## License

Public domain ([Unlicense](LICENSE)). Use it however you like; no attribution needed.
