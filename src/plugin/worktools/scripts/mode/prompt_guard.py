"""UserPromptSubmit hook: make sure a mode was chosen before any work starts.

The SessionStart text alone was ignored by Haiku in a test, so this hook enforces it:
- mode set (started with `worktools <mode>`): do nothing
- non-interactive run (`claude -p`): block every prompt and name the commands to use
- interactive run: block the first prompt once and show the modes; the user restarts with
  `worktools <mode>`, or sends the prompt again to continue without a mode

Non-interactive is detected from CLAUDE_CODE_ENTRYPOINT (sdk-*) or CLAUDE_CODE_SESSION_ATTENDED=0,
observed on Claude Code 2.1.310; both are undocumented, so anything else counts as interactive.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modes as mode_lib  # noqa: E402


def non_interactive(env: dict) -> bool:
    return (env.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk")
            or env.get("CLAUDE_CODE_SESSION_ATTENDED") == "0")


def menu(modes: dict) -> str:
    return "\n".join(f"  worktools {name:<9} … {spec['title']}" for name, spec in modes.items())


def decide(payload: dict, env: dict, state_dir: Path):
    """Return the hook output dict, or None to let the prompt through."""
    modes = mode_lib.load()
    if env.get(mode_lib.ENV_MODE, "").strip():  # any explicit mode, including custom ones (e.g. eval runs)
        return None
    if non_interactive(env):
        return {"decision": "block",
                "reason": "worktools: モードが指定されていません / no mode given.\n"
                          f"次のどちらかで実行してください:\n{menu(modes)}"}
    marker = state_dir / f"{payload.get('session_id') or 'unknown'}.mode-asked"
    if marker.exists():
        return None
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        return None  # cannot remember the question: do not block forever
    return {"decision": "block",
            "reason": "worktools: モードを選んでください / choose a mode.\n"
                      f"{menu(modes)}\n"
                      "モデルは起動時に決まるので、/exit してから上のどちらかで起動し直してください。\n"
                      "モードなしで続けるなら、同じ依頼をもう一度送ってください。"}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    try:
        state = Path(os.environ.get("CODE_SURVEY_STATE_DIR")
                     or os.path.expanduser("~/.cache/code-survey"))
        out = decide(payload, dict(os.environ), state)
    except Exception:  # never lock the user out because of a bug
        out = None
    if out:
        print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
