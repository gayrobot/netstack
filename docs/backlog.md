# Backlog

The ordered list of work from [strategy.md](strategy.md). Newest state wins; update it at the Sunday review. Items use role names; the specifics (which client, which port, which switch) are in `private/`.

Columns: **Threat** is from the strategy's threat table. **Tier** is from [change-control.md](change-control.md); "owner" means tier 3 or a physical step, and the agent prepares a checklist. **Effort** is wall-clock for one session: S under an hour, M a session, L more than one.

## Phase A: quick wins

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| A1 | **Move the NAS's peer-to-peer download client behind the VPN gateway container, then close the two internet-facing port forwards.** Check done 2026-10-31: the forwards are that client's inbound peer port. Checks still open: the VPN provider offers port forwarding; the forwards map to the peer port only. Then: a client container in the app VM sharing the VPN gateway's network namespace, the download share mounted over NFS, the provider's forwarded port set in both, the kill switch verified, tasks moved over, the NAS client's peer-to-peer module off, both forwards disabled, verified from outside | T2 | 2 / owner | L | open; risk R1 accepted 2026-10-31 until this lands. Tried and rolled back 2026-10-28 because the check was skipped |
| A2 | Fix DNS on the container VLAN: DHCP hands out resolvers the Containers zone can't reach | T1 | 2 | S | open |
| A3 | Turn threat management (IPS) on for every network, not just the main LAN; watch gateway memory afterwards | T1 | 2 | S | open |
| A4 | Set mDNS reflection to the services that need it instead of all, so the new VLANs in phase B don't see every service | T1 | 2 | S | open; do before B2 |
| A5 | Unplug or isolate the travel router wired into an access-switch port | T1 | owner | S | open; physical |
| A6 | Resolve the access switch in unknown state since mid-October and the offline mini switch; apply the pending firmware update | T1 | 1 / owner | M | open; a session outside the repo is already on the re-adopt. Finish it there, log the result here |
| A7 | Disable unused switch ports (they're enabled with the all-VLANs profile) | T1 | 1 | S | open |
| A8 | Review VPN peers: one per device, delete unknown ones | T6 | owner | S | open |
| A9 | Review gateway admin accounts; MFA on the cloud account | T6 | owner | S | open |
| A10 | NAS: disable the default `admin` and `guest` accounts; 2FA on the owner's account; disable QuickConnect if unused | T2, T6 | owner | S | open |
| A11 | NAS share clean-up: the world-writable share, the empty shares, the stale NFS rule, the unused packages | T2, T4 | 2 / owner | S | open |
| A12 | Vet the home-automation plugin (HomeClaw) that's already installed. It can act on locks and cameras | T5 | 3 | M | open; listed as "not vetted" in [vetting/README.md](vetting/README.md) |

## Phase B: segmentation

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| B1 | Owner decisions from the 2026-10-21 audit: which Wi-Fi network keeps the current name; whether to keep the DNS filter; whether servers move to the server VLAN now or later; which network the doorbell joins; any Matter or Thread devices; identify the unknown clients | – | owner | S | open; blocks B2 |
| B2 | Create the IoT, camera and guest networks and zones and their policies, with no clients moved yet | T1 | 2 | M | open |
| B3 | Guest Wi-Fi on the guest network: internet only | T1 | 2 | S | open |
| B4 | DNS filter on the server VLAN at the address DHCP already expects, with a second resolver; or drop it and point DHCP at a working resolver (A2 is the stopgap) | T1 | 2 | M | open; depends on B1 |
| B5 | Cameras to the camera VLAN, one at a time, from the switch ports; the doorbell by Wi-Fi | T1 | 2 | M | open |
| B6 | A trusted Wi-Fi network for phones, laptops and watches: WPA3 only, management-frame protection required | T1, T6 | 2 | M | open |
| B7 | The home-automation VM gets a second NIC on the IoT VLAN, the way the app VM reaches the container VLAN | T1 | owner | M | open; VM host change |
| B8 | Flip the existing Wi-Fi network to the IoT network; wired IoT devices to IoT ports; fixed IPs; update home-automation integrations | T1 | 2 | L | open; the one with user-visible downtime, do it last in the phase |
| B9 | Internal → Containers: replace allow-all with one allow per service that a trusted device needs | T1 | 2 | M | open |
| B10 | Tighten: shrink the main LAN DHCP pool; DNS enforcement on IoT; optional: servers to the server VLAN (its own plan, since it re-IPs NFS and the container policies) | T1 | 2 | L | open |

## Phase C: servers

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| C1 | NAS firewall: DSM, SMB and NFS from trusted and VPN only; auto-block on | T2 | owner | M | open |
| C2 | NAS data protection: scheduled snapshots of the data shares, a quarterly scrub, an off-site backup; then a test restore of one share | T4 | owner | L | open; today one bad delete has no undo |
| C3 | App VM: disable rpcbind (listening on all interfaces, not needed for NFSv4) | T1 | 1 | S | proposed 2026-10-26, pending |
| C4 | NFS export restricted to the app VM, root squashed (`sec=sys` trusts client-asserted UIDs) | T1, T3 | 2 | S | open |
| C5 | App VM inventory account: a read-only Docker API proxy and a user with neither `docker` nor `sudo`, replacing the current root-equivalent account | T5 | 3 | M | open |
| C6 | Containers: pin images by digest; bring the exited monitoring container back; fix or drop the allow rule that points at its unassigned IP | T3 | 2 / owner | M | open |
| C7 | The app VM's management NIC has a global IPv6 address: confirm inbound v6 is blocked (it is by the default rule) and decide whether servers need SLAAC at all | T2 | 2 | S | open |
| C8 | Synology MCP: run from the hash lock, fixed working directory, TLS verification on (an admin password is sent with verification off) | T5, T6 | 3 | S | proposed 2026-10-26, pending |
| C9 | UniFi MCP: run from the hash-locked environment instead of re-resolving on every start | T5 | 3 | S | proposed 2026-10-26, pending |

## Phase D: detect and sustain

| ID | Item | Threat | Tier | Effort | Status |
|---|---|---|---|---|---|
| D1 | Drift detection: a nightly read of the gateway config through the read connection, diffed against the last approved state, with a diff written somewhere the Sunday review sees | T5, T6 | 0 | L | not started (CLAUDE.md phase 2) |
| D2 | Quarterly gateway test restore into a throwaway controller; date recorded in the backup manifest | T4 | owner | M | open |
| D3 | Alerts for what failed silently this month: a switch offline, a container exited, gateway memory above a threshold | T1, T3 | 0 | M | open |
| D4 | Review dates: exceptions and rubrics on 2027-01-29; read-only token rotation (automated, one approval) | T5 | 3 | S | scheduled |

## Parking lot: governance ideas with no backlog item yet

Reviewed monthly. Built only when an item above needs it.

- Broker / MCP proxy on a separate host, policy engine, tier-1 auto-approval ([jit-design.md](jit-design.md)). Needs: the agent making changes on a schedule. Not yet
- Category-scoped change windows (proposed 2026-10-26). Needs: the flag-flipping window mode, which the write connections replaced
- A `SessionStart` warning for passed review-by dates. Needs: a review date to pass
- Server-side denylist CI with other contributors. Needs: other contributors
- A `changes.md` check that blocks the write until each "check first" step is ticked. Strategy principle 6 covers it as a rule; automate it after it's been followed by hand for a few changes

## Friction log

One line per time a control got in the way. Reviewed monthly with the parking lot; fix the rule only when a line repeats.

| Date | What got in the way | What was done instead |
|---|---|---|
| 2026-10-28 | A task list showed a rollback as done while the second write still waited for approval; the prompt looked like a read and was denied | One step per write call |
| 2026-10-29 | Every session start prompted 1Password up to four times | Read connections on a read-only token; write connections behind the write gate |
| 2026-10-29 | New worktrees didn't inherit the project's MCP config, then did | Config moved to repo scope |

## Couldn't verify

- Current state of any item. Statuses come from the repo's docs and the 2026-10-21 audit; the first Sunday review starts with a fresh read.
- Whether A6's outside session finished the re-adopt.
- The effort estimates. They're guesses until a few items have been done at this pace.
