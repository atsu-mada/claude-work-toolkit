"""PreToolUse hook (Read|Grep|Glob): keep subagents under a reading budget.

Applies to subagents only (the hook input has `agent_id`); the main session is never limited.
1. Budget: when the subagent's last request already used more than the limit of prompt tokens, further
   reads are refused with a message telling it to write its result now. Haiku 5.5 costs 5x per token above
   100,000 prompt tokens, and an instruction alone did not keep a surveyor under it (178k in a test).
2. Whole-file reads: a Read without offset/limit of a file over 400 lines is refused for the kit's own
   agents (surveyor, locator), which are told to Grep first and read ranges.

Limit: $CODE_SURVEY_SUBAGENT_PROMPT_LIMIT (default 80000). Set it to 0 to turn the budget off.
Never fails closed: any error lets the call through.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_LIMIT = 80_000
WHOLE_FILE_LINES = 400
OWN_AGENTS = ("surveyor", "locator")


def last_prompt_tokens(agent_file: Path) -> int:
    """Prompt size (input + cache read + cache write) of the subagent's latest request."""
    try:
        with open(agent_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 400_000))
            tail = f.read().splitlines()
    except OSError:
        return 0
    for raw in reversed(tail):
        if b'"usage"' not in raw:
            continue
        try:
            usage = json.loads(raw).get("message", {}).get("usage") or {}
        except (ValueError, AttributeError):
            continue
        return ((usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
                + (usage.get("cache_creation_input_tokens") or 0))
    return 0


def deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def decide(payload: dict, env: dict):
    agent_id = payload.get("agent_id")
    if not agent_id:
        return None
    agent_type = payload.get("agent_type") or ""
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    limit = int(env.get("CODE_SURVEY_SUBAGENT_PROMPT_LIMIT") or DEFAULT_LIMIT)
    transcript = Path(payload.get("transcript_path") or "")
    if limit > 0 and transcript.name:
        agent_file = transcript.parent / transcript.stem / "subagents" / f"agent-{agent_id}.jsonl"
        used = last_prompt_tokens(agent_file)
        if used > limit:
            return deny(f"Reading budget reached ({used:,} of {limit:,} prompt tokens). Stop reading. "
                        "Write your result now with what you have, and list what you could not read "
                        "as open questions.")

    if (tool == "Read" and agent_type.split(":")[-1] in OWN_AGENTS
            and not tool_input.get("limit") and not tool_input.get("offset")):
        path = tool_input.get("file_path") or ""
        try:
            with open(path, "rb") as f:
                lines = sum(1 for _ in f)
        except OSError:
            return None
        if lines > WHOLE_FILE_LINES:
            return deny(f"{path} has {lines} lines. Do not read it whole: Grep for what you need, then "
                        "Read with offset and limit (at most about 200 lines at a time).")
    return None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        out = decide(payload, dict(os.environ))
    except Exception:
        out = None
    if out:
        print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
