# Review prompt template

Copy, fill the brackets, paste into a FRESH session with no prior
discussion of this change. The reviewer must not be primed by the
implementer's verdict.

- **Session destination:** fresh session, no implementation history
- **Outcome:** [same checkable result the implementation claimed]
- **Relevant context:** [same requirements the implementer had:
  `AGENTS.md` rules, applicable spec sections, and the ACTUAL diff
  (commit range or files); never the implementer's summary alone]
- **Scope and authority:** [read and run only; no edits, no commits, no
  pushes, no environment changes]
- **Task-specific workflow:** [re-derive correctness from requirements;
  rerun the acceptance checks; probe edge cases the diff touches]
- **Acceptance checks:** [same commands as implementation; all must pass
  independently]
- **Evidence:** [report each finding as confirmed (with command output) or
  dismissed (with reason); no new scope]
- **Handoff:** [return findings to the implementation session; do not edit
  `docs/HANDOFF.md` yourself]

Rule: agreement is not the default. Disagree with evidence when the diff
does not meet the requirements.
