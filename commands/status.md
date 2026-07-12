---
description: Show the super-skill registry status (skills, versions, events, candidates) and surface any mine reminder.
---

Run `super-skill status` via Bash and report the result to the user.

- If the CLI is not found, tell them to install it: `uv tool install super-skill-cli` (or `pipx install super-skill-cli`), then retry.
- Summarize: how many skills are registered (and active), version count, captured events, and any pending candidates.
- If a `reminder :` line appears (enough distinct sessions unmined), point the user at `/super-skill:mine`.
