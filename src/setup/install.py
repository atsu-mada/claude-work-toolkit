"""Write the status line settings of code-survey-kit into a Claude Code settings file.

Plugins cannot set the parent status line, so this script adds:
  statusLine          -> scripts/usage/statusline.py   (refreshes every N seconds)
  subagentStatusLine  -> scripts/usage/subagent_statusline.py
The log hooks come with the plugin itself (hooks/hooks.json).

Usage:
  python3 src/setup/install.py                       # ~/.claude/settings.json
  python3 src/setup/install.py --target <file>       # another settings file
  python3 src/setup/install.py --dry-run             # show the change only
  python3 src/setup/install.py --uninstall           # remove the two entries

An existing statusLine that is not ours is kept unless --force is given.
A backup <target>.bak-<timestamp> is written before any change.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "src" / "plugin" / "code-survey" / "scripts" / "usage"
MARK = "code-survey"


def command(python: str, script: str) -> str:
    return f"{shlex.quote(python)} {shlex.quote(str(SCRIPTS / script))}"


def ours(entry) -> bool:
    return isinstance(entry, dict) and MARK in str(entry.get("command", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", default=str(Path.home() / ".claude" / "settings.json"))
    parser.add_argument("--python", default="python3", help="Python used to run the scripts")
    parser.add_argument("--refresh", type=int, default=5, help="refreshInterval in seconds")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    target = Path(args.target).expanduser()
    settings = {}
    if target.exists():
        settings = json.loads(target.read_text(encoding="utf-8") or "{}")
    before = json.dumps(settings, ensure_ascii=False, indent=2)

    if args.uninstall:
        for key in ("statusLine", "subagentStatusLine"):
            if ours(settings.get(key)):
                settings.pop(key)
    else:
        for key in ("statusLine", "subagentStatusLine"):
            current = settings.get(key)
            if current and not ours(current) and not args.force:
                print(f"skip {key}: another command is set ({current.get('command')!r}); "
                      "use --force to replace it", file=sys.stderr)
                continue
            entry = {"type": "command",
                     "command": command(args.python, "statusline.py" if key == "statusLine"
                                        else "subagent_statusline.py")}
            if key == "statusLine":
                entry["refreshInterval"] = args.refresh
            settings[key] = entry

    after = json.dumps(settings, ensure_ascii=False, indent=2)
    if before == after:
        print(f"no change: {target}")
        return 0
    if args.dry_run:
        print(after)
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_name(f"{target.name}.bak-{time.strftime('%Y-%m-%d_%H-%M-%S')}")
        shutil.copy2(target, backup)
        print(f"backup: {backup}")
    target.write_text(after + "\n", encoding="utf-8")
    print(f"updated: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
