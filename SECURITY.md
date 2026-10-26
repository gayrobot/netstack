# Security policy

## Reporting a problem

Please **don't open a public issue** for a security problem. Use GitHub's private reporting instead: **Security → Report a vulnerability** on this repo.

Useful things to include: which script or doc, what an attacker could do, and steps to reproduce. You'll get an acknowledgement within a week. This is a personal project, so there's no SLA.

## In scope

- `scripts/`: the change-window gate, the denylist check, the NAS backup job
- `.githooks/` and `.claude/settings.json`
- Anything in the docs that would lead someone to set up an unsafe configuration

Examples: a way to open a change window without a valid restore point, a way past the commit hooks without `--no-verify`, the backup job leaking plaintext or credentials, a TLS pinning bypass.

## Out of scope

- Vulnerabilities in UniFi, Synology or the MCP servers themselves. Report those upstream. The [vetting notes](docs/vetting/) record what was reviewed.
- The known limits listed in the [README](README.md#known-limits) and [redaction.md](docs/redaction.md#limits).

## If you're using this repo

- Never commit anything from `private/`, and never put real hostnames or account names in tracked files.
- If you think you've pushed a secret, **rotate it first**, then clean up. Forks and clones keep whatever was pushed.
