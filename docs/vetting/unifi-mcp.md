# Vetting: sirkirby/unifi-mcp (UniFi Network MCP)

**Reviewed:** 2026-10-26
**Verdict:** OK for Phase 1 **once mutations are disabled** (see Findings 1 and 2)

## What's installed

| Piece | Source | Pin |
|---|---|---|
| Claude Code plugin `unifi-network` 1.1.5 | marketplace `sirkirby/unifi-mcp` (GitHub) | git commit `e269b2b823a39bfcb38bae833c33b5cf3a666779` |
| MCP server | PyPI `unifi-network-mcp`, launched with `uvx` | `==0.38.3` |
| Transitive deps | PyPI `unifi-mcp-shared`, `unifi-core` | **range only** (`<0.7,>=0.6.33`, `<0.5,>=0.4.72`) |

The plugin was installed on 2026-10-15, before this review. Doing the install first and the vetting after is the opposite of the plan, so this is a retroactive review.

## Findings

1. **Mutations are enabled.** In the plugin options, `policy_create = true` and `policy_update = true`. `policy_delete` is unset, so it defaults to off. The confirm prompt (`permission_mode` defaults to `confirm`) is the only remaining guard. Proposed fix: [changes.md](../changes.md).
2. **Account scope unknown.** The MCP logs in as a dedicated local UDM account. Since create and update are enabled, that role probably allows writes. For Phase 1 it should be a **View Only** Network role. Check what role it has in the UniFi OS console.
3. **The top-level version pin doesn't lock the code that runs.** `uvx unifi-network-mcp==0.38.3` re-resolves the shared libraries each time. The local uv cache has six environments for the same 0.38.3 pin, and they contain three versions of `unifi-mcp-shared` (0.6.33, 0.6.34, 0.6.35) and two of `unifi-core` (0.4.72, 0.4.76). The permission gate itself (`unifi_mcp_shared/permissioned_tool.py`, `unifi_core/policy_gate.py`) lives in those floating packages. Fix: run from a locked environment (`uv tool install` with `--constraint`, or a pinned `requirements.txt` with hashes) instead of `uvx`.
4. **Plugin hook.** A `SessionStart` hook runs `scripts/claude-session-check.sh`. I read it in full. It only checks `.claude/settings.local.json` for old `UNIFI_*` keys and prints a notice. It makes no network calls and writes nothing. OK.

## What I checked in the source (0.38.3 + shared 0.6.35 + core 0.4.76)

- **Integrity:** recomputed all 246 file hashes against each wheel's `RECORD`, and every one matched. This proves the installed files are what PyPI shipped. It doesn't prove that what PyPI shipped matches the GitHub commit.
- **Outbound hosts:** the only hardcoded URLs are the configured controller host, a `192.168.1.1` default, and GitHub links in docs. I found no telemetry or analytics endpoints.
- **Process execution:** `subprocess` is used only in `unifi_mcp_shared/bootstrap.py`, to run the operator's `password_command` / `api_key_command` as an argv list with no shell. That's expected.
- **Size:** about 218 Python files and about 65k lines. This was a targeted scan, not a line-by-line read.

## Not yet done

- Diff the PyPI wheel against the GitHub tag for 0.38.3 (checks that the published build is reproducible)
- Read `policy_gate.py` and `permissioned_tool.py` end to end to confirm that disabling the policies actually blocks those tools, rather than only hiding them
- Generate a lockfile with hashes and switch the plugin to it
