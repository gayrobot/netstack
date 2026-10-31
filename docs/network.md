# Network

**Source:** read-only UniFi API queries through the MCP, 2026-10-26. The controller has 93 firewall policies; 7 are user-defined. Specific hosts and rules are in `private/network.md`.

## Networks

| Network | VLAN | Subnet | Zone | IPv6 | Role |
|---|---|---|---|---|---|
| Main LAN | untagged | 10.0.0.0/23 | Internal | prefix delegation + SLAAC (global addresses) | Flat: gateway, VM host, app VM's management NIC, NAS, home automation, clients |
| Container VLAN | 2 | 10.0.2.0/24 | **Containers** (custom) | none | App containers on macvlan, static IPs |
| Server VLAN | 3 | 10.0.3.0/24 | Internal | none | Internal DNS resolvers |
| Remote-user VPN | – | 192.168.3.0/24 | Vpn | – | WireGuard |
| WAN 1 / WAN 2 | – | – | External | WAN 2 delegates the v6 prefix | |

## Containers zone

| From → To | Effect |
|---|---|
| Internal → Containers | **Allow all** (user rule, every protocol and port, v4+v6) |
| Containers → Internal | Block, except one home-automation web port, NAS admin HTTPS from one monitoring IP, and return traffic |
| Containers → External | Allow (egress) |
| External / Vpn / Hotspot / Dmz → Containers | Block |

## Inbound from the internet

- External → Internal blocks everything new, IPv4 and IPv6, apart from the port forwards below. There are no custom IPv6 allow rules, so hosts with global IPv6 addresses aren't reachable from outside.
- External → Gateway allows only WireGuard and IPv6 neighbor discovery/RA/DHCPv6.
- **Two WAN port forwards (TCP+UDP, any source) to the NAS**, created around Oct 2024. The owner identified the client on 2026-10-31: they are the inbound peer port of a peer-to-peer download client built into the NAS OS. They reach that one listener, not DSM or the shares. Carried as accepted risk R1 in [strategy.md](strategy.md) until the client moves behind the VPN gateway container (backlog A1).

## Findings

1. **Internet-facing port forwards to the NAS, open to any source.** They looked stale but are in use by a client on the NAS; disabling them was tried and rolled back on 2026-10-28 (see [changes.md](changes.md)). On 2026-10-31 the owner identified the client as the NAS's built-in peer-to-peer download client, so the forwards expose its inbound peer listener only. The owner accepted that as risk R1 ([strategy.md](strategy.md)); the exit is moving the client off the NAS (backlog A1).
2. **Internal → Containers is allow-all.** Every device on the flat main LAN, IoT and phones included, can reach every container's admin UI.
3. A monitoring allow rule points at a container IP that's currently unassigned (container stopped).
4. The container VLAN's DHCP hands out DNS servers that the Containers zone can't reach. The static-IP containers don't care, but a DHCP client there would get no DNS.
5. An old per-client egress allow rule looks like it predates the VPN setup.

## Couldn't verify

- The client's listening-port and peer-discovery settings, and that the forwards map to its peer port only and not its web port. The read account can't see them (DSM error 105); the owner checks in DSM
- Server VLAN clients beyond the DNS resolvers
- WLAN-to-network mapping
- Rule ordering between user and predefined policies (needs API key plus session)
- Site-wide mDNS / multicast settings
