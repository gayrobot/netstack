# Vetting: sirkirby/unifi-mcp (UniFi Network MCP)

**Reviewed:** 2026-10-26 (initial scan, then provenance, gate and lock follow-up the same day)
**Verdict:** **OK with conditions.** Run it read-only by default, use category-scoped write windows, and install from the hash lock (Findings 3, 5, 6).

## What's installed

| Piece | Source | Pin |
|---|---|---|
| Claude Code plugin `unifi-network` 1.1.5 | marketplace `sirkirby/unifi-mcp` (GitHub) | git commit `e269b2b823a39bfcb38bae833c33b5cf3a666779` |
| MCP server | PyPI `unifi-network-mcp`, launched with `uvx` | `==0.38.3` |
| Security-relevant libraries | PyPI `unifi-mcp-shared`, `unifi-core` | **range only** (`<0.7,>=0.6.33`, `<0.5,>=0.4.72`) |
| Hash lock (this repo) | [`locks/unifi-network-mcp-0.38.3.txt`](locks/unifi-network-mcp-0.38.3.txt) | 56 packages, every one hash-pinned |

The plugin was installed on 2026-10-15, before this review, so this review is retroactive.

## Provenance (artifact → source → build)

| Package | Trusted Publishing attestation | Wheel vs. tagged source |
|---|---|---|
| `unifi-network-mcp` 0.38.3 | `sirkirby/unifi-mcp` / `release-network.yml` | 39/40 files identical; only the generated `_version.py` differs (tag `network/v0.38.3`) |
| `unifi-mcp-shared` 0.6.35 | `sirkirby/unifi-mcp` / `release-shared.yml` | 36/37 identical, only `_version.py` (tag `shared/v0.6.35`) |
| `unifi-core` 0.4.76 | `sirkirby/unifi-mcp` / `release-core.yml` | 154/155 identical, only `_version.py` (tag `core/v0.4.76`) |

Each downloaded wheel matched PyPI's sha256, and the locally installed files matched each wheel's `RECORD` (246 files). That gives an unbroken chain: **installed files = PyPI wheel = tagged source, built by the project's own GitHub workflow.** It doesn't rule out a malicious commit by a maintainer or a compromised maintainer account; that would need a review of the commits themselves.

## Permission gate (read end to end)

`unifi_core/policy_gate.py` (207 lines) and `unifi_mcp_shared/permissioned_tool.py` (255 lines):

- **Enforced at call time, not by hiding tools.** Every tool that declares a `permission_action` is wrapped, and the gate is checked on each call. A disabled tool stays visible but returns a denial.
- **Registration fails closed.** A tool that declares no permission must be annotated `readOnlyHint=True`, or the server refuses to register it. All 204 tools follow this: 98 are read-only, 106 declare create/update/delete. An AST scan of the 98 read-only tools found no calls that look like writes.
- **Default-allow when unset.** If none of the `UNIFI_POLICY_*` variables is set, writes are **allowed**. The plugin always passes the server-level variables, and an empty or unrecognized value is treated as denied, so the plugin path fails closed. A manual install without those variables doesn't.
- **The most specific variable wins:** `UNIFI_POLICY_NETWORK_<CATEGORY>_<ACTION>` overrides `UNIFI_POLICY_NETWORK_<ACTION>`, which overrides `UNIFI_POLICY_<ACTION>`. A category-level variable inherited from the environment would override the server-wide off switch. None are set on this machine (checked 2026-10-26).
- **"Confirm" mode isn't a human.** It makes a mutating tool return a preview unless it's called with `confirm=true`, and the *model* supplies that argument. Human approval depends on the agent client's own tool-permission prompts.

## Findings

1. **Mutations were enabled.** `policy_create` and `policy_update` were `true`. **Fixed 2026-10-26:** all three policies are off by default, and writes go through change windows ([change-control.md](../change-control.md)).
2. **Account scope.** The MCP's gateway account should be a **View Only** Network role, with writes going through a separate account during windows. Not done yet.
3. **The version pin doesn't lock the code that runs.** `uvx unifi-network-mcp==0.38.3` re-resolves the shared libraries on each run. The local cache holds three versions of `unifi-mcp-shared` and two of `unifi-core` for the same pin, and the permission gate lives in those libraries. **Mitigation built:** a hash lock, tested to reject tampered hashes. Switching the plugin to it is proposed in [changes.md](../changes.md).
4. **Plugin hook.** A `SessionStart` hook runs `scripts/claude-session-check.sh`. I read it in full: it only checks `.claude/settings.local.json` for old keys and prints a notice. OK.
5. **"Delete off" doesn't cover what the plugin's docs say.** The option text says delete covers tools that "delete, block, reboot or revoke". In code, `block_client`, `reboot_device`, `upgrade_device`, `power_cycle_port`, `toggle_device` and `forget_client` (which *permanently deletes* a client record) are all **`update`**. So a change window that enables update also enables reboots, firmware upgrades and client deletion. **Condition:** scope windows by category, for example `UNIFI_POLICY_NETWORK_PORT_FORWARDS_UPDATE=true` with the server-wide update left off. Proposed in changes.md.
6. **Human confirmation isn't guaranteed by the MCP.** See "Confirm mode" above. With an agent client in an auto-approve mode, the policy flags and the change window are the only hard controls. **Condition:** keep policies off outside windows. Consider an `ask` rule for the MCP's execute/batch tools during windows.

## Other checks

- **Outbound hosts:** only the configured controller, a `192.168.1.1` default, and GitHub links in docs. No telemetry endpoints.
- **Process execution:** `subprocess` only in `unifi_mcp_shared/bootstrap.py`, which runs the operator's `password_command` / `api_key_command` as an argv list with no shell.
- **Size:** about 230 Python files across the three packages. The gate and bootstrap code were read in full; the rest was a targeted scan, not a line-by-line read.

## Hash lock

```
uv venv <dir> --python 3.13
VIRTUAL_ENV=<dir> uv pip install --require-hashes --no-deps --no-build -r docs/vetting/locks/unifi-network-mcp-0.38.3.txt
```

- `--no-build` matters. The lock lists both wheel and sdist hashes, so without it, a tampered wheel hash can fall back to building from the sdist.
- Tested 2026-10-26: the real lock installs cleanly. With every hash for `unifi-network-mcp` altered, the install fails with `Hash mismatch`.
- Only the three `unifi-*` packages were vetted. The other 53 are frozen at the versions resolved today but not reviewed.

## Not yet done

- Switch the running server from `uvx` to the locked environment (proposed)
- Category-scoped change windows (proposed)
- Review the release workflows (`release-*.yml`) and recent commit history for anything unusual
- Gateway account role split (Finding 2)
