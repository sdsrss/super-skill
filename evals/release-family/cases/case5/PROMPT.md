# Task: fix the release script's ordering

`release.sh` automates our release, but its steps run in an order that has
burned us before: it tags before the suite is green, and it creates the
GitHub release before the branch and the tag are pushed, so the release
points at refs the remote doesn't have yet.

Reorder the five steps so that, strictly:

1. the test suite runs first;
2. the tag is created only after tests pass;
3. both pushes (branch and tag) happen after tagging;
4. `gh release create` runs last, after both pushes.

Keep all five steps; change only their order. Work inside this directory.
