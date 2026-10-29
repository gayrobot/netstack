# Redaction: what stays out of this repo, and how that's enforced

This repo documents how the network is governed, not a map of the house. Specifics live in a gitignored `private/` folder, and the public docs use role names.

## Role names

| Role | Meaning |
|---|---|
| gateway | UniFi Dream Machine Pro |
| VM host | the always-on Mac Pro running UTM |
| app VM | the Ubuntu VM that runs the containers |
| app containers | the services in the app VM |
| VPN gateway container | the container that tunnels other containers' egress |
| NAS | network storage |
| admin laptop | where Claude Code runs |

## Controls

1. **`private/` is gitignored.** Real host docs, raw inventory output and the denylist live there.
2. **The denylist is private too.** A public list of banned words would itself leak them, so `private/denylist.txt` holds the private terms and `scripts/check-public.sh` adds generic patterns (MAC addresses, globally routable IPv6).
3. **Hooks fail closed.** `.githooks/pre-commit` scans staged contents and paths, and `.githooks/commit-msg` scans the message. If the denylist is missing, the commit is refused. Turn them on with `git config core.hooksPath .githooks`.
4. **History check before every push.** `scripts/check-public.sh tree` scans every commit, path, message and author field.

## Limits

- Hooks are local and can be skipped with `--no-verify`. CLAUDE.md forbids that. `.github/workflows/check-public.yml` repeats the full-history scan on every PR and push to `main`, with the denylist from the `DENYLIST` secret. It discards the scan output, because logs on a public repo are public. It runs after a branch is pushed, so it stops a leak reaching `main`, not reaching GitHub; the local hooks are still the first line.
- Whether the CI job blocks a merge depends on branch protection requiring it, which the owner sets in GitHub.
- A term not on the list isn't caught. New hostnames and services need to be added when they appear.
- Nothing can un-publish a pushed commit. If something leaks, rotate what can be rotated and treat the rest as public.
