"""Row body for each subagent in the agent panel: type, model, tokens, spend, cache.

Claude Code sends {"transcript_path", "session_id", "tasks": [...]} on stdin and
expects one JSON line {"id", "content"} per row to override.
Example row:  code-surveyor · Haiku · 84.2k tok · ¥12 · キャッシュ 71% · auth モジュール調査
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_core as core  # noqa: E402


def row_content(task: dict, agent: dict | None, rate) -> str:
    parts = [task.get("agentType") or (agent or {}).get("type") or "agent"]
    model = task.get("model")
    if model:
        parts.append(core.family(model))
    parts.append(f"{core.tokens(task.get('tokenCount') or 0)} tok")
    if agent:
        parts.append(core.money(agent["all"]["usd"], rate))
        rate_text = agent["all"]["hit_rate"]
        if rate_text is not None:
            parts.append(f"キャッシュ {round(rate_text * 100)}%")
    label = task.get("label") or task.get("description")
    if label:
        parts.append(label[:40])
    return " · ".join(parts)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    tasks = payload.get("tasks") or []
    if not tasks:
        return
    agents = {}
    transcript = payload.get("transcript_path")
    if transcript:
        try:
            agents = core.summarize(transcript, payload.get("session_id") or "")["agents"]
        except Exception:
            agents = {}
    rate = core.usd_jpy()
    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        key = str(task_id)
        agent = agents.get(key[len("agent-"):] if key.startswith("agent-") else key)
        print(json.dumps({"id": task_id, "content": row_content(task, agent, rate)},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
