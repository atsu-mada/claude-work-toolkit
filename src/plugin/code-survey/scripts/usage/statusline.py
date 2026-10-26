"""Status line for the parent session: spend of parent and subagents, cache, context.

Claude Code runs this with the session JSON on stdin and shows what it prints.
Example:  [eco]｜¥128（親 ¥81 · サブ ¥47・3体）｜キャッシュ 親93% サブ71% 残42分｜ctx 34%｜Sonnet 5.5

It also saves the official prompt_cache and cost fields to the state folder, so
the log hook can record cache misses and their causes at the end of the session.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_core as core  # noqa: E402


def pct(value) -> str:
    return "—" if value is None else f"{round(value * 100)}%"


def cache_part(payload: dict, summary: dict) -> str:
    pc = payload.get("prompt_cache") or {}
    main_rate = pc.get("hit_ratio")
    if main_rate is None:
        main_rate = summary["main"]["all"]["hit_rate"]
    text = f"キャッシュ 親{pct(main_rate)}"
    if summary["agents"]:
        text += f" サブ{pct(summary['sub']['all']['hit_rate'])}"
    expires = pc.get("expires_at")
    if pc.get("warm") and isinstance(expires, (int, float)):
        left = int((expires - time.time()) // 60)
        if left >= 0:
            text += f" 残{left}分"
    elif pc.get("caching_observed") and pc.get("warm") is False:
        text += " 切れ"
    misses = pc.get("misses") or 0
    if misses:
        causes = (pc.get("last_miss_cause") or {}).get("causes") or []
        text += f" ミス{misses}" + (f"({causes[0]})" if causes else "")
    return text


def mode_part() -> str:
    """Mode set by `code-survey <mode>` (CODE_SURVEY_MODE), shown first."""
    mode = os.environ.get("CODE_SURVEY_MODE", "").strip()
    return f"[{mode}]" if mode else "[モードなし]"


def render(payload: dict) -> str:
    transcript = payload.get("transcript_path") or ""
    session_id = payload.get("session_id") or ""
    summary = core.summarize(transcript, session_id) if transcript else None
    rate = core.usd_jpy()
    parts = [mode_part()]
    if summary:
        main_usd = summary["main"]["all"]["usd"]
        sub_usd = summary["sub"]["all"]["usd"]
        count = len(summary["agents"])
        parts.append(f"{core.money(main_usd + sub_usd, rate)}（親 {core.money(main_usd, rate)}"
                     f" · サブ {core.money(sub_usd, rate)}・{count}体）")
        parts.append(cache_part(payload, summary))
    ctx = (payload.get("context_window") or {}).get("used_percentage")
    if ctx is not None:
        parts.append(f"ctx {round(ctx)}%")
    model = (payload.get("model") or {}).get("display_name")
    if model:
        parts.append(model)
    save_snapshot(payload, session_id)
    return "｜".join(parts)


def save_snapshot(payload: dict, session_id: str) -> None:
    if not session_id:
        return
    snapshot = {
        "saved_at": time.time(),
        "prompt_cache": payload.get("prompt_cache"),
        "official_cost_usd": (payload.get("cost") or {}).get("total_cost_usd"),
        "model": (payload.get("model") or {}).get("id"),
        "context_used_percentage": (payload.get("context_window") or {}).get("used_percentage"),
        "version": payload.get("version"),
    }
    try:
        core.write_json(core.state_dir() / f"{session_id}.status.json", snapshot)
    except OSError:
        pass


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    try:
        print(render(payload))
    except Exception as error:  # never leave the bar blank because of a bug
        print(f"code-survey: {type(error).__name__}")


if __name__ == "__main__":
    main()
