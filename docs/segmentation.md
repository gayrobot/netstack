# Segmentation: smart devices off the main LAN, by MAC, on the same Wi-Fi

**Status:** proposed 2026-11-05, not applied. **Backlog:** replaces the plan in B2, B5, B7 and B8. **Tier:** 2 for creating the networks, zone, policies and mDNS scope (step 1); 1 for moving one client into an existing IoT network or back (owner, 2026-11-05).

## What the owner asked for

1. Smart devices move to their own VLANs **by MAC address**. Nobody re-joins a different SSID: re-pairing dozens of devices isn't going to happen.
2. Two kinds of smart device. A few need the internet to work (the dishwasher, the robot vacuums). Most are controlled through HomeKit and don't.
3. The cameras stay as they are. They're UniFi devices on UniFi's own path.
4. **mDNS and HomeKit must work across the VLANs.** This is a hard requirement, not a nice-to-have.

## The mechanism: Virtual Network Override

UniFi gateways can put a client on a network by its MAC, at the gateway, with no change to the SSID, the passphrase, the switches or the APs. Ubiquiti calls it **Virtual Network Override** (VNO): "MAC-Based VLAN Assignment via Virtual Network Override ... useful for cases such as when WPA3 Enterprise is not supported, or as an alternative to PPSK" ([Creating Virtual Networks](https://help.ui.com/hc/en-us/articles/9761080275607-Creating-Virtual-Networks-VLANs), read 2026-11-05). The gateway is a UDM Pro, which supports it.

Why not the other two ways UniFi offers:

| Option | Same SSID | Same passphrase | Unknown devices | Verdict |
|---|---|---|---|---|
| **Virtual Network Override** | yes | yes | stay on the SSID's network (the main LAN) | **use this** |
| PPSK (one passphrase per VLAN) | yes | **no**, every moved device re-joins with a new passphrase | land wherever their passphrase says | fails requirement 1 |
| RADIUS MAC authentication | yes | yes | **refused**: it's an allowlist, so every new phone, laptop and guest needs a RADIUS entry first | too much friction for a home |

What a move looks like: set the override on the client in the controller, then reconnect the client so it takes a lease in the new subnet. Undoing it is the same two steps. HomeKit finds accessories by mDNS, not by IP, so a new address doesn't break pairing.

One gap: the UniFi MCP has no tool for the override (read 2026-11-05: none of the client, network or switch tools set it). So the override is set by the owner in the UI, from a checklist the agent generates, and the agent verifies each move through the read connections. If moves turn out to be frequent, a tool goes through `docs/vetting/build-or-adopt.md` first.

## The networks

| Network | Zone | Who's on it | Internet | Reaches the LAN |
|---|---|---|---|---|
| Main LAN (unchanged) | Internal | phones, laptops, tablets, **the Apple home hubs**, AirPlay speakers, the arcade gateways, the servers | yes | yes |
| **IoT-Cloud** (new) | **IoT** (new) | devices that only work through the vendor's cloud, such as the dishwasher and the robot vacuums | yes | no |
| **IoT-Local** (new) | **IoT** | HomeKit devices that work locally: smart plugs, the lighting bridge, Wi-Fi lamps; the thermostats if the owner accepts the trade-off below | **no** (DNS and NTP from the gateway only) | no |
| Cameras | Internal (unchanged) | the cameras and the doorbell | unchanged | unchanged |
| Container VLAN, server VLAN | unchanged | unchanged | | |

Classes come from the 2026-11-05 read. The per-device list is in `private/segmentation-devices.md`.

### Who stays on the main LAN, and why

- **The Apple home hubs (HomePods and Apple TVs) stay with the phones.** They are what talks to HomeKit accessories when the phone isn't home, they are the Thread border routers, and they are AirPlay targets. Thread accessories have no Wi-Fi address at all; they reach the house through the hubs, so they move nowhere. Moving the hubs would break AirPlay and Thread for no gain.
- **AirPlay speakers** are targets the phones need on the same network.
- **The cameras and doorbell** (owner, 2026-11-05). B5 is withdrawn.
- **The arcade gateways** (owner call, 2026-11-02).

## The firewall (zone-based policies)

The gateway's zone firewall is stateful, so a reply to a connection the LAN started is always allowed. That's why HomeKit works with IoT → Internal blocked: the hubs, phones and home automation open the connection to the accessory, and the accessory's events come back on that same connection.

| # | From → To | Rule |
|---|---|---|
| 1 | Internal → IoT | allow (phones, hubs and home automation control the devices) |
| 2 | IoT → Internal | block new connections; replies allowed. Exceptions only per integration (see "Callbacks" below) |
| 3 | IoT → Gateway | allow DHCP, DNS, NTP and mDNS (UDP 67, 53, 123, 5353); block the rest, including the gateway's admin UI |
| 4 | IoT-Cloud → External | allow |
| 5 | IoT-Local → External | **block** (source = the IoT-Local network), except a daily 03:00–04:00 window for firmware updates (decision 1) |
| 6 | IoT → Containers, Vpn, Hotspot | block |
| 7 | IoT-Cloud ↔ IoT-Local | block (routed traffic between the two) |

Both new networks get IPS (as A3 did for the existing three), no IPv6 (no prefix delegation, so nothing gets a global address that the IPv4 policies don't cover), and no UPnP.

**Callbacks.** A few integrations have the device start a connection back to the controller instead of replying on the controller's connection. One known case: a home-automation integration for one brand of Wi-Fi lamp sends a query to the lamp and the lamp answers to a different UDP port on the home-automation host. Rule 2 drops that. Each such integration gets one narrow allow (that source network, the home-automation host, that port), written up in `changes.md`. Which integrations need one isn't known from here; the pilot shows it.

## mDNS: what makes HomeKit work across VLANs

The gateway's mDNS proxy has three modes: Auto (common services across every VLAN), Off, and Custom (chosen services across chosen networks) ([mDNS Proxy](https://help.ui.com/hc/en-us/articles/12648701398807-UniFi-Gateway-Multicast-DNS-mDNS-Proxy), read 2026-11-05). This design uses **Custom**:

- **Networks:** main LAN, IoT-Cloud, IoT-Local. Not the container, server or guest networks.
- **Services:** HomeKit accessory protocol (`_hap._tcp`), plus the lighting bridge's own service if its app needs local discovery. Nothing else. AirPlay, printers and screen sharing don't need to cross, because their devices all stay on the main LAN.

This is A4, done where it belongs (owner's call, 2026-11-02).

### The trap: Matter and IPv6

Matter devices (and HomeKit over IPv6) talk over IPv6 link-local and the hubs' private (ULA) prefix. The read on 2026-11-05 shows the hubs advertising that prefix on the main LAN, and other devices taking addresses from it. Neither crosses a VLAN boundary: the mDNS proxy would announce the device, and the hub couldn't reach it. So **a Wi-Fi Matter device stays on the main LAN** until the IoT networks get routed IPv6, which is its own decision. The owner checks each HomeKit Wi-Fi device in the Home app (accessory settings show a "Matter" section if it is one) before it's moved.

## The update trade-off (decided 2026-11-05: option 1)

IoT-Local has no internet, so its devices **can't update their own firmware**. That conflicts with the owner's call that everything updates itself (2026-11-02). Three ways out:

1. **A daily update window (recommended).** Rule 5 gets a schedule: IoT-Local reaches the internet from 03:00 to 04:00, the same window the gateway, switches and NAS update in. No human clicks anything. Whether each device checks for updates inside that hour can't be known in advance; the agent watches firmware versions afterwards and flags a device whose firmware hasn't moved in 90 days.
2. **No internet, no updates.** Simplest and tightest. The plugs and lamps on IoT-Local rarely get updates anyway, and a device that can't reach its vendor can't be told to do anything by it either.
3. **Everything that wants updates goes to IoT-Cloud.** Then IoT-Local is nearly empty and the split is mostly theatre.

The thermostats and the lighting bridge are the devices where this matters most: they get real firmware updates, and their vendors' apps (remote access, schedules, weather) stop working without internet even though HomeKit keeps working. **Owner, 2026-11-05: option 1, and the thermostats and the lighting bridge go to IoT-Local.** Their vendor apps lose remote access; HomeKit keeps working, and the daily window keeps their firmware current.

## Rollout

Step 1 is tier 2: its own `changes.md` entry, chat approval and change window. Steps 2–4 are single-client moves, tier 1 (owner, 2026-11-05): the owner approves each call and each move is logged in `changes.md` afterwards, with no change window. The tier covers moving one client between the main LAN and an IoT network that already exists, nothing else; a new network, zone, policy or mDNS change is still tier 2. Nothing in step 2 or later starts until the step before has been verified.

| Step | What | Who | Verified when |
|---|---|---|---|
| 0 | This design; the owner answers the decisions below | agent, owner | merged |
| 1 | Create IoT-Cloud and IoT-Local, the IoT zone, policies 1–7, mDNS Custom, IPS on both. **No clients moved** | agent (write connection, tier 2) | read connection shows both networks, the zone and every policy; nothing changed for any client |
| 2 | Pilot: one arcade-cabinet plug to IoT-Local, one robot vacuum to IoT-Cloud | owner sets the override; agent reconnects the client and verifies | the plug shows up in IoT-Local in UniFi **and** HomeKit reports it reachable (read through the home-automation plugin), and the owner toggles it from a phone on the main LAN and from cellular; the vacuum's app works from cellular; no new blocked flows from either after 48 hours except the expected internet blocks from the plug |
| 3 | The rest of IoT-Cloud, one sitting | owner + agent | each client in IoT-Cloud; each app works from cellular |
| 4 | The rest of IoT-Local, plugs and lamps first, the lighting bridge last (it carries ~50 accessories) | owner + agent | every moved accessory reachable in HomeKit; home-automation integrations updated for any that were pinned to an IP |
| 5 | Narrow rule 1 from "allow all" to the hubs, the phones' network and the home-automation host, once a week of flows shows what's used | agent | |

**Rollback** for any device: clear its override and reconnect it. It's back on the main LAN with its old behaviour. Rollback for step 1: disable the two networks (no clients are on them yet).

**What the agent checks after every move**, through the read connections only: the client's network in UniFi; the accessory's `reachable` state in HomeKit; blocked flows from that client in the gateway's flow log. A move isn't done until all three are right.

## How this keeps working after rollout

A new device joins the house Wi-Fi and lands on the main LAN, like today. That is the one weakness of VNO: segmentation is opt-in per device. The daily check (and later the observer, O2) closes it: a client the controller hasn't seen before gets classified from what the read connections show (vendor prefix, hostname, the controller's device fingerprint, whether a matching accessory appeared in HomeKit, what it talks to) and the agent proposes "IoT-Local", "IoT-Cloud" or "stays". A client nobody can name is proposed for IoT-Cloud, as decision 3 did. The owner sets the override from the proposal, a tier-1 move.

## Decisions for the owner

1. **Updates on IoT-Local:** decided 2026-11-05, the daily 03:00–04:00 window.
2. **Thermostats and the lighting bridge:** decided 2026-11-05, IoT-Local.
3. **Clients the agent couldn't identify:** decided 2026-11-05. The owner named two, and they join their classes. The two nobody could name go to **IoT-Cloud as containment**: they keep their internet, so whatever they do keeps working, but they lose the LAN. A device that misbehaves after the move identifies itself. Details in `private/segmentation-devices.md`.
4. **Tier for a single-client move:** decided 2026-11-05, tier 1. A change to these controls, so the owner's call (tier 3); recorded in CLAUDE.md rules 1 and 5 and in [change-control.md](change-control.md).

## Couldn't verify

- That VNO behaves the same for a wired client (the lighting bridge) as for a wireless one. Ubiquiti's article says it's done at the gateway with no switch configuration; the pilot doesn't cover a wired device, so the bridge goes last and alone.
- The site's current mDNS mode. The read connection can't see it (the MCP doesn't expose the site-level setting).
- Which accessories are Matter, and which home-automation integrations use device-initiated callbacks.
- Which devices need the internet for anything beyond their vendor app. There's no per-device traffic record to answer it from yet; blocked flows after step 2 are the first evidence.
- Whether IoT-Local devices check for firmware updates inside a one-hour window.
- The match between some HomeKit accessories and Wi-Fi clients (details in `private/`).
