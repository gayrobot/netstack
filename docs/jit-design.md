# Just-in-time access for the agent: design

**Status:** design only. What exists today is step 1 of this (see "Where we are"). The rest gets built when the agent automation needs it, not before (see "When to build each piece").

## Goal

The agent does more and more of the network work on its own, and it can do that safely because:

1. it holds **no standing write access** to any device,
2. write access is **granted per change, scoped and self-expiring**, by something the agent can't control, and
3. every grant and every call is **logged**, so autonomy can grow on evidence rather than trust.

## Where we are

| Today | Limitation |
|---|---|
| `change-window.sh` flips MCP policy flags in a settings file | Same machine as the agent, same credentials; the agent could edit the file |
| Approval happens in chat, and `open` requires a matching `changes.md` entry | Every change needs a human, even trivial ones |
| Restore-point gate before any window | Good as it is; becomes a broker policy |
| Client-side deny rules (proposed for the NAS MCP) | Only cover one client; the agent can go around them with a shell |
| Agent accounts with admin roles (NAS) or unknown roles (gateway) | The real boundary is missing |

## Target design

```
agent ──► grant request {change: <changes.md title>, target, tools, args, ttl}
              │
              ▼
          approver ── policy engine for tier 1 · human for tier 2 · refuse for tier 3
              │  grant {id, tools, arg constraints, expires_at}
              ▼
          MCP proxy / broker   (separate host; the only holder of device admin credentials)
              │  every call: match an active grant → forward + log, else refuse + log
              ▼
          gateway / NAS   (agent's own accounts: read-only)
```

### Components

- **Read accounts:** View Only on the gateway and non-admin on the NAS, used for all standing access. Permanent.
- **Broker:** a small service on a host the agent has no shell on. It holds write credentials and a grant table, enforces TTLs with its own clock, and refuses anything not covered by a grant. It works as an MCP proxy, so any agent client goes through it.
- **Approver:** starts as you in chat (the broker sends a request and you approve). Moves to policy-as-code for tier 1.
- **Policies:** preconditions for a grant, such as a fresh restore point, a `changes.md` entry, the target being inside the allowed category, and no other grant already open on the same object.
- **Audit:** grant requested, granted, used and expired, each with the change title, in an append-only log on the broker, cross-checked against device logs.
- **Break glass:** your own admin accounts, used by hand and never given to the agent.

### Risk tiers

| Tier | Examples | Approval | Grant |
|---|---|---|---|
| 0 | inventory, health, drift detection | none (standing read) | – |
| 1 | toggle a port forward, rename a client, DHCP reservation | **policy** (fresh restore point + logged entry) | minutes, single object |
| 2 | firewall policy, VLAN, WAN, VPN, NAS share permissions | human | short, single change |
| 3 | create or alter admins, authentication, backups, snapshots, the broker itself | **never through the agent** | – |

Actions move from tier 2 to tier 1 only when the log shows a track record for that action: N successful changes, zero rollbacks.

### Credential vending vs. proxy

- **Vending:** the broker enables a scoped write account on the device and hands the agent a short-lived credential. Simpler to build, but the credential reaches the agent's machine, and UniFi has no native account expiry.
- **Proxy (chosen):** credentials never leave the broker. Revoking access is just a grant expiring. It also gives per-call logging and argument checks for free.

## When to build each piece

Build controls when the automation that needs them exists. Until then, cheap stopgaps are enough.

| Piece | Build when | Stopgap until then |
|---|---|---|
| Read-only agent accounts | **now**; the risk exists today | – |
| Client deny rules for ungated write tools | **now**; ten minutes | – |
| Broker / proxy | the agent makes changes on a schedule or without you watching | `change-window.sh` + chat approval |
| Policy engine and tier 1 auto-approval | there's a log of repeated, boring tier 2 changes worth automating | chat approval |
| Server-side denylist CI | other people contribute | local hooks + push protection |

## Mapping from today's pieces

- `changes.md` entries become grant requests.
- `change-window.sh open` checks (title exists, restore point) become broker policies.
- `change-windows.log` becomes the broker's audit log.
- MCP policy flags stay as defense in depth inside the servers.
- Deny rules get removed once the proxy is the only route.
