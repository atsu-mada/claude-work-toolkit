# claude-work-toolkit

Tools for using Claude Code (CLI) at work on a limited usage budget: start modes, a codebase survey with an
HTML report, a repository layout policy, and spend / cache display and logging.
Formerly `code-survey-kit` (renamed 2026-10-27; the old GitHub URL redirects here).

Current scope (v0.6)

**Start in a mode** (models are fixed at start)

```bash
worktools eco        # エコ: main session and subagents on Haiku (default choice for most work)
worktools balanced   # バランス: main session on Sonnet, subagents on Haiku
worktools            # asks which mode first
```

Arguments after the mode go to `claude` (`worktools eco -p "..."`). Plain `claude` with the plugin shows
the modes before the first prompt; `claude -p` without a mode is refused.

**Survey on Haiku**
- `worktools:survey` skill: the main session plans and combines, subagents read, and `survey/<date>/report.html` is built automatically (awesome-design-skills design, no model tokens)
- `worktools:surveyor` (Haiku, low effort): reads one module, writes a JSON note; a hook rejects notes that miss required keys
- `worktools:locator` (Haiku): returns `file:line` locations only
- Guards: subagents stop reading above 80k prompt tokens (Haiku costs 5x above 100k); whole reads of files over 400 lines are refused; config keys are checked for actual use
- `install.py --profile haiku-subagents | haiku-all`: fixed routing in a settings file, for use without the launcher

**Repository layout**
- `worktools:repo-layout-policy` skill: keeps new files out of the repository root and under `config/`, `data/`, `docs/`, `src/`, `old/` (tests in `src/test/`)

**Usage display and logging**
- Status line: API-equivalent spend of the parent session and its subagents, cache hit rate, context use
- Subagent rows: type, model, tokens, spend, and cache hit rate per subagent
- Hooks: one log line per subagent and per session (tokens, cache hit rate, spend) for the next review cycle

Planned: usage review skill, coding agents.

Install the log hooks (Claude Code 2.1.275 or later):

```
/plugin install worktools --marketplace atsu-mada/claude-work-toolkit
```

Then add the status lines with `src/setup/install.py`.

- Changes by release (Japanese): [docs/changes.md](docs/changes.md)
- Setup: [docs/setup.md](docs/setup.md)
- What is measured and how: [docs/metrics.md](docs/metrics.md)
- Why Haiku is routed this way (measurements): [docs/decisions/2026-10-26_haiku-routing.md](docs/decisions/2026-10-26_haiku-routing.md)
