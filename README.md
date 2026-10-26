# code-survey-kit

Claude Code (CLI) kit for surveying a codebase on a limited usage budget.

Current scope (v0.1): **usage display and logging**
- Status line: API-equivalent spend of the parent session and its subagents, cache hit rate, context use
- Subagent rows: type, model, tokens, spend, and cache hit rate per subagent
- Hooks: one log line per subagent and per session (tokens, cache hit rate, spend) for the next review cycle

Planned: survey subagent, survey skill, HTML report renderer, usage review skill.

Install the log hooks (Claude Code 2.1.275 or later):

```
/plugin install code-survey --marketplace atsu-mada/code-survey-kit
```

Then add the status lines with `src/setup/install.py`.

- Setup: [docs/setup.md](docs/setup.md)
- What is measured and how: [docs/metrics.md](docs/metrics.md)
