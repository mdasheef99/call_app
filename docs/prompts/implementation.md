# Implementation prompt template

Copy, fill the brackets, paste into the implementation session
(normally the existing session).

- **Session destination:** [existing session / new session and why]
- **Outcome:** [one checkable result]
- **Relevant context:** [files to read first, branch, prior HANDOFF notes;
  rules in `AGENTS.md`, status in `docs/HANDOFF.md`]
- **Scope and authority:** [allowed edits; explicit bans for this task;
  what needs approval: push, migrations, spending, config changes]
- **Task-specific workflow:** [ordered steps for this task, each ending in
  a check]
- **Acceptance checks:** [exact commands and expected results]
- **Evidence:** [report commands run with actual output; mark untested work
  UNTESTED per `AGENTS.md` reporting requirements]
- **Handoff:** [update `docs/HANDOFF.md` with state, evidence, next action]

Follow `docs/agent-workflow.md` steps 1-4, then 6-8. Do not perform step 5
yourself; review happens in a separate session via
`docs/prompts/review.md`.
