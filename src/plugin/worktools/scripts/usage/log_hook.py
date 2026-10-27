"""Hook that records token usage and cache hit rate to JSONL logs.

Events (hook_event_name on stdin):
- SubagentStop: append one line per finished subagent to subagents.jsonl
- Stop:         overwrite sessions/<session_id>.json with the running totals
- SessionEnd:   append the final session line to sessions.jsonl

Only numbers and labels are written: no code, prompts, or replies.
Log folder: $CODE_SURVEY_LOG_DIR, default ~/.local/share/code-survey/logs.
Optional label for a run: $CODE_SURVEY_LABEL (for example "auth-module survey").
The hook never blocks Claude Code: it always exits 0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_core as core  # noqa: E402

SCHEMA = 1


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def git_head(cwd: str) -> str:
    if not cwd:
        return ""
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=2)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def append(path: Path, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def compact(t: dict) -> dict:
    """Totals with the per-model table, rounded for the log."""
    return {"all": t["all"], "models": t["models"]}


def base(payload: dict) -> dict:
    cwd = payload.get("cwd") or ""
    return {
        "schema": SCHEMA,
        "ts": now_iso(),
        "session_id": payload.get("session_id") or "",
        "project": os.path.basename(cwd.rstrip("/")) if cwd else "",
        "git_head": git_head(cwd),
        "label": os.environ.get("CODE_SURVEY_LABEL", ""),
        "mode": os.environ.get("CODE_SURVEY_MODE", ""),
    }


def on_subagent_stop(payload: dict) -> None:
    agent_path = payload.get("agent_transcript_path")
    if not agent_path:
        return
    path = Path(agent_path).expanduser()
    pricing = core.load_pricing()
    rows = list(core.read_rows(path, {}).get("rows", {}).values())
    meta = core.subagent_meta(path)
    record = base(payload)
    record.update({
        "event": "subagent",
        "agent_id": payload.get("agent_id") or path.stem[len("agent-"):],
        "agent_type": payload.get("agent_type") or meta.get("agentType") or "",
        "description": meta.get("description") or "",
        **compact(core.totals(pricing, rows)),
    })
    append(core.log_dir() / "subagents.jsonl", record)


def session_record(payload: dict, event: str) -> dict | None:
    transcript = payload.get("transcript_path")
    session_id = payload.get("session_id") or ""
    if not transcript:
        return None
    summary = core.summarize(transcript, session_id)
    status = core.read_json(core.state_dir() / f"{session_id}.status.json", {})
    pc = status.get("prompt_cache") or {}
    agent_types: dict = {}
    for info in summary["agents"].values():
        key = info["type"] or "unknown"
        slot = agent_types.setdefault(key, {"count": 0, "usd": 0.0, "hit_rate_avg": None,
                                            "_rates": []})
        slot["count"] += 1
        slot["usd"] = round(slot["usd"] + info["all"]["usd"], 6)
        if info["all"]["hit_rate"] is not None:
            slot["_rates"].append(info["all"]["hit_rate"])
    for slot in agent_types.values():
        rates = slot.pop("_rates")
        slot["hit_rate_avg"] = round(sum(rates) / len(rates), 4) if rates else None
    total_usd = summary["total"]["all"]["usd"]
    record = base(payload)
    record.update({
        "event": event,
        "reason": payload.get("reason") or "",
        "main": compact(summary["main"]),
        "sub": compact(summary["sub"]),
        "total": compact(summary["total"]),
        "sub_share": round(summary["sub"]["all"]["usd"] / total_usd, 4) if total_usd else None,
        "subagent_count": len(summary["agents"]),
        "subagent_types": agent_types,
        "official": {
            "cost_usd": status.get("official_cost_usd"),
            "hit_ratio_main": pc.get("hit_ratio"),
            "misses": pc.get("misses"),
            "miss_causes": pc.get("miss_causes"),
            "miss_recache_tokens": pc.get("miss_recache_tokens"),
            "expected_rebuilds": pc.get("expected_rebuilds"),
            "ttl": pc.get("ttl"),
            "claude_code_version": status.get("version"),
        },
        "pricing_checked_on": summary["pricing_checked_on"],
    })
    return record


def on_stop(payload: dict) -> None:
    record = session_record(payload, "stop")
    if record:
        folder = core.log_dir() / "sessions"
        folder.mkdir(exist_ok=True)
        core.write_json(folder / f"{record['session_id'] or 'unknown'}.json", record)


def on_session_end(payload: dict) -> None:
    record = session_record(payload, "session_end")
    if record and record["total"]["all"]["requests"]:
        append(core.log_dir() / "sessions.jsonl", record)


HANDLERS = {"SubagentStop": on_subagent_stop, "Stop": on_stop, "SessionEnd": on_session_end}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        handler = HANDLERS.get(payload.get("hook_event_name") or "")
        if handler:
            handler(payload)
    except Exception as error:  # record the failure, never block the session
        try:
            append(core.log_dir() / "hook_errors.jsonl",
                   {"ts": now_iso(), "error": f"{type(error).__name__}: {error}"})
        except OSError:
            pass
    sys.exit(0)


if __name__ == "__main__":
    main()
