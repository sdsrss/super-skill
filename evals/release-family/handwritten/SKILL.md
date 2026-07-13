---
name: solo-release-publisher
description: >
  Invoke when a solo developer asks an agent to cut a release of a library or CLI —
  bumping the version, tagging, pushing, publishing to a registry (npm or PyPI), and
  creating a GitHub release. Trigger phrases include "ship it", "cut a release",
  "publish to npm/PyPI", "tag and release", "bump the version", or "make a GitHub
  release". Use it whenever the task is turning committed code into a published,
  versioned artifact. Do NOT invoke for routine commits, opening a normal PR, CI
  config changes, deploying a running service (that is deployment, not package
  release), or pre-release exploratory coding. If no publishable package manifest
  (package.json, pyproject.toml, setup.py) exists, stop and say so instead of guessing.
---

# Solo Release / Publish Workflow

A release is irreversible in practice: published registry versions cannot be
re-published, and pushed tags are seen by everyone. Treat every step as verify-first.

## 0. Preconditions (block the release if any fail)

- Working tree is clean (`git status --porcelain` empty). Never release with
  uncommitted or stashed changes — the published artifact must match a real commit.
- You are on the intended branch (usually `main`/`master`) and it is up to date with
  the remote (`git pull --ff-only`). Releasing from a stale or detached HEAD is a bug.
- The full test suite passes locally right now, and CI on the target commit is green.
  "Tests passed earlier" is not evidence — re-run them.
- The build produces a clean artifact (`npm pack` / `python -m build`). Inspect the
  file list; publishing secrets, `.env`, or local scratch files is a common leak.

## 1. Choose the version (SemVer, deliberately)

- MAJOR for breaking changes, MINOR for backward-compatible features, PATCH for
  fixes. When unsure between two, ASK the user — you cannot un-publish the wrong one.
- The new version MUST be greater than the latest published one. Check the registry
  (`npm view <pkg> version`, `pip index versions <pkg>`) AND existing git tags.
- Keep the version consistent everywhere it appears: manifest (`package.json` /
  `pyproject.toml`), any `__version__`/`version.ts` constant, lockfile, and CHANGELOG.
  A mismatch between the tag and the manifest is a classic released-artifact defect.

## 2. Changelog and metadata

- Update `CHANGELOG.md` with a dated section for the new version before tagging —
  users read it, and it should be part of the tagged commit, not an afterthought.
- Confirm package metadata is publishable: correct `name`, `license`, `repository`
  URL, `description`, entry points (`bin`/`main`/`exports`, `[project.scripts]`), and
  the `files`/`include` allowlist so only intended files ship.

## 3. Commit, tag, push (order matters)

1. Commit the version bump + changelog together: `chore(release): vX.Y.Z`.
2. Create an **annotated** tag matching the manifest exactly: `git tag -a vX.Y.Z -m
   "vX.Y.Z"`. Pick one tag convention (`vX.Y.Z` vs `X.Y.Z`) and never mix them.
3. Push the commit, then the tag: `git push && git push origin vX.Y.Z`. Pushing a
   tag often triggers a release CI workflow — know whether it does before you push.
4. A tag is hard to move once others pulled it. If you tagged the wrong commit,
   prefer a new higher version over force-moving a public tag.

## 4. Publish to the registry

- Ensure auth exists (`npm whoami`, or a PyPI API token) before starting; do not
  paste tokens into the shell history or commit them.
- **Do a dry run first**: `npm publish --dry-run`, or build and check with `twine
  check dist/*`. Review the file manifest one last time.
- Publish: `npm publish` (add `--access public` for the first publish of a scoped
  package) or `twine upload dist/*`. For pre-releases use `npm publish --tag next`
  or a PEP 440 pre-release suffix (`1.2.0rc1`) so it is not the default install.
- If a registry token or CI secret is required and missing, stop and ask — do not
  invent credentials or disable auth.

## 5. GitHub release

- Create the release from the exact pushed tag: `gh release create vX.Y.Z --title
  "vX.Y.Z" --notes "<changelog section>"`. Mark pre-releases with `--prerelease`.
- Attach build artifacts only if users consume them directly (binaries, wheels);
  for registry packages the registry is the source of truth.

## 6. Post-publish verification (do not skip)

- Confirm the version is live: `npm view <pkg> version` shows the new number, or the
  PyPI/GitHub release page renders. Publishing can silently no-op or race with CI.
- Install the published artifact fresh in a clean environment and smoke-test it
  (`npx <pkg>@X.Y.Z --version`, or `pip install <pkg>==X.Y.Z` then run it). The
  package that installs from the registry can differ from your local build.
- Report the published version, the tag, the registry URL, and the release URL.

## Hard rules

- Never `npm publish` / `twine upload` from a dirty tree or a failing test run.
- Never reuse or force-overwrite an already-published version number — bump instead.
- Never commit or log registry tokens, and never disable auth/cert checks to "make
  publish work".
- Keep tag, manifest version, and changelog in lockstep; a mismatch is a failed release.
- If any precondition is unmet or a version choice is ambiguous, stop and ask rather
  than publishing something irreversible.
