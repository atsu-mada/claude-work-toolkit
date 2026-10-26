# code-survey-kit

Claude Code (CLI) kit for surveying a codebase on a limited usage budget.

Current scope (v0.4)

**Start in a mode** (models are fixed at start)

```bash
code-survey eco        # エコ: main session and subagents on Haiku (default choice for most work)
code-survey balanced   # バランス: main session on Sonnet, subagents on Haiku
code-survey            # asks which mode first
```

Arguments after the mode go to `claude` (`code-survey eco -p "..."`). Plain `claude` with the plugin shows
the modes before the first prompt; `claude -p` without a mode is refused.

**Survey on Haiku**
- `code-survey:survey` skill: the main session plans and combines, subagents read
- `code-survey:surveyor` (Haiku, low effort): reads one module, writes a JSON note; a hook rejects notes that miss required keys
- `code-survey:locator` (Haiku): returns `file:line` locations only
- Guards: subagents stop reading above 80k prompt tokens (Haiku costs 5x above 100k); whole reads of files over 400 lines are refused; config keys are checked for actual use
- `install.py --profile haiku-subagents | haiku-all`: fixed routing in a settings file, for use without the launcher

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
