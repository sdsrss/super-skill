"""Repair every *.json manifest in a directory to the requested version."""

import json
import sys
from pathlib import Path


def main(argv):
    if len(argv) != 2:
        print("usage: sync_versions.py <version> <manifest-dir>", file=sys.stderr)
        return 2
    version, root = argv[0], Path(argv[1])
    repaired = 0
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            print(f"cannot repair {path.name}: not valid JSON", file=sys.stderr)
            continue
        data["version"] = version
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        repaired += 1
    # Exit code reflects what REMAINS broken after repair, not what was attempted.
    remaining = 0
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            remaining += 1
            continue
        if data.get("version") != version:
            remaining += 1
    print(f"repaired {repaired} manifest(s), {remaining} still broken")
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
