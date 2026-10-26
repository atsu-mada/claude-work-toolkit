# 2026-10-26 Haiku routing

Claude Code 2.1.310, Anthropic API, Haiku 5.5. Same task each time: "use the Explore subagent to count the
.py files under src/" (answer: 6 in every run). API-equivalent cost from `claude -p --output-format json`.

| Setup | Total | Main | Explore subagent |
| --- | --- | --- | --- |
| main Sonnet, `CLAUDE_CODE_SUBAGENT_MODEL=haiku` only | $0.250 | Sonnet $0.167 | **Sonnet** $0.084 |
| main Sonnet, + `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` | $0.258 | Sonnet $0.253 | Haiku $0.0045 |
| main Haiku, + FORCE | **$0.019** | Haiku | Haiku |

Findings
- The environment variable alone does not move the built-in Explore off the main model; FORCE does.
  Posts on X reported the same (for example 9,628 subagent replies with zero on Haiku).
- In short sessions the main session's first cache write dominates (about 60k tokens of system prompt,
  tools, and CLAUDE.md). Putting the main session on Haiku cut the cost by about 14x.

Survey run (05_image_processor, 43k lines, 3 modules, everything on Haiku via `--profile haiku-all`)
- First run: $0.044, 94 s. Entry-point line numbers checked by hand: 6 of 6 correct. But only 1 of 3 notes
  kept the required JSON keys.
- Added `scripts/survey/check_note.py` (PostToolUse on Write): rejects a note with missing keys, the
  surveyor rewrites it. Second run: $0.052, 119 s, 3 of 3 notes in format, largest single prompt 34k tokens.

Decisions
- Default for surveys: `--profile haiku-all`. Our own agents also pin `model: haiku`, `effort: low`,
  `omitClaudeMd: true`, read-only tools plus Write for the note.
- Do not use `--advisor`: posts report that each advisor call reads the whole session at Opus price without
  cache.
- Keep work that needs judgment (final conclusions, risky changes) for a Sonnet session.
