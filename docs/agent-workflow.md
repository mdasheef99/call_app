# Agent workflow

Reusable loop for every work item in this repo. Details live in
`AGENTS.md` (rules) and `docs/HANDOFF.md` (status); this file defines
only the sequence.

1. **Define outcome.** One checkable result, stated before any edit.
2. **Inspect context.** Read the files the change touches; verify tool and
   branch state first.
3. **Implement a small change.** Smallest diff that achieves the outcome;
   stay inside the authorized scope.
4. **Verify actual behavior.** Run the change (tests, app, device), not a
   proxy. Record commands and results.
5. **Independent review.** A fresh session gets the same requirements plus
   the actual diff, without the implementer's verdict. See
   `docs/prompts/review.md`.
6. **Correct confirmed findings.** Fix what the reviewer proved; dispute
   with evidence, not opinion.
7. **Integrate within authorization.** Commit, branch, and push only as
   approved. Never force-push, never touch `main` without approval.
8. **Update handoff.** Record state, evidence, and the next action in
   `docs/HANDOFF.md`.

Prompt templates: `docs/prompts/implementation.md` (steps 1-4, 6-8),
`docs/prompts/review.md` (step 5). Upstream inspiration:
`docs/prompts/SOURCES.md`.
