# Exceptions to the project rules

**Status:** draft, proposed 2026-10-29. **Review by:** 2027-01-29 (see "Reviewing").

The rules in `CLAUDE.md` are defaults. When one doesn't fit, use the cascade below. **The first step that works wins.** The cascade is built to push back toward the rules. If the same rule keeps needing exceptions, the rule is wrong and should change, rather than collecting exceptions.

Same shape as the [build-or-adopt rubric](vetting/build-or-adopt.md).

## The cascade

1. **Is it really an exception?** Read what the rule is protecting. If the action already meets that intent, it isn't an exception. Note why in `changes.md` and go ahead.
2. **Do it within the rule,** even if that's slower. Use the write connection with its prompt, a change window, or have the owner do it.
3. **Narrow it until the rule fits:** a smaller account, a narrower tool or a smaller scope, so the rule applies as written. This is usually [build-or-adopt](vetting/build-or-adopt.md) step 2 or 4.
4. **Change the rule** if this case will come up again, or if this rule already has an exception listed below. Changing the rule is a PR that edits `CLAUDE.md` (tier 3: the owner approves it).
5. **Grant an exception** with compensating controls: something that covers what the rule protected, such as a prompt, a test, a pin, or a fixed tool list. It needs:
   - the owner's approval in chat
   - a row in the register below, with a review-by date (default: 90 days)
   - a `changes.md` entry
6. **Otherwise, don't.** The owner does it by hand, or it doesn't happen.

Granting, renewing or ending an exception is a change to "these controls", so it's tier 3. The agent proposes it and the owner decides.

## Register

| ID | Rule | Scope | Why | Compensating controls | Approved | Review by |
|---|---|---|---|---|---|---|
| EX-1 | 5: reads only on read connections, without prompts only there | `synology-extras` read-only tools (today: `package_list`) run on the NAS admin login with an `allow` rule, only while `write-gate` has `synology-extras` on | DSM has no non-admin role that can list packages (error 105); prompting a read-only list was judged not worth the friction | the agent never sees the password; the tool list is fixed in code and changes only through a reviewed PR; anything that changes the NAS stays `ask`; off by default behind write-gate, so the tools exist only after the agent turns them on for one session; `CHECKED_AGAINST` test on upgrades of the Synology MCP | owner, in chat, 2026-10-28 | 2027-01-29 |

At review, each row is renewed (with a new date), ended, or replaced by a rule change.

## Reviewing

- **Each row, by its review-by date:** is it still needed? Has a better option appeared, such as a narrower DSM role or an upstream tool? Did the compensating controls hold?
- **The cascade itself, by the date at the top:** did any exception get through too easily, or did a sensible action get stuck? Are better practices available now?
- **Signal to act sooner:** a second exception to the same rule (go to step 4).
- **Record:** a `changes.md` entry for every review, and the new dates here.

Nothing reminds anyone of these dates yet. One option is a warning in the existing `SessionStart` hook when a review-by date has passed. That would be a change to the controls, so it's proposed, not built.

## Couldn't verify

- That 90 days is the right default review period. It's a starting point, and the first review should revisit it
