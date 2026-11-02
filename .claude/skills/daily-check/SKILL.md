---
name: daily-check
description: The daily scope check for netstack. Reads what changed in the documents that define the project's scope since the last check, checks the leading candidates against live state through the read connections, and recommends the one backlog item to work on next. Use once a day, when a session starts with the "hasn't run today" notice, or when the owner asks "what's next".
---

# Daily scope check

Read-only. This check recommends; it doesn't start the work, write to a device or open a PR. The Sunday review in `docs/strategy.md` still picks the week's items. The daily check keeps that pick current between Sundays.

## Steps

1. **Collect.** Run `scripts/daily-check.sh report`. It fetches `origin/main` and lists the commits that touched the scope documents since the last check, the files they touched, and the open backlog rows.
2. **Read what changed.** For each scope commit in the report, read the diff (`git show <sha> -- <file>`), not just the subject line. Read `docs/backlog.md` on `origin/main` in full, including "Owner calls that shape the backlog" and the friction log. Say in two or three lines what the changes did to the project's scope: a new phase, an item closed or put on hold, a new owner call, a rule change.
3. **Filter the candidates.** Drop every open item that:
   - is on hold or blocked (its status says so, or it depends on an open item);
   - another session already owns (its status says so);
   - goes against an owner call (physical security, the arcade gateways, a control whose benefit needs a segment that doesn't exist yet, "notify and click" patching);
   - is governance that no posture item needs now (strategy principle 2).
4. **Check live state** for the top two or three candidates, through the read connections only (rule 5). An item whose status is already true is done: say so, and don't recommend it. Note anything the tools can't do that the item needs, such as a setting the MCP can only read, because that changes who does the step. Never turn a write connection on for this check.
5. **Recommend one item.** In backlog order unless a scope change says otherwise. Give:
   - the ID and one line on what it is;
   - why it beats the next candidate, in a sentence;
   - the evidence from step 4;
   - its tier and who does each step (agent, or owner for tier 3 and UI-only steps);
   - what the session for it starts with (normally the `changes.md` entry with its checks).

   Then list the runners-up in one line each, and anything that should become a backlog line (don't add it yourself; say so).
6. **Record.** Run `scripts/daily-check.sh done`. The next report starts from here.

## Output

Short, plain text, for a phone notification as much as a terminal:

```
Scope since <date>: <two or three lines>
Next: <ID>: <one line>. <why>. <evidence>. Tier <n>; <who does what>.
Runners-up: <ID> (<reason>), <ID> (<reason>)
Noticed: <anything for the backlog, or "nothing">
```

## Couldn't verify

Name whatever the read connections couldn't show, in one line, after the output. If a read connection was down, say which, and recommend from the docs alone, marked as unverified.
