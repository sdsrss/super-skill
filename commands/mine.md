---
description: Mine captured sessions for recurring task families that could become skills, and offer to draft candidates.
---

Run `super-skill mine` via Bash and interpret the output for the user.

- If the CLI is not found, tell them to install it: `uv tool install super-skill-cli` (or `pipx install super-skill-cli`).
- If families are surfaced, explain the top few (a family = a task pattern recurring across ≥3 distinct sessions) and ask whether to scaffold candidates with `super-skill candidate draft`.
- If nothing recurs yet, report the distinct-session count and note that capture must be wired (`super-skill hooks-config`, or the plugin's hooks) so sessions accumulate.
- The final `events on disk:` line (stderr) reports the raw-event WAL footprint. If it counts day(s) beyond the TTL, offer to reclaim the space and, if the user accepts, run `super-skill prune --apply` for them (it only deletes event days older than the TTL; the registry, candidates, and mined output are unaffected). If the WAL is large but all days are within the TTL, mention the size and that `super-skill prune --days N --apply` (or `SUPER_SKILL_EVENT_TTL`) shortens the window — but do not run that variant unprompted.
- Do NOT approve or promote anything automatically — drafting and approval are separate, human-reviewed steps (`/super-skill:candidates`).
