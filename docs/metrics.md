# Metrics

## Source

Claude Code writes each session to `~/.claude/projects/<project>/<session>.jsonl` and each subagent to
`<session>/subagents/agent-<id>.jsonl` (type in `agent-<id>.meta.json`). Assistant lines carry
`message.usage` and `message.model`. One request can span several lines with the same `message.id`;
the last one is used. The on-disk format is not formally documented; `src/test/` pins what we rely on.

## Numbers

- **Spend**: API list price from `config/pricing.json` (per million tokens, tiers by prompt size,
  inference-geo multiplier). On a subscription or Enterprise seat this is an estimate, not the bill.
- **Cache hit rate**: cache reads / (uncached input + cache reads + cache writes). Same definition as the
  status line's `prompt_cache.hit_ratio`, which covers the parent only; the kit adds the subagents.
- **Sub share**: subagent spend / total spend.

Check on 2026-10-26 (Claude Code 2.1.310, Haiku session with one Explore subagent): kit total $0.01800,
official `cost.total_cost_usd` $0.01828 (1.6% apart). The official figure includes subagents.

## Logs

| File | Written by | Content |
| --- | --- | --- |
| `subagents.jsonl` | SubagentStop | one line per finished subagent: type, per-model tokens, hit rate, spend |
| `sessions/<id>.json` | Stop | running totals of the session, overwritten each turn |
| `sessions.jsonl` | SessionEnd | final line per session: parent / sub / total by model, sub share, subagent types, official cache stats (misses, miss causes) |
| `hook_errors.jsonl` | any | hook failures (the session is never blocked) |

Logs hold numbers and labels only (no code, prompts, or replies).
