# Setup

Requirements: Claude Code CLI (v2.1.293 or later for `agentType` in subagent rows), Python 3.9+ as `python3`.

## 1. Get the kit

```bash
git clone https://github.com/atsu-mada/code-survey-kit.git ~/code-survey-kit
```

## 2. Install the plugin (log hooks)

```bash
claude plugin marketplace add ~/code-survey-kit
claude plugin install code-survey@code-survey-kit
```

For a one-off test without installing: `claude --plugin-dir ~/code-survey-kit/src/plugin/code-survey`.

## 3. Add the status lines

Plugins cannot set the parent status line, so a script writes it into the settings file:

```bash
python3 ~/code-survey-kit/src/setup/install.py --dry-run   # show the change
python3 ~/code-survey-kit/src/setup/install.py             # write ~/.claude/settings.json (backup first)
```

Options: `--target <file>` for another settings file, `--python <path>`, `--refresh <seconds>` (default 5),
`--force` to replace another status line, `--uninstall` to remove ours.
The status line scripts run from the cloned folder, so keep it in place.

## 4. Install the `code-survey` command (modes)

```bash
python3 ~/code-survey-kit/src/setup/install.py --launcher --no-statusline   # links ~/.local/bin/code-survey
code-survey --list
```

| Mode | Aliases | Main session | Subagents | Use for |
| --- | --- | --- | --- | --- |
| `eco` (エコ) | `c`, `haiku`, `economy` | Haiku | Haiku | most surveys and routine development |
| `balanced` (バランス) | `b`, `sonnet-haiku`, `standard` | Sonnet | Haiku | design decisions, risky changes, final reviews |

- `code-survey` with no mode asks in the terminal (no default). Without a terminal it exits with code 2.
- The mode is passed with `--model` and `--settings` (env `CLAUDE_CODE_SUBAGENT_MODEL`, `..._FORCE=1`,
  `CODE_SURVEY_MODE`), so nothing is written to your settings files. Logs record the mode.
- Plain `claude` with the plugin: the first prompt is held once and the modes are shown; send it again to
  continue without a mode. `claude -p` without a mode is refused.
- Rename or add modes in `src/plugin/code-survey/config/modes.json`.

## 5. Fixed routing without the launcher (optional)

A plugin cannot set environment variables, so the routing goes into a settings file:

```bash
python3 ~/code-survey-kit/src/setup/install.py --profile haiku-subagents   # every subagent on Haiku
python3 ~/code-survey-kit/src/setup/install.py --profile haiku-all         # main session on Haiku too
```

- `haiku-subagents` sets `CLAUDE_CODE_SUBAGENT_MODEL=haiku` and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`.
  Without FORCE the built-in Explore keeps the main session's model (measured).
- `haiku-all` also sets `"model": "haiku"`. Start with it for surveys; switch a session to Sonnet with
  `--model sonnet` when a question needs more judgment.
- Use `--target .claude/settings.json` to apply it to one repository only. `--uninstall` removes only what
  the script set (recorded in `<target>.code-survey.json`).
- Check: the subagent rows of the status line show the model; the logs record it per subagent.

Paste [config/templates/CLAUDE.survey.md](../config/templates/CLAUDE.survey.md) into the CLAUDE.md of the
repository you survey (or into `~/.claude/CLAUDE.md`).

Then run a survey: `/code-survey:survey` or ask "survey this repository with the code-survey skill".

## 6. Optional environment variables

| Variable | Default | Use |
| --- | --- | --- |
| `CODE_SURVEY_LOG_DIR` | `~/.local/share/code-survey/logs` | Where logs are written |
| `CODE_SURVEY_STATE_DIR` | `~/.cache/code-survey` | Read offsets and status snapshots |
| `CODE_SURVEY_LABEL` | empty | Label for a run, e.g. `auth-survey` |
| `CODE_SURVEY_USDJPY` | fetched once a day | Fixed USD to JPY rate; `0` shows dollars |
| `CODE_SURVEY_NO_FX` | unset | `1` disables the rate fetch (dollars shown) |
| `CODE_SURVEY_PRICING` | plugin `config/pricing.json` | Another pricing table |

## Company machines

- `haiku` means Haiku 5.5 on the Anthropic API (Claude Code 2.1.293 or later). Through Bedrock, Google Cloud,
  or Foundry it resolves to Haiku 4.5, which is weaker and has no effort setting.
- If the organization restricts models with `availableModels`, Haiku may be blocked. Check
  `ANTHROPIC_DEFAULT_HAIKU_MODEL` too: if it points at another model, `haiku` is not Haiku.

- If the organization sets `allowManagedHooksOnly` or `disableAllHooks`, custom status lines and plugin hooks
  do not run. Ask the administrator.
- The rate fetch calls `api.frankfurter.dev`. Set `CODE_SURVEY_NO_FX=1` if outbound calls are not allowed.
