"""PostToolUse hook (Write|Edit): rebuild report.html whenever a survey's summary.json is written.

In a test the main session (Haiku) skipped the report step of the survey skill, so the report is built
here instead: no model tokens, always up to date. A survey folder is one that holds summary.json and a
notes/ folder. The hook tells Claude where the report is, so it can pass the path on to the user.
Never blocks: errors are reported as context only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RENDERER = Path(__file__).resolve().parents[2] / "skills" / "survey" / "scripts"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    path = Path((payload.get("tool_input") or {}).get("file_path") or "")
    if path.name != "summary.json" or not (path.parent / "notes").is_dir():
        sys.exit(0)
    try:
        sys.path.insert(0, str(RENDERER))
        import render_report
        summary, notes = render_report.load_survey(path.parent)
        out = path.parent / "report.html"
        out.write_text(render_report.render(summary, notes), encoding="utf-8")
        message = f"code-survey: HTML report written to {out} ({len(notes)} modules). Give this path to the user."
    except Exception as error:
        message = f"code-survey: building report.html failed ({type(error).__name__}: {error})."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                             "additionalContext": message}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
