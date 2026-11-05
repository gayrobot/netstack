# Vetting: HomeClaw (HomeKit MCP plugin)

**Reviewed:** 2026-11-05, read-only, using the [checklist](README.md). Backlog A12.
**Verdict:** **OK with conditions.** The plugin itself is a thin, readable socket client with no network, shell or file access of its own. The risk is the authority it hands over: with no filter set, the agent can unlock doors, create automations that fire unattended, and point an event feed at any URL. Nothing in the plugin gates those calls. The conditions below put the gate where it can hold.

This one was installed on 2026-10-18, before any review, so this review is retroactive. Home-automation syncs and automations are plane 3 ([spec.md](../spec.md)), not this repo's concern. What's reviewed here is the agent's access to them.

## Identity and provenance

| | |
|---|---|
| Upstream | `omarshahine/HomeClaw` on GitHub, MIT license, created 2026-02-24, 190 stars, 3 open issues, last push 2026-11-03 |
| Maintainer | one author; no published security advisories |
| What gets installed | the Claude Code plugin from the author's own marketplace repo (user scope, 2026-10-18), pinned by the install to commit `28fc9a0`, version 1.0.13. The plugin runs `node mcp-server/dist/server.js` |
| What the plugin talks to | a separate macOS app, **HomeClaw.app**, over a local Unix socket. The app holds the HomeKit access; the plugin holds none |
| The app | installed from the Mac App Store (Apple-signed, signature verifies, Gatekeeper accepts). It is version 1.0.14, one ahead of the plugin's 1.0.13 |
| Installed files vs. install record | all **425 of 425** files match the install manifest's hashes. The manifest was written by the installer, so this shows nothing changed since install, not that the files match the published source |
| Published artifact vs. source | **not checked.** The plugin has no release attestation (no Sigstore, no Trusted Publishing); it is a git checkout. The shipped `dist/server.js` is a 16,794-line esbuild bundle of the 89-line `server.js`, the `lib/` handlers and the MCP SDK; it was not rebuilt and diffed |
| App binary vs. source | **not checked.** The app's source is in the repo; the App Store binary can't be compared to it |

## Dependencies

- One runtime dependency, `@modelcontextprotocol/sdk` (range `^1.31.0`), plus `esbuild` for the build. A `package-lock.json` is committed and `undici` is overridden to an exact version.
- The SDK is **bundled into `dist/server.js`**, so what runs is whatever was resolved when the author built it. There's nothing to install at run time and nothing for us to hash-lock. The pin is the plugin commit.
- Hash-locked requirements file and tamper test: not applicable to a prebuilt bundle. Pinning the plugin to a commit stands in for it.

## Behavior

- **Network:** the plugin's own code (`server.js`, `lib/handlers/homekit.js`, `lib/socket-client.js`, `lib/freshness.js`) makes no outbound calls. A search of it for URLs, `fetch`, `spawn`, `exec`, `child_process`, environment reads and file writes finds none. Its only I/O is the local socket (App Store build: a socket in the app's group container; otherwise `/tmp`), with a 30 s timeout. The bundled SDK contains HTTP transport code that the entry point doesn't use. **Not checked line by line.**
- **What the app does on the network:** the one outbound feature is the webhook (below). The app's own network use, telemetry and update checks were not checked; `docs/privacy.md` in the repo describes them and wasn't read in full.
- **Hooks and startup scripts:** the plugin declares none. Its manifest declares only the one stdio server. The repo ships Claude skills and commands for iOS development under its own `.claude/`; they aren't part of the plugin and don't load here.
- **Credentials:** the plugin has none and stores none. The webhook bearer token is set through the `homekit_webhook` tool, so the model would see it in the call, and it would appear in the session transcript.
- **Event log:** the app keeps a local event log of every characteristic change (50 MB, 3 backups, enabled). It records what happens in the house, so it is as sensitive as the home itself.

## Authority

The server exposes ten tools. From the code and schemas, not the docs:

| Tool | Read | Create / update | Delete |
|---|---|---|---|
| `homekit_status`, `_rooms`, `_device_map`, `_events` | yes | | |
| `homekit_accessories` | list, get, search | **`control`: set any characteristic, including lock target state (unlock), garage, alarm, thermostat** | |
| `homekit_scenes` | list, get | `trigger` (runs a scene) | |
| `homekit_automations` | list, get | `create`, `create_time`, `add_condition`, `enable`, `disable`: automations that **fire unattended**, on any sensor, button or time | `delete` |
| `homekit_manage` | list_groups | rename, assign rooms, create or rename rooms, zones, groups | `remove_accessory`, `remove_room`, `remove_zone`, `delete_group` |
| `homekit_config` | get | **`set`: change the active home, the filter mode and the allowlist** | |
| `homekit_webhook` | status, test | **`setup`: URL and bearer token; the app then pushes HomeKit events to that URL** | |

- **How its own controls are enforced:** the plugin enforces nothing. There is no call-time permission check, no read-only mode, no confirmation field, and no tool-level deny. Many `homekit_manage` and automation calls accept `dry_run`, but that is a flag the model passes, not a human check. The **only** gate is the Claude client's own per-tool prompt. No allow or deny rule for these tools is set in the user settings, so each call prompts today.
- **The accessory filter is the one control with teeth, and it is off.** The app's `allowlist` mode hides accessories from the plugin entirely. Live read 2026-11-05 through the tool: filter mode is **`all`**, and every accessory the home has is visible to the agent, locks and cameras included. A stored allowlist exists but isn't applied. The agent can also change this setting itself (`homekit_config set`), so the filter only holds if the client prompt on that call does.
- **Confirmation:** the prompt in the client is a human. Nothing in the plugin adds to it.
- **The account it runs as:** the HomeKit access of the Apple account signed in on the host the app runs on. HomeKit has no lower role for the app: it acts as the home's owner or an admin member.
- **Webhook:** disabled and unconfigured today (live read 2026-11-05: no URL, 0 delivered). Turning it on lets an agent, or anything that steers one, send the house's event stream, including door and motion events, to any URL. The README's own setup prompt points it at a local gateway only.

## Verdict

**OK with conditions.** The code that loads into the agent is small and clean, and its source and install are consistent. It is acceptable only while these hold:

1. **(Not met; risk accepted by the owner 2026-11-05, strategy.md R2.)** The app's settings screen doesn't let the owner change the filter, so it stays on `all`. **Set the filter to `allowlist` and leave out every lock, garage, alarm and camera.** The owner does this in the HomeClaw app (Settings, Devices), tier 3. Until it's done, the agent can unlock a door with one approved prompt. The agent doesn't change this setting.
2. **Gate the risky tools in the client.** Keep a prompt on `homekit_accessories` (control), `homekit_manage`, `homekit_automations`, `homekit_config` and `homekit_webhook`. Never allow-list them. Reads (`status`, `rooms`, `device_map`, `events`, and the list, get and search actions) may run without a prompt. Because the client's rules are per tool, not per action, the combined tools mean this is all or nothing; if reads need to be free, a deny on the writes isn't possible without losing control. The owner chooses.
3. **Keep the webhook off.** Enabling it is a new change with a `changes.md` entry, and the URL is a loopback or LAN host the owner names.
4. **Don't auto-update.** Re-vet on any change to the plugin commit; the app updates itself through the App Store and a new app version is a new review of the socket commands. See [README.md](README.md) rule 3.
5. **Treat the event log as sensitive.** It stays on the host that runs the app and is never copied into the repo or a chat.

## Not done

- Rebuild `dist/server.js` from the tagged source with the committed lockfile and diff it against the shipped bundle.
- Read the HomeClaw app's socket command set and its network behavior (telemetry, updates, `docs/privacy.md`). The plugin's authority is bounded by it.
- Whether Claude's per-tool prompt can be made per-action instead of per-tool, which would allow free reads and gated writes.
- The home-automation hub (Home Assistant) is a separate connector and isn't covered here.
- What the app does when two clients use the socket at once.

## Couldn't verify

- Anything about the published artifact's origin: the plugin has no attestation, so provenance rests on the git commit and the author's repository.
- Whether the App Store binary matches the source in the repo.
- Which accessories are locks, cameras or garage, since the exact inventory stays in `private/`. The allowlist condition needs that list.

## Addendum 2026-11-05 (owner)

The owner reports that Apple's Home asks for authentication on the phone when an automation touches a lock. If so, the unattended-automation risk for locks is limited to what the owner confirms. A direct `homekit_accessories control` call is the remaining path, and it is gated only by the client prompt. Reported by the owner; not tested by the agent. Garage and alarm accessories weren't covered by the report.
