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

## 2026-10-31: Accept the NAS port forwards as a known risk (R1)
- Status: proposed; accepted when the owner merges the PR
- Target: docs only. `strategy.md` (T2 re-rated, new "Accepted risks" register), `network.md` (inbound section, finding 1), `backlog.md` (A1 reshaped). No device changes
- Why: the owner identified what the two forwards serve: the inbound peer port of the NAS's built-in peer-to-peer download client. That narrows T2 from "DSM on the internet" to "one closed-source listener on the internet", so the docs were overstating the likelihood and understating why it still matters (the listener runs on the NAS, on the flat LAN). The owner wants inbound peers to keep working, so the forwards stay for now and the exposure is written down as a risk with an exit
- Check first: done. The read account can't see the client's settings (DSM error 105) and Container Manager isn't installed on the NAS, so the client is the built-in one, as the owner said. Which port it listens on and whether the forwards hit only that port are still the owner's to confirm in DSM (network.md, "Couldn't verify")
- Alternatives considered: disable both forwards (zero inbound exposure, peers can't connect in; the owner declined); a proxy in front of the ports (moves the address, not the code; rejected); restrict the forwards' source (meaningless for peer traffic, which comes from anywhere; rejected); the move to the app VM behind the VPN gateway container with provider port forwarding (the exit for R1, now the shape of A1)
- Diff: see the PR
- Rollback: revert the PR; nothing on any device changed
- Approved by / when: owner, in chat, 2026-10-31 ("mark what I am accepting to be a risk"); the merge is the acceptance

## 2026-10-29: Put synology-extras behind write-gate, at repo scope
- Status: **proposed** (tier 3: a new connection and its credential; the owner registers it)
- Target: agent client MCP config and user settings (one new connection, two permission rules)
- Why: the registration in the 2026-10-28 synology-extras entry used user scope and started the server directly. Since then the NAS connections moved to local scope for this repo, and the write connections run behind [write-gate](../tools/write-gate/README.md). synology-extras holds the NAS admin login, so it follows the write connections (owner's choice in chat, 2026-10-29: "Behind write-gate")
- Diff:
  1. Register `synology-extras` at local scope in this repo and its worktrees, with its command wrapped as `write-gate run --name synology-extras -- /usr/bin/python3 -I <repo>/tools/synology-extras/server.py` ([mcp.example.json](../tools/synology-extras/mcp.example.json))
  2. Permission rules unchanged: `allow` on `mcp__synology-extras__package_list`, `ask` on `mcp__synology-extras__package_upgrade`, none for the whole server
  3. Use: when a package check or upgrade is next, the agent says so and runs `write-gate on synology-extras`. Starting the server reads no password; each tool call runs `op read`, so the 1Password prompt comes with the call
  4. Docs: [change-control.md](change-control.md) (also puts the synology-extras row back inside the connection table, which a merge had pushed below it), the synology-extras README and vetting conditions, and EX-1's scope in [exceptions.md](exceptions.md)
- Rollback: `claude mcp remove synology-extras -s local` in each checkout, and remove the two permission rules
- Verify: a new session here shows `synology-extras` connected with no tools and no prompt. `write-gate on synology-extras`, then `package_list` brings a 1Password prompt and no click; `package_upgrade` with its default dry run needs a click
- Approved by / when: placement behind write-gate, owner, in chat, 2026-10-29. Registration pending (owner)
- Couldn't verify: how often 1Password asks again when the password is read on each call; that the server works behind the gate (the gate is tested live only with `unifi-write`)

## 2026-10-29: No 1Password prompts for read connections; write connections only when needed
- Status: **proposed** (tier 3: agent credentials and the write connections themselves; the owner applies). Steps 0 and 3 were applied by the agent on 2026-10-29 at the owner's request (logged here per rule 4)
- Target: agent client MCP config and user settings (UniFi plugin options, the NAS launcher); 1Password (a new vault and a service account); macOS Keychain (one item)
- Why: every MCP connection runs `op read` when it starts, so each new session triggers up to four 1Password approvals. Two of them are for **read-only** accounts, which shouldn't need the owner at all. The UniFi read plugin is also enabled for every project, so it prompts in unrelated work too. The 2026-10-28 entry noted this ("each MCP start is its own `op` process"). [change-control.md](change-control.md) lists the read connections as "Prompts: none", which is only true of tool calls, not of the launch
- Constraint: 1Password stays the single source of truth. The Keychain copies were dropped on 2026-10-28 because they went stale, so this proposal doesn't bring password copies back
- Diff:
  0. **Applied 2026-10-29 (agent, owner asked "make it stop"):** `synology`, `synology-write` and `unifi-write` moved from user scope to local scope for this repo and its three existing worktrees. Other projects no longer start them. Backup of the client config taken first. New worktrees do inherit them (seen 2026-10-29, see step 1)
  1. **Read connections stop prompting.** The owner creates a 1Password vault holding only the gateway and NAS read-only items, and a service account with **read access to that vault only**. Its token goes into one login Keychain item. A small wrapper (`op-ro-read <ref>`: loads the token from the Keychain into `OP_SERVICE_ACCOUNT_TOKEN`, then runs `op read`) replaces plain `op read` for the two read connections only: the UniFi plugin's `password_command`, and the NAS read launcher (the launcher is shared with the NAS write connection today, so it needs a switch or a second launcher). Passwords still live only in 1Password; what's cached locally is a revocable token that can only read the read-only items
     - **Done 2026-10-29 (owner, in their own terminal):** read-only vault created; the two read-only logins moved into it (the write logins stay where they were); service account created with `read_items` on that vault only and a 90-day expiry; its token saved straight into a login Keychain item without being displayed. Names and IDs are in `private/`
     - **Checked 2026-10-29 (agent):** the Keychain item exists; through the token, the read-only vault is the only one visible and holds exactly the two logins; both write logins are refused
     - **Applied 2026-10-29 by the owner** with a private script: the wrapper is [tools/op-ro-read](../tools/op-ro-read/README.md) (tested against both read items, lengths only, and refused on a write item). The script installed it, pointed the UniFi plugin's `password_command` at it, added a token mode to the NAS launcher (on only when the read connection sets `SYNOLOGY_RO_TOKEN_SERVICE`, so the NAS write connection keeps `op read` and its prompt), and repointed the NAS read connection, backing up each file first
     - **Checked 2026-10-29 (agent), static:** the installed wrapper matches the repo copy; the gateway read `password_command` and the NAS read path both return a value when run as configured, the NAS one in a minimal environment; the NAS read connection is repointed in the repo and all three worktrees; the NAS write connection has no token setting
     - **Checked 2026-10-29 (agent, from the client's MCP logs of a new session in a new worktree):** both read connections connected with no prompt (gateway 2.6 s, NAS 3.7 s). The owner got one 1Password prompt, from the write connections: both waited on it and timed out after 30 s. That's what step 2 removes. The new worktree also inherited the repo's local-scope servers, which answers the open question in step 0. **Not yet run:** the read smoke test through the new connections
  2. **Write connections off until needed.** Applied 2026-10-29 by the owner with a private script (client config backed up first); the agent checked the installed gate matches the repo and both write connections are wrapped in the repo and all three worktrees. Each write connection's MCP entry runs through [write-gate](../tools/write-gate/README.md). While writes are off it's a stand-in with no tools, so starting a session reads no write password and shows no 1Password prompt
     - **The agent turns writes on, not the owner** (owner, 2026-10-29: "you call that tool for me when it is time to write ... I don't want two steps to authenticate"). When a write is next, the agent tells the owner a 1Password prompt is coming and runs `write-gate on <connection>`. The gate starts the real server in place, the owner approves the one prompt, and the tools appear without a reconnect. The per-call `ask` click stays: it approves the specific change (rule 5), it isn't a sign-in. `CLAUDE.md` rule 5 says this
     - **One prompt:** windows are per connection and per session. `on` records the session that ran it, so other open sessions stay off. Default 60 minutes, max 240; afterwards the real server stops once no call is in flight. A failed or ignored prompt isn't retried until `on` is run again
     - **Not a security boundary:** the agent can turn a window on, but that only lets the real server ask 1Password. The owner's approval of that prompt and of each call are still the controls. Closer to [jit-design.md](jit-design.md)'s "no standing write access" than having the write accounts logged in for every session
     - **Not the client's own disable:** the first draft used the client's per-project MCP disable, but reports say it fails in the desktop app, isn't inherited by worktrees and hasn't always applied at startup. A connection that *fails* instead gets skipped for 15 minutes, which is why the gate serves a stand-in rather than exiting
     - **Checked 2026-10-29 (agent):** 11 offline tests pass (also in CI), with a fake server behind the gate: stand-in while off, live swap with a `tools/list_changed` and a working call, removal when off, a window for another session ignored, a failed start not retried. Against the real client, a gated server shows **Connected** while off. A dry run of the owner's config edit wraps only the two write connections, each with its own name, and is idempotent
     - **Live test 2026-10-29 (owner, in a new session; no write made):** the gateway write connection connected as the stand-in in 59 ms at session start, with no prompt. `write-gate on` for it, then one 1Password approval; 36 s later the real server was up and the client logged "Received tools/list_changed notification, refreshing tools". `write-gate off` 10 s later: a second refresh, status back to `off`. The NAS write connection stayed off throughout (one prompt, not two). Cross-check, the controller's audit log (owner's screenshot): one write-account login at the same second the real server came up, none at session start. Earlier that day, before the gate, there's a write-account login at every session start, and one about 5 minutes after a session whose write connection had timed out waiting on 1Password (likely a late approval of that prompt; not confirmed)
     - **Not verified:** that the write tools were then listed in that session's tool set (the client log shows the refresh, not its result)
     - The owner applies it with a private script (backs up the client config first)
  3. **UniFi read plugin scoped to this repo. Applied 2026-10-29 (agent, owner: "Do step 3"):** `unifi-network@unifi-plugins` set to `false` in the user's `enabledPlugins` (backup taken first) and `true` in this repo's `.claude/settings.json` (this PR). Its options (`pluginConfigs`) stay in user settings. Until this PR merges, only this branch's checkout has the project setting, so the plugin won't load in the main checkout
  4. **Docs, once applied:** [change-control.md](change-control.md)'s connection table (prompts at launch vs per call, write connections off by default) and [jit-design.md](jit-design.md)'s "Where we are"
  5. **Automated token rotation** (owner, 2026-10-29: "I want rotation automated"). The service account from step 1 is created with `--expires-in 90d`, and a launchd job rotates it before then:
     - Runs daily as the owner, outside the agent. The owner installs it (tier 3); the agent never calls it. It does nothing until the token is within 14 days of expiry, read from a local non-secret file holding the expiry date
     - Then: `op service-account create <name>-<date> --vault <read-only vault>:read_items --expires-in 90d --raw`, written straight into the Keychain item (never printed or logged). It checks the new token with one `op read` of a read-only item, and only then updates the expiry file. On any failure it keeps the current token and tries again the next day
     - **One owner approval per rotation.** `op service-account create` needs the owner's 1Password sign-in, so the desktop app asks for Touch ID. Rotating with no person at all would mean keeping a credential for the owner's whole 1Password account on disk, which is far more powerful than the read-only token it rotates. Rejected
     - If the prompt is missed, the next day's run asks again. A macOS notification reports success or failure, and the `SessionStart` hook warns within 14 days of expiry as a backstop. If the token does expire, the read connections fail to start (fail closed) and nothing falls back to a broader account
     - No overlap problem: the old token keeps working until its own expiry. The CLI can't list or revoke service accounts, so a leaked token is revoked in the 1Password web app, and expired accounts are deleted there now and then
     - Built first-party under `tools/` with a [build-or-adopt](vetting/build-or-adopt.md) pass first: landed on step 4, no third-party tool found (search 2026-10-29; the CLI has no rotate, list or delete for service accounts). Record and checklist: [vetting/op-rotate.md](vetting/op-rotate.md)
     - **Built 2026-10-29 (agent, owner: "lets build it now"):** [tools/op-rotate](../tools/op-rotate/README.md), 11 offline tests (also in CI) with fake `op`, `security` and notifier: not due does nothing; due rotates with the exact `create` argv; a denied prompt, a bad token, a token that can't read, or a failed Keychain write each keep the current token; the token appears in no argv, log, state or notification; a config value can't inject `security` options. A `SessionStart` hook runs `op-rotate status --hook`, silent unless within 14 days, failed or expired, and silent where it isn't installed
     - **To apply (owner):** a private install script writes the config, seeds the current service account and its expiry, installs the launchd agent, and does one test rotation through launchd (one 1Password approval). That test answers the main open question: whether 1Password prompts for `op` started by launchd
     - **Applied 2026-10-29 by the owner** with the private script; the agent checked the result. The test rotation ran from launchd (not a terminal): 1Password prompted, the owner approved, and the new service account was created, checked and saved 6 s after the run started. Through the new token a read-only item reads (length only). The launchd job is loaded and exited 0; the installed script matches the repo. The previous service account stays valid until its own expiry and can be deleted in the web app. Next rotation from about 2027-01-13
- Risk: the Keychain item is readable by any process the owner runs, the agent's shell included, so the agent *could* recover the read-only passwords. That's the same access the read connections already have, and rule 3 forbids it. Limits: the token can only read one vault holding only read-only items, and the owner can revoke it in 1Password at any time
- Rollback: 0, move the three servers back to user scope (or restore the `~/.claude.json.bak-20261029-*` backup). 1, point both read connections back at plain `op read`, then delete the service account and the Keychain item. 2, re-enable the write connections. 3, re-enable the plugin in user settings
- Verify: a new session in another project starts none of these connections and shows no prompt. A new session here starts both read connections with no prompt and passes the 2026-10-28 read smoke test. Both write connections are off. Enabling one in `/mcp` brings up one 1Password prompt, and a tier-1 call still needs its own approval
- Approved by / when: step 0, owner, in chat, 2026-10-29 ("make it stop please"). Step 3, owner, in chat, 2026-10-29 ("Do step 3"). Steps 4 and 5 pending; steps 1 and 2 applied by the owner (owner asked for this proposal in chat, 2026-10-29: "Write the proposal"; confirmed in chat that the plan supports service accounts, "I can use a service account here")
- Couldn't verify: that a service account can't create another service account (expected from the docs, which require a user account with permission; this is why step 5 needs an owner approval); whether 1Password limits how many service accounts an account can have, expired ones included; whether `op` with a service-account token avoids the desktop-app prompt in every case (expected: yes, it doesn't use the app integration); whether 1Password logs service-account reads somewhere the owner can audit

## 2026-10-29: Exceptions cascade and build-or-adopt rubric
- Status: **proposed** (tier 3: these are the project's own controls). Drafted after the owner's review comments on PR 5: rules shouldn't be so rigid that exceptions pile up, exception detail shouldn't cost context in `CLAUDE.md`, and the rubrics need periodic review
- Target: [exceptions.md](exceptions.md), [vetting/build-or-adopt.md](vetting/build-or-adopt.md), `CLAUDE.md`
- Why: the first exception (`synology-extras` reads on an admin login) was written straight into rule 5, and the reasoning for building `synology-extras` wasn't recorded anywhere a later session could find. The third-party vs homegrown rubric the owner remembered wasn't written down
- Diff:
  1. `exceptions.md`: a cascade (is it really an exception, do it within the rule, narrow it, change the rule, a registered exception with compensating controls and a review-by date, or don't). The register starts with EX-1, `synology-extras` read-only tools without a prompt
  2. `build-or-adopt.md`: a cascade (use what's connected, widen a permission, adopt third-party, build first-party gaps only, or keep it manual), with Package Center as the worked example. Its step 3 (search for an existing third-party DSM package MCP) was not done and is flagged
  3. `CLAUDE.md`: the `synology-extras` sentence in rule 5, the old rule 10 and the layout detail are removed. The new rule 10 is one line pointing to both rubrics
  4. Both rubrics and every exception have review-by dates (first: 2027-01-29). A reminder in the `SessionStart` hook is proposed, not built
- Rollback: revert the docs and `CLAUDE.md`
- Approved by / when: direction, owner, in PR 5 review and in chat, 2026-10-29 ("Draft one fresh"); content pending review

## 2026-10-28: Upgrade process for the Synology MCP, and overlap with synology-extras
- Status: **proposed** (tier 3: it changes how the agent's controls are maintained). The overlap rule itself was decided by the owner in chat
- Target: process; [vetting/synology-mcp-upgrades.md](vetting/synology-mcp-upgrades.md), `tools/synology-extras/test_server.py`
- Why: nothing defined what happens when `mcp-server-synology` releases a new version, or what happens when it gains a tool `synology-extras` already has. A future session won't remember this conversation, so it's written down and enforced by a test
- Diff:
  1. Upgrade path: provenance, tag diff, new tools blocked until reviewed, overlap check, new lock, addendum, owner switch, smoke test, rollback; plus an emergency path
  2. Overlap rule: one path per action, keep the safer one. Retire ours if theirs is as narrow and safe, deny theirs if it's broader, decide per tool if mixed
  3. Tripwire: each `synology-extras` tool records the upstream version it was checked against; a test fails if that doesn't match the pin in `locks/mcp-server-synology.in`
  4. Gap noted, not changed: both Synology connectors still start under `uvx` with floating dependencies
- Rollback: revert the doc, the rule and the test
- Approved by / when: overlap rule, owner, in chat, 2026-10-28 ("Make the PR"); the process as a whole pending review of this PR

## 2026-10-28: First-party synology-extras MCP (package list and upgrade)
- Status: **proposed** (tier 3: it adds an agent control, so the owner registers it). Code, offline tests and vetting are in this PR; no live DSM call has been made yet
- Target: agent client MCP config and permission rules; the NAS (Package Center, through the existing NAS write account)
- Why: vendor security advisories (Synology-SA-26:14 was the trigger) are fixed by package updates. The vetted Synology MCP has no package tools, and SSH would give the agent a full shell on the NAS
- Diff:
  1. New `tools/synology-extras/` server, starting with two tools, `package_list` and `package_upgrade` (upgrade only, Synology's servers only, dry run by default). Review: [vetting/synology-extras.md](vetting/synology-extras.md)
  2. Owner registers it from `tools/synology-extras/mcp.example.json`, using the NAS write account's 1Password item. No new account
  3. **Gating per tool, one connector** (owner, 2026-10-28). DSM needs an administrator even to list packages, so `package_list` runs on the admin login with an `allow` rule (no prompt), and `package_upgrade` has an `ask` rule. Recorded as exception EX-1 in [exceptions.md](exceptions.md): the password never reaches the agent, and the only way to widen the tool set is a reviewed PR
  4. **Scope:** `synology-extras` holds only what the third-party Synology MCP can't do. Overlaps are retired when upstream catches up (see [vetting/synology-mcp-upgrades.md](vetting/synology-mcp-upgrades.md))
  5. Tier for `package_upgrade`, owner's choice: proposed **tier 1** (one package, from Synology, approved per call), logged here after each use with role names only; installed package names and versions go in `private/`
- Rollback: remove the MCP entry and its permission rules. A package upgrade itself can't be rolled back from DSM
- Verify: `package_list` returns the installed packages; a dry run reports the right from/to versions; one upgrade of a low-risk package, checked in Package Center
- Approved by / when: design and gating, owner, in chat, 2026-10-28 ("I would like to do synology-extras", ungated list). Registration still pending (tier 3, owner)

## 2026-10-28: Apply vendor security updates for Synology-SA-26:14
- Status: **closed 2026-10-28** after the owner checked Package Center. Details in `private/changes.md`
- Target: the NAS
- Why: [Synology-SA-26:14](https://www.synology.com/en-au/security/advisory/Synology_SA_26_14), critical remote code execution in some DSM packages
- Diff: see `private/changes.md`
- Approved by / when: n/a

## 2026-10-28: Governance proof: denied write and read-connection refusal
- Status: **tested 2026-10-28; no change made.** End state matches the start state (UTC times below fall on 2026-10-29)
- Target: the same in-wall access point as the proof of concept below; controller device name only
- Why: the proof of concept showed the approved path working. This tests that the controls actually stop a write: a write the owner denies, and a write attempted through the read connection
- Diff:
  1. Before (read connection, 01:59 UTC): name `<model default>`, online
  2. Deny test (write connection, `unifi_execute` → `unifi_rename_device`, new name `deny-test`, `confirm: true`). **Approval prompt appeared** showing the tool, device and new name (owner's screenshot, 01:59:43 UTC). Owner clicked **Deny**; the client rejected the call and nothing was sent
  3. Verify (read connection, 02:00 UTC): name still `<model default>`, online
  4. Negative test (read connection, same tool, new name `read-test`): refused by the read connection's own policy before any controller call ("Update is disabled by policy for devices"). No prompt, since the read connection has none
  5. Verify (read connection, 02:00 UTC): name still `<model default>`, online
- Findings:
  - Both controls held. Deny ends the agent's turn, so the owner has to tell it to carry on afterwards
  - The read-connection refusal came from the MCP's policy layer only. Whether the controller would also refuse the view-only account (a 403) wasn't tested, because that needs the read connection's policy turned on (tier 3)
  - Independent audit: the controller's **Admin Activity** log (owner's screenshot from the UI) shows exactly two entries, both attributed to the write account: the two proof-of-concept renames at 01:25:57 and 01:27:37 UTC. There is **no entry** for the denied call or the read-connection attempt. The agent can't reach this log: the network event log has no rename events, and `/system-log` with admin categories returns HTTP 400. So the audit trail is checked by the owner, outside the agent
  - The write connection runs with the MCP's own permission mode set to bypass, so the client `ask` rule is the only per-call gate on it
- Rollback: none needed
- Approved by / when: owner, 2026-10-28. Read-connection test approved in chat ("the new tests"); Deny clicked by the owner on the prompt

## 2026-10-28: Proof of concept: tier-1 rename through the write connection
- Status: **applied and reverted 2026-10-28** (temporary test; the owner hasn't chosen real AP names yet). End state matches the start state
- Target: one in-wall access point (one of three sharing the model's default name); controller device name only
- Why: first end-to-end test of the per-call-approved gateway write connection, and of whether the client's `ask` rule is enforced for it
- Diff:
  1. Before (read connection, 01:24 UTC): name `<model default>`, online, uplink on the core switch
  2. Write 1 (write connection, `unifi_execute` → `unifi_rename_device`, `confirm: true`): `<model default> -> test-rename`. **Approval prompt appeared** (owner confirmed, screenshot taken before approving). Returned success
  3. Verify (read connection): name `test-rename`, briefly `provisioning`, then `online`, same IP and uplink
  4. Write 2 (same tool): `test-rename -> <model default>`. **Approval prompt appeared** (owner confirmed, screenshot taken). Returned success
  5. Verify (read connection, 01:28 UTC): name back to `<model default>`, `online`, same IP
- Findings: the `ask` rule held in auto mode. Each prompt showed the tool, the device and the new name before anything ran. The read connection lagged the write by up to about a minute (it reported the old name until the AP's next check-in), so verify after a short wait rather than right away. Tool discovery used the read connection's `unifi_tool_index`, so only the two writes went through the write connection
- Rollback: write 2 was the rollback
- Approved by / when: owner, by clicking Allow once on each prompt, 2026-10-28; task set by the governance session the same day

## 2026-10-28: Backup job creates a fresh gateway backup each night
- Status: **applied 2026-10-28.** Deployed on the NAS; first on-demand run stored a backup created the same minute, `archive_check: ok` (verified by the agent through the read-only NAS account). Test: on-demand create returned `rc: ok` in about 1 s; the download was a valid archive; the file does not join the auto-backup list and its name is fixed per controller version, so it is overwritten each run and nothing builds up. The updated job ran twice locally against the gateway (exit 0), and a **test decrypt** with the offline key reproduced the original file's hash exactly
- Target: the NAS backup job; the gateway's network backups (via the backup account, Network Full Management)
- Why: on Network 10.6 the auto-backup schedule is weekly only and the UI has no daily option. "Back Up Now" on the console page makes a cloud console backup, not a network backup the job can fetch
- Diff: before pulling, the job calls the API to create an on-demand network backup and downloads that file. No gateway setting changes. It creates one backup file on the gateway per run
- Test: one on-demand backup created by hand with the backup account, downloaded, validity checked, then discarded
- Rollback: revert the job script; the job falls back to pulling the weekly auto-backups
- Approved by / when: owner, in chat, 2026-10-28 ("Yes, test it")

## 2026-10-28: Agent credentials from 1Password; both MCPs on the read-only accounts
- Status: **applied 2026-10-28** in the agent client config (the NAS launcher swap is done by the owner). Verified before switching: all four agent accounts log in. Gateway read account: Network `readonly`. Gateway write account: Network `admin` and super admin; the owner reduced it the same day to Network **Site Admin** with no other app or admin-management access, and the agent confirmed it is no longer a super admin. NAS read account: not in `administrators`. NAS write account: in `administrators`
- Target: agent client user settings (UniFi plugin options), MCP config (Synology env), the NAS MCP launcher
- Why: the owner keeps the agent passwords in 1Password; the Keychain copies were stale after the accounts were renamed
- Diff: UniFi username → read account, `password_command` → `op read <ref>`, owner's personal API key removed. Synology username → read account, launcher reads `op read "$SYNOLOGY_OP_REF"` instead of the Keychain
- Note: each MCP start is its own `op` process, so each one triggers a 1Password approval
- Smoke test 2026-10-28, after reload, both MCPs on the read accounts:
  - Gateway: `list_networks`, `list_firewall_policies`, `list_clients`, `list_port_forwards`, `list_devices` work. `list_backups` returns 403 (as expected with View Only)
  - NAS, works: `synology_status`, `synology_system_info`, `list_shares`, `list_directory`. `synology_health_summary` succeeds but returns only the system section
  - NAS, needs admin (error 105): `synology_volume_status`, `synology_storage_pool`, `synology_disk_health`, `synology_utilization`, `synology_list_users`, `synology_get_user_permissions`, `synology_services`
  - NAS: the read account lists every share. Not checked yet: whether it can read files in all of them, or only see their names
- Parked: disk, volume and pool health need admin on the NAS. Nothing depends on them yet; revisit with drift detection (SNMPv3 read-only is the likely route)
- Rollback: restore the `.bak-1password` copies of both config files and the previous launcher
- Approved by / when: owner, in chat, 2026-10-28 ("we will now use 1Password, fix the configuration")

## 2026-10-28: Split each MCP into a read connection and a per-call-approved write connection
- Status: **applied 2026-10-28** in the agent client (takes effect in a new session). Gateway write connection runs from the hash-locked environment and was checked to start and log in as the write account. `ask` rules cover both write connections; the NAS write connection also denies `synology_login`. `change-window.sh` runs in gate-only mode. Not yet verified: that the approval prompt appears in a new session, and one real tier-1 write end to end. Not done: a hash lock for the NAS write connection (its launcher still uses `uvx`), and TLS verification for both write connections (the MCPs only support verify on or off, and both devices use self-signed certificates)
- Target: agent client MCP config and permission rules; gateway and NAS agent accounts (2026-10-28: the original agent account on each device was renamed to become the write account, with its password unchanged; the read-only accounts are new)
- Why: change windows need a script, two plugin reloads and a fresh restore point for every write, which is too much for small fixes. With the agent's gateway account at View Only and no write account wired up, the agent can't make gateway fixes at all
- Diff:
  1. Read connections (gateway, NAS) log in as the read-only accounts. No prompts. The gateway read connection drops the owner's personal API key (done; see the 1Password entry above)
  2. New write connections log in as the write accounts, run from the hash-locked environments, and have an `ask` rule on every tool, so each call needs one owner click. Gateway `delete` stays off
  3. The 46 NAS deny rules move from deny to `ask` on the write connection only; the read connection keeps them
  4. Rules: firewall, VLAN, WAN, VPN and NAS share-permission changes still need a `changes.md` entry and a fresh restore point first. Account, authentication, backup and snapshot changes stay with the owner. Everything else is click-to-approve, and the agent logs it here afterwards
  5. `change-window.sh` stays for tier-2 changes; `change-control.md` and `CLAUDE.md` rule 5 are updated to match
- Rollback: remove the write connections and their rules; the read connections keep working
- Approved by / when: owner, in chat, 2026-10-28 ("Build the split")

## 2026-10-28: Rename one access switch (name only)
- Status: **applied 2026-10-28 by the owner in the UniFi UI, outside a change window.** The owner asked for a window in chat, but `change-window.sh open` was blocked (no usable off-box gateway backup on record), so the owner made the rename by hand. The agent did not apply it. Not verified by the agent after the fact
- Target: one access switch (recovered today after a physical reset and re-adopt); controller device name only
- Why: after the reset it came back with the model name; the owner wants a role-based name
- Diff: device name `<model default> -> <owner's chosen name>` via `rename_device`. No port, VLAN, firewall or gateway change
- Window note: `open` enables server-wide `policy_update`, which also covers reboot, firmware upgrade and client deletion ([vetting](vetting/unifi-mcp.md), Finding 5). Had a window opened, the agent would have applied only the rename. The category-scoped window entry above would narrow this
- Rollback: rename it back
- Verify (agent): `list_devices` shows the new name; the switch stays online with the same port table
- Approved by / when: owner, in chat, 2026-10-28 (asked for a window; the backup gate blocked it, so no window was opened and the change did not go through the process)
- Follow-up: record whether low-risk, non-gateway changes should get a lighter path or a logged owner override

## 2026-10-26: Gateway: agent account to View Only
- Status: **applied 2026-10-28** by owner. Smoke test 2026-10-28: `list_networks`, `list_firewall_policies`, `list_clients` and `list_port_forwards` work; **`list_backups` returns 403**, so listing and downloading backups needs more than View Only. The remote-user VPN network also no longer appears in `list_networks` (5 networks instead of 6), so View Only hides some objects. Consequence: the backup job's account will hit the same 403 and needs the lowest role that can list backups
- Target: the agent's local gateway account (used by the UniFi MCP)
- Why: write access should come only from change windows; the account's current role is unknown
- Diff: UniFi OS → Admins & Users → agent account → Network role **View Only**, no other app access, no remote/cloud access
- Verify (agent, read-only): `list_networks`, `list_firewall_policies`, `list_clients`, `list_port_forwards`, `list_backups` still succeed. Any that fail get recorded as needing a higher role
- Rollback: restore the previous role
- Approved by / when: owner, in chat, 2026-10-26

## 2026-10-26: NAS: non-admin account for the agent's everyday reads
- Status: approved 2026-10-26; owner creates the account, agent runs the smoke test
- Target: NAS accounts; the Synology MCP config (username + Keychain item)
- Why: the agent's NAS account is in `administrators` ([vetting](vetting/synology-mcp.md))
- Plan:
  1. Owner creates a new non-admin NAS user for the agent: not in `administrators`, read-only on the shares the agent should see, no access elsewhere, DSM desktop and File Station allowed, everything else denied.
  2. Owner adds its password to the Keychain under service `synology-mcp`, then switches the MCP config's username to it.
  3. Agent runs the read smoke test: `synology_status`, `synology_system_info`, `synology_volume_status`, `synology_storage_pool`, `synology_disk_health`, `synology_health_summary`, `synology_utilization`, `list_shares`, `list_directory`, `synology_list_users`, `synology_get_user_permissions`, `synology_services`. Each one gets recorded as works / needs admin.
  4. Decide from the results: if the health and storage reads need admin, those go through a change window, or later through the proxy in [jit-design.md](jit-design.md).
  5. The current admin account stays for the owner's own use and is removed from the agent's config.
- Rollback: switch the MCP config back to the previous account
- Approved by / when: owner, in chat, 2026-10-26

## 2026-10-26: Synology MCP: deny write tools in the agent client
- Status: **applied 2026-10-26.** 46 deny rules in the agent client's user settings (43 write tools, `synology_login`, Edit/Write on the server's config directory). Verified: the denied tools dropped out of the agent's available tools right away, and read tools still work. Backup of the previous settings kept next to the file
- Target: agent client user settings (permission deny rules)
- Why: 43 write tools with no gating, running as a NAS administrator, no per-call prompt ([vetting](vetting/synology-mcp.md))
- Diff: add `deny` rules for the 43 write tools and `synology_login`, plus deny writes/edits to the server's config directory (so the remote bridge can't be enabled)
- Rollback: remove the rules
- Approved by / when: owner, in chat, 2026-10-26

## 2026-10-26: Synology MCP: hash lock, fixed working directory, TLS verification
- Status: proposed
- Target: the local wrapper script that starts the Synology MCP
- Why: floating dependencies; `./.env` gets loaded from the agent's working directory; TLS verification off while sending an admin password
- Diff: `cd` into the wrapper's own directory before starting; run from a venv built from `docs/vetting/locks/mcp-server-synology-1.8.0.txt`; `VERIFY_SSL=true` with `REQUESTS_CA_BUNDLE` set to the NAS certificate (requires a cert valid for the address used)
- Rollback: restore the previous wrapper
- Approved by / when: pending

## 2026-10-26: Synology MCP: non-admin account for everyday reads
- Status: proposed (needs testing which read tools work without admin)
- Target: NAS accounts; Synology MCP config
- Why: the agent's NAS account is in `administrators`
- Diff: create a non-admin read account for daily use; keep admin credentials for change windows only, or put a filtering MCP proxy in front with a read-tool allowlist and a call log
- Rollback: switch the MCP back to the current account
- Approved by / when: pending

## 2026-10-26: Run the UniFi MCP from the hash-locked environment
- Status: proposed
- Target: agent machine; the UniFi MCP server launch command
- Why: `uvx unifi-network-mcp==0.38.3` re-resolves the libraries that hold the permission gate on every run ([vetting](vetting/unifi-mcp.md), Finding 3)
- Diff: create a venv from `docs/vetting/locks/unifi-network-mcp-0.38.3.txt` with `--require-hashes --no-deps --no-build`; point the MCP server command at that venv's `unifi-network-mcp` instead of `uvx`; disable the plugin's own server entry
- Rollback: re-enable the plugin's server entry
- Approved by / when: pending

## 2026-10-26: Category-scoped change windows
- Status: proposed
- Target: `scripts/change-window.sh`
- Why: server-wide `update` also enables reboot, firmware upgrade, port power-cycle and permanent client deletion ([vetting](vetting/unifi-mcp.md), Finding 5)
- Diff: `open` takes the categories the change needs and enables only `UNIFI_POLICY_NETWORK_<CATEGORY>_<ACTION>` for those, leaving server-wide create/update off. First check how the client passes extra env vars to the MCP process
- Rollback: revert the script
- Approved by / when: pending

## 2026-10-26: Daily gateway backups to the NAS
- Status: approved 2026-10-26 (design in [gateway-backups.md](gateway-backups.md)); **NAS job running since 2026-10-28.** First run (owner-triggered, exit 0): pulled the newest gateway auto-backup (2026-10-25), `archive_check: ok`, encrypted to the offline key, manifest written; verified by the agent through the read-only NAS account. The backup share turned out not to be encrypted at the folder level; left as is, since every file is encrypted to the offline key. Weekly-to-daily isn't possible on Network 10.6 (no UI option); replaced by the on-demand entry above. Laptop gate connected 2026-10-28: `change-window.sh` fetches the manifest and the latest backup over the DSM API as the agent's read-only NAS account (TLS key pinned; a wrong pin is refused). `status` reports a NAS restore point 0 h old
- Finding 2026-10-28: listing backups (`cmd/backup list-backups`) returns 403 for both **View Only** and **Site Admin**. The backup account currently has the predefined Viewer role, which also grants read access to the other UniFi apps and the user list; it needs Network only. Retested the same day with Network **Full Management** and no other app or admin access (not super admin): listing works (8 auto-backups, newest 2026-10-25) and downloading works (HTTP 200). So Full Management is the lowest role that works. Community sources saying Super Admin or Owner is required are outdated for this firmware. Trade-off: the job's credential can change the entire network, so it stays on the NAS only, local-only, and readable only by the job user
- Target: gateway (new backup account; auto-backup weekly → daily), NAS (share, two users, immutable snapshots, scheduled job)
- Why: the only gateway backups are stored on the gateway itself; change windows need a verified off-box restore point
- Diff: see the build order in gateway-backups.md; the gateway auto-backup schedule `30 0 * * 0` → `30 0 * * *`, max files unchanged
- Rollback: disable the NAS task; set the auto-backup schedule back to weekly; the share and snapshots can stay
- Approved by / when: owner, in chat, 2026-10-26 (design; each device step still runs as its own step)

## 2026-10-26: Disable stale WAN port forwards to the NAS
- Status: **rejected after being applied: rolled back 2026-10-28.** End state matches the start state (both rules enabled)
- Target: gateway, two port-forward rules to the NAS
- Why (as proposed): they expose the NAS to the internet on two ports; the service they were thought to be for now runs behind a VPN tunnel in the app VM
- Diff:
  1. Before (read connection): both rules enabled, TCP+UDP, any source
  2. Disable (write connection, `unifi_toggle_port_forward`, `confirm: true`), one call per rule, approval prompt on each. Both returned `enabled: false`; read-back confirmed
  3. Owner: a different client on the NAS, which the agent didn't know about, still uses both forwards. **The premise was wrong**
  4. Rollback, re-enabling both (write connection, same tool), one call per rule. The owner denied the second prompt at first, thinking it was the read-back; the agent stopped, checked state through the read connection (one rule on, one off), and the owner then approved the retry
  5. Verify (read connection): both rules enabled, as before
- Findings:
  - **Process failure: the "Check first" step was skipped.** It asked whether anything on the NAS still used the ports. The agent assumed nothing did, applied the change and noted the skip afterwards. Writing a skipped step down doesn't make skipping it safe. Proposed for `change-control.md` (owner's call): a check in a proposal blocks the write until it's done or the owner waives it in chat
  - The task list showed the rollback as done while the second write was still waiting for approval, so the prompt looked like a read. One step per write call from now on
  - The forwards aren't stale, but they still expose the client to the internet from any source. Narrowing that is a new proposal, with the specifics in `private/`
- Rollback: done (step 4)
- Approved by / when: owner, 2026-10-28, in chat ("Yes, close them"), Allow on each disable prompt; rollback approved in chat ("Yes, roll back") and on each prompt

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
