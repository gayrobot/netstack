# VM host

**Role:** always-on Mac Pro running UTM VMs. It runs no containers itself. Specifics are in `private/hosts/`.

| | |
|---|---|
| Model | Mac Pro, late 2013 (`MacPro6,1`), x86_64 |
| macOS | 15.7 |
| Container runtime | none on the host |
| Remote Login (SSH) | off |
| Screen Sharing / ARD | on, `*:3283` |
| VMs | app VM (Ubuntu, containers), home-automation OS VM |
| Network | two wired NICs on the main LAN; one carries a macOS VLAN interface for the container VLAN |

Current Docker Desktop doesn't support this model, and since the containers already run in a Linux VM, no host runtime (Colima etc.) is needed.

## Couldn't verify

- Root and system listeners (`lsof` ran without sudo)
- UTM network mode for each VM
