# Vetting: MCP servers, plugins and skills

Anything an agent loads can act with the agent's access. Nothing gets installed or connected here until it has a review in this folder, and every review answers the same questions.

## Rule

1. **Vet before install.** Install only after the review is written and its verdict is OK.
2. **Pin what runs.** Use an exact version and, for packages, a hash-locked requirements file (`locks/`), installed with `--require-hashes --no-build`.
3. **Re-vet on change.** A version bump, a new dependency resolution or a new permission means a new review, or a dated addendum to the existing one. How upgrades run: [third-party-upgrades.md](third-party-upgrades.md).
4. **Least privilege first.** Every review ends with the narrowest account and settings the tool can run with.

## Checklist

Copy this into `docs/vetting/<name>.md` and fill in every line. Write "not checked" rather than leaving a line out.

**Identity and provenance**
- [ ] Source repo, maintainer, license, release cadence, open security issues
- [ ] Exactly what gets installed (plugin, package, container image, skill files) and from where
- [ ] Published artifact traced to source: Trusted Publishing / Sigstore attestation, or a reproducible-build diff of the artifact against the tagged source
- [ ] Installed files match the published artifact (RECORD hashes, image digest)

**Dependencies**
- [ ] Direct dependencies and how they're pinned (exact, range, unpinned)
- [ ] The same provenance check for any dependency that holds security logic
- [ ] Hash-locked requirements file generated and tested, including a tamper test

**Behavior**
- [ ] Outbound network destinations (hardcoded URLs, telemetry)
- [ ] Process execution, shell use, file writes outside its own directory
- [ ] Hooks or startup scripts that run automatically (read every one in full)
- [ ] Credential handling: where secrets come from, whether they can show up in logs or argv

**Authority**
- [ ] Every action it can take, grouped read / create / update / delete, as the **code** declares them, not as the docs describe them
- [ ] How its own permission controls are enforced (call-time check or hidden from the tool list; default-allow or default-deny; what overrides what)
- [ ] Whether "confirmation" means a human or just the model passing a flag
- [ ] The account it runs as on the target system, and the lowest role that works

**Verdict**
- [ ] OK / OK with conditions / Not OK, with the conditions listed
- [ ] Not-done list

## Reviews

| Tool | Version | Verdict | Review |
|---|---|---|---|
| UniFi Network MCP (sirkirby/unifi-mcp) | plugin 1.1.5, PyPI 0.38.3 | OK with conditions | [unifi-mcp.md](unifi-mcp.md) |
| Synology MCP (atom2ueki/mcp-server-synology) | 1.8.0 | **Not OK as configured** (admin account, 43 ungated write tools) | [synology-mcp.md](synology-mcp.md) |
| synology-extras (first-party, `tools/synology-extras/`) | 0.1.0 | OK with conditions (not registered yet) | [synology-extras.md](synology-extras.md) |
| HomeClaw plugin | 1.0.13 | **Not vetted** (already installed) | pending |
