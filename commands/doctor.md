---
description: Check super-skill registry integrity (hashes, active pointers, host sync) and offer to repair drift.
---

Run `super-skill doctor` via Bash (read-only) and report findings.

- If the CLI is not found, tell them to install it: `uv tool install super-skill-cli` (or `pipx install super-skill-cli`).
- If it exits clean (OK), say so.
- If it reports errors (hash mismatch, dangling pointer, host drift), explain each. Offer `super-skill doctor --fix`, which restores git-recoverable versions and re-materializes host drift, then re-verifies — but call out that a dangling active pointer or a name mismatch is left for the user to resolve by hand.
- Only run `--fix` after the user agrees.
