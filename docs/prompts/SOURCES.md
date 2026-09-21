# Sources

Upstream inspiration for `docs/agent-workflow.md` and the prompt templates:
the pstack plugin in `cursor/plugins`
(https://github.com/cursor/plugins/tree/main/pstack).

- Upstream commit recorded: `6ed0f7a9504f577d7529064103cecce9be7dfc5e`
  (full SHA resolved via `git ls-remote` HEAD on 2026-09-21; the short
  `6ed0f7a` prefix in the earlier draft means this same commit. Pin all
  reads below to the full SHA, since `main` keeps moving.)
- All six orchestrator paths confirmed present at that commit via per-path
  GitHub API reads (verified 2026-09-21, not inferred from search):
  `pstack/skills/poteto-mode/SKILL.md` (playbook router plus
  prove-it-works verification posture; read in full),
  `pstack/skills/poteto-mode/playbooks/feature.md`,
  `pstack/skills/poteto-mode/playbooks/bug-fix.md`,
  `pstack/skills/interrogate/references/reviewer-prompt.md`
  (reviewer template: severity, finding, evidence, suggestion, output shape),
  `pstack/skills/interrogate/references/lead-judgment.md`
  (lead-judgment framework: filter, contextualize, decide),
  `pstack/skills/principle-prove-it-works/SKILL.md` (verification).
  Permanent links pin the commit, e.g.
  https://github.com/cursor/plugins/blob/6ed0f7a9504f577d7529064103cecce9be7dfc5e/pstack/skills/poteto-mode/SKILL.md
- Correction note: the first draft wrongly reported the reviewer, judgment,
  and verification files as not found. The error was mine: I searched the
  playbooks, references, skills, and automations listings but never the
  `interrogate/` and `principle-prove-it-works/` skill directories. The
  per-path check above corrects the record; the workflow itself is
  unchanged.
- License: MIT, Copyright (c) 2026 Lauren Tan. The workflow documents here
  are original adaptations, not copies, so no upstream text is reproduced.
