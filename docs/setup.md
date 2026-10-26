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

## 4. Optional environment variables

| Variable | Default | Use |
| --- | --- | --- |
| `CODE_SURVEY_LOG_DIR` | `~/.local/share/code-survey/logs` | Where logs are written |
| `CODE_SURVEY_STATE_DIR` | `~/.cache/code-survey` | Read offsets and status snapshots |
| `CODE_SURVEY_LABEL` | empty | Label for a run, e.g. `auth-survey` |
| `CODE_SURVEY_USDJPY` | fetched once a day | Fixed USD to JPY rate; `0` shows dollars |
| `CODE_SURVEY_NO_FX` | unset | `1` disables the rate fetch (dollars shown) |
| `CODE_SURVEY_PRICING` | plugin `config/pricing.json` | Another pricing table |

## Company machines

- If the organization sets `allowManagedHooksOnly` or `disableAllHooks`, custom status lines and plugin hooks
  do not run. Ask the administrator.
- The rate fetch calls `api.frankfurter.dev`. Set `CODE_SURVEY_NO_FX=1` if outbound calls are not allowed.
