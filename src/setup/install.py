"""Write the status line settings of code-survey-kit into a Claude Code settings file.

Plugins cannot set the parent status line, so this script adds:
  statusLine          -> scripts/usage/statusline.py   (refreshes every N seconds)
  subagentStatusLine  -> scripts/usage/subagent_statusline.py
The log hooks come with the plugin itself (hooks/hooks.json).

Usage (status lines; add --profile for model routing):
  python3 src/setup/install.py                       # ~/.claude/settings.json
  python3 src/setup/install.py --target <file>       # another settings file
  python3 src/setup/install.py --dry-run             # show the change only
  python3 src/setup/install.py --uninstall           # remove everything this script set
  python3 src/setup/install.py --profile haiku-subagents   # + every subagent on Haiku
  python3 src/setup/install.py --profile haiku-all         # + main session on Haiku too

A profile's keys are recorded in <target>.code-survey.json so --uninstall removes only them.

An existing statusLine that is not ours is kept unless --force is given.
A backup <target>.bak-<timestamp> is written before any change.
"""

from __future__ import annotations

import argparse
import json
import os
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


# Model routing profiles. Measured on 2026-10-26 (Claude Code 2.1.310): with only
# CLAUDE_CODE_SUBAGENT_MODEL=haiku the built-in Explore still ran on the main model (Sonnet);
# adding CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1 moved Explore to Haiku as well.
SUBAGENT_ENV = {"CLAUDE_CODE_SUBAGENT_MODEL": "haiku", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1"}
PROFILES = {
    "haiku-subagents": {"env": SUBAGENT_ENV},
    "haiku-all": {"env": SUBAGENT_ENV, "model": "haiku"},
}


LAUNCHER = REPO / "src" / "launcher" / "code_survey.py"


def link_launcher(bin_dir: Path, dry_run: bool, uninstall: bool) -> None:
    """Symlink <bin_dir>/code-survey to the launcher script (or remove our link)."""
    link = bin_dir / "code-survey"
    if uninstall:
        if link.is_symlink() and link.resolve() == LAUNCHER.resolve():
            if not dry_run:
                link.unlink()
            print(f"removed: {link}")
        return
    if link.exists() or link.is_symlink():
        if link.is_symlink() and link.resolve() == LAUNCHER.resolve():
            print(f"launcher already linked: {link}")
            return
        print(f"skip launcher: {link} exists and is not ours", file=sys.stderr)
        return
    if dry_run:
        print(f"would link: {link} -> {LAUNCHER}")
        return
    bin_dir.mkdir(parents=True, exist_ok=True)
    LAUNCHER.chmod(LAUNCHER.stat().st_mode | 0o111)
    link.symlink_to(LAUNCHER)
    print(f"linked: {link} -> {LAUNCHER}")
    if str(bin_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"note: add {bin_dir} to PATH to run `code-survey`", file=sys.stderr)


def apply_profile(settings: dict, name: str) -> dict:
    """Set the profile's keys; return a record of what was set (to undo it later)."""
    profile = PROFILES[name]
    record = {"profile": name, "env": {}, "model": None}
    env = settings.setdefault("env", {})
    for key, value in profile["env"].items():
        if key in env and env[key] != value:
            print(f"note: env {key} was {env[key]!r}, now {value!r}", file=sys.stderr)
        env[key] = value
        record["env"][key] = value
    if "model" in profile:
        if settings.get("model") not in (None, profile["model"]):
            print(f"note: model was {settings['model']!r}, now {profile['model']!r}",
                  file=sys.stderr)
        settings["model"] = profile["model"]
        record["model"] = profile["model"]
    return record


def remove_profile(settings: dict, record: dict) -> None:
    """Undo only the keys this script set that still hold the value it set."""
    env = settings.get("env") or {}
    for key, value in (record.get("env") or {}).items():
        if env.get(key) == value:
            env.pop(key)
    if "env" in settings and not settings["env"]:
        settings.pop("env")
    if record.get("model") and settings.get("model") == record["model"]:
        settings.pop("model")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", default=str(Path.home() / ".claude" / "settings.json"))
    parser.add_argument("--python", default="python3", help="Python used to run the scripts")
    parser.add_argument("--refresh", type=int, default=5, help="refreshInterval in seconds")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--profile", choices=sorted(PROFILES),
                        help="model routing: haiku-subagents (every subagent on Haiku) or "
                             "haiku-all (main session on Haiku too)")
    parser.add_argument("--no-statusline", action="store_true",
                        help="leave statusLine and subagentStatusLine untouched")
    parser.add_argument("--launcher", action="store_true",
                        help="link the `code-survey` command into --bin-dir")
    parser.add_argument("--bin-dir", default=str(Path.home() / ".local" / "bin"))
    args = parser.parse_args()

    if args.launcher:
        link_launcher(Path(args.bin_dir).expanduser(), args.dry_run, args.uninstall)

    target = Path(args.target).expanduser()
    settings = {}
    if target.exists():
        settings = json.loads(target.read_text(encoding="utf-8") or "{}")
    before = json.dumps(settings, ensure_ascii=False, indent=2)
    record_path = target.with_name(target.name + ".code-survey.json")
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}

    if args.uninstall:
        remove_profile(settings, record)
        record = {}
        for key in ("statusLine", "subagentStatusLine"):
            if ours(settings.get(key)):
                settings.pop(key)
    elif args.profile:
        remove_profile(settings, record)
        record = apply_profile(settings, args.profile)
    if args.uninstall or args.no_statusline:
        pass
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
    if record:
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    elif record_path.exists() and (args.uninstall or args.profile):
        record_path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
