"""SessionStart hook: tell Claude which code-survey mode is active, or to ask for one.

`code-survey <mode>` sets CODE_SURVEY_MODE. When it is missing (plain `claude`), Claude is told to ask
the user which mode to use before any survey or development work, and to have them restart with
`code-survey <mode>`, since the models are fixed when a session starts.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modes as mode_lib  # noqa: E402


def context(env: dict) -> str:
    modes = mode_lib.load()
    mode = mode_lib.resolve(env.get(mode_lib.ENV_MODE, ""), modes)
    if mode:
        spec = modes[mode]
        return (f"code-survey mode: {mode} ({spec['title']}). Main model {spec['model']}, every "
                f"subagent {spec['subagent_model']}. Do not switch models during this session.")
    lines = "\n".join(f"- {name}: {spec['title']}. {spec['summary']} Start: `code-survey {name}`"
                      for name, spec in modes.items())
    return (
        "code-survey: no mode was chosen for this session. The prompt hook shows the user these modes "
        "before the first prompt:\n"
        f"{lines}\n"
        "If the user continues without a mode, work normally; do not ask again. If they ask how to "
        "switch, tell them to exit and restart with one of the commands above (models are fixed at start)."
    )


def main() -> None:
    try:
        json.load(sys.stdin)
    except ValueError:
        pass
    try:
        text = context(dict(os.environ))
    except Exception:  # never block the session
        sys.exit(0)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": text}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
