---
description: Import existing ~/.claude/skills into the super-skill registry under version control (read-only on the host).
---

Run `super-skill seed` via Bash and report the result.

- If the CLI is not found, tell them to install it: `uv tool install super-skill-cli` (or `pipx install super-skill-cli`).
- seed is idempotent by content hash and never mutates `~/.claude/skills` — it only brings the current skills under version control (new content becomes a new version).
- Summarize imported / updated / unchanged / skipped counts. After seeding, suggest `/super-skill:status`, `/super-skill:explain <id>`, or `/super-skill:doctor`.
