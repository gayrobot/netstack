# Security strategy

**Status:** proposed 2026-10-29; re-cut 2026-11-02 against [spec.md](spec.md). **Review:** every Sunday (30 minutes, see "Rhythm"); the whole document by 2027-01-29.

This document says what we're protecting, from what, in what order, and how the work moves. What the system *is* and what it does for the owner is [spec.md](spec.md), which this serves. The ordered list of work is [backlog.md](backlog.md).

## Goal

A compromised phone or IoT device, an exploited internet-facing service, a bad container image, a mistaken change or a ransomware run on the NAS doesn't give anyone the NAS data, the gateway, or the home-automation system, and nothing is lost that can't be restored from a verified copy.

## Where we are, honestly

| | State on 2026-10-29 |
|---|---|
| Governance | **Strong.** In four days (2026-10-26 to 29) eleven PRs built the read/write split, per-call approval, the restore-point gate, nightly encrypted off-box gateway backups, vetting, hash locks, exceptions and build-or-adopt rubrics, token rotation and the write gate. The controls were tested with a real approved write, a denied write and a refused read-connection write |
| Posture | **Largely unchanged when this was written.** Segmentation hadn't started, and the 2026-10-21 audit's findings were the backlog's Phase A and B. The one network change attempted was rolled back because a check step was skipped. Phase A has since closed several items (see [backlog.md](backlog.md)) |
| Work pattern | Reactive. A friction point appears (1Password prompts, a security advisory, a switch that dropped off), a session fixes it, and the fix becomes a control or a tool. Each fix was good. The sum is a governance system with nothing to govern yet, and the owner's time going to the tooling instead of the network |

The imbalance is the problem this document fixes. Governance isn't wrong; it's ahead of the work it exists for.

**Re-cut, 2026-11-02.** The diagnosis above was half right. Governance was ahead of the posture work, but the bigger gap was that the repo governed only the write path (an agent, in a session, changing the network) and never specified the watching layer: inventory, advisories, drift, health, patch state. That's most of what managing a home network is, and none of it ran on its own. [spec.md](spec.md) defines it as the observer, with the write-path controls as the spine it proposes into. The backlog now has an observer phase (O) that runs alongside A and B rather than after them, because it doesn't depend on segmentation. The one thing that does, traffic anomaly detection, still waits for Phase B.

## What we're protecting, from what

**Assets, most valuable first:** the NAS data (irreplaceable); the gateway's config and control (owning it owns everything); the app VM and its containers (they hold service credentials and a VPN session); the home-automation system (anything with a physical effect); the family's own devices and traffic; the agent's credentials.

**Threats, most likely first.** The order sets the backlog's order.

| # | Threat | Why it's likely | Today's exposure |
|---|---|---|---|
| T1 | A phone, TV, speaker or IoT device on the LAN is compromised and moves sideways | Many consumer devices are rarely patched, and the network isn't segmented yet | **High until Phase B.** Segmentation is the backlog's biggest single item |
| T2 | An internet-facing service on the NAS is exploited | One inbound exposure existed on the NAS until 2026-11-05, and a flaw in any internet-facing service lands on the most valuable host | **Reduced 2026-11-05.** The inbound forwards are disabled; see R1 and backlog A1/E1 |
| T3 | A container image or dependency is malicious or vulnerable | Image pinning and egress controls are still to do | **Medium.** The Containers zone limits what they reach inside; the rest is Phase C |
| T4 | Ransomware or an accidental delete on the NAS | Data-share protection is still partial | **High until Phase C.** Snapshots, off-site copy and scrubs are Phase C |
| T5 | The agent makes a wrong or injected change | Reads untrusted data (device names, SSIDs, docs) with write tools present | **Low.** This is the best-covered threat: read/write split, per-call approval, restore-point gate, change log |
| T6 | A leaked or stolen credential (laptop, cloud account, VPN peer) | Normal | **Medium.** 1Password holds the agent's credentials; account and peer reviews were Phase A items (A8 to A10, done 2026-11-02) |

Out of scope: targeted nation-state attack, physical break-in, the ISP. Physical access inside the house is trusted (owner's call, 2026-11-02), so controls aimed at someone plugging a device into a wall or switch port aren't proposed.

### Accepted risks

Risks the owner has looked at and chosen to carry for now, with what would end the acceptance. Each row has a review-by date; at review it's renewed, ended by its exit, or re-rated. Accepting a risk is the owner's call (tier 3): the agent writes the row, the owner accepts it by merging.

| ID | What is accepted | Why | What would end it | Accepted | Review by |
|---|---|---|---|---|---|
| R1 | An inbound internet exposure on the NAS, accepted from 2026-10-31 until it was closed | The owner wanted a service on the NAS to keep working while a safer arrangement was built | Moving that service off the NAS (backlog A1, E1). Details are in `private/` | owner, in chat, 2026-10-31; confirmed by merging the PR that added this row. **Ended 2026-11-05:** the owner had the forwards disabled (backlog A1 part 2), so the NAS is no longer reachable from outside through them | 2027-01-29 |
| R2 | The home-automation plugin's accessory filter is wider than it needs to be, so the agent can see and, with one approved prompt per call, act on more of the house than the task requires. The plugin has no gate of its own; the client's per-call prompt is the only one ([vetting/homeclaw.md](vetting/homeclaw.md)) | The app's settings screen doesn't let the owner narrow the filter reliably, so the owner chose to carry the risk. Apple's Home adds its own confirmation for some actions (reported by the owner, not tested by the agent). A direct control call isn't covered by that. Which accessories are in scope is in `private/` | Narrowing the filter (a fixed app, or another way to set it), reducing what the agent can see, or removing the plugin. Also ended by any case of the agent acting on the house in a way the owner didn't ask for | owner, in chat, 2026-11-05 | 2027-01-29 |

## Principles

1. **Posture first.** The backlog is the work. Governance exists so the backlog can move safely, and is judged by how much backlog it lets through.
2. **Governance is pull, not push.** A control, tool or rubric gets built when a backlog item needs it, or after a real incident. "This would be nice" goes to the parking lot in [backlog.md](backlog.md), and the parking lot is reviewed monthly, not acted on as it fills. The observer is the pull: its collectors and detectors are the work, and the governance it needs (feed vetting, the demotion rule, the patch policy) is listed in [spec.md](spec.md) and built with it, not ahead of it.
3. **Segment before you harden.** VLANs and zones remove the most risk per hour and make most other items smaller. They come right after the quick wins.
4. **Biggest risk per hour first.** Order by threat (T1 to T6) and effort, not by what's interesting or what just broke.
5. **One item, one session, one PR.** A session is named after a backlog ID and ends when its PR merges. A second thing that comes up inside a session becomes a backlog line, not a detour. (This is what "we're using git wrong" was: sessions that drift, branches that outlive their PR, worktrees nobody closes.)
6. **Check first, and the check blocks the write.** Every proposal lists the checks that have to pass before the write. A skipped check means no write, unless the owner waives it in chat. This is the lesson of the 2026-10-28 rollback, made a rule.
7. **The owner doing it by hand is progress.** Tier 3 items get a checklist from the agent and the owner does them in the UI. That's a backlog item closed, not a governance gap.
8. **Verified beats inferred.** An item is done when the read connection shows the new state and the `changes.md` entry says so.

## Rhythm

**Daily, scheduled.** The `daily-check` skill (`.claude/skills/daily-check/`) reads what changed in the scope documents since the last check, checks the leading candidates through the read connections, and recommends one item. It runs every morning as a local scheduled task, and a session that starts before it has run that day says so. It recommends and stops; it doesn't replace the Sunday pick.

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
| A. Quick wins | now to mid-November 2026 | Items that are one toggle, one setting or one owner checklist and need no segmentation: NAS exposure, DNS on the container VLAN, threat management on every network, a switch in an unknown state, VPN peers, admin accounts and MFA, NAS accounts | T2 and T6 drop to low; nothing on the quick-wins list is open |
| B. Segmentation | mid-November to end of December 2026 | IoT, camera and guest networks and zones; a trusted Wi-Fi network for phones and laptops; the existing Wi-Fi network becomes IoT-only; the home-automation VM gets a leg on the IoT network; Internal → Containers becomes per-service allows | T1 drops to low; a phone on the IoT or guest network can't reach a server or a container admin UI |
| C. Servers | January to mid-February 2027 | NAS: firewall, data-share snapshots, off-site backup, scrub schedule, share clean-up. App VM: service lockdown, least-privilege inventory access, images pinned by digest, monitoring restored | T3 and T4 drop to low; a test restore of a data share succeeds |
| O. Observer | from November 2026, alongside A and B | The watching layer in [spec.md](spec.md): the observer container, collectors, drift and health detection, advisory matching, the patch lane, the identity inventory. Replaces the detection half of the old Phase D | The six outcomes in spec.md, checked at the Sunday review |
| D. Sustain | ongoing | A quarterly gateway test restore, the review dates in the rubrics, the traffic-anomaly detector once Phase B is done | A test restore has succeeded in the last quarter; nothing in the rubrics is past review |

## Couldn't verify

- The current state of the network. This document was written from the repo's docs (read 2026-10-26) and the 2026-10-21 audit; no new read was made. The first weekly review should start with a fresh read and correct the backlog.
- That the 2026-10-21 Wi-Fi findings still hold.
- Whether the owner's cloud account and the VPN peers were reviewed outside the agent since the audit.
- The device counts in the audit. They're from 2026-10-21 and stay in `private/`.
