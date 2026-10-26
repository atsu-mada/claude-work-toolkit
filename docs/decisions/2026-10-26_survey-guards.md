# 2026-10-26 Survey guards

Problems found by the blind quality review (`2026-10-26_quality-eval.md`):
1. Every configuration described config keys from their names; most keys were never read by the code.
2. A Haiku surveyor read up to 178k prompt tokens despite an 80k instruction (5x price tier above 100k).

Changes
- Surveyor: for every reported key, Grep its use outside the config; topics `config-key`,
  `config-key-unused`, `config-key-ignored` (hardcoded override). Survey skill asks the key question for
  every module with configuration.
- `scripts/survey/read_budget.py` (PreToolUse on Read|Grep|Glob, subagents only): refuses further reads
  when the subagent's last request exceeded `CODE_SURVEY_SUBAGENT_PROMPT_LIMIT` (default 80000), and
  refuses whole reads of files over 400 lines for the kit's own agents.
- Status line starts with the mode (`[eco]`, `[balanced]`, `[モードなし]`).

Re-run (same survey task, 05_image_processor, survey only)

| | B before | B after | C before | C after |
| --- | --- | --- | --- | --- |
| Cost | $0.519 | $0.442 | $0.068 | $0.055 |
| Largest subagent prompt | 178k | 35k | 45k | 28k |
| Requests over 100k | 4 | 0 | 0 | 0 |
| Dead config keys flagged as unused (of 11) | 0 | 5 | 0 | **11** |
| Hardcoded `max_size` override found | no | no | no | yes |

All 17 keys C marked unused were checked by grep: none is read by the code (three name matches were
different identifiers, which the note itself pointed out).
Budget hook in a real run with the limit set to 15k: 6 refusals, the surveyor wrote its note with the
unread parts as open questions; largest prompt 24k (the check uses the previous request, so one step over).
