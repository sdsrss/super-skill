# Task: fix the release gate's exit-code semantics

`scripts/sync_versions.py <version> <manifest-dir>` repairs every `*.json`
manifest in a directory to the given version. Our release pipeline gates on
its exit code — but the script exits 0 even when a manifest could not be
repaired and is still broken, so broken releases sail through.

Fix the exit-code semantics: exit 0 only when, after repair, every manifest
actually carries the requested version; otherwise exit non-zero. Keep the
CLI interface unchanged. Work inside this directory.
