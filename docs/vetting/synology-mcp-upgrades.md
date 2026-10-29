# Upgrading the third-party Synology MCP

**Status:** proposed 2026-10-28.

`mcp-server-synology` (connectors `synology` and `synology-write`) runs with the agent's NAS credentials, one of them an administrator. A new release is new software with admin access, so it gets the same treatment as a first install, scaled to how much changed.

## Principle

**Nothing upgrades on its own.** The version changes only through a PR the owner merges, and the owner switches the running connectors (tier 3). Until then, the pinned, vetted version keeps running even if a newer one exists.

Gap to close first: both connectors start with `uvx mcp-server-synology==1.8.0`, which re-resolves dependencies on each start (4 versions of the crypto library were seen across caches). The hash lock in [`locks/`](locks/) exists but isn't used yet. Running both connectors from a locked environment is a tier 3 owner step, and it's what makes "pinned" true.

## When to look

- **Routine:** compare the pinned version with the latest release on PyPI monthly.
- **Security:** an advisory for the package or a dependency in its lock triggers the emergency path.
- **Need:** a tool we want ships upstream.
- Skipping a release is fine. A vetted old version is safer than an unvetted new one, unless the new one fixes a security issue.

## Upgrade path (one PR)

The agent prepares steps 1 to 6. The owner reviews, merges and switches (steps 7 to 8).

1. **Provenance.** The release has a Trusted Publishing attestation from `atom2ueki/mcp-server-synology`, and the wheel's files match the release tag. A change in publisher, workflow or maintainers means stop and ask.
2. **Code diff between the two tags.** Look for tools added, removed or changed; outbound hosts (including the remote bridge); process execution; config files it reads (it already loads `./.env`); and login, logging and TLS handling.
3. **New tools start blocked.** List the tools in both versions. Every new tool is denied on `synology`, and denied or `ask` on `synology-write`, until the addendum decides otherwise.
4. **Overlap with `synology-extras`** (below). Settle every overlapping tool in this PR.
5. **New lock** `locks/mcp-server-synology-<version>.txt`, plus a tamper test (alter one hash, expect `Hash mismatch`). Update the pin in `locks/mcp-server-synology.in`, and keep the old lock for rollback.
6. **Vetting addendum,** dated, in [synology-mcp.md](synology-mcp.md): what changed, the findings, the verdict and the permission rule changes. Also update the version in the vetting README table and add a `changes.md` entry (tier 3).
7. **Switch (owner).** Build the new locked environment next to the old one, point both launchers at it, apply the permission rules from step 3, then start a new session.
8. **Verify.** Rerun the NAS smoke test from the 1Password entry in `changes.md`: the same tools should work, and the same ones should fail with 105. Confirm a write tool still prompts. Record the results in the `changes.md` entry.

**Rollback:** point the launchers back at the old environment and revert the permission rules. Delete the old environment after a week without problems.

## Overlap with synology-extras

`synology-extras` holds only what this MCP can't do ([build-or-adopt.md](build-or-adopt.md), step 4). When a release adds something equivalent, there's **one path per action, and it's the safer one.** Compare the two tools on:

| Question | Why |
|---|---|
| Can theirs do more (install, uninstall, upload a `.spk`, take a URL or host)? | Ours deliberately can't |
| What guards does it have (dry run, download-host check, TLS)? | TLS verification was off by default in 1.8.0 |
| What account does it need? | DSM requires admin for most of what `synology-extras` does, so theirs can only work on `synology-write` |

Then one of these:

- **Theirs is as narrow and safe as ours:** retire ours (delete the tool and its tests, and add an addendum to [synology-extras.md](synology-extras.md)), then move the permission rule to theirs. If `synology-extras` has no tools left, the owner removes the connector.
- **Theirs is broader:** keep ours and deny theirs on both connectors, permanently.
- **Mixed:** settle it per tool, the same way.

Note: if a read-only tool moves to theirs, it runs on `synology-write`, where everything is `ask`. Keeping it unprompted needs an `allow` rule for that one tool, which is the owner's call at the time.

**Tripwire.** Each `synology-extras` tool records the upstream version it was last checked against (`CHECKED_AGAINST` in `server.py`). A test fails if that doesn't match the pin in `locks/mcp-server-synology.in`, so an upgrade PR can't pass until every tool has been rechecked and its version bumped. The test forces the question; the PR author answers it, and the owner approves.

## Emergency path

- **Security fix in a release:** steps 1, 2 (the fix and anything else in that release), 4, 5 and 7 the same day. Do the full addendum afterwards.
- **Suspected compromise** (unexpected publisher, a yanked release, an advisory against the package itself): the owner disables both connectors first, then we investigate.

## If upstream stalls or a release fails vetting

Stay on the last vetted version. If DSM changes break it, our options are a fork (we'd own the full review), or moving the few tools we use into `synology-extras`.

## Couldn't verify

- How the `synology` read connector's launcher is pinned (the `synology-write` launcher uses `uvx`; the read one is assumed to be the same)
