# Rubric: adopt a third-party MCP or build our own

**Status:** draft, proposed 2026-10-29. **Review by:** 2027-01-29, and whenever a new kind of tool appears (see "Reviewing this rubric").

Use this when the agent needs a capability it doesn't have. Work down the steps; **the first one that works wins.** Each step down means more code we're responsible for, or more authority handed out, so the bar rises at each one.

## The cascade

1. **Use what's already connected.** A vetted connector already does it, ideally on its read connection. Done; nothing new.
2. **Widen a permission, not the toolset.** An existing connector would do it if its account had one more permission. Grant the narrowest permission the device offers (tier 3, owner). Prefer this to new code whenever the device has a fine-grained enough role.
3. **Adopt a third-party MCP**, if one exists and passes [vetting](README.md):
   - provenance traceable to source (Trusted Publishing or a reproducible build)
   - runs from a hash lock
   - its write tools can be denied or prompted per tool
   - actively maintained
4. **Build first-party, gaps only.** Add the tool to an existing first-party server for that device (for example `tools/synology-extras/`), or start one if there's none. Conditions:
   - covers only what steps 1 to 3 can't
   - standard library where possible, so there's nothing extra to lock
   - no host, URL or credential as a tool argument
   - tests that fake the device
   - a vetting doc like any third-party tool
   - an overlap check on every upgrade of the third-party MCP it sits beside ([synology-mcp-upgrades.md](synology-mcp-upgrades.md))
5. **Don't give the agent this capability.** The owner does it by hand, and the agent can prepare the steps. This is the right answer when the action is rare, when the device API is unstable, or when the only route is a shell or a full admin session.

**Never:** fork a third-party MCP to add tools. A fork gives up upstream provenance and means owning the review of the whole package. Use step 4 for the gap instead.

## What every decision records

Put this in the `changes.md` entry that proposes the capability:

- which step it landed on, and why each earlier step didn't work (with "not checked" where it wasn't)
- the account it runs as, and how each tool is gated

## Worked example: Package Center (2026-10-28)

| Step | Result |
|---|---|
| 1. Already connected | No. `mcp-server-synology` 1.8.0 has no package tools; `synology_services` only lists packages, and needs admin to do even that |
| 2. Widen a permission | No. DSM has no non-admin role for Package Center (the read account gets error 105) |
| 3. Adopt third-party | **Not checked.** No search was made for a dedicated DSM package MCP |
| 4. Build gaps-only | Chosen: `synology-extras` with `package_list` and `package_upgrade` |
| 5. Owner by hand | The fallback; this is how SA-26:14 was actually checked |

Step 3 being unchecked is a gap. A search for an existing DSM package MCP belongs in the first review of this rubric.

## Reviewing this rubric

- **When:** by the review-by date above, and when a new type of capability comes up that the steps don't fit well.
- **What:**
  - Are there better options now (for example, a device vendor shipping an official MCP, or the client gaining finer permission controls)?
  - Did any decision since the last review feel forced?
  - Should a step move?
- **Record:** a `changes.md` entry, and a new review-by date here.

## Couldn't verify

- Whether a maintained third-party MCP for DSM Package Center exists (step 3 above was skipped)
