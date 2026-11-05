# Backlog

The ordered list of work from [strategy.md](strategy.md). Newest state wins; update it at the Sunday review. Items use role names; the specifics (which client, which port, which switch) are in `private/`.

Columns: **Threat** is from the strategy's threat table. **Tier** is from [change-control.md](change-control.md); "owner" means tier 3 or a physical step, and the agent prepares a checklist. **Effort** is wall-clock for one session: S under an hour, M a session, L more than one.

## Phase A: quick wins

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| A1 | **Close the NAS's inbound internet exposure.** Both forwards were disabled 2026-11-05 and the read connection confirms nothing else forwards those ports. Tried and rolled back 2026-10-28 because a check was skipped. The service they served now has a second home in the app VM (part 1, applied 2026-11-05); moving its remaining tasks is E1. Still open: an outside probe of the ports, the NAS-side listener state (the read account can't see it), and the new gateways' kill-switch test (needs a shell on the VM). Specifics are in `private/` and `changes.md` | T2 | 2 / owner | L | part 1 and part 2 applied 2026-11-05; risk R1 ended |
| A2 | Fix DNS on the container VLAN: DHCP hands out resolvers the Containers zone can't reach | T1 | 2 | S | done 2026-10-31: the VLAN's DHCP DNS now points at its own gateway, verified through the read connection (see `changes.md`). Nothing answered at the old resolvers. Stopgap until B4 |
| A3 | Turn threat management (IPS) on for every network, not just the main LAN; watch gateway memory afterwards | T1 | 2 / owner | S | done 2026-11-02: all three internal networks protected, verified through the read connection. The UI dropped one legacy category (accepted). Memory reads at 1 h and 24 h still open (see `changes.md`) |
| A4 | ~~Set mDNS reflection to the services that need it~~ Folded into B2: scoping reflection means nothing while everything is still on one VLAN, so decide it when the IoT, camera and guest networks exist | T1 | – | – | moved to B2 2026-11-02 (owner's call) |
| A5 | ~~Unplug or isolate the travel router wired into an access-switch port~~ | T1 | – | – | won't do 2026-11-02 (owner's call): the travel routers are the owner's controlled gateways for arcade games. Others exist but are offline. Not a rogue device; don't flag them again. If they ever need isolating, that's part of the B2 zone design |
| A6 | Resolve the access switch in unknown state since mid-October and the offline mini switch; apply the pending firmware update | T1 | 1 / owner | M | done 2026-11-02: the "unknown" switch was the 8-port PoE switch (owner). Re-adopted around 2026-10-28 in a session outside the repo; the read connection shows it online and current, and no switch has a firmware update waiting. The mini switch is offline by design (owner call below). Its last uplink is listed under the core switch's default model name, from before the core switch was renamed; it's the same switch |
| A7 | ~~Disable unused switch ports~~ | T1 | – | – | won't do 2026-11-02 (owner's call): physical access to the house is out of scope (see strategy's out-of-scope list). Revisit only if an untrusted person gets physical access, such as a rental room or a business use |
| A8 | Review VPN peers: one per device, delete unknown ones | T6 | owner | S | **done 2026-11-02.** The only server is Teleport (owner's phone, laptop, tablet); the old WireGuard server is gone. Teleport doesn't list enrolled devices, so the peer review moves to O7 |
| A9 | Review gateway admin accounts; MFA on the cloud account | T6 | owner | S | **done 2026-11-02.** Six console users, all known; MFA on the owner's cloud account; the home-automation account trimmed |
| A10 | NAS: disable the default `admin` and `guest` accounts; 2FA on the owner's account; disable QuickConnect if unused | T2, T6 | owner | S | **done 2026-11-02.** `admin` and `guest` deactivated; the one admin is the owner's daily account, with 2FA; no other account is an admin; QuickConnect off. Leftover: one account to review (details in `private/`) |
| A11 | NAS share clean-up: share and package clean-up (specifics in `private/`) | T2, T4 | 2 / owner | S | done 2026-11-05, by the owner in DSM and confirmed through the read connection. Left for the owner (tier 3): narrow the write account's access to what a change needs |
| A12 | Vet the home-automation plugin (HomeClaw) that's already installed. It can act on home-automation devices | T5 | 3 | M | vetted 2026-11-05: OK with conditions, see [vetting/homeclaw.md](vetting/homeclaw.md). The filter couldn't be narrowed, so the owner accepted the risk 2026-11-05: strategy.md R2, review by 2027-01-29. Keep the webhook off |

## Phase B: segmentation

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| B1 | Owner decisions from the 2026-10-21 audit: which Wi-Fi network keeps the current name; whether to keep the DNS filter; whether servers move to the server VLAN now or later; which network the doorbell joins; any Matter or Thread devices; identify the unknown clients | – | owner | S | open; blocks B2. 2026-11-05: the doorbell stays with the cameras (owner); the Wi-Fi name question is gone (no SSID change, B8); four unidentified clients listed in `private/segmentation-devices.md` |
| B2 | Create the IoT-Cloud and IoT-Local networks, the IoT zone and its policies, with no clients moved yet. Includes the mDNS proxy scope for HomeKit (was A4) and adding both networks to IPS (A3). Design: [segmentation.md](segmentation.md). The guest network is B3's | T1 | 2 | M | designed 2026-11-05 (owner asked: VLAN by MAC on the existing Wi-Fi, HomeKit across VLANs, cameras unchanged); proposed in `changes.md`. Owner decided 2026-11-05: daily update window, thermostats and lighting bridge to IoT-Local, moves tier 1, unidentified clients to IoT-Cloud as containment. Ready for step 1 |
| B3 | Guest Wi-Fi on the guest network: internet only | T1 | 2 | S | open |
| B4 | DNS filter on the server VLAN at the address DHCP already expects, with a second resolver; or drop it and point DHCP at a working resolver (A2 is the stopgap) | T1 | 2 | M | open; depends on B1. Read 2026-10-31: nothing answers at those addresses, and the server VLAN hands out the same dead pair, so this item covers that VLAN too |
| B5 | ~~Cameras to the camera VLAN, one at a time, from the switch ports; the doorbell by Wi-Fi~~ | T1 | – | – | won't do 2026-11-05 (owner's call): the cameras and doorbell stay as they are, on UniFi's own path |
| B6 | A trusted Wi-Fi network for phones, laptops and watches: WPA3 only, management-frame protection required | T1, T6 | 2 | M | open |
| B7 | ~~The home-automation VM gets a second NIC on the IoT VLAN~~ | T1 | – | – | not needed 2026-11-05: Internal → IoT is allowed and the firewall is stateful, so home automation reaches the IoT networks from where it is ([segmentation.md](segmentation.md)). Reopen only if an integration needs layer-2 discovery the mDNS proxy can't carry |
| B8 | Move smart devices by MAC (Virtual Network Override), no SSID change: a pilot of one plug and one vacuum, then IoT-Cloud, then IoT-Local, the lighting bridge last; update home-automation integrations pinned to an IP. Rollout steps 2–5 in [segmentation.md](segmentation.md) | T1 | 1 per move | L | open; after B2. Single-client moves are tier 1 (owner, 2026-11-05). The override has no MCP tool, so the owner sets it from the agent's checklist and the agent verifies each move |
| B9 | Internal → Containers: replace the broad allow with one allow per service that a trusted device needs | T1 | 2 | M | open |
| B10 | Tighten: shrink the main LAN DHCP pool; DNS enforcement on IoT; optional: servers to the server VLAN (its own plan, since it re-IPs NFS and the container policies) | T1 | 2 | L | open |

## Phase C: servers

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| C1 | NAS firewall: DSM, SMB and NFS from trusted and VPN only; auto-block on | T2 | owner | M | open |
| C2 | NAS data protection: scheduled snapshots of the data shares, a quarterly scrub, an off-site backup; then a test restore of one share | T4 | owner | L | open |
| C3 | App VM: turn off a service it doesn't need | T1 | 1 | S | proposed 2026-10-26, pending. **Parked by the owner 2026-11-05;** do it the next time the owner is logged in to the VM. The two commands are in `changes.md` |
| C4 | NFS export tightened to the app VM | T1, T3 | 2 | S | open |
| C5 | App VM inventory account: a read-only Docker API proxy and a user with neither `docker` nor `sudo`, replacing the current inventory account | T5 | 3 | M | open |
| C6 | Containers: pin images by digest; bring the exited monitoring container back; fix or drop the allow rule that points at its unassigned IP | T3 | 2 / owner | M | open |
| C7 | Confirm inbound IPv6 is blocked for the servers and decide whether they need SLAAC at all | T2 | 2 | S | open |
| C8 | Synology MCP: run from the hash lock, fixed working directory, TLS verification on | T5, T6 | 3 | S | proposed 2026-10-26, pending |
| C9 | UniFi MCP: run from the hash-locked environment instead of re-resolving on every start | T5 | 3 | S | proposed 2026-10-26, pending |

## Phase O: observer (alongside A and B)

The watching layer from [spec.md](spec.md). It doesn't depend on segmentation, so it runs in parallel with A and B. Each item's "done when" is in the spec's build-order table; the outcome it serves is listed here.

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| O1 | Observer container on the app VM: scheduler, SQLite store, push notifier (channel chosen at vetting), view skeleton. A test event reaches the owner's phone | T5, T6 | 3 (new workload, new credential) | M | open; needs vetting entries for the push channel |
| O2 | Gateway collector + unapproved-change detector; baseline from the current approved state; `docs/network.md` regenerated from the store | T5, T6 | 0 | L | open; closes D1 (outcome 3) |
| O3 | NAS collector; backup-stale and backup-job health detectors from the job's manifest | T4 | 0 | M | open (outcome 3) |
| O4 | Feeds collector (KEV, Ubiquiti and Synology advisories, Ubuntu security notices, image scans) + advisory-match and patch-lag detectors | T2, T3 | 0 | L | open; needs one vetting entry per feed (outcome 2) |
| O5 | Patch lane, vendor side: auto-update on for the gateway, switches, APs and DSM (owner checklist, tier 3); backup job rescheduled before the gateway's update window; post-update health checks in the observer | T2, T3 | owner + 0 | S | vendor side done 2026-11-02: device firmware 03:00 (read connection), gateway OS and apps 03:00, DSM 04:00, packages on release (owner); backup 01:30 runs first. Post-update health checks wait for O1 (outcome 4) |
| O6 | App VM collector (needs C5) and the container-image updater: new digest → pull → health check → digest bump committed to the compose repo; rollback on failure. The only autonomous write | T3 | 1 (scoped to the compose repo and the Docker socket) | L | open; blocked by C5 (outcome 4) |
| O7 | Identity inventory and detector: every account, token, VPN peer and agent credential with an owner and an age; pages on a new admin, a new peer or an aged token | T6 | 0 | M | open; folds in the review half of A8 and A9 once they're done by hand |
| O8 | Interpreter: Claude drafts the Sunday digest and the proposals from the store's records, with a budget; the system is complete without it | T5 | 3 | M | open; after O2–O4 produce records worth explaining |
| O9 | Host pages regenerated from the store; the hand-written `docs/hosts/` retired | – | 0 | S | open (outcome 5) |
| O10 | Traffic-anomaly detector (IPS events, egress, DNS) | T1 | 0 | M | **after Phase B**; no baseline until the network is segmented |

## Phase D: sustain

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| D1 | ~~Drift detection~~ | T5, T6 | – | – | superseded by O2 and O3, 2026-11-02 |
| D2 | Quarterly gateway test restore into a throwaway controller; date recorded in the backup manifest | T4 | owner | M | open |
| D3 | ~~Alerts for what failed silently~~ | T1, T3 | – | – | superseded by the health detector in O2, O3 and O5, 2026-11-02 |
| D4 | Review dates: exceptions and rubrics on 2027-01-29; read-only token rotation (automated, one approval) | T5 | 3 | S | scheduled |

## Phase E: after the current plan

Owner's order, 2026-11-05: last in the backlog; start only when A–D are done.

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| E1 | Move the NAS service's remaining tasks to the containers built in A1 part 1, then turn the NAS-side module off. The exposure is already closed (A1 part 2) | T2 | owner | M | open; deferred by the owner 2026-11-05 |

## Parking lot: governance ideas with no backlog item yet

Reviewed monthly. Built only when an item above needs it.

- Broker / MCP proxy on a separate host, policy engine, tier-1 auto-approval ([jit-design.md](jit-design.md)). Needs: the agent making changes on a schedule. Not yet. 2026-11-02: the observer ([spec.md](spec.md)) proposes rather than writes, and the one scheduled write (container images, O6) is scoped to the app VM, so this stays parked
- Category-scoped change windows (proposed 2026-10-26). Needs: the flag-flipping window mode, which the write connections replaced
- A `SessionStart` warning for passed review-by dates. Needs: a review date to pass
- Server-side denylist CI with other contributors. Needs: other contributors
- A `changes.md` check that blocks the write until each "check first" step is ticked. Strategy principle 6 covers it as a rule; automate it after it's been followed by hand for a few changes

## Owner calls that shape the backlog

Recorded 2026-11-02 so no session has to be told again. This is a home, not an enterprise. Before proposing an item, check it against how the house is used.

- Physical security inside the house is out of scope (strategy). Don't propose port lockdowns, port-security or similar controls aimed at someone plugging in.
- The travel routers on the network are the owner's arcade-game gateways, some offline. Don't call them rogue.
- The mini switch travels in the owner's DJ gear case and joins the network only when that gear is used away from its usual desk. Offline is its normal state; don't flag it (owner, 2026-11-02). The observer's offline detector needs an exception for it.
- Don't propose a control whose benefit depends on a segmentation step that hasn't happened (mDNS scoping before the IoT VLAN exists). Put it in the item that creates the segments.
- Spending on a different VPN provider is acceptable to get A1 done.
- Everything updates itself (owner, 2026-11-02). Don't propose "notify and click" for any patch target; propose the vendor's auto-updater plus a check that it ran. The observer verifies, it doesn't install.
- Status checks never need governance (owner, 2026-11-02). A read-only check, such as a post-change read or update verification, gets scheduled and run by the agent through the read connections, with no `changes.md` entry, PR or owner step. Its result is reported, and recorded only when the next PR touches that entry.
- Home-automation syncs and automations (calendars, HomeKit scenes) are plane 3 in [spec.md](spec.md): not this repo's concern. Their hosts and credentials are.

## Friction log

One line per time a control got in the way. Reviewed monthly with the parking lot; fix the rule only when a line repeats.

| Date | What got in the way | What was done instead |
|---|---|---|
| 2026-10-28 | A task list showed a rollback as done while the second write still waited for approval; the prompt looked like a read and was denied | One step per write call |
| 2026-10-29 | Every session start prompted 1Password up to four times | Read connections on a read-only token; write connections behind the write gate |
| 2026-10-29 | New worktrees didn't inherit the project's MCP config, then did | Config moved to repo scope |
| 2026-11-02 | "What's next" recommended A4, A5 and A7 off the backlog's text alone; the owner rejected all three as not fitting a home | Items closed or folded in above; the owner-calls section records why |
| 2026-10-31 | The UniFi read plugin had been silently missing since 2026-10-29: worktree sessions take project settings from the main checkout, which had gone stale after PRs merged on GitHub | Main checkout fast-forwarded by hand |

## Couldn't verify

- Current state of any item. Statuses come from the repo's docs and the 2026-10-21 audit; the first Sunday review starts with a fresh read.
- Whether A6's outside session finished the re-adopt.
- The effort estimates. They're guesses until a few items have been done at this pace.
