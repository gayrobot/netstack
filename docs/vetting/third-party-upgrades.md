# Upgrading third-party MCPs

**Status:** proposed 2026-10-28. Nothing here is automated yet; see "Open decisions".

Third-party MCP servers run with the agent's device credentials, so a new release is a new piece of software with admin access. It gets the same treatment as a first install, scaled to how much changed. This page covers `mcp-server-synology` (connectors `synology`, `synology-write`), the UniFi plugin and `unifi-network-mcp` (the UniFi read connector, `unifi-write`), and anything vetted later.

## Principle

**Nothing upgrades on its own.** A version changes only through a PR that the owner merges, and the owner switches the running connector (tier 3). Until then, the pinned, vetted version keeps running even if a newer one exists.

## Gaps to close first

The principle isn't fully true today:

| Connector | Runs from | Problem |
|---|---|---|
| `synology`, `synology-write` | `uvx mcp-server-synology==1.8.0` | Dependencies re-resolve on each start (4 versions of the crypto library were seen across caches). A lock exists but isn't used yet |
| UniFi read (plugin) | plugin 1.1.5 starting `uvx unifi-network-mcp==0.38.3` | Same floating dependencies, and the permission gate lives in those libraries. The plugin may also update from its marketplace on its own |
| `unifi-write` | hash-locked environment | OK |

Fix: run every connector from a hash-locked environment built with `--require-hashes --no-deps --no-build`, and turn off auto-update for the UniFi plugin's marketplace. Both are tier 3 owner steps.

## When to look

- **Routine:** compare pinned and latest versions monthly. A read-only script could report this (PyPI JSON API and GitHub tags); it would change nothing and open nothing.
- **Security:** an advisory for the MCP or a dependency in its lock triggers the emergency path below.
- **Need:** a tool we want ships upstream. That's also the trigger to retire the matching `synology-extras` tool.
- Skipping a release is fine. Being behind on a vetted version is safer than running an unvetted one, unless there's a security fix.

## Upgrade path (one PR per MCP)

The agent prepares everything in steps 1 to 6. The owner reviews, merges and switches (steps 7 to 8).

1. **Provenance.** The release has a Trusted Publishing attestation from the expected repo and workflow. The wheel's files match the release tag. Any change in publisher, workflow or maintainers is a stop-and-ask.
2. **Code diff between the two tags,** read for:
   - tools added, removed or renamed, and any change in what an existing tool does
   - permission declarations and annotations (for UniFi: category, create/update/delete; a tool moving from read to write is a finding)
   - outbound hosts, subprocess use, startup code, config files it reads
   - credential handling (login, logging, TLS)
3. **Tool inventory diff.** List the tools from the code for both versions and record the delta in the addendum. Every new tool needs an explicit decision before go-live: **deny on read connectors, `ask` on write connectors, until reviewed.** That's the default even for tools that look read-only.
4. **Overlap with `synology-extras`.** If upstream now does something a `synology-extras` tool does, retire ours in the same PR, or in a follow-up PR that lands before the switch. Move the permission rule to the upstream tool. There's one exception: if the upstream tool is broader (for example, it can also install), keep ours and deny theirs.
5. **New lock.** `locks/<package>-<version>.txt` from the `.in` file, plus a tamper test (alter one hash, expect `Hash mismatch`). Keep the old lock for rollback.
6. **Vetting addendum,** dated, in the existing review: what changed, the findings, the verdict, and the permission rule changes. Add a `changes.md` entry (tier 3) and update the version in the vetting README table.
7. **Switch (owner).** Build the new locked environment next to the old one, point the launcher at it, update the permission rules from step 3, then start a new session.
8. **Verify.**
   - Run the read smoke test from the 1Password entry in `changes.md`: the same tools should work, and the same ones should fail with 105 or 403.
   - Confirm a write tool still prompts.
   - Confirm a new tool behaves as decided in step 3.
   - Record the results in the `changes.md` entry.

**Rollback:** point the launcher back at the old environment and revert the permission rules. Delete the old environment only after a week without problems.

## Emergency path

- **Security fix in a release:** steps 1, 2 (only the fix and anything else in that release), 5 and 7 the same day. Do the full addendum afterwards.
- **Suspected compromise** (unexpected publisher, yanked release, an advisory against the package itself): the owner disables the connector first, then we investigate. Disabling loses nothing that matters: the read tools are conveniences, and writes can be done by hand.

## If upstream stalls or a release fails vetting

Stay on the last vetted version, which keeps working until DSM or UniFi changes break it. If that happens, our options are forking (we'd own the full review), or moving the few tools we actually use into a first-party server like `synology-extras`. The current smoke test shows how few tools we use.

## Open decisions

- How often to check, and whether a scheduled read-only check runs it or a person does
- Whether to build the tool-inventory diff as a script (`scripts/mcp-tool-diff`), so step 3 isn't done by eye
- Whether new upstream tools stay denied by default even on write connectors (proposed: yes, until reviewed)

## Couldn't verify

- Whether the UniFi plugin's marketplace auto-updates in this client, and whether it's currently on
- How the `synology` read connector's launcher is pinned (the `synology-write` one uses `uvx`; it's assumed to be the same)
