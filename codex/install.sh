#!/usr/bin/env bash
# Install the super-skill meta-skill into Codex's user-level skills directory.
# Codex has no marketplace; it reads open-standard SKILL.md from ~/.agents/skills.
# Idempotent: safe to re-run (overwrites the one skill file, touches nothing else).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/skills/super-skill"
DEST="${HOME}/.agents/skills/super-skill"

if [ ! -f "${SRC}/SKILL.md" ]; then
  echo "error: ${SRC}/SKILL.md not found (run from the codex/ package dir)" >&2
  exit 1
fi

mkdir -p "${DEST}"
# Copy the whole skill tree: SKILL.md + optional agents/openai.yaml (host extension).
cp -R "${SRC}/." "${DEST}/"
echo "installed super-skill meta-skill -> ${DEST}/ (SKILL.md + agents/openai.yaml)"

if ! command -v super-skill >/dev/null 2>&1; then
  echo "note: the 'super-skill' CLI is not on PATH — install it with:" >&2
  echo "      pipx install super-skill-cli   # or: uv tool install super-skill-cli" >&2
fi
