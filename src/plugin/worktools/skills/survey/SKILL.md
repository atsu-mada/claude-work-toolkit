---
name: survey
description: Survey a codebase on a small budget - split it into modules, have the Haiku surveyor subagent read each module and write a JSON note, then combine the notes. Use when asked to investigate, map, or explain a codebase or a large part of it.
---

# Code survey on a small budget

The main session plans and combines. The `worktools:surveyor` subagent (Haiku) does all the reading.
Never read source files in the main session beyond a quick look at the top-level layout.

## 1. Plan (main session)

1. Get the layout cheaply: `git ls-files | head -200` and the top-level README or manifest only.
2. Split the code into 3 to 8 modules of similar size. A module is a directory or a group of files that
   one reader can cover in about 80,000 tokens.
3. For each module write 2 to 5 concrete questions (what it does, its entry points, how it talks to the
   other modules, anything the user asked about). For a module with configuration files, always ask
   "which keys are read by the code, which are defined but unused, and which are overridden by
   hardcoded values".
4. Choose the output folder: `survey/<YYYY-MM-DD>/` in the repository unless the user names another place.

Small repositories (under about 30 files or 3,000 lines): skip the subagents and read directly.
Delegation costs a fresh start for every subagent and only pays off when there is a lot to read.

## 2. Read (subagents)

For each module, call `worktools:surveyor` with:

```
module: <path>
questions:
- ...
note_path: survey/<date>/notes/<module-slug>.json
language: <the language the user writes in, e.g. Japanese>
```

- Run independent modules in parallel, at most 4 at a time.
- Do not pass a model; the agent definition sets Haiku.
- Use `worktools:locator` for single "where is X" lookups.
- Keep each subagent's reply out of your own reasoning beyond its 5-line summary. Open a note file only
  when you need a specific detail.

## 3. Combine (main session)

1. Read the notes (they are short JSON).
2. Write `survey/<date>/summary.json` (text in the user's language):
   `{"repository": "", "date": "", "overview": "", "modules": [{"slug": "", "summary": ""}],
   "cross_module": [{"from": "", "to": "", "how": ""}], "risks": [""], "open_questions": [""]}`
3. If a note has `open_questions` that block the user's question, send one more surveyor call for just
   those questions. Do not re-read whole modules.

## 4. HTML report

A hook builds `report.html` automatically every time `summary.json` is written (no model tokens; the
design follows the awesome-design-skills system). Run the script yourself only to add options or when the
hook reported a failure:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render_report.py" survey/<date>
```

- It writes `survey/<date>/report.html` from `summary.json` and `notes/*.json`.
- Add `--source-url https://<host>/<org>/<repo>/blob/<branch>/` to turn every `file:line` into a link.
- Do not write or edit the report HTML yourself. If the user wants a different layout or another HTML
  page, invoke `/awesome-design-skills` first and follow it, then change the script, not one report.

## 5. Tell the user

Give the overview in a few lines and the path of `report.html`, plus the notes folder.

## Budget rules

- Do not change the model, MCP servers, or CLAUDE.md during the survey: each change rebuilds the cache.
- Use `/clear` between surveys of different repositories.
- Check the status line: if the subagent share is high and the cache hit rate is low, tell the user.
