---
description: Review pending super-skill candidates and walk through approving or rejecting them.
---

Help the user review skill candidates mined from their sessions.

1. Run `super-skill candidate list` via Bash. If the CLI is missing, tell them to install it (`uv tool install super-skill-cli`).
2. For each pending candidate the user wants to look at, run `super-skill candidate show <id>` — this prints the draft SKILL.md, the instruction-gate findings, and the eval-lite result.
3. A draft is a human-editable TODO-stub; coarse mining names a recurring family, it does not author the procedure. Encourage the user to edit the draft into a real reusable skill before approving.
4. `super-skill candidate approve <id>` runs three blocking checks (instruction-layer adversarial scan, unedited-template-placeholder check, deterministic eval-lite) and only then promotes: registers an immutable version and materializes it to the host skills directory. `super-skill candidate reject <id>` marks it rejected without promoting (there is no `--reason` flag on reject).
5. Never approve on the user's behalf without explicit confirmation — approval writes to their live skills directory.
