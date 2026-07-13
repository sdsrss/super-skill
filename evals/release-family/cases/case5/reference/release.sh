#!/usr/bin/env bash
set -euo pipefail

VERSION="$1"

python -m pytest -q
git tag "v${VERSION}"
git push origin main
git push origin "v${VERSION}"
gh release create "v${VERSION}" --title "v${VERSION}" --generate-notes
