# Security strategy

**Status:** proposed 2026-10-29. **Review:** every Sunday (30 minutes, see "Rhythm"); the whole document by 2027-01-29.

This is the document the rest of the repo serves. It says what we're protecting, from what, in what order, and how the work moves. The ordered list of work is [backlog.md](backlog.md).

## Goal

A compromised phone or IoT device, an exploited internet-facing service, a bad container image, a mistaken change or a ransomware run on the NAS doesn't give anyone the NAS data, the gateway, or the home-automation system, and nothing is lost that can't be restored from a verified copy.

## Where we are, honestly

| | State on 2026-10-29 |
|---|---|
| Governance | **Strong.** In four days (2026-10-26 to 29) eleven PRs built the read/write split, per-call approval, the restore-point gate, nightly encrypted off-box gateway backups, vetting, hash locks, exceptions and build-or-adopt rubrics, token rotation and the write gate. The controls were tested with a real approved write, a denied write and a refused read-connection write |
| Posture | **Almost unchanged since the 2026-10-21 audit.** The flat main LAN still carries IoT devices, cameras, phones and the servers together. The NAS still has two internet-facing port forwards open to any source. The one network change attempted (closing them) was rolled back because a check step was skipped. Nothing else on the audit's list has been applied |
| Work pattern | Reactive. A friction point appears (1Password prompts, a security advisory, a switch that dropped off), a session fixes it, and the fix becomes a control or a tool. Each fix was good. The sum is a governance system with nothing to govern yet, and the owner's time going to the tooling instead of the network |

The imbalance is the problem this document fixes. Governance isn't wrong; it's ahead of the work it exists for.

## What we're protecting, from what

**Assets, most valuable first:** the NAS data (irreplaceable); the gateway's config and control (owning it owns everything); the app VM and its containers (they hold service credentials and a VPN session); the home-automation system (locks, cameras, physical effects); the family's own devices and traffic; the agent's credentials.

**Threats, most likely first.** The order sets the backlog's order.

| # | Threat | Why it's likely | Today's exposure |
|---|---|---|---|
| T1 | A phone, TV, speaker or IoT device on the LAN is compromised and moves sideways | Dozens of IoT devices, most never patched, share one network with the servers | **High.** One flat LAN; Internal → Containers is allow-all; every container admin UI is reachable from every device in the house |
| T2 | An internet-facing service on the NAS is exploited | The two forwards reach one process: the inbound peer listener of a peer-to-peer download client built into the NAS OS (identified by the owner 2026-10-31). It parses unauthenticated connections from any source, is closed source, and is patched only when the vendor ships that package. No public exploit of that listener is known. DSM itself and the shares aren't reachable through the forwards | **Medium likelihood, high impact.** The client runs on the NAS, on the flat LAN, so a flaw in it lands on the most valuable host. Carried as accepted risk R1 below until backlog A1 moves the client off the NAS |
| T3 | A container image or dependency is malicious or vulnerable | Images are pinned by tag only; containers auto-restart and have open egress | **Medium.** The Containers zone limits what they reach inside; egress and tag-pinning are open |
| T4 | Ransomware or an accidental delete on the NAS | No undo exists for the data shares today | **High.** Snapshots cover only the gateway-backup share; no data-share snapshots, no off-site copy, no scrub schedule |
| T5 | The agent makes a wrong or injected change | Reads untrusted data (device names, SSIDs, docs) with write tools present | **Low.** This is the best-covered threat: read/write split, per-call approval, restore-point gate, change log |
| T6 | A leaked or stolen credential (laptop, cloud account, VPN peer) | Normal | **Medium.** 1Password holds the agent's credentials; UniFi cloud account MFA, VPN peer list and NAS default accounts are unreviewed |

Out of scope: targeted nation-state attack, physical break-in, the ISP.

### Accepted risks

Risks the owner has looked at and chosen to carry for now, with what would end the acceptance. Each row has a review-by date; at review it's renewed, ended by its exit, or re-rated. Accepting a risk is the owner's call (tier 3): the agent writes the row, the owner accepts it by merging.

| ID | What is accepted | Why | What would end it | Accepted | Review by |
|---|---|---|---|---|---|
| R1 | The two WAN port forwards to the NAS stay open to any source. They reach only the inbound peer listener of the NAS's built-in peer-to-peer download client, not DSM or the shares. A flaw in that listener would run code on the NAS, on the flat LAN, with write access to the download share. The NAS's public IP is also visible to every peer it exchanges data with | The owner wants peers to be able to connect inbound. Closing the forwards keeps downloads working but makes the NAS unreachable to peers. A proxy in front of the ports would change which address receives the packets, not which code parses them, so it doesn't reduce this risk | Moving the client into the app VM behind the VPN gateway container, with the VPN provider's port forwarding carrying inbound peers through the tunnel (backlog A1). Then both forwards close and the home IP leaves the peer lists | owner, in chat, 2026-10-31; confirmed by merging the PR that added this row | 2027-01-29 |

## Principles

1. **Posture first.** The backlog is the work. Governance exists so the backlog can move safely, and is judged by how much backlog it lets through.
2. **Governance is pull, not push.** A control, tool or rubric gets built when a backlog item needs it, or after a real incident. "This would be nice" goes to the parking lot in [backlog.md](backlog.md), and the parking lot is reviewed monthly, not acted on as it fills.
3. **Segment before you harden.** VLANs and zones remove the most risk per hour and make most other items smaller. They come right after the quick wins.
4. **Biggest risk per hour first.** Order by threat (T1 to T6) and effort, not by what's interesting or what just broke.
5. **One item, one session, one PR.** A session is named after a backlog ID and ends when its PR merges. A second thing that comes up inside a session becomes a backlog line, not a detour. (This is what "we're using git wrong" was: sessions that drift, branches that outlive their PR, worktrees nobody closes.)
6. **Check first, and the check blocks the write.** Every proposal lists the checks that have to pass before the write. A skipped check means no write, unless the owner waives it in chat. This is the lesson of the 2026-10-28 rollback, made a rule.
7. **The owner doing it by hand is progress.** Tier 3 items get a checklist from the agent and the owner does them in the UI. That's a backlog item closed, not a governance gap.
8. **Verified beats inferred.** An item is done when the read connection shows the new state and the `changes.md` entry says so.

## Rhythm

**Weekly, Sunday, 30 minutes.** Open [backlog.md](backlog.md). Mark what got done. Pick one to three items for the week, in order. Archive every session whose PR merged. Close every worktree whose branch merged. Add any friction lines to the parking lot. Nothing else.

**Per item.** Start a session named after the backlog ID. The session: reads current state through the read connections; writes the proposal in `changes.md` with its checks; stops for approval; applies through the write connection (or hands the owner a checklist for tier 3); verifies through the read connection; logs; opens the PR; stops. Anything it notices on the way becomes a backlog line.

**Monthly.** One session for the parking lot: which governance items now have a backlog item that needs them? Build those. Drop the rest or leave them parked.

**Stop signs.** Any of these means stop and come back to this document:
- a governance PR that no backlog item needs
- a third session open on the same subject
- a write applied with a check skipped
- a week with no backlog item closed

## Phases

Dates assume one to three items a week. They're a pace, not a promise.

| Phase | Window | What | Done when |
|---|---|---|---|
| A. Quick wins | now to mid-November 2026 | Items that are one toggle, one setting or one owner checklist and need no segmentation: the NAS port forwards, broken DNS on the container VLAN, threat management on every network, mDNS scope, the travel router, the unknown-state switch, VPN peers, admin accounts and MFA, NAS default accounts | T2 and T6 drop to low; nothing on the quick-wins list is open |
| B. Segmentation | mid-November to end of December 2026 | IoT, camera and guest networks and zones; a trusted Wi-Fi network for phones and laptops; the existing Wi-Fi network becomes IoT-only; the home-automation VM gets a leg on the IoT network; Internal → Containers becomes per-service allows | T1 drops to low; a phone on the IoT or guest network can't reach a server or a container admin UI |
| C. Servers | January to mid-February 2027 | NAS: firewall, data-share snapshots, off-site backup, scrub schedule, share clean-up. App VM: rpcbind off, NFS export restricted, read-only Docker access for inventory, images pinned by digest, the monitoring container back | T3 and T4 drop to low; a test restore of a data share succeeds |
| D. Detect and sustain | from February 2027, ongoing | Drift detection (CLAUDE.md phase 2), a quarterly gateway test restore, alerts for the things that failed silently this month (a switch offline, a container exited, gateway memory), the review dates in the rubrics | A change made outside the agent shows up as a diff within a day |

## Couldn't verify

- The current state of the network. This document was written from the repo's docs (read 2026-10-26) and the 2026-10-21 audit; no new read was made. The first weekly review should start with a fresh read and correct the backlog.
- That the 2026-10-21 Wi-Fi findings (one network for everything, WPA2/WPA3 transition, management-frame protection optional) still hold.
- Whether the owner's cloud account and the VPN peers were reviewed outside the agent since the audit.
- The device counts in the audit (about 29 IoT devices, 5 cameras, 57 clients online). They're from 2026-10-21.
