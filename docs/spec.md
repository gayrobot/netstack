# netstack: what the system is

**Status:** proposed 2026-11-02. **Review:** with [strategy.md](strategy.md), every Sunday; the whole document by 2027-01-29.

This is the definition of the system. [strategy.md](strategy.md) says what we're protecting and in what order; this says what the thing we're building *does*, judged from the owner's side. Everything else in the repo (the tiers, the gates, the vetting, the backlog) exists to serve this.

## One sentence

A management plane for the house's infrastructure: it watches the network, the hosts, the storage, the patch state, the backups and the infrastructure identities, keeps them patched on their own, and tells the owner only when something needs a person.

## Why this document exists

Through 2026-11-02 the repo governed one thing well: an agent, in a session, with the owner watching, changing the network. Read/write split, per-call approval, the restore-point gate, tiers, the change log. That's the write path, and it's a small fraction of what managing a home network is. The rest is watching: inventory, advisories, drift, failures, patch state. None of it existed, nothing ran on its own but the backup job, and "the agent" meant Claude Code on the admin laptop.

The write-path controls stay. They become the spine that the watching layer hands its proposals to. This document specifies the watching layer and the one place it's allowed to act on its own.

## Outcomes

The system is working when all of these are true. They are the acceptance test for every build item, and the Sunday review checks them before anything else.

1. **One push a week unless something's wrong.** A Sunday digest, and otherwise silence.
2. **An advisory for something the house owns, with a fix available, reaches the owner within a day.** Advisories for things the house doesn't own, or with no fix, never interrupt.
3. **A change made outside the agent shows up within a day.** A change made through the agent is marked verified without the owner doing anything.
4. **Every target updates itself.** The owner hears about an update only when it failed, hasn't landed within its window, or broke something afterwards.
5. **Nothing in `docs/hosts/` or the inventory is hand-maintained.** It regenerates from what the collectors read.
6. **Adding a host of a known class costs nothing.** A new class costs one collector, through one PR.

## Scope: the three planes

| Plane | What's in it | netstack's concern |
|---|---|---|
| **1. Infrastructure** | Gateway, switches, APs, the VM host and its VMs, the NAS, the container VLAN, backups, the accounts and tokens that touch any of these | **All of it.** This is the system |
| **2. Platform services** | Home-automation OS, HomeKit bridges, the home-automation plugin, calendar integrations, other services | **As workloads and identities only.** Their hosts get inventoried, patched and segmented; their credentials and agents go in the identity inventory; the plugins get vetted |
| **3. Automations** | What those services do: sync a calendar, run a schedule | **None.** Governed by the service's own permission model. A future agent that acts on the house is a separate project and a client of this one |

The identity inventory (plane 1, threat T6) deliberately reaches into plane 2: every service account, API token, VPN peer and agent credential in the house is listed, with an owner and an age, whatever it's for.

## Architecture

One container, the **observer**, on the app VM, on the container VLAN, using the read accounts that already exist. It runs on a schedule and holds no interactive session.

```
feeds (KEV, vendor advisories, OS security, image scans)
gateway · NAS · app VM · VM host · home-automation VM   (read accounts)
        │
        ▼
   collectors  ── deterministic; one per device class; write structured records
        │
        ▼
      store    ── SQLite; inventory, snapshots, advisories, events, patch log
        │
        ▼
   detectors   ── deterministic; state diffs, advisory matches, thresholds
        │
        ├──► notifier   push (page) · Sunday digest · log, by severity
        ├──► proposer   writes a changes.md entry or a PR; never applies it
        ├──► patch lane the one autonomous write (below)
        ├──► interpreter  optional: Claude reads the diff that's already computed,
        │                 explains and ranks it, drafts the proposal and the digest
        └──► view       one page that reads the store
```

Design rules, in order of how much they matter:

1. **Deterministic except the interpreter.** Collectors and detectors are plain code with tests that fake the device. Two runs on the same state produce the same result. The LLM never polls a device, never decides whether something changed, and never sees a write tool.
2. **Untrusted data stays in a column.** Device names, SSIDs, filenames and advisory text are fields in records. The interpreter sees records, with the fields labelled, not raw text pasted into a prompt. This is threat T5 for an unattended run, and it's the reason the interpreter is optional: if it's down, over budget or wrong, the diffs and matches still land, unexplained.
3. **No write connection exists in the observer's configuration**, except the patch lane's, which is scoped to its targets. Not gated; absent.
4. **Proposals go through the spine.** The observer's only route into the write path is a `changes.md` entry with its checks listed, the same as a session would write. A person approves; the tiers apply.
5. **It can't change itself.** Detector thresholds, soak periods, severities, collector code and the patch policy are tier 3: a PR the owner merges.

## Collectors

One per device class. Each reads through the existing read account, writes records with a timestamp and a source, and keeps the raw response in `private/` for debugging. "Not yet" means the collector is wanted but blocked; the blocker is a backlog item.

| Class | Reads | Through | State |
|---|---|---|---|
| Gateway | Devices and firmware, networks and VLANs, DHCP scopes and leases, clients, port forwards, firewall policies, VPN peers, admin accounts, alerts, IPS events, memory | UniFi read account (View Only) | build first; this is drift detection (was D1) done properly |
| NAS | DSM version, packages and their versions, shares and permissions, NFS rules, snapshot schedules, login log, the backup job's manifest | NAS read account; `synology-extras` for package versions (exception EX-1) | build second |
| App VM | OS and package state, pending security updates, listeners, container list with image digests and states | A read-only Docker API proxy and a user with neither `docker` nor `sudo` (backlog C5; pulled forward because this collector needs it) | after C5 |
| VM host | macOS version, VMs and their state, listeners | A small script under `launchd` on the host that posts records to the observer. Remote Login is off, so the path is local: Claude Code is installed on the host and writes and installs the script (tier 3, the owner runs the install); it does not run the collection itself. Rewritten, not redesigned, at a Linux move | build with O2 |
| Home-automation VM | OS version, the plugin's version, its credentials | after B7 gives it a network leg the observer can reach, and after A12 vets the plugin | not yet |
| Feeds | CISA KEV; Ubiquiti security advisories; Synology security advisories; Ubuntu security notices; image vulnerability scans | Pinned sources, each with its own vetting entry | build with the advisory detector |
| Identities | Every account, token, VPN peer and agent credential the house has, with owner, scope and age. Includes every Claude Code install in the house (the admin laptop, the VM host) and the tokens each holds, since an always-on host with an agent on it is a standing credential | Gathered from the other collectors plus a hand-kept list in `private/` for the ones no API shows | build third |

## Detectors

Each detector has a severity and a false-positive log. Severities:

- **Page:** push notification now.
- **Digest:** waits for Sunday.
- **Log:** stored, shown in the view, never pushed.

| Detector | Fires when | Severity |
|---|---|---|
| Unapproved change | A snapshot differs from the baseline and no approved `changes.md` entry matches the diff | page for gateway and NAS; digest for everything else |
| Approved change landed | A diff matches an approved entry | log; marks the entry verified |
| Advisory match | A feed item names a product and version the inventory has **and** a fix is available | page if KEV or vendor-rated critical; otherwise digest |
| Patch lag | A fix has been available longer than the target's window and the inventory still shows the old version | page |
| Patch failed | The vendor updater reports failure, or a post-update health check fails | page |
| Backup stale | The nightly gateway backup is older than the gateway's next update window, or the job's manifest is missing | page |
| Health | A switch or AP offline past a threshold; a container exited; gateway memory over threshold; the VPN gateway's tunnel down; a DNS resolver the DHCP scopes hand out not answering | digest, page after it persists for a day |
| Identity | A new admin account; a new VPN peer; a token past its rotation age; a credential with no owner in the inventory | page |
| New device | A client the inventory hasn't seen, on a network where new devices aren't expected | digest; page once the IoT and guest networks exist and the device is on a trusted one |
| Traffic anomaly | IPS events, unexpected egress, DNS oddities | **deferred until Phase B.** Until Phase B segments the network there's no baseline for "unusual" |

**Demotion rule.** Three false positives from one detector in a month demotes it one severity until its next review. A demotion is a line in the Sunday digest, and the fix is a PR, not a toggle in the running system.

The policy the observer reads is the JSON block in [detectors.html](detectors.html), which also renders this table with the rows still under review marked. The table above is the prose copy; when they disagree, the JSON wins and this gets fixed.

## The patch lane

The one place the observer acts on its own. The principle: **the vendor's own updater does the update; the observer verifies it happened, catches the lag, and checks nothing broke.** The observer never applies a gateway, NAS or OS update itself.

| Target | Updater | Window | After | Rollback |
|---|---|---|---|---|
| Gateway (UniFi OS, Network app) | UniFi auto-update, on | its schedule, nightly. **The backup job runs before it**, so a restore point younger than the update always exists | health check: all devices adopted, VPN up, DHCP scopes' resolvers answering, memory under threshold | the previous night's off-box backup |
| Switches, APs | UniFi auto-update, on | same | adoption and uptime | UniFi keeps the prior firmware |
| NAS DSM and packages | DSM auto-install for important updates and packages, on (tier 3, the owner sets it once) | DSM's schedule | DSM reachable, shares mounted on the app VM, backup job's next run succeeds | DSM's own |
| App VM OS | `unattended-upgrades`, security pocket only | daily | listeners unchanged, containers running | apt history |
| Container images | A small job in the app VM: new digest upstream → pull → start → health check → commit the digest bump to the compose repo. This is the one updater we build, and the only one that writes | daily | container healthy five minutes after restart | previous digest, automatic on a failed health check |

"Validated" per target: the update came from the vendor's own channel (not a mirror, not a third-party build); for images, it also passes the image scan the feeds collector runs. Soak periods start at zero and are a policy knob per target; raising one is a PR.

Every applied update is logged with before and after versions and the health-check result. A failed health check pages. A failed rollback pages and stops the lane for that target until a person looks.

## What happens when the infrastructure changes

**The inventory is observed, never declared.** The owner doesn't tell the system what the house has; the collectors read it. So a change is a diff, and every diff ends one of three ways:

1. **Through the agent.** A `changes.md` entry exists. The observer matches the diff to the entry and marks it verified. Nothing for the owner to do.
2. **By hand in a UI.** No entry matches. Push: "gateway: forward X enabled, no approved change." The owner replies *mine* and the observer records an acknowledged manual change and moves the baseline. No reply, and it stays open on the Sunday digest. (How the reply gets back to the observer is decided at build time: the push channel's reply feature, or a one-line file in the repo.)
3. **New hardware.** A device of a class the collectors know (another switch, another container) appears in the inventory on the next run and gets watched. A new class (a Linux host replacing the VM host, a second NAS) needs a collector: one PR, one vetting entry. That is the whole cost of a migration, and the host page regenerates itself afterwards.

## Governance of the observer

What's new here, and why "governance is the core" becomes true rather than aspirational:

- **No standing write access**, except the container-image lane in the app VM, which writes to the compose repo and the Docker socket and nothing else.
- **Proposals only** into the gateway, NAS and host write paths. The tiers in [change-control.md](change-control.md) are unchanged.
- **Detector quality is governed like a rule.** False-positive logs, the demotion rule, and changes by PR.
- **Feeds are vetted like MCP servers.** Which sources, pinned how, what the observer does when one is unreachable (it says so in the digest; it doesn't guess). Entries in [vetting/](vetting/).
- **The push channel is vetted** the same way: it carries the names of what's in the house.
- **The interpreter is replaceable.** It has a budget, it reads records not prompts, and the system is complete without it.
- **The observer's own credentials** are in the identity inventory with a rotation age, like everything else.

## Build order

Alongside Phase A and B of the backlog, not after them. The observer doesn't depend on segmentation; the traffic-anomaly detector does, and it waits.

| ID | Item | Done when |
|---|---|---|
| O1 | Observer container on the app VM: scheduler, store, notifier with a pushed test message, the view skeleton | A test event pages the owner's phone |
| O2 | Gateway collector and the unapproved-change detector; baseline taken from the current approved state; `docs/network.md` regenerated from the store | Outcome 3 for the gateway. D1 closes |
| O3 | NAS collector; backup-stale detector reading the job's manifest; health detector for the backup job | Outcome 3 for the NAS |
| O4 | Feeds collector and the advisory and patch-lag detectors, starting with KEV and the two vendors' advisories | Outcome 2 |
| O5 | Patch lane: vendor auto-update on everywhere (owner, tier 3, one checklist); backup job scheduled before the gateway's window; post-update health checks | Outcome 4 for the gateway, switches, APs and NAS |
| O6 | App VM collector (needs C5) and the container-image updater | Outcome 4 for the app VM and containers |
| O7 | Identity inventory and detector | Every credential in the house has an owner and an age |
| O8 | Interpreter: Claude drafts the digest and the proposals from the store's records | The Sunday digest reads like a person wrote it, and the owner stops reading the raw diffs |
| O9 | Hosts pages regenerated from the store; the hand-written ones retired | Outcome 5 |
| O10 | Traffic-anomaly detector | after Phase B |

D1 and D3 from the backlog are O2, O3 and O5. D2 (the quarterly test restore) and D4 (review dates) stay as they are.

## Not in this system

- What the home-automation services do (plane 3).
- A broker, policy engine or tier-1 auto-approval ([jit-design.md](jit-design.md)). The observer proposes; it doesn't need grants. The parking lot keeps the design for the day an agent needs to write on a schedule, and the patch lane is the evidence that day may never come.
- A SIEM, log shipping or a dashboard product. The view is one page over SQLite.
- Physical security inside the house (strategy's out-of-scope list).

## Couldn't verify

- The current state of the network and hosts. This was written from the repo's docs; the first collector run is the first fresh read.
- That UniFi auto-update is on for the gateway and the switches, and what its schedule is. The owner said it is; O5 confirms it from the read account.
- Whether DSM's auto-install covers the packages the house runs, or only DSM itself.
- What credentials the Claude Code install on the VM host holds today, and whether it's the "admin laptop" in `CLAUDE.md` or a second install
- Whether the UniFi read account can see firmware availability (not just the installed version). If not, the Ubiquiti feed carries that.
- Whether the push channel chosen at vetting supports a reply, which decides how *mine* gets back to the observer.
- That a read-only Docker API proxy exposes image digests (it should; it's a plain `GET`).
