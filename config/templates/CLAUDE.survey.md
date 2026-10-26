<!-- Paste into the CLAUDE.md of a repository you survey (or into ~/.claude/CLAUDE.md). Keep it short. -->
## Code survey budget rules

- Investigate code with the `code-survey:survey` skill. The main session plans and combines; the
  `code-survey:surveyor` subagent (Haiku) reads, one module per call.
- Use `code-survey:locator` for "where is X" lookups instead of reading files in the main session.
- Do not change the model or MCP servers during a session; use `/clear` between unrelated tasks.
- When documentation and code disagree, follow the code and list every mismatch in the final reply.
- Build survey reports with the survey skill's `render_report.py`; do not hand-write report HTML.
- For any HTML page (reports, previews, dashboards), invoke `/awesome-design-skills` first and follow it.
