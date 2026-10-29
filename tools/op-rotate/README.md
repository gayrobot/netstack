# op-rotate

Renews the read-only 1Password service-account token that [op-ro-read](../op-ro-read/README.md) uses, before it expires. Proposed in the 2026-10-29 entry "No 1Password prompts for read connections" in [changes.md](../../docs/changes.md), step 5.

```
op-rotate check                      daily, from launchd: rotates within 14 days of expiry
op-rotate rotate                     rotate now
op-rotate status [--hook]            when it expires; --hook prints only when it needs attention
op-rotate seed <name> <YYYY-MM-DD>   record the current service account and its expiry (install)
op-rotate plist                      print the launchd agent for this install
```

## What a rotation does

1. A macOS notification says a 1Password prompt is coming.
2. `op service-account create <base>-<date> --vault <read-only vault>:read_items --expires-in 90d --raw`. This needs the owner's 1Password sign-in, so 1Password asks once (Touch ID). That's the only thing the owner does.
3. The new token reads one read-only item. If it can't, nothing changes.
4. The token goes into the Keychain item through `security -i` on stdin, so it's never in argv, a log or the terminal. It's read back and compared.
5. The state file gets the new name and expiry, and a notification says it worked and names the old service account, which can be deleted in the 1Password web app (the CLI can't delete service accounts). The old one keeps working until its own expiry, so there's no gap.

Any failure (prompt ignored or denied, new token can't read, Keychain write fails) keeps the current token, sends a notification, records `last_result=failed: ...` and tries again the next day. If the token expires anyway, the read connections fail to start (fail closed); nothing falls back to a broader account.

The agent never runs `check` or `rotate`. The `SessionStart` hook runs `status --hook`, which prints a warning only within 14 days of expiry, after a failed run, or once expired, so the agent can tell the owner.

## Files

- `~/.config/netstack/op-rotate/config` (owner, non-secret, private names): `base_name`, `vault`, `keychain_service`, `verify_ref`, optional `account`, `warn_days` (14), `expires_days` (90)
- `state` (name, expiry, last result), `rotate.log` (no secrets), `rotate-now` (if present, the next `check` rotates; used to test the launchd path once at install)
- `~/Library/LaunchAgents/local.netstack.op-rotate.plist`: daily at 10:00 and at login. launchd runs a missed run when the Mac wakes

Stdlib Python. Offline tests in `test_op_rotate.py` use fake `op`, `security` and notifier, and check the token appears in no argv, log, state or notification (in CI).

## Install (owner, tier 3)

```
install -m 755 tools/op-rotate/op_rotate.py ~/.local/bin/op-rotate
```

Then write the config, `op-rotate seed <current service account> <its expiry>`, and load the agent from `op-rotate plist`. The owner's private install script does all of this.

## Couldn't verify

- That the 1Password app shows its approval prompt for `op` started by launchd rather than a terminal (expected: yes, launchd agents run in the owner's login session). The install test rotation answers this
- How long `op` waits for that prompt before giving up (op-rotate stops waiting at 5 minutes)
- Whether service-account names must be unique (op-rotate adds the time if a name would repeat on the same day)
- Whether 1Password limits how many service accounts an account can have, expired ones included (about four a year are created)
