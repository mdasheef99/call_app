# Sources

Upstream inspiration for `docs/agent-workflow.md` and the prompt templates:
the pstack plugin in `cursor/plugins`
(https://github.com/cursor/plugins/tree/main/pstack).

- Upstream commit recorded: `6ed0f7a9504f577d7529064103cecce9be7dfc5e`
  (resolved via `git ls-remote` on 2026-09-21; pin any future reads to it).
- Files actually read at that commit: `pstack/skills/poteto-mode/SKILL.md`
  (playbook router plus prove-it-works verification posture),
  `pstack/skills/poteto-mode/playbooks/feature.md`,
  `pstack/skills/poteto-mode/playbooks/bug-fix.md` ( listings confirmed via
  the GitHub API; SKILL.md read in full).
- License: MIT, Copyright (c) 2026 Lauren Tan. The workflow documents here
  are original adaptations, not copies, so no upstream text is reproduced.

Not found at that commit under the listed locations, and therefore NOT
used as sources: files named `router`, `reviewer-template`,
`lead-judgment`, or `verification`. Closest verified analogues, also not
copied: `pstack/skills/poteto-mode/references/bugbot-triage.md`
(skeptical review posture) and the `create-verification-skill` /
`maintain-verification-skill` skill entries.
