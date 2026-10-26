"""Read Claude Code transcripts and total the token usage of a session.

The parent's transcript is <projects>/<project>/<session>.jsonl and each
subagent's is <projects>/<project>/<session>/subagents/agent-<id>.jsonl.
Every assistant line carries message.usage and message.model. One API request
can be split over several lines that share message.id, so the last line of
each id wins.

Files are read incrementally: the byte offset and the rows already seen are
kept in a state file, so the status line stays fast in long sessions.
Standard library only; works on Python 3.9 or later.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRICING = PLUGIN_ROOT / "config" / "pricing.json"
RATE_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=JPY"

# A row: [model, input, output, cache_read, cache_write_5m, cache_write_1h, geo]
FIELDS = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")


def state_dir() -> Path:
    base = os.environ.get("CODE_SURVEY_STATE_DIR") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "code-survey")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    base = os.environ.get("CODE_SURVEY_LOG_DIR") or os.path.expanduser(
        "~/.local/share/code-survey/logs")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


# ---------- transcripts ----------

def usage_row(entry: dict):
    """Return (request id, row) for an assistant line with usage, else None."""
    if entry.get("type") != "assistant":
        return None
    message = entry.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    model = message.get("model") or ""
    if not isinstance(usage, dict) or not model or model == "<synthetic>":
        return None
    key = message.get("id") or entry.get("requestId") or entry.get("uuid")
    if not key:
        return None
    write_total = usage.get("cache_creation_input_tokens") or 0
    split = usage.get("cache_creation")
    if isinstance(split, dict):
        write_5m = split.get("ephemeral_5m_input_tokens") or 0
        write_1h = split.get("ephemeral_1h_input_tokens") or 0
    else:
        write_5m, write_1h = write_total, 0
    row = [
        model,
        usage.get("input_tokens") or 0,
        usage.get("output_tokens") or 0,
        usage.get("cache_read_input_tokens") or 0,
        write_5m,
        write_1h,
        usage.get("inference_geo") or "global",
    ]
    return key, row


def read_rows(path: Path, cache: dict) -> dict:
    """Update cache {"offset", "rows"} with the lines added since the last read."""
    rows = cache.setdefault("rows", {})
    offset = cache.get("offset", 0)
    try:
        size = path.stat().st_size
    except OSError:
        return cache
    if size < offset:  # file was rewritten; start over
        rows.clear()
        offset = 0
    if size == offset:
        return cache
    with open(path, "rb") as f:
        f.seek(offset)
        chunk = f.read()
    end = chunk.rfind(b"\n")
    if end < 0:
        return cache  # only a partial line so far
    for raw in chunk[: end + 1].splitlines():
        if b'"usage"' not in raw:
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        found = usage_row(entry)
        if found:
            rows[found[0]] = found[1]
    cache["offset"] = offset + end + 1
    return cache


def subagent_files(transcript: Path) -> list:
    folder = transcript.parent / transcript.stem / "subagents"
    if not folder.is_dir():
        return []
    return sorted(folder.glob("agent-*.jsonl"))


def subagent_meta(agent_file: Path) -> dict:
    meta = read_json(agent_file.with_name(agent_file.stem + ".meta.json"), {})
    return meta if isinstance(meta, dict) else {}


def collect(transcript_path: str, session_id: str = "") -> dict:
    """Rows of the parent and of every subagent, read incrementally.

    Returns {"main": [row...], "agents": {agent_id: {"type", "description", "rows"}}}.
    """
    transcript = Path(transcript_path).expanduser()
    sid = session_id or transcript.stem
    state_path = state_dir() / f"{sid}.rows.json"
    state = read_json(state_path, {})
    if state.get("transcript") != str(transcript):
        state = {"transcript": str(transcript), "files": {}}
    files = state.setdefault("files", {})

    main_cache = read_rows(transcript, files.setdefault("main", {}))
    agents = {}
    for agent_file in subagent_files(transcript):
        agent_id = agent_file.stem[len("agent-"):]
        cache = read_rows(agent_file, files.setdefault(agent_id, {}))
        meta = subagent_meta(agent_file)
        agents[agent_id] = {
            "type": meta.get("agentType") or "",
            "description": meta.get("description") or "",
            "rows": list(cache.get("rows", {}).values()),
        }
    try:
        write_json(state_path, state)
    except OSError:
        pass
    return {"main": list(main_cache.get("rows", {}).values()), "agents": agents}


# ---------- pricing ----------

def load_pricing(path: str = "") -> dict:
    chosen = Path(path or os.environ.get("CODE_SURVEY_PRICING") or DEFAULT_PRICING)
    data = read_json(chosen.expanduser(), {})
    return data if isinstance(data, dict) else {}


def rates_for(pricing: dict, model: str, prompt_tokens: int):
    models = pricing.get("models") or {}
    key = next((k for k in sorted(models, key=len, reverse=True) if model.startswith(k)), None)
    if key is None:
        return None
    entry = models[key]
    for tier in entry.get("tiers") or []:
        limit = tier.get("max_prompt_tokens")
        if limit is None or prompt_tokens <= limit:
            return tier
    return entry if "input" in entry else None


def row_usd(pricing: dict, row) -> float:
    model, inp, out, cr, cw5, cw1h, geo = (list(row) + ["global"])[:7]
    rates = rates_for(pricing, model, inp + cr + cw5 + cw1h)
    if not rates:
        return 0.0
    multiplier = ((pricing.get("multipliers") or {}).get("inference_geo") or {}).get(geo, 1.0)
    usd = (inp * rates["input"] + out * rates["output"] + cr * rates["cache_read"]
           + cw5 * rates["cache_write_5m"] + cw1h * rates["cache_write_1h"]) / 1_000_000
    return usd * multiplier


def family(model: str) -> str:
    for name in ("opus", "sonnet", "haiku", "fable"):
        if name in model:
            return name.capitalize()
    return model or "?"


def totals(pricing: dict, rows) -> dict:
    """Sum rows into {"models": {model: {...}}, "all": {...}}."""
    def empty():
        return {"requests": 0, "usd": 0.0, **{k: 0 for k in FIELDS},
                "max_prompt": 0, "requests_over_100k": 0}
    by_model: dict = {}
    overall = empty()
    for row in rows:
        model = row[0]
        bucket = by_model.setdefault(model, empty())
        usd = row_usd(pricing, row)
        # prompt size of this one request; Haiku 5.5 costs 5x per token above 100k
        prompt = row[1] + row[3] + row[4] + row[5]
        for target in (bucket, overall):
            target["requests"] += 1
            target["usd"] += usd
            target["max_prompt"] = max(target["max_prompt"], prompt)
            if prompt > 100_000:
                target["requests_over_100k"] += 1
            for i, name in enumerate(FIELDS, start=1):
                target[name] += row[i]
    for target in list(by_model.values()) + [overall]:
        target["usd"] = round(target["usd"], 6)
        target["hit_rate"] = hit_rate(target)
    return {"models": by_model, "all": overall}


def hit_rate(t: dict):
    """Cache reads as a share of all prompt tokens (same definition as prompt_cache.hit_ratio)."""
    prompt = t["input"] + t["cache_read"] + t["cache_write_5m"] + t["cache_write_1h"]
    return round(t["cache_read"] / prompt, 4) if prompt else None


def summarize(transcript_path: str, session_id: str = "", pricing: dict | None = None) -> dict:
    pricing = pricing if pricing is not None else load_pricing()
    data = collect(transcript_path, session_id)
    main = totals(pricing, data["main"])
    agents = {}
    sub_rows = []
    for agent_id, info in data["agents"].items():
        agents[agent_id] = {"type": info["type"], "description": info["description"],
                            **totals(pricing, info["rows"])}
        sub_rows.extend(info["rows"])
    sub = totals(pricing, sub_rows)
    everything = totals(pricing, data["main"] + sub_rows)
    return {"main": main, "sub": sub, "total": everything, "agents": agents,
            "pricing_checked_on": pricing.get("checked_on", "")}


# ---------- money ----------

def usd_jpy(max_age_s: int = 86400, timeout: float = 1.5):
    """USD->JPY, fetched at most once a day; None when unavailable or disabled."""
    fixed = os.environ.get("CODE_SURVEY_USDJPY")
    if fixed:
        try:
            return float(fixed) or None
        except ValueError:
            return None
    if os.environ.get("CODE_SURVEY_NO_FX") == "1":
        return None
    path = state_dir() / "usdjpy.json"
    kept = read_json(path, {})
    now = time.time()
    if kept.get("rate") and now - kept.get("fetched", 0) < max_age_s:
        return kept["rate"]
    if now - kept.get("tried", 0) < 600:  # do not retry a failing network every tick
        return kept.get("rate")
    kept["tried"] = now
    try:
        with urllib.request.urlopen(RATE_URL, timeout=timeout) as response:
            rate = json.load(response).get("rates", {}).get("JPY")
        if isinstance(rate, (int, float)) and rate > 0:
            kept.update(rate=rate, fetched=now)
    except Exception:
        pass
    try:
        write_json(path, kept)
    except OSError:
        pass
    return kept.get("rate")


def money(usd: float, rate) -> str:
    if rate:
        return f"¥{round(usd * rate):,}"
    return f"${usd:.2f}"


def tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)
