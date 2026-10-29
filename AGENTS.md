# Agent instructions

The rules for any agent working in this repo are in [`CLAUDE.md`](CLAUDE.md). Read it in full before doing anything; it applies to every agent, not only Claude.

The short version:
- Read-only by default. Writes happen only inside a change window for one entry in `docs/changes.md` that the owner approved in chat (`docs/change-control.md`).
- Never read `.env`, never SSH into the gateway, never use `git commit --no-verify`.
- Every change goes through a branch and a pull request; never push to `main`.
- Real names go in `private/`; tracked files use role names.
