# code-survey-kit

Claude Code (CLI) kit for surveying a codebase on a limited usage budget.

Current scope (v0.2)

**Survey on Haiku**
- `code-survey:survey` skill: the main session plans and combines, subagents read
- `code-survey:surveyor` (Haiku, low effort): reads one module, writes a JSON note; a hook rejects notes that miss required keys
- `code-survey:locator` (Haiku): returns `file:line` locations only
- `install.py --profile haiku-subagents | haiku-all`: puts every subagent (and optionally the main session) on Haiku

**Usage display and logging**
- Status line: API-equivalent spend of the parent session and its subagents, cache hit rate, context use
- Subagent rows: type, model, tokens, spend, and cache hit rate per subagent
- Hooks: one log line per subagent and per session (tokens, cache hit rate, spend) for the next review cycle

Planned: HTML report renderer, usage review skill.

Install the log hooks (Claude Code 2.1.275 or later):

```
/plugin install code-survey --marketplace atsu-mada/code-survey-kit
```

Then add the status lines with `src/setup/install.py`.

- Setup: [docs/setup.md](docs/setup.md)
- What is measured and how: [docs/metrics.md](docs/metrics.md)
- Why Haiku is routed this way (measurements): [docs/decisions/2026-10-26_haiku-routing.md](docs/decisions/2026-10-26_haiku-routing.md)
