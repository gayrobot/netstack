# App VM

**Inventoried:** 2026-10-26, read-only, no sudo. Container names, images and IPs are in `private/hosts/`.

## Host

| | |
|---|---|
| Runs on | VM host, UTM (QEMU q35), x86-64 |
| OS | Ubuntu 26.04 LTS |
| Docker | 29.9, AppArmor + seccomp default profiles |
| Compose | one project, versioned in git, `.env` mode 600 |
| NICs | management NIC on the main LAN (DHCP + SLAAC); second NIC is the macvlan parent for the container VLAN |
| Storage | bulk data over NFSv4.1 from the NAS |

## How containers are exposed

- **No container publishes a port.** Nine containers sit on the container VLAN through macvlan, each with its own static IP; one shares the VPN gateway container's network namespace.
- Reachability is therefore set entirely by the UDM's Containers zone (see [network.md](../network.md)), not by Docker or the VM firewall.
- None are privileged. One has `CAP_NET_ADMIN` (the VPN gateway). All use `restart: unless-stopped`. Images are pinned by tag, not by digest.
- One container (monitoring) has been exited with an error for 3 days.

## VM listeners

| Port | Bind | Service | Flag |
|---|---|---|---|
| 22/tcp | `0.0.0.0`, `[::]` | sshd | LAN-only in practice (External → Internal blocks inbound v6) |
| 53, 323 | localhost | resolved, chronyd | local only |

## Findings

1. Service hardening on the VM is proposed (backlog C3, C4).
2. The inventory account is broader than it needs to be (backlog C5).
3. Images are pinned by tag only (backlog C6).

## Couldn't verify

- ufw / iptables and socket owners (needs sudo)
- Per-container listening ports
- Whether running containers match the committed compose file (that check prints secrets)
- The NAS export rules
