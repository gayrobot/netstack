# op-ro-read

Reads a password for a **read connection** with a read-only 1Password service-account token, so the connection starts without a 1Password prompt. Proposed in the 2026-10-29 entry "No 1Password prompts for read connections" in [changes.md](../../docs/changes.md).

```
op-ro-read <keychain-service> <op://vault/item/field>
```

- Loads the token from the login Keychain item `<keychain-service>` (account: the current user), exports it as `OP_SERVICE_ACCOUNT_TOKEN` and runs `op read`. The token is never printed.
- The service account can only read the read-only vault, so this can't reach the write accounts' passwords even if it's pointed at them. Checked 2026-10-29: both write items are refused.
- Write connections keep plain `op read` with the owner's sign-in and its prompt.
- Real vault, item and Keychain names go in the client config and `private/`, never here.

## Install (owner, tier 3)

```
install -m 755 tools/op-ro-read/op-ro-read ~/.local/bin/op-ro-read
```

Copy rather than symlink, so the installed file doesn't change when a branch does. The UniFi MCP warns if the helper is writable by others.

## Couldn't verify

- Whether `op read` with a service-account token ever falls back to the desktop app prompt (expected: no, a token in the environment takes precedence)
- Behaviour after the token expires, beyond `op` returning an error (the read connection should then fail to start)
