#!/usr/bin/env bash
set -euo pipefail

VERSION="$1"

git tag "v${VERSION}"
gh release create "v${VERSION}" --title "v${VERSION}" --generate-notes
python -m pytest -q
git push origin main
git push origin "v${VERSION}"
