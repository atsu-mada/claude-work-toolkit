# 2026-10-27 HTML report

- `skills/survey/scripts/render_report.py` builds one page from `summary.json` and `notes/*.json`: counts,
  overview, modules, cross-module links, risks, then per module the answers with evidence, entry points,
  findings, config keys (problems first: ignored, unused, read), dependencies, open questions, files read.
  A filter box narrows findings and answers. `--source-url` links every `file:line`.
- Design: the awesome-design-skills system (user request, 2026-10-27), same tokens as
  `~/agent-skills/design/preview/tokens.css`: white surface, black as the only fill and divider, pill
  controls, no shadows or gradients, Open Sans / JetBrains Mono. Status colors (success, warning, danger)
  fail AA as small text on white, so they appear only as badge borders and dots; text stays `--text`.
  The system defines no dark theme, so the page has none.
- Built by a PostToolUse hook (`scripts/survey/auto_report.py`) on every write of `summary.json`: in a test
  the Haiku main session skipped the report step of the skill. With the hook, an eco survey of
  05_image_processor produced the report automatically ($0.048, 94 s) and the final reply named its path.
- Checked in a browser at desktop and 375 px width (no horizontal overflow; long paths wrap).
- Notes and summary are written in the user's language (`language` passed to the surveyor), since an
  English task prompt produced an English report.
