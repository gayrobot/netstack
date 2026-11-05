# Network

**Source:** read-only UniFi API queries through the MCP, 2026-10-26. The controller has 93 firewall policies; 7 are user-defined. Specific hosts and rules are in `private/network.md`.

## Networks

| Network | VLAN | Subnet | Zone | IPv6 | Role |
|---|---|---|---|---|---|
| Main LAN | untagged | 10.0.0.0/23 | Internal | prefix delegation + SLAAC (global addresses) | Gateway, VM host, app VM's management NIC, NAS, home automation, clients |
| Container VLAN | 2 | 10.0.2.0/24 | **Containers** (custom) | none | App containers on macvlan, static IPs |
| Server VLAN | 3 | 10.0.3.0/24 | Internal | none | Meant for internal DNS resolvers; nothing answered there on 2026-10-31 |
| Remote-user VPN | – | 192.168.2.0/24 | Vpn | – | Teleport, for the owner's own devices. The read account can't see it |
| WAN 1 / WAN 2 | – | – | External | WAN 2 delegates the v6 prefix | |

## Containers zone

| From → To | Effect |
|---|---|
| Internal → Containers | Allow, broader than needed; narrowing it is backlog B9 |
| Containers → Internal | Block, with a few narrow exceptions and return traffic |
| Containers → External | Allow (egress) |
| External / Vpn / Hotspot / Dmz → Containers | Block |

## Inbound from the internet

- External → Internal blocks everything new, IPv4 and IPv6, apart from the port forwards below. There are no custom IPv6 allow rules, so hosts with global IPv6 addresses aren't reachable from outside.
- External → Gateway allows only WireGuard and IPv6 neighbor discovery/RA/DHCPv6.
- **No inbound port forwards are enabled.** The last two, to the NAS, were disabled 2026-11-05 (backlog A1 part 2; they stay in the controller as disabled rules, so rollback is a toggle). Background: [strategy.md](strategy.md) (R1) and [changes.md](changes.md).

## Findings

1. **Inbound exposure to the NAS: closed 2026-11-05.** Tried and rolled back 2026-10-28, then done with a proper check ([changes.md](changes.md), backlog A1).
2. **Internal → Containers is broader than needed.** Narrowing it to per-service allows is backlog B9.
3. A monitoring allow rule points at a container IP that's currently unassigned (container stopped).
4. The server VLAN's DHCP hands out DNS resolvers on that same VLAN, and nothing answers at them (read 2026-10-31; backlog B4). The container VLAN did the same until 2026-10-31, when it moved to its own gateway as a stopgap (backlog A2, see [changes.md](changes.md)).
5. An old per-client egress allow rule looks like it predates the VPN setup.

## Couldn't verify

- The listener state of the NAS service the old forwards served. The read account can't see it (DSM error 105); the owner checks in DSM
- Whether the server VLAN has any clients. The controller shows none online on 2026-10-31
- WLAN-to-network mapping
- Rule ordering between user and predefined policies (needs API key plus session)
- Site-wide mDNS / multicast settings
