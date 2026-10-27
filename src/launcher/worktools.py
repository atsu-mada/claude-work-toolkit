#!/usr/bin/env python3
"""Start Claude Code in a worktools mode.

Usage:
  worktools eco [claude args...]        main session and subagents on Haiku
  worktools balanced [claude args...]   main session on Sonnet, subagents on Haiku
  worktools [claude args...]            asks which mode first (interactive terminals only)
  worktools --list                      show the modes
  worktools --dry-run <mode> ...        print the claude command instead of running it

Everything after the mode goes to `claude` unchanged, e.g. `worktools eco -p "survey this repo"`.
Aliases (b, c, haiku, ...) and the modes themselves are defined in
src/plugin/worktools/config/modes.json. Install as a command with `src/setup/install.py --launcher`.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "src" / "plugin" / "worktools" / "scripts" / "mode"))
import modes as mode_lib  # noqa: E402


def ask(modes: dict, stream_in=sys.stdin, stream_out=sys.stderr) -> str | None:
    """Ask for a mode on the terminal; no default, so the user always chooses."""
    names = list(modes)
    print("worktools: モードを選んでください / choose a mode", file=stream_out)
    for i, name in enumerate(names, 1):
        print(f"  {i}) {name:<9} {modes[name]['title']}", file=stream_out)
    for _ in range(3):
        print(f"番号か名前 [1-{len(names)}] (q で中止): ", end="", file=stream_out, flush=True)
        answer = stream_in.readline()
        if not answer:
            return None
        answer = answer.strip()
        if answer.lower() in ("q", "quit"):
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            return names[int(answer) - 1]
        chosen = mode_lib.resolve(answer, modes)
        if chosen:
            return chosen
        print(f"  '{answer}' は選べません", file=stream_out)
    return None


def build(mode: str, rest: list, modes: dict) -> list:
    settings = mode_lib.settings_for(mode, modes)
    return ["claude", "--model", settings["model"],
            "--settings", json.dumps({"env": settings["env"]}, separators=(",", ":"))] + rest


def main(argv: list) -> int:
    modes = mode_lib.load()
    dry = False
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv and argv[0] == "--list":
        print("\n".join(mode_lib.describe(modes)))
        return 0
    if argv and argv[0] == "--dry-run":
        dry, argv = True, argv[1:]

    mode, rest = None, argv
    first = argv[0] if argv else ""
    if first and not first.startswith("-"):
        mode = mode_lib.resolve(first, modes)
        if mode:
            rest = argv[1:]
        elif " " not in first:  # one word that is not a mode: a typo, not a prompt
            print(f"worktools: unknown mode '{first}'. Modes:\n  "
                  + "\n  ".join(mode_lib.describe(modes)), file=sys.stderr)
            return 2
    if mode is None:
        if not sys.stdin.isatty():
            print("worktools: no mode given and no terminal to ask. Start with one of: "
                  + ", ".join(modes), file=sys.stderr)
            return 2
        mode = ask(modes)
        if mode is None:
            print("worktools: cancelled", file=sys.stderr)
            return 1

    command = build(mode, rest, modes)
    print(f"worktools: mode {mode} ({modes[mode]['title']})", file=sys.stderr)
    if dry:
        print(json.dumps(command, ensure_ascii=False))
        return 0
    if not shutil.which("claude"):
        print("worktools: `claude` was not found on PATH", file=sys.stderr)
        return 127
    os.execvp("claude", command)
    return 0  # not reached


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
