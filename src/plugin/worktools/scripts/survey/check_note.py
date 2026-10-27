"""PostToolUse hook: check a survey note written by the surveyor subagent.

Runs after Write. Acts only when the writer is the worktools surveyor and the file is a
JSON note under a `notes/` folder. If the note is not valid JSON or lacks required keys,
exit code 2 sends the problem back to the subagent so it rewrites the note. A valid note
costs no tokens. Never blocks anything else.
"""

from __future__ import annotations

import json
import sys

REQUIRED = {
    "module": str,
    "summary": str,
    "entry_points": list,
    "dependencies": dict,
    "findings": list,
    "answers": list,
    "open_questions": list,
    "files_read": list,
}
CITED = ("findings", "answers")


def problems(note) -> list:
    if not isinstance(note, dict):
        return ["the note must be one JSON object"]
    found = []
    for key, kind in REQUIRED.items():
        if key not in note:
            found.append(f"missing key `{key}`")
        elif not isinstance(note[key], kind):
            found.append(f"`{key}` must be a {kind.__name__}")
    for item in note.get("findings") or []:
        if isinstance(item, dict) and not (item.get("file") and item.get("line")):
            found.append(f"finding `{item.get('topic', '?')}` needs `file` and `line`")
    for item in note.get("answers") or []:
        if isinstance(item, dict) and not item.get("evidence"):
            found.append(f"answer to `{item.get('question', '?')}` needs `evidence`")
    return found


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    agent = payload.get("agent_type") or ""
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not agent.endswith("surveyor") or "/notes/" not in path or not path.endswith(".json"):
        sys.exit(0)
    try:
        with open(path, encoding="utf-8") as f:
            note = json.load(f)
    except (OSError, ValueError) as error:
        print(f"Survey note {path} is not valid JSON ({error}). Rewrite it.", file=sys.stderr)
        sys.exit(2)
    found = problems(note)
    if found:
        print(f"Survey note {path} does not match the required format: " + "; ".join(found)
              + ". Rewrite the whole note with exactly the keys in your instructions "
              "(put extra information such as risks into `findings`).", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
