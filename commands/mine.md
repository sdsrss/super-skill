---
description: Mine captured sessions for recurring task families that could become skills, and offer to draft candidates.
---

Run `super-skill mine` via Bash and interpret the output for the user.

- If the CLI is not found, tell them to install it: `uv tool install super-skill-cli` (or `pipx install super-skill-cli`).
- If families are surfaced, explain the top few (a family = a task pattern recurring across ≥3 distinct sessions) and ask whether to scaffold candidates with `super-skill candidate draft`.
- If nothing recurs yet, report the distinct-session count and note that capture must be wired (`super-skill hooks-config`, or the plugin's hooks) so sessions accumulate.
- Do NOT approve or promote anything automatically — drafting and approval are separate, human-reviewed steps (`/super-skill:candidates`).
